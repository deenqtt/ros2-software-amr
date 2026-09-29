/**
 * Zone API.
 *
 * Wire format is snake_case; the application is camelCase. The translation
 * lives here and nowhere else.
 */

import { api, ApiError } from './client'
import type { Zone, ZoneDraft, ZoneKind, ZonePoint } from '@/domain/types'

interface ZoneWire {
  id: string
  map_id: string
  name: string
  kind: ZoneKind
  polygon: ZonePoint[]
  speed_limit: number | null
  avoid_cost: number | null
  enabled: boolean
  note: string | null
  created_at: string
  updated_at: string
}

export function fromWire(wire: ZoneWire): Zone {
  return {
    id: wire.id,
    mapId: wire.map_id,
    name: wire.name,
    kind: wire.kind,
    polygon: wire.polygon,
    speedLimit: wire.speed_limit,
    avoidCost: wire.avoid_cost,
    enabled: wire.enabled,
    note: wire.note,
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
  }
}

export type ZonePatch = Partial<Omit<ZoneDraft, 'mapId'>>

/**
 * Only what changed.
 *
 * `kind` and its setting travel together, because the server validates them
 * against the row as it will be *after* the patch — sending a new kind without
 * its setting is how a speed zone ends up with no limit.
 */
function toWire(patch: ZonePatch): Record<string, unknown> {
  const wire: Record<string, unknown> = {}
  if ('name' in patch) wire.name = patch.name
  if ('kind' in patch) wire.kind = patch.kind
  if ('polygon' in patch) wire.polygon = patch.polygon
  if ('speedLimit' in patch) wire.speed_limit = patch.speedLimit ?? null
  if ('avoidCost' in patch) wire.avoid_cost = patch.avoidCost ?? null
  if ('enabled' in patch) wire.enabled = patch.enabled
  if ('note' in patch) wire.note = patch.note ?? null
  return wire
}

/** A name already used by another zone on the same map. */
export class ZoneNameTakenError extends Error {
  constructor(readonly requested: string) {
    super(`This map already has a zone called "${requested}"`)
    this.name = 'ZoneNameTakenError'
  }
}

function asNameTaken(error: ApiError, attempted: string): ZoneNameTakenError | null {
  if (error.status !== 409) return null
  try {
    const parsed = JSON.parse(error.message) as { detail?: { field?: string } }
    if (parsed.detail?.field === 'name') return new ZoneNameTakenError(attempted)
  } catch {
    // Body was not JSON; fall through to a generic conflict.
  }
  return new ZoneNameTakenError(attempted)
}

export const zonesApi = {
  async list(mapId?: string, kind?: ZoneKind): Promise<Zone[]> {
    const query = new URLSearchParams()
    if (mapId) query.set('map_id', mapId)
    if (kind) query.set('kind', kind)
    const suffix = query.toString() ? `?${query}` : ''
    const rows = await api.get<ZoneWire[]>(`/zones${suffix}`)
    return rows.map(fromWire)
  },

  async create(draft: ZoneDraft): Promise<Zone> {
    const body = {
      map_id: draft.mapId,
      name: draft.name,
      kind: draft.kind,
      polygon: draft.polygon,
      // Omitted entirely rather than sent as null: the server refuses a setting
      // the kind has no use for, and a null is still a value that was sent.
      ...(draft.kind === 'speed' ? { speed_limit: draft.speedLimit } : {}),
      ...(draft.kind === 'avoid' ? { avoid_cost: draft.avoidCost } : {}),
      enabled: draft.enabled ?? true,
      note: draft.note ?? null,
    }
    try {
      return fromWire(await api.post<ZoneWire>('/zones', body))
    } catch (error) {
      if (error instanceof ApiError) {
        const taken = asNameTaken(error, draft.name)
        if (taken) throw taken
      }
      throw error
    }
  },

  async update(id: string, patch: ZonePatch): Promise<Zone> {
    try {
      return fromWire(await api.patch<ZoneWire>(`/zones/${id}`, toWire(patch)))
    } catch (error) {
      if (error instanceof ApiError && patch.name !== undefined) {
        const taken = asNameTaken(error, patch.name)
        if (taken) throw taken
      }
      throw error
    }
  },

  async remove(id: string): Promise<void> {
    await api.del<void>(`/zones/${id}`)
  },
}
