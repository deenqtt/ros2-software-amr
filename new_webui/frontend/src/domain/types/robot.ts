/** Operational status vocabulary. One scale for the whole UI. */
export type StatusTone = 'neutral' | 'active' | 'attention' | 'warning' | 'fault' | 'success'

/** Link state of the rosbridge WebSocket. */
export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'

/**
 * What the robot's stack is actually running.
 *
 * `unknown` is the honest default. The old UI inferred mode from a local flag
 * that /api/mode/switch set optimistically, so it could claim Navigation while
 * the robot was still running SLAM (see audit section 3.2). Until a
 * /robot_mode server exists and reports back, this stays `unknown`.
 */
export type RobotMode = 'unknown' | 'mapping' | 'navigation'

/** Robot activity, derived from custom_interfaces/msg/RobotStatus. */
export type RobotActivity =
  | 'idle'
  | 'navigating'
  | 'executing'
  | 'docking'
  | 'undocking'
  | 'charging'
  | 'waiting_confirm'
  | 'error'

export type DockingState = 'idle' | 'docking' | 'docked' | 'undocking' | 'error'

/**
 * RobotStatus.robot_current_sts values — as master_control actually fills them
 * (master_control_node.cpp): 0 available/idle, 1 moving (driving, docking or
 * undocking), 2 waiting for the operator's "OK". The codes 3-5 the message
 * declares are never published; treating them as anything in particular would
 * be a guess dressed up as data.
 */
export const ROBOT_STATUS_CODE = {
  idle: 0,
  moving: 1,
  waitingVerification: 2,
} as const

/**
 * The one status word for a robot, shared by the dashboard, the robot page and
 * the mission list. Derived by the agent (amr_agent/robot_status.py) and read
 * from the registry — never re-derived per surface, which is how code 2 was
 * once rendered as "Docking".
 */
export type RobotStatusValue =
  | 'parked'
  | 'mapping'
  | 'ready'
  | 'on_mission'
  | 'waiting_confirm'
  | 'charging'
  | 'error'
  | 'paused'

/** A robot as configured in the registry, not as observed. */
export interface RobotConfig {
  id: string
  name: string
  /** rosbridge WebSocket, e.g. ws://192.168.1.50:8765 */
  bridgeUrl: string
  /**
   * ROS_DOMAIN_ID. Optional: it only matters when something on the operator's
   * own machine speaks DDS directly. The browser reaches the robot through
   * rosbridge, which does not care about the domain — so leaving this empty is
   * the normal case, not an incomplete record.
   */
  rosDomainId: number | null
  /** web_video_server base, e.g. http://192.168.1.50:8080 */
  cameraUrl: string | null
  /** Topic namespace. Empty for one-bridge-per-robot. */
  namespace: string
  /** 1-8, indexes the --robot-accent-N tokens. Identity only, never status. */
  accent: number
  serial: string | null
  /**
   * The map this robot is meant to be running, or null when none is assigned.
   *
   * Assignment is per robot, not global. Robots in one building normally share
   * a map — they have to, or a station at (12.4, 3.1) names a different
   * physical place for each — but one being re-surveyed while another keeps
   * working is exactly what a single global setting cannot express.
   */
  activeMapId: string | null
  /**
   * What this robot is *supposed* to be doing, as opposed to what it is doing.
   *
   * `nav` is the resting state and the default — a robot that is powered on and
   * has a map should be ready for work, without anyone pressing a button. Nav2
   * running is not the robot moving: an idle planner plans nothing, and the
   * robot only moves when a mission gives it a goal.
   */
  desiredMode: DesiredMode
  /**
   * Whether this robot's agent has a token issued. The token itself is never
   * readable after it is generated. Optional so fixtures that predate the
   * field stay valid; absent means not set.
   */
  agentTokenSet?: boolean
  /** When the current agent token was generated, or null when there is none. */
  agentTokenCreatedAt?: string | null
  /**
   * The robot's own word for what it is doing, as reported by its agent.
   *
   * Null until the agent's first report arrives. Not the same question as
   * `desiredMode`, which is what the robot is supposed to be doing; both are
   * shown, and disagreeing is exactly what an operator needs to see.
   */
  status?: RobotStatusValue | null
  /** One line of context from the robot, e.g. "docking at Table 3". */
  statusDetail?: string
  /** When the current status began (server clock). */
  statusSince?: string | null
  /** When the last report arrived. Older than a few heartbeats = offline. */
  statusReportedAt?: string | null
}

/**
 * Valid ROS_DOMAIN_ID range.
 *
 * 0-232 is what the platform accepts; 0-101 is the range that is safe on every
 * OS without colliding with ephemeral ports. Values above 101 are allowed here
 * and warned about rather than rejected, because a fleet may already be using
 * them.
 */
export const ROS_DOMAIN_ID_MAX = 232
export const ROS_DOMAIN_ID_SAFE_MAX = 101

export interface Pose {
  x: number
  y: number
  theta: number
}

export interface Velocity {
  linear: number
  angular: number
}

export interface Battery {
  percent: number | null
  voltage: number | null
  charging: boolean
}

/**
 * Live, observed state of one robot.
 *
 * `lastMessageAt` exists so staleness is detectable. The old UI compared no
 * timestamps at all, so a dead Nav2 behind a live rosbridge read as
 * ONLINE/AVAILABLE indefinitely (audit section 5.4).
 */
export interface RobotTelemetry {
  connection: ConnectionState
  mode: RobotMode
  activity: RobotActivity
  docking: DockingState
  pose: Pose
  velocity: Velocity
  battery: Battery
  /** Per-topic wall-clock timestamp of the last received message. */
  lastMessageAt: Record<string, number>
  faults: RobotFault[]
}

export interface RobotFault {
  id: string
  severity: 'warning' | 'fault'
  message: string
  since: number
}

export const DESIRED_MODES = ['nav', 'idle', 'map'] as const
export type DesiredMode = (typeof DESIRED_MODES)[number]

export const DESIRED_MODE_LABEL: Record<DesiredMode, string> = {
  nav: 'Working',
  idle: 'Parked',
  map: 'Surveying',
}
