/**
 * Zones: areas of a map that change how a robot behaves inside them.
 *
 * Not only keepout. Nav2 enforces zones through *costmap filters*, of which
 * there are exactly three, and these four kinds cover all of them — `keepout`
 * and `avoid` share a filter and differ only in the value written into its
 * mask.
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

/** Nav2 reads a mask value of 0 as "no limit", so this is the slowest expressible. */
export const SPEED_STEP = 0.1
export const SPEED_MIN = 0.1
export const SPEED_MAX = 10

export interface Zone {
  id: string
  mapId: string
  name: string
  kind: ZoneKind
  polygon: ZonePoint[]
  /** m/s. Only on a speed zone. */
  speedLimit: number | null
  /** 1..99 reluctance. Only on an avoid zone — 100 would be a keepout. */
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
