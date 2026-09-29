<script setup lang="ts">
/**
 * Routes on one map, and what is running right now.
 *
 * Map first, because a route names stations and a station's coordinates only
 * mean something in one frame. Dispatching to a robot on a different map is
 * refused by the server; the map selector is what stops it being offered.
 *
 * Nothing here executes a mission. Dispatch writes a run to the registry and
 * nudges the robot's agent, which is what actually sends goals — the previous
 * UI sequenced waypoints from tab memory, so closing the tab stranded a robot
 * mid-route with nobody left to send the next one.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ListOrdered, Pencil, Play, Plus, Square, Trash2, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useMapStore } from '@/stores/maps'
import { useFleetStore } from '@/stores/fleet'
import { useMissionStore } from '@/stores/missions'
import {
  isRunLive,
  RUN_MODE_LABEL,
  RUN_MODES,
  type MissionRun,
  type MissionSummary,
  type RunMode,
} from '@/domain/types'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Dialog } from '@/shared/ui/dialog'
import { Badge } from '@/shared/ui/badge'
import { RowActions, RowActionItem, RowActionSeparator } from '@/shared/ui/menu'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import { cn } from '@/shared/lib/utils'

const maps = useMapStore()
const fleet = useFleetStore()
const missions = useMissionStore()

const selectedMapId = ref<string | null>(null)

const mapOptions = computed(() =>
  maps.maps.map((map) => ({ value: map.id, label: `${map.name} v${map.version}` })),
)

const selectedMap = computed(() => (selectedMapId.value ? maps.byId(selectedMapId.value) : null))

async function selectMap(mapId: string) {
  selectedMapId.value = mapId
  await missions.load(mapId)
}

onMounted(async () => {
  await Promise.all([maps.load(), fleet.load()])
  const first = maps.maps[0]
  if (first) await selectMap(first.id)
})

/**
 * Poll only while something is live.
 *
 * Progress is written by the robot's agent, so the only way to see it move is
 * to ask. Polling an idle floor is traffic for a number that cannot change.
 */
let poll: ReturnType<typeof setInterval> | null = null

watch(
  () => missions.liveRuns.length,
  (live) => {
    if (live > 0 && poll === null) {
      poll = setInterval(() => void missions.refreshRuns(), 2000)
    } else if (live === 0 && poll !== null) {
      clearInterval(poll)
      poll = null
    }
  },
)

onBeforeUnmount(() => {
  if (poll !== null) clearInterval(poll)
})

function robotName(id: string | null): string {
  if (!id) return '—'
  return fleet.robots.find((robot) => robot.id === id)?.name ?? 'retired robot'
}

// ── Dispatch ─────────────────────────────────────────────────────────────────

const dispatching = ref<MissionSummary | null>(null)
const dispatchRobotId = ref<string | null>(null)
const dispatchMode = ref<RunMode>('once')
const dispatchLaps = ref(5)
const dispatchError = ref<string | null>(null)
const dispatchPending = ref(false)

/**
 * Only robots already on this map.
 *
 * Every station in the route names a place in this map's frame. A robot on a
 * different map would accept the numbers and drive somewhere else entirely, so
 * it is not offered rather than being offered and refused.
 */
const dispatchOptions = computed(() =>
  fleet.robots
    .filter((robot) => robot.activeMapId === selectedMapId.value)
    .map((robot) => {
      const busy = missions.runForRobot(robot.id)
      return {
        value: robot.id,
        label: robot.name,
        hint: busy ? `Running ${busy.missionName}` : undefined,
        disabled: Boolean(busy),
      }
    }),
)

const modeOptions = RUN_MODES.map((mode) => ({ value: mode, label: RUN_MODE_LABEL[mode] }))

function openDispatch(mission: MissionSummary) {
  dispatching.value = mission
  dispatchRobotId.value = dispatchOptions.value.find((option) => !option.disabled)?.value ?? null
  dispatchMode.value = 'once'
  dispatchError.value = null
}

/** A route with a step that waits for a person should not be left to loop. */
const loopNeedsSomeone = computed(
  () => dispatchMode.value !== 'once' && Boolean(dispatching.value?.note?.includes('confirm')),
)

