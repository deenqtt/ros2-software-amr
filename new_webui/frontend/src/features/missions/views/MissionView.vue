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
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ChevronRight, Eye, ListOrdered, Pencil, Play, Plus, Square, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useMapStore } from '@/stores/maps'
import { useFleetStore } from '@/stores/fleet'
import { useMissionStore } from '@/stores/missions'
import { useStationStore } from '@/stores/stations'
import {
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
import { Skeleton } from '@/shared/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import BlockedTip from '@/shared/components/BlockedTip.vue'
import { usePermission } from '@/shared/composables/usePermission'
import { cn } from '@/shared/lib/utils'
import { STATION_TYPE_STYLE } from '@/features/stations/stationType'
import MissionTableSkeleton from '../components/MissionTableSkeleton.vue'
import MissionRowActions from '../components/MissionRowActions.vue'
import {
  lastFinishedRun,
  missionStatus,
  routePreview,
  runProgress,
  RUN_RESULT,
  timeAgo,
} from '../missionList'

const maps = useMapStore()
const fleet = useFleetStore()
const missions = useMissionStore()
const stations = useStationStore()
const route = useRoute()
const router = useRouter()
const { canOperate, operateBlocker, canEdit, editBlocker } = usePermission()

const selectedMapId = ref<string | null>(null)

const mapOptions = computed(() =>
  maps.maps.map((map) => ({ value: map.id, label: `${map.name} v${map.version}` })),
)

const selectedMap = computed(() => (selectedMapId.value ? maps.byId(selectedMapId.value) : null))

/** Robots on the selected map: the only ones a mission here can be sent to. */
const robotsOnMap = computed(() =>
  fleet.robots.filter((robot) => robot.activeMapId === selectedMapId.value),
)

async function selectMap(mapId: string) {
  selectedMapId.value = mapId
  // In the URL so a reload or a shared link lands on the same map.
  if (route.query.map !== mapId) void router.replace({ query: { ...route.query, map: mapId } })
  // Stations alongside, so a route preview can name its stops.
  await Promise.all([missions.load(mapId), stations.load(mapId)])
}

/**
 * The map to open on: the one in the URL, else the one most robots are on.
 *
 * Opening on the first map in the list could land on a floor with no robot,
 * where every Run button is disabled and nothing says why.
 */
function initialMapId(): string | null {
  const fromUrl = typeof route.query.map === 'string' ? route.query.map : null
  if (fromUrl && maps.byId(fromUrl)) return fromUrl
  const counts = new Map<string, number>()
  for (const robot of fleet.robots) {
    if (robot.activeMapId) counts.set(robot.activeMapId, (counts.get(robot.activeMapId) ?? 0) + 1)
  }
  const busiest = maps.maps
    .filter((map) => counts.has(map.id))
    .sort((a, b) => (counts.get(b.id) ?? 0) - (counts.get(a.id) ?? 0))[0]
  return busiest?.id ?? maps.maps[0]?.id ?? null
}

/**
 * True until the first map's missions are in.
 *
 * The stores start out empty and not loading, which would flash "No maps yet"
 * for the moment before the first request goes out.
 */
const booting = ref(true)

onMounted(async () => {
  try {
    await Promise.all([maps.load(), fleet.load()])
    const mapId = initialMapId()
    if (mapId) await selectMap(mapId)
  } finally {
    booting.value = false
  }
})

const showSkeleton = computed(() => booting.value || missions.loading)

// ── Row content ──────────────────────────────────────────────────────────────

/** A clock for "5m ago", ticking slowly: the labels are minutes-coarse. */
const now = ref(Date.now())
const clock = setInterval(() => (now.value = Date.now()), 30_000)
onBeforeUnmount(() => clearInterval(clock))

function stationLabel(id: string): string {
  return stations.byId(id)?.name ?? 'missing station'
}

function stationDot(id: string): string {
  const station = stations.byId(id)
  return station ? STATION_TYPE_STYLE[station.type].colour : 'rgb(128,132,140)'
}

function preview(mission: MissionSummary) {
  const shown = routePreview(mission.stationIds, (id) => id)
  return { ids: shown.shown, hidden: shown.hidden }
}

function liveRunOf(mission: MissionSummary): MissionRun | null {
  return missions.liveRuns.find((run) => run.missionId === mission.id) ?? null
}

function lastResult(mission: MissionSummary) {
  const run = lastFinishedRun(missions.runs, mission.id)
  if (!run || run.state === 'running' || run.state === 'stopping') return null
  return { ...RUN_RESULT[run.state], ago: timeAgo(run.endedAt ?? run.startedAt, now.value), run }
}

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

/** The phone row's one-line status, standing in for the table's Status column. */
function statusOf(mission: MissionSummary) {
  return missionStatus(
    mission,
    liveRunOf(mission),
    missions.runs,
    now.value,
    robotName,
    canEdit.value,
  )
}

/** Phone rows, each status worked out once per render rather than per binding. */
const phoneRows = computed(() =>
  missions.missions.map((mission) => ({ mission, status: statusOf(mission) })),
)

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
  robotsOnMap.value.map((robot) => {
    const busy = missions.runForRobot(robot.id)
    return {
      value: robot.id,
      label: robot.name,
      hint: busy ? `Running ${busy.missionName}` : undefined,
      disabled: Boolean(busy),
    }
  }),
)

