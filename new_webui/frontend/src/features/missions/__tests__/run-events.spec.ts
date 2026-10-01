import { describe, expect, it } from 'vitest'
import { diffRun, diffRuns } from '../runEvents'
import type { MissionRun } from '@/domain/types'

function run(overrides: Partial<MissionRun> = {}): MissionRun {
  return {
    id: 'run-1',
    missionId: 'mission-1',
    missionName: 'Shuttle',
    robotId: 'robot-1',
    mode: 'once',
    lapsTarget: null,
    lap: 1,
    stepIndex: 0,
    reachedLap: null,
    reachedIndex: null,
    reachedAt: null,
    state: 'running',
    detail: null,
    startedAt: '2026-10-01 08:00:00',
    endedAt: null,
    ...overrides,
  }
}

const kinds = (events: { kind: string }[]) => events.map((event) => event.kind)

describe('diffRun', () => {
  it('announces a run seen for the first time while it is live', () => {
    expect(kinds(diffRun(undefined, run()))).toEqual(['started'])
  })

  it('says nothing when nothing changed', () => {
    expect(diffRun(run(), run())).toEqual([])
  })

  it('does not call moving on to the next step an arrival', () => {
    // step_index is written before the robot sets off, so it is not "got there".
    expect(diffRun(run(), run({ stepIndex: 1 }))).toEqual([])
  })

  it('reports an arrival when the server stamps one', () => {
    const arrived = run({ reachedLap: 1, reachedIndex: 0, reachedAt: '2026-10-01 08:01:00' })
    expect(kinds(diffRun(run(), arrived))).toEqual(['reached'])
  })

  it('reports the same step on the next lap as a new arrival', () => {
    const before = run({ lap: 1, reachedLap: 1, reachedIndex: 0, reachedAt: '08:01:00' })
    const after = run({ lap: 2, reachedLap: 2, reachedIndex: 0, reachedAt: '08:05:00' })
    expect(kinds(diffRun(before, after))).toEqual(['reached'])
  })

  it('reports the last arrival and the ending from one poll', () => {
    // The final stop and "done" land within the same couple of seconds.
    const before = run({ stepIndex: 1, reachedLap: 1, reachedIndex: 0, reachedAt: '08:01:00' })
    const after = run({
      stepIndex: 1,
      reachedLap: 1,
      reachedIndex: 1,
      reachedAt: '08:02:00',
      state: 'done',
    })
    expect(kinds(diffRun(before, after))).toEqual(['reached', 'done'])
  })

  it.each([
    ['failed', 'failed'],
    ['canceled', 'canceled'],
    ['done', 'done'],
  ] as const)('reports a run ending as %s', (state, kind) => {
    expect(kinds(diffRun(run(), run({ state })))).toEqual([kind])
  })

  it('reports an ending once, not on every poll after it', () => {
    expect(diffRun(run({ state: 'failed' }), run({ state: 'failed' }))).toEqual([])
  })

  it('does not treat stop-after-lap as an ending', () => {
    expect(diffRun(run(), run({ state: 'stopping' }))).toEqual([])
  })
})

describe('diffRuns', () => {
  it('stays quiet on the first poll', () => {
    // A page opened in the afternoon must not announce the morning's runs.
    expect(diffRuns(null, [run({ state: 'done' }), run({ id: 'run-2' })])).toEqual([])
  })

  it('announces a run that started and finished between two polls', () => {
    const events = diffRuns(new Map(), [run({ state: 'done' })])
    expect(kinds(events)).toEqual(['done'])
  })

  it('diffs each run against its own previous sighting', () => {
    const previous = new Map([['run-1', run()]])
    const events = diffRuns(previous, [run({ state: 'failed' }), run({ id: 'run-2' })])
    expect(events.map((event) => [event.run.id, event.kind])).toEqual([
      ['run-1', 'failed'],
      ['run-2', 'started'],
    ])
  })
})
