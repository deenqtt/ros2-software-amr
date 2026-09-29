/**
 * Single mapping from robot state to the status vocabulary.
 *
 * The old UI had three overlapping implementations of this
 * (App.vue statusVariant, App.vue dockVariant, DockingPanel dockVariant) with
 * different shapes and inconsistent labels (audit section 6.2).
 */

import {
  ROBOT_STATUS_CODE,
  type ConnectionState,
  type DockingState,
  type RobotActivity,
  type StatusTone,
} from '../types/robot'

export interface StatusDescriptor {
  tone: StatusTone
  label: string
}

const ACTIVITY_STATUS: Record<RobotActivity, StatusDescriptor> = {
  idle: { tone: 'neutral', label: 'Idle' },
  navigating: { tone: 'active', label: 'Navigating' },
  executing: { tone: 'active', label: 'Executing' },
  docking: { tone: 'active', label: 'Docking' },
  undocking: { tone: 'active', label: 'Undocking' },
  charging: { tone: 'success', label: 'Charging' },
  waiting_confirm: { tone: 'attention', label: 'Waiting for confirm' },
  error: { tone: 'fault', label: 'Error' },
}

const DOCKING_STATUS: Record<DockingState, StatusDescriptor> = {
  idle: { tone: 'neutral', label: 'Not docked' },
  docking: { tone: 'active', label: 'Docking' },
  docked: { tone: 'success', label: 'Docked' },
  undocking: { tone: 'active', label: 'Undocking' },
  error: { tone: 'fault', label: 'Dock error' },
}

const CONNECTION_STATUS: Record<ConnectionState, StatusDescriptor> = {
  disconnected: { tone: 'fault', label: 'Offline' },
  connecting: { tone: 'warning', label: 'Connecting' },
  connected: { tone: 'success', label: 'Online' },
  reconnecting: { tone: 'warning', label: 'Reconnecting' },
}

export function activityStatus(activity: RobotActivity): StatusDescriptor {
  return ACTIVITY_STATUS[activity]
}

export function dockingStatus(state: DockingState): StatusDescriptor {
  return DOCKING_STATUS[state]
}

export function connectionStatus(state: ConnectionState): StatusDescriptor {
  return CONNECTION_STATUS[state]
}

/** Map RobotStatus.robot_current_sts onto an activity. */
export function activityFromStatusCode(code: number): RobotActivity {
  switch (code) {
    case ROBOT_STATUS_CODE.navigating:
      return 'navigating'
    case ROBOT_STATUS_CODE.docking:
      return 'docking'
    case ROBOT_STATUS_CODE.undocking:
      return 'undocking'
    case ROBOT_STATUS_CODE.charging:
      return 'charging'
    case ROBOT_STATUS_CODE.error:
      return 'error'
    default:
      return 'idle'
  }
}

/**
 * Whether the robot may accept a new navigation command.
 *
 * The old store computed an equivalent `isBusy` and documented it as a command
 * gate, then used it only to render a badge — nothing was ever disabled
 * (audit section 5.3). Anything that sends a goal must call this.
 */
export function acceptsNewCommand(
  connection: ConnectionState,
  activity: RobotActivity,
  docking: DockingState,
): boolean {
  if (connection !== 'connected') return false
  if (activity !== 'idle' && activity !== 'charging') return false
  if (docking === 'docking' || docking === 'undocking') return false
  return true
}

/** Battery tone. Charging outranks level, so a low-but-charging pack is not a fault. */
export function batteryTone(percent: number | null, charging: boolean): StatusTone {
  if (charging) return 'success'
  if (percent === null) return 'neutral'
  if (percent <= 10) return 'fault'
  if (percent <= 20) return 'warning'
  if (percent <= 40) return 'warning'
  return 'neutral'
}

/** A topic is stale once nothing has arrived for longer than its budget. */
export function isStale(lastMessageAt: number | undefined, budgetMs: number, now = Date.now()): boolean {
  if (lastMessageAt === undefined) return true
  return now - lastMessageAt > budgetMs
}
