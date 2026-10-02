<script setup lang="ts">
/**
 * Stations for one map.
 *
 * Map first, then points. A station's coordinates only mean something in one
 * frame, so there is no view of "all stations" — that would invite reading one
 * site's poses against another's image, and the result looks entirely plausible.
 *
 * Two ways to place one, and they are not equivalent:
 *
 *   By clicking the map, which is fast and accurate to about a cell.
 *   By driving a robot there and capturing its pose, which is accurate to
 *   whatever the robot's localisation is — and, more importantly, provably
 *   reachable. A dock the robot cannot actually stop at is not a dock.
 *
 * Nothing here changes what a robot is doing. Opening this page does not start
 * navigation and leaving it does not stop it.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  Crosshair,
  MapPin,
  PanelRightClose,
  PanelRightOpen,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useMapStore } from '@/stores/maps'
import { useFleetStore } from '@/stores/fleet'
import { useStationStore } from '@/stores/stations'
import { useLinkStore } from '@/stores/links'
import { useMissionStore } from '@/stores/missions'
import { RouterLink } from 'vue-router'
import { useRobotTelemetry } from '@/features/mapping/useRobotTelemetry'
import { mapsApi } from '@/shared/api/maps'
import { StationInUseError } from '@/shared/api/stations'
import { decodePgm, type Grid } from '@/domain/map/pgm'
import { radToDeg } from '@/domain/ros/quaternion'
import { type Station, type StationType } from '@/domain/types'
import { STATION_TYPE_LIST, STATION_TYPE_STYLE } from '../stationType'
import StationMapCanvas from '../components/StationMapCanvas.vue'
import { missionsByStation } from '../stationUsage'
import { Button } from '@/shared/ui/button'
import { Select } from '@/shared/ui/select'
import { RowActions, RowActionItem, RowActionSeparator } from '@/shared/ui/menu'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Dialog } from '@/shared/ui/dialog'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { cn } from '@/shared/lib/utils'

const maps = useMapStore()
const fleet = useFleetStore()
const links = useLinkStore()
const stations = useStationStore()
const missions = useMissionStore()

const selectedMapId = ref<string | null>(null)
const grid = ref<Grid | null>(null)
const mapLoading = ref(false)
const mapError = ref<string | null>(null)

const selectedId = ref<string | null>(null)
const placing = ref(false)
/**
 * Collapsed to a strip on request; the map is what the screen is for.
 *
 * Starts collapsed below 1024px: next to the sidebar the open list left the
 * map half the screen.
 */
function wideScreen(): boolean {
  try {
    return window.matchMedia?.('(min-width: 1024px)')?.matches ?? true
  } catch {
    return true
  }
}
const panelOpen = ref(wideScreen())

/** Missions on this map, by the stations they visit. */
const usage = computed(() => missionsByStation(missions.missions))

function usedBy(stationId: string) {
  return usage.value.get(stationId) ?? []
}

/** Which robot to read a pose from. Only one is watched, and only on request. */
const teachRobotId = ref<string | null>(null)
const telemetry = useRobotTelemetry(() => teachRobotId.value ?? '')

const form = ref<{
  open: boolean
  editing: Station | null
  name: string
  type: StationType
  x: number
  y: number
  yaw: number
  note: string
  taughtByRobotId: string | null
}>({
  open: false,
  editing: null,
  name: '',
  type: 'pick',
  x: 0,
  y: 0,
  yaw: 0,
  note: '',
  taughtByRobotId: null,
})
const saving = ref(false)
const formError = ref<string | null>(null)
const pendingRemoval = ref<Station | null>(null)
const removing = ref(false)

/** Every version is listed: each one carries its own stations. */
const mapChoices = computed(() => maps.maps)

const mapOptions = computed(() =>
  mapChoices.value.map((map) => ({
    value: map.id,
    label: `${map.name} v${map.version}`,
    hint: map.note ?? undefined,
  })),
)

const selectedMap = computed(() =>
  selectedMapId.value ? maps.byId(selectedMapId.value) : null,
)

const placement = computed(() => ({
  resolution: selectedMap.value?.resolution ?? 0.05,
  originX: selectedMap.value?.originX ?? 0,
  originY: selectedMap.value?.originY ?? 0,
}))

/**
 * Robots assigned to the selected map.
 *
 * Only these can teach a pose: a robot running a different map reports its
 * position in that map's frame, and the number would be accepted without
 * complaint while naming the wrong place entirely.
 */
