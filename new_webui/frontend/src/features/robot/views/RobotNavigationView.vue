<script setup lang="ts">
/**
 * Operational page for one robot.
 *
 * Navigation owns the live map and the controls that can change where the
 * robot believes it is or where it should go. Technical telemetry stays on
 * RobotDetailView so opening diagnostics can never arm a navigation tool.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  Crosshair,
  Eye,
  EyeOff,
  Hand,
  Layers,
  Navigation,
  Play,
  PanelRightClose,
  PanelRightOpen,
  Square,
  WifiOff,
  X,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from 'reka-ui'
import { useMissionStore } from '@/stores/missions'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import { useZoneStore } from '@/stores/zones'
import { useStationStore } from '@/stores/stations'
import { useMapStore } from '@/stores/maps'
import { useUiStore } from '@/stores/ui'
import { missionsApi } from '@/shared/api/missions'
import { useRosPool } from '@/app/ros/pool'
import { useRobotTelemetry } from '@/features/mapping/useRobotTelemetry'
import { ZONE_KIND_LIST } from '@/features/zones/zoneKind'
import { goalPoseMessage, initialPoseMessage, type PlanarPose } from '../pose'
import { GOAL_OUTCOME_LABEL } from '../goalStatus'
import { cancelAllGoals } from '../cancelGoal'
import { stallLabel } from '../stall'
import { SERVICE_TYPES } from '@/domain/ros/topics'
import RobotMapCanvas, { type MapTool } from '../components/RobotMapCanvas.vue'
import RobotBar from '../components/RobotBar.vue'
import { useRobotStop } from '../useRobotStop'
import { missionOverlay } from '../missionMarkers'
import { RUN_MODE_LABEL, RUN_MODES, type Mission, type RunMode } from '@/domain/types'
import { activityStatus, dockingStatus } from '@/domain/ros/status'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Select } from '@/shared/ui/select'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { cn, formatNumber, formatPercent } from '@/shared/lib/utils'

const route = useRoute()
const fleet = useFleetStore()
const links = useLinkStore()
const missions = useMissionStore()

const robotId = computed(() => String(route.params.robotId))
const robot = computed(() => fleet.byId(robotId.value))
const link = computed(() => links.linkFor(robotId.value))
const vitals = computed(() => links.vitalsFor(robotId.value))
const muted = computed(() => links.isMuted(robotId.value))

const maps = useMapStore()
const ui = useUiStore()

// The map wants the width; the rail folds while this page is open and comes
// back as it was on the way out.
onMounted(() => ui.foldNav(true))
onBeforeUnmount(() => ui.foldNav(false))

onMounted(async () => {
  // For the active map's name; the id alone means nothing to an operator.
  if (!maps.loaded) void maps.load()
  if (!fleet.loaded) await fleet.load()
  links.sync(fleet.robots)
  links.focus(robotId.value)
})

watch(robotId, (id) => links.focus(id))
onBeforeUnmount(() => links.focus(null))

const activity = computed(() =>
  vitals.value.activity === null ? null : activityStatus(vitals.value.activity),
)
const docking = computed(() =>
  vitals.value.docking === null ? null : dockingStatus(vitals.value.docking),
)

const pool = useRosPool()
const zones = useZoneStore()
const stations = useStationStore()
const telemetry = useRobotTelemetry(() => robotId.value)
const tool = ref<MapTool>('view')

const selectedMissionId = ref<string | null>(null)
const missionMode = ref<RunMode>('once')
const missionLaps = ref(5)
const missionPending = ref(false)

const layers = ref<Record<string, boolean>>({
  map: true,
  costmap: false,
  zones: true,
  scan: true,
  particles: false,
  plan: true,
  mission: true,
  robot: true,
})

const LAYER_LIST = [
  { key: 'costmap', label: 'Costmap', hint: 'What the planner thinks the floor costs' },
  { key: 'scan', label: 'Laser', hint: 'What the robot can see right now' },
  { key: 'particles', label: 'Particles', hint: 'Whether it knows where it is' },
  { key: 'plan', label: 'Plan', hint: 'Where it intends to go' },
  { key: 'mission', label: 'Mission', hint: 'The stops of the running mission, and which are done' },
  { key: 'zones', label: 'Zones', hint: 'Rules that apply on this map' },
] as const

watch(
  () => robot.value?.activeMapId,
  async (mapId) => {
    selectedMissionId.value = null
    if (mapId) {
      void zones.load(mapId)
      // The mission markers are stations; their poses live here.
      void stations.load(mapId)
      await missions.load(mapId)
    }
  },
  { immediate: true },
)

const availableMissions = computed(() => missions.missions.filter((mission) => mission.stepCount > 0))
const missionOptions = computed(() =>
  availableMissions.value.map((mission) => ({
    value: mission.id,
    label: mission.name,
    hint: mission.note ?? `${mission.stepCount} steps`,
  })),
)
const modeOptions = RUN_MODES.map((mode) => ({ value: mode, label: RUN_MODE_LABEL[mode] }))
const activeRun = computed(() => missions.runForRobot(robotId.value))
const navReady = computed(
  () =>
    link.value.state === 'online' &&
    Boolean(robot.value?.activeMapId) &&
    agentMode.value === 'nav' &&
    agentState.value === 'running' &&
    Boolean(telemetry.pose.value) &&
    activeRun.value === null,
)
const missionBlockReason = computed(() => {
  if (!robot.value?.activeMapId) return 'Assign a map before running a mission.'
  if (link.value.state !== 'online') return 'Robot connection is offline.'
  if (!telemetry.agent.value) return 'Waiting for robot agent status.'
  if (agentMode.value !== 'nav' || agentState.value !== 'running') return 'Nav2 is not ready yet.'
  if (!telemetry.pose.value) return 'Set the initial pose before running a mission.'
  if (activeRun.value) return `Running ${activeRun.value.missionName}.`
  if (!availableMissions.value.length) return 'No saved mission with steps exists on this map.'
  if (!selectedMissionId.value) return 'Choose a mission to run.'
  return null
})

// Runs are kept fresh by the app-wide watcher (app/runNotifications.ts), which
// also catches a run started from another tab — the poll that lived here only
// started once this page already knew of a live run.

/** The route of the run in progress: a run carries its mission id, not its steps. */
const runMission = ref<Mission | null>(null)
watch(
  () => activeRun.value?.missionId ?? null,
  async (missionId) => {
    if (!missionId) {
      runMission.value = null
      return
    }
    if (runMission.value?.id === missionId) return
    try {
      const mission = await missionsApi.get(missionId)
      // Another run may have started while this was in flight.
      if (activeRun.value?.missionId === missionId) runMission.value = mission
    } catch {
      // No markers is a smaller problem than an error over the map; the card
      // still shows the step number.
      runMission.value = null
    }
  },
  { immediate: true },
)

