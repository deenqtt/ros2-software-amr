/**
 * One robot's rosbridge connection.
 *
 * A class, not a composable holding module-level state. The old project kept
 * the socket, the TF buffer and the mission cursor in `let` bindings at module
 * scope, so a second robot was structurally impossible — `connect()` began by
 * tearing down whatever was already there.
 *
 * Responsibilities kept deliberately narrow: open and keep a socket, hold the
 * subscription set for a tier, count what arrives, reconnect with backoff.
 * Everything about what the messages *mean* lives elsewhere.
 */

import ROSLIB, { type Ros, type Topic } from 'roslib'
import { backoffDelay } from './link'
import { specsForTier, topicState, type Tier, type TopicHealth, type TopicSpec } from './health'
import { LATCHED_QOS, rosNames, type RosNames } from './topics'
import { TfBuffer, type TransformStamped } from './tf'

export interface RosClientOptions {
  url: string
  namespace?: string
  /** Injected in tests. */
  now?: () => number
  setTimeoutFn?: typeof setTimeout
  clearTimeoutFn?: typeof clearTimeout
  random?: () => number
}

export interface ClientSnapshot {
  socketOpen: boolean
  connecting: boolean
  attempt: number
  tier: Tier | null
  lastError: string | null
  topics: TopicHealth[]
}

type Listener = (snapshot: ClientSnapshot) => void
type MessageHandler = (key: string, message: unknown) => void

interface TopicRecord {
  spec: TopicSpec
  topic: Topic | null
  messages: number
  lastMessageAt: number | null
  /**
   * The last payload seen.
   *
   * Kept so a view opened mid-session has something to draw immediately. A
   * status topic at 1 Hz otherwise leaves a fresh screen blank for a second,
   * and a latched one may never send again at all.
   */
  lastMessage: unknown
  /** Timestamps within the rate window, for the observed-Hz readout. */
  recent: number[]
}

const RATE_WINDOW_MS = 5000

/** Message types for the topics this client publishes to. */
const PUBLISH_TYPES: Partial<Record<string, string>> = {
  teleopCmdVel: 'geometry_msgs/msg/Twist',
  goalPose: 'geometry_msgs/msg/PoseStamped',
  initialPose: 'geometry_msgs/msg/PoseWithCovarianceStamped',
  zones: 'std_msgs/msg/String',
  missionPayload: 'std_msgs/msg/String',
}

export class RosClient {
  private ros: Ros | null = null
  private records = new Map<string, TopicRecord>()
  private publishers = new Map<string, Topic>()
  private listeners = new Set<Listener>()
  private messageHandlers = new Set<MessageHandler>()

  private socketOpen = false
  private connecting = false
  private attempt = 0
  private tier: Tier | null = null
  private lastError: string | null = null
  private retryHandle: ReturnType<typeof setTimeout> | null = null
  private disposed = false

  readonly tf = new TfBuffer()
  private names: RosNames

  private readonly now: () => number
  private readonly setTimeoutFn: typeof setTimeout
  private readonly clearTimeoutFn: typeof clearTimeout
  private readonly random: () => number

  constructor(private options: RosClientOptions) {
    this.names = rosNames(options.namespace ?? '')
    this.now = options.now ?? (() => Date.now())
    this.setTimeoutFn = options.setTimeoutFn ?? setTimeout
    this.clearTimeoutFn = options.clearTimeoutFn ?? clearTimeout
    this.random = options.random ?? Math.random
  }

  // ── Observation ────────────────────────────────────────────────────────────

