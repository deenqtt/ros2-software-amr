/**
 * Online means the robot answered, not that the relay accepted the socket.
 *
 * The backend relay accepts the browser's socket before it reaches the robot.
 * Counting that open socket as online made a robot with a wrong bridge address
 * flicker Online → Connecting about once a second, forever, because each
 * "connection" also reset the backoff.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

interface FakeRos {
  handlers: Record<string, (payload?: unknown) => void>
  closed: boolean
  fire(event: string, payload?: unknown): void
}

const sockets = vi.hoisted(() => [] as FakeRos[])

vi.mock('roslib', () => {
  class Ros {
    handlers: Record<string, (payload?: unknown) => void> = {}
    closed = false
    constructor() {
      sockets.push(this as unknown as FakeRos)
    }
    on(event: string, cb: (payload?: unknown) => void) {
      this.handlers[event] = cb
    }
    fire(event: string, payload?: unknown) {
      this.handlers[event]?.(payload)
    }
    close() {
      this.closed = true
    }
  }
  class Topic {
    subscribe() {}
    unsubscribe() {}
    publish() {}
  }
  class Message {
    constructor(public values: unknown) {}
  }
  const api = { Ros, Topic, Message, Service: class {}, ServiceRequest: class {} }
  return { default: api, ...api }
})

import { READY_TIMEOUT_MS, RELAY_READY, RosClient } from '../client'
import { deriveLinkState } from '../link'

const READY = { op: 'status', level: 'info', msg: RELAY_READY }

/** Pending timers only: a cancelled one is removed, as the browser would. */
let timers: { id: number; fn: () => void; ms: number }[]
let nextId = 0

function makeClient() {
  timers = []
  sockets.length = 0
  const client = new RosClient({
    url: 'ws://relay/backend/api/robots/r1/ros',
    random: () => 0.5, // no jitter: delays are exactly 1 s, 2 s, 4 s…
    setTimeoutFn: ((fn: () => void, ms?: number) => {
      nextId += 1
      timers.push({ id: nextId, fn, ms: ms ?? 0 })
      return nextId as unknown as ReturnType<typeof setTimeout>
    }) as typeof setTimeout,
    clearTimeoutFn: ((handle: unknown) => {
      timers = timers.filter((timer) => timer.id !== (handle as number))
    }) as typeof clearTimeout,
  })
  return client
}

function state(client: RosClient) {
  const s = client.snapshot()
  return deriveLinkState({ muted: false, socketOpen: s.socketOpen, connecting: s.connecting, hasStaleTopic: false })
}

function socketAt(index: number): FakeRos {
  const socket = sockets[index]
  if (!socket) throw new Error(`no socket ${index}`)
  return socket
}

function lastTimer(): { id: number; fn: () => void; ms: number } {
  const timer = timers[timers.length - 1]
  if (!timer) throw new Error('no timer')
  return timer
}

/** Run the most recent timer (the retry), which opens the next socket. */
function runLastTimer() {
  const timer = lastTimer()
  timers.pop()
  timer.fn()
}

