/**
 * The one status vocabulary, for every surface that speaks about a robot.
 *
 * The agent derives one of these words (amr_agent/robot_status.py) and reports
 * it to the registry; the dashboard, the robot page and the mission list read
 * it from there instead of each translating the robot's own topics again —
 * which is how "waiting for the operator" once rendered as "Docking".
 *
 * Each word also carries a tone from the shared StatusTone scale, so colour
 * means the same thing everywhere: red is always a robot that needs someone,
 * green is always a robot that is fine.
 *
 * `offline` is not a word the robot reports — a robot that cannot report
 * cannot say so. It is what this module returns when the last report is older
 * than a few heartbeats, judged from the server's received stamp.
 */
import type { RobotStatusValue, StatusTone } from './types/robot'

/** Heartbeat cadence of the agent's report (REPORT_INTERVAL_S) plus slack for
 * a few missed beats on a wifi robot. Past this, silence is the news. */
export const STATUS_FRESH_MS = 45_000

export const ROBOT_STATUSES: readonly RobotStatusValue[] = [
  'parked',
  'mapping',
  'ready',
  'on_mission',
  'waiting_confirm',
  'charging',
  'error',
  'paused',
]

const TONE: Record<RobotStatusValue, StatusTone> = {
  parked: 'neutral',
  mapping: 'active',
  ready: 'neutral',
  on_mission: 'active',
  // A robot holding a payload and waiting for someone is not an emergency,
  // but it is the one status that will not resolve without a person.
  waiting_confirm: 'attention',
  charging: 'success',
  error: 'fault',
  paused: 'warning',
}

const LABEL: Record<RobotStatusValue, string> = {
  parked: 'Parked',
  mapping: 'Surveying',
  ready: 'Ready',
  on_mission: 'On mission',
  waiting_confirm: 'Needs confirm',
  charging: 'Charging',
  error: 'Error',
  paused: 'Paused',
}

export interface RobotStatusDescriptor {
  tone: StatusTone
  label: string
  /** True when the word is missing or has gone stale. */
  offline: boolean
}

const NO_REPORT: RobotStatusDescriptor = {
  tone: 'neutral',
  label: 'No report yet',
  offline: true,
}

const GONE_QUIET: RobotStatusDescriptor = {
  tone: 'warning',
  label: 'Offline',
  offline: true,
}

/**
 * A registry stamp as an instant.
 *
 * SQLite's `datetime('now')` writes "2026-10-17 03:14:55": UTC, but with no
 * zone marker to say so. Handed to `Date.parse` that reads as local wall-clock
 * — seven hours adrift in WIB, which made a two-second-old report look hours
 * stale and every robot read as Offline. So the zone is made explicit here, the
 * same way `auditLabel.ts` does it; a stamp that already carries one is left
 * alone.
 */
function parseReported(value: string): number {
  const hasZone = /[zZ]$|[+-]\d\d:?(\d\d)?$/.test(value.trim())
  const iso = hasZone ? value.trim() : `${value.trim().replace(' ', 'T')}Z`
  return Date.parse(iso)
}

/** The status to show for one robot, staleness judged against `now`. */
export function robotStatusDescriptor(
  status: RobotStatusValue | null | undefined,
  reportedAt: string | null | undefined,
  now: number = Date.now(),
): RobotStatusDescriptor {
  if (!status) return NO_REPORT
  if (!reportedAt) return NO_REPORT
  const reported = parseReported(reportedAt)
  if (Number.isNaN(reported) || now - reported > STATUS_FRESH_MS) return GONE_QUIET
  return { tone: TONE[status], label: LABEL[status], offline: false }
}

/** The robot's one line: the status label, or its own context when it has some. */
export function robotStatusLine(
  status: RobotStatusValue | null | undefined,
  detail: string | null | undefined,
  reportedAt: string | null | undefined,
  now: number = Date.now(),
): string {
  const descriptor = robotStatusDescriptor(status, reportedAt, now)
  if (descriptor.offline) return descriptor.label
  const context = (detail ?? '').trim()
  return context || descriptor.label
}