  subscribeToSnapshots(listener: Listener): () => void {
    this.listeners.add(listener)
    listener(this.snapshot())
    return () => this.listeners.delete(listener)
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler)
    return () => this.messageHandlers.delete(handler)
  }

  snapshot(): ClientSnapshot {
    const at = this.now()
    return {
      socketOpen: this.socketOpen,
      connecting: this.connecting,
      attempt: this.attempt,
      tier: this.tier,
      lastError: this.lastError,
      topics: [...this.records.values()].map((record) => this.healthOf(record, at)),
    }
  }

  private healthOf(record: TopicRecord, at: number): TopicHealth {
    const sample = {
      subscribed: record.topic !== null,
      messages: record.messages,
      lastMessageAt: record.lastMessageAt,
    }
    const window = record.recent.filter((t) => at - t <= RATE_WINDOW_MS)
    return {
      key: record.spec.key,
      label: record.spec.label,
      cadence: record.spec.cadence,
      tier: record.spec.tier,
      needsStack: record.spec.needsStack ?? false,
      ...sample,
      state: topicState(record.spec, sample, at),
      rateHz: window.length >= 2 ? Number((window.length / (RATE_WINDOW_MS / 1000)).toFixed(1)) : null,
    }
  }

  private emit(): void {
    const snapshot = this.snapshot()
    for (const listener of this.listeners) listener(snapshot)
  }

  /** Called on a timer by the pool, so staleness is noticed without traffic. */
  poll(): void {
    if (this.records.size > 0) this.emit()
  }

  // ── Connection ─────────────────────────────────────────────────────────────

  connect(tier: Tier): void {
    if (this.disposed) return
    this.tier = tier

    if (this.socketOpen) {
      this.applyTier(tier)
      return
    }
    if (this.connecting) return

    this.connecting = true
    this.lastError = null
    this.emit()

    const ros = new ROSLIB.Ros({ url: this.options.url })
    this.ros = ros

    ros.on('connection', () => {
      this.socketOpen = true
      this.connecting = false
      this.attempt = 0
      this.applyTier(this.tier ?? tier)
      this.emit()
    })

    ros.on('error', (error: unknown) => {
      // roslibjs reports errors as an Event with no useful message; a generic
      // string beats printing "[object Event]" at an operator.
      this.lastError = error instanceof Error ? error.message : 'WebSocket error'
      this.emit()
    })

    ros.on('close', () => {
      this.socketOpen = false
      this.connecting = false
      this.teardownSubscriptions()
      this.publishers.clear()
      // Stale transforms from a dead session must never be reused: they would
      // put the robot marker somewhere it is not.
      this.tf.clear()
      this.emit()
      this.scheduleRetry()
    })
  }

  private scheduleRetry(): void {
    if (this.disposed || this.tier === null) return
    this.attempt += 1
    const delay = backoffDelay(this.attempt, {}, this.random)
    this.connecting = true
    this.emit()
    this.retryHandle = this.setTimeoutFn(() => {
      this.retryHandle = null
      this.connecting = false
      if (!this.disposed && this.tier !== null) this.connect(this.tier)
    }, delay)
  }

  /** Stop monitoring. Cancels retries; the socket does not come back by itself. */
  disconnect(): void {
    this.tier = null
    if (this.retryHandle !== null) {
      this.clearTimeoutFn(this.retryHandle)
      this.retryHandle = null
    }
    this.teardownSubscriptions()
    this.records.clear()
    this.publishers.clear()
    this.tf.clear()
    this.attempt = 0
    this.connecting = false
    if (this.ros) {
      this.ros.close()
      this.ros = null
    }
    this.socketOpen = false
    this.emit()
  }

  dispose(): void {
    this.disposed = true
    this.disconnect()
    this.listeners.clear()
    this.messageHandlers.clear()
  }

  // ── Subscriptions ──────────────────────────────────────────────────────────

  /**
   * Bring the open subscriptions in line with the requested tier.
   *
   * Counters survive a tier change, so leaving a robot's page and coming back
   * does not reset its diagnostics to zero.
   */
  private applyTier(tier: Tier): void {
    const wanted = new Map(specsForTier(tier).map((spec) => [spec.key, spec]))

    for (const [key, record] of this.records) {
      if (!wanted.has(key) && record.topic) {
        record.topic.unsubscribe()
        record.topic = null
      }
    }

    for (const [key, spec] of wanted) {
      const existing = this.records.get(key)
      if (existing?.topic) continue
      const record: TopicRecord = existing ?? {
        spec,
        topic: null,
        messages: 0,
        lastMessageAt: null,
        lastMessage: undefined,
        recent: [],
      }
      record.topic = this.openTopic(spec)
      this.records.set(key, record)
    }
  }

  private openTopic(spec: TopicSpec): Topic | null {
    if (!this.ros) return null
    const name = this.names.topics[spec.key as keyof RosNames['topics']]
    if (!name) return null

    const topic = new ROSLIB.Topic({
      ros: this.ros,
      name,
      messageType: spec.messageType,
      throttle_rate: spec.throttleMs ?? 0,
      queue_length: 1,
    })

    // Order matters, and it is the whole fix.
    //
    // rosbridge keeps one subscription per topic shared by every client, and
    // its own source says the QoS "is determined at the first registration of
    // a subscriber". roslibjs's subscribe carries no QoS, so whichever request
    // arrives first decides it for everyone — and a first request sent while
    // nothing is publishing yet resolves to volatile, permanently.
    //
    // A volatile subscription never receives a latched replay. /tf_static and
    // /robot_description publish exactly once, when robot_state_publisher
    // starts, and then never again: the browser therefore never learned where
    // the laser is mounted, and drew every scan from the robot's centre
    // instead — a fixed offset of a third of a metre on the robot this was
    // found on, which reads as a miscalibrated sensor rather than a missing
    // subscription. /map hid the bug by republishing every few seconds.
    //
    // Repeating the request afterwards does not help; the profile is already
    // fixed. Asking first does.
    if (spec.cadence === 'latched') {
      this.ros.callOnConnection({
        op: 'subscribe',
        topic: name,
        type: spec.messageType,
        throttle_rate: 0,
        queue_length: 1,
        qos: LATCHED_QOS,
      })
    }

    topic.subscribe((message: unknown) => this.record(spec.key, message))

    return topic
  }

  private record(key: string, message: unknown): void {
    const record = this.records.get(key)
    if (!record) return

    // Feed the transform buffer before anything else looks at it. Without
    // this the buffer stays empty, resolveMapToBase() never answers, and every
    // consumer of the robot's pose silently renders nothing — which is what
    // it did: the map drew fine while the robot and its laser were simply
    // absent, with no error anywhere to say why.
    if (key === 'tf' || key === 'tfStatic') {
      const frame = message as { transforms?: TransformStamped[] }
      if (frame.transforms) this.tf.ingest(frame.transforms)
    }

    const at = this.now()
    record.messages += 1
    record.lastMessageAt = at
    record.lastMessage = message
    record.recent.push(at)
    if (record.recent.length > 200) record.recent.splice(0, record.recent.length - 200)

    for (const handler of this.messageHandlers) handler(key, message)
  }

  // ── Publishing ─────────────────────────────────────────────────────────────

  /**
   * Publish to one of the registered topics.
   *
   * Publishers are cached: creating a ROSLIB.Topic per message would advertise
   * and unadvertise on every frame, which at teleop rates floods rosbridge
   * with bookkeeping instead of commands.
   */
  /**
   * The last message seen on a topic, or undefined.
   *
   * For a reader that wants the current value rather than the next change —
   * a fleet view reading one field from every robot, say, where subscribing
   * again per robot would double every subscription on the graph.
   */
  latest(key: keyof RosNames['topics']): unknown {
    return this.records.get(key)?.lastMessage
  }

  publish(key: keyof RosNames['topics'], message: Record<string, unknown>): boolean {
    if (!this.ros || !this.socketOpen) return false
    const name = this.names.topics[key]
    if (!name) return false

    let publisher = this.publishers.get(key)
    if (!publisher) {
      publisher = new ROSLIB.Topic({
        ros: this.ros,
        name,
        messageType: PUBLISH_TYPES[key] ?? 'std_msgs/msg/String',
      })
      this.publishers.set(key, publisher)
    }
    publisher.publish(new ROSLIB.Message(message))
    return true
  }

  /**
   * Call a service and resolve with its response.
   *
   * Rejects rather than resolving on failure: a caller that cannot tell a
   * refusal from a success will report one as the other, which is how the old
   * UI announced an emergency stop that never happened.
   */
  callService<TResponse = Record<string, unknown>>(
    key: keyof RosNames['services'],
    serviceType: string,
    request: Record<string, unknown>,
    timeoutMs = 30_000,
  ): Promise<TResponse> {
    return new Promise((resolve, reject) => {
      if (!this.ros || !this.socketOpen) {
        reject(new Error('Not connected to this robot'))
        return
      }
      const name = this.names.services[key]
      const service = new ROSLIB.Service<Record<string, unknown>, TResponse>({
        ros: this.ros,
        name,
        serviceType,
      })

      let settled = false
      const timer = setTimeout(() => {
        if (settled) return
        settled = true
        reject(new Error(`${name} did not answer within ${Math.round(timeoutMs / 1000)}s`))
      }, timeoutMs)

      service.callService(
        new ROSLIB.ServiceRequest(request) as Record<string, unknown>,
        (response) => {
          if (settled) return
          settled = true
          clearTimeout(timer)
          resolve(response)
        },
        (error) => {
          if (settled) return
          settled = true
          clearTimeout(timer)
          reject(new Error(String(error) || `${name} failed`))
        },
      )
    })
  }

  private teardownSubscriptions(): void {
    for (const record of this.records.values()) {
      if (record.topic) {
        record.topic.unsubscribe()
        record.topic = null
      }
    }
  }
}
