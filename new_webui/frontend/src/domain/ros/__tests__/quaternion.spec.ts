import { describe, expect, it } from 'vitest'
import {
  degToRad,
  normalizeAngle,
  quaternionToYaw,
  radToDeg,
  yawToQuaternion,
} from '../quaternion'

describe('quaternion', () => {
  it('round-trips yaw', () => {
    for (const yaw of [0, 0.5, -0.5, Math.PI / 2, -Math.PI / 2, 2]) {
      expect(quaternionToYaw(yawToQuaternion(yaw))).toBeCloseTo(yaw, 10)
    }
  })

  it('treats a partial quaternion as identity', () => {
    // rosbridge omits zero-valued fields on the wire.
    expect(quaternionToYaw({ w: 1 })).toBe(0)
    expect(quaternionToYaw({})).toBe(0)
    expect(quaternionToYaw(null)).toBe(0)
    expect(quaternionToYaw(undefined)).toBe(0)
  })

  it('reads yaw from a partial quaternion carrying only z and w', () => {
    const q = yawToQuaternion(Math.PI / 4)
    expect(quaternionToYaw({ z: q.z, w: q.w })).toBeCloseTo(Math.PI / 4, 10)
  })

  it('normalizes angles into (-pi, pi]', () => {
    expect(normalizeAngle(0)).toBeCloseTo(0)
    expect(normalizeAngle(3 * Math.PI)).toBeCloseTo(Math.PI)
    expect(normalizeAngle(-3 * Math.PI)).toBeCloseTo(Math.PI)
    expect(normalizeAngle(1.5 * Math.PI)).toBeCloseTo(-0.5 * Math.PI)
  })

  it('converts between radians and degrees', () => {
    expect(radToDeg(Math.PI)).toBeCloseTo(180)
    expect(degToRad(180)).toBeCloseTo(Math.PI)
  })
})
