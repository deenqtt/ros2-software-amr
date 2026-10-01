/**
 * A goal that is still running while the robot is not moving.
 *
 * Nav2 does not give up on a goal it cannot start: the behaviour tree runs
 * `wait`, asks the planner again, fails again, and repeats. The goal stays
 * EXECUTING throughout, so a robot wedged against a wall reports "driving to
 * the goal" for as long as anyone is willing to watch. This is the part the
 * screen was missing — not why it is stuck, which needs the planner's own
 * reason, but that it is not getting anywhere.
 */

/**
 * Below this the robot is treated as stationary.
 *
 * Not zero, and that is not slack. Isaac Sim reports a small constant velocity
 * for a robot that is demonstrably parked — measured at 0.0011 m/s and
 * -0.0028 rad/s with the pose not changing at all — so a zero test would call
 * a stopped robot "moving" forever and this would never fire.
 */
export const STILL_LINEAR_MPS = 0.02
export const STILL_ANGULAR_RPS = 0.05

/** How long it has to stay still before the screen says so. */
export const STALL_AFTER_MS = 15_000

export interface StallInput {
  /** True while a navigation goal is accepted or executing. */
  goalRunning: boolean
  linear: number
  angular: number
  /** When the robot was last seen moving, or null if it has not been. */
  movingSince: number | null
  now: number
}

export interface StallState {
  stalled: boolean
  /** Milliseconds the robot has been still under a running goal. */
  stillFor: number
}

export function isMoving(linear: number, angular: number): boolean {
  return Math.abs(linear) > STILL_LINEAR_MPS || Math.abs(angular) > STILL_ANGULAR_RPS
}

/**
 * Whether to report a stall, given when the robot last moved.
 *
 * Only while a goal is running: a parked robot with nothing to do is still on
 * purpose, and calling that a stall would put a warning on every idle machine
 * in the fleet.
 */
export function stallState(input: StallInput): StallState {
  if (!input.goalRunning) return { stalled: false, stillFor: 0 }
  if (isMoving(input.linear, input.angular)) return { stalled: false, stillFor: 0 }
  if (input.movingSince === null) return { stalled: false, stillFor: 0 }

  const stillFor = Math.max(0, input.now - input.movingSince)
  return { stalled: stillFor >= STALL_AFTER_MS, stillFor }
}

export function stallLabel(stillFor: number): string {
  const seconds = Math.round(stillFor / 1000)
  if (seconds < 120) return `Not moving for ${seconds}s`
  return `Not moving for ${Math.round(seconds / 60)} min`
}