const missionMap = computed(() => {
  const run = activeRun.value
  const mission = runMission.value
  if (!run || !mission || mission.id !== run.missionId) return null
  return missionOverlay(mission.steps, stations.byId, run)
})

/** Where the robot is headed, by name, for the mission card. */
const currentStopName = computed(() => {
  const run = activeRun.value
  const step = run ? runMission.value?.steps[run.stepIndex] : undefined
  return step ? (stations.byId(step.stationId)?.name ?? null) : null
})

const TOOLS = [
  { value: 'view', label: 'Pan', icon: Hand, hint: 'Move the view' },
  {
    value: 'initialPose',
    label: 'Set pose',
    icon: Crosshair,
    hint: 'Tell AMCL where the robot is. Drag for heading.',
  },
  {
    value: 'goal',
    label: 'Go here',
    icon: Navigation,
    hint: 'Send a one-off navigation goal. Drag for the arrival heading.',
  },
] as const

const agentMode = computed(() => telemetry.agent.value?.mode ?? 'unknown')
const agentState = computed(() => telemetry.agent.value?.state ?? 'waiting')

/**
 * Whether anything shown below is live.
 *
 * Offline, the tiles used to say "UNKNOWN" and "WAITING" — true, and a
 * misreading of the actual problem, which is that nothing is connected.
 */
