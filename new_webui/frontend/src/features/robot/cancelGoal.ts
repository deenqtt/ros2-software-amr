/**
 * Stop the robot where it is.
 *
 * Goals are sent on /goal_pose, a topic, so there is no handle to cancel
 * through. The action server exposes its own cancel service, and this builds
 * the request for it.
 */

/**
 * action_msgs/srv/CancelGoal request.
 *
 * Indexable because it is handed straight to the service caller, which takes
 * any JSON object — the shape is documented here rather than lost in a cast.
 */
export interface CancelGoalRequest {
  [key: string]: unknown
  goal_info: {
    goal_id: { uuid: number[] }
    stamp: { sec: number; nanosec: number }
  }
}

/**
 * Cancel every goal the server is holding.
 *
 * A zero uuid with a zero stamp is the wildcard: the action spec reads it as
 * "all goals" rather than as a goal that happens to be numbered zero. That is
 * what is wanted here — a person pressing stop means the robot, not one
 * particular goal they would have to identify first.
 *
 * Sending a real stamp would cancel only goals accepted at or before it, and
 * under simulated time the browser's clock is not the robot's: the newest goal,
 * the one actually driving, would be the one left running.
 */
export function cancelAllGoals(): CancelGoalRequest {
  return {
    goal_info: {
      goal_id: { uuid: new Array<number>(16).fill(0) },
      stamp: { sec: 0, nanosec: 0 },
    },
  }
}
