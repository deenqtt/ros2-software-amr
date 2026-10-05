/**
 * What a mission row says beyond its name: where it goes, and how it last went.
 *
 * Kept out of the view so the rules — which run counts as "last", how a long
 * route is shortened — can be tested without mounting a table.
 */
import { isRunLive, type MissionRun, type MissionSummary, type RunState } from '@/domain/types'

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
 * Where a live run is, for a person: the stop it is heading to and how far
 * along the route that is. "step 2" alone made the operator open the route to
 * find out what step 2 was.
 *
 * Falls back to the bare index when the route is not loaded here — a run on
 * another map, or one whose route was deleted while it ran.
 */
export function runProgress(
  stepIndex: number,
  stationIds: string[] | null,
  nameOf: (id: string) => string,
): string {
  const step = stepIndex + 1
  if (!stationIds?.length) return `step ${step}`
  const target = stationIds[stepIndex]
  // Past the end means the route was edited under a live run; a count like
  // "6/2" would only confuse.
  if (target === undefined) return `step ${step}`
  return `→ ${nameOf(target)} (${step}/${stationIds.length})`
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

export interface MissionStatus {
  /** A text colour class, the same ones the table's status column uses. */
  tone: string
  label: string
  /** Why the last run ended, when the server said; for a tooltip. */
  detail: string | null
}

/**
 * A mission's state as one line, for the phone list where there is no room
 * for a status column: "Running · R1 · step 2 of 4", "Failed · 2h ago · R2".
 *
 * An empty route outranks how it last went: it cannot run again until it has
 * steps, so that is the thing to say.
 */
export function missionStatus(
  mission: Pick<MissionSummary, 'id' | 'stepCount'>,
  liveRun: MissionRun | null,
  runs: MissionRun[],
  now: number,
  robotName: (id: string | null) => string,
  canEdit = true,
): MissionStatus {
  if (liveRun) {
    const robot = robotName(liveRun.robotId)
    if (liveRun.state === 'stopping') {
      return { tone: 'text-status-warn', label: `Stopping · ${robot}`, detail: null }
    }
    const step = liveRun.stepIndex + 1
    const where =
      step <= mission.stepCount ? `step ${step} of ${mission.stepCount}` : `step ${step}`
    return { tone: 'text-status-run', label: `Running · ${robot} · ${where}`, detail: null }
  }
  if (!mission.stepCount) {
    return {
      tone: 'text-status-warn',
      label: `No steps yet${canEdit ? ' — add the first stop' : ''}`,
      detail: null,
    }
  }
  const last = lastFinishedRun(runs, mission.id)
  if (!last || isRunLive(last.state)) {
    return { tone: 'text-muted-soft', label: 'Never run', detail: null }
  }
  const result = RUN_RESULT[last.state as keyof typeof RUN_RESULT]
  const label = result.label.charAt(0).toUpperCase() + result.label.slice(1)
  return {
    tone: result.tone,
    label: `${label} · ${timeAgo(last.endedAt ?? last.startedAt, now)} · ${robotName(last.robotId)}`,
    detail: last.detail,
  }
}
