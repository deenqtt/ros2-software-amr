/**
 * Planar TF buffer and composition.
 *
 * Ported from web-ui useROS.js:36-92, where it lived in module-level mutable
 * state shared by the whole app. Here it is a class, so each robot connection
 * owns its own buffer — the precondition for multi-robot.
 */

import { quaternionToYaw, type Quaternion } from './quaternion'

export interface Transform2D {
  tx: number
  ty: number
  yaw: number
}

export interface Pose2D {
  x: number
  y: number
  theta: number
}

/** A single transform as it arrives on /tf or /tf_static. */
export interface TransformStamped {
  header: { frame_id: string }
  child_frame_id: string
  transform: {
    translation: { x: number; y: number; z?: number }
    rotation: Partial<Quaternion>
  }
}

/** Compose two planar transforms: result = parent * child. */
export function composeTransform(parent: Transform2D, child: Transform2D): Transform2D {
  const cos = Math.cos(parent.yaw)
  const sin = Math.sin(parent.yaw)
  return {
    tx: parent.tx + child.tx * cos - child.ty * sin,
    ty: parent.ty + child.tx * sin + child.ty * cos,
    yaw: parent.yaw + child.yaw,
  }
}

const MAP_FRAMES = ['map'] as const
const ODOM_FRAMES = ['odom', 'odom_combined'] as const
const BASE_FRAMES = ['base_footprint', 'base_link'] as const

export class TfBuffer {
  private transforms = new Map<string, Transform2D>()

  private static key(parent: string, child: string): string {
    return `${parent}/${child}`
  }

  /**
   * Frame ids may carry a leading slash (ROS 1 style) or a robot namespace
   * prefix. Strip both so lookups work regardless of how the bridge reports
   * them.
   */
  private static normalizeFrame(frame: string): string {
    const bare = frame.replace(/^\/+/, '')
    const lastSegment = bare.split('/').pop()
    return lastSegment ?? bare
  }

  set(parentFrame: string, childFrame: string, transform: TransformStamped['transform']): void {
    this.transforms.set(
      TfBuffer.key(TfBuffer.normalizeFrame(parentFrame), TfBuffer.normalizeFrame(childFrame)),
      {
        tx: transform.translation.x,
        ty: transform.translation.y,
        yaw: quaternionToYaw(transform.rotation),
      },
    )
  }

  ingest(transforms: readonly TransformStamped[]): void {
    for (const t of transforms) {
      this.set(t.header.frame_id, t.child_frame_id, t.transform)
    }
  }

  get(parentFrame: string, childFrame: string): Transform2D | undefined {
    return this.transforms.get(
      TfBuffer.key(TfBuffer.normalizeFrame(parentFrame), TfBuffer.normalizeFrame(childFrame)),
    )
  }

  private firstOf(
    parents: readonly string[],
    children: readonly string[],
  ): Transform2D | undefined {
    for (const parent of parents) {
      for (const child of children) {
        const found = this.get(parent, child)
        if (found) return found
      }
    }
    return undefined
  }

  /**
   * Resolve map -> base by composing map->odom with odom->base.
   *
   * This is the primary pose source: it works in both SLAM and navigation
   * mode, whereas /amcl_pose only exists under AMCL and /pose only under
   * slam_toolbox. Returns undefined when either link is missing, so the
   * caller can fall back.
   */
  resolveMapToBase(): Pose2D | undefined {
    const mapToOdom = this.firstOf(MAP_FRAMES, ODOM_FRAMES)
    const odomToBase = this.firstOf(ODOM_FRAMES, BASE_FRAMES)
    if (!mapToOdom || !odomToBase) return undefined

    const { tx, ty, yaw } = composeTransform(mapToOdom, odomToBase)
    return { x: tx, y: ty, theta: yaw }
  }

  /** True once map->odom exists, i.e. the TF chain is preferable to /amcl_pose. */
  hasMapToOdom(): boolean {
    return this.firstOf(MAP_FRAMES, ODOM_FRAMES) !== undefined
  }

  /** Clear on disconnect so a new session never reuses stale transforms. */
  clear(): void {
    this.transforms.clear()
  }

  get size(): number {
    return this.transforms.size
  }
}
