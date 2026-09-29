/**
 * Live telemetry for one robot, created per robot id.
 *
 * The old project had a single module-level store holding pose, battery, nav
 * status, docking, waypoints, keepout zones and costmap toggles for the one
 * robot that could exist (audit section 4, items 3-6). Here `useRobotStore(id)`
 * returns an independent store instance, so N robots can be live at once.
 *
 * Message payloads are deliberately NOT stored here — an OccupancyGrid's data
 * array is millions of entries and Vue would deep-proxy every one. Those go
 * in shallowRef state owned by the map layer.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { acceptsNewCommand, activityStatus, dockingStatus, isStale } from '@/domain/ros/status'
import type {
  Battery,
  ConnectionState,
  DockingState,
  Pose,
  RobotActivity,
  RobotFault,
  RobotMode,
  Velocity,
} from '@/domain/types'

/** How long a topic may be silent before its data is called stale. */
const STALENESS_BUDGET_MS: Record<string, number> = {
  pose: 2000,
  status: 5000,
  battery: 15000,
}

export const useRobotStore = (robotId: string) =>
  defineStore(`robot:${robotId}`, () => {
    const connection = ref<ConnectionState>('disconnected')
    const mode = ref<RobotMode>('unknown')
    const activity = ref<RobotActivity>('idle')
    const docking = ref<DockingState>('idle')

    const pose = ref<Pose>({ x: 0, y: 0, theta: 0 })
    const velocity = ref<Velocity>({ linear: 0, angular: 0 })
    const battery = ref<Battery>({ percent: null, voltage: null, charging: false })
    const faults = ref<RobotFault[]>([])

    const lastMessageAt = ref<Record<string, number>>({})

    const activityDescriptor = computed(() => activityStatus(activity.value))
    const dockingDescriptor = computed(() => dockingStatus(docking.value))

    const isConnected = computed(() => connection.value === 'connected')

    /** The single gate every command must consult before sending. */
    const canCommand = computed(() =>
      acceptsNewCommand(connection.value, activity.value, docking.value),
    )

    /**
     * True when the link is up but the robot has stopped talking. This is the
     * failure the old UI could not see at all: rosbridge alive, Nav2 dead,
     * pose frozen, badge still reading ONLINE / AVAILABLE.
     */
    const staleTopics = computed(() =>
      Object.entries(STALENESS_BUDGET_MS)
        .filter(([topic, budget]) => isStale(lastMessageAt.value[topic], budget))
        .map(([topic]) => topic),
    )

    const isTelemetryStale = computed(() => isConnected.value && staleTopics.value.length > 0)

    function markReceived(topic: string, at = Date.now()) {
      lastMessageAt.value[topic] = at
    }

    function setConnection(state: ConnectionState) {
      connection.value = state
      if (state === 'disconnected') {
        lastMessageAt.value = {}
        activity.value = 'idle'
        // Mode is a property of the robot, not of the link. It is unknown
        // again once we can no longer observe it.
        mode.value = 'unknown'
      }
    }

    function setPose(next: Pose) {
      pose.value = next
      markReceived('pose')
    }

    function setVelocity(next: Velocity) {
      velocity.value = next
    }

    function setBattery(next: Battery) {
      battery.value = next
      markReceived('battery')
    }

    function setActivity(next: RobotActivity) {
      activity.value = next
      markReceived('status')
    }

    function setDocking(next: DockingState) {
      docking.value = next
    }

    function setMode(next: RobotMode) {
      mode.value = next
    }

    function raiseFault(fault: RobotFault) {
      if (!faults.value.some((f) => f.id === fault.id)) faults.value.push(fault)
    }

    function clearFault(id: string) {
      faults.value = faults.value.filter((f) => f.id !== id)
    }

    function reset() {
      setConnection('disconnected')
      docking.value = 'idle'
      pose.value = { x: 0, y: 0, theta: 0 }
      velocity.value = { linear: 0, angular: 0 }
      battery.value = { percent: null, voltage: null, charging: false }
      faults.value = []
    }

    return {
      connection,
      mode,
      activity,
      docking,
      pose,
      velocity,
      battery,
      faults,
      lastMessageAt,
      activityDescriptor,
      dockingDescriptor,
      isConnected,
      canCommand,
      staleTopics,
      isTelemetryStale,
      markReceived,
      setConnection,
      setPose,
      setVelocity,
      setBattery,
      setActivity,
      setDocking,
      setMode,
      raiseFault,
      clearFault,
      reset,
    }
  })()
