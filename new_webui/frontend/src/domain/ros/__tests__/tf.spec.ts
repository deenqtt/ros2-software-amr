import { describe, expect, it } from 'vitest'
import { composeTransform, TfBuffer, type TransformStamped } from '../tf'
import { yawToQuaternion } from '../quaternion'

function stamped(parent: string, child: string, tx: number, ty: number, yaw: number): TransformStamped {
  return {
    header: { frame_id: parent },
    child_frame_id: child,
    transform: { translation: { x: tx, y: ty }, rotation: yawToQuaternion(yaw) },
  }
}

describe('composeTransform', () => {
  it('is identity when the parent is identity', () => {
    const child = { tx: 2, ty: 3, yaw: 0.4 }
    expect(composeTransform({ tx: 0, ty: 0, yaw: 0 }, child)).toEqual(child)
  })

  it('rotates the child translation into the parent frame', () => {
    const result = composeTransform({ tx: 0, ty: 0, yaw: Math.PI / 2 }, { tx: 1, ty: 0, yaw: 0 })
    expect(result.tx).toBeCloseTo(0, 10)
    expect(result.ty).toBeCloseTo(1, 10)
    expect(result.yaw).toBeCloseTo(Math.PI / 2, 10)
  })

  it('adds translations after rotating', () => {
    const result = composeTransform({ tx: 5, ty: -2, yaw: Math.PI }, { tx: 2, ty: 0, yaw: 0.1 })
    expect(result.tx).toBeCloseTo(3, 10)
    expect(result.ty).toBeCloseTo(-2, 10)
    expect(result.yaw).toBeCloseTo(Math.PI + 0.1, 10)
  })
})

describe('TfBuffer', () => {
  it('returns undefined until both links are present', () => {
    const buffer = new TfBuffer()
    expect(buffer.resolveMapToBase()).toBeUndefined()
    expect(buffer.hasMapToOdom()).toBe(false)

    buffer.ingest([stamped('map', 'odom', 1, 0, 0)])
    expect(buffer.hasMapToOdom()).toBe(true)
    expect(buffer.resolveMapToBase()).toBeUndefined()

    buffer.ingest([stamped('odom', 'base_footprint', 2, 0, 0)])
    expect(buffer.resolveMapToBase()).toEqual({ x: 3, y: 0, theta: 0 })
  })

  it('composes a rotated chain', () => {
    const buffer = new TfBuffer()
    buffer.ingest([
      stamped('map', 'odom', 0, 0, Math.PI / 2),
      stamped('odom', 'base_link', 2, 0, 0),
    ])
    const pose = buffer.resolveMapToBase()
    expect(pose?.x).toBeCloseTo(0, 10)
    expect(pose?.y).toBeCloseTo(2, 10)
    expect(pose?.theta).toBeCloseTo(Math.PI / 2, 10)
  })

  it('accepts odom_combined and base_link variants', () => {
    const buffer = new TfBuffer()
    buffer.ingest([
      stamped('map', 'odom_combined', 1, 1, 0),
      stamped('odom_combined', 'base_link', 1, 0, 0),
    ])
    expect(buffer.resolveMapToBase()).toEqual({ x: 2, y: 1, theta: 0 })
  })

  it('strips leading slashes and namespace prefixes from frame ids', () => {
    const buffer = new TfBuffer()
    buffer.ingest([
      stamped('/map', '/odom', 1, 0, 0),
      stamped('amr_01/odom', 'amr_01/base_footprint', 1, 0, 0),
    ])
    expect(buffer.resolveMapToBase()).toEqual({ x: 2, y: 0, theta: 0 })
  })

  it('overwrites rather than accumulating repeated transforms', () => {
    const buffer = new TfBuffer()
    buffer.ingest([stamped('map', 'odom', 1, 0, 0), stamped('odom', 'base_footprint', 0, 0, 0)])
    buffer.ingest([stamped('map', 'odom', 5, 0, 0)])
    expect(buffer.size).toBe(2)
    expect(buffer.resolveMapToBase()).toEqual({ x: 5, y: 0, theta: 0 })
  })

  it('clears, so a reconnect never reuses stale transforms', () => {
    const buffer = new TfBuffer()
    buffer.ingest([stamped('map', 'odom', 1, 0, 0), stamped('odom', 'base_footprint', 1, 0, 0)])
    buffer.clear()
    expect(buffer.size).toBe(0)
    expect(buffer.resolveMapToBase()).toBeUndefined()
  })
})
