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

/**
 * The band of high, non-lethal cost the robot lays round every keep-out, in
 * metres. Mirrors keepout_halo_width in amr_agent/zone_raster.py: costmap
 * filters are not inflated, so without it the robot's body clips into a
 * keep-out and gets stuck there.
 */
export const KEEPOUT_HALO_M = 0.6

/** The robot footprint's circumscribed radius: 0.783 m x 0.582 m, from the centre. */
export const ROBOT_RADIUS_M = 0.49

/** Distance from a point to the polygon's outline, or 0 when the point is inside it. */
export function distanceToPolygon(polygon: ZonePoint[], x: number, y: number): number {
  if (polygon.length >= ZONE_MIN_POINTS && pointInPolygon(polygon, x, y)) return 0
  let best = Infinity
  for (let i = 0; i < polygon.length; i += 1) {
    const [ax, ay] = polygon[i] as ZonePoint
    const [bx, by] = polygon[(i + 1) % polygon.length] as ZonePoint
    const dx = bx - ax
    const dy = by - ay
    const lengthSq = dx * dx + dy * dy
    const t =
      lengthSq === 0 ? 0 : Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / lengthSq))
    best = Math.min(best, Math.hypot(x - (ax + t * dx), y - (ay + t * dy)))
  }
  return best
}

/**
 * The places a keep-out would crowd: a robot standing there, body and all,
 * would touch the keep-out or its halo.
 *
 * Not a reason to refuse the zone — a keep-out right beside a dock can be
 * exactly what was meant — but a robot sent to such a station may be unable to
 * reach it, or to leave it, and the operator should know before saving.
 */
export function keepoutCrowds<T extends { x: number; y: number }>(
  polygon: ZonePoint[],
  places: T[],
  clearance: number = KEEPOUT_HALO_M + ROBOT_RADIUS_M,
): T[] {
  if (polygon.length < ZONE_MIN_POINTS) return []
  return places.filter((place) => distanceToPolygon(polygon, place.x, place.y) < clearance)
}

/**
 * The active keep-out a point lies in, if any.
 *
 * A goal there can never be reached: the planner treats a keep-out as lethal,
 * and Nav2 then retries its recoveries against an area that will not move.
 * The robot's agent and the backend's relay refuse such a goal too; this is
 * so the operator hears why at once, in words, instead of watching a robot
 * try for minutes.
 */
export function keepoutAt(
  zones: Pick<Zone, 'kind' | 'enabled' | 'polygon' | 'name'>[],
  x: number,
  y: number,
): Pick<Zone, 'kind' | 'enabled' | 'polygon' | 'name'> | undefined {
  return zones.find(
    (zone) =>
      zone.kind === 'keepout' &&
      zone.enabled &&
      zone.polygon.length >= ZONE_MIN_POINTS &&
      pointInPolygon(zone.polygon, x, y),
  )
}