/** Why Run is unavailable for a mission, or null when it can be run. */
function runBlocker(mission: MissionSummary): string | null {
  if (!canOperate.value) return operateBlocker.value
  if (!mission.stepCount) return 'Add steps before running this'
  if (!robotsOnMap.value.length) return 'No robot is on this map'
  if (!dispatchOptions.value.some((option) => !option.disabled)) {
    return 'Every robot on this map is already running a mission'
  }
  return null
}

const mapSubtitle = computed(() => {
  if (!selectedMap.value) return 'Pick a map'
  const n = missions.count
  const r = robotsOnMap.value.length
  return `${n} mission${n === 1 ? '' : 's'} · ${r ? `${r} robot${r === 1 ? '' : 's'}` : 'no robot'} on this map`
})

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
  if (!mission || !robotId || !canOperate.value) return
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

function progressOf(run: MissionRun): string {
  const mission = missions.missions.find((m) => m.id === run.missionId)
  return runProgress(run.stepIndex, mission?.stationIds ?? null, stationLabel)
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
  if (newNameProblem.value || !selectedMapId.value || !canEdit.value) return
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
    // An empty route cannot run, so the next thing to do is always this.
    await router.push(`/mission/edit/${created.id}`)
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
  <div class="space-y-base p-sm sm:p-base md:p-lg">
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
          <span
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-control bg-status-run/12 text-status-run"
          >
            <Play :size="13" />
          </span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-body-md text-ink">{{ run.missionName }}</p>
            <p class="truncate font-data text-caption text-muted">
              {{ robotName(run.robotId) }} · {{ progressOf(run) }} · {{ lapLabel(run) }}
            </p>
          </div>
          <!-- On a phone the controls get a row of their own, three even
               thumb-sized slots; from md they sit at the end of the line. -->
          <div class="grid w-full grid-cols-3 gap-xs md:flex md:w-auto md:items-center md:gap-sm">
            <!-- The run is a robot moving somewhere; watching it is one click. -->
            <Button v-if="run.robotId" variant="ghost" size="sm" class="w-full md:w-auto" as-child>
              <RouterLink
                :to="`/robot/${run.robotId}/nav`"
                :title="`Watch ${robotName(run.robotId)}`"
              >
                <Eye :size="13" /> Watch
              </RouterLink>
            </Button>

            <!-- `stopping` is not a failure and not finished: it is a lap in
                 progress that will be the last one. -->
            <Badge
              v-if="run.state === 'stopping'"
              class="justify-center bg-status-warn/12 text-center text-status-warn md:justify-start md:text-left"
            >
              stopping after this lap
            </Badge>

            <BlockedTip
              v-if="run.state === 'running'"
              :reason="operateBlocker"
              class="w-full md:w-auto"
            >
              <Button
                variant="outline"
                size="sm"
                class="w-full md:w-auto"
                :disabled="!canOperate || runPending"
                @click="stoppingRun = run"
              >
                <Square :size="13" /> Stop after lap
              </Button>
            </BlockedTip>
            <BlockedTip :reason="operateBlocker" class="w-full md:w-auto">
              <Button
                variant="ghost"
                size="sm"
                class="w-full hover:text-status-fault md:w-auto"
                :disabled="!canOperate || runPending"
                @click="cancellingRun = run"
              >
                <X :size="13" /> Cancel
              </Button>
            </BlockedTip>
          </div>
        </div>
      </CardContent>
    </Card>

    <Card>
      <PanelToolbar title="Missions" :subtitle="mapSubtitle">
        <template #icon><ListOrdered :size="14" class="shrink-0 text-muted" /></template>
        <template #actions>
          <div v-if="mapOptions.length" class="hidden md:block">
            <Select
              label="Map"
              :model-value="selectedMapId"
              :options="mapOptions"
              class="min-w-[12rem]"
              @update:model-value="selectMap"
            />
          </div>
          <BlockedTip :reason="editBlocker">
            <Button size="sm" :disabled="!canEdit || !selectedMapId" @click="createOpen = true">
              <Plus :size="13" /> New mission
            </Button>
          </BlockedTip>
        </template>
      </PanelToolbar>

      <!-- Beside "New mission" the picker would squeeze both on a phone; a row
           of its own keeps the map name readable. -->
      <div v-if="mapOptions.length" class="border-b border-hairline px-base py-sm md:hidden">
        <Select
          label="Map"
          :model-value="selectedMapId"
          :options="mapOptions"
          class="w-full"
          @update:model-value="selectMap"
        />
      </div>

      <CardContent>
        <template v-if="showSkeleton">
          <ul class="divide-y divide-hairline md:hidden">
            <li v-for="row in 3" :key="row" class="flex items-center gap-sm py-sm">
              <div class="flex-1 space-y-xs">
                <Skeleton class="h-4 w-32" />
                <Skeleton class="h-3 w-44" />
              </div>
              <Skeleton class="h-8 w-16" />
            </li>
          </ul>
          <div class="hidden md:block">
            <Table>
              <MissionTableSkeleton />
            </Table>
          </div>
        </template>

        <EmptyState
          v-else-if="!mapOptions.length"
          title="No maps yet"
          description="A mission names stations, and stations belong to a map. Survey one or upload one first."
        />

        <EmptyState
          v-else-if="!missions.count"
          title="No missions on this map"
          description="A mission is an ordered route: pick at one station, drop at another. Create one and add its steps."
        >
          <template #action>
            <BlockedTip :reason="editBlocker">
              <Button size="sm" :disabled="!canEdit" @click="createOpen = true">
                <Plus :size="13" /> New mission
              </Button>
            </BlockedTip>
          </template>
        </EmptyState>

        <template v-else>
          <!-- A disabled button's tooltip is easy to miss; say it once, in view. -->
          <p
            v-if="!robotsOnMap.length"
            class="mb-sm rounded-control border border-status-warn/40 bg-status-warn/10 p-sm text-caption text-body"
          >
            No robot is on this map, so nothing here can run. Load this map on a robot, or pick the
            map a robot is on.
          </p>

          <!--
            Phone: the name and one line of status. The route, its note and the
            step count are one tap away in the editor.
          -->
          <ul class="divide-y divide-hairline md:hidden">
            <li
              v-for="{ mission, status } in phoneRows"
              :key="mission.id"
              class="flex items-center gap-xs"
            >
              <RouterLink
                :to="`/mission/edit/${mission.id}`"
                class="flex min-h-[56px] min-w-0 flex-1 flex-col justify-center py-sm pr-xs transition-colors active:bg-surface-strong"
              >
                <span class="block truncate text-body-md font-medium text-ink">
                  {{ mission.name }}
                </span>
                <span
                  :class="cn('mt-[2px] block truncate text-body-sm', status.tone)"
                  :title="status.detail ?? undefined"
                >
                  {{ status.label }}
                </span>
              </RouterLink>
              <BlockedTip :reason="operateBlocker">
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="runBlocker(mission) !== null"
                  :title="runBlocker(mission) ?? `Run ${mission.name}`"
                  @click="openDispatch(mission)"
                >
                  <Play :size="13" /> Run
                </Button>
              </BlockedTip>
              <MissionRowActions :mission="mission" @remove="pendingRemoval = mission" />
            </li>
          </ul>

          <div class="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead class="w-full max-w-0">Mission</TableHead>
                  <TableHead class="whitespace-nowrap">Status</TableHead>
                  <TableHead align="right">Actions</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                <TableRow v-for="mission in missions.missions" :key="mission.id" interactive>
                  <TableCell class="w-full max-w-0">
                    <div class="min-w-0 space-y-xxs py-xxs">
                      <div class="flex min-w-0 items-baseline gap-xs">
                        <RouterLink
                          :to="`/mission/edit/${mission.id}`"
                          class="truncate text-body-md text-ink hover:text-primary hover:underline"
                          :title="`Edit ${mission.name}`"
                        >
                          {{ mission.name }}
                        </RouterLink>
                        <span
                          v-if="mission.note"
                          class="hidden truncate text-caption text-muted lg:inline"
                          :title="mission.note"
                        >
                          {{ mission.note }}
                        </span>
                      </div>

                      <!-- The route itself, so "Shuttle" and "Shuttle 2" can be told
                         apart without opening either. -->
                      <div
                        v-if="mission.stationIds.length"
                        class="flex min-w-0 flex-wrap items-center gap-x-xxs gap-y-0 text-caption text-body"
                        :title="mission.stationIds.map(stationLabel).join(' → ')"
                      >
                        <!-- Each arrow travels with the stop after it, so a wrap never
                           leaves a "›" stranded at the start of a line. -->
                        <span
                          v-for="(id, index) in preview(mission).ids"
                          :key="index"
                          class="inline-flex min-w-0 items-center gap-xxs whitespace-nowrap"
                        >
                          <template v-if="index > 0">
                            <ChevronRight :size="11" class="shrink-0 text-muted-soft" />
                            <template
                              v-if="
                                index === preview(mission).ids.length - 1 && preview(mission).hidden
                              "
                            >
                              <span class="font-data text-muted"
                                >+{{ preview(mission).hidden }}</span
                              >
                              <ChevronRight :size="11" class="shrink-0 text-muted-soft" />
                            </template>
                          </template>
                          <span
                            class="h-2 w-2 shrink-0 rounded-full"
                            :style="{ backgroundColor: stationDot(id) }"
                          />
                          <span class="max-w-[9rem] truncate">{{ stationLabel(id) }}</span>
                        </span>
                        <span class="ml-xxs whitespace-nowrap font-data text-muted-soft">
                          · {{ mission.stepCount }} step{{ mission.stepCount === 1 ? '' : 's' }}
                        </span>
                      </div>
                      <RouterLink
                        v-else
                        :to="`/mission/edit/${mission.id}`"
                        class="inline-flex items-center gap-xxs text-caption text-status-warn hover:underline"
                      >
                        <Plus :size="12" /> No steps yet{{ canEdit ? ' — add the first stop' : '' }}
                      </RouterLink>
                    </div>
                  </TableCell>

                  <!--
                  One column for what the route is doing: running now, or how it
                  last ended. A separate Status column said "Idle" on nearly
                  every row. The robot is written out, not left to a tooltip.
                -->
                  <TableCell>
                    <div
                      v-if="liveRunOf(mission)"
                      class="flex flex-col items-start gap-xxs whitespace-nowrap"
                    >
                      <span
                        class="inline-flex items-center gap-xxs rounded-chip bg-status-run/12 px-xs py-[2px] text-caption text-status-run"
                      >
                        <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-status-run" />
                        {{ liveRunOf(mission)!.state === 'stopping' ? 'Stopping' : 'Running' }}
                      </span>
                      <span class="text-caption text-muted">
                        {{ robotName(liveRunOf(mission)!.robotId) }} ·
                        {{ progressOf(liveRunOf(mission)!) }}
                      </span>
                    </div>
                    <div
                      v-else-if="lastResult(mission)"
                      class="flex flex-col whitespace-nowrap"
                      :title="lastResult(mission)!.run.detail ?? undefined"
                    >
                      <span class="text-body-sm">
                        <span :class="lastResult(mission)!.tone">{{
                          lastResult(mission)!.label
                        }}</span>
                        <span class="text-muted"> · {{ lastResult(mission)!.ago }}</span>
                      </span>
                      <span class="text-caption text-muted">
                        {{ robotName(lastResult(mission)!.run.robotId) }}
                      </span>
                    </div>
                    <span v-else class="whitespace-nowrap text-body-sm text-muted-soft"
                      >Never run</span
                    >
                  </TableCell>

                  <TableCell align="right">
                    <div class="flex justify-end gap-xxs">
                      <!-- A route with no steps has nothing to send, so the button
                       says so rather than producing a server error. -->
                      <BlockedTip :reason="operateBlocker">
                        <Button
                          variant="ghost"
                          size="sm"
                          :disabled="runBlocker(mission) !== null"
                          :title="runBlocker(mission) ?? `Run ${mission.name}`"
                          @click="openDispatch(mission)"
                        >
                          <Play :size="13" /> Run
                        </Button>
                      </BlockedTip>
                      <!-- The editor opens read-only without the admin role, so it is
                         still offered, as what it then is. -->
                      <Button
                        variant="ghost"
                        size="sm"
                        class="hidden lg:inline-flex"
                        :title="`${canEdit ? 'Edit' : 'View'} ${mission.name}`"
                        @click="router.push(`/mission/edit/${mission.id}`)"
                      >
                        <template v-if="canEdit"><Pencil :size="13" /> Edit</template>
                        <template v-else><Eye :size="13" /> View</template>
                      </Button>
                      <!-- Below lg the Edit button gives way and the menu carries it. -->
                      <MissionRowActions
                        :mission="mission"
                        open-class="lg:hidden"
                        @remove="pendingRemoval = mission"
                      />
                    </div>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </template>
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
                  'rounded-control border px-sm py-xxs text-body-sm transition-colors touch:min-h-[44px]',
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
          This route has a step that waits for someone to confirm. Looping it means somebody has to
          be there every lap.
        </p>

        <p v-if="dispatchError" class="text-caption text-status-fault">{{ dispatchError }}</p>
      </form>

      <template #footer>
        <Button
          variant="secondary"
          size="sm"
          :disabled="dispatchPending"
          @click="dispatching = null"
        >
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
