/**
 * What the dashboard decides needs a person.
 *
 * These are the sentences somebody reads at two in the morning, so they are
 * pinned here rather than left to whatever the template happened to render.
 */
import { describe, expect, it } from 'vitest'
import { attentionItems, fleetCounts, type FleetInput } from '../attention'
import type { LinkState } from '@/domain/ros/link'
import type { MissionRun, RobotConfig } from '@/domain/types'

function robot(overrides: Partial<RobotConfig> = {}): RobotConfig {
  return {
    id: 'r1',
    name: 'AMR-01',
    bridgeUrl: 'ws://10.0.0.1:8765',
    rosDomainId: null,
    cameraUrl: null,
    namespace: '',
    serial: null,
    accent: 1,
    activeMapId: 'map1',
    desiredMode: 'nav',
    ...overrides,
  }
}

function run(overrides: Partial<MissionRun> = {}): MissionRun {
  return {
    id: 'run1',
    missionId: 'm1',
    missionName: 'Shuttle',
    robotId: 'r1',
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

function input(overrides: Partial<FleetInput> = {}): FleetInput {
  return {
    robots: [robot()],
    linkFor: () => 'online' as LinkState,
    agentFor: () => ({ mode: 'nav', state: 'running', detail: '', backend: 'ok' }),
    runFor: () => null,
    ...overrides,
  }
}

describe('a healthy fleet', () => {
  it('reports nothing, and that emptiness is the message', () => {
    expect(attentionItems(input())).toEqual([])
  })
})

describe('link problems', () => {
  it('reports an offline robot as a fault', () => {
    const items = attentionItems(input({ linkFor: () => 'offline' }))
    expect(items).toHaveLength(1)
    expect(items[0]!.severity).toBe('fault')
    expect(items[0]!.title).toContain('No link')
  })

  it('says nothing else about an offline robot', () => {
    // Its mode and map are unknowable from here. Listing them would be
    // reporting one fact several times.
    const items = attentionItems(
      input({
        robots: [robot({ activeMapId: null })],
        linkFor: () => 'offline',
        agentFor: () => null,
      }),
    )
    expect(items).toHaveLength(1)
  })

  it('treats stale as a warning, not a fault', () => {
    // The link is up. Something is wrong, but the robot may still be working.
    const items = attentionItems(input({ linkFor: () => 'stale' }))
    expect(items[0]!.severity).toBe('warn')
  })

  it('treats muted as information, not a problem', () => {
    // Somebody chose this. It is not a fault to be fixed.
    const items = attentionItems(input({ linkFor: () => 'muted' }))
    expect(items[0]!.severity).toBe('info')
  })
})

describe('intent drifting from reality', () => {
  it('reports a robot that should be navigating and is not', () => {
    // The reason desired_mode exists. Before it, nothing noticed.
    const items = attentionItems(
      input({ agentFor: () => ({ mode: 'unknown', state: 'idle', detail: '', backend: 'ok' }) }),
    )
    expect(items.map((item) => item.title)).toContain('Should be navigating, but is not')
  })

  it('stays quiet while navigation is still coming up', () => {
    const items = attentionItems(
      input({
        agentFor: () => ({ mode: 'unknown', state: 'starting', detail: '', backend: 'ok' }),
      }),
    )
    expect(items).toEqual([])
  })

  it('reports a failed start as a fault, and carries the reason', () => {
    const items = attentionItems(
      input({
        agentFor: () => ({
          mode: 'nav',
          state: 'failed',
          detail: 'launch exited early with code 1',
          backend: 'ok',
        }),
      }),
    )
    expect(items[0]!.severity).toBe('fault')
    expect(items[0]!.action).toContain('launch exited early')
  })

  it('does not ask a parked robot why it is not navigating', () => {
    // Parked is a choice, not a failure.
    const items = attentionItems(
      input({
        robots: [robot({ desiredMode: 'idle' })],
        agentFor: () => ({ mode: 'unknown', state: 'idle', detail: '', backend: 'ok' }),
      }),
    )
    expect(items).toEqual([])
  })

  it('does not blame the mode when the real problem is the missing map', () => {
    const items = attentionItems(
      input({
        robots: [robot({ activeMapId: null })],
        agentFor: () => ({ mode: 'unknown', state: 'idle', detail: '', backend: 'ok' }),
      }),
    )
    expect(items.map((item) => item.title)).toEqual(['No map assigned'])
  })
})

describe('other conditions', () => {
  it('reports a robot that cannot reach the registry', () => {
    const items = attentionItems(
      input({
        agentFor: () => ({ mode: 'nav', state: 'running', detail: '', backend: 'unreachable' }),
      }),
    )
    expect(items[0]!.title).toContain('cannot reach the registry')
  })

  it('stays quiet while the registry state is still unknown', () => {
    const items = attentionItems(
      input({
        agentFor: () => ({ mode: 'nav', state: 'running', detail: '', backend: 'unknown' }),
      }),
    )
    expect(items).toEqual([])
  })

  it('reports a failed run with the step it failed on', () => {
    const items = attentionItems(
      input({ runFor: () => run({ state: 'failed', detail: 'lap 3, step 2: nav status 6' }) }),
    )
    expect(items[0]!.severity).toBe('fault')
    expect(items[0]!.action).toContain('lap 3, step 2')
  })
})

describe('ordering', () => {
  it('puts faults first, then warnings, then information', () => {
    const items = attentionItems(
      input({
        robots: [
          robot({ id: 'a', name: 'AMR-01' }),
          robot({ id: 'b', name: 'AMR-02' }),
          robot({ id: 'c', name: 'AMR-03', activeMapId: null }),
        ],
        linkFor: (id) => (id === 'a' ? 'muted' : id === 'b' ? 'offline' : 'online'),
      }),
    )
    expect(items.map((item) => item.severity)).toEqual(['fault', 'warn', 'info'])
  })

  it('keeps a stable order across polls', () => {
    // The list is polled while being read; reshuffling it moves what somebody
    // is about to click.
    const base = input({
      robots: [robot({ id: 'b', name: 'AMR-02' }), robot({ id: 'a', name: 'AMR-01' })],
      linkFor: () => 'offline',
    })
    expect(attentionItems(base).map((item) => item.robotName)).toEqual(['AMR-01', 'AMR-02'])
  })
})

describe('fleetCounts', () => {
  it('counts working by what is actually running, not what could', () => {
    const counts = fleetCounts(
      input({
        robots: [robot({ id: 'a' }), robot({ id: 'b' })],
        runFor: (id) => (id === 'a' ? run() : null),
      }),
      [],
    )
    expect(counts).toMatchObject({ total: 2, online: 2, working: 1, parked: 0 })
  })

  it('counts a robot with several problems once', () => {
    const state = input({
      robots: [robot({ activeMapId: null })],
      linkFor: () => 'stale',
      agentFor: () => ({ mode: 'unknown', state: 'idle', detail: '', backend: 'error' }),
    })
    const items = attentionItems(state)
    expect(items.length).toBeGreaterThan(1)
    expect(fleetCounts(state, items).needsAttention).toBe(1)
  })

  it('does not count a muted robot as needing attention', () => {
    const state = input({ linkFor: () => 'muted' })
    expect(fleetCounts(state, attentionItems(state)).needsAttention).toBe(0)
  })
})
