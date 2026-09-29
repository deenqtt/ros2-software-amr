/**
 * "Goal sent" was the last thing the UI ever said.
 *
 * Goals go out on /goal_pose, a topic, so nothing on this side holds an action
 * handle to wait on. The robot arrived and the screen still showed the toast
 * from when the goal left — which reads as a robot that did not go.
 */
import { describe, expect, it } from 'vitest'
import { GOAL_STATUS, latestGoal, outcomeOf } from '../goalStatus'

function entry(status: number, sec: number, nanosec = 0) {
  return { status, goal_info: { stamp: { sec, nanosec } } }
}

describe('latestGoal', () => {
  it('reports nothing when no goal has been given', () => {
    expect(latestGoal(null)).toBeNull()
    expect(latestGoal({ status_list: [] })).toBeNull()
  })

  it('picks the newest goal by its stamp, not its position in the array', () => {
    // The server keeps every goal it still remembers and does not order them.
    // Reading the last element reports whichever it happened to put there —
    // during a retry, the one that already failed.
    const newest = latestGoal({
      status_list: [
        entry(GOAL_STATUS.executing, 200),
        entry(GOAL_STATUS.aborted, 100),
      ],
    })
    expect(newest?.status).toBe(GOAL_STATUS.executing)
  })

  it('compares sub-second stamps too', () => {
    const newest = latestGoal({
      status_list: [entry(GOAL_STATUS.aborted, 5, 900), entry(GOAL_STATUS.succeeded, 5, 100)],
    })
    expect(newest?.status).toBe(GOAL_STATUS.aborted)
  })
})

describe('outcomeOf', () => {
  it('treats accepted, executing and canceling as still going', () => {
    for (const status of [GOAL_STATUS.accepted, GOAL_STATUS.executing, GOAL_STATUS.canceling]) {
      expect(outcomeOf({ status, at: 1 })).toBe('running')
    }
  })

  it('separates arrival from cancellation and from failure', () => {
    expect(outcomeOf({ status: GOAL_STATUS.succeeded, at: 1 })).toBe('arrived')
    expect(outcomeOf({ status: GOAL_STATUS.canceled, at: 1 })).toBe('canceled')
    expect(outcomeOf({ status: GOAL_STATUS.aborted, at: 1 })).toBe('failed')
  })

  it('says nothing rather than guessing for an unknown code', () => {
    expect(outcomeOf({ status: GOAL_STATUS.unknown, at: 1 })).toBe('none')
    expect(outcomeOf(null)).toBe('none')
  })
})
