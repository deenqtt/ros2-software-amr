<script setup lang="ts">
/**
 * Mapping session.
 *
 * The session lives on the robot, not in this tab. Closing the page leaves the
 * robot in mapping mode, and reopening it rejoins — which is why the agent
 * republishes its status at 1 Hz rather than only on change.
 *
 * Driving publishes to /teleop/cmd_vel, never /cmd_vel. The agent relays it
 * and stops the robot when the stream goes quiet; nothing else in the stack
 * arbitrates or times out velocity commands, so that watchdog is the only
 * thing standing between a dropped wifi link and a robot that keeps going.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Gamepad2, Save, ScanLine, Square, TriangleAlert } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useFleetStore } from '@/stores/fleet'
import { useLinkStore } from '@/stores/links'
import { useMapStore } from '@/stores/maps'
import { useRosPool } from '@/app/ros/pool'
import { useGamepad } from '@/shared/composables/useGamepad'
import { useRobotTelemetry } from '../useRobotTelemetry'
import {
  SPEED_PRESETS,
  TELEOP_BLOCK_MESSAGE,
  TELEOP_PUBLISH_HZ,
  ZERO_TWIST,
  stickToTwist,
  teleopBlockedBy,
  type SpeedPreset,
  type Twist,
} from '@/domain/teleop'
import { SERVICE_TYPES } from '@/domain/ros/topics'
import { classifyMapSave, mapSaveFailureMessage } from '@/domain/mapSave'
import { radToDeg } from '@/domain/ros/quaternion'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { FormField } from '@/shared/ui/label'
import { Dialog } from '@/shared/ui/dialog'
import PanelToolbar from '@/shared/components/PanelToolbar.vue'
import SectionLabel from '@/shared/components/SectionLabel.vue'
import MetricTile from '@/shared/components/MetricTile.vue'
import LinkIndicator from '@/shared/components/LinkIndicator.vue'
import EmergencyStop from '@/shared/components/EmergencyStop.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ConfirmDialog from '@/shared/components/ConfirmDialog.vue'
import SlamIndicator from '../components/SlamIndicator.vue'
import LiveMapCanvas from '../components/LiveMapCanvas.vue'
import DriveJoystick from '../components/DriveJoystick.vue'
import { cn, formatNumber } from '@/shared/lib/utils'

const route = useRoute()
const router = useRouter()
const fleet = useFleetStore()
const links = useLinkStore()
const maps = useMapStore()
const pool = useRosPool()

const robotId = computed(() => String(route.params.robotId))
const robot = computed(() => fleet.byId(robotId.value))
const link = computed(() => links.linkFor(robotId.value))

const telemetry = useRobotTelemetry(() => robotId.value)

// ── Session state ────────────────────────────────────────────────────────────
const startingMode = ref(false)
const confirmStart = ref(false)
const saveOpen = ref(false)
const saving = ref(false)
const saveName = ref('')
const saveNote = ref('')
const saveError = ref<string | null>(null)

const mappingActive = computed(
  () => telemetry.agent.value?.mode === 'map' && telemetry.agent.value?.state === 'running',
)
const agentPresent = computed(() => telemetry.agent.value !== null)
const agentManaged = computed(() => telemetry.agent.value?.managed === true)

watch(
  robotId,
  async (id) => {
    if (!fleet.loaded) await fleet.load()
    links.sync(fleet.robots)
    links.focus(id)
    telemetry.reattach()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  stopDriving()
  links.focus(null)
})

// ── Driving ──────────────────────────────────────────────────────────────────
const preset = ref<SpeedPreset>(SPEED_PRESETS[1]!)
const command = ref<Twist>({ ...ZERO_TWIST })
const usingGamepad = ref(false)

const gamepad = useGamepad({
  onSample: (state) => {
    if (!state.connected) return
    usingGamepad.value = true
    const next = state.deadmanHeld
      ? stickToTwist(state.leftX, state.leftY, preset.value)
      : { ...ZERO_TWIST }
    command.value = next
  },
})

const gate = computed(() => ({
  linkOnline: link.value.state === 'online',
  mappingActive: mappingActive.value,
  deadmanHeld: gamepad.state.value.deadmanHeld,
  // The screen stick is its own deadman: letting go recentres it.
  deadmanRequired: usingGamepad.value && gamepad.state.value.connected,
  windowFocused: gamepad.windowFocused.value,
  gamepadLost: usingGamepad.value && !gamepad.state.value.connected,
}))

const blockedBy = computed(() => teleopBlockedBy(gate.value))
const driveBlockedMessage = computed(() =>
  blockedBy.value ? TELEOP_BLOCK_MESSAGE[blockedBy.value] : null,
)

let publishTimer: ReturnType<typeof setInterval> | null = null

/**
 * Publish at a steady rate rather than on every input event.
 *
 * The agent republishes at 20 Hz and stops the robot after 300 ms of silence,
 * so a steady stream is what keeps it alive — and a steady stream is also what
 * makes stopping a matter of ceasing to send.
 */