const online = computed(() => link.value.state === 'online' || link.value.state === 'stale')

const mapLabel = computed(() => {
  const id = robot.value?.activeMapId
  if (!id) return null
  const map = maps.byId(id)
  return map ? `${map.name} v${map.version}` : 'Unknown map'
})

/**
 * Why a map tool cannot be used right now, or null when it can.
 *
 * Both tools publish to the robot, and a goal into a stack that is not running
 * goes nowhere without a word. Disabled with the reason, like Start mission,
 * rather than enabled and failing in a toast.
 */
function toolBlocker(value: MapTool): string | null {
  if (value === 'view') return null
  if (!online.value) return 'Robot is not connected.'
  if (agentMode.value !== 'nav' || agentState.value !== 'running') return 'Nav2 is not running.'
  if (value === 'goal' && !telemetry.pose.value) return 'Set the pose first.'
  return null
}

// A tool that stops being usable mid-gesture drops back to panning.
watch(
  () => toolBlocker(tool.value),
  (blocked) => {
    if (blocked) tool.value = 'view'
  },
)

/** How many optional layers are on, for the Layers button. */
const layersOn = computed(() => LAYER_LIST.filter((layer) => layers.value[layer.key]).length)

/**
 * The stack in one line: which one is up and in what state.
 *
 * Mode and stack used to be two tiles that were only ever read together.
 */
const stackLine = computed(() => {
  if (!online.value) return { text: '—', tone: 'text-muted' }
  const name = agentMode.value === 'nav' ? 'Nav2' : agentMode.value === 'map' ? 'SLAM' : null
  if (!name) return { text: 'Stopped', tone: 'text-muted' }
  const state = agentState.value
  const tone =
    state === 'running'
      ? 'text-status-ok'
      : state === 'failed'
        ? 'text-status-fault'
        : 'text-status-warn'
  return { text: `${name} ${state}`, tone }
})

const batteryLine = computed(() => {
  const percent = vitals.value.battery.percent
  if (percent === null || percent === undefined) return '—'
  const volts = vitals.value.battery.voltage
  return [
    formatPercent(percent),
    vitals.value.battery.charging ? 'charging' : null,
    volts !== null && volts !== undefined ? `${formatNumber(volts, 1)} V` : null,
  ]
    .filter(Boolean)
    .join(' · ')
})

/**
 * The side panel, collapsible like the Station and Zone lists. Starts closed
 * below 1024px, where open it would leave the map a strip.
 */
function wideScreen(): boolean {
  try {
    return window.matchMedia?.('(min-width: 1024px)')?.matches ?? true
  } catch {
    return true
  }
}
const panelOpen = ref(wideScreen())

/** Kinds worth a legend entry: drawable ones, and any present on this map. */
const legendKinds = computed(() =>
  ZONE_KIND_LIST.filter(
    (kind) => !kind.unavailable || zones.zones.some((zone) => zone.kind === kind.value),
  ),
)

function onPick(pose: PlanarPose) {
  const client = pool.clientFor(robotId.value)
  if (!client) {
    toast.error('No connection to this robot')
    return
  }

  const active = tool.value
  const sent =
    active === 'initialPose'
      ? client.publish('initialPose', initialPoseMessage(pose))
      : client.publish('goalPose', goalPoseMessage(pose))

  if (!sent) {
    toast.error('Could not send — the link dropped')
    return
  }

  toast.success(active === 'initialPose' ? 'Pose sent. Watch the particles settle.' : 'Goal sent', {
    description: `${pose.x.toFixed(2)}, ${pose.y.toFixed(2)} m`,
  })
  tool.value = 'view'
}

