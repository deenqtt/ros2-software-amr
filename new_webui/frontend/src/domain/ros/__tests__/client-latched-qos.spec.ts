/**
 * A latched topic has one chance to be asked for correctly.
 *
 * rosbridge shares one subscription per topic between all clients, and its own
 * source states the QoS "is determined at the first registration of a
 * subscriber". roslibjs's subscribe carries no QoS, so if it goes out first the
 * subscription is created volatile — and a volatile subscription never receives
 * a latched replay. /tf_static and /robot_description publish exactly once, so
 * they then never arrive at all, and the browser never learns where the laser
 * is mounted.
 *
 * The order below is therefore the fix, and this locks it.
 */
import { describe, expect, it, vi } from 'vitest'

const log = vi.hoisted(() => [] as Array<{ kind: 'qos' | 'plain'; topic: string }>)

vi.mock('roslib', () => {
  class Ros {
    private handlers: Record<string, () => void> = {}
    on(event: string, cb: (message?: unknown) => void) {
      this.handlers[event] = cb
      if (event === 'connection') queueMicrotask(cb)
      // The backend relay's "robot answered" frame (see RELAY_READY).
      if (event === 'status') queueMicrotask(() => cb({ op: 'status', msg: 'amr-relay: ready' }))
    }
    close() {}
    callOnConnection(msg: { op?: string; topic?: string; qos?: unknown }) {
      if (msg.op === 'subscribe' && msg.qos) log.push({ kind: 'qos', topic: msg.topic ?? '' })
    }
  }
  class Topic {
    constructor(private options: { name: string }) {}
    subscribe() {
      log.push({ kind: 'plain', topic: this.options.name })
    }
    unsubscribe() {}
    publish() {}
  }
  class Message {
    constructor(public values: unknown) {}
  }
  class ServiceRequest {
    constructor(public values: unknown) {}
  }
  class Service {
    callService() {}
  }
  return {
    default: { Ros, Topic, Message, Service, ServiceRequest },
    Ros,
    Topic,
    Message,
    Service,
    ServiceRequest,
  }
})

import { RosClient } from '../client'
import { TOPIC_SPECS } from '../health'

async function connected() {
  log.length = 0
  const client = new RosClient({ url: 'ws://test:8765' })
  client.connect('full')
  await new Promise((resolve) => queueMicrotask(() => resolve(null)))
  return client
}

const LATCHED = TOPIC_SPECS.filter((spec) => spec.cadence === 'latched').map((s) => s.key)

describe('latched topics are subscribed with QoS first', () => {
  it('has latched topics to protect', () => {
    expect(LATCHED).toContain('tfStatic')
    expect(LATCHED).toContain('robotDescription')
  })

  it('sends the QoS-bearing subscribe before the plain one, for every latched topic', async () => {
    await connected()

    for (const name of ['/tf_static', '/robot_description', '/map']) {
      const first = log.findIndex((e) => e.topic === name)
      expect(first, `${name} was never subscribed`).toBeGreaterThanOrEqual(0)
      expect(log[first]!.kind, `${name} was asked for without QoS first`).toBe('qos')
    }
  })

  it('does not ask for QoS on topics that are not latched', async () => {
    await connected()

    for (const name of ['/scan', '/odom']) {
      const entries = log.filter((e) => e.topic === name)
      expect(entries.length).toBeGreaterThan(0)
      expect(entries.every((e) => e.kind === 'plain')).toBe(true)
    }
  })
})
