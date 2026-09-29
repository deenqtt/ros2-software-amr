/**
 * Mission registry store.
 *
 * The distinctions that matter: a route is not a run, `stopping` is still live,
 * and a robot already working cannot be given another route. Each of those was
 * wrong in the previous design in a way that only showed up on the floor.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { MissionRun, MissionSummary } from '@/domain/types'

const missionsMock = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
}))

const runsMock = vi.hoisted(() => ({
  list: vi.fn(),
  start: vi.fn(),
  stopAfterLap: vi.fn(),
  cancel: vi.fn(),
}))

vi.mock('@/shared/api/missions', async (importOriginal) => {
  // Only the transport is stubbed: RobotBusyError and friends have to stay the
  // real classes or `instanceof` in the store silently stops matching.
  const actual = await importOriginal<typeof import('@/shared/api/missions')>()
  return { ...actual, missionsApi: missionsMock, runsApi: runsMock }
})

const { useMissionStore } = await import('@/stores/missions')

function summary(overrides: Partial<MissionSummary> = {}): MissionSummary {
  return {
    id: 'm1',
    mapId: 'map1',
    name: 'Shuttle',
    note: null,
    stepCount: 2,
    createdAt: '2026-09-28 10:00:00',
    updatedAt: '2026-09-28 10:00:00',
    ...overrides,
  }
}

function run(overrides: Partial<MissionRun> = {}): MissionRun {
  return {
    id: 'r1',
    missionId: 'm1',
    missionName: 'Shuttle',
    robotId: 'bot1',
    mode: 'once',
    lapsTarget: null,
    lap: 1,
    stepIndex: 0,
    state: 'running',
    detail: null,
    startedAt: '2026-09-28 10:00:00',
    endedAt: null,
    ...overrides,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  missionsMock.list.mockReset().mockResolvedValue([])
  missionsMock.create.mockReset()
  missionsMock.update.mockReset()
  missionsMock.remove.mockReset().mockResolvedValue(undefined)
  runsMock.list.mockReset().mockResolvedValue([])
  runsMock.start.mockReset()
  runsMock.stopAfterLap.mockReset().mockResolvedValue(run({ state: 'stopping' }))
  runsMock.cancel.mockReset().mockResolvedValue(run({ state: 'canceled' }))
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('loading', () => {
  it('scopes missions to a map but not runs', async () => {
    // A route belongs to one map; an operator watching the floor wants every
    // robot at once, and a run carries its own.
    missionsMock.list.mockResolvedValue([summary()])
    runsMock.list.mockResolvedValue([run({ missionId: 'other' })])
    const store = useMissionStore()

    await store.load('map1')

    expect(missionsMock.list).toHaveBeenCalledWith('map1')
    expect(runsMock.list).toHaveBeenCalledWith()
    expect(store.count).toBe(1)
    expect(store.runs).toHaveLength(1)
  })

  it('clears the list when a load fails rather than showing another map', async () => {
    missionsMock.list.mockResolvedValue([summary()])
    const store = useMissionStore()
    await store.load('map1')

    const { ApiError } = await import('@/shared/api/client')
    missionsMock.list.mockRejectedValue(new ApiError('boom', 500, '/missions'))
    await store.load('map2')

    expect(store.missions).toEqual([])
    expect(store.error).toBeTruthy()
  })
})

describe('what counts as live', () => {
  it('treats stopping as still running', async () => {
    // "Finish this lap, then stop" is a lap in progress. Treating it as done
    // would let a second route be dispatched to a robot still driving.
    runsMock.list.mockResolvedValue([run({ state: 'stopping' })])
    const store = useMissionStore()
    await store.load('map1')

    expect(store.liveRuns).toHaveLength(1)
    expect(store.runForRobot('bot1')?.state).toBe('stopping')
  })

  it.each(['done', 'failed', 'canceled'] as const)('treats %s as finished', async (state) => {
    runsMock.list.mockResolvedValue([run({ state })])
    const store = useMissionStore()
    await store.load('map1')

    expect(store.liveRuns).toHaveLength(0)
    expect(store.runForRobot('bot1')).toBeNull()
  })

  it('finds the run belonging to one robot', async () => {
    runsMock.list.mockResolvedValue([
      run({ id: 'r1', robotId: 'bot1' }),
      run({ id: 'r2', robotId: 'bot2', missionName: 'Night run' }),
    ])
    const store = useMissionStore()
    await store.load('map1')

    expect(store.runForRobot('bot2')?.missionName).toBe('Night run')
  })
})

describe('name collisions', () => {
  it('spots a taken name before the server does', async () => {
    missionsMock.list.mockResolvedValue([summary({ id: 'a', name: 'Shuttle' })])
    const store = useMissionStore()
    await store.load('map1')

    expect(store.nameTaken('Shuttle')).toBe(true)
    expect(store.nameTaken('shuttle')).toBe(true)
    expect(store.nameTaken('Night run')).toBe(false)
  })

  it('does not report a mission as colliding with itself', async () => {
    missionsMock.list.mockResolvedValue([summary({ id: 'a', name: 'Shuttle' })])
    const store = useMissionStore()
    await store.load('map1')

    // Otherwise editing a route without renaming it is refused.
    expect(store.nameTaken('Shuttle', 'a')).toBe(false)
  })
})

describe('dispatch and stop', () => {
  it('refreshes the runs after dispatching', async () => {
    missionsMock.list.mockResolvedValue([summary()])
    runsMock.start.mockResolvedValue(run())
    const store = useMissionStore()
    await store.load('map1')
    runsMock.list.mockClear().mockResolvedValue([run()])

    await store.dispatch({ missionId: 'm1', robotId: 'bot1', mode: 'once' })

    expect(runsMock.list).toHaveBeenCalled()
    expect(store.liveRuns).toHaveLength(1)
  })

  it('surfaces a busy robot as its own kind of failure', async () => {
    const { RobotBusyError } = await import('@/shared/api/missions')
    runsMock.start.mockRejectedValue(new RobotBusyError('Night run'))
    const store = useMissionStore()

    await expect(
      store.dispatch({ missionId: 'm1', robotId: 'bot1', mode: 'once' }),
    ).rejects.toThrow(/Night run/)
  })

  it('describes a wrong-map refusal in the server words', async () => {
    const { WrongMapError } = await import('@/shared/api/missions')
    const store = useMissionStore()

    expect(store.describeError(new WrongMapError('AMR-01 is not on the map'))).toContain(
      'not on the map',
    )
  })

  it('a failed run poll does not become a visible error', async () => {
    // A missed poll is a stale number for two seconds; the next one fixes it.
    missionsMock.list.mockResolvedValue([summary()])
    const store = useMissionStore()
    await store.load('map1')
    runsMock.list.mockRejectedValue(new Error('network blip'))

    await store.refreshRuns()

    expect(store.error).toBeNull()
  })
})

describe('removal', () => {
  it('treats an already-deleted mission as deleted', async () => {
    const { ApiError } = await import('@/shared/api/client')
    missionsMock.list.mockResolvedValue([summary({ id: 'a' })])
    missionsMock.remove.mockRejectedValue(new ApiError('gone', 404, '/missions/a'))
    const store = useMissionStore()
    await store.load('map1')

    await store.remove('a')

    expect(store.count).toBe(0)
  })

  it('keeps the row when the server fails for a real reason', async () => {
    const { ApiError } = await import('@/shared/api/client')
    missionsMock.list.mockResolvedValue([summary({ id: 'a' })])
    missionsMock.remove.mockRejectedValue(new ApiError('boom', 500, '/missions/a'))
    const store = useMissionStore()
    await store.load('map1')

    await expect(store.remove('a')).rejects.toThrow()
    expect(store.count).toBe(1)
  })
})
