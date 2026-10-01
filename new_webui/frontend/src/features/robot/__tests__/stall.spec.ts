import { describe, expect, it } from 'vitest'
import { isMoving, stallState, stallLabel, STALL_AFTER_MS } from '../stall'

describe('isMoving', () => {
  it('does not call a simulator idle velocity movement', () => {
    // Isaac reports this for a robot whose pose is not changing at all. A zero
    // test would treat it as driving and the stall would never be reported.
    expect(isMoving(0.0011, -0.0028)).toBe(false)
  })

  it('counts turning on the spot as moving', () => {
    expect(isMoving(0, 0.4)).toBe(true)
  })

  it('counts creeping forward as moving', () => {
    expect(isMoving(0.05, 0)).toBe(true)
  })
})

describe('stallState', () => {
  const still = { linear: 0.001, angular: 0.001 }

  it('says nothing about a robot with no goal', () => {
    // A parked robot is stopped on purpose. Warning about it would put a
    // fault on every idle machine in the fleet.
    expect(
      stallState({ goalRunning: false, ...still, movingSince: 0, now: 10 * STALL_AFTER_MS }),
    ).toEqual({ stalled: false, stillFor: 0 })
  })

  it('waits before calling it a stall', () => {
    const early = stallState({ goalRunning: true, ...still, movingSince: 0, now: STALL_AFTER_MS - 1 })
    expect(early.stalled).toBe(false)
    expect(early.stillFor).toBe(STALL_AFTER_MS - 1)
  })

  it('reports once the robot has been still long enough under a goal', () => {
    const late = stallState({ goalRunning: true, ...still, movingSince: 0, now: STALL_AFTER_MS })
    expect(late.stalled).toBe(true)
  })

  it('clears as soon as the robot moves again', () => {
    expect(
      stallState({ goalRunning: true, linear: 0.3, angular: 0, movingSince: 0, now: 10 * STALL_AFTER_MS }),
    ).toEqual({ stalled: false, stillFor: 0 })
  })

  it('says nothing until the robot has been seen moving at least once', () => {
    // Otherwise a page opened onto an already-idle robot reports a stall that
    // began before anyone was watching.
    expect(
      stallState({ goalRunning: true, ...still, movingSince: null, now: 10 * STALL_AFTER_MS }),
    ).toEqual({ stalled: false, stillFor: 0 })
  })
})

describe('stallLabel', () => {
  it('counts in seconds, then in minutes', () => {
    expect(stallLabel(45_000)).toBe('Not moving for 45s')
    expect(stallLabel(300_000)).toBe('Not moving for 5 min')
  })
})
