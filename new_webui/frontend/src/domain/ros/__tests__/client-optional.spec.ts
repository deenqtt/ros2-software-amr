/**
 * Heavy layers are subscribed only while a page shows them.
 *
 * The costmap and the particle cloud were 78% of a navigation page's traffic
 * with both layers switched off. This locks that they stay closed until asked
 * for, open when asked, and close again — without touching anything else.
 */
import { describe, expect, it, vi } from 'vitest'

const live = vi.hoisted(() => new Set<string>())

vi.mock('roslib', () => {
  class Ros {
    on(event: string, cb: () => void) {
      if (event === 'connection') queueMicrotask(cb)
    }
    close() {}
    callOnConnection() {}
  }
  class Topic {
    constructor(private options: { name: string }) {}
    subscribe() {
      live.add(this.options.name)
    }
    unsubscribe() {
      live.delete(this.options.name)
    }
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

async function connected() {
  live.clear()
  const client = new RosClient({ url: 'ws://test:8765' })
  client.connect('full')
  await new Promise((resolve) => queueMicrotask(() => resolve(null)))
  return client
}

describe('optional topics', () => {
  it('leaves the costmap and particle cloud closed until asked for', async () => {
    await connected()
    expect(live.has('/scan')).toBe(true)
    expect(live.has('/global_costmap/costmap')).toBe(false)
    expect(live.has('/particle_cloud')).toBe(false)
  })

  it('opens one when asked and closes it again, leaving the rest alone', async () => {
    const client = await connected()
    client.setOptionalTopics(['costmap'])
    expect(live.has('/global_costmap/costmap')).toBe(true)
    expect(live.has('/particle_cloud')).toBe(false)

    client.setOptionalTopics([])
    expect(live.has('/global_costmap/costmap')).toBe(false)
    expect(live.has('/scan')).toBe(true)
  })
})
