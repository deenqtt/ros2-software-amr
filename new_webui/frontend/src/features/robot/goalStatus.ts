/**
 * What became of the navigation goal.
 *
 * Goals are published on /goal_pose, a plain topic that bt_navigator wraps into
 * an action on the robot's side. Nothing here holds an action handle, so there
 * is no result to await: the UI said "Goal sent" and then never spoke again,
 * whatever happened next. The action server publishes its own status, and this
 * turns that into something an operator can read.
 */

/** action_msgs/msg/GoalStatus status codes. */
export const GOAL_STATUS = {
  unknown: 0,
  accepted: 1,
  executing: 2,
  canceling: 3,
  succeeded: 4,
  canceled: 5,
  aborted: 6,
} as const

export type GoalOutcome = 'none' | 'running' | 'arrived' | 'canceled' | 'failed'

export interface GoalStatusEntry {
  status: number
  /** Nanoseconds since the epoch, from the goal's own stamp. */
  at: number
}

export interface GoalStatusArrayLike {
  status_list?: Array<{
    status?: number
    goal_info?: { stamp?: { sec?: number; nanosec?: number } }
  }>
}

function stampNs(stamp?: { sec?: number; nanosec?: number }): number {
  return (stamp?.sec ?? 0) * 1e9 + (stamp?.nanosec ?? 0)
}

/**
 * The newest goal in the list, by its own stamp.
 *
 * The array carries every goal the server still remembers, and it is not
 * ordered: reading the last element reports whichever goal the server happened
 * to put there, which during a retry is the one that already failed.
 */
export function latestGoal(message: GoalStatusArrayLike | null): GoalStatusEntry | null {
  const list = message?.status_list
  if (!list || list.length === 0) return null
  let newest: GoalStatusEntry | null = null
  for (const entry of list) {
    const candidate = { status: entry.status ?? GOAL_STATUS.unknown, at: stampNs(entry.goal_info?.stamp) }
    if (!newest || candidate.at > newest.at) newest = candidate
  }
  return newest
}

export function outcomeOf(entry: GoalStatusEntry | null): GoalOutcome {
  if (!entry) return 'none'
  switch (entry.status) {
    case GOAL_STATUS.accepted:
    case GOAL_STATUS.executing:
    case GOAL_STATUS.canceling:
      return 'running'
    case GOAL_STATUS.succeeded:
      return 'arrived'
    case GOAL_STATUS.canceled:
      return 'canceled'
    case GOAL_STATUS.aborted:
      return 'failed'
    default:
      return 'none'
  }
}

export const GOAL_OUTCOME_LABEL: Record<GoalOutcome, string> = {
  none: 'No goal',
  running: 'Driving to the goal',
  arrived: 'Arrived',
  canceled: 'Goal canceled',
  // Deliberately not "failed to navigate": Nav2 aborts for reasons that are
  // usually about the map or the surroundings, not the robot.
  failed: 'Could not reach it',
}
