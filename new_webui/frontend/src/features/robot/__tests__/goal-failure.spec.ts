import { describe, expect, it } from 'vitest'
import { explainGoalFailure, type NavLogLine } from '../goalFailure'

const warn = (node: string, text: string): NavLogLine => ({ level: 30, node, text })
const error = (node: string, text: string): NavLogLine => ({ level: 40, node, text })

describe('explainGoalFailure', () => {
  it('recognises a robot Nav2 believes is inside an obstacle', () => {
    // Lifted from a real run: the robot sat clear in the simulator while the
    // map drew the doorway's wall thick enough to swallow its footprint.
    const result = explainGoalFailure([
      warn('controller_server', 'Optimizer fail to compute path'),
      error('controller_server', 'Controller patience exceeded'),
      warn('behavior_server', 'Collision Ahead - Exiting DriveOnHeading'),
      warn('behavior_server', 'backup failed'),
      error('bt_navigator', 'Goal failed'),
    ])
    expect(result.boxedIn).toBe(true)
    expect(result.reason).toContain('inside an obstacle')
  })

  it('separates a controller that cannot move from a boxed-in robot', () => {
    const result = explainGoalFailure([error('controller_server', 'Controller patience exceeded')])
    expect(result.boxedIn).toBe(false)
    expect(result.reason).toContain('controller')
  })

  it('names a planner failure', () => {
    expect(explainGoalFailure([warn('planner_server', 'Failed to create plan')]).reason).toContain(
      'no route',
    )
  })

  it('falls back to the last error rather than inventing a cause', () => {
    expect(explainGoalFailure([error('bt_navigator', 'Something unforeseen')]).reason).toBe(
      'bt_navigator: Something unforeseen',
    )
    expect(explainGoalFailure([]).reason).toBeNull()
  })
})