function startPublishing() {
  if (publishTimer !== null) return
  publishTimer = setInterval(() => {
    const client = pool.clientFor(robotId.value)
    if (!client) return
    const twist = blockedBy.value === null ? command.value : ZERO_TWIST
    client.publish('teleopCmdVel', {
      linear: { x: twist.linear, y: 0, z: 0 },
      angular: { x: 0, y: 0, z: twist.angular },
    })
  }, 1000 / TELEOP_PUBLISH_HZ)
}

function stopDriving() {
  command.value = { ...ZERO_TWIST }
  if (publishTimer !== null) {
    clearInterval(publishTimer)
    publishTimer = null
  }
  // One explicit zero, rather than trusting the watchdog to notice. The
  // watchdog is the backstop, not the mechanism.
  pool.clientFor(robotId.value)?.publish('teleopCmdVel', {
    linear: { x: 0, y: 0, z: 0 },
    angular: { x: 0, y: 0, z: 0 },
  })
}

watch(mappingActive, (active, wasActive) => {
  if (active) {
    startPublishing()
    return
  }
  stopDriving()
  // Only on a real transition out of mapping, not on first render: the stack
  // that produced this map is gone, so keeping it on screen would show a
  // live-looking survey of a robot that is no longer surveying.
  if (wasActive) telemetry.clear()
})

function onJoystick(twist: Twist) {
  usingGamepad.value = false
  command.value = twist
}

// ── Mode ─────────────────────────────────────────────────────────────────────
async function requestMode(mode: 'map' | 'stop'): Promise<void> {
  const client = pool.clientFor(robotId.value)
  if (!client) throw new Error('No connection to this robot')
  const response = await client.callService<{ result: string }>(
    'robotMode',
    SERVICE_TYPES.robotMode,
    { robot_mode: mode },
  )
  // The agent answers "ACCEPTED" or "REJECTED ...". Treating a refusal as
  // success is how the old UI reported things it had not done.
  if (!response.result?.startsWith('ACCEPTED')) {
    throw new Error(response.result || `The robot refused to switch to ${mode}`)
  }
}

async function startMapping() {
  confirmStart.value = false
  startingMode.value = true
  try {
    await requestMode('map')
    toast.success('Starting mapping', { description: 'SLAM is coming up; this takes a moment.' })
  } catch (error) {
    toast.error('Could not start mapping', {
      description: error instanceof Error ? error.message : String(error),
    })
  } finally {
    startingMode.value = false
  }
}

const stoppingMode = ref(false)
const confirmStop = ref(false)

/**
 * Shut SLAM down.
 *
 * Leaving the robot with no stack running is the safe resting state: it is not
 * navigating, not surveying, and not holding a map server open. Getting back
 * to work is an explicit mode request, which is the point.
 */
async function stopMapping(reason?: string) {
  confirmStop.value = false
  stoppingMode.value = true
  stopDriving()
  try {
    await requestMode('stop')
    toast.success('Mapping stopped', {
      description: reason ?? 'SLAM has been shut down. The robot is idle.',
    })
  } catch (error) {
    toast.error('Could not stop mapping', {
      description: error instanceof Error ? error.message : String(error),
    })
  } finally {
    stoppingMode.value = false
  }
}

