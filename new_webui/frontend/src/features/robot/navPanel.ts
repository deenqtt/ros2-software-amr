/**
 * Layout and one-line summary helpers for the robot Navigation page's status
 * panel. Pure so the per-screen behaviour can be unit tested without CSS.
 */
import type { Screen } from '@/stores/ui'
import type { GoalOutcome } from './goalStatus'
import { stallLabel } from './stall'

export type PanelPlacement = 'docked' | 'strip' | 'overlay' | 'sheet'

/**
 * Where the status panel lives. On a phone it is always a bottom sheet (its
 * peek bar stays visible, so "open" only expands it); on a tablet an open panel
 * floats over the map instead of docking, so the map is never crushed.
 */
export function panelPlacement(screen: Screen, open: boolean): PanelPlacement {
  if (screen === 'phone') return 'sheet'
  if (screen === 'tablet') return open ? 'overlay' : 'strip'
  return open ? 'docked' : 'strip'
}

export type VerdictTone = 'ok' | 'warn' | 'fault' | 'muted' | 'primary'

export interface NavVerdictRun {
  missionName: string
  /** 0-based. */
  stepIndex: number
  stepCount: number | null
  stopName: string | null
}

export interface NavVerdictInput {
  online: boolean
  muted: boolean
  attempt: number
  hasMap: boolean
  run: NavVerdictRun | null
  /** 'nav' | 'map' | anything else (e.g. 'unknown'). */
  agentMode: string
  /** 'running' | 'failed' | 'starting' | 'waiting' | ... */
  agentState: string
  poseSet: boolean
  goalOutcome: GoalOutcome
  goalBoxedIn: boolean
  stalled: boolean
  stillFor: number
}

export interface NavVerdict {
  text: string
  tone: VerdictTone
}

/**
 * The phone peek bar's one line. Checks are ordered by what blocks the
 * operator first: no point mentioning the pose while the link is down.
 */
export function navVerdict(input: NavVerdictInput): NavVerdict {
  if (input.muted) return { text: 'Monitoring is off', tone: 'muted' }
  if (!input.online) {
    return {
      text: input.attempt > 0 ? 'Not connected, reconnecting' : 'Not connected',
      tone: 'warn',
    }
  }
  if (!input.hasMap) return { text: 'No map assigned', tone: 'warn' }

  const run = input.run
  if (run !== null) {
    let text = `${run.missionName} · step ${run.stepIndex + 1}`
    if (run.stepCount !== null) text += `/${run.stepCount}`
    if (run.stopName) text += ` → ${run.stopName}`
    return { text, tone: 'primary' }
  }

  if (!(input.agentMode === 'nav' && input.agentState === 'running')) {
    const name = input.agentMode === 'nav' ? 'Nav2' : input.agentMode === 'map' ? 'SLAM' : null
    if (name === null) return { text: 'Stopped', tone: 'muted' }
    // SLAM running still warns: this page cannot send goals while mapping.
    return {
      text: `${name} ${input.agentState}`,
      tone: input.agentState === 'failed' ? 'fault' : 'warn',
    }
  }

  if (input.goalOutcome === 'failed') {
    return { text: input.goalBoxedIn ? 'Goal failed · boxed in' : 'Goal failed', tone: 'fault' }
  }
  if (input.stalled) return { text: stallLabel(input.stillFor), tone: 'warn' }
  if (!input.poseSet) return { text: 'Set the pose to start', tone: 'warn' }
  if (input.goalOutcome === 'running') return { text: 'Driving to goal', tone: 'ok' }
  return { text: 'Ready', tone: 'ok' }
}

export type PeekAction = 'stopAfterLap' | 'openMission'

/**
 * The single mission button the peek bar shows. A run in progress can be asked
 * to stop even while the robot link is down, since the run lives on the
 * backend; starting one needs a live robot.
 */
export function peekAction(input: { online: boolean; runState: string | null }): PeekAction | null {
  if (input.runState !== null) return input.runState === 'stopping' ? null : 'stopAfterLap'
  return input.online ? 'openMission' : null
}

export const VERDICT_TONE_CLASS: Record<VerdictTone, string> = {
  ok: 'text-status-ok',
  warn: 'text-status-warn',
  fault: 'text-status-fault',
  muted: 'text-muted',
  primary: 'text-primary',
}
