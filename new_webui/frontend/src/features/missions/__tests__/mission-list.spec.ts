import { describe, expect, it } from 'vitest'
import {
  lastFinishedRun,
  missionStatus,
  routePreview,
  runProgress,
  serverTime,
  timeAgo,
} from '../missionList'
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
    state: 'done',
    detail: null,
    startedAt: '2026-10-01 08:00:00',
    endedAt: '2026-10-01 08:05:00',
    ...overrides,
  }
}

describe('lastFinishedRun', () => {
  it('picks the newest finished run of that mission', () => {
    const runs = [
      run({ id: 'old', startedAt: '2026-10-01 07:00:00', state: 'failed' }),
      run({ id: 'new', startedAt: '2026-10-01 09:00:00' }),
      run({ id: 'other', missionId: 'mission-2', startedAt: '2026-10-01 10:00:00' }),
    ]
    expect(lastFinishedRun(runs, 'mission-1')?.id).toBe('new')
  })

  it('skips a run that is still live', () => {
    const runs = [
      run({ id: 'live', state: 'running', startedAt: '2026-10-01 09:00:00' }),
      run({ id: 'done', startedAt: '2026-10-01 08:00:00' }),
    ]
    expect(lastFinishedRun(runs, 'mission-1')?.id).toBe('done')
  })

  it('is null for a mission never run', () => {
    expect(lastFinishedRun([run()], 'mission-9')).toBeNull()
  })
})

describe('routePreview', () => {
  const name = (id: string) => id.toUpperCase()

  it('shows a short route whole', () => {
    expect(routePreview(['a', 'b', 'a'], name)).toEqual({ shown: ['A', 'B', 'A'], hidden: 0 })
  })

  it('keeps both ends of a long route and counts the middle', () => {
    expect(routePreview(['a', 'b', 'c', 'd', 'e', 'f'], name)).toEqual({
      shown: ['A', 'B', 'C', 'F'],
      hidden: 2,
    })
  })
})

describe('server time', () => {
  it('reads a zoneless SQLite timestamp as UTC', () => {
    expect(serverTime('2026-10-01 08:00:00')).toBe(Date.UTC(2026, 9, 1, 8, 0, 0))
  })

  it('formats elapsed time coarsely', () => {
    const now = Date.UTC(2026, 9, 1, 12, 0, 0)
    expect(timeAgo('2026-10-01 11:59:50', now)).toBe('just now')
    expect(timeAgo('2026-10-01 11:55:00', now)).toBe('5m ago')
    expect(timeAgo('2026-10-01 09:00:00', now)).toBe('3h ago')
    expect(timeAgo('2026-09-29 12:00:00', now)).toBe('2d ago')
  })
})

describe('runProgress', () => {
  const names: Record<string, string> = { a: 'Dock', b: 'Line 1', c: 'Line 2' }
  const nameOf = (id: string) => names[id] ?? id

  it('names the stop the robot is heading to, and how far along it is', () => {
    expect(runProgress(1, ['a', 'b', 'c'], nameOf)).toBe('→ Line 1 (2/3)')
  })

  it('falls back to the bare index when the route is not loaded', () => {
    expect(runProgress(1, null, nameOf)).toBe('step 2')
    expect(runProgress(0, [], nameOf)).toBe('step 1')
  })

  it('drops the count when the route was shortened under a live run', () => {
    expect(runProgress(5, ['a', 'b'], nameOf)).toBe('step 6')
  })
})

describe('missionStatus', () => {
  const now = Date.UTC(2026, 9, 1, 12, 0, 0)
  const names: Record<string, string> = { 'robot-1': 'R1', 'robot-2': 'R2' }
  const robotName = (id: string | null) => (id ? (names[id] ?? 'retired robot') : '—')
  const mission = { id: 'mission-1', stepCount: 4 }

  it('says which robot is running it and how far along', () => {
    const live = run({ state: 'running', stepIndex: 1, endedAt: null })
    expect(missionStatus(mission, live, [live], now, robotName)).toEqual({
      tone: 'text-status-run',
      label: 'Running · R1 · step 2 of 4',
      detail: null,
    })
  })

  it('says a run is stopping after its lap', () => {
    const live = run({ state: 'stopping', endedAt: null })
    const status = missionStatus(mission, live, [live], now, robotName)
    expect(status.label).toBe('Stopping · R1')
    expect(status.tone).toBe('text-status-warn')
  })

  it('gives the last result, how long ago, and the robot', () => {
    const runs = [
      run({ state: 'done', endedAt: '2026-10-01 11:55:00' }),
      run({
        id: 'later',
        robotId: 'robot-2',
        state: 'failed',
        detail: 'Goal aborted',
        startedAt: '2026-10-01 09:30:00',
        endedAt: '2026-10-01 10:00:00',
      }),
    ]
    expect(missionStatus(mission, null, [runs[0]!], now, robotName)).toMatchObject({
      label: 'Completed · 5m ago · R1',
      tone: 'text-status-ok',
    })
    expect(missionStatus(mission, null, runs, now, robotName)).toEqual({
      tone: 'text-status-fault',
      label: 'Failed · 2h ago · R2',
      detail: 'Goal aborted',
    })
  })

  it('says a mission has never run', () => {
    expect(missionStatus(mission, null, [], now, robotName)).toMatchObject({
      label: 'Never run',
      tone: 'text-muted-soft',
    })
  })

  it('warns about an empty route before anything else it could say', () => {
    const empty = { id: 'mission-1', stepCount: 0 }
    expect(missionStatus(empty, null, [run()], now, robotName)).toMatchObject({
      label: 'No steps yet — add the first stop',
      tone: 'text-status-warn',
    })
    expect(missionStatus(empty, null, [], now, robotName, false).label).toBe('No steps yet')
  })
})
