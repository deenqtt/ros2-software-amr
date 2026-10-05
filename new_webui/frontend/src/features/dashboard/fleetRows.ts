/**
 * The fleet as a phone shows it: one line per robot, the line that matters.
 *
 * A phone has room for a name and one status, so this decides which status and
 * in what order — exception first (Wroblewski's mobile-first, NN/g's "content
 * over chrome"): a robot that needs a person, then robots at work, then idle,
 * then robots that are not connected. The detail the desktop table shows — the
 * stack, the map, the link — is one tap away on the robot's own page.
 *
 * A dropped link is reported as "Offline", at the bottom, rather than as a red
 * row at the top. On a phone a list of six red "no link" rows hides the one
 * robot that is stuck mid-route; the count of offline robots is in the summary.
 * The exception is a robot in the middle of a mission: losing sight of a robot
 * that is driving a route is worth a warning, so that row stays near the top.
 */
import type { LinkState } from '@/domain/ros/link'
import type { MissionRun, RobotConfig } from '@/domain/types'
import type { AttentionItem } from './attention'

export type FleetRowTone = 'fault' | 'warning' | 'active' | 'idle' | 'off'

export interface FleetRow {
  robotId: string
  name: string
  accent: number
  tone: FleetRowTone
  /** The one line under the name. */
  status: string
  /** False while the link is down or still opening. */
  connected: boolean
}

export interface FleetRowInput {
  robots: readonly RobotConfig[]
  attention: readonly AttentionItem[]
  linkFor: (robotId: string) => LinkState
  runFor: (robotId: string) => MissionRun | null
}

const RANK: Record<FleetRowTone, number> = { fault: 0, warning: 1, active: 2, idle: 3, off: 4 }

const LIVE_RUN = new Set(['running', 'stopping'])

function runLine(run: MissionRun): string {
  const lap =
    run.mode === 'laps'
      ? ` · lap ${run.lap}/${run.lapsTarget}`
      : run.mode === 'forever'
        ? ` · lap ${run.lap}`
        : ''
  const head = run.state === 'stopping' ? `Finishing lap · ${run.missionName}` : run.missionName
  return `${head} · step ${run.stepIndex + 1}${lap}`
}

function rowFor(robot: RobotConfig, input: FleetRowInput): FleetRow {
  const link = input.linkFor(robot.id)
  const base = {
    robotId: robot.id,
    name: robot.name,
    accent: robot.accent,
    connected: link !== 'offline' && link !== 'connecting',
  }

  const run = input.runFor(robot.id)
  const working = run !== null && LIVE_RUN.has(run.state)

  if (link === 'muted') return { ...base, tone: 'off', status: 'Not monitored' }
  if (link === 'offline' || link === 'connecting') {
    if (working) {
      const lost = link === 'offline' ? 'link lost' : 'reconnecting…'
      return { ...base, tone: 'warning', status: `${runLine(run)} · ${lost}` }
    }
    return { ...base, tone: 'off', status: link === 'offline' ? 'Offline' : 'Connecting…' }
  }

  // Worst problem first; attentionItems already sorts by severity.
  const problem = input.attention.find(
    (item) => item.robotId === robot.id && item.severity !== 'info',
  )
  if (problem) {
    return {
      ...base,
      tone: problem.severity === 'fault' ? 'fault' : 'warning',
      status: problem.title,
    }
  }

  if (working) return { ...base, tone: 'active', status: runLine(run) }

  if (robot.desiredMode === 'idle') return { ...base, tone: 'idle', status: 'Parked' }
  if (robot.desiredMode === 'map') return { ...base, tone: 'active', status: 'Surveying' }
  return { ...base, tone: 'idle', status: 'Idle' }
}

export function fleetRows(input: FleetRowInput): FleetRow[] {
  return input.robots
    .map((robot) => rowFor(robot, input))
    .sort(
      (a, b) =>
        RANK[a.tone] - RANK[b.tone] ||
        a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }),
    )
}

/** "4 robots · 1 needs you · 2 working · 1 not connected", without the zero parts. */
export function fleetLine(rows: readonly FleetRow[]): string {
  const count = (tones: FleetRowTone[]) => rows.filter((row) => tones.includes(row.tone)).length
  const parts = [`${rows.length} robot${rows.length === 1 ? '' : 's'}`]
  const needs = count(['fault', 'warning'])
  const working = count(['active'])
  const off = rows.filter((row) => !row.connected).length
  if (needs) parts.push(`${needs} need${needs === 1 ? 's' : ''} you`)
  if (working) parts.push(`${working} working`)
  if (off) parts.push(`${off} not connected`)
  return parts.join(' · ')
}
