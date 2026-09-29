/**
 * Station registry store.
 *
 * The invariant that matters most: the loaded stations and the map they belong
 * to move together. A list from one map paired with another map's id renders
 * poses over the wrong image, and the result looks entirely plausible — which
 * is the worst kind of wrong for a place a robot drives to.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { Station } from '@/domain/types'

const apiMock = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  countForMap: vi.fn(),
}))

vi.mock('@/shared/api/stations', async (importOriginal) => {
  // Only the transport is stubbed: StationNameTakenError has to stay the real
  // class or `instanceof` in the store silently stops matching.
  const actual = await importOriginal<typeof import('@/shared/api/stations')>()
  return { ...actual, stationsApi: apiMock }
})

const { useStationStore } = await import('@/stores/stations')

function station(overrides: Partial<Station> = {}): Station {
  return {
    id: 's1',
    mapId: 'm1',
    name: 'Dock 1',
    type: 'charging',
    x: 1,
    y: 2,
    yaw: 0,
    note: null,
    taughtByRobotId: null,
    createdAt: '2026-09-28 10:00:00',
    updatedAt: '2026-09-28 10:00:00',
    ...overrides,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  apiMock.list.mockReset().mockResolvedValue([])
  apiMock.create.mockReset()
  apiMock.update.mockReset()
  apiMock.remove.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('loading', () => {
  it('records which map the stations belong to', async () => {
    apiMock.list.mockResolvedValue([station()])
    const store = useStationStore()

    await store.load('m1')

    expect(apiMock.list).toHaveBeenCalledWith('m1')
    expect(store.mapId).toBe('m1')
    expect(store.count).toBe(1)
  })

  it('does not leave another map stations on a failed load', async () => {
    apiMock.list.mockResolvedValue([station()])
    const store = useStationStore()
    await store.load('m1')

    const { ApiError } = await import('@/shared/api/client')
    apiMock.list.mockRejectedValue(new ApiError('boom', 500, '/stations'))
    await store.load('m2')

    // Keeping m1 poses while the view thinks it is showing m2 would render them
    // over the wrong image.
    expect(store.stations).toEqual([])
    expect(store.error).toBeTruthy()
  })
})

describe('name collisions', () => {
  it('spots a taken name before the server does', async () => {
    apiMock.list.mockResolvedValue([station({ id: 'a', name: 'Dock 1' })])
    const store = useStationStore()
    await store.load('m1')

    expect(store.nameTaken('Dock 1')).toBe(true)
    // Case is not what distinguishes two stations.
    expect(store.nameTaken('dock 1')).toBe(true)
    expect(store.nameTaken('  Dock 1  ')).toBe(true)
    expect(store.nameTaken('Dock 2')).toBe(false)
  })

  it('does not report a station as colliding with itself', async () => {
    apiMock.list.mockResolvedValue([station({ id: 'a', name: 'Dock 1' })])
    const store = useStationStore()
    await store.load('m1')

    // Otherwise editing a station without renaming it is refused.
    expect(store.nameTaken('Dock 1', 'a')).toBe(false)
  })
})

describe('writing', () => {
  it('keeps the list sorted by name after a create', async () => {
    apiMock.list.mockResolvedValue([station({ id: 'a', name: 'Bravo' })])
    apiMock.create.mockResolvedValue(station({ id: 'b', name: 'Alpha' }))
    const store = useStationStore()
    await store.load('m1')

    await store.create({ mapId: 'm1', name: 'Alpha', type: 'pick', x: 0, y: 0, yaw: 0 })

    expect(store.stations.map((s) => s.name)).toEqual(['Alpha', 'Bravo'])
  })

  it('replaces only the station that changed', async () => {
    apiMock.list.mockResolvedValue([station({ id: 'a' }), station({ id: 'b', name: 'Dock 2' })])
    apiMock.update.mockResolvedValue(station({ id: 'b', name: 'Dock 2', x: 9 }))
    const store = useStationStore()
    await store.load('m1')

    await store.update('b', { x: 9 })

    expect(store.byId('a')?.x).toBe(1)
    expect(store.byId('b')?.x).toBe(9)
  })

  it('treats an already-deleted station as deleted', async () => {
    // Otherwise the row is unremovable: every retry 404s against the same
    // missing station.
    const { ApiError } = await import('@/shared/api/client')
    apiMock.list.mockResolvedValue([station({ id: 'a' })])
    apiMock.remove.mockRejectedValue(new ApiError('gone', 404, '/stations/a'))
    const store = useStationStore()
    await store.load('m1')

    await store.remove('a')

    expect(store.count).toBe(0)
  })

  it('reports a real delete failure rather than dropping the row', async () => {
    const { ApiError } = await import('@/shared/api/client')
    apiMock.list.mockResolvedValue([station({ id: 'a' })])
    apiMock.remove.mockRejectedValue(new ApiError('boom', 500, '/stations/a'))
    const store = useStationStore()
    await store.load('m1')

    await expect(store.remove('a')).rejects.toThrow()
    expect(store.count).toBe(1)
  })
})
