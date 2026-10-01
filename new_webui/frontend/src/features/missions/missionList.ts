/**
 * What a mission row says beyond its name: where it goes, and how it last went.
 *
 * Kept out of the view so the rules — which run counts as "last", how a long
 * route is shortened — can be tested without mounting a table.
 */
import { isRunLive, type MissionRun, type RunState } from '@/domain/types'

/**
 * The most recent run of a mission that has finished.
 *
 * Live runs are left out: "running" is already the row's status, and showing
 * it again as the last result would say the same thing twice. Runs arrive
 * newest first from the server, but are compared by time anyway so a list
 * merged from two polls cannot reorder the answer.
 */
export function lastFinishedRun(runs: MissionRun[], missionId: string): MissionRun | null {
  let latest: MissionRun | null = null
  for (const run of runs) {
    if (run.missionId !== missionId || isRunLive(run.state)) continue
    if (!latest || serverTime(run.startedAt) > serverTime(latest.startedAt)) latest = run
  }
  return latest
}

export interface RoutePreview {
  /** Names to show, in order. */
  shown: string[]
  /** How many stops were left out of the middle. */
  hidden: number
}

/**
 * A route as a short line of station names.
 *
 * Long routes keep their ends and drop the middle: where a route starts and
 * finishes is what tells two shuttles apart, the stops between rarely are.
 */
export function routePreview(
  stationIds: string[],
  nameOf: (id: string) => string,
  max = 4,
): RoutePreview {
  const names = stationIds.map(nameOf)
  if (names.length <= max) return { shown: names, hidden: 0 }
  const head = names.slice(0, max - 1)
  const tail = names[names.length - 1] as string
  return { shown: [...head, tail], hidden: names.length - max }
}

/**
 * A server timestamp as epoch milliseconds.
 *
 * SQLite's `datetime('now')` is UTC but carries no zone, and `Date` reads a
 * zoneless string as local time — off by the browser's offset, which is seven
 * hours here.
 */
export function serverTime(at: string): number {
  const iso = at.includes('T') ? at : at.replace(' ', 'T')
  return Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
}

/** "just now", "5m ago", "3h ago", "2d ago". */
export function timeAgo(at: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - serverTime(at)) / 1000))
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

export const RUN_RESULT: Record<
  Exclude<RunState, 'running' | 'stopping'>,
  { label: string; tone: string }
> = {
  done: { label: 'completed', tone: 'text-status-ok' },
  failed: { label: 'failed', tone: 'text-status-fault' },
  canceled: { label: 'canceled', tone: 'text-muted' },
}
