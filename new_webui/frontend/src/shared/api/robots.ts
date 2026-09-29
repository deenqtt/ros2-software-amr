/**
 * Robot registry API.
 *
 * The wire format is snake_case; the application is camelCase. That translation
 * happens here and nowhere else, so a component never has to know which side of
 * the boundary a field came from — and a rename on either side breaks in one
 * file with a type error rather than silently producing `undefined`.
 */

import { api, ApiError } from './client'
import type { DesiredMode, RobotConfig } from '@/domain/types'

/** Exactly what the backend returns. Do not use this shape outside this file. */
interface RobotWire {
  id: string
  name: string
  bridge_url: string
  ros_domain_id: number | null
  camera_url: string | null
  namespace: string
  serial: string | null
  accent: number
  active_map_id: string | null
  desired_mode: DesiredMode
  created_at: string
  updated_at: string
}

/** Fields the client may send on create. The server assigns id and accent. */
interface RobotCreateWire {
  name: string
  bridge_url: string
  ros_domain_id: number | null
  camera_url: string | null
  namespace: string
  serial: string | null
}

/**
 * Partial update.
 *
 * Every key is optional and *omitted is not null*: leaving a key out keeps the
 * stored value, sending null clears it. Only send what actually changed.
 */
type RobotPatchWire = Partial<RobotCreateWire>

/**
 * created_at and updated_at are deliberately dropped: nothing renders them yet,
 * and carrying fields no screen uses invites code that quietly depends on them.
 * Add them to RobotConfig on the day a screen needs one.
 */
export function fromWire(wire: RobotWire): RobotConfig {
  return {
    id: wire.id,
    name: wire.name,
    bridgeUrl: wire.bridge_url,
    rosDomainId: wire.ros_domain_id,
    cameraUrl: wire.camera_url,
    namespace: wire.namespace,
    serial: wire.serial,
    accent: wire.accent,
    activeMapId: wire.active_map_id,
    desiredMode: wire.desired_mode,
  }
}

export type RobotDraft = Pick<RobotConfig, 'name' | 'bridgeUrl' | 'rosDomainId'> &
  Partial<Pick<RobotConfig, 'cameraUrl' | 'namespace' | 'serial'>>

export function toCreateWire(draft: RobotDraft): RobotCreateWire {
  return {
    name: draft.name,
    bridge_url: draft.bridgeUrl,
    ros_domain_id: draft.rosDomainId,
    camera_url: draft.cameraUrl ?? null,
    namespace: draft.namespace ?? '',
    serial: draft.serial ?? null,
  }
}

export function toPatchWire(patch: Partial<RobotDraft>): RobotPatchWire {
  const wire: RobotPatchWire = {}
  // `in` rather than a truthiness check, so an explicit null is sent as null
  // instead of being skipped — clearing a field has to be expressible.
  if ('name' in patch) wire.name = patch.name
  if ('bridgeUrl' in patch) wire.bridge_url = patch.bridgeUrl
  if ('rosDomainId' in patch) wire.ros_domain_id = patch.rosDomainId
  if ('cameraUrl' in patch) wire.camera_url = patch.cameraUrl ?? null
  if ('namespace' in patch) wire.namespace = patch.namespace ?? ''
  if ('serial' in patch) wire.serial = patch.serial ?? null
  return wire
}

/** A uniqueness conflict the server rejected, carrying the offending field. */
export class RobotConflictError extends Error {
  constructor(
    readonly field: 'name' | 'bridge_url' | string,
    message: string,
  ) {
    super(message)
    this.name = 'RobotConflictError'
  }

  /** The client-side field name, for attaching the message to an input. */
  get formField(): 'name' | 'bridgeUrl' | null {
    if (this.field === 'name') return 'name'
    if (this.field === 'bridge_url') return 'bridgeUrl'
    return null
  }
}

interface ConflictDetail {
  field?: string
  message?: string
}

/**
 * FastAPI wraps a raised HTTPException body in `detail`. Recover the structured
 * conflict so the form can point at the field, rather than showing the operator
 * a raw JSON blob.
 */
function asConflict(error: ApiError): RobotConflictError | null {
  if (error.status !== 409) return null
  try {
    const parsed = JSON.parse(error.message) as { detail?: ConflictDetail }
    const detail = parsed.detail
    if (detail?.field) {
      return new RobotConflictError(detail.field, detail.message ?? error.message)
    }
  } catch {
    // Body was not JSON; fall through to a generic conflict.
  }
  return new RobotConflictError('unknown', error.message)
}

async function call<T>(operation: () => Promise<T>): Promise<T> {
  try {
    return await operation()
  } catch (error) {
    if (error instanceof ApiError) {
      const conflict = asConflict(error)
      if (conflict) throw conflict
    }
    throw error
  }
}

/** Point a robot at a map, or clear the assignment with null. */
export async function assignMap(robotId: string, mapId: string | null): Promise<RobotConfig> {
  return fromWire(await api.put<RobotWire>(`/robots/${robotId}/map`, { map_id: mapId }))
}

/**
 * Say what a robot should be doing.
 *
 * Intent, not a command: the agent reconciles towards it and keeps doing so, so
 * a robot that restarts comes back to work rather than coming back idle.
 */
export async function setMode(robotId: string, mode: DesiredMode): Promise<RobotConfig> {
  return fromWire(await api.put<RobotWire>(`/robots/${robotId}/mode`, { desired_mode: mode }))
}

export const robotsApi = {
  async list(): Promise<RobotConfig[]> {
    const rows = await api.get<RobotWire[]>('/robots')
    return rows.map(fromWire)
  },

  async create(draft: RobotDraft): Promise<RobotConfig> {
    return call(async () => fromWire(await api.post<RobotWire>('/robots', toCreateWire(draft))))
  },

  async update(id: string, patch: Partial<RobotDraft>): Promise<RobotConfig> {
    return call(async () =>
      fromWire(await api.patch<RobotWire>(`/robots/${id}`, toPatchWire(patch))),
    )
  },

  async remove(id: string): Promise<void> {
    await api.del<void>(`/robots/${id}`)
  },

  assignMap,
  setMode,
}
