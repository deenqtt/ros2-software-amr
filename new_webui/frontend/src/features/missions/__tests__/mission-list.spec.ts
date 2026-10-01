import { describe, expect, it } from 'vitest'
import { lastFinishedRun, routePreview, serverTime, timeAgo } from '../missionList'
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
