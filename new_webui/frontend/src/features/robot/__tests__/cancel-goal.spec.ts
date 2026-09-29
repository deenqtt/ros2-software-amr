import { describe, expect, it } from 'vitest'
import { cancelAllGoals } from '../cancelGoal'

describe('cancelAllGoals', () => {
  it('asks for every goal, not one numbered zero', () => {
    const request = cancelAllGoals()
    // 16 zero bytes plus a zero stamp is the action spec's wildcard. A real
    // uuid would cancel one goal, and the operator does not have one to give.
    expect(request.goal_info.goal_id.uuid).toHaveLength(16)
    expect(request.goal_info.goal_id.uuid.every((byte) => byte === 0)).toBe(true)
  })

  it('leaves the stamp at zero', () => {
    // A real stamp cancels only goals accepted at or before it. Under simulated
    // time the browser's clock is not the robot's, so the newest goal — the one
    // actually driving — would be the one left running.
    expect(cancelAllGoals().goal_info.stamp).toEqual({ sec: 0, nanosec: 0 })
  })

  it('builds a fresh request each time', () => {
    const first = cancelAllGoals()
    first.goal_info.goal_id.uuid[0] = 9
    expect(cancelAllGoals().goal_info.goal_id.uuid[0]).toBe(0)
  })
})
