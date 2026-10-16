import { describe, expect, it } from 'vitest'
import type { LinkState } from '@/domain/ros/link'
import type { MissionRun, RobotConfig } from '@/domain/types'
import type { AttentionItem } from '../attention'
import { fleetLine, fleetRows } from '../fleetRows'

function robot(id: string, name: string, desiredMode: RobotConfig['desiredMode'] = 'nav') {
  return { id, name, accent: 1, desiredMode } as RobotConfig
}

function run(robotId: string, extra: Partial<MissionRun> = {}): MissionRun {
  return {
    id: `run-${robotId}`,
    missionId: 'm',
    missionName: 'Shuttle',
    robotId,
    mode: 'once',
    lapsTarget: null,
    lap: 1,
    stepIndex: 1,
    reachedLap: null,
    reachedIndex: null,
    reachedAt: null,
    state: 'running',
    detail: null,
    startedAt: '',
    endedAt: null,
    ...extra,
  } as MissionRun
}

const ROBOTS = [
  robot('a', 'AMR-01'),
  robot('b', 'AMR-02'),
  robot('c', 'AMR-03', 'idle'),
  robot('d', 'AMR-04'),
  robot('e', 'AMR-10'),
]

const LINKS: Record<string, LinkState> = {
  a: 'online',
  b: 'online',
  c: 'online',
  d: 'offline',
  e: 'online',
}

const ATTENTION: AttentionItem[] = [
  { key: 'b1', robotId: 'b', robotName: 'AMR-02', severity: 'fault', title: 'Shuttle failed' },
  { key: 'd1', robotId: 'd', robotName: 'AMR-04', severity: 'fault', title: 'No link to this robot' },
  { key: 'e1', robotId: 'e', robotName: 'AMR-10', severity: 'info', title: 'Monitoring is muted' },
]

const rows = fleetRows({
  robots: ROBOTS,
  attention: ATTENTION,
  linkFor: (id) => LINKS[id] ?? 'offline',
  runFor: (id) => (id === 'a' ? run('a', { mode: 'laps', lapsTarget: 3, lap: 2 }) : null),
})

describe('fleetRows', () => {
  it('puts what needs a person first, offline last', () => {
    expect(rows.map((row) => row.name)).toEqual(['AMR-02', 'AMR-01', 'AMR-03', 'AMR-10', 'AMR-04'])
  })

  it('says one thing per robot: the problem, the work, or the rest', () => {
    const status = Object.fromEntries(rows.map((row) => [row.name, row.status]))
    expect(status['AMR-02']).toBe('Shuttle failed')
    expect(status['AMR-01']).toBe('Shuttle · step 2 · lap 2/3')
    expect(status['AMR-03']).toBe('Parked')
    expect(status['AMR-10']).toBe('Idle') // an info item is not a problem
    expect(status['AMR-04']).toBe('Offline')
  })

  it('does not report a dropped link as a red problem row', () => {
    expect(rows.find((row) => row.name === 'AMR-04')?.tone).toBe('off')
  })

  it('keeps a robot that loses its link mid-mission near the top', () => {
    const lost = fleetRows({
      robots: [robot('x', 'AMR-01'), robot('y', 'AMR-02')],
      attention: [],
      linkFor: (id) => (id === 'x' ? 'connecting' : 'online'),
      runFor: (id) => (id === 'x' ? run('x') : null),
    })
    expect(lost[0]).toMatchObject({ name: 'AMR-01', tone: 'warning' })
    expect(lost[0]?.status).toBe('Shuttle · step 2 · reconnecting…')
  })

  it('sorts names as a person would: AMR-2 before AMR-10', () => {
    const two = fleetRows({
      robots: [robot('x', 'AMR-10'), robot('y', 'AMR-2')],
      attention: [],
      linkFor: () => 'online',
      runFor: () => null,
    })
    expect(two.map((row) => row.name)).toEqual(['AMR-2', 'AMR-10'])
  })
})

describe('fleetLine', () => {
  it('summarises in one line and leaves out the zeros', () => {
    expect(fleetLine(rows)).toBe('5 robots · 1 needs you · 1 working · 1 not connected')
    expect(fleetLine(rows.filter((row) => row.tone === 'idle'))).toBe('2 robots')
  })
})

describe('fleetRows with a reported robot status', () => {
  // The robot's own word from the registry (amr_agent/robot_status.py), fresh
  // as of `now`. Without a fresh report the legacy desired-mode lines stand.
  const now = Date.parse('2026-10-16T08:00:00Z') + 1_000

  function reportedRobot(status: RobotConfig['status'], detail = ''): RobotConfig {
    return {
      ...robot('s', 'AMR-09'),
      status,
      statusDetail: detail,
      statusReportedAt: '2026-10-16T08:00:00Z',
    }
  }

  function rowsFor(status: RobotConfig['status'], detail = '') {
    return fleetRows({
      robots: [reportedRobot(status, detail)],
      attention: [],
      linkFor: () => 'online',
      runFor: () => null,
      now,
    })
  }

  it("speaks the robot's word instead of the desired-mode guess", () => {
    expect(rowsFor('charging', 'battery 44%')[0]).toMatchObject({
      tone: 'idle',
      status: 'battery 44%',
    })
    expect(rowsFor('mapping')[0]).toMatchObject({ tone: 'active', status: 'Surveying' })
  })

  it('a robot saying error is not Idle, whatever the registry intended', () => {
    expect(rowsFor('error', 'lap 1, step 2: no valid path found')[0]).toMatchObject({
      tone: 'fault',
      status: 'lap 1, step 2: no valid path found',
    })
  })

  it('a robot waiting for the operator ranks as a warning', () => {
    expect(rowsFor('waiting_confirm', 'waiting for the operator at Table 3')[0]).toMatchObject({
      tone: 'warning',
      status: 'waiting for the operator at Table 3',
    })
  })

  it('a stale report does not speak at all', () => {
    const stale = fleetRows({
      robots: [
        {
          ...reportedRobot('error', 'the last mission failed'),
          statusReportedAt: '2026-10-16T07:00:00Z',
        },
      ],
      attention: [],
      linkFor: () => 'online',
      runFor: () => null,
      now,
    })
    // The link indicator owns silence; the row keeps the desired-mode line
    // rather than quoting an hour-old word as if it were current.
    expect(stale[0]).toMatchObject({ tone: 'idle', status: 'Idle' })
  })
})
