<script setup lang="ts">
/**
 * The steps of one route, in order.
 *
 * A step is one station plus what to do there, and maps exactly onto one
 * MissionPlan goal — so nothing in the ROS contract has to change: the robot's
 * agent sends one goal per step and advances when it completes.
 *
 * Steps are saved as a whole list, never row by row. The thing being edited is
 * an *order*, and patching rows individually means shuffling positions past a
 * uniqueness rule with every intermediate state having to be legal.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  ListOrdered,
  Plus,
  Save,
  Trash2,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useMapStore } from '@/stores/maps'
import { useStationStore } from '@/stores/stations'
import { useMissionStore } from '@/stores/missions'
import { useUiStore } from '@/stores/ui'
import { missionsApi } from '@/shared/api/missions'
import { mapsApi } from '@/shared/api/maps'
import { decodePgm, type Grid } from '@/domain/map/pgm'
import {
  STEP_CONFIRMS,
  STEP_TASK_LABEL,
  STEP_TASKS,
  type Mission,
  type StepConfirm,
  type StepDraft,
  type StepTask,
  type StationType,
} from '@/domain/types'
import { STATION_TYPE_STYLE } from '@/features/stations/stationType'
import MissionRouteMap from '../components/MissionRouteMap.vue'
import { Skeleton } from '@/shared/ui/skeleton'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import BlockedTip from '@/shared/components/BlockedTip.vue'
import CollapsibleSection from '@/shared/components/CollapsibleSection.vue'
import { usePermission } from '@/shared/composables/usePermission'
import { cn } from '@/shared/lib/utils'

const route = useRoute()
const router = useRouter()
const maps = useMapStore()
const stations = useStationStore()
const missions = useMissionStore()
const ui = useUiStore()
// Without the admin role the page is a read-only view of the route.
const { canEdit, editBlocker } = usePermission()

const missionId = computed(() => String(route.params.missionId ?? ''))

const mission = ref<Mission | null>(null)
const name = ref('')
const note = ref('')
const steps = ref<StepDraft[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const saving = ref(false)
const saveError = ref<string | null>(null)
const confirmLeave = ref(false)

/**
 * What was loaded, to tell an edited route from an untouched one.
 *
 * A ref, not a plain variable: `isDirty` is first computed while the page is
 * still loading, and a plain variable assigned afterwards never invalidates it
 * — the page opened already saying "Unsaved changes".
 */
const baseline = ref('')

function snapshot(): string {
  return JSON.stringify({
    name: name.value.trim(),
    note: note.value.trim(),
    steps: steps.value.map((step) => [step.stationId, step.task, step.confirm, step.note]),
  })
}

const isDirty = computed(() => snapshot() !== baseline.value)

/** One rule for both Save buttons, the toolbar's and the phone's sticky one. */
const saveDisabled = computed(
  () =>
    !canEdit.value ||
    !isDirty.value ||
    Boolean(nameProblem.value) ||
    brokenSteps.value.length > 0 ||
    saving.value,
)

/**
 * On a phone the toolbar Save scrolls away with the steps it saves; a bar at
 * the bottom keeps it in reach while there is something to save.
 */
const showSaveBar = computed(
  () => ui.screen === 'phone' && canEdit.value && (isDirty.value || saving.value),
)

const stationOptions = computed(() =>
  stations.stations.map((station) => ({
    value: station.id,
    label: station.name,
    hint: STATION_TYPE_STYLE[station.type].label,
  })),
)

function stationName(id: string): string {
  return stations.byId(id)?.name ?? 'missing station'
}

function stationColour(id: string): string {
  const station = stations.byId(id)
  return station ? STATION_TYPE_STYLE[station.type].colour : 'rgb(128,132,140)'
}

let nextKey = 0
function makeKey(): string {
  nextKey += 1
  return `s${nextKey}`
}

