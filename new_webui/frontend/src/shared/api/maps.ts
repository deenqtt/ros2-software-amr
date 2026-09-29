/**
 * Map registry API.
 *
 * Wire format is snake_case; the application is camelCase. The translation
 * lives here and nowhere else.
 */

import { api, ApiError } from './client'
import { config } from '@/app/config'
import type { MapRecord } from '@/domain/types'

interface MapWire {
  id: string
  name: string
  version: number
  content_hash: string
  yaml_file: string
  image_file: string
  image_bytes: number
  resolution: number | null
  width: number | null
  height: number | null
  origin_x: number | null
  origin_y: number | null
  origin_yaw: number | null
  negate: number | null
  occupied_thresh: number | null
  free_thresh: number | null
  created_by_robot_id: string | null
  note: string | null
  created_at: string
}

export function fromWire(wire: MapWire): MapRecord {
  return {
    id: wire.id,
    name: wire.name,
    version: wire.version,
    contentHash: wire.content_hash,
    yamlFile: wire.yaml_file,
    imageFile: wire.image_file,
    imageBytes: wire.image_bytes,
    resolution: wire.resolution,
    width: wire.width,
    height: wire.height,
    originX: wire.origin_x,
    originY: wire.origin_y,
    originYaw: wire.origin_yaw,
    negate: wire.negate,
    occupiedThresh: wire.occupied_thresh,
    freeThresh: wire.free_thresh,
    createdByRobotId: wire.created_by_robot_id,
    note: wire.note,
    createdAt: wire.created_at,
  }
}

/**
 * A delete the server refused because robots are still assigned.
 *
 * Carries their names, because "cannot delete" without saying who is holding
 * it leaves the operator with nowhere to go.
 */
export class MapInUseError extends Error {
  constructor(
    readonly robots: string[],
    message: string,
  ) {
    super(message)
    this.name = 'MapInUseError'
  }
}

/** A rename the server refused because another lineage owns that name. */
export class MapNameTakenError extends Error {
  constructor(readonly requested: string) {
    super(`A map named "${requested}" already exists`)
    this.name = 'MapNameTakenError'
  }
}

interface InUseDetail {
  message?: string
  robots?: string[]
}

function asInUse(error: ApiError): MapInUseError | null {
  if (error.status !== 409) return null
  try {
    const parsed = JSON.parse(error.message) as { detail?: InUseDetail }
    const detail = parsed.detail
    if (detail?.robots) {
      return new MapInUseError(detail.robots, detail.message ?? error.message)
    }
  } catch {
    // Body was not JSON; fall through to a generic conflict.
  }
  return new MapInUseError([], error.message)
}

export interface MapUpload {
  name: string
  yamlFile: File
  imageFile: File
  robotId?: string | null
  note?: string | null
}

export const mapsApi = {
  async list(): Promise<MapRecord[]> {
    const rows = await api.get<MapWire[]>('/maps')
    return rows.map(fromWire)
  },

  async upload(upload: MapUpload): Promise<MapRecord> {
    const form = new FormData()
    form.append('name', upload.name)
    form.append('yaml_file', upload.yamlFile)
    form.append('image_file', upload.imageFile)
    if (upload.robotId) form.append('robot_id', upload.robotId)
    if (upload.note) form.append('note', upload.note)
    // Content-Type is left to the browser: it has to add the multipart
    // boundary, and setting the header by hand omits it.
    return fromWire(await api.upload<MapWire>('/maps', form))
  },

  /**
   * Replace a version's contents, keeping its id, name and version number.
   *
   * The alternative to publishing a new version. Assignments survive because the
   * id does not move — which is exactly why it is the riskier of the two: a robot
   * keeps pointing at this map while what the map says has changed.
   */
  async replaceImage(id: string, payload: Omit<MapUpload, 'name' | 'robotId'>): Promise<MapRecord> {
    const form = new FormData()
    form.append('yaml_file', payload.yamlFile)
    form.append('image_file', payload.imageFile)
    if (payload.note) form.append('note', payload.note)
    return fromWire(await api.uploadPut<MapWire>(`/maps/${id}/image`, form))
  },

  /**
   * Rename a map.
   *
   * Renames every version sharing the name — the server treats the name as the
   * lineage key — so the caller must reload rather than patching one row.
   */
  async rename(id: string, name: string): Promise<MapRecord> {
    try {
      return fromWire(await api.patch<MapWire>(`/maps/${id}`, { name }))
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        throw new MapNameTakenError(name)
      }
      throw error
    }
  },

  async remove(id: string): Promise<void> {
    try {
      await api.del<void>(`/maps/${id}`)
    } catch (error) {
      if (error instanceof ApiError) {
        const inUse = asInUse(error)
        if (inUse) throw inUse
      }
      throw error
    }
  },

  /**
   * The stored bytes of one half of a pair.
   *
   * The editor needs both: the image to decode and paint, and the yaml *verbatim*
   * so it can be sent back untouched. Rebuilding the yaml from MapRecord would
   * silently drop keys the record does not carry — `mode: trinary` among them.
   */
  fetchFile(id: string, which: 'yaml' | 'image'): Promise<Uint8Array> {
    return api.bytes(`/maps/${id}/files/${which}`)
  },

  /** Direct link to one half of a pair. Used by the robot, not the operator. */
  fileUrl(id: string, which: 'yaml' | 'image'): string {
    return `${config.apiBaseUrl}/maps/${id}/files/${which}`
  },

  /**
   * Both halves as a zip — what the Download button points at.
   *
   * The yaml names its image, so handing over either half alone produces a file
   * that looks like a map and will not load.
   */
  archiveUrl(id: string): string {
    return `${config.apiBaseUrl}/maps/${id}/archive`
  },
}
