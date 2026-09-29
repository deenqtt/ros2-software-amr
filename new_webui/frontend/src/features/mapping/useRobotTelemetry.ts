/**
 * Live full-tier telemetry for one robot, scoped to a page.
 *
 * Deliberately not a Pinia store. An OccupancyGrid's `data` array runs to
 * millions of entries and Vue would wrap every one of them in a reactive
 * proxy; `shallowRef` hands the message straight to the renderer and lets the
 * canvas decide what changed.
 *
 * It also unsubscribes on unmount, which is what stops a 30 Hz pose stream
 * feeding a component that is no longer on screen.
 */

import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import {
  latestGoal,
  outcomeOf,
  type GoalOutcome,
  type GoalStatusArrayLike,
} from '@/features/robot/goalStatus'
import { useRosPool } from '@/app/ros/pool'
import { parseUrdfFootprint, type Footprint } from '@/domain/ros/urdf'
import { quaternionToYaw } from '@/domain/ros/quaternion'
import type { LaserScan, NavPath, OccupancyGrid, Pose, PoseCloud, Velocity } from '@/domain/types'

export interface AgentStatus {
  mode: 'map' | 'nav' | 'stop' | 'unknown'
  state: 'idle' | 'starting' | 'running' | 'stopping' | 'failed'
  map: string
  mapId: string
  detail: string
  managed: boolean
  backend: string
  teleop: boolean
}

function emptyStatus(): AgentStatus {
  return {
    mode: 'unknown',
    state: 'idle',
    map: '',
    mapId: '',
    detail: '',
    managed: false,
    backend: 'unknown',
    teleop: false,
  }
}

export function useRobotTelemetry(robotId: () => string) {
  const pool = useRosPool()

  const grid = shallowRef<OccupancyGrid | null>(null)
  const scan = shallowRef<LaserScan | null>(null)
  const pose = ref<Pose | null>(null)
  const velocity = ref<Velocity>({ linear: 0, angular: 0 })
  const footprint = shallowRef<Footprint | null>(null)
  /**
   * Where the laser sits relative to the robot's base.
   *
   * A scan is measured from the sensor, not from the robot's centre. Drawing
   * it as if it came from the centre shifts every point by the mounting
   * distance — small on a compact robot, and exactly the kind of small error
   * that makes a map look subtly wrong without anyone being able to say why.
   */
  const sensorOffset = ref<{ x: number; y: number; yaw: number } | null>(null)
  /**
   * Null until the agent speaks. The page must be able to tell "no agent" from
   * "agent says idle": the first means mode switching is unavailable, the
   * second means it is available and nothing is running.
   */
  const agent = ref<AgentStatus | null>(null)

  /**
   * What became of the last navigation goal.
   *
   * Goals leave on /goal_pose, a topic, so nothing here holds an action handle
   * to wait on: without this the UI said "Goal sent" and then never spoke
   * again, whatever the robot went on to do.
   */
  const goalOutcome = ref<GoalOutcome>('none')

  /**
   * The planner's costmap, the route it intends to take, and AMCL's particles.
   *
   * Separate from `grid` because they answer different questions: the map is
   * the building, the costmap is what the planner thinks of it, the plan is
   * what it decided, and the particles are whether it knows where it is.
   */
  const costmap = shallowRef<OccupancyGrid | null>(null)
  const plan = shallowRef<NavPath | null>(null)
  const particles = shallowRef<PoseCloud | null>(null)

  let detach: (() => void) | null = null

  function handle(key: string, message: unknown) {
    switch (key) {
      case 'map':
        grid.value = message as OccupancyGrid
        break
      case 'costmap':
        costmap.value = message as OccupancyGrid
        break
      case 'plan':
        plan.value = message as NavPath
        break
      case 'particleCloud':
        particles.value = message as PoseCloud
        break
      case 'scan': {
        const next = message as LaserScan
        scan.value = next
        const frame = next.header?.frame_id
        if (frame) {
          const client = pool.clientFor(robotId())
          // base_footprint is where the pose is expressed; the scan frame is
          // wherever the sensor was bolted on.
          const mount =
            client?.tf.get('base_footprint', frame) ?? client?.tf.get('base_link', frame)
          sensorOffset.value = mount
            ? { x: mount.tx, y: mount.ty, yaw: mount.yaw }
            : null
        }
        break
      }
      case 'odom': {
        const msg = message as { twist?: { twist?: { linear?: { x?: number }; angular?: { z?: number } } } }
        velocity.value = {
          linear: msg.twist?.twist?.linear?.x ?? 0,
          angular: msg.twist?.twist?.angular?.z ?? 0,
        }
        break
      }
      case 'tf': {
        // The client keeps the buffer; we only read the resolved pose, so a
        // 30 Hz stream costs one composition rather than a re-render per
        // transform.
        const resolved = pool.clientFor(robotId())?.tf.resolveMapToBase()
        if (resolved) pose.value = resolved
        break
      }
      case 'amclPose':
      case 'slamPose': {
        // Fallbacks, used only while the TF chain has not formed.
        const client = pool.clientFor(robotId())
        if (client?.tf.hasMapToOdom()) break
        const msg = message as {
          pose?: { pose?: { position?: { x: number; y: number }; orientation?: object } }
        }
        const position = msg.pose?.pose?.position
        if (!position) break
        pose.value = {
          x: position.x,
          y: position.y,
          theta: quaternionToYaw(msg.pose?.pose?.orientation as never),
        }
        break
      }
      case 'navGoalStatus':
        goalOutcome.value = outcomeOf(latestGoal(message as GoalStatusArrayLike))
        break
      case 'robotDescription': {
        const msg = message as { data?: string }
        if (msg.data) footprint.value = parseUrdfFootprint(msg.data)
        break
      }
      case 'robotModeStatus': {
        const msg = message as { data?: string }
        if (!msg.data) break
        try {
          agent.value = { ...emptyStatus(), ...(JSON.parse(msg.data) as Partial<AgentStatus>) }
        } catch {
          // A malformed status is worth ignoring, not worth crashing a page
          // an operator is steering from.
        }
        break
      }
      default:
        break
    }
  }

  onMounted(() => {
    const client = pool.clientFor(robotId())
    if (client) detach = client.onMessage(handle)
  })

  onBeforeUnmount(() => {
    detach?.()
    detach = null
  })

  /**
   * Forget everything the robot told us.
   *
   * Called when the stack it came from goes away. A grid that stays on screen
   * after SLAM stops looks exactly like a grid that is still being built, and
   * the pose under it is frozen at wherever the robot happened to be — a
   * display that is confidently wrong rather than honestly empty.
   */
  function clear() {
    grid.value = null
    costmap.value = null
    plan.value = null
    particles.value = null
    scan.value = null
    pose.value = null
    velocity.value = { linear: 0, angular: 0 }
    sensorOffset.value = null
    goalOutcome.value = 'none'
  }

  /** Re-attach after the pool rebuilds a client, e.g. its bridge URL changed. */
  function reattach() {
    detach?.()
    const client = pool.clientFor(robotId())
    detach = client ? client.onMessage(handle) : null
  }

  return {
    grid,
    costmap,
    plan,
    particles,
    scan,
    pose,
    velocity,
    footprint,
    sensorOffset,
    agent,
    goalOutcome,
    clear,
    reattach,
  }
}
