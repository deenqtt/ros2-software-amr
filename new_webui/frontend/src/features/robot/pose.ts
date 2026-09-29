/**
 * Building the two pose messages this UI publishes.
 *
 * Kept out of the view because both have a detail that is easy to get wrong and
 * expensive to debug — a robot that silently refuses to localise looks like a
 * broken robot rather than a malformed message.
 */

/** A yaw as the quaternion ROS carries. Only z and w are ever non-zero in 2D. */
export function yawToQuaternion(yaw: number) {
  return { x: 0, y: 0, z: Math.sin(yaw / 2), w: Math.cos(yaw / 2) }
}

export interface PlanarPose {
  x: number
  y: number
  theta: number
}

/**
 * geometry_msgs/PoseWithCovarianceStamped for /initialpose.
 *
 * Two things here were learned the hard way by the previous UI.
 *
 * The stamp is zero. AMCL compares the header stamp against its own clock, and
 * under simulated time a wall-clock stamp is hours away from sim time — the
 * message is dropped, silently, and the robot never localises. A zero stamp
 * means "now" to every consumer that matters here.
 *
 * The covariance says how sure the operator is. All zeros would claim perfect
 * certainty and collapse AMCL's particle cloud onto one point, which cannot
 * then recover if the guess was wrong. 0.25 on x, y and yaw is the value RViz
 * uses: confident, not infallible.
 */
export function initialPoseMessage(pose: PlanarPose) {
  const covariance = new Array(36).fill(0)
  covariance[0] = 0.25 // x
  covariance[7] = 0.25 // y
  covariance[35] = 0.25 // yaw

  return {
    header: { frame_id: 'map', stamp: { sec: 0, nanosec: 0 } },
    pose: {
      pose: {
        position: { x: pose.x, y: pose.y, z: 0 },
        orientation: yawToQuaternion(pose.theta),
      },
      covariance,
    },
  }
}

/** geometry_msgs/PoseStamped for /goal_pose. */
export function goalPoseMessage(pose: PlanarPose) {
  return {
    header: { frame_id: 'map', stamp: { sec: 0, nanosec: 0 } },
    pose: {
      position: { x: pose.x, y: pose.y, z: 0 },
      orientation: yawToQuaternion(pose.theta),
    },
  }
}
