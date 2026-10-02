/**
 * Station registry API.
 *
 * Wire format is snake_case; the application is camelCase. The translation
 * lives here and nowhere else.
 */

import { api, ApiError } from './client'
import type { Station, StationDraft, StationType } from '@/domain/types'

interface StationWire {
  id: string
  map_id: string
  name: string
  type: StationType
  x: number
  y: number
  yaw: number
  note: string | null
  taught_by_robot_id: string | null
  created_at: string
  updated_at: string
}

export function fromWire(wire: StationWire): Station {
  return {
    id: wire.id,
    mapId: wire.map_id,
    name: wire.name,
    type: wire.type,
    x: wire.x,
    y: wire.y,
    yaw: wire.yaw,
    note: wire.note,
    taughtByRobotId: wire.taught_by_robot_id,
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
  }
}

/**
 * A partial update.
 *
 * Omitted is not null: a key left out keeps the stored value, which is what lets
 * a dragged marker send x and y alone rather than a whole record that might
 * carry a name the operator has since edited in another tab.
 */
export type StationPatch = Partial<Omit<StationDraft, 'mapId'>>

function toPatchWire(patch: StationPatch): Record<string, unknown> {
  const wire: Record<string, unknown> = {}
  // `in` rather than a truthiness check: 0 is a valid coordinate and null is a
  // meaningful value for note.
  if ('name' in patch) wire.name = patch.name
  if ('type' in patch) wire.type = patch.type
  if ('x' in patch) wire.x = patch.x
  if ('y' in patch) wire.y = patch.y
  if ('yaw' in patch) wire.yaw = patch.yaw
  if ('note' in patch) wire.note = patch.note ?? null
  if ('taughtByRobotId' in patch) wire.taught_by_robot_id = patch.taughtByRobotId ?? null
  return wire
}

/** A name already used by another station on the same map. */
export class StationNameTakenError extends Error {
  constructor(readonly requested: string) {
    super(`This map already has a station called "${requested}"`)
    this.name = 'StationNameTakenError'
  }
}

/**
 * A delete the server refused because mission steps still name the station.
 *
 * Carries the mission names, so the refusal can say which routes to edit
 * rather than showing the raw 409 body.
 */
export class StationInUseError extends Error {
  constructor(
    readonly missions: string[],
    message: string,
  ) {
    super(message)
    this.name = 'StationInUseError'
  }
}

function asInUse(error: ApiError): StationInUseError | null {
  if (error.status !== 409) return null
  try {
    const parsed = JSON.parse(error.message) as {
      detail?: { message?: string; missions?: string[] }
    }
    const missions = parsed.detail?.missions ?? []
    return new StationInUseError(missions, parsed.detail?.message ?? 'Station is in use')
  } catch {
    return new StationInUseError([], 'Station is in use')
  }
}

interface ConflictDetail {
  field?: string
  message?: string
}

function asNameTaken(error: ApiError, attempted: string): StationNameTakenError | null {
  if (error.status !== 409) return null
  try {
    const parsed = JSON.parse(error.message) as { detail?: ConflictDetail }
    if (parsed.detail?.field === 'name') {
      return new StationNameTakenError(attempted)
    }
  } catch {
    // Body was not JSON; fall through to a generic conflict.
  }
  return new StationNameTakenError(attempted)
}

export const stationsApi = {
  /** Every station on one map, or the whole registry when mapId is omitted. */
  async list(mapId?: string): Promise<Station[]> {
    const query = mapId ? `?map_id=${encodeURIComponent(mapId)}` : ''
    const rows = await api.get<StationWire[]>(`/stations${query}`)
    return rows.map(fromWire)
  },

  async create(draft: StationDraft): Promise<Station> {
    const body = {
      map_id: draft.mapId,
      name: draft.name,
      type: draft.type,
      x: draft.x,
      y: draft.y,
      yaw: draft.yaw,
      note: draft.note ?? null,
      taught_by_robot_id: draft.taughtByRobotId ?? null,
    }
    try {
      return fromWire(await api.post<StationWire>('/stations', body))
    } catch (error) {
      if (error instanceof ApiError) {
        const taken = asNameTaken(error, draft.name)
        if (taken) throw taken
      }
      throw error
    }
  },

  async update(id: string, patch: StationPatch): Promise<Station> {
    try {
      return fromWire(await api.patch<StationWire>(`/stations/${id}`, toPatchWire(patch)))
    } catch (error) {
      if (error instanceof ApiError && patch.name !== undefined) {
        const taken = asNameTaken(error, patch.name)
        if (taken) throw taken
      }
      throw error
    }
  },

  async remove(id: string): Promise<void> {
    try {
      await api.del<void>(`/stations/${id}`)
    } catch (error) {
      throw (error instanceof ApiError && asInUse(error)) || error
    }
  },

  /**
   * How many stations a map carries.
   *
   * Deleting a map cascades to its stations, so a delete confirmation has to be
   * able to say what else goes with it.
   */
  async countForMap(mapId: string): Promise<number> {
    const body = await api.get<{ stations: number }>(`/maps/${mapId}/stations/count`)
    return body.stations
  },
}