async function startMission() {
  if (!robot.value?.activeMapId || !selectedMissionId.value || !navReady.value) return

  missionPending.value = true
  try {
    const run = await missions.dispatch({
      missionId: selectedMissionId.value,
      robotId: robotId.value,
      mode: missionMode.value,
      lapsTarget: missionMode.value === 'laps' ? missionLaps.value : null,
    })
    toast.success(`${run.missionName} started`, {
      description: `${robot.value.name} is executing the mission`,
    })
  } catch (error) {
    toast.error('Could not start mission', { description: missions.describeError(error) })
  } finally {
    missionPending.value = false
  }
}

async function stopMissionAfterLap() {
  const run = activeRun.value
  if (!run) return

  missionPending.value = true
  try {
    await missions.stopAfterLap(run.id)
    toast.success(`${run.missionName} will stop after this lap`)
  } catch (error) {
    toast.error('Could not stop the mission', { description: missions.describeError(error) })
  } finally {
    missionPending.value = false
  }
}

const stopPending = ref(false)
const { stopAndPark, stopPending: parkPending } = useRobotStop(robotId)

/**
 * Stop driving, now, without ending anything else.
 *
 * Goals go out on /goal_pose and there is no handle to cancel through, so this
 * goes to the action server's own cancel service. The mission is left alone on
 * purpose: this is for a robot heading somewhere wrong, not for abandoning the
 * route.
 */
async function cancelGoal() {
  const target = robot.value
  if (!target) return
  const client = pool.clientFor(target.id)
  if (!client) {
    toast.error('No connection to this robot')
    return
  }
  stopPending.value = true
  try {
    await client.callService('cancelNavGoal', SERVICE_TYPES.cancelGoal, cancelAllGoals())
    toast.success('Goal canceled', { description: 'The robot stops where it is.' })
  } catch (error) {
    toast.error('Could not cancel the goal', {
      description: error instanceof Error ? error.message : String(error),
    })
  } finally {
    stopPending.value = false
  }
}

async function cancelMission() {
  const run = activeRun.value
  if (!run) return

  missionPending.value = true
  try {
    await missions.cancel(run.id)
    // The agent also gives the goal up when it sees the run gone, within a
    // couple of seconds. Canceling it here too stops the robot now rather
    // than then. Best effort: the run is already canceled either way.
    const client = pool.clientFor(robotId.value)
    if (client) {
      await client
        .callService('cancelNavGoal', SERVICE_TYPES.cancelGoal, cancelAllGoals())
        .catch(() => undefined)
    }
    toast.success(`${run.missionName} canceled`, { description: 'The robot stops where it is.' })
  } catch (error) {
    toast.error('Could not cancel the mission', { description: missions.describeError(error) })
  } finally {
    missionPending.value = false
  }
}
</script>