/**
 * Whether this robot's agent can reach the registry at all.
 *
 * `not configured` is the dangerous one: the agent works, SLAM runs, the save
 * succeeds locally, and nothing ever appears in the map list.
 */
const registryUnreachable = computed(() => {
  const backend = telemetry.agent.value?.backend
  return backend === 'not configured' || backend === 'unreachable' || backend === 'error'
})

async function onSave() {
  const name = saveName.value.trim()
  if (!name) {
    saveError.value = 'A map name is required.'
    return
  }
  saving.value = true
  saveError.value = null
  try {
    const client = pool.clientFor(robotId.value)
    if (!client) throw new Error('No connection to this robot')
    const response = await client.callService<{ result: string }>(
      'mapSave',
      SERVICE_TYPES.robotMode,
      { robot_mode: name },
      180_000,
    )
    const outcome = classifyMapSave(response.result)
    if (outcome.kind !== 'published') throw new Error(mapSaveFailureMessage(outcome))

    await maps.load()
    saveOpen.value = false

    // The survey is finished, so the stack that was running it comes down.
    // Leaving SLAM up after a save means the robot keeps building a map
    // nobody asked for, and its next map load has to fight the running one.
    await stopMapping(`${name} is in the registry and SLAM has been shut down.`)

    // And then straight back to work.
    //
    // `nav` is the resting state of a robot that is powered on — the registry
    // defaults to it precisely so that assigning a map is enough to make a
    // robot useful, with no button in the production flow. Stopping SLAM goes
    // through /robot_mode stop, which the agent records as `idle`, and that is
    // right for an emergency stop and wrong here: a survey that ended normally
    // left the robot parked, and only an operator who knew to go and release it
    // could get it moving again.
    //
    // Deliberately not fatal. The map is saved and assigned; losing this note
    // costs one click on the dashboard, while failing here would throw away a
    // finished survey over it.
    try {
      await fleet.setMode(robotId.value, 'nav')
    } catch (error) {
      toast.warning('Robot is parked', {
        description:
          error instanceof Error
            ? `${error.message} — release it from the dashboard when you are ready.`
            : 'Release it from the dashboard when you are ready.',
      })
    }

    void router.push('/maps')
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : String(error)
  } finally {
    saving.value = false
  }
}

/**
 * Emergency stop.
 *
 * Drive commands cease first and synchronously — that is the part that must
 * not wait on a network round trip. Tearing the stack down follows, because
 * anything bad enough to reach for this button ends the survey.
 *
 * It still does not substitute for the physical E-STOP: this cuts what the
 * browser is asking for, not power to the motors.
 */
function onEmergencyStop() {
  stopDriving()
  toast.error('Stopped', {
    description: 'Drive commands halted and SLAM is shutting down. Use the physical E-STOP to cut power.',
  })
  void stopMapping('Stopped from the survey page.')
}

// ── Readouts ─────────────────────────────────────────────────────────────────
const poseTiles = computed(() => [
  { label: 'X', value: formatNumber(telemetry.pose.value?.x ?? null), unit: 'm' },
  { label: 'Y', value: formatNumber(telemetry.pose.value?.y ?? null), unit: 'm' },
  {
    label: 'θ',
    value: formatNumber(
      telemetry.pose.value ? radToDeg(telemetry.pose.value.theta) : null,
      1,
    ),
    unit: 'deg',
  },
])

const gridSummary = computed(() => {
  const info = telemetry.grid.value?.info
  if (!info) return 'No grid yet'
  const metres = `${formatNumber(info.width * info.resolution, 1)} × ${formatNumber(info.height * info.resolution, 1)} m`
  return `${info.width}×${info.height} px · ${metres}`
})
</script>

