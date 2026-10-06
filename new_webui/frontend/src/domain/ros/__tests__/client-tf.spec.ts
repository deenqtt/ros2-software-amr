/**
 * The transform buffer has to actually be fed.
 *
 * It was not. The buffer existed, was cleared on disconnect, and was read by
 * every consumer of the robot's pose — but no code ever put a transform into
 * it. The failure was silent in the worst way: the map rendered perfectly
 * while the robot and its laser were simply absent, and nothing anywhere
 * reported an error.
 */
import { describe, expect, it, vi } from 'vitest'

const topics = vi.hoisted(() => [] as Array<{ name: string; handler: (m: unknown) => void }>)

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
    callOnConnection() {}
  }
  class Topic {
    constructor(private options: { name: string }) {}
    subscribe(handler: (m: unknown) => void) {
      topics.push({ name: this.options.name, handler })
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
import { yawToQuaternion } from '../quaternion'

function transform(parent: string, child: string, tx: number, ty: number, yaw = 0) {
  return {
    header: { frame_id: parent },
    child_frame_id: child,
    transform: { translation: { x: tx, y: ty }, rotation: yawToQuaternion(yaw) },
  }
}

async function connected() {
  topics.length = 0
  const client = new RosClient({ url: 'ws://test:8765' })
  client.connect('full')
  await new Promise((resolve) => queueMicrotask(() => resolve(null)))
  return client
}

function deliver(name: string, message: unknown) {
  for (const topic of topics) {
    if (topic.name === name) topic.handler(message)
  }
}

describe('RosClient transform handling', () => {
  it('subscribes to /tf on the full tier', async () => {
    await connected()
    expect(topics.map((t) => t.name)).toContain('/tf')
  })

  it('feeds incoming transforms into the buffer', async () => {
    const client = await connected()
    expect(client.tf.size).toBe(0)

    deliver('/tf', {
      transforms: [transform('map', 'odom', 1, 0), transform('odom', 'base_footprint', 2, 0)],
    })

    expect(client.tf.size).toBe(2)
    expect(client.tf.resolveMapToBase()).toEqual({ x: 3, y: 0, theta: 0 })
  })

  it('resolves a pose only once the whole chain has arrived', async () => {
    const client = await connected()
    deliver('/tf', { transforms: [transform('map', 'odom', 1, 0)] })
    expect(client.tf.resolveMapToBase()).toBeUndefined()

    deliver('/tf', { transforms: [transform('odom', 'base_footprint', 0, 4)] })
    expect(client.tf.resolveMapToBase()).toEqual({ x: 1, y: 4, theta: 0 })
  })

  it('keeps static transforms, so a sensor mount survives', async () => {
    const client = await connected()
    deliver('/tf_static', { transforms: [transform('base_footprint', 'base_scan', 0.2, 0)] })
    expect(client.tf.get('base_footprint', 'base_scan')).toEqual({ tx: 0.2, ty: 0, yaw: 0 })
  })

  it('survives a malformed transform message without throwing', async () => {
    const client = await connected()
    expect(() => deliver('/tf', {})).not.toThrow()
    expect(client.tf.size).toBe(0)
  })

  it('drops the buffer when the socket closes', async () => {
    const client = await connected()
    deliver('/tf', {
      transforms: [transform('map', 'odom', 1, 0), transform('odom', 'base_footprint', 1, 0)],
    })
    expect(client.tf.size).toBe(2)

    // Stale transforms from a dead session would put the robot somewhere it
    // is not, which is worse than showing nothing.
    client.disconnect()
    expect(client.tf.size).toBe(0)
  })
})
