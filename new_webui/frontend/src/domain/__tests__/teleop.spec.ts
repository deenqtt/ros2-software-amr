import { describe, expect, it } from 'vitest'
import {
  applyDeadzone,
  canDrive,
  clamp,
  SPEED_PRESETS,
  stickToTwist,
  teleopBlockedBy,
  type TeleopGate,
} from '../teleop'

const NORMAL = SPEED_PRESETS[1]!

function gate(overrides: Partial<TeleopGate> = {}): TeleopGate {
  return {
    linkOnline: true,
    mappingActive: true,
    deadmanHeld: true,
    deadmanRequired: true,
    windowFocused: true,
    gamepadLost: false,
    ...overrides,
  }
}

describe('applyDeadzone', () => {
  it('treats a resting stick as centred', () => {
    // Worn thumbsticks rest at a small non-zero value; without this a robot
    // drifts across a warehouse while nobody is touching the controller.
    expect(applyDeadzone(0.05)).toBe(0)
    expect(applyDeadzone(-0.05)).toBe(0)
  })

  it('rescales so the first effective input is gentle', () => {
    // Not 0.13: that would jump straight to deadzone-worth of speed.
    expect(applyDeadzone(0.13)).toBeCloseTo(0.011, 3)
  })

  it('keeps full deflection at full', () => {
    expect(applyDeadzone(1)).toBeCloseTo(1)
    expect(applyDeadzone(-1)).toBeCloseTo(-1)
  })
})

describe('clamp', () => {
  it('bounds in both directions', () => {
    expect(clamp(5, 2)).toBe(2)
    expect(clamp(-5, 2)).toBe(-2)
    expect(clamp(1, 2)).toBe(1)
  })
})

describe('stickToTwist', () => {
  it('maps a centred stick to a full stop', () => {
    expect(stickToTwist(0, 0, NORMAL)).toEqual({ linear: 0, angular: 0 })
  })

  it('maps full forward to the preset speed', () => {
    const twist = stickToTwist(0, 1, NORMAL)
    expect(twist.linear).toBeCloseTo(NORMAL.linear)
    expect(twist.angular).toBe(0)
  })

  it('treats positive x as a left turn, matching ROS', () => {
    // Screen coordinates grow rightward and downward; ROS does not. Callers
    // flip at the edge so the confusion lives in one place.
    expect(stickToTwist(1, 0, NORMAL).angular).toBeCloseTo(NORMAL.angular)
    expect(stickToTwist(-1, 0, NORMAL).angular).toBeCloseTo(-NORMAL.angular)
  })

  it('never exceeds the preset, even on out-of-range input', () => {
    const twist = stickToTwist(3, 3, NORMAL)
    expect(twist.linear).toBeLessThanOrEqual(NORMAL.linear)
    expect(twist.angular).toBeLessThanOrEqual(NORMAL.angular)
  })

  it('honours a slower preset', () => {
    const slow = SPEED_PRESETS[0]!
    expect(stickToTwist(0, 1, slow).linear).toBeCloseTo(slow.linear)
    expect(slow.linear).toBeLessThan(NORMAL.linear)
  })
})

describe('teleopBlockedBy', () => {
  it('allows driving when every condition is met', () => {
    expect(teleopBlockedBy(gate())).toBeNull()
    expect(canDrive(gate())).toBe(true)
  })

  it('blocks on a dead link before anything else', () => {
    expect(teleopBlockedBy(gate({ linkOnline: false, mappingActive: false }))).toBe('link')
  })

  it('blocks when the robot is not mapping', () => {
    // Nav2 owns /cmd_vel in navigation mode; the agent refuses the relay too.
    expect(teleopBlockedBy(gate({ mappingActive: false }))).toBe('mode')
  })

  it('blocks when the deadman is released', () => {
    expect(teleopBlockedBy(gate({ deadmanHeld: false }))).toBe('deadman')
  })

  it('does not demand a deadman when none is in use', () => {
    // The screen joystick is its own deadman: letting go ends the drag.
    expect(teleopBlockedBy(gate({ deadmanRequired: false, deadmanHeld: false }))).toBeNull()
  })

  it('blocks when the window loses focus', () => {
    // A controller resting on a bench with a stick pushed over must not keep
    // driving while the operator walks away.
    expect(teleopBlockedBy(gate({ windowFocused: false }))).toBe('focus')
  })

  it('blocks when a controller disappears mid-drive', () => {
    expect(teleopBlockedBy(gate({ gamepadLost: true }))).toBe('gamepad-lost')
  })

  it('reports the most actionable reason first', () => {
    const everything = gate({
      linkOnline: false,
      mappingActive: false,
      windowFocused: false,
      deadmanHeld: false,
      gamepadLost: true,
    })
    expect(teleopBlockedBy(everything)).toBe('link')
  })
})