async function confirmDispatch() {
  const mission = dispatching.value
  const robotId = dispatchRobotId.value
  if (!mission || !robotId) return
  dispatchPending.value = true
  dispatchError.value = null
  try {
    const run = await missions.dispatch({
      missionId: mission.id,
      robotId,
      mode: dispatchMode.value,
      lapsTarget: dispatchMode.value === 'laps' ? dispatchLaps.value : null,
    })
    toast.success(`${run.missionName} dispatched to ${robotName(robotId)}`, {
      description:
        run.mode === 'once'
          ? 'One pass.'
          : run.mode === 'laps'
            ? `${run.lapsTarget} laps.`
            : 'Runs until stopped.',
    })
    dispatching.value = null
  } catch (error) {
    dispatchError.value = missions.describeError(error)
  } finally {
    dispatchPending.value = false
  }
}

// ── Run control ──────────────────────────────────────────────────────────────

const stoppingRun = ref<MissionRun | null>(null)
const cancellingRun = ref<MissionRun | null>(null)
const runPending = ref(false)

async function stopAfterLap(run: MissionRun) {
  runPending.value = true
  try {
    await missions.stopAfterLap(run.id)
    toast.success(`${run.missionName} will stop after this lap`)
    stoppingRun.value = null
  } catch (error) {
    toast.error('Could not stop the run', { description: missions.describeError(error) })
  } finally {
    runPending.value = false
  }
}

async function cancelRun(run: MissionRun) {
  runPending.value = true
  try {
    await missions.cancel(run.id)
    toast.success(`${run.missionName} canceled`)
    cancellingRun.value = null
  } catch (error) {
    toast.error('Could not cancel the run', { description: missions.describeError(error) })
  } finally {
    runPending.value = false
  }
}

function lapLabel(run: MissionRun): string {
  if (run.mode === 'once') return 'single pass'
  if (run.mode === 'laps') return `lap ${run.lap} of ${run.lapsTarget}`
  return `lap ${run.lap}`
}

// ── Creating and removing ────────────────────────────────────────────────────

const createOpen = ref(false)
const newName = ref('')
const creating = ref(false)
const createError = ref<string | null>(null)

const newNameProblem = computed(() => {
  const name = newName.value.trim()
  if (!name) return 'A name is required.'
  if (missions.nameTaken(name)) return 'This map already has a mission with that name.'
  return null
})

async function createMission() {
  if (newNameProblem.value || !selectedMapId.value) return
  creating.value = true
  createError.value = null
  try {
    // Created empty, then filled in the editor: a route is an ordered list, and
    // a dialog is the wrong place to build one.
    const created = await missions.create({
      mapId: selectedMapId.value,
      name: newName.value.trim(),
      steps: [],
    })
    createOpen.value = false
    newName.value = ''
    toast.success(`Created ${created.name}`, { description: 'Add its steps next.' })
  } catch (error) {
    createError.value = missions.describeError(error)
  } finally {
    creating.value = false
  }
}

const pendingRemoval = ref<MissionSummary | null>(null)
const removing = ref(false)

async function confirmRemoval() {
  const mission = pendingRemoval.value
  if (!mission) return
  removing.value = true
  try {
    await missions.remove(mission.id)
    toast.success(`Removed ${mission.name}`)
    pendingRemoval.value = null
  } catch (error) {
    toast.error(`Could not remove ${mission.name}`, {
      description: missions.describeError(error),
    })
  } finally {
    removing.value = false
  }
}

watch(createOpen, (open) => {
  if (open) createError.value = null
})
</script>

