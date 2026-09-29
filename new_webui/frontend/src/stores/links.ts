/**
 * Live link state for every robot in the registry.
 *
 * One store for the whole fleet rather than one per robot: the Robot table and
 * the Dashboard both need every row at once, and N stores would mean N
 * subscriptions to keep in step.
 *
 * It owns no sockets. The pool does that; this is the reactive projection of
 * what the pool reports.
 */
import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import { useRosPool } from '@/app/ros/pool'
import { anyStale, type TopicHealth } from '@/domain/ros/health'
import { deriveLinkState, type LinkState } from '@/domain/ros/link'
import { activityFromStatusCode } from '@/domain/ros/status'
import type { ClientSnapshot } from '@/domain/ros/client'
import type { Battery, DockingState, RobotActivity } from '@/domain/types'
import type { RobotConfig } from '@/domain/types'

export interface RobotLink {
  state: LinkState
  attempt: number
  lastError: string | null
  /**
   * Raw message payloads are never stored. An OccupancyGrid's data array runs
   * to millions of entries and Vue would deep-proxy every one of them; only
   * counts and timestamps live here.
   */
  topics: TopicHealth[]
}

export interface RobotVitals {
  activity: RobotActivity | null
  docking: DockingState | null
  battery: Battery
}

function emptyLink(): RobotLink {
  return { state: 'offline', attempt: 0, lastError: null, topics: [] }
}

function emptyVitals(): RobotVitals {
  return {
    // null, not 'idle'. /robot_status has no timer, so a robot parked since
    // this morning sends nothing — and guessing "idle" would be inventing a
    // fact about a machine nobody has heard from.
    activity: null,
    docking: null,
    battery: { percent: null, voltage: null, charging: false },
  }
}

const DOCK_STATES: Record<string, DockingState> = {
  idle: 'idle',
  navigating_to_approach: 'docking',
  navigating_to_dock: 'docking',
  docked: 'docked',
  undocking: 'undocking',
  error: 'error',
}

