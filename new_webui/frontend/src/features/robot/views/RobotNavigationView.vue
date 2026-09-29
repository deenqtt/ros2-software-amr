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
  ArrowLeft,
  Bell,
  BellOff,
  Bot,
  Crosshair,
  Hand,
  Navigation,
  Play,
  OctagonX,
  Radio,
  Square,
  X,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useMissionStore } from '@/stores/missions'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import { useZoneStore } from '@/stores/zones'
import { useRosPool } from '@/app/ros/pool'
import { useRobotTelemetry } from '@/features/mapping/useRobotTelemetry'
import { ZONE_KIND_LIST } from '@/features/zones/zoneKind'
import { goalPoseMessage, initialPoseMessage, type PlanarPose } from '../pose'
import { GOAL_OUTCOME_LABEL } from '../goalStatus'
import { cancelAllGoals } from '../cancelGoal'
import { SERVICE_TYPES } from '@/domain/ros/topics'
import RobotMapCanvas, { type MapTool } from '../components/RobotMapCanvas.vue'
import { RUN_MODE_LABEL, RUN_MODES, type RunMode } from '@/domain/types'
import { activityStatus, dockingStatus } from '@/domain/ros/status'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Select } from '@/shared/ui/select'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import LinkIndicator from '@/shared/components/LinkIndicator.vue'
import MetricTile from '@/shared/components/MetricTile.vue'
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

onMounted(async () => {
  if (!fleet.loaded) await fleet.load()
  links.sync(fleet.robots)
  links.focus(robotId.value)
})

watch(robotId, (id) => links.focus(id))
onBeforeUnmount(() => {
  links.focus(null)
  if (missionPoll !== null) clearInterval(missionPoll)
})

const activity = computed(() =>
  vitals.value.activity === null ? null : activityStatus(vitals.value.activity),
)
const docking = computed(() =>
  vitals.value.docking === null ? null : dockingStatus(vitals.value.docking),
)

const pool = useRosPool()
const zones = useZoneStore()
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
  robot: true,
})

const LAYER_LIST = [
  { key: 'costmap', label: 'Costmap', hint: 'What the planner thinks the floor costs' },
  { key: 'scan', label: 'Laser', hint: 'What the robot can see right now' },
  { key: 'particles', label: 'Particles', hint: 'Whether it knows where it is' },
  { key: 'plan', label: 'Plan', hint: 'Where it intends to go' },
  { key: 'zones', label: 'Zones', hint: 'Rules that apply on this map' },
] as const

