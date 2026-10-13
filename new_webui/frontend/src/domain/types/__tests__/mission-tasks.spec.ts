/**
 * Step tasks and the numbers the robot receives for them.
 *
 * The numbers are master_control's Station_Action_t on MissionPlan.dest_tasks;
 * the backend (TASK_TO_WIRE) and the agent (MISSION_TASK_WIRE) use the same.
 */
import { describe, expect, it } from 'vitest'
import { STEP_TASK_LABEL, STEP_TASK_WIRE, STEP_TASKS } from '../mission'

describe('step tasks', () => {
  it('match the robot numbering', () => {
    expect(STEP_TASK_WIRE).toEqual({ none: 0, pick: 1, drop: 2, drop_pick: 3 })
  })

  it('all have a label for the editor', () => {
    for (const task of STEP_TASKS) expect(STEP_TASK_LABEL[task]).toBeTruthy()
    expect(STEP_TASK_LABEL.drop_pick).toBe('Drop & pick')
  })
})