const teachCandidates = computed(() =>
  fleet.robots.filter(
    (robot) => robot.activeMapId === selectedMapId.value && links.stateFor(robot.id) === 'online',
  ),
)

const teachOptions = computed(() =>
  teachCandidates.value.map((robot) => ({ value: robot.id, label: robot.name })),
)

const robotPose = computed(() => {
  const pose = telemetry.pose.value
  if (!pose || !teachRobotId.value) return null
  return { x: pose.x, y: pose.y, yaw: pose.theta }
})

async function loadMapImage(mapId: string) {
  mapLoading.value = true
  mapError.value = null
  grid.value = null
  try {
    grid.value = decodePgm(await mapsApi.fetchFile(mapId, 'image'))
  } catch (error) {
    mapError.value = error instanceof Error ? error.message : String(error)
  } finally {
    mapLoading.value = false
  }
}

async function selectMap(mapId: string) {
  selectedMapId.value = mapId
  selectedId.value = null
  placing.value = false
  teachRobotId.value = null
  // Missions too: they say which stations cannot be deleted. Failing to load
  // them only loses that hint — the server still refuses the delete.
  await Promise.all([
    loadMapImage(mapId),
    stations.load(mapId),
    missions.load(mapId).catch(() => undefined),
  ])
}

onMounted(async () => {
  await Promise.all([maps.load(), fleet.load()])
  const first = maps.maps[0]
  if (first) await selectMap(first.id)
})

// ── Placing and editing ──────────────────────────────────────────────────────

function openCreate(pose: { x: number; y: number; yaw?: number }, taughtBy: string | null = null) {
  form.value = {
    open: true,
    editing: null,
    name: '',
    type: 'pick',
    x: pose.x,
    y: pose.y,
    yaw: pose.yaw ?? 0,
    note: '',
    taughtByRobotId: taughtBy,
  }
  formError.value = null
  placing.value = false
}

function openEdit(station: Station) {
  form.value = {
    open: true,
    editing: station,
    name: station.name,
    type: station.type,
    x: station.x,
    y: station.y,
    yaw: station.yaw,
    note: station.note ?? '',
    taughtByRobotId: station.taughtByRobotId,
  }
  formError.value = null
}

function teachFromRobot() {
  const pose = robotPose.value
  if (!pose) return
  openCreate(pose, teachRobotId.value)
}

const nameProblem = computed(() => {
  const name = form.value.name.trim()
  if (!name) return 'A name is required.'
  if (stations.nameTaken(name, form.value.editing?.id)) {
    return 'Another station on this map already uses this name.'
  }
  return null
})

async function onSubmit() {
  if (nameProblem.value || !selectedMapId.value) return
  saving.value = true
  formError.value = null
  try {
    const payload = {
      name: form.value.name.trim(),
      type: form.value.type,
      x: form.value.x,
      y: form.value.y,
      yaw: form.value.yaw,
      note: form.value.note.trim() || null,
    }
    if (form.value.editing) {
      const updated = await stations.update(form.value.editing.id, payload)
      toast.success(`Updated ${updated.name}`)
    } else {
      const created = await stations.create({
        mapId: selectedMapId.value,
        taughtByRobotId: form.value.taughtByRobotId,
        ...payload,
      })
      selectedId.value = created.id
      toast.success(`Added ${created.name}`)
    }
    form.value.open = false
  } catch (error) {
    formError.value = stations.describeError(error)
  } finally {
    saving.value = false
  }
}

/**
 * A dragged marker writes immediately.
 *
 * No confirmation, because the change is visible on the map and trivially
 * reversible by dragging back. Blocking every nudge behind a dialog would make
 * the one gesture this page exists for the slowest thing on it.
 */
let dragWrite: ReturnType<typeof setTimeout> | null = null
const dragPreview = ref<Map<string, { x: number; y: number }>>(new Map())

function onMove(payload: { id: string; x: number; y: number }) {
  // Shown at once, written after the drag settles: a pointer at 60 Hz would
  // otherwise issue sixty PATCHes per second.
  dragPreview.value = new Map(dragPreview.value).set(payload.id, { x: payload.x, y: payload.y })
  if (dragWrite) clearTimeout(dragWrite)
  dragWrite = setTimeout(async () => {
    try {
      await stations.update(payload.id, { x: payload.x, y: payload.y })
    } catch (error) {
      toast.error('Could not move the station', {
        description: stations.describeError(error),
      })
      if (selectedMapId.value) await stations.load(selectedMapId.value)
    } finally {
      const next = new Map(dragPreview.value)
      next.delete(payload.id)
      dragPreview.value = next
    }
  }, 250)
}