<template>
  <div class="space-y-base p-lg">
    <!--
      What is happening on the floor, above the routes that describe it. An
      operator opening this page while a robot is moving wants that first.
    -->
    <Card v-if="missions.liveRuns.length">
      <PanelToolbar title="Running now" :subtitle="`${missions.liveRuns.length} in progress`">
        <template #icon><Play :size="14" class="shrink-0 text-status-run" /></template>
      </PanelToolbar>
      <CardContent class="space-y-xs">
        <div
          v-for="run in missions.liveRuns"
          :key="run.id"
          class="flex flex-wrap items-center gap-sm rounded-control border border-hairline p-sm"
        >
          <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-control bg-status-run/12 text-status-run">
            <Play :size="13" />
          </span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-body-md text-ink">{{ run.missionName }}</p>
            <p class="truncate font-data text-caption text-muted">
              {{ robotName(run.robotId) }} · step {{ run.stepIndex + 1 }} · {{ lapLabel(run) }}
            </p>
          </div>

          <!-- `stopping` is not a failure and not finished: it is a lap in
               progress that will be the last one. -->
          <Badge v-if="run.state === 'stopping'" class="bg-status-warn/12 text-status-warn">
            stopping after this lap
          </Badge>

          <Button
            v-if="run.state === 'running'"
            variant="outline"
            size="sm"
            :disabled="runPending"
            @click="stoppingRun = run"
          >
            <Square :size="13" /> Stop after lap
          </Button>
          <Button
            variant="ghost"
            size="sm"
            class="hover:text-status-fault"
            :disabled="runPending"
            @click="cancellingRun = run"
          >
            <X :size="13" /> Cancel
          </Button>
        </div>
      </CardContent>
    </Card>

    <Card>
      <PanelToolbar
        title="Missions"
        :subtitle="selectedMap ? `${missions.count} on ${selectedMap.name} v${selectedMap.version}` : 'Pick a map'"
      >
        <template #icon><ListOrdered :size="14" class="shrink-0 text-muted" /></template>
        <template #actions>
          <Select
            v-if="mapOptions.length"
            label="Map"
            :model-value="selectedMapId"
            :options="mapOptions"
            class="min-w-[12rem]"
            @update:model-value="selectMap"
          />
          <Button size="sm" :disabled="!selectedMapId" @click="createOpen = true">
            <Plus :size="13" /> New mission
          </Button>
        </template>
      </PanelToolbar>

      <CardContent>
        <EmptyState
          v-if="!mapOptions.length && !maps.loading"
          title="No maps yet"
          description="A mission names stations, and stations belong to a map. Survey one or upload one first."
        />

        <EmptyState
          v-else-if="!missions.count && !missions.loading"
          title="No missions on this map"
          description="A mission is an ordered route: pick at one station, drop at another. Create one and add its steps."
        />

        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead class="w-full max-w-0">Mission</TableHead>
              <TableHead class="whitespace-nowrap">Steps</TableHead>
              <TableHead class="whitespace-nowrap">Status</TableHead>
              <TableHead align="right">Actions</TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            <TableRow v-for="mission in missions.missions" :key="mission.id" interactive>
              <TableCell class="w-full max-w-0">
                <div class="min-w-0">
                  <span class="block truncate text-body-md text-ink">{{ mission.name }}</span>
                  <span
                    v-if="mission.note"
                    class="block truncate text-caption text-muted"
                    :title="mission.note"
                  >
                    {{ mission.note }}
                  </span>
                </div>
              </TableCell>

              <TableCell>
                <span
                  class="whitespace-nowrap font-data text-body-sm"
                  :class="mission.stepCount ? 'text-body' : 'text-status-warn'"
                >
                  {{ mission.stepCount || 'none yet' }}
                </span>
              </TableCell>

              <TableCell>
                <span class="whitespace-nowrap text-body-sm text-muted">
                  {{
                    missions.runs.find((r) => r.missionId === mission.id && isRunLive(r.state))
                      ? 'running'
                      : 'idle'
                  }}
                </span>
              </TableCell>

              <TableCell align="right">
                <div class="flex justify-end gap-xxs">
                  <!-- A route with no steps has nothing to send, so the button
                       says so rather than producing a server error. -->
                  <Button
                    variant="ghost"
                    size="sm"
                    :disabled="!mission.stepCount || !dispatchOptions.some((o) => !o.disabled)"
                    :title="
                      !mission.stepCount
                        ? 'Add steps before running this'
                        : `Run ${mission.name}`
                    "
                    @click="openDispatch(mission)"
                  >
                    <Play :size="13" /> Run
                  </Button>
                  <RowActions :label="`More actions for ${mission.name}`">
                    <RowActionItem :icon="Pencil" :to="`/mission/edit/${mission.id}`">
                      Edit steps
                    </RowActionItem>
                    <RowActionSeparator class="my-xxs h-px bg-hairline" />
                    <RowActionItem :icon="Trash2" destructive @select="pendingRemoval = mission">
                      Remove
                    </RowActionItem>
                  </RowActions>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <Dialog
      :open="createOpen"
      title="New mission"
      description="Name it now, add its steps next."
      @update:open="(value: boolean) => !creating && (createOpen = value)"
    >
      <form @submit.prevent="createMission">
        <FormField label="Name" required :error="createError ?? newNameProblem ?? undefined">
          <template #default="{ id, invalid }">
            <Input :id="id" v-model="newName" :invalid="invalid" placeholder="Shuttle A to B" />
          </template>
        </FormField>
      </form>
      <template #footer>
        <Button variant="secondary" size="sm" :disabled="creating" @click="createOpen = false">
          Cancel
        </Button>
        <Button size="sm" :disabled="Boolean(newNameProblem) || creating" @click="createMission">
          {{ creating ? 'Creating…' : 'Create' }}
        </Button>
      </template>
    </Dialog>

    <Dialog
      :open="dispatching !== null"
      :title="`Run ${dispatching?.name ?? ''}`"
      description="The robot executes this, not the browser — closing this page does not stop it."
      @update:open="(value: boolean) => !value && !dispatchPending && (dispatching = null)"
    >
      <form class="space-y-base" @submit.prevent="confirmDispatch">
        <FormField label="Robot" required hint="Only robots already on this map.">
          <template #default>
            <Select
              label="Robot"
              :model-value="dispatchRobotId"
              :options="dispatchOptions"
              placeholder="Pick a robot"
              class="w-full"
              @update:model-value="dispatchRobotId = $event"
            />
          </template>
        </FormField>

        <div class="space-y-xxs">
          <p class="text-label uppercase text-muted">How many times</p>
          <div class="flex flex-wrap gap-xxs">
            <button
              v-for="option in modeOptions"
              :key="option.value"
              type="button"
              :class="
                cn(
                  'rounded-control border px-sm py-xxs text-body-sm transition-colors',
                  dispatchMode === option.value
                    ? 'border-primary bg-primary/10 text-ink'
                    : 'border-hairline text-body hover:border-primary',
                )
              "
              @click="dispatchMode = option.value"
            >
              {{ option.label }}
            </button>
          </div>
          <p class="text-caption text-muted">
            <!-- Looping is chosen here, not stored on the route: the same route
                 is sometimes a one-off and sometimes a shift of shuttling. -->
            Looping is part of running it, not part of the route.
          </p>
        </div>

        <FormField v-if="dispatchMode === 'laps'" label="Laps" required>
          <template #default="{ id }">
            <Input
              :id="id"
              :model-value="dispatchLaps"
              type="number"
              min="1"
              @update:model-value="dispatchLaps = Math.max(1, Number($event))"
            />
          </template>
        </FormField>

        <p
          v-if="loopNeedsSomeone"
          class="rounded-control border border-status-warn/40 bg-status-warn/10 p-sm text-caption text-body"
        >
          This route has a step that waits for someone to confirm. Looping it means
          somebody has to be there every lap.
        </p>

        <p v-if="dispatchError" class="text-caption text-status-fault">{{ dispatchError }}</p>
      </form>

      <template #footer>
        <Button variant="secondary" size="sm" :disabled="dispatchPending" @click="dispatching = null">
          Cancel
        </Button>
        <Button size="sm" :disabled="!dispatchRobotId || dispatchPending" @click="confirmDispatch">
          {{ dispatchPending ? 'Starting…' : 'Run' }}
        </Button>
      </template>
    </Dialog>

    <ConfirmDialog
      :open="stoppingRun !== null"
      :pending="runPending"
      title="Stop after this lap?"
      description="The robot finishes the lap it is on and then stops. Stopping mid-lap can leave it holding a load it has not delivered — use the physical E-STOP for that."
      confirm-label="Stop after lap"
      @update:open="(value: boolean) => !value && !runPending && (stoppingRun = null)"
      @cancel="stoppingRun = null"
      @confirm="stoppingRun && stopAfterLap(stoppingRun)"
    />

    <ConfirmDialog
      :open="cancellingRun !== null"
      destructive
      :pending="runPending"
      title="Cancel this run?"
      description="The run ends where it is. The robot stops after the step it is on, wherever that leaves it."
      confirm-label="Cancel run"
      @update:open="(value: boolean) => !value && !runPending && (cancellingRun = null)"
      @cancel="cancellingRun = null"
      @confirm="cancellingRun && cancelRun(cancellingRun)"
    />

    <ConfirmDialog
      :open="pendingRemoval !== null"
      destructive
      :pending="removing"
      :title="`Remove ${pendingRemoval?.name ?? ''}?`"
      description="The record of what it has already run is kept. Nothing currently running is affected."
      confirm-label="Remove"
      @update:open="(value: boolean) => !value && !removing && (pendingRemoval = null)"
      @cancel="pendingRemoval = null"
      @confirm="confirmRemoval"
    />
  </div>
</template>