describe('relay link state', () => {
  beforeEach(() => {
    sockets.length = 0
  })

  it('stays connecting while the relay has the socket but not the robot', () => {
    const client = makeClient()
    client.connect('vitals')
    socketAt(0).fire('connection')
    expect(client.snapshot().socketOpen).toBe(false)
    expect(state(client)).toBe('connecting')
  })

  it('is online once the relay says the robot answered', () => {
    const client = makeClient()
    client.connect('vitals')
    socketAt(0).fire('connection')
    socketAt(0).fire('status', READY)
    expect(state(client)).toBe('online')
    expect(client.snapshot().lastError).toBeNull()
  })

  it('ignores other status frames', () => {
    const client = makeClient()
    client.connect('vitals')
    socketAt(0).fire('connection')
    socketAt(0).fire('status', { op: 'status', level: 'warning', msg: 'something else' })
    expect(state(client)).toBe('connecting')
  })

  it('never shows online for an unreachable robot, and backs off', () => {
    const client = makeClient()
    client.connect('vitals')
    const delays: number[] = []
    for (let i = 0; i < 4; i += 1) {
      const socket = socketAt(sockets.length - 1)
      socket.fire('connection')
      expect(state(client)).not.toBe('online')
      socket.fire('close', { code: 1011 })
      delays.push(lastTimer().ms)
      runLastTimer()
    }
    // 1 s, 2 s, 4 s, 8 s — not 1 s forever.
    expect(delays).toEqual([1000, 2000, 4000, 8000])
    expect(client.snapshot().lastError).toMatch(/unreachable/i)
  })

  it('resets the backoff only after the robot answered', () => {
    const client = makeClient()
    client.connect('vitals')
    socketAt(0).fire('connection')
    socketAt(0).fire('close', { code: 1011 })
    runLastTimer()
    socketAt(1).fire('connection')
    socketAt(1).fire('status', READY)
    expect(client.snapshot().attempt).toBe(0)
    socketAt(1).fire('close', { code: 1006 })
    expect(lastTimer().ms).toBe(1000)
  })

  it.each([4401, 4403, 4404])('does not retry by itself after close %i', (code) => {
    const client = makeClient()
    client.connect('vitals')
    socketAt(0).fire('connection')
    socketAt(0).fire('close', { code })
    expect(timers).toHaveLength(0) // no retry, and the ready timer was cancelled
    expect(state(client)).toBe('offline')
    expect(client.snapshot().lastError).toBeTruthy()

    // The page asking again (navigation, focus) opens a new socket.
    client.connect('vitals')
    expect(sockets).toHaveLength(2)
  })

  it('gives up on a socket that never says ready, and retries at once', () => {
    const client = makeClient()
    client.connect('vitals')
    socketAt(0).fire('connection')
    expect(lastTimer().ms).toBe(READY_TIMEOUT_MS)
    runLastTimer()
    expect(socketAt(0).closed).toBe(true)
    expect(client.snapshot().lastError).toMatch(/no answer/i)
    // The retry is scheduled without waiting for the dead socket's close…
    expect(lastTimer().ms).toBe(1000)
    // …and that late close changes nothing.
    socketAt(0).fire('close', { code: 1006 })
    expect(timers).toHaveLength(1)
    runLastTimer()
    expect(sockets).toHaveLength(2)
  })

  it('ignores a replaced socket closing late, so the live one keeps working', () => {
    const client = makeClient()
    client.connect('vitals')
    socketAt(0).fire('connection')
    socketAt(0).fire('status', READY)
    client.disconnect() // e.g. muted, then unmuted
    client.connect('vitals')
    socketAt(1).fire('connection')
    socketAt(1).fire('status', READY)
    // The first socket's close arrives only now.
    socketAt(0).fire('close', { code: 1000 })
    expect(state(client)).toBe('online')
    expect(client.publish('teleopCmdVel', { linear: { x: 0 }, angular: { z: 0 } })).toBe(true)
    expect(timers).toHaveLength(0)
  })

  it('cannot send until the robot answered', () => {
    const client = makeClient()
    client.connect('vitals')
    socketAt(0).fire('connection')
    expect(client.publish('teleopCmdVel', { linear: { x: 0 }, angular: { z: 0 } })).toBe(false)
    socketAt(0).fire('status', READY)
    expect(client.publish('teleopCmdVel', { linear: { x: 0 }, angular: { z: 0 } })).toBe(true)
  })

  it('says the link was lost when an online robot drops', () => {
    const client = makeClient()
    client.connect('vitals')
    socketAt(0).fire('connection')
    socketAt(0).fire('status', READY)
    socketAt(0).fire('close', { code: 1011 })
    expect(client.snapshot().lastError).toMatch(/lost the connection/i)
  })

  it('cancels the ready timer on disconnect', () => {
    const client = makeClient()
    client.connect('vitals')
    socketAt(0).fire('connection')
    client.disconnect()
    expect(timers).toHaveLength(0)
  })
})
