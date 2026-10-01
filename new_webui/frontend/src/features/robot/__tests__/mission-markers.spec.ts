import { describe, expect, it } from 'vitest'
import { missionOverlay, stepStatus } from '../missionMarkers'
import type { MissionRun, MissionStep, Station } from '@/domain/types'

function run(overrides: Partial<MissionRun> = {}): MissionRun {
  return {
    id: 'run-1',
    missionId: 'mission-1',
    missionName: 'Shuttle',
    robotId: 'robot-1',
    mode: 'laps',
    lapsTarget: 3,
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

function station(id: string, x: number): Station {
  return {
    id,
    mapId: 'map-1',
    name: id.toUpperCase(),
    type: 'pick',
    x,
    y: 0,
    yaw: 0,
    note: null,
    taughtByRobotId: null,
    createdAt: '',
    updatedAt: '',
  }
}

function step(stationId: string, ordinal: number): MissionStep {
  return { id: `s${ordinal}`, ordinal, stationId, task: 'none', confirm: 'auto', note: null }
}

const stations = new Map([
  ['a', station('a', 1)],
  ['b', station('b', 2)],
  ['c', station('c', 3)],
])
const lookup = (id: string) => stations.get(id) ?? null

describe('stepStatus', () => {
  it('marks steps behind the robot done, its target current, the rest pending', () => {
    const at = run({ stepIndex: 1 })
    expect([0, 1, 2].map((index) => stepStatus(index, at))).toEqual(['done', 'current', 'pending'])
  })

  it('marks the target done as soon as the robot arrives, before the next step starts', () => {
    const arrived = run({ stepIndex: 1, reachedLap: 1, reachedIndex: 1, reachedAt: 't' })
    expect(stepStatus(1, arrived)).toBe('done')
  })

  it('ignores an arrival from the previous lap', () => {
    // Lap 2 has just begun: last lap's final arrival must not mark this lap done.
    const nextLap = run({ lap: 2, stepIndex: 0, reachedLap: 1, reachedIndex: 2, reachedAt: 't' })
    expect([0, 1, 2].map((index) => stepStatus(index, nextLap))).toEqual([
      'current',
      'pending',
      'pending',
    ])
  })

  it('marks every step done once the run is', () => {
    expect(stepStatus(2, run({ state: 'done', stepIndex: 0 }))).toBe('done')
  })
})

describe('missionOverlay', () => {
  it('gives one marker per station, numbered with every step that uses it', () => {
    const steps = [step('a', 1), step('b', 2), step('a', 3)]
    const { markers, route } = missionOverlay(steps, lookup, run({ stepIndex: 1 }))

    expect(markers.map((marker) => [marker.stationId, marker.ordinals])).toEqual([
      ['a', [1, 3]],
      ['b', [2]],
    ])
    expect(route).toHaveLength(3)
  })

  it('keeps a revisited station pending while a visit is still ahead', () => {
    const steps = [step('a', 1), step('b', 2), step('a', 3)]
    const { markers } = missionOverlay(steps, lookup, run({ stepIndex: 1 }))
    // Step 1 is done but step 3 is not: the station is not finished with.
    expect(markers.find((marker) => marker.stationId === 'a')?.status).toBe('pending')
    expect(markers.find((marker) => marker.stationId === 'b')?.status).toBe('current')
  })

  it('skips a step whose station is gone without renumbering the rest', () => {
    const steps = [step('a', 1), step('gone', 2), step('c', 3)]
    const { markers } = missionOverlay(steps, lookup, run())
    expect(markers.map((marker) => marker.ordinals)).toEqual([[1], [3]])
  })
})
