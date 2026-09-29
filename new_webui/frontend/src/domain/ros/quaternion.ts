/** Planar (yaw-only) quaternion helpers. Ported from web-ui useROS.js:1210-1221. */

export interface Quaternion {
  x: number
  y: number
  z: number
  w: number
}

export function yawToQuaternion(yaw: number): Quaternion {
  return { x: 0, y: 0, z: Math.sin(yaw * 0.5), w: Math.cos(yaw * 0.5) }
}

/**
 * Extract yaw from a quaternion. Tolerates partial messages — rosbridge omits
 * zero-valued fields, so `{ w: 1 }` is a legal identity rotation on the wire.
 */
export function quaternionToYaw(q: Partial<Quaternion> | null | undefined): number {
  if (!q) return 0
  const x = q.x ?? 0
  const y = q.y ?? 0
  const z = q.z ?? 0
  const w = q.w ?? 1
  return Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
}

/** Wrap an angle to (-pi, pi]. */
export function normalizeAngle(angle: number): number {
  let a = angle % (2 * Math.PI)
  if (a > Math.PI) a -= 2 * Math.PI
  if (a <= -Math.PI) a += 2 * Math.PI
  return a
}

export function radToDeg(rad: number): number {
  return (rad * 180) / Math.PI
}

export function degToRad(deg: number): number {
  return (deg * Math.PI) / 180
}
