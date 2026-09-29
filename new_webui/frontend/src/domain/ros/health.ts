/**
 * Topic health.
 *
 * The distinction this file exists for: **not every silent topic is a sick
 * topic.** Three cadences behave completely differently, and treating them
 * alike produces either false alarms or blindness.
 *
 *  - `periodic`  published on a timer. Silence past its budget is a fault.
 *  - `event`     published only when something changes. Silence is normal and
 *                says nothing; a robot parked all morning is correctly quiet.
 *  - `latched`   transient_local, delivered once on subscribe. Silence after
 *                the first message is normal; never receiving one is a fault.
 *
 * Marking `/plan` stale because the robot is not navigating would train an
 * operator to ignore the colour — which is worse than showing nothing.
 */

import { MESSAGE_TYPES, THROTTLE_MS } from './topics'

export type Cadence = 'periodic' | 'event' | 'latched'

/** Which connection tier a topic belongs to. See the pool for why. */
export type Tier = 'vitals' | 'full'

export interface TopicSpec {
  /** Key in the name registry, not the wired name — namespacing resolves later. */
  key: string
  messageType: string
  cadence: Cadence
  tier: Tier
  /** Milliseconds of silence before a periodic topic is stale. */
  budgetMs?: number
  /** rosbridge throttle_rate. 0 or absent means unthrottled. */
  throttleMs?: number
  /**
   * Published only while a SLAM or Nav2 stack is up.
   *
   * A robot at rest — agent alive, no stack running — is the designed resting
   * state, and in it these topics are correctly silent. Counting that silence
   * as staleness marks a healthy robot as faulty, and the survey dialog then
   * refuses to offer it, so a second survey can never be started.
   */
  needsStack?: boolean
  /** Human label for the diagnostics table. */
  label: string
}

/**
 * Budgets are deliberately several times the expected period. A single dropped
 * message is not a fault; a topic that has gone quiet is.
 */
export const TOPIC_SPECS: readonly TopicSpec[] = [
  // ── vitals: cheap enough to run for every robot in the fleet at once ──────
  {
    key: 'robotStatus',
    label: 'Robot status',
    messageType: MESSAGE_TYPES.robotStatus,
    // No timer in mission_manager — it publishes only on a state change, so a
    // robot that has been idle since this morning sends nothing at all. That
    // makes "connected but state unknown" a normal condition, not an error.
    cadence: 'event',
    tier: 'vitals',
  },
  {
    key: 'batteryState',
    label: 'Battery',
    messageType: MESSAGE_TYPES.batteryState,
    cadence: 'periodic',
    budgetMs: 6000, // battery_sim_node publishes at 1 Hz
    throttleMs: THROTTLE_MS.battery,
    tier: 'vitals',
  },
  {
    key: 'dockStatus',
    label: 'Dock status',
    messageType: MESSAGE_TYPES.string,
    cadence: 'periodic',
    budgetMs: 6000, // docking_manager has a 1 Hz timer
    tier: 'vitals',
  },

  // ── full: only for the robot currently being looked at ───────────────────
  {
    key: 'robotModeStatus',
    label: 'Agent status',
    messageType: MESSAGE_TYPES.string,
    // The agent repeats itself at 1 Hz precisely so a page opened mid-session
    // learns the robot is already mapping instead of offering to start again.
    cadence: 'periodic',
    budgetMs: 5000,
    tier: 'vitals',
  },
  {
    key: 'tf',
    needsStack: true,
    label: 'Transforms',
    messageType: MESSAGE_TYPES.tfMessage,
    cadence: 'periodic',
    budgetMs: 2000,
    throttleMs: THROTTLE_MS.tf,
    tier: 'full',
  },
  {
    key: 'tfStatic',
    label: 'Static transforms',
    messageType: MESSAGE_TYPES.tfMessage,
    // Latched: sensor mounts do not move, so they are published once. They are
    // what put a laser scan where the sensor actually is rather than at the
    // robot's centre.
    cadence: 'latched',
    tier: 'full',
  },
  {
    key: 'odom',
    label: 'Odometry',
    messageType: MESSAGE_TYPES.odometry,
    cadence: 'periodic',
    budgetMs: 3000,
    throttleMs: THROTTLE_MS.odom,
    tier: 'full',
  },
  {
    key: 'scan',
    label: 'Laser scan',
    messageType: MESSAGE_TYPES.laserScan,
    cadence: 'periodic',
    budgetMs: 3000,
    throttleMs: THROTTLE_MS.scan,
    tier: 'full',
  },
  {
    key: 'map',
    label: 'Map',
    messageType: MESSAGE_TYPES.occupancyGrid,
    cadence: 'latched',
    tier: 'full',
  },
  {
    key: 'costmap',
    needsStack: true,
    label: 'Global costmap',
    messageType: MESSAGE_TYPES.occupancyGrid,
    cadence: 'periodic',
    budgetMs: 6000,
    throttleMs: THROTTLE_MS.costmap,
    tier: 'full',
  },
  {
    key: 'plan',
    label: 'Planned path',
    messageType: MESSAGE_TYPES.path,
    cadence: 'event',
    tier: 'full',
  },
  {
    key: 'navGoalStatus',
    label: 'Goal status',
    messageType: MESSAGE_TYPES.goalStatusArray,
    // Published when a goal changes state and not otherwise. Silence means no
    // goal has been given, which is not a fault.
    cadence: 'event',
    tier: 'full',
  },
  {
    key: 'particleCloud',
    label: 'Particle cloud',
    messageType: MESSAGE_TYPES.particleCloud,
    cadence: 'event',
    throttleMs: THROTTLE_MS.particleCloud,
    tier: 'full',
  },
  {
    key: 'robotDescription',
    label: 'Robot description',
    messageType: MESSAGE_TYPES.string,
    cadence: 'latched',
    tier: 'full',
  },
] as const

