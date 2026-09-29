/**
 * Minimal ambient types for roslibjs.
 *
 * The package ships no types. A bare `declare module 'roslib'` would make the
 * whole thing `any`, which hides exactly the mistakes worth catching at this
 * boundary — a misspelled option, a handler with the wrong arity. Only the
 * surface this application uses is declared; extend it when something new is
 * needed rather than widening it to any.
 */
declare module 'roslib' {
  export interface RosOptions {
    url: string
    /** rosbridge protocol: 'json' (default) or 'cbor'. */
    transportLibrary?: string
  }

  /**
   * Raw rosbridge protocol op, used for the operations roslibjs does not model
   * — notably a subscribe carrying explicit QoS, and ROS 2 action goals.
   */
  export interface ConnectionMessage {
    op: string
    id?: string
    topic?: string
    type?: string
    throttle_rate?: number
    queue_length?: number
    qos?: Record<string, string | number>
    action?: string
    action_type?: string
    args?: Record<string, unknown>
    [key: string]: unknown
  }

  export class Ros {
    constructor(options: RosOptions)
    on(event: 'connection' | 'close', callback: () => void): void
    on(event: 'error', callback: (error: unknown) => void): void
    on(event: string, callback: (data: never) => void): void
    close(): void
    callOnConnection(message: ConnectionMessage): void
  }

  export interface TopicOptions {
    ros: Ros
    name: string
    messageType: string
    /** Milliseconds rosbridge waits between deliveries. 0 means unthrottled. */
    throttle_rate?: number
    queue_length?: number
    latch?: boolean
    compression?: string
  }

  export class Topic<TMessage = unknown> {
    constructor(options: TopicOptions)
    readonly name: string
    subscribe(callback: (message: TMessage) => void): void
    unsubscribe(): void
    publish(message: unknown): void
    advertise(): void
    unadvertise(): void
  }

  export class Message {
    constructor(values: Record<string, unknown>)
  }

  export class ServiceRequest {
    constructor(values: Record<string, unknown>)
  }

  export interface ServiceOptions {
    ros: Ros
    name: string
    serviceType: string
  }

  export class Service<TRequest = unknown, TResponse = unknown> {
    constructor(options: ServiceOptions)
    callService(
      request: TRequest,
      callback: (response: TResponse) => void,
      failedCallback?: (error: string) => void,
    ): void
  }

  const ROSLIB: {
    Ros: typeof Ros
    Topic: typeof Topic
    Message: typeof Message
    Service: typeof Service
    ServiceRequest: typeof ServiceRequest
  }
  export default ROSLIB
}
