/**
 * Where a robot stands before it docks at a station, and whether it fits.
 *
 * A pick or drop step docks: master_control asks Nav2's docking server, which
 * first drives the robot to a *staging pose* a fixed distance behind the
 * station, along the station's heading but facing away from it, and then
 * reverses onto the station itself — rear first, the same way it meets its
 * charger. The operator only ever places the station. When the staging pose
 * lands in a wall the planner refuses it ("no valid path found") and the
 * robot never moves — with nothing on the map saying why. This module is what
 * lets the station editor draw that pose and say so before a mission finds out.
 *
 * The numbers are the robot's (amr_description/config/amr_cfg.yaml):
 * docking_server.simple_charging_dock.staging_x_offset,
 * docking_server.simple_charging_dock.staging_yaw_offset (≈ π, hence the
 * reversed heading) and the costmap footprint. They are written here rather
 * than read from the robot because the editor works without one connected;
 * change them together.
 */
import { type Grid, type MapPlacement } from './map/pgm'

import { normalizeAngle } from './ros/quaternion'

/** staging_x_offset: -1.0 — the staging pose is this far behind the station. */
export const STAGING_DISTANCE_M = 1.0

/** The costmap footprint, [[0.3915, 0.291], ...]: length along the heading, width across it. */
export const ROBOT_FOOTPRINT = { length: 0.783, width: 0.582 } as const

/**
 * Added on every side when checking for walls. The planner checks the bare
 * footprint, but a pose that clears a wall by one cell is one localisation
 * error away from not clearing it.
 */
export const CLEARANCE_MARGIN_M = 0.05

export interface PlanarPose {
  x: number
  y: number
  /** Radians, ROS convention: counter-clockwise from +x. */
  yaw: number
}

/**
 * The staging pose of a station: STAGING_DISTANCE_M behind it, facing away
 * from it. The robot waits here tail first and then backs straight onto the
 * station — staging_yaw_offset is ≈ π and dock_backwards is on.
 */
export function stagingPose(station: PlanarPose): PlanarPose {
  return {
    x: station.x - Math.cos(station.yaw) * STAGING_DISTANCE_M,
    y: station.y - Math.sin(station.yaw) * STAGING_DISTANCE_M,
    yaw: normalizeAngle(station.yaw + Math.PI),
  }
}

/** Corners of a robot-sized rectangle at a pose, in world metres, in drawing order. */
export function footprintCorners(
  pose: PlanarPose,
  length: number = ROBOT_FOOTPRINT.length,
  width: number = ROBOT_FOOTPRINT.width,
): { x: number; y: number }[] {
  const c = Math.cos(pose.yaw)
  const s = Math.sin(pose.yaw)
  const hl = length / 2
  const hw = width / 2
  return [
    [hl, hw],
    [hl, -hw],
    [-hl, -hw],
    [-hl, hw],
  ].map(([dx, dy]) => ({
    x: pose.x + (dx as number) * c - (dy as number) * s,
    y: pose.y + (dx as number) * s + (dy as number) * c,
  }))
}

export type DockingProblem = 'staging-blocked' | 'approach-blocked' | 'staging-unknown' | 'off-map'

export interface DockingCheck {
  staging: PlanarPose
  /** Null when the robot fits at the staging pose and along the way in. */
  problem: DockingProblem | null
  /** Distance from the staging pose's centre to the nearest wall cell, metres; null if none within 2 m. */
  wallDistance: number | null
}

type Material = 'occupied' | 'unknown' | 'free'

/**
 * What a world point falls on, or null off the map. By the image value, the
 * way map_server's trinary mode reads it: dark is occupied, near-white free,
 * anything between unknown — so an edited or rescaled map still classifies.
 */
function cellAt(grid: Grid, placement: MapPlacement, x: number, y: number): Material | null {
  const column = Math.floor((x - placement.originX) / placement.resolution)
  const rowFromBottom = Math.floor((y - placement.originY) / placement.resolution)
  if (column < 0 || column >= grid.width || rowFromBottom < 0 || rowFromBottom >= grid.height) {
    return null
  }
  const value = grid.cells[(grid.height - 1 - rowFromBottom) * grid.width + column]
  if (value === undefined) return null
  if (value <= 50) return 'occupied'
  if (value >= 250) return 'free'
  return 'unknown'
}

