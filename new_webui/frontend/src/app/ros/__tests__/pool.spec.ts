/**
 * Connection pool.
 *
 * These are the guarantees that make a fleet affordable and honest: one cheap
 * connection per robot, one expensive connection at a time, and no sockets
 * left running for robots nobody is watching.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const instances = vi.hoisted(() => [] as Array<{
  url: string
  namespace: string
  connect: ReturnType<typeof vi.fn>
  disconnect: ReturnType<typeof vi.fn>
  dispose: ReturnType<typeof vi.fn>
  poll: ReturnType<typeof vi.fn>
  subscribeToSnapshots: ReturnType<typeof vi.fn>
  onMessage: ReturnType<typeof vi.fn>
  setOptionalTopics: ReturnType<typeof vi.fn>
}>)

vi.mock('@/domain/ros/client', () => ({
  RosClient: vi.fn().mockImplementation((options: { url: string; namespace?: string }) => {
    const instance = {
      url: options.url,
      namespace: options.namespace ?? '',
      connect: vi.fn(),
      disconnect: vi.fn(),
      dispose: vi.fn(),
      poll: vi.fn(),
      subscribeToSnapshots: vi.fn(() => () => {}),
      onMessage: vi.fn(() => () => {}),
      setOptionalTopics: vi.fn(),
    }
    instances.push(instance)
    return instance
  }),
}))

import { RosPool } from '../pool'
import type { RobotConfig } from '@/domain/types'

function robot(id: string, overrides: Partial<RobotConfig> = {}): RobotConfig {
  return {
    id,
    name: id.toUpperCase(),
    bridgeUrl: `ws://10.0.0.${id.replace(/\D/g, '') || 1}:8765`,
    rosDomainId: null,
    cameraUrl: null,
    namespace: '',
    accent: 1,
    serial: null,
    activeMapId: null,
    desiredMode: 'nav',
    ...overrides,
  }
}

function latestTier(index: number): string | undefined {
  const calls = instances[index]?.connect.mock.calls ?? []
  return calls.at(-1)?.[0]
}

let pool: RosPool

beforeEach(() => {
  instances.length = 0
  vi.useFakeTimers()
  pool = new RosPool()
})

describe('sync', () => {
  it('creates one client per robot', () => {
    pool.sync([robot('r1'), robot('r2')])
    expect(instances).toHaveLength(2)
  })

  it('is idempotent — repeated syncs do not pile up clients', () => {
    const fleet = [robot('r1'), robot('r2')]
    pool.sync(fleet)
    pool.sync(fleet)
    pool.sync(fleet)
    expect(instances).toHaveLength(2)
  })

  it('disposes the client of a robot that left the registry', () => {
    pool.sync([robot('r1'), robot('r2')])
    pool.sync([robot('r1')])
    expect(instances[1]?.dispose).toHaveBeenCalled()
  })

  it('rebuilds the client when the bridge address changes', () => {
    // A moved bridge is a different endpoint, not a reconfiguration.
    pool.sync([robot('r1', { bridgeUrl: 'ws://old:8765' })])
    pool.sync([robot('r1', { bridgeUrl: 'ws://new:8765' })])
    expect(instances).toHaveLength(2)
    expect(instances[0]?.dispose).toHaveBeenCalled()
    expect(instances[1]?.url).toBe('ws://new:8765')
  })

  it('rebuilds when only the namespace changes', () => {
    pool.sync([robot('r1', { namespace: '' })])
    pool.sync([robot('r1', { namespace: 'amr_01' })])
    expect(instances).toHaveLength(2)
  })

  it('passes the optional topics a page asked for on to a rebuilt client', () => {
    pool.sync([robot('r1', { bridgeUrl: 'ws://old:8765' })])
    pool.setOptionalTopics('r1', ['costmap'])
    expect(instances[0]?.setOptionalTopics).toHaveBeenLastCalledWith(['costmap'])
    pool.sync([robot('r1', { bridgeUrl: 'ws://new:8765' })])
    expect(instances[1]?.setOptionalTopics).toHaveBeenCalledWith(['costmap'])
  })
})

describe('tiering', () => {
  it('puts every robot on the cheap tier by default', () => {
    pool.sync([robot('r1'), robot('r2'), robot('r3')])
    expect(latestTier(0)).toBe('vitals')
    expect(latestTier(1)).toBe('vitals')
    expect(latestTier(2)).toBe('vitals')
  })

  it('promotes only the focused robot to full telemetry', () => {
    // 20 robots at the full tier would be ~1400 messages/second plus PNG
    // encodes; the whole point of the tier split is that only one is expensive.
    pool.sync([robot('r1'), robot('r2')])
    pool.focus('r1')
    expect(latestTier(0)).toBe('full')
    expect(latestTier(1)).toBe('vitals')
  })

  it('demotes when focus moves to another robot', () => {
    pool.sync([robot('r1'), robot('r2')])
    pool.focus('r1')
    pool.focus('r2')
    expect(latestTier(0)).toBe('vitals')
    expect(latestTier(1)).toBe('full')
  })

  it('demotes everyone when focus is cleared', () => {
    pool.sync([robot('r1')])
    pool.focus('r1')
    pool.focus(null)
    expect(latestTier(0)).toBe('vitals')
  })

  it('keeps the focused robot on the full tier across a registry sync', () => {
    pool.sync([robot('r1')])
    pool.focus('r1')
    pool.sync([robot('r1'), robot('r2')])
    expect(latestTier(0)).toBe('full')
    expect(latestTier(1)).toBe('vitals')
  })
})

describe('muting', () => {
  it('disconnects a muted robot instead of retrying forever', () => {
    // A robot in the workshop would otherwise reconnect endlessly and hold a
    // permanently red row — which teaches operators to ignore red.
    pool.sync([robot('r1'), robot('r2')])
    pool.setMuted('r1', true)
    expect(instances[0]?.disconnect).toHaveBeenCalled()
    expect(latestTier(1)).toBe('vitals')
  })

  it('reconnects when unmuted', () => {
    pool.sync([robot('r1')])
    pool.setMuted('r1', true)
    instances[0]?.connect.mockClear()
    pool.setMuted('r1', false)
    expect(latestTier(0)).toBe('vitals')
  })

  it('does not promote a muted robot even when it is focused', () => {
    pool.sync([robot('r1')])
    pool.setMuted('r1', true)
    instances[0]?.connect.mockClear()
    pool.focus('r1')
    expect(instances[0]?.connect).not.toHaveBeenCalled()
  })

  it('reports its own mute state', () => {
    pool.sync([robot('r1')])
    expect(pool.isMuted('r1')).toBe(false)
    pool.setMuted('r1', true)
    expect(pool.isMuted('r1')).toBe(true)
  })
})

describe('polling', () => {
  it('ticks every client so silence becomes visible without traffic', () => {
    // A topic that has gone quiet emits nothing, so nothing would recompute
    // its state; the tick is what turns silence into a stale badge.
    pool.sync([robot('r1'), robot('r2')])
    vi.advanceTimersByTime(3000)
    expect(instances[0]?.poll.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(instances[1]?.poll.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('stops ticking after dispose', () => {
    pool.sync([robot('r1')])
    pool.dispose()
    const before = instances[0]?.poll.mock.calls.length ?? 0
    vi.advanceTimersByTime(5000)
    expect(instances[0]?.poll.mock.calls.length).toBe(before)
  })
})
