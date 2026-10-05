import { describe, expect, it } from 'vitest'
import type { TopicHealth } from '@/domain/ros/health'
import { problemTopics, robotHealth } from '../robotHealth'

function topic(label: string, state: TopicHealth['state']): TopicHealth {
  return {
    key: label,
    label,
    cadence: 'periodic',
    tier: 'vitals',
    subscribed: state !== 'idle',
    messages: 1,
    lastMessageAt: 0,
    state,
    rateHz: 1,
    needsStack: false,
  }
}

const HEALTHY_TOPICS = [topic('/odom', 'ok'), topic('/scan', 'ok'), topic('/map', 'idle')]
const NAV = { mode: 'nav', state: 'running', backend: 'ok' }

describe('robotHealth', () => {
  it('says healthy, with what runs and how much data flows', () => {
    expect(robotHealth({ link: 'online', host: 'h', agent: NAV, topics: HEALTHY_TOPICS })).toEqual({
      tone: 'ok',
      title: 'Healthy',
      line: 'Nav2 running · 2 of 2 topics OK',
    })
  })

  it('stops at the first problem: reaching the robot comes before anything else', () => {
    const verdict = robotHealth({ link: 'offline', host: '10.0.0.5', agent: NAV, topics: [] })
    expect(verdict).toMatchObject({ tone: 'fault', title: "Can't reach the robot" })
    expect(verdict.line).toContain('10.0.0.5')
  })

  it('names a single silent topic, counts several', () => {
    const one = robotHealth({
      link: 'stale',
      host: 'h',
      agent: NAV,
      topics: [topic('/odom', 'ok'), topic('/scan', 'stale')],
    })
    expect(one).toMatchObject({ tone: 'warn', title: '/scan has gone quiet' })
    const two = robotHealth({
      link: 'stale',
      host: 'h',
      agent: NAV,
      topics: [topic('/odom', 'stale'), topic('/scan', 'stale')],
    })
    expect(two.title).toBe('2 topics have gone quiet')
  })

  it('reports a failed stack before silent topics', () => {
    const verdict = robotHealth({
      link: 'online',
      host: 'h',
      agent: { mode: 'nav', state: 'failed', backend: 'ok' },
      topics: [topic('/scan', 'stale')],
    })
    expect(verdict).toMatchObject({ tone: 'fault', title: 'Nav2 failed to start' })
  })

  it('does not call a muted robot broken', () => {
    expect(robotHealth({ link: 'muted', host: 'h', agent: null, topics: [] }).tone).toBe('muted')
  })

  it('warns while connected but nothing has arrived yet', () => {
    expect(
      robotHealth({ link: 'online', host: 'h', agent: null, topics: [topic('/odom', 'waiting')] })
        .title,
    ).toBe('Connected, waiting for data')
  })
})

describe('problemTopics', () => {
  it('keeps only what is not plainly fine', () => {
    const topics = [topic('/a', 'ok'), topic('/b', 'stale'), topic('/c', 'waiting'), topic('/d', 'idle')]
    expect(problemTopics(topics).map((t) => t.label)).toEqual(['/b', '/c'])
  })
})