/** Stored positions with any in-flight drag applied on top. */
const shownStations = computed(() =>
  stations.stations.map((station) => {
    const moved = dragPreview.value.get(station.id)
    return moved ? { ...station, x: moved.x, y: moved.y } : station
  }),
)

/** Missions that keep the station being removed from being deleted. */
const removalBlockedBy = computed(() =>
  pendingRemoval.value ? usedBy(pendingRemoval.value.id) : [],
)

async function confirmRemoval() {
  const station = pendingRemoval.value
  if (!station) return
  removing.value = true
  try {
    await stations.remove(station.id)
    if (selectedId.value === station.id) selectedId.value = null
    toast.success(`Removed ${station.name}`)
    pendingRemoval.value = null
  } catch (error) {
    toast.error(`Could not remove ${station.name}`, {
      description: stations.describeError(error),
    })
    // A mission added since this page loaded: refresh, and the dialog turns
    // into the blocked version with links to the routes.
    if (error instanceof StationInUseError && selectedMapId.value) {
      await missions.load(selectedMapId.value).catch(() => undefined)
    }
  } finally {
    removing.value = false
  }
}

function robotName(id: string | null): string {
  if (!id) return '—'
  return fleet.robots.find((robot) => robot.id === id)?.name ?? 'retired robot'
}

watch(
  () => form.value.open,
  (open) => {
    if (!open) formError.value = null
  },
)

/**
 * Escape leaves placing mode.
 *
 * A sticky mode with no way out but clicking the button again is how an
 * operator ends up dropping a station they did not want. The dialog handles its
 * own Escape, so this only fires when nothing is on top.
 */