/**
 * The worst cell under a rectangle: occupied beats unknown beats free.
 * Sampled at half a cell so no cell is stepped over.
 */
function worstUnder(
  grid: Grid,
  placement: MapPlacement,
  centre: PlanarPose,
  length: number,
  width: number,
): 'occupied' | 'unknown' | 'off-map' | 'free' {
  const step = placement.resolution / 2
  const c = Math.cos(centre.yaw)
  const s = Math.sin(centre.yaw)
  let unknown = false
  for (let a = -length / 2; a <= length / 2 + 1e-9; a += step) {
    for (let b = -width / 2; b <= width / 2 + 1e-9; b += step) {
      const cell = cellAt(grid, placement, centre.x + a * c - b * s, centre.y + a * s + b * c)
      if (cell === null) return 'off-map'
      if (cell === 'occupied') return 'occupied'
      if (cell === 'unknown') unknown = true
    }
  }
  return unknown ? 'unknown' : 'free'
}

function nearestWall(grid: Grid, placement: MapPlacement, at: PlanarPose): number | null {
  const reach = 2.0
  const cells = Math.ceil(reach / placement.resolution)
  let best: number | null = null
  for (let i = -cells; i <= cells; i += 1) {
    for (let j = -cells; j <= cells; j += 1) {
      const x = at.x + i * placement.resolution
      const y = at.y + j * placement.resolution
      if (cellAt(grid, placement, x, y) !== 'occupied') continue
      const d = Math.hypot(x - at.x, y - at.y)
      if (d <= reach && (best === null || d < best)) best = d
    }
  }
  return best
}

/**
 * Whether a robot can stand at a station's staging pose and back straight in.
 *
 * Checks the footprint (plus CLEARANCE_MARGIN_M) at the staging pose, then the
 * band it sweeps on the way to the station. The station's own footprint is not
 * checked: a real dock is meant to be touched.
 */
export function checkDocking(
  grid: Grid,
  placement: MapPlacement,
  station: PlanarPose,
): DockingCheck {
  const staging = stagingPose(station)
  const length = ROBOT_FOOTPRINT.length + 2 * CLEARANCE_MARGIN_M
  const width = ROBOT_FOOTPRINT.width + 2 * CLEARANCE_MARGIN_M
  const wallDistance = nearestWall(grid, placement, staging)

  const atStaging = worstUnder(grid, placement, staging, length, width)
  if (atStaging === 'off-map') return { staging, problem: 'off-map', wallDistance }
  if (atStaging === 'occupied') return { staging, problem: 'staging-blocked', wallDistance }

  // From the staging pose's centre to the station's: the band the robot's
  // body sweeps while it reverses in.
  const band: PlanarPose = {
    x: (staging.x + station.x) / 2,
    y: (staging.y + station.y) / 2,
    yaw: station.yaw,
  }
  const sweep = worstUnder(grid, placement, band, STAGING_DISTANCE_M, width)
  if (sweep === 'occupied' || sweep === 'off-map') {
    return { staging, problem: 'approach-blocked', wallDistance }
  }
  if (atStaging === 'unknown') return { staging, problem: 'staging-unknown', wallDistance }
  return { staging, problem: null, wallDistance }
}

/** One line for the operator: what is wrong, and what to do about it. */
export function dockingProblemText(check: DockingCheck): string | null {
  const away =
    check.wallDistance === null ? '' : ` (${check.wallDistance.toFixed(2)} m from a wall)`
  switch (check.problem) {
    case null:
      return null
    case 'staging-blocked':
      return `The robot does not fit at the docking entry${away}. Turn the heading or move the station so there is room behind it.`
    case 'approach-blocked':
      return 'Something is in the way between the docking entry and the station. Turn the heading or move the station.'
    case 'staging-unknown':
      return 'The docking entry is on unmapped ground. Map that area, or turn the heading towards mapped floor.'
    case 'off-map':
      return 'The docking entry is off the map. Turn the heading or move the station inwards.'
  }
}
