/**
 * Zones: areas of a map that change how a robot behaves inside them.
 *
 * Not only keepout. Nav2 enforces zones through *costmap filters*, of which
 * there are exactly three types, and these four kinds cover all of them —
 * `keepout` and `avoid` are both KeepoutFilters, each with its own mask on the
 * robot, and an avoid zone is never lethal.
 *
 * A zone belongs to a map, not to a robot: a speed limit at a blind corner is a
 * property of the building. A robot that must go slower everywhere is a robot
 * setting.
 */

export const ZONE_KINDS = ['keepout', 'avoid', 'speed', 'binary'] as const
export type ZoneKind = (typeof ZONE_KINDS)[number]

/**
 * Metres in the map frame, never pixels.
 *
 * A pixel is a property of the image, and a re-survey at a finer resolution
 * would move every zone while every number still looked right.
 */
export type ZonePoint = [number, number]

/** Two points make a line, and a line encloses nothing. */
export const ZONE_MIN_POINTS = 3
export const ZONE_MAX_POINTS = 500

/**
 * Speed zone limits, m/s. Mirrors SPEED_LIMIT_MAX in the backend's zone schema.
 *
 * The robot encodes a limit in centimetres per second, so 0.01 is the finest
 * step and the slowest limit there is — Nav2 reads a mask value of 0 as "no
 * limit", never as "stop". The top is the robots' MPPI vx_max: Nav2 hands MPPI
 * an absolute limit it does not clamp, and MPPI scales its turning speed by the
 * same ratio, so a limit above it would make a robot turn faster inside the
 * zone meant to slow it down. To forbid an area, draw a keep-out instead.
 */
export const SPEED_STEP = 0.01
export const SPEED_MIN = 0.01
export const SPEED_MAX = 0.6

/** Why a speed limit cannot be saved, or null when it can. Same rule as the backend. */
export function speedLimitProblem(limit: number): string | null {
  if (!Number.isFinite(limit) || limit <= 0 || limit > SPEED_MAX) {
    return `Must be more than 0 and at most ${SPEED_MAX} m/s (the robots' top speed). To keep robots out, use a Keep out zone.`
  }
  return null
}

export interface Zone {
  id: string
  mapId: string
  name: string
  kind: ZoneKind
  polygon: ZonePoint[]
  /** m/s. Only on a speed zone. */
  speedLimit: number | null
  /**
   * 1..99 reluctance. Only on an avoid zone — 100 would be a keepout. The robot
   * maps it onto a cost that is never lethal, so it may still cross.
   */
  avoidCost: number | null
  /** Switched off without being deleted, so it comes back the same shape. */
  enabled: boolean
  note: string | null
  createdAt: string
  updatedAt: string
}

export interface ZoneDraft {
  mapId: string
  name: string
  kind: ZoneKind
  polygon: ZonePoint[]
  speedLimit?: number | null
  avoidCost?: number | null
  enabled?: boolean
  note?: string | null
}

/** Twice the signed area. Used to tell a drawn ring from a degenerate one. */
export function polygonArea(polygon: ZonePoint[]): number {
  let total = 0
  for (let i = 0; i < polygon.length; i += 1) {
    const [x1, y1] = polygon[i] as ZonePoint
    const [x2, y2] = polygon[(i + 1) % polygon.length] as ZonePoint
    total += x1 * y2 - x2 * y1
  }
  return Math.abs(total) / 2
}

/**
 * Whether a point falls inside a polygon.
 *
 * Ray casting, the same rule the robot's rasteriser uses — so what looks
 * selected on screen is what will be filled in the mask.
 */
export function pointInPolygon(polygon: ZonePoint[], x: number, y: number): boolean {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i, i += 1) {
    const [xi, yi] = polygon[i] as ZonePoint
    const [xj, yj] = polygon[j] as ZonePoint
    // Half-open in y, so a vertex exactly on the ray counts once rather than
    // twice — otherwise the test flips on the boundary.
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}
