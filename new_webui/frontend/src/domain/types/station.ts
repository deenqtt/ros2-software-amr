/**
 * Stations: named poses a robot can be sent to.
 *
 * A station belongs to a *map*, not to a robot. Its coordinates are metres in
 * that map's frame, so the same numbers name a different physical place in any
 * other map, and two robots working one site share its stations because they
 * share its map.
 *
 * Coordinates are never stored in pixels. A pixel is a property of the image,
 * and the image can be re-surveyed at a different resolution while the shelf
 * stays exactly where it is.
 */

/**
 * The four kinds the robot understands.
 *
 * Carried as text everywhere in the application and converted to the wire
 * number only at the edge — a registry that stores `2` is one nobody can read.
 */
export const STATION_TYPES = ['pick', 'drop', 'pick_drop', 'charging'] as const

export type StationType = (typeof STATION_TYPES)[number]

/** custom_interfaces/srv/StationConfig.srv: 0=Pick, 1=Drop, 2=Pick&Drop, 3=Charging. */
export const STATION_TYPE_WIRE: Record<StationType, number> = {
  pick: 0,
  drop: 1,
  pick_drop: 2,
  charging: 3,
}

/** StationConfig.srv action field: 0 = delete, 1 = save. */
export const STATION_ACTION = {
  delete: 0,
  save: 1,
} as const

export interface Station {
  /**
   * Stable and immutable.
   *
   * The old UI passed the display *name* as the robot's station key, so
   * renaming a dock registered a second station and orphaned the first
   * (audit section 1.4). The name is free to change; this is not.
   */
  id: string
  /** The map version this pose is expressed in. */
  mapId: string
  name: string
  type: StationType
  /** Metres in the map frame. */
  x: number
  y: number
  /** Approach heading in radians. A dock reached from the wrong side is not reached. */
  yaw: number
  note: string | null
  /** Set when the pose was captured by driving a robot there. */
  taughtByRobotId: string | null
  createdAt: string
  updatedAt: string
}

/** What the operator fills in; the server assigns id and timestamps. */
export interface StationDraft {
  mapId: string
  name: string
  type: StationType
  x: number
  y: number
  yaw: number
  note?: string | null
  taughtByRobotId?: string | null
}

export const STATION_TYPE_LABEL: Record<StationType, string> = {
  pick: 'Pick',
  drop: 'Drop',
  pick_drop: 'Pick & drop',
  charging: 'Charging',
}
