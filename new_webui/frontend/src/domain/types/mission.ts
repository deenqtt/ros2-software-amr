/**
 * Missions: a route, and the record of running one.
 *
 * Two shapes, not one. A **mission** is a route — "Pickup A, then Dropoff" —
 * and changes when somebody edits it. A **run** is one execution of that route
 * by one robot, and changes every few seconds while the robot is moving.
 *
 * Looping belongs to the run, not to the route. The same route is sometimes a
 * one-off delivery and sometimes a shift of shuttling; storing `loop` on the
 * route forces two near-identical routes that drift apart the moment one is
 * edited. The previous schema made that mistake.
 */

/** What to do on arrival. `none` is a waypoint merely passed through. */
export const STEP_TASKS = ['none', 'pick', 'drop'] as const
export type StepTask = (typeof STEP_TASKS)[number]

/** MissionPlan.action dest_tasks. Converted at the edge; the app carries words. */
export const STEP_TASK_WIRE: Record<StepTask, number> = { none: 0, pick: 1, drop: 2 }

/**
 * Whether the robot continues by itself.
 *
 * `confirm` waits for /mission_confirm, which means somebody has to be standing
 * there to press it — worth saying out loud before a route like that is set to
 * loop overnight.
 */
export const STEP_CONFIRMS = ['auto', 'confirm'] as const
export type StepConfirm = (typeof STEP_CONFIRMS)[number]

export interface MissionStep {
  id: string
  /** Position in the route, from 1. Assigned by the server from list order. */
  ordinal: number
  /** A stable station id, never a display name — renaming must not orphan it. */
  stationId: string
  task: StepTask
  confirm: StepConfirm
  note: string | null
}

/** What the editor holds while a route is being built. */
export interface StepDraft {
  /** Client-side list key, so a reorder does not remount every row. */
  key: string
  stationId: string
  task: StepTask
  confirm: StepConfirm
  note: string | null
}

export interface Mission {
  id: string
  /** Stations name places in one map's frame, so a route belongs to one map. */
  mapId: string
  name: string
  note: string | null
  steps: MissionStep[]
  createdAt: string
  updatedAt: string
}

/** A list row: everything but the steps, plus how many there are. */
export interface MissionSummary {
  id: string
  mapId: string
  name: string
  note: string | null
  stepCount: number
  createdAt: string
  updatedAt: string
}

export const RUN_MODES = ['once', 'laps', 'forever'] as const
export type RunMode = (typeof RUN_MODES)[number]

/**
 * `stopping` is not terminal: it means "finish this lap, then stop".
 *
 * Halting mid-lap can leave a robot holding a payload it has not delivered, so
 * the ordinary Stop asks for this and the immediate one is the E-STOP.
 */
export const RUN_STATES = ['running', 'stopping', 'done', 'failed', 'canceled'] as const
export type RunState = (typeof RUN_STATES)[number]

export function isRunLive(state: RunState): boolean {
  return state === 'running' || state === 'stopping'
}

export interface MissionRun {
  id: string
  /** Null once the route is deleted; `missionName` keeps the record readable. */
  missionId: string | null
  missionName: string
  robotId: string | null
  mode: RunMode
  lapsTarget: number | null
  /** Owned by the robot's agent. The browser used to hold these and lose them. */
  lap: number
  stepIndex: number
  state: RunState
  detail: string | null
  startedAt: string
  endedAt: string | null
}

export const STEP_TASK_LABEL: Record<StepTask, string> = {
  none: 'Pass through',
  pick: 'Pick',
  drop: 'Drop',
}

export const RUN_MODE_LABEL: Record<RunMode, string> = {
  once: 'Once',
  laps: 'Laps',
  forever: 'Until stopped',
}