export function specsForTier(tier: Tier): TopicSpec[] {
  return tier === 'vitals'
    ? TOPIC_SPECS.filter((spec) => spec.tier === 'vitals')
    : [...TOPIC_SPECS]
}

/** What we know about one topic on one robot, right now. */
export interface TopicHealth {
  key: string
  label: string
  cadence: Cadence
  tier: Tier
  /** Whether a subscription is currently open. */
  subscribed: boolean
  messages: number
  lastMessageAt: number | null
  state: TopicState
  /** Messages per second over the recent window; null until measurable. */
  rateHz: number | null
  /** See TopicSpec.needsStack. */
  needsStack: boolean
}

export type TopicState =
  /** Not subscribed — this tier is not active. */
  | 'idle'
  /** Subscribed, nothing received yet. */
  | 'waiting'
  /** Receiving, or quiet in a way that is normal for its cadence. */
  | 'ok'
  /** Periodic topic that has gone silent past its budget. */
  | 'stale'

export interface TopicSample {
  subscribed: boolean
  messages: number
  lastMessageAt: number | null
}

export function topicState(
  spec: TopicSpec,
  sample: TopicSample,
  now: number = Date.now(),
): TopicState {
  if (!sample.subscribed) return 'idle'
  if (sample.lastMessageAt === null) return 'waiting'

  // Event and latched topics are allowed to be quiet forever once they have
  // spoken. Only a periodic topic owes us a heartbeat.
  if (spec.cadence !== 'periodic') return 'ok'

  const budget = spec.budgetMs ?? 5000
  return now - sample.lastMessageAt > budget ? 'stale' : 'ok'
}

/**
 * Whether the robot as a whole should read as stale.
 *
 * Only periodic topics in the active tier can trigger it, and only after they
 * have delivered at least one message: a topic that has never spoken is
 * `waiting`, which is a different and less alarming thing than one that spoke
 * and then stopped.
 */
export function anyStale(
  healths: readonly TopicHealth[],
  stackRunning: boolean = true,
): boolean {
  return healths.some(
    (health) => health.state === 'stale' && (stackRunning || !health.needsStack),
  )
}