watch(
  () => robot.value?.activeMapId,
  async (mapId) => {
    selectedMissionId.value = null
    if (mapId) {
      void zones.load(mapId)
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

let missionPoll: ReturnType<typeof setInterval> | null = null
watch(
  () => missions.liveRuns.length,
  (live) => {
    if (live > 0 && missionPoll === null) {
      missionPoll = setInterval(() => void missions.refreshRuns(), 2000)
    } else if (live === 0 && missionPoll !== null) {
      clearInterval(missionPoll)
      missionPoll = null
    }
  },
  { immediate: true },
)

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
const localization = computed(() => (telemetry.pose.value ? 'Pose available' : 'Waiting for pose'))

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

/**
 * Everything stops, and stays stopped.
 *
 * Three separate things, in this order and for a reason. Cancelling the goal
 * alone leaves the agent free to send the next step; cancelling the run alone
 * leaves the robot finishing the goal it already has. Parking last is what
 * stops it resuming: without it the registry still says `nav`, and the agent
 * reconciles back within its sync period.
 *
 * Each step is attempted even if an earlier one failed. A stop that gives up
 * halfway is worse than no stop at all, because it looks like it worked.
 *
 * This is not the physical E-STOP. It cuts what the software is asking for,
 * not power to the motors, and the button says so.
 */
async function emergencyStop() {
  const target = robot.value
  if (!target) return
  const failures: string[] = []
  stopPending.value = true
  try {
    const client = pool.clientFor(target.id)
    if (client) {
      try {
        await client.callService('cancelNavGoal', SERVICE_TYPES.cancelGoal, cancelAllGoals())
      } catch (error) {
        failures.push(`goal: ${error instanceof Error ? error.message : String(error)}`)
      }
    } else {
      failures.push('goal: no connection to this robot')
    }

    const run = activeRun.value
    if (run) {
      try {
        await missions.cancel(run.id)
      } catch (error) {
        failures.push(`mission: ${missions.describeError(error)}`)
      }
    }

    try {
      await fleet.setMode(target.id, 'idle')
    } catch (error) {
      failures.push(`park: ${error instanceof Error ? error.message : String(error)}`)
    }

    if (failures.length === 0) {
      toast.error('Stopped', {
        description: 'Goal canceled, mission canceled, robot parked. Use the physical E-STOP to cut power.',
      })
    } else {
      toast.error('Stopped, but not completely', { description: failures.join(' · ') })
    }
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
    toast.success(`${run.missionName} canceled`)
  } catch (error) {
    toast.error('Could not cancel the mission', { description: missions.describeError(error) })
  } finally {
    missionPending.value = false
  }
}
</script>

<template>
  <div class="space-y-base p-lg">
    <EmptyState
      v-if="!robot"
      title="Robot not found"
      description="It may have been removed from the registry."
    >
      <template #action>
        <Button size="sm" variant="secondary" as-child>
          <RouterLink to="/robot">Back to robots</RouterLink>
        </Button>
      </template>
    </EmptyState>

    <template v-else>
      <Card>
        <PanelToolbar :title="`${robot.name} navigation`" :subtitle="robot.bridgeUrl">
          <template #icon>
            <span
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white"
              :style="{ backgroundColor: `rgb(var(--robot-accent-${robot.accent}))` }"
            >
              <Bot :size="14" />
            </span>
          </template>
          <template #actions>
            <LinkIndicator :state="link.state" :attempt="link.attempt" />
            <!-- Always reachable, whatever else is on screen. A stop that has
                 to be found is not a stop. -->
            <Button
              variant="danger"
              size="sm"
              :disabled="stopPending"
              title="Cancel the goal, cancel the mission, and park the robot. Not the physical E-STOP."
              @click="emergencyStop"
            >
              <OctagonX :size="13" /> Stop
            </Button>
            <Button
              variant="outline"
              size="sm"
              :title="muted ? 'Resume monitoring' : 'Stop monitoring this robot'"
              @click="links.setMuted(robotId, !muted)"
            >
              <component :is="muted ? BellOff : Bell" :size="14" />
              {{ muted ? 'Muted' : 'Monitoring' }}
            </Button>
            <Button variant="ghost" size="sm" as-child>
              <RouterLink :to="`/robot/${robotId}/detail`"><Radio :size="14" /> Details</RouterLink>
            </Button>
            <Button variant="ghost" size="sm" as-child>
              <RouterLink to="/robot"><ArrowLeft :size="14" /> Back</RouterLink>
            </Button>
          </template>
        </PanelToolbar>
      </Card>

      <Card>
        <CardContent class="grid gap-sm sm:grid-cols-2 lg:grid-cols-5">
          <div class="rounded-control bg-surface-soft px-sm py-xs">
            <div class="text-label uppercase text-muted">Mode</div>
            <div class="mt-xxs text-body-sm font-medium uppercase">{{ agentMode }}</div>
          </div>
          <div class="rounded-control bg-surface-soft px-sm py-xs">
            <div class="text-label uppercase text-muted">Stack</div>
            <div class="mt-xxs text-body-sm font-medium uppercase">{{ agentState }}</div>
          </div>
          <div class="rounded-control bg-surface-soft px-sm py-xs">
            <div class="text-label uppercase text-muted">Localization</div>
            <div class="mt-xxs text-body-sm font-medium">{{ localization }}</div>
          </div>
          <!-- Goals leave on a topic, so nothing here waits on a result. This is
               the only place the answer arrives. -->
          <div class="rounded-control bg-surface-soft px-sm py-xs">
            <div class="text-label uppercase text-muted">Goal</div>
            <div
              class="mt-xxs text-body-sm font-medium"
              :class="{
                'text-status-ok': telemetry.goalOutcome.value === 'arrived',
                'text-status-fault': telemetry.goalOutcome.value === 'failed',
                'text-muted': telemetry.goalOutcome.value === 'none',
              }"
            >
              {{ GOAL_OUTCOME_LABEL[telemetry.goalOutcome.value] }}
            </div>
          </div>
          <div class="rounded-control bg-surface-soft px-sm py-xs">
            <div class="text-label uppercase text-muted">Active map</div>
            <div class="mt-xxs truncate text-body-sm font-medium" :title="robot.activeMapId ?? undefined">
              {{ robot.activeMapId || 'Not assigned' }}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <PanelToolbar title="Mission" subtitle="Run a saved route on this robot" />
        <CardContent class="space-y-base">
          <div v-if="activeRun" class="rounded-control border border-primary/30 bg-primary/5 p-sm">
            <div class="flex flex-wrap items-start justify-between gap-sm">
              <div>
                <div class="text-body-md font-medium text-ink">{{ activeRun.missionName }}</div>
                <div class="mt-xxs text-body-sm text-muted">
                  Step {{ activeRun.stepIndex + 1 }} ·
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
            <div class="grid gap-sm md:grid-cols-[minmax(0,1fr)_minmax(0,12rem)]">
              <div class="space-y-xxs">
                <p class="text-label uppercase text-muted">Mission</p>
                <Select
                  label="Mission"
                  :model-value="selectedMissionId"
                  :options="missionOptions"
                  placeholder="Choose a mission"
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
        </CardContent>
      </Card>

      <Card>
        <CardContent class="space-y-xs">
          <div class="flex flex-wrap items-center gap-base">
            <div class="flex gap-xxs">
              <button
                v-for="item in TOOLS"
                :key="item.value"
                type="button"
                :title="item.hint"
                :aria-pressed="tool === item.value"
                :class="
                  cn(
                    'flex h-control-sm items-center gap-xs rounded-control border px-sm text-body-sm transition-colors',
                    tool === item.value
                      ? 'border-primary bg-primary/10 text-ink'
                      : 'border-hairline text-body hover:border-primary',
                  )
                "
                @click="tool = item.value"
              >
                <component :is="item.icon" :size="13" />
                {{ item.label }}
              </button>
            </div>

            <span class="h-5 w-px bg-hairline" />

            <div class="flex flex-wrap gap-xxs">
              <button
                v-for="layer in LAYER_LIST"
                :key="layer.key"
                type="button"
                :title="layer.hint"
                :aria-pressed="layers[layer.key]"
                :class="
                  cn(
                    'rounded-chip border px-sm py-xxs text-caption transition-colors',
                    layers[layer.key]
                      ? 'border-primary bg-primary/10 text-ink'
                      : 'border-hairline text-muted hover:text-ink',
                  )
                "
                @click="layers[layer.key] = !layers[layer.key]"
              >
                {{ layer.label }}
              </button>
            </div>
          </div>

          <div class="h-[min(68vh,42rem)] overflow-hidden rounded-surface border border-hairline">
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
              :layers="layers"
              :tool="tool"
              @pick="onPick"
            >
              <template #legend>
                <span
                  v-for="kind in ZONE_KIND_LIST"
                  :key="kind.value"
                  class="flex items-center gap-xxs"
                >
                  <span class="h-2.5 w-2.5 rounded-[2px]" :style="{ backgroundColor: kind.colour }" />
                  {{ kind.label }}
                </span>
              </template>
            </RobotMapCanvas>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent class="grid gap-sm sm:grid-cols-2 lg:grid-cols-4">
          <MetricTile
            label="Battery"
            :value="formatPercent(vitals.battery.percent)"
            :unit="vitals.battery.charging ? 'charging' : undefined"
            size="lg"
          />
          <MetricTile label="Voltage" :value="formatNumber(vitals.battery.voltage, 1)" unit="V" size="lg" />
          <div class="rounded-control bg-surface-soft px-sm py-xs">
            <div class="text-label uppercase text-muted">Activity</div>
            <div class="mt-xxs">
              <StatusBadge v-if="activity" :tone="activity.tone" :label="activity.label" />
              <span v-else class="text-body-sm text-muted-soft">Not reported yet</span>
            </div>
          </div>
          <div class="rounded-control bg-surface-soft px-sm py-xs">
            <div class="text-label uppercase text-muted">Docking</div>
            <div class="mt-xxs">
              <StatusBadge v-if="docking" :tone="docking.tone" :label="docking.label" />
              <span v-else class="text-body-sm text-muted-soft">Not reported yet</span>
            </div>
          </div>
        </CardContent>
      </Card>

    </template>
  </div>
</template>
