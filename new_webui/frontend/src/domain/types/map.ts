/**
 * Map registry types.
 *
 * A map here is an immutable, versioned artefact. Saving the same name again
 * creates the next version rather than overwriting: stations store coordinates
 * in a specific map frame, so replacing a map's contents silently invalidates
 * every station attached to it — on every robot still running the old one.
 */

export interface MapRecord {
  id: string
  /** Shared across versions: "Warehouse A" v1, v2, v3. */
  name: string
  version: number
  /** sha256 of the image. What a robot compares its cache against. */
  contentHash: string
  /** Filenames inside the map's directory; a cache must match them exactly. */
  yamlFile: string
  imageFile: string
  imageBytes: number
  resolution: number | null
  width: number | null
  height: number | null
  originX: number | null
  originY: number | null
  originYaw: number | null
  negate: number | null
  occupiedThresh: number | null
  freeThresh: number | null
  /** Which robot surveyed it. Null once that robot is retired. */
  createdByRobotId: string | null
  note: string | null
  createdAt: string
}

export interface Point2D {
  x: number
  y: number
}

export interface KeepoutZone {
  id: number
  mapId: number
  name: string
  polygon: Point2D[]
}

/** nav_msgs/msg/OccupancyGrid, as delivered by rosbridge. */
export interface OccupancyGrid {
  info: {
    width: number
    height: number
    resolution: number
    origin: {
      position: { x: number; y: number; z: number }
      orientation: { x: number; y: number; z: number; w: number }
    }
  }
  data: number[] | Int8Array
}

export interface LaserScan {
  /** Which frame the ranges are measured from — usually a mast, not the base. */
  header?: { frame_id?: string }
  angle_min: number
  angle_max: number
  angle_increment: number
  range_min: number
  range_max: number
  ranges: number[]
}

/**
 * nav_msgs/msg/Path — the route the planner intends to drive.
 *
 * Worth drawing on its own: without it, "the robot is thinking" and "the robot
 * is stuck" look identical on screen.
 */
export interface NavPath {
  header?: { frame_id?: string }
  poses: { pose: { position: { x: number; y: number } } }[]
}

/**
 * geometry_msgs/msg/PoseArray — AMCL's particle cloud.
 *
 * How localisation health is actually read. A tight cluster means the robot is
 * confident about where it is; a cloud spread across the map means it is lost —
 * and a lost robot looks exactly like a stopped one until you can see this.
 */
export interface PoseCloud {
  header?: { frame_id?: string }
  poses: {
    position: { x: number; y: number }
    orientation: { x: number; y: number; z: number; w: number }
  }[]
}

/** Physical extent in metres, or null when the grid size is unknown. */
export function mapExtentMetres(map: MapRecord): { width: number; height: number } | null {
  if (map.resolution === null || map.width === null || map.height === null) return null
  return { width: map.width * map.resolution, height: map.height * map.resolution }
}