<template>
  <div v-if="!robot" class="p-lg">
    <EmptyState title="Robot not found" description="It may have been removed from the registry.">
      <template #action>
        <Button size="sm" variant="secondary" as-child>
          <RouterLink to="/robot">Back to robots</RouterLink>
        </Button>
      </template>
    </EmptyState>
  </div>

  <!--
    One bar, then the map. Everything else that used to stack above the map —
    an offline banner, a row of tools, a row of layer chips — now sits on the
    map or in the side panel, so the map starts right under the robot's name.
    The bar is outside any scrolling region: Stop & park is always on screen.
  -->
  <div v-else class="flex h-full min-h-0 flex-col">
    <RobotBar
      :robot="robot"
      :link-state="link.state"
      :attempt="link.attempt"
      :stop-pending="parkPending"
      @stop="stopAndPark"
    />

    <div class="flex min-h-0 flex-1">
      <!-- The map, with its controls on it rather than in rows above it. -->
      <section class="relative min-w-0 flex-1">
        <RobotMapCanvas
          :grid="telemetry.grid.value"
          :costmap="telemetry.costmap.value"
          :plan="telemetry.plan.value"
          :particles="telemetry.particles.value"
          :scan="telemetry.scan.value"
          :pose="telemetry.pose.value"
          :sensor-offset="telemetry.sensorOffset.value"
          :zones="zones.zones"
          :footprint="telemetry.footprint.value"
          :mission="missionMap"
          :layers="layers"
          :tool="tool"
          @pick="onPick"
        >
          <template #legend>
            <span v-for="kind in legendKinds" :key="kind.value" class="flex items-center gap-xxs">
              <span class="h-2.5 w-2.5 rounded-[2px]" :style="{ backgroundColor: kind.colour }" />
              {{ kind.label }}
            </span>
          </template>
        </RobotMapCanvas>

        <!-- Above the offline veil: they stay readable, and Layers stays usable. -->
        <div class="absolute left-sm top-sm z-[2] flex items-center gap-xs">
          <!-- One at a time: a segmented control, not a row of toggles. -->
          <div
            role="radiogroup"
            aria-label="Map tool"
            class="inline-flex rounded-control border border-hairline bg-surface p-[2px] shadow-soft"
          >
            <button
              v-for="item in TOOLS"
              :key="item.value"
              type="button"
              role="radio"
              :aria-checked="tool === item.value"
              :disabled="toolBlocker(item.value) !== null"
              :title="toolBlocker(item.value) ?? item.hint"
              :class="
                cn(
                  'flex h-[26px] items-center gap-xs rounded-[6px] px-sm text-body-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                  tool === item.value ? 'bg-primary text-on-primary' : 'text-body hover:text-ink',
                )
              "
              @click="tool = item.value"
            >
              <component :is="item.icon" :size="13" />
              <span class="hidden sm:inline">{{ item.label }}</span>
            </button>
          </div>

          <!-- Six layer chips were a second toolbar; one button holds them. -->
          <PopoverRoot>
            <PopoverTrigger
              class="flex h-[32px] items-center gap-xs rounded-control border border-hairline bg-surface px-sm text-body-sm text-body shadow-soft transition-colors hover:text-ink"
              aria-label="Map layers"
            >
              <Layers :size="14" />
              <span class="hidden sm:inline">Layers</span>
              <span class="font-data text-caption text-muted">{{ layersOn }}</span>
            </PopoverTrigger>
            <PopoverPortal>
              <PopoverContent
                side="bottom"
                align="start"
                :side-offset="6"
                class="z-50 w-[15rem] rounded-surface border border-hairline bg-surface p-xxs shadow-soft"
              >
                <button
                  v-for="layer in LAYER_LIST"
                  :key="layer.key"
                  type="button"
                  role="menuitemcheckbox"
                  :aria-checked="layers[layer.key]"
                  class="flex w-full items-start gap-xs rounded-control px-xs py-xs text-left transition-colors hover:bg-surface-soft"
                  @click="layers[layer.key] = !layers[layer.key]"
                >
                  <component
                    :is="layers[layer.key] ? Eye : EyeOff"
                    :size="14"
                    :class="cn('mt-[2px] shrink-0', layers[layer.key] ? 'text-primary' : 'text-muted-soft')"
                  />
                  <span class="min-w-0">
                    <span
                      class="block text-body-sm"
                      :class="layers[layer.key] ? 'text-ink' : 'text-muted'"
                    >
                      {{ layer.label }}
                    </span>
                    <span class="block text-caption text-muted-soft">{{ layer.hint }}</span>
                  </span>
                </button>
              </PopoverContent>
            </PopoverPortal>
          </PopoverRoot>
        </div>

        <!-- Offline: said once, where the map would be, instead of a banner
             above it and "unknown" in every field. -->
        <div
          v-if="!online"
          class="absolute inset-0 z-[1] flex items-center justify-center bg-canvas/70 p-base backdrop-blur-[1px]"
        >
          <div
            class="max-w-[22rem] rounded-surface border border-hairline bg-surface px-base py-sm text-center shadow-soft"
          >
            <WifiOff :size="18" class="mx-auto text-status-warn" />
            <p class="mt-xs text-body-md text-ink">
              {{ muted ? 'Monitoring is off' : `${robot.name} is not connected` }}
            </p>
            <p class="mt-xxs text-caption text-muted">
              <template v-if="muted">
                Turn it on in
                <RouterLink :to="`/robot/${robotId}/detail`" class="text-primary hover:underline">
                  Details
                </RouterLink>
                to see the live map.
              </template>
              <template v-else>
                {{ link.attempt > 0 ? `Reconnecting, attempt ${link.attempt}. ` : '' }}The map and
                the controls come back when it does.
              </template>
            </p>
          </div>
        </div>
      </section>

      <!-- Status and mission. Collapsible to a strip, like Station and Zone. -->
      <aside
        class="flex shrink-0 flex-col border-l border-hairline bg-surface transition-[width] duration-150"
        :class="panelOpen ? 'w-[19rem]' : 'w-[3rem]'"
      >
        <button
          type="button"
          class="flex h-10 shrink-0 items-center gap-xs border-b border-hairline px-sm text-body-sm text-body transition-colors hover:text-ink"
          :aria-expanded="panelOpen"
          :title="panelOpen ? 'Hide the panel' : 'Show status and mission'"
          @click="panelOpen = !panelOpen"
        >
          <component :is="panelOpen ? PanelRightClose : PanelRightOpen" :size="15" class="shrink-0" />
          <span v-if="panelOpen">Status &amp; mission</span>
        </button>

        <div v-if="panelOpen" class="min-h-0 flex-1 space-y-base overflow-y-auto p-base scrollbar-thin">
          <!-- A short list, not ten tiles: these are read at a glance. -->
          <dl class="space-y-xs text-body-sm">
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="text-muted">Stack</dt>
              <dd class="font-medium" :class="stackLine.tone">{{ stackLine.text }}</dd>
            </div>
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="text-muted">Pose</dt>
              <dd
                class="font-medium"
                :class="!online ? 'text-muted' : telemetry.pose.value ? 'text-ink' : 'text-status-warn'"
              >
                {{ !online ? '—' : telemetry.pose.value ? 'Localized' : 'Not set' }}
              </dd>
            </div>
            <!-- A stalled goal is still "executing" as far as Nav2 is
                 concerned, so saying so would be true and useless. -->
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="text-muted">Goal</dt>
              <dd
                class="text-right font-medium"
                :class="
                  !online
                    ? 'text-muted'
                    : telemetry.stall.value.stalled
                      ? 'text-status-warn'
                      : telemetry.goalOutcome.value === 'arrived'
                        ? 'text-status-ok'
                        : telemetry.goalOutcome.value === 'failed'
                          ? 'text-status-fault'
                          : 'text-muted'
                "
              >
                {{
                  !online
                    ? '—'
                    : telemetry.stall.value.stalled
                      ? stallLabel(telemetry.stall.value.stillFor)
                      : GOAL_OUTCOME_LABEL[telemetry.goalOutcome.value]
                }}
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="text-muted">Map</dt>
              <dd class="min-w-0 truncate font-medium">
                <RouterLink
                  v-if="mapLabel"
                  to="/maps"
                  class="text-ink hover:text-primary hover:underline"
                  :title="robot.activeMapId ?? undefined"
                >
                  {{ mapLabel }}
                </RouterLink>
                <span v-else class="text-status-warn">Not assigned</span>
              </dd>
            </div>
            <div class="flex items-baseline justify-between gap-sm">
              <dt class="text-muted">Battery</dt>
              <dd class="font-data font-medium text-ink">{{ batteryLine }}</dd>
            </div>
            <!-- Only when the robot reports them; "not reported" twice was noise. -->
            <div v-if="activity" class="flex items-center justify-between gap-sm">
              <dt class="text-muted">Activity</dt>
              <dd><StatusBadge :tone="activity.tone" :label="activity.label" /></dd>
            </div>
            <div v-if="docking" class="flex items-center justify-between gap-sm">
              <dt class="text-muted">Docking</dt>
              <dd><StatusBadge :tone="docking.tone" :label="docking.label" /></dd>
            </div>
          </dl>

          <section class="space-y-sm border-t border-hairline pt-base">
            <p class="text-label uppercase text-muted">Mission</p>


          <div v-if="activeRun" class="rounded-control border border-primary/30 bg-primary/5 p-sm">
            <div class="flex flex-wrap items-start justify-between gap-sm">
              <div>
                <div class="text-body-md font-medium text-ink">{{ activeRun.missionName }}</div>
                <div class="mt-xxs text-body-sm text-muted">
                  Step {{ activeRun.stepIndex + 1
                  }}<span v-if="runMission"> of {{ runMission.steps.length }}</span>
                  <span v-if="currentStopName" class="text-ink"> → {{ currentStopName }}</span> ·
                  {{ activeRun.mode === 'once' ? 'single pass' : `lap ${activeRun.lap}` }}
                  <span v-if="activeRun.mode === 'laps'"> of {{ activeRun.lapsTarget }}</span>
                </div>
                <div v-if="activeRun.detail" class="mt-xxs text-caption text-muted">
                  {{ activeRun.detail }}
                </div>
              </div>
              <span class="rounded-chip bg-primary/10 px-sm py-xxs text-caption uppercase text-primary">
                {{ activeRun.state }}
              </span>
            </div>
            <div class="mt-sm flex flex-wrap gap-xxs">
              <Button
                variant="outline"
                size="sm"
                :disabled="missionPending || activeRun.state === 'stopping'"
                @click="stopMissionAfterLap"
              >
                <Square :size="13" /> Stop after lap
              </Button>
              <Button
                variant="ghost"
                size="sm"
                class="hover:text-status-fault"
                :disabled="missionPending"
                @click="cancelMission"
              >
                <X :size="13" /> Cancel mission
              </Button>
              <!-- Stops the driving without ending the route: for a robot
                   heading somewhere wrong, not for abandoning the job. -->
              <Button
                variant="ghost"
                size="sm"
                :disabled="stopPending"
                title="Stop driving now. The mission is left alone."
                @click="cancelGoal"
              >
                <Hand :size="13" /> Cancel goal
              </Button>
            </div>
          </div>

          <template v-else>
            <!-- Stacked: the panel is narrow at any screen width. -->
            <div class="grid grid-cols-[minmax(0,1fr)_7.5rem] gap-xs">
              <div class="space-y-xxs">
                <p class="text-label uppercase text-muted">Route</p>
                <Select
                  label="Route"
                  :model-value="selectedMissionId"
                  :options="missionOptions"
                  placeholder="Choose…"
                  class="w-full"
                  @update:model-value="selectedMissionId = $event"
                />
              </div>

              <div class="space-y-xxs">
                <p class="text-label uppercase text-muted">Run mode</p>
                <Select
                  label="Run mode"
                  :model-value="missionMode"
                  :options="modeOptions"
                  class="w-full"
                  @update:model-value="missionMode = $event"
                />
              </div>
            </div>

            <div v-if="missionMode === 'laps'" class="max-w-[12rem] space-y-xxs">
              <p class="text-label uppercase text-muted">Laps</p>
              <Input
                :model-value="missionLaps"
                type="number"
                min="1"
                aria-label="Number of laps"
                @update:model-value="missionLaps = Math.max(1, Number($event))"
              />
            </div>

            <div class="flex flex-wrap items-center justify-between gap-sm">
              <p v-if="missionBlockReason" class="text-caption text-muted">
                {{ missionBlockReason }}
              </p>
              <span v-else class="text-caption text-status-ok">Ready to run</span>
              <Button
                size="sm"
                :disabled="missionPending || !selectedMissionId || !navReady"
                @click="startMission"
              >
                <Play :size="13" /> Start mission
              </Button>
            </div>
          </template>
          </section>
        </div>
      </aside>
    </div>
  </div>
</template>
