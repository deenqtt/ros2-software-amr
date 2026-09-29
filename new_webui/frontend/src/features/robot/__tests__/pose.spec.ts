/**
 * The two pose messages this UI publishes.
 *
 * Both have a detail that is easy to get wrong and expensive to find: a robot
 * that silently refuses to localise reads as a broken robot, not as a malformed
 * message. These pin the details.
 */
import { describe, expect, it } from 'vitest'
import { goalPoseMessage, initialPoseMessage, yawToQuaternion } from '../pose'

describe('yawToQuaternion', () => {
  it('keeps a planar rotation planar', () => {
    const q = yawToQuaternion(1.2)
    expect(q.x).toBe(0)
    expect(q.y).toBe(0)
  })

  it('round-trips through atan2', () => {
    for (const yaw of [0, 0.5, Math.PI / 2, -Math.PI / 2, 3]) {
      const q = yawToQuaternion(yaw)
      const back = Math.atan2(2 * q.w * q.z, 1 - 2 * q.z * q.z)
      expect(back).toBeCloseTo(yaw, 9)
    }
  })

  it('gives the identity for zero', () => {
    expect(yawToQuaternion(0)).toEqual({ x: 0, y: 0, z: 0, w: 1 })
  })
})

describe('initialPoseMessage', () => {
  it('stamps zero, so simulated time cannot make AMCL drop it', () => {
    // A wall-clock stamp is hours from sim time; AMCL discards the message and
    // the robot never localises, with nothing anywhere saying why.
    expect(initialPoseMessage({ x: 1, y: 2, theta: 0 }).header.stamp).toEqual({
      sec: 0,
      nanosec: 0,
    })
  })

  it('is expressed in the map frame', () => {
    expect(initialPoseMessage({ x: 0, y: 0, theta: 0 }).header.frame_id).toBe('map')
  })

  it('claims confidence, not certainty', () => {
    // All zeros would collapse the particle cloud onto one point, which cannot
    // recover when the operator's guess was slightly off.
    const { covariance } = initialPoseMessage({ x: 0, y: 0, theta: 0 }).pose
    expect(covariance).toHaveLength(36)
    expect(covariance[0]).toBe(0.25) // x
    expect(covariance[7]).toBe(0.25) // y
    expect(covariance[35]).toBe(0.25) // yaw
    expect(covariance.filter((value) => value !== 0)).toHaveLength(3)
  })

  it('carries the pose it was given', () => {
    const message = initialPoseMessage({ x: -1.5, y: 2.25, theta: Math.PI / 2 })
    expect(message.pose.pose.position).toEqual({ x: -1.5, y: 2.25, z: 0 })
    expect(message.pose.pose.orientation.z).toBeCloseTo(Math.sin(Math.PI / 4), 9)
  })
})

describe('goalPoseMessage', () => {
  it('is a bare PoseStamped in the map frame', () => {
    const message = goalPoseMessage({ x: 3, y: -1, theta: 0 })
    expect(message.header.frame_id).toBe('map')
    expect(message.pose.position).toEqual({ x: 3, y: -1, z: 0 })
    // No covariance: a goal is a request, not a belief.
    expect(message.pose).not.toHaveProperty('covariance')
  })
})
