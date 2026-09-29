/**
 * Fleet connection pool.
 *
 * Lives outside the component tree, on purpose. If the connections were owned
 * by the Robot page, navigating to Dashboard would tear them all down and the
 * fleet would read as offline — which is precisely the moment an operator most
 * wants the truth.
 *
 * Tiering is what makes a fleet affordable. Every robot holds a cheap socket
 * with three low-rate topics, enough to answer "is it alive, what is it doing,
 * how is its battery". Only the robot being looked at subscribes to pose at
 * 30 Hz, laser, costmap and map.
 *
 *   20 robots x vitals   ~ 40 messages/second   fine
 *   20 robots x full     ~ 1400 messages/second plus PNG encodes   not fine
 */

import { RosClient, type ClientSnapshot } from '@/domain/ros/client'
import type { Tier } from '@/domain/ros/health'
import type { RobotConfig } from '@/domain/types'

/** How often staleness is re-evaluated when no traffic is arriving. */
const POLL_MS = 1000

export type PoolListener = (robotId: string, snapshot: ClientSnapshot) => void

interface Entry {
  client: RosClient
  url: string
  namespace: string
  unsubscribe: () => void
}

export class RosPool {
  private entries = new Map<string, Entry>()
  private listeners = new Set<PoolListener>()
  private muted = new Set<string>()
  private focusedId: string | null = null
  private pollHandle: ReturnType<typeof setInterval> | null = null

  onSnapshot(listener: PoolListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  isMuted(robotId: string): boolean {
    return this.muted.has(robotId)
  }

  /**
   * Reconcile the pool against the registry.
   *
   * Idempotent, so it can be called on every registry change. A robot whose
   * bridge URL or namespace changed is reconnected; one that disappeared is
   * disposed.
   */
  sync(robots: readonly RobotConfig[]): void {
    const wanted = new Map(robots.map((robot) => [robot.id, robot]))

    for (const [id, entry] of this.entries) {
      const robot = wanted.get(id)
      if (!robot) {
        entry.unsubscribe()
        entry.client.dispose()
        this.entries.delete(id)
        continue
      }
      // A moved bridge is a different endpoint, not a reconfiguration.
      if (entry.url !== robot.bridgeUrl || entry.namespace !== robot.namespace) {
        entry.unsubscribe()
        entry.client.dispose()
        this.entries.delete(id)
      }
    }

    for (const robot of wanted.values()) {
      if (!this.entries.has(robot.id)) this.create(robot)
    }

    this.applyTiers()
    this.ensurePolling()
  }

  private create(robot: RobotConfig): void {
    const client = new RosClient({ url: robot.bridgeUrl, namespace: robot.namespace })
    const unsubscribe = client.subscribeToSnapshots((snapshot) => {
      for (const listener of this.listeners) listener(robot.id, snapshot)
    })
    this.entries.set(robot.id, {
      client,
      unsubscribe,
      url: robot.bridgeUrl,
      namespace: robot.namespace,
    })
  }

  /**
   * Promote one robot to the full tier and demote everyone else.
   *
   * Passing null demotes all — used when leaving a robot's page, so the 30 Hz
   * subscriptions stop the moment nothing is rendering them.
   */
  focus(robotId: string | null): void {
    this.focusedId = robotId
    this.applyTiers()
  }

  setMuted(robotId: string, muted: boolean): void {
    if (muted) this.muted.add(robotId)
    else this.muted.delete(robotId)
    this.applyTiers()
  }

  private applyTiers(): void {
    for (const [id, entry] of this.entries) {
      if (this.muted.has(id)) {
        entry.client.disconnect()
        continue
      }
      const tier: Tier = id === this.focusedId ? 'full' : 'vitals'
      entry.client.connect(tier)
    }
  }

  clientFor(robotId: string): RosClient | null {
    return this.entries.get(robotId)?.client ?? null
  }

  /**
   * A topic that has gone quiet produces no event, so nothing would recompute
   * its state. The tick is what lets silence become visible.
   */
  private ensurePolling(): void {
    if (this.pollHandle !== null || this.entries.size === 0) return
    this.pollHandle = setInterval(() => {
      for (const entry of this.entries.values()) entry.client.poll()
    }, POLL_MS)
  }

  dispose(): void {
    if (this.pollHandle !== null) {
      clearInterval(this.pollHandle)
      this.pollHandle = null
    }
    for (const entry of this.entries.values()) {
      entry.unsubscribe()
      entry.client.dispose()
    }
    this.entries.clear()
    this.listeners.clear()
  }
}

let singleton: RosPool | null = null

export function useRosPool(): RosPool {
  singleton ??= new RosPool()
  return singleton
}

/** Tests only — drops the shared instance so each case starts clean. */
export function resetRosPool(): void {
  singleton?.dispose()
  singleton = null
}
