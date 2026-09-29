/**
 * Link state and reconnect policy.
 *
 * Five states, not two. The old UI had `rosConnected: boolean`, which cannot
 * express the failure that actually bit it: rosbridge answering while the
 * stack behind it is dead. The bridge says hello, the robot is useless, and a
 * boolean calls that "connected".
 */

export type LinkState =
  /** Deliberately not monitored — a robot in the workshop. */
  | 'muted'
  /** No usable connection. */
  | 'offline'
  /** Opening, or reopening after a drop. */
  | 'connecting'
  /** Connected and periodic data is arriving. */
  | 'online'
  /** Connected, but a periodic topic has gone silent. */
  | 'stale'

export interface LinkInputs {
  muted: boolean
  socketOpen: boolean
  connecting: boolean
  /** A periodic topic in the active tier has exceeded its budget. */
  hasStaleTopic: boolean
}

export function deriveLinkState(input: LinkInputs): LinkState {
  // Mute wins over everything: the operator has said they do not care right
  // now, and showing a fault for a machine that is deliberately off is how a
  // console teaches people to ignore red.
  if (input.muted) return 'muted'
  if (input.socketOpen) return input.hasStaleTopic ? 'stale' : 'online'
  if (input.connecting) return 'connecting'
  return 'offline'
}

/** Whether commands may be sent. Stale counts as no: we cannot see the robot. */
export function linkAllowsCommands(state: LinkState): boolean {
  return state === 'online'
}

// ── Reconnect backoff ────────────────────────────────────────────────────────

export interface BackoffOptions {
  baseMs?: number
  factor?: number
  maxMs?: number
  /** Fraction of the delay to randomise, 0..1. */
  jitter?: number
}

const DEFAULTS: Required<BackoffOptions> = {
  baseMs: 1000,
  factor: 2,
  maxMs: 30_000,
  jitter: 0.25,
}

/**
 * Delay before retry number `attempt` (1-based).
 *
 * Jitter is not decoration. With a fleet, a single network blip drops every
 * robot at once; a fixed schedule then has all of them retry in the same
 * millisecond, forever, in lockstep. Spreading the retries is what stops a
 * recovering network from being hit by a synchronised stampede.
 */
export function backoffDelay(
  attempt: number,
  options: BackoffOptions = {},
  random: () => number = Math.random,
): number {
  const { baseMs, factor, maxMs, jitter } = { ...DEFAULTS, ...options }
  if (attempt < 1) return 0

  const raw = Math.min(baseMs * factor ** (attempt - 1), maxMs)
  // random() in [0,1) maps to a spread of [-jitter, +jitter].
  const spread = raw * jitter * (random() * 2 - 1)
  return Math.max(0, Math.round(raw + spread))
}

/** Upper bound for a given attempt, for tests and for documenting behaviour. */
export function backoffCeiling(options: BackoffOptions = {}): number {
  const { maxMs, jitter } = { ...DEFAULTS, ...options }
  return Math.round(maxMs * (1 + jitter))
}