async function load() {
  loading.value = true
  loadError.value = null
  try {
    const found = await missionsApi.get(missionId.value)
    mission.value = found
    name.value = found.name
    note.value = found.note ?? ''
    steps.value = found.steps.map((step) => ({
      key: makeKey(),
      stationId: step.stationId,
      task: step.task,
      confirm: step.confirm,
      note: step.note,
    }))
    if (!maps.loaded) await maps.load()
    // The station list is the source for every picker on this page, and it is
    // scoped to the route's own map — a station from elsewhere names a place in
    // a frame this route does not use.
    await stations.load(found.mapId)
    baseline.value = snapshot()
    // Not awaited: the steps are usable without the picture, and a large map
    // should not hold the whole page on a skeleton.
    void loadMapImage(found.mapId)
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── Map ──────────────────────────────────────────────────────────────────────

const grid = ref<Grid | null>(null)
const mapLoading = ref(true)
const mapError = ref<string | null>(null)

async function loadMapImage(mapId: string) {
  mapLoading.value = true
  mapError.value = null
  try {
    grid.value = decodePgm(await mapsApi.fetchFile(mapId, 'image'))
  } catch (error) {
    mapError.value = error instanceof Error ? error.message : String(error)
  } finally {
    mapLoading.value = false
  }
}

const placement = computed(() => {
  const map = mission.value ? maps.byId(mission.value.mapId) : null
  return {
    resolution: map?.resolution ?? 0.05,
    originX: map?.originX ?? 0,
    originY: map?.originY ?? 0,
  }
})

const routeIds = computed(() => steps.value.map((step) => step.stationId))

/** The station of the step being looked at, ringed on the map. */
const focusedStationId = ref<string | null>(null)

// ── Editing the list ─────────────────────────────────────────────────────────

/** What a step usually does at a station of this type; still editable after. */
const DEFAULT_TASK: Record<StationType, StepTask> = {
  pick: 'pick',
  drop: 'drop',
  pick_drop: 'none',
  charging: 'none',
}

function appendStep(stationId: string) {
  const station = stations.byId(stationId)
  steps.value = [
    ...steps.value,
    {
      key: makeKey(),
      stationId,
      task: station ? DEFAULT_TASK[station.type] : 'none',
      confirm: 'auto',
      note: null,
    },
  ]
}

function addStep() {
  // Start from where the route left off is no better a guess than the first
  // station, but a different stop from the last one usually is.
  const last = steps.value[steps.value.length - 1]?.stationId
  const next = stations.stations.find((station) => station.id !== last) ?? stations.stations[0]
  if (next) appendStep(next.id)
}

/** A click on the map adds that station as the next stop. */
function onMapSelect(stationId: string | null) {
  if (!stationId) return
  if (!canEdit.value) {
    focusedStationId.value = stationId
    return
  }
  appendStep(stationId)
  focusedStationId.value = stationId
  toast.success(`Step ${steps.value.length}: ${stationName(stationId)}`, { duration: 1500 })
}

function removeStep(key: string) {
  steps.value = steps.value.filter((step) => step.key !== key)
}

function move(index: number, by: number) {
  const target = index + by
  if (target < 0 || target >= steps.value.length) return
  const next = [...steps.value]
  const [moved] = next.splice(index, 1)
  if (moved) next.splice(target, 0, moved)
  steps.value = next
}

function patch(key: string, changes: Partial<StepDraft>) {
  steps.value = steps.value.map((step) => (step.key === key ? { ...step, ...changes } : step))
}

const nameProblem = computed(() => {
  const value = name.value.trim()
  if (!value) return 'A name is required.'
  if (missions.nameTaken(value, missionId.value)) {
    return 'This map already has a mission with that name.'
  }
  return null
})

/**
 * A step naming a station that no longer exists.
 *
 * The server refuses to delete a station a route uses, so this should be
 * impossible — but a route loaded in one tab while another deletes is not, and
 * a step pointing at nothing fails on the robot with "Unknown station_id" in
 * front of whoever is standing there.
 */
const brokenSteps = computed(() =>
  steps.value.filter((step) => stations.byId(step.stationId) === null),
)

const taskOptions = STEP_TASKS.map((task) => ({ value: task, label: STEP_TASK_LABEL[task] }))
const confirmOptions: { value: StepConfirm; label: string }[] = STEP_CONFIRMS.map((value) => ({
  value,
  label: value === 'auto' ? 'Continue' : 'Wait for confirm',
}))

async function save() {
  if (!canEdit.value || nameProblem.value || brokenSteps.value.length) return
  saving.value = true
  saveError.value = null
  try {
    await missions.update(missionId.value, {
      name: name.value.trim(),
      note: note.value.trim() || null,
      steps: steps.value,
    })
    baseline.value = snapshot()
    toast.success(`Saved ${name.value.trim()}`)
    void router.push('/mission')
  } catch (error) {
    saveError.value = missions.describeError(error)
  } finally {
    saving.value = false
  }
}

function leave() {
  if (!isDirty.value) {
    void router.push('/mission')
    return
  }
  confirmLeave.value = true
}

function onBeforeUnloadGuard(event: BeforeUnloadEvent) {
  if (!isDirty.value) return
  event.preventDefault()
}

onMounted(() => window.addEventListener('beforeunload', onBeforeUnloadGuard))
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnloadGuard))