<template>
  <div class="p-lg">
    <EmptyState
      v-if="!robot"
      title="Robot not found"
      description="It may have been removed from the registry."
    >
      <template #action>
        <Button size="sm" variant="secondary" as-child>
          <RouterLink to="/maps">Back to maps</RouterLink>
        </Button>
      </template>
    </EmptyState>

    <div v-else class="space-y-base">
      <!--
        A survey run against an agent with no backend cannot be published. Saying
        so before the drive starts costs a banner; saying it after costs the map.
      -->
      <div
        v-if="registryUnreachable"
        class="flex items-start gap-xs rounded-surface border border-status-warn/40 bg-status-warn/10 p-sm text-xs text-body"
      >
        <TriangleAlert :size="14" class="mt-px shrink-0 text-status-warn" />
        <p>
          <span class="font-medium">This robot cannot publish maps.</span>
          Its agent reports the backend as
          <span class="font-ident">{{ telemetry.agent.value?.backend }}</span
          >, so a save will land on the robot's own disk and never reach the map
          list. Restart the robot with <span class="font-ident">AMR_BACKEND_URL</span> and
          <span class="font-ident">AMR_ROBOT_ID</span> set.
        </p>
      </div>

      <Card>
        <PanelToolbar :title="`Survey with ${robot.name}`" :subtitle="gridSummary">
          <template #icon><ScanLine :size="14" class="shrink-0 text-muted" /></template>
          <template #actions>
            <SlamIndicator :agent="telemetry.agent.value" />
            <LinkIndicator :state="link.state" :attempt="link.attempt" />
            <Button
              v-if="mappingActive || telemetry.agent.value?.state === 'starting'"
              variant="outline"
              size="sm"
              :disabled="stoppingMode"
              @click="confirmStop = true"
            >
              <Square :size="13" />
              {{ stoppingMode ? 'Stopping…' : 'Stop mapping' }}
            </Button>
            <EmergencyStop
              :connected="link.state === 'online'"
              :moving="command.linear !== 0 || command.angular !== 0"
              @stop="onEmergencyStop"
            />
            <Button variant="ghost" size="sm" as-child>
              <RouterLink to="/maps"><ArrowLeft :size="14" /> Maps</RouterLink>
            </Button>
          </template>
        </PanelToolbar>

        <!-- The agent is what makes mapping possible at all. Saying so beats
             offering a button that cannot work. -->
        <CardContent v-if="!agentPresent" class="p-base">
          <EmptyState
            title="No agent on this robot"
            description="The robot agent publishes /robot_mode_status and owns mode switching. Launch the robot with the agent running, or start SLAM on the robot by hand."
          />
        </CardContent>

        <CardContent v-else-if="!agentManaged" class="p-base">
          <EmptyState
            title="Mode switching is disabled"
            description="This robot was launched with a fixed mode, so the agent refuses to change it. Relaunch it in managed mode to survey from here."
          />
        </CardContent>

        <CardContent v-else-if="!mappingActive" class="p-base">
          <EmptyState
            title="Not mapping yet"
            :description="
              telemetry.agent.value?.state === 'starting'
                ? 'SLAM is coming up.'
                : 'Starting a survey stops whatever this robot is doing now.'
            "
          >
            <template #action>
              <Button
                size="sm"
                :disabled="startingMode || link.state !== 'online' || telemetry.agent.value?.state === 'starting'"
                @click="confirmStart = true"
              >
                {{ telemetry.agent.value?.state === 'starting' ? 'Starting…' : 'Start mapping' }}
              </Button>
            </template>
          </EmptyState>
        </CardContent>
      </Card>

      <div v-if="mappingActive" class="grid gap-base lg:grid-cols-[1fr_320px]">
        <Card class="overflow-hidden">
          <div class="h-[min(62vh,620px)]">
            <LiveMapCanvas
              :grid="telemetry.grid.value"
              :pose="telemetry.pose.value"
              :scan="telemetry.scan.value"
              :footprint="telemetry.footprint.value"
              :sensor-offset="telemetry.sensorOffset.value"
            />
          </div>
        </Card>

        <div class="space-y-base">
          <Card>
            <CardContent class="space-y-sm">
              <SectionLabel>
                <template #icon><Gamepad2 :size="12" /></template>
                Drive
              </SectionLabel>

              <div class="flex justify-center">
                <DriveJoystick
                  :preset="preset"
                  :disabled="blockedBy !== null && blockedBy !== 'deadman'"
                  @command="onJoystick"
                  @release="command = { ...ZERO_TWIST }"
                />
              </div>

              <div class="flex items-center gap-[2px] rounded-control bg-surface-strong p-[3px]">
                <button
                  v-for="option in SPEED_PRESETS"
                  :key="option.label"
                  type="button"
                  :class="
                    cn(
                      'h-7 flex-1 rounded-[6px] text-caption transition-colors',
                      preset.label === option.label
                        ? 'bg-surface text-ink'
                        : 'text-muted hover:text-ink',
                    )
                  "
                  @click="preset = option"
                >
                  {{ option.label }}
                </button>
              </div>

              <p
                v-if="driveBlockedMessage"
                class="rounded-control bg-status-warn/10 px-sm py-xs text-caption text-status-warn"
              >
                {{ driveBlockedMessage }}
              </p>
              <p v-else-if="gamepad.state.value.connected" class="text-caption text-muted">
                {{ gamepad.state.value.id.slice(0, 40) }} · hold L1 to drive
              </p>
              <p v-else class="text-caption text-muted">
                Drag the stick, or plug in a controller and hold L1.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent class="space-y-sm">
              <SectionLabel>Motion</SectionLabel>
              <div class="grid grid-cols-3 gap-xs">
                <MetricTile
                  v-for="tile in poseTiles"
                  :key="tile.label"
                  :label="tile.label"
                  :value="tile.value"
                  :unit="tile.unit"
                />
              </div>
              <!-- Commanded and measured side by side: the difference is what
                   tells an operator the robot is stuck or slipping, rather
                   than just replaying their own thumb. -->
              <div class="grid grid-cols-2 gap-xs">
                <MetricTile
                  label="Commanded"
                  :value="formatNumber(command.linear)"
                  unit="m/s"
                />
                <MetricTile
                  label="Measured"
                  :value="formatNumber(telemetry.velocity.value.linear)"
                  unit="m/s"
                />
              </div>
            </CardContent>
          </Card>

          <Button class="w-full" :disabled="!telemetry.grid.value" @click="saveOpen = true">
            <Save :size="15" /> Save map
          </Button>
          <p v-if="!telemetry.grid.value" class="text-center text-caption text-muted">
            Nothing to save until SLAM publishes a grid.
          </p>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :open="confirmStart"
      :title="`Start mapping with ${robot?.name ?? ''}?`"
      :description="`${robot?.name ?? 'This robot'} leaves navigation mode and starts SLAM. Any mission it is running is cancelled, and it cannot navigate until a map is loaded again.`"
      confirm-label="Start mapping"
      @update:open="(value: boolean) => (confirmStart = value)"
      @cancel="confirmStart = false"
      @confirm="startMapping"
    />

    <ConfirmDialog
      :open="confirmStop"
      :pending="stoppingMode"
      :title="`Stop mapping on ${robot?.name ?? ''}?`"
      description="SLAM shuts down and the robot goes idle. Anything surveyed since the last save is lost — the map only exists in the running stack until it is saved."
      confirm-label="Stop mapping"
      destructive
      @update:open="(value: boolean) => !value && !stoppingMode && (confirmStop = false)"
      @cancel="confirmStop = false"
      @confirm="stopMapping()"
    />

    <Dialog
      v-model:open="saveOpen"
      :pending="saving"
      title="Save map"
      description="The map is written to this robot's disk first, then published to the registry — so a survey survives the server being unreachable."
    >
      <form id="save-map" class="space-y-base" novalidate @submit.prevent="onSave">
        <FormField
          label="Map name"
          required
          hint="Re-using an existing name adds a version. Existing versions are never overwritten."
          :error="saveError ?? undefined"
        >
          <template #default="{ id, invalid }">
            <Input :id="id" v-model="saveName" :invalid="invalid" placeholder="Warehouse A" />
          </template>
        </FormField>
        <FormField label="Note" hint="Optional. What this survey covered.">
          <template #default="{ id }">
            <Input :id="id" v-model="saveNote" placeholder="Ground floor, east wing" />
          </template>
        </FormField>
      </form>
      <template #footer>
        <Button variant="secondary" size="sm" :disabled="saving" @click="saveOpen = false">
          Cancel
        </Button>
        <Button type="submit" form="save-map" size="sm" :disabled="saving">
          {{ saving ? 'Saving…' : 'Save' }}
        </Button>
      </template>
    </Dialog>
  </div>
</template>
