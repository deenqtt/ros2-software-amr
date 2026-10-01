/**
 * Mission and run API.
 *
 * Wire format is snake_case; the application is camelCase. The translation
 * lives here and nowhere else.
 */

import { api, ApiError } from './client'
import type {
  Mission,
  MissionRun,
  MissionStep,
  MissionSummary,
  RunMode,
  RunState,
  StepConfirm,
  StepDraft,
  StepTask,
} from '@/domain/types'

interface StepWire {
  id: string
  ordinal: number
  station_id: string
  task: StepTask
  confirm: StepConfirm
  note: string | null
}

interface MissionWire {
  id: string
  map_id: string
  name: string
  note: string | null
  steps: StepWire[]
  created_at: string
  updated_at: string
}

interface SummaryWire {
  id: string
  map_id: string
  name: string
  note: string | null
  step_count: number
  station_ids?: string[]
  created_at: string
  updated_at: string
}

interface RunWire {
  id: string
  mission_id: string | null
  mission_name: string
  robot_id: string | null
  mode: RunMode
  laps_target: number | null
  lap: number
  step_index: number
  // Optional on the wire: a backend from before migration 007 does not send them.
  reached_lap?: number | null
  reached_index?: number | null
  reached_at?: string | null
  state: RunState
  detail: string | null
  started_at: string
  ended_at: string | null
}

function stepFromWire(wire: StepWire): MissionStep {
  return {
    id: wire.id,
    ordinal: wire.ordinal,
    stationId: wire.station_id,
    task: wire.task,
    confirm: wire.confirm,
    note: wire.note,
  }
}

export function missionFromWire(wire: MissionWire): Mission {
  return {
    id: wire.id,
    mapId: wire.map_id,
    name: wire.name,
    note: wire.note,
    steps: wire.steps.map(stepFromWire),
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
  }
}

export function summaryFromWire(wire: SummaryWire): MissionSummary {
  return {
    id: wire.id,
    mapId: wire.map_id,
    name: wire.name,
    note: wire.note,
    stepCount: wire.step_count,
    // Optional on the wire so an older backend still lists, just without a preview.
    stationIds: wire.station_ids ?? [],
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
  }
}

export function runFromWire(wire: RunWire): MissionRun {
  return {
    id: wire.id,
    missionId: wire.mission_id,
    missionName: wire.mission_name,
    robotId: wire.robot_id,
    mode: wire.mode,
    lapsTarget: wire.laps_target,
    lap: wire.lap,
    stepIndex: wire.step_index,
    reachedLap: wire.reached_lap ?? null,
    reachedIndex: wire.reached_index ?? null,
    reachedAt: wire.reached_at ?? null,
    state: wire.state,
    detail: wire.detail,
    startedAt: wire.started_at,
    endedAt: wire.ended_at,
  }
}

function stepsToWire(steps: StepDraft[]) {
  // `key` is a client-side list identity and must not be sent: the server
  // forbids unknown fields, which is what stops a typo becoming a silent no-op.
  return steps.map((step) => ({
    station_id: step.stationId,
    task: step.task,
    confirm: step.confirm,
    note: step.note,
  }))
}

/** A name already used by another mission on the same map. */
export class MissionNameTakenError extends Error {
  constructor(readonly requested: string) {
    super(`This map already has a mission called "${requested}"`)
    this.name = 'MissionNameTakenError'
  }
}

/** A dispatch the server refused because the robot is already working. */
export class RobotBusyError extends Error {
  constructor(readonly mission: string) {
    super(`This robot is already running "${mission}"`)
    this.name = 'RobotBusyError'
  }
}

/** A dispatch refused because the robot is not on the mission's map. */
export class WrongMapError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'WrongMapError'
  }
}

interface ConflictDetail {
  field?: string
  message?: string
  mission?: string
  expected_map_id?: string
}

function conflictDetail(error: ApiError): ConflictDetail | null {
  if (error.status !== 409) return null
  try {
    return (JSON.parse(error.message) as { detail?: ConflictDetail }).detail ?? null
  } catch {
    return null
  }
}

export interface MissionDraft {
  mapId: string
  name: string
  note?: string | null
  steps: StepDraft[]
}

export const missionsApi = {
  async list(mapId?: string): Promise<MissionSummary[]> {
    const query = mapId ? `?map_id=${encodeURIComponent(mapId)}` : ''
    const rows = await api.get<SummaryWire[]>(`/missions${query}`)
    return rows.map(summaryFromWire)
  },

  async get(id: string): Promise<Mission> {
    return missionFromWire(await api.get<MissionWire>(`/missions/${id}`))
  },

  async create(draft: MissionDraft): Promise<Mission> {
    const body = {
      map_id: draft.mapId,
      name: draft.name,
      note: draft.note ?? null,
      steps: stepsToWire(draft.steps),
    }
    try {
      return missionFromWire(await api.post<MissionWire>('/missions', body))
    } catch (error) {
      if (error instanceof ApiError && conflictDetail(error)?.field === 'name') {
        throw new MissionNameTakenError(draft.name)
      }
      throw error
    }
  },

  /** Omitted keeps; `steps` is all-or-nothing, because it is an order. */
  async update(
    id: string,
    patch: { name?: string; note?: string | null; steps?: StepDraft[] },
  ): Promise<Mission> {
    const body: Record<string, unknown> = {}
    if ('name' in patch) body.name = patch.name
    if ('note' in patch) body.note = patch.note ?? null
    if (patch.steps) body.steps = stepsToWire(patch.steps)
    try {
      return missionFromWire(await api.patch<MissionWire>(`/missions/${id}`, body))
    } catch (error) {
      if (error instanceof ApiError && conflictDetail(error)?.field === 'name') {
        throw new MissionNameTakenError(patch.name ?? '')
      }
      throw error
    }
  },

  async remove(id: string): Promise<void> {
    await api.del<void>(`/missions/${id}`)
  },
}

export interface DispatchDraft {
  missionId: string
  robotId: string
  mode: RunMode
  lapsTarget?: number | null
}

export const runsApi = {
  async list(limit = 50): Promise<MissionRun[]> {
    const rows = await api.get<RunWire[]>(`/runs?limit=${limit}`)
    return rows.map(runFromWire)
  },

  async start(draft: DispatchDraft): Promise<MissionRun> {
    const body = {
      mission_id: draft.missionId,
      robot_id: draft.robotId,
      mode: draft.mode,
      // Only sent for `laps`: the server refuses a count without a looping mode,
      // and a null would be a count that is not a count.
      ...(draft.mode === 'laps' ? { laps_target: draft.lapsTarget } : {}),
    }
    try {
      return runFromWire(await api.post<RunWire>('/runs', body))
    } catch (error) {
      if (error instanceof ApiError) {
        const detail = conflictDetail(error)
        if (detail?.mission) throw new RobotBusyError(detail.mission)
        if (detail?.expected_map_id) throw new WrongMapError(detail.message ?? error.message)
      }
      throw error
    }
  },

  /**
   * Ask a run to finish the lap it is on and stop.
   *
   * Not a terminal state: halting mid-lap can leave a robot holding a payload
   * it has not delivered. The immediate stop is the E-STOP.
   */
  async stopAfterLap(id: string): Promise<MissionRun> {
    return runFromWire(await api.patch<RunWire>(`/runs/${id}`, { state: 'stopping' }))
  },

  async cancel(id: string): Promise<MissionRun> {
    return runFromWire(
      await api.patch<RunWire>(`/runs/${id}`, {
        state: 'canceled',
        detail: 'canceled by the operator',
      }),
    )
  },
}
