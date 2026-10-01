/**
 * What changed about a mission run between two polls, as events a person
 * would want to be told about.
 *
 * Pure, so the rules live in one tested place rather than inside a watcher:
 * which change counts as an arrival, which as an ending, and what is said
 * about a run that was already over before anyone was watching.
 */
import { isRunLive, type MissionRun } from '@/domain/types'

export type RunEventKind = 'started' | 'reached' | 'done' | 'failed' | 'canceled'

export interface RunEvent {
  kind: RunEventKind
  run: MissionRun
}

const TERMINAL: Partial<Record<MissionRun['state'], RunEventKind>> = {
  done: 'done',
  failed: 'failed',
  canceled: 'canceled',
}

/** The events between one sighting of a run and the next. */
export function diffRun(previous: MissionRun | undefined, next: MissionRun): RunEvent[] {
  const events: RunEvent[] = []

  if (!previous && isRunLive(next.state)) events.push({ kind: 'started', run: next })

  // An arrival is a new server stamp, not a new index: the same step on the
  // next lap has the same index and is still a new arrival.
  if (
    next.reachedAt !== null &&
    next.reachedIndex !== null &&
    next.reachedAt !== (previous?.reachedAt ?? null)
  ) {
    events.push({ kind: 'reached', run: next })
  }

  const ending = TERMINAL[next.state]
  if (ending && previous?.state !== next.state) events.push({ kind: ending, run: next })

  return events
}

/**
 * Events across every run in a poll.
 *
 * `previous` is null on the first poll. That poll is a baseline and says
 * nothing: a page opened in the afternoon must not announce every run that
 * finished in the morning.
 */
export function diffRuns(previous: Map<string, MissionRun> | null, next: MissionRun[]): RunEvent[] {
  if (previous === null) return []
  return next.flatMap((run) => diffRun(previous.get(run.id), run))
}
