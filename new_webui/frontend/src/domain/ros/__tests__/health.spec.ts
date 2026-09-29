import { describe, expect, it } from 'vitest'
import {
  anyStale,
  specsForTier,
  topicState,
  TOPIC_SPECS,
  type TopicHealth,
  type TopicSpec,
} from '../health'

function spec(overrides: Partial<TopicSpec> = {}): TopicSpec {
  return {
    key: 'k',
    label: 'K',
    messageType: 'std_msgs/msg/String',
    cadence: 'periodic',
    tier: 'vitals',
    budgetMs: 5000,
    ...overrides,
  }
}

describe('topicState', () => {
  it('is idle when nothing is subscribed', () => {
    expect(topicState(spec(), { subscribed: false, messages: 0, lastMessageAt: null })).toBe('idle')
  })

  it('is waiting once subscribed but before the first message', () => {
    expect(topicState(spec(), { subscribed: true, messages: 0, lastMessageAt: null })).toBe(
      'waiting',
    )
  })

  it('goes stale when a periodic topic exceeds its budget', () => {
    const now = 100_000
    expect(
      topicState(spec({ budgetMs: 5000 }), { subscribed: true, messages: 9, lastMessageAt: now - 6000 }, now),
    ).toBe('stale')
    expect(
      topicState(spec({ budgetMs: 5000 }), { subscribed: true, messages: 9, lastMessageAt: now - 1000 }, now),
    ).toBe('ok')
  })

  it('never calls an event topic stale, however long it has been quiet', () => {
    // /robot_status publishes only on a state change: a robot parked since
    // this morning is correctly silent, and flagging it would be a false alarm
    // that teaches operators to ignore the colour.
    const now = 100_000
    expect(
      topicState(
        spec({ cadence: 'event' }),
        { subscribed: true, messages: 1, lastMessageAt: now - 3_600_000 },
        now,
      ),
    ).toBe('ok')
  })

  it('never calls a latched topic stale after its single message', () => {
    const now = 100_000
    expect(
      topicState(
        spec({ cadence: 'latched' }),
        { subscribed: true, messages: 1, lastMessageAt: now - 600_000 },
        now,
      ),
    ).toBe('ok')
  })

  it('still reports a latched topic that never arrived as waiting', () => {
    expect(
      topicState(spec({ cadence: 'latched' }), { subscribed: true, messages: 0, lastMessageAt: null }),
    ).toBe('waiting')
  })
})

describe('tiers', () => {
  it('keeps the vitals tier small enough to run for a whole fleet', () => {
    const vitals = specsForTier('vitals')
    expect(vitals.length).toBeLessThanOrEqual(4)
    expect(vitals.every((s) => s.tier === 'vitals')).toBe(true)
  })

  it('includes every topic in the full tier', () => {
    expect(specsForTier('full')).toHaveLength(TOPIC_SPECS.length)
  })

  it('gives every periodic topic a budget, and no other topic one', () => {
    for (const s of TOPIC_SPECS) {
      if (s.cadence === 'periodic') {
        expect(s.budgetMs, `${s.key} needs a budget`).toBeGreaterThan(0)
      }
    }
  })

  it('puts robot_status on the event cadence, because it has no timer', () => {
    const status = TOPIC_SPECS.find((s) => s.key === 'robotStatus')
    expect(status?.cadence).toBe('event')
  })

  it('uses unique keys', () => {
    const keys = TOPIC_SPECS.map((s) => s.key)
    expect(new Set(keys).size).toBe(keys.length)
  })
})

describe('anyStale', () => {
  const health = (state: TopicHealth['state']): TopicHealth => ({
    key: 'k',
    label: 'K',
    cadence: 'periodic',
    tier: 'vitals',
    subscribed: true,
    messages: 1,
    lastMessageAt: 1,
    state,
    rateHz: null,
    needsStack: false,
  })

  it('is false when nothing has gone quiet', () => {
    expect(anyStale([health('ok'), health('waiting'), health('idle')])).toBe(false)
  })

  it('is true as soon as one periodic topic is stale', () => {
    expect(anyStale([health('ok'), health('stale')])).toBe(true)
  })
})
