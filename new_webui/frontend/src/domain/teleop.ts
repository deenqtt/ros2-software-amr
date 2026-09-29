/**
 * Teleoperation maths and safety rules.
 *
 * Kept free of Vue and of the browser so the rules that stop a robot can be
 * tested without mounting anything — and so the same rules apply whether the
 * command came from a thumbstick, a screen joystick or a keyboard.
 *
 * The browser publishes to /teleop/cmd_vel, never to /cmd_vel. The robot agent
 * relays it and stops the robot when the stream goes quiet, which is what
 * makes driving over wifi survivable.
 */

export interface Twist {
  linear: number
  angular: number
}

export const ZERO_TWIST: Twist = { linear: 0, angular: 0 }

export interface SpeedPreset {
  label: string
  linear: number
  angular: number
}

export const SPEED_PRESETS: readonly SpeedPreset[] = [
  { label: 'Slow', linear: 0.15, angular: 0.5 },
  { label: 'Normal', linear: 0.3, angular: 1.0 },
  { label: 'Fast', linear: 0.5, angular: 1.5 },
] as const

/** Publish rate. The agent republishes at 20 Hz and times out at 300 ms. */
export const TELEOP_PUBLISH_HZ = 12

/**
 * Stick input below this is treated as centred.
 *
 * Worn thumbsticks rest at a small non-zero value. Without a deadzone a robot
 * drifts across a warehouse while nobody is touching the controller.
 */
export const STICK_DEADZONE = 0.12

export function applyDeadzone(value: number, deadzone: number = STICK_DEADZONE): number {
  if (Math.abs(value) < deadzone) return 0
  // Rescale so the first effective input is a gentle one rather than a jump
  // from nothing to deadzone-worth of speed.
  const sign = Math.sign(value)
  return sign * ((Math.abs(value) - deadzone) / (1 - deadzone))
}

export function clamp(value: number, limit: number): number {
  return Math.max(-limit, Math.min(limit, value))
}

/**
 * Convert a normalised stick position into a velocity command.
 *
 * `y` is forward-positive and `x` is left-positive, which is the ROS
 * convention — not the screen convention, where y grows downward. Callers
 * reading a pointer or a gamepad axis have to flip it before calling, and
 * doing that at the edge keeps the sign confusion in one place.
 */
export function stickToTwist(x: number, y: number, preset: SpeedPreset): Twist {
  return {
    linear: clamp(applyDeadzone(y) * preset.linear, preset.linear),
    angular: clamp(applyDeadzone(x) * preset.angular, preset.angular),
  }
}

/** Every reason the UI may refuse to send a command. */
export type TeleopBlock =
  | 'link'
  | 'mode'
  | 'deadman'
  | 'focus'
  | 'gamepad-lost'
  | null

export interface TeleopGate {
  /** The robot's link is healthy enough to command. */
  linkOnline: boolean
  /** The robot is in mapping mode and running. */
  mappingActive: boolean
  /** A deadman control is held, when one is required. */
  deadmanHeld: boolean
  /** A deadman is required — true while a gamepad is driving. */
  deadmanRequired: boolean
  /** The browser tab is focused. */
  windowFocused: boolean
  /** A gamepad was in use and has gone away. */
  gamepadLost: boolean
}

/**
 * Why driving is blocked, or null when it is allowed.
 *
 * Ordered by what the operator should fix first, so the UI can show one
 * reason rather than a list.
 */
export function teleopBlockedBy(gate: TeleopGate): TeleopBlock {
  if (!gate.linkOnline) return 'link'
  if (!gate.mappingActive) return 'mode'
  if (gate.gamepadLost) return 'gamepad-lost'
  // A controller left resting on a bench with a stick pushed over must not
  // keep driving while the operator walks away, so focus is part of the gate.
  if (!gate.windowFocused) return 'focus'
  if (gate.deadmanRequired && !gate.deadmanHeld) return 'deadman'
  return null
}

export function canDrive(gate: TeleopGate): boolean {
  return teleopBlockedBy(gate) === null
}

export const TELEOP_BLOCK_MESSAGE: Record<NonNullable<TeleopBlock>, string> = {
  link: 'No link to this robot.',
  mode: 'The robot is not in mapping mode.',
  deadman: 'Hold the deadman button to drive.',
  focus: 'Click the page to take control.',
  'gamepad-lost': 'The controller disconnected.',
}