watch(
  () => steps.value.length,
  () => {
    saveError.value = null
  },
)
</script>

<template>
  <div class="p-sm sm:p-base md:p-lg">
    <EmptyState v-if="loadError" title="Cannot edit this mission" :description="loadError">
      <template #action>
        <Button size="sm" variant="secondary" as-child>
          <RouterLink to="/mission">Back to missions</RouterLink>
        </Button>
      </template>
    </EmptyState>

    <Card v-else>
      <PanelToolbar
        :title="mission ? `${canEdit ? 'Edit' : 'View'} ${mission.name}` : 'Edit mission'"
        :subtitle="`${steps.length} step${steps.length === 1 ? '' : 's'}`"
      >
        <template #icon><ListOrdered :size="14" class="shrink-0 text-muted" /></template>
        <template #actions>
          <span
            class="hidden font-data text-caption sm:inline"
            :class="isDirty ? 'text-status-act' : 'text-muted-soft'"
          >
            {{ isDirty ? 'Unsaved changes' : 'Saved' }}
          </span>
          <BlockedTip :reason="editBlocker">
            <Button size="sm" :disabled="saveDisabled" @click="save">
              <Save :size="13" /> {{ saving ? 'Saving…' : 'Save' }}
            </Button>
          </BlockedTip>
          <Button variant="ghost" size="sm" aria-label="Back to missions" @click="leave">
            <ArrowLeft :size="14" /> <span class="hidden sm:inline">Missions</span>
          </Button>
        </template>
      </PanelToolbar>

      <CardContent>
        <div v-if="loading" class="grid gap-base xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div class="space-y-base">
            <div class="grid gap-base md:grid-cols-2">
              <div class="space-y-xs">
                <Skeleton class="h-3 w-12" /><Skeleton class="h-9 w-full" />
              </div>
              <div class="space-y-xs">
                <Skeleton class="h-3 w-12" /><Skeleton class="h-9 w-full" />
              </div>
            </div>
            <Skeleton class="h-3 w-24" />
            <div
              v-for="row in 3"
              :key="row"
              class="flex items-center gap-sm rounded-control border border-hairline p-sm"
            >
              <Skeleton class="h-6 w-6" />
              <Skeleton class="h-9 flex-1" />
              <Skeleton class="h-9 w-32" />
              <Skeleton class="h-9 w-36" />
            </div>
          </div>
          <Skeleton class="h-[24rem] w-full rounded-surface xl:h-[32rem]" />
        </div>

        <div v-else class="grid items-start gap-base xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div class="min-w-0 space-y-base">
            <p v-if="!canEdit" class="text-caption text-muted">
              View only — editing missions needs the admin role.
            </p>
            <div class="grid gap-base md:grid-cols-2">
              <FormField label="Name" required :error="saveError ?? nameProblem ?? undefined">
                <template #default="{ id, invalid }">
                  <Input :id="id" v-model="name" :invalid="invalid" :disabled="!canEdit" />
                </template>
              </FormField>
              <FormField label="Note" hint="What this route is for.">
                <template #default="{ id }">
                  <Input
                    :id="id"
                    v-model="note"
                    placeholder="Morning shuttle from the dock"
                    :disabled="!canEdit"
                  />
                </template>
              </FormField>
            </div>

            <div class="space-y-xs">
              <div class="flex items-center gap-sm">
                <p class="text-label uppercase text-muted">Steps</p>
                <span class="hidden truncate text-caption text-muted-soft sm:inline">
                  The robot visits these in order, one goal per step.
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  class="ml-auto"
                  :disabled="!canEdit || !stations.count"
                  @click="addStep"
                >
                  <Plus :size="13" /> Add step
                </Button>
              </div>

              <EmptyState
                v-if="!stations.count"
                title="This map has no stations"
                description="A step goes to a station, so there has to be one first."
              >
                <template #action>
                  <Button size="sm" variant="secondary" as-child>
                    <RouterLink to="/station">Add stations</RouterLink>
                  </Button>
                </template>
              </EmptyState>

              <EmptyState
                v-else-if="!steps.length"
                title="No steps yet"
                :description="canEdit ? 'Click a station on the map, or use Add step.' : undefined"
              />

              <div
                v-for="(step, index) in steps"
                v-else
                :key="step.key"
                class="flex flex-wrap items-start gap-sm rounded-control border p-sm transition-colors md:flex-nowrap"
                :class="
                  stations.byId(step.stationId) === null
                    ? 'border-status-fault/50 bg-status-fault/[0.04]'
                    : focusedStationId === step.stationId
                      ? 'border-primary/50 bg-primary/[0.03]'
                      : 'border-hairline'
                "
                @mouseenter="focusedStationId = step.stationId"
                @focusin="focusedStationId = step.stationId"
              >
                <span
                  class="mt-[6px] flex h-6 w-6 shrink-0 items-center justify-center rounded-control font-data text-caption text-white"
                  :style="{ backgroundColor: stationColour(step.stationId) }"
                >
                  {{ index + 1 }}
                </span>

                <!--
                  Station on its own line, then what happens there. Three selects
                  side by side were switched on by the screen width, but the step
                  list only ever gets part of the screen — at 1024px each select
                  was cut to a single letter. Two rows fit any width the column has.

                  The second-row labels are visible: "Pass through" and
                  "Continue" read as nothing without saying what they answer.
                -->
                <div class="grid min-w-0 flex-1 grid-cols-2 gap-x-xs gap-y-xxs">
                  <Select
                    label="Station"
                    :model-value="step.stationId"
                    :options="stationOptions"
                    class="col-span-2 w-full"
                    :disabled="!canEdit"
                    @update:model-value="patch(step.key, { stationId: $event })"
                  />
                  <span class="mt-xxs text-caption text-muted" aria-hidden="true"
                    >At the station</span
                  >
                  <span class="mt-xxs text-caption text-muted" aria-hidden="true">Then</span>
                  <Select
                    label="At the station"
                    :model-value="step.task"
                    :options="taskOptions"
                    class="w-full"
                    :disabled="!canEdit"
                    @update:model-value="patch(step.key, { task: $event as StepTask })"
                  />
                  <Select
                    label="Then"
                    :model-value="step.confirm"
                    :options="confirmOptions"
                    class="w-full"
                    :disabled="!canEdit"
                    @update:model-value="patch(step.key, { confirm: $event as StepConfirm })"
                  />
                  <p
                    v-if="stations.byId(step.stationId) === null"
                    class="col-span-2 text-caption text-status-fault"
                  >
                    {{ stationName(step.stationId) }} — pick another before saving.
                  </p>
                </div>

                <!-- Under the selects on a phone, where a side column would
                     leave them too narrow to read. -->
                <div
                  class="flex w-full shrink-0 justify-end border-t border-hairline pt-xs md:mt-[2px] md:w-auto md:justify-start md:border-0 md:pt-0"
                >
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    title="Move up"
                    :disabled="!canEdit || index === 0"
                    @click="move(index, -1)"
                  >
                    <ArrowUp :size="13" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    title="Move down"
                    :disabled="!canEdit || index === steps.length - 1"
                    @click="move(index, 1)"
                  >
                    <ArrowDown :size="13" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    title="Remove this step"
                    class="hover:text-status-fault"
                    :disabled="!canEdit"
                    @click="removeStep(step.key)"
                  >
                    <Trash2 :size="13" />
                  </Button>
                </div>
              </div>

              <p
                v-if="steps.some((s) => s.confirm === 'confirm')"
                :class="
                  cn(
                    'rounded-control border border-status-warn/40 bg-status-warn/10 p-sm text-caption text-body',
                  )
                "
              >
                A step set to wait for confirmation needs somebody standing there to press it — on
                every lap, if this route is ever set to loop.
              </p>
            </div>

            <div
              v-if="showSaveBar"
              class="sticky bottom-0 -mx-base flex items-center gap-sm border-t border-hairline bg-surface px-base py-sm md:hidden"
            >
              <span class="shrink-0 font-data text-caption text-status-act">
                {{ saving ? 'Saving…' : 'Unsaved changes' }}
              </span>
              <BlockedTip :reason="editBlocker" class="flex-1">
                <Button class="w-full" :disabled="saveDisabled" @click="save">
                  <Save :size="14" /> {{ saving ? 'Saving…' : 'Save' }}
                </Button>
              </BlockedTip>
            </div>
          </div>

          <!--
            On a phone the map sits under the steps and would push them a
            screen apart from the save bar; folded, its header still counts the
            stops. Tapping stations to build a route still works once opened.
          -->
          <CollapsibleSection
            v-if="ui.screen === 'phone'"
            title="Route map"
            :summary="`${steps.length} stop${steps.length === 1 ? '' : 's'}`"
          >
            <div class="relative h-[20rem] overflow-hidden rounded-surface border border-hairline">
              <MissionRouteMap
                :grid="grid"
                :placement="placement"
                :stations="stations.stations"
                :selected-id="focusedStationId"
                :route="routeIds"
                :loading="mapLoading"
                :error="mapError"
                :can-edit="canEdit"
                @select="onMapSelect"
              />
            </div>
          </CollapsibleSection>
          <!-- Sticky, so a long route can be scrolled while its shape stays in view. -->
          <div
            v-else
            class="relative h-[24rem] overflow-hidden rounded-surface border border-hairline xl:sticky xl:top-base xl:h-[calc(100vh-10rem)] xl:min-h-[28rem]"
          >
            <MissionRouteMap
              :grid="grid"
              :placement="placement"
              :stations="stations.stations"
              :selected-id="focusedStationId"
              :route="routeIds"
              :loading="mapLoading"
              :error="mapError"
              :can-edit="canEdit"
              @select="onMapSelect"
            />
          </div>
        </div>
      </CardContent>
    </Card>

    <ConfirmDialog
      :open="confirmLeave"
      destructive
      title="Leave without saving?"
      description="The steps you changed are not stored yet, so they are lost."
      confirm-label="Leave"
      @update:open="(value: boolean) => !value && (confirmLeave = false)"
      @cancel="confirmLeave = false"
      @confirm="router.push('/mission')"
    />
  </div>
</template>
