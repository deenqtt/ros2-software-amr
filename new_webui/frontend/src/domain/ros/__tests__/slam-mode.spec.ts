import { describe, expect, it } from 'vitest'
import { anyStale, topicState, TOPIC_SPECS, type TopicHealth } from '@/domain/ros/health'

describe('SLAM mode reality check', () => {
  it('does not report stale for a costmap that never existed', () => {
    // Observed on the live sim: in SLAM mode there is no Nav2, so
    // /global_costmap/costmap, /plan and /particle_cloud never publish at all.
    // If "never spoke" were treated as "went quiet", every SLAM session would
    // show a false Stale — and a false alarm is worse than no alarm.
    const costmap = TOPIC_SPECS.find((s) => s.key === 'costmap')!
    const state = topicState(costmap, { subscribed: true, messages: 0, lastMessageAt: null })
    expect(state).toBe('waiting')

    const health: TopicHealth = {
      key: costmap.key, label: costmap.label, cadence: costmap.cadence, tier: costmap.tier,
      subscribed: true, messages: 0, lastMessageAt: null, state, rateHz: null,
      needsStack: costmap.needsStack ?? false,
    }
    expect(anyStale([health])).toBe(false)
  })

  it('does report stale once a periodic topic has spoken and then stopped', () => {
    const now = 100_000
    const costmap = TOPIC_SPECS.find((s) => s.key === 'costmap')!
    expect(
      topicState(costmap, { subscribed: true, messages: 40, lastMessageAt: now - 30_000 }, now),
    ).toBe('stale')
  })

  it('does not report stale for stack topics once the stack is deliberately stopped', () => {
    // The bug this covers: finishing a survey stops SLAM, /tf correctly falls
    // silent, and two seconds later the robot reads as Stale. The survey dialog
    // blocks stale robots, so a second survey could never be started — the
    // operator had to reload the page to clear it.
    const now = 100_000
    const tf = TOPIC_SPECS.find((s) => s.key === 'tf')!
    expect(tf.needsStack).toBe(true)

    const health: TopicHealth = {
      key: tf.key, label: tf.label, cadence: tf.cadence, tier: tf.tier,
      subscribed: true, messages: 900, lastMessageAt: now - 30_000,
      state: topicState(tf, { subscribed: true, messages: 900, lastMessageAt: now - 30_000 }, now),
      rateHz: null, needsStack: true,
    }
    expect(health.state).toBe('stale')

    expect(anyStale([health], false)).toBe(false)
    // Still a fault while the stack is supposed to be running.
    expect(anyStale([health], true)).toBe(true)
  })

  it('still reports stale for a sensor topic whatever the stack is doing', () => {
    // /scan and /odom come from the simulator or the hardware, not from the
    // stack, so their silence is a real fault even with nothing running.
    const now = 100_000
    const scan = TOPIC_SPECS.find((s) => s.key === 'scan')!
    expect(scan.needsStack).toBeUndefined()

    const health: TopicHealth = {
      key: scan.key, label: scan.label, cadence: scan.cadence, tier: scan.tier,
      subscribed: true, messages: 500, lastMessageAt: now - 30_000,
      state: 'stale', rateHz: null, needsStack: false,
    }
    expect(anyStale([health], false)).toBe(true)
  })
})
