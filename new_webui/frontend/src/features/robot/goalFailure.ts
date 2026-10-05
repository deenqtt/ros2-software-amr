/**
 * Why a navigation goal failed, from what Nav2 logged while it ran.
 *
 * Goals go out on /goal_pose, a topic, so nothing returns a result: the goal
 * status says "aborted" and no more. Nav2 does say why — in its log — and that
 * reaches the browser on /rosout. Read the WARN and ERROR lines from the
 * navigation nodes during the goal, and say what they add up to.
 */

/** rcl_interfaces/msg/Log levels. */
export const LOG_WARN = 30

/** The nodes whose complaints explain a navigation goal. */
export const NAV2_NODES = new Set([
  'bt_navigator',
  'controller_server',
  'planner_server',
  'behavior_server',
  'collision_monitor',
  'smoother_server',
  'velocity_smoother',
])

export interface NavLogLine {
  level: number
  node: string
  text: string
}

export interface GoalFailure {
  /** One sentence for the operator, or null when the log says nothing useful. */
  reason: string | null
  /**
   * Nav2 believes the robot is already touching an obstacle: every trajectory
   * is rejected and the recoveries refuse to move it in either direction. A
   * new goal will fail the same way until the robot is moved clear — or the
   * map stops saying there is a wall where there is none.
   */
  boxedIn: boolean
}

function any(lines: NavLogLine[], pattern: RegExp): boolean {
  return lines.some((line) => pattern.test(line.text))
}

export function explainGoalFailure(lines: NavLogLine[]): GoalFailure {
  const noTrajectory = any(lines, /fail to compute path|no valid trajector/i)
  const collisionAhead = any(lines, /collision ahead/i)
  const boxedIn = noTrajectory && collisionAhead

  if (boxedIn) {
    return {
      reason: 'Nav2 thinks the robot is inside an obstacle and will not move it in any direction.',
      boxedIn,
    }
  }
  if (any(lines, /goal.*(occupied|lethal|in collision|not free)|start.*occupied/i)) {
    return { reason: 'The goal, or the robot itself, sits on an obstacle in the costmap.', boxedIn }
  }
  if (any(lines, /failed to create (a )?plan|no valid path|could not find (a )?path|planner.*fail/i)) {
    return { reason: 'The planner found no route to the goal.', boxedIn }
  }
  if (any(lines, /outside.*(map|costmap|bounds)|out of bounds/i)) {
    return { reason: 'The goal is outside the map.', boxedIn }
  }
  if (any(lines, /failed to make progress/i)) {
    return { reason: 'The robot stopped making progress towards the goal.', boxedIn }
  }
  if (noTrajectory || any(lines, /controller patience exceeded/i)) {
    return { reason: 'The controller found no safe way to move the robot.', boxedIn }
  }
  const lastError = [...lines].reverse().find((line) => line.level > LOG_WARN)
  return { reason: lastError ? `${lastError.node}: ${lastError.text}` : null, boxedIn }
}