function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Escape' || form.value.open) return
  if (placing.value) placing.value = false
  else selectedId.value = null
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <!--
    The map is the page.

    Boxing a canvas inside a card, inside page padding, with a table beside it
    puts four layers of chrome around the one thing the screen exists for — and
    caps the map at whatever is left over. Every tool where placing things on a
    canvas is the job does it the other way round: the canvas fills the frame
    and the lists dock at its edge. That is the arrangement here.
  -->
  <div class="flex h-full min-h-0 flex-col">
    <div
      class="flex shrink-0 flex-wrap items-center gap-xs border-b border-hairline bg-surface px-base py-xs"
    >
      <MapPin :size="14" class="shrink-0 text-muted" />
      <Select
        v-if="mapOptions.length"
        label="Map"
        :model-value="selectedMapId"
        :options="mapOptions"
        class="min-w-[12rem]"
        @update:model-value="selectMap"
      />

      <Button
        :variant="placing ? 'primary' : 'outline'"
        size="sm"
        :disabled="!grid"
        @click="placing = !placing"
      >
        <Plus :size="13" />
        {{ placing ? 'Click the map…' : 'Add station' }}
      </Button>

      <!--
        Only robots on this exact map can teach a pose. One running a different
        map reports its position in that map's frame, and the number would be
        accepted while naming the wrong place.
      -->
      <div v-if="teachOptions.length" class="flex items-center gap-xxs">
        <Select
          label="Robot to capture a pose from"
          :model-value="teachRobotId"
          :options="teachOptions"
          placeholder="Teach from…"
          class="min-w-[9rem]"
          @update:model-value="teachRobotId = $event"
        />
        <Button size="sm" variant="outline" :disabled="!robotPose" @click="teachFromRobot">
          <Crosshair :size="13" />
          Capture
        </Button>
      </div>
      <!-- Shown even when nobody can use it, or nobody learns it exists. -->
      <Button
        v-else-if="grid"
        size="sm"
        variant="outline"
        disabled
        title="No robot is online on this map. Load this map on a robot to capture its pose."
      >
        <Crosshair :size="13" />
        Capture from robot
      </Button>
      <span v-if="grid && !teachOptions.length" class="hidden text-caption text-muted-soft xl:inline">
        No robot online on this map
      </span>
    </div>

    <div class="flex min-h-0 flex-1">
      <div class="relative min-w-0 flex-1">
        <EmptyState
          v-if="!mapChoices.length && !maps.loading"
          class="p-lg"
          title="No maps yet"
          description="A station is a pose in a map's frame, so there has to be a map first. Survey one or upload one."
        />
        <EmptyState
          v-else-if="mapError"
          class="p-lg"
          title="Cannot show this map"
          :description="mapError"
        />
        <div v-else-if="mapLoading" class="h-full w-full animate-pulse bg-hairline-soft" />

        <StationMapCanvas
          v-else
          :grid="grid"
          :placement="placement"
          :stations="shownStations"
          :selected-id="selectedId"
          :placing="placing"
          :robot-pose="robotPose"
          @place="openCreate"
          @select="selectedId = $event"
          @move="onMove"
        >
          <!-- Four colours on the map mean nothing without this. -->
          <template #legend>
            <span
              v-for="kind in STATION_TYPE_LIST"
              :key="kind.value"
              class="flex items-center gap-xxs"
            >
              <span class="h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: kind.colour }" />
              {{ kind.label }}
            </span>
            <span v-if="robotPose" class="flex items-center gap-xxs">
              <span class="h-2.5 w-2.5 rounded-full border-2 border-ink bg-surface" />
              Robot
            </span>
          </template>
        </StationMapCanvas>
      </div>

      <!--
        Docked, and collapsible to a strip. The list is reference material: it
        answers "what is this called" and "what are its numbers", which is not
        worth a fifth of the map on a narrow screen when nobody is reading it.
      -->
      <aside
        class="flex shrink-0 flex-col border-l border-hairline bg-surface transition-[width] duration-150"
        :class="panelOpen ? 'w-[18rem]' : 'w-[3rem]'"
      >
        <button
          type="button"
          class="flex h-11 shrink-0 items-center gap-xs border-b border-hairline px-sm text-body-sm text-body transition-colors hover:text-ink"
          :aria-expanded="panelOpen"
          :title="panelOpen ? 'Hide the station list' : 'Show the station list'"
          @click="panelOpen = !panelOpen"
        >
          <component :is="panelOpen ? PanelRightClose : PanelRightOpen" :size="15" class="shrink-0" />
          <template v-if="panelOpen">
            <span>Stations</span>
            <span class="ml-auto font-data text-caption text-muted">{{ stations.count }}</span>
          </template>
        </button>

        <div v-if="panelOpen" class="min-h-0 flex-1 overflow-y-auto scrollbar-thin p-xs">
          <EmptyState
            v-if="!stations.count"
            title="Nothing here yet"
            description="Add one on the map, or drive a robot to the spot and capture its pose."
          />

          <div v-else class="space-y-xxs">
            <div
              v-for="station in stations.stations"
              :key="station.id"
              :class="
                cn(
                  'flex items-start gap-xs rounded-control border p-xs transition-colors',
                  selectedId === station.id
                    ? 'border-primary bg-primary/[0.06]'
                    : 'border-transparent hover:border-hairline',
                )
              "
            >
              <button
                type="button"
                class="flex min-w-0 flex-1 items-start gap-xs text-left"
                @click="selectedId = station.id"
              >
                <span
                  class="mt-px flex h-6 w-6 shrink-0 items-center justify-center rounded-control text-white"
                  :style="{ backgroundColor: STATION_TYPE_STYLE[station.type].colour }"
                >
                  <component :is="STATION_TYPE_STYLE[station.type].icon" :size="13" />
                </span>
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-body-sm text-ink">{{ station.name }}</span>
                  <!-- The type in words: four colours are not a vocabulary. -->
                  <span class="block truncate text-caption text-muted">
                    {{ STATION_TYPE_STYLE[station.type].label }} ·
                    <span class="font-data">
                      {{ station.x.toFixed(2) }}, {{ station.y.toFixed(2) }} m ·
                      {{ Math.round(radToDeg(station.yaw)) }}°
                    </span>
                  </span>
                  <span
                    v-if="usedBy(station.id).length"
                    class="mt-xxs inline-block rounded-chip bg-surface-strong px-xxs text-caption text-muted"
                    :title="usedBy(station.id).map((m) => m.name).join(', ')"
                  >
                    {{ usedBy(station.id).length }} mission{{ usedBy(station.id).length === 1 ? '' : 's' }}
                  </span>
                  <!-- Only on the selected one: detail every row carries is not
                       detail, it is noise that makes the list twice as long. -->
                  <span
                    v-if="selectedId === station.id && (station.taughtByRobotId || station.note)"
                    class="mt-xxs block text-caption text-muted-soft"
                  >
                    {{
                      [
                        station.taughtByRobotId
                          ? `Taught by ${robotName(station.taughtByRobotId)}`
                          : null,
                        station.note,
                      ]
                        .filter(Boolean)
                        .join(' · ')
                    }}
                  </span>
                </span>
              </button>

              <RowActions :label="`More actions for ${station.name}`">
                <RowActionItem :icon="Pencil" @select="openEdit(station)">Edit</RowActionItem>
                <RowActionSeparator class="my-xxs h-px bg-hairline" />
                <RowActionItem :icon="Trash2" destructive @select="pendingRemoval = station">
                  Remove
                </RowActionItem>
              </RowActions>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <Dialog
      :open="form.open"
      :title="form.editing ? `Edit ${form.editing.name}` : 'New station'"
      description="The pose is in this map's frame, in metres and degrees. Nothing is sent to a robot by saving it."
      @update:open="(value: boolean) => !saving && (form.open = value)"
    >
      <form class="space-y-base" @submit.prevent="onSubmit">
        <FormField label="Name" required :error="formError ?? nameProblem ?? undefined">
          <template #default="{ id, invalid }">
            <Input :id="id" v-model="form.name" :invalid="invalid" placeholder="Dock 1" />
          </template>
        </FormField>

        <div class="space-y-xxs">
          <p class="text-label uppercase text-muted">Type</p>
          <div class="flex flex-wrap gap-xxs">
            <button
              v-for="kind in STATION_TYPE_LIST"
              :key="kind.value"
              type="button"
              :title="kind.hint"
              :aria-pressed="form.type === kind.value"
              :class="
                cn(
                  'flex items-center gap-xs rounded-control border px-sm py-xxs text-body-sm transition-colors',
                  form.type === kind.value
                    ? 'border-primary bg-primary/10 text-ink'
                    : 'border-hairline text-body hover:border-primary',
                )
              "
              @click="form.type = kind.value"
            >
              <span class="h-3 w-3 rounded-[3px]" :style="{ backgroundColor: kind.colour }" />
              {{ kind.label }}
            </button>
          </div>
        </div>

        <div class="grid grid-cols-3 gap-xs">
          <FormField label="X (m)" required>
            <template #default="{ id }">
              <Input
                :id="id"
                :model-value="form.x"
                type="number"
                step="0.01"
                @update:model-value="form.x = Number($event)"
              />
            </template>
          </FormField>
          <FormField label="Y (m)" required>
            <template #default="{ id }">
              <Input
                :id="id"
                :model-value="form.y"
                type="number"
                step="0.01"
                @update:model-value="form.y = Number($event)"
              />
            </template>
          </FormField>
          <FormField label="Heading (°)" required hint="Which way the robot faces on arrival.">
            <template #default="{ id }">
              <Input
                :id="id"
                :model-value="Math.round(radToDeg(form.yaw))"
                type="number"
                step="1"
                @update:model-value="form.yaw = (Number($event) * Math.PI) / 180"
              />
            </template>
          </FormField>
        </div>

        <FormField label="Note" hint="Why this spot, for whoever inherits the site.">
          <template #default="{ id }">
            <Input :id="id" v-model="form.note" placeholder="Bench by the shutter" />
          </template>
        </FormField>
      </form>

      <template #footer>
        <Button variant="secondary" size="sm" :disabled="saving" @click="form.open = false">
          Cancel
        </Button>
        <Button size="sm" :disabled="Boolean(nameProblem) || saving" @click="onSubmit">
          {{ saving ? 'Saving…' : form.editing ? 'Save' : 'Add station' }}
        </Button>
      </template>
    </Dialog>

    <!--
      The server refuses to delete a station a mission still names, so a
      station in use is not offered for deletion: the dialog names the routes
      and links to them instead.
    -->
    <ConfirmDialog
      :open="pendingRemoval !== null"
      destructive
      :pending="removing"
      :title="`Remove ${pendingRemoval?.name ?? ''}?`"
      :description="
        removalBlockedBy.length
          ? `${removalBlockedBy.map((m) => m.name).join(', ')} still ${removalBlockedBy.length === 1 ? 'visits' : 'visit'} this station. Take it out of ${removalBlockedBy.length === 1 ? 'that mission' : 'those missions'} first.`
          : 'No mission uses this station. Robots keep their copy until their stations are next pushed.'
      "
      :blocked="removalBlockedBy.length > 0"
      confirm-label="Remove"
      @update:open="(value: boolean) => !value && !removing && (pendingRemoval = null)"
      @cancel="pendingRemoval = null"
      @confirm="confirmRemoval"
    >
      <template v-if="removalBlockedBy.length" #actions>
        <Button
          v-for="mission in removalBlockedBy.slice(0, 3)"
          :key="mission.id"
          size="sm"
          variant="secondary"
          as-child
        >
          <RouterLink :to="`/mission/edit/${mission.id}`">Edit {{ mission.name }}</RouterLink>
        </Button>
      </template>
    </ConfirmDialog>
  </div>
</template>