export const useLinkStore = defineStore('links', () => {
  const pool = useRosPool()

  const links = ref<Record<string, RobotLink>>({})
  const vitals = ref<Record<string, RobotVitals>>({})
  const muted = ref<Record<string, boolean>>({})
  // shallowRef: the handler set is swapped wholesale, never read reactively.
  const messageUnsubscribers = shallowRef<Record<string, () => void>>({})
  let started = false

  function linkFor(robotId: string): RobotLink {
    return links.value[robotId] ?? emptyLink()
  }

  function vitalsFor(robotId: string): RobotVitals {
    return vitals.value[robotId] ?? emptyVitals()
  }

  function stateFor(robotId: string): LinkState {
    return linkFor(robotId).state
  }

  const onlineCount = computed(
    () => Object.values(links.value).filter((link) => link.state === 'online').length,
  )
  const faultCount = computed(
    () =>
      Object.values(links.value).filter(
        (link) => link.state === 'offline' || link.state === 'stale',
      ).length,
  )

  /**
   * Whether each robot currently has a SLAM or Nav2 stack up.
   *
   * Read from the agent's own status rather than inferred from topic traffic:
   * the whole point is to tell "the stack is down, so /tf is correctly quiet"
   * apart from "/tf has gone quiet and something is wrong". Absent until the
   * agent speaks, and treated as running until then, so a robot with no agent
   * keeps the behaviour it had before.
   */
  const stackUp = ref<Record<string, boolean>>({})

  function applySnapshot(robotId: string, snapshot: ClientSnapshot): void {
    links.value = {
      ...links.value,
      [robotId]: {
        state: deriveLinkState({
          muted: Boolean(muted.value[robotId]),
          socketOpen: snapshot.socketOpen,
          connecting: snapshot.connecting,
          hasStaleTopic: anyStale(snapshot.topics, stackUp.value[robotId] ?? true),
        }),
        attempt: snapshot.attempt,
        lastError: snapshot.lastError,
        topics: snapshot.topics,
      },
    }
  }

  /** Pull the few fields the fleet views need out of the vitals topics. */
  function handleMessage(robotId: string, key: string, message: unknown): void {
    const current = vitalsFor(robotId)
    let next: RobotVitals | null = null

    if (key === 'robotStatus') {
      const msg = message as {
        robot_current_sts?: number
        robot_docked?: boolean
        charging_state?: boolean
        battery_percentage?: number
        battery_voltage?: number
      }
      next = {
        activity: activityFromStatusCode(msg.robot_current_sts ?? 0),
        docking: msg.robot_docked ? 'docked' : current.docking,
        battery: {
          percent: msg.battery_percentage ?? current.battery.percent,
          voltage: msg.battery_voltage ?? current.battery.voltage,
          charging: Boolean(msg.charging_state || msg.robot_docked),
        },
      }
    } else if (key === 'batteryState') {
      const msg = message as { percentage?: number; voltage?: number; power_supply_status?: number }
      next = {
        ...current,
        battery: {
          // sensor_msgs/BatteryState carries 0..1; the UI shows a percentage.
          percent: msg.percentage === undefined ? current.battery.percent : Math.round(msg.percentage * 100),
          voltage: msg.voltage ?? current.battery.voltage,
          charging: msg.power_supply_status === 1 || current.battery.charging,
        },
      }
    } else if (key === 'robotModeStatus') {
      // The agent publishes this at 1 Hz whatever it is doing, so it is also
      // the heartbeat that proves the robot is reachable while every
      // stack-owned topic is legitimately silent.
      try {
        const status = JSON.parse(String((message as { data?: string }).data ?? '')) as {
          state?: string
        }
        stackUp.value = { ...stackUp.value, [robotId]: status.state === 'running' }
      } catch {
        // A malformed status tells us nothing; leave the last known value.
      }
    } else if (key === 'dockStatus') {
      const raw = String((message as { data?: string }).data ?? '')
        .trim()
        .toLowerCase()
      const docking = DOCK_STATES[raw]
      if (docking) next = { ...current, docking }
    }

    if (next) vitals.value = { ...vitals.value, [robotId]: next }
  }

  /** Idempotent: safe to call from every view that needs live state. */
  function start(): void {
    if (started) return
    started = true
    pool.onSnapshot(applySnapshot)
  }

  function sync(robots: readonly RobotConfig[]): void {
    start()
    pool.sync(robots)

    const ids = new Set(robots.map((r) => r.id))
    const handlers = { ...messageUnsubscribers.value }

    for (const [id, off] of Object.entries(handlers)) {
      if (!ids.has(id)) {
        off()
        delete handlers[id]
      }
    }
    for (const robot of robots) {
      if (handlers[robot.id]) continue
      const client = pool.clientFor(robot.id)
      if (!client) continue
      handlers[robot.id] = client.onMessage((key, message) =>
        handleMessage(robot.id, key, message),
      )
    }
    messageUnsubscribers.value = handlers

    // Drop state for robots that left the registry.
    for (const map of [links, vitals] as const) {
      const pruned = Object.fromEntries(
        Object.entries(map.value).filter(([id]) => ids.has(id)),
      )
      map.value = pruned as never
    }
  }

  /** Promote one robot to full telemetry; null demotes everyone. */
  function focus(robotId: string | null): void {
    pool.focus(robotId)
  }

  function setMuted(robotId: string, value: boolean): void {
    muted.value = { ...muted.value, [robotId]: value }
    pool.setMuted(robotId, value)
    // Mute has to show immediately, not after the next snapshot.
    applySnapshot(robotId, {
      socketOpen: false,
      connecting: false,
      attempt: 0,
      tier: null,
      lastError: null,
      topics: value ? [] : linkFor(robotId).topics,
    })
  }

  function isMuted(robotId: string): boolean {
    return Boolean(muted.value[robotId])
  }

  return {
    links,
    vitals,
    onlineCount,
    faultCount,
    linkFor,
    vitalsFor,
    stateFor,
    sync,
    focus,
    setMuted,
    isMuted,
  }
})
