/**
 * What needs a person, and why.
 *
 * The difference between a dashboard and a wallpaper. A screen that shows six
 * robots and leaves the operator to work out which one is in trouble has made
 * them do the scanning; this does the scanning and shows only the answer.
 *
 * Deliberately a pure function of state, with no Vue in it, so the rules can be
 * read and tested on their own — these are the sentences somebody will be
 * reading at two in the morning.
 */

import type { LinkState } from '@/domain/ros/link'
import type { MissionRun, RobotConfig } from '@/domain/types'

/** Ordered worst first; the list is rendered in this order. */
export const ATTENTION_SEVERITIES = ['fault', 'warn', 'info'] as const
export type AttentionSeverity = (typeof ATTENTION_SEVERITIES)[number]

export interface AttentionItem {
  /** Stable across polls, so the list does not reshuffle while being read. */
  key: string
  robotId: string
  robotName: string
  severity: AttentionSeverity
  /** What is wrong, in one line. */
  title: string
  /** What to do about it. Omitted when there is nothing useful to say. */
  action?: string
}

export interface AgentSnapshot {
  mode: string
  state: string
  detail: string
  backend: string
}

export interface FleetInput {
  robots: RobotConfig[]
  linkFor: (robotId: string) => LinkState
  agentFor: (robotId: string) => AgentSnapshot | null
  runFor: (robotId: string) => MissionRun | null
}

const SEVERITY_ORDER: Record<AttentionSeverity, number> = { fault: 0, warn: 1, info: 2 }

/**
 * One robot's problems, worst first.
 *
 * Only the first is usually worth acting on — a robot that is offline has an
 * unknown mode too, and listing both would be reporting the same fact twice.
 */
function forRobot(robot: RobotConfig, input: FleetInput): AttentionItem[] {
  const items: AttentionItem[] = []
  const link = input.linkFor(robot.id)
  const agent = input.agentFor(robot.id)
  const run = input.runFor(robot.id)

  const base = { robotId: robot.id, robotName: robot.name }

  if (link === 'offline') {
    // Everything else is unknowable from here, so nothing else is reported.
    return [
      {
        ...base,
        key: `${robot.id}:offline`,
        severity: 'fault',
        title: 'No link to this robot',
        action: 'Check it is powered on and that rosbridge is reachable.',
      },
    ]
  }

  if (link === 'muted') {
    return [
      {
        ...base,
        key: `${robot.id}:muted`,
        severity: 'info',
        title: 'Monitoring is muted',
        action: 'Nothing is being read from this robot.',
      },
    ]
  }

  if (link === 'stale') {
    items.push({
      ...base,
      key: `${robot.id}:stale`,
      severity: 'warn',
      title: 'Telemetry has gone quiet',
      action: 'The link is up but nothing is arriving. Check the robot has not hung.',
    })
  }

  if (!robot.activeMapId) {
    items.push({
      ...base,
      key: `${robot.id}:no-map`,
      severity: 'warn',
      title: 'No map assigned',
      action: 'Assign a map before this robot can navigate or run a mission.',
    })
  }

  if (agent?.backend && agent.backend !== 'ok' && agent.backend !== 'unknown') {
    items.push({
      ...base,
      key: `${robot.id}:backend`,
      severity: 'warn',
      title: `This robot cannot reach the registry (${agent.backend})`,
      action: 'Maps, stations and zones will not reach it until this is fixed.',
    })
  }

  // The reason desired_mode exists: intent and reality drifting apart, with
  // nothing previously reporting it.
  if (robot.desiredMode === 'nav' && robot.activeMapId && agent) {
    if (agent.state === 'failed') {
      items.push({
        ...base,
        key: `${robot.id}:nav-failed`,
        severity: 'fault',
        title: 'Navigation failed to start',
        action: agent.detail || 'Check the robot log.',
      })
    } else if (agent.mode !== 'nav' && agent.state !== 'starting') {
      items.push({
        ...base,
        key: `${robot.id}:not-navigating`,
        severity: 'warn',
        title: 'Should be navigating, but is not',
        action: agent.detail || 'The agent has not brought Nav2 up yet.',
      })
    }
  }

  if (run?.state === 'failed') {
    items.push({
      ...base,
      key: `${robot.id}:run-failed`,
      severity: 'fault',
      title: `${run.missionName} failed`,
      action: run.detail ?? undefined,
    })
  }

  return items
}

/** Everything that needs a person, across the fleet, worst first. */
export function attentionItems(input: FleetInput): AttentionItem[] {
  return input.robots
    .flatMap((robot) => forRobot(robot, input))
    .sort((a, b) => {
      const bySeverity = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
      // Then by name, so the order is stable across polls rather than following
      // whatever the fleet list happened to return.
      return bySeverity !== 0 ? bySeverity : a.robotName.localeCompare(b.robotName)
    })
}

export interface FleetCounts {
  total: number
  online: number
  working: number
  parked: number
  needsAttention: number
}

export function fleetCounts(input: FleetInput, attention: AttentionItem[]): FleetCounts {
  const troubled = new Set(
    attention.filter((item) => item.severity !== 'info').map((item) => item.robotId),
  )
  return {
    total: input.robots.length,
    online: input.robots.filter((robot) => input.linkFor(robot.id) === 'online').length,
    // Working means a mission is actually running on it, not that it could.
    working: input.robots.filter((robot) => input.runFor(robot.id) !== null).length,
    parked: input.robots.filter((robot) => robot.desiredMode === 'idle').length,
    needsAttention: troubled.size,
  }
}
