/**
 * Every ROS name the frontend touches, in one place.
 *
 * The old project scattered these as string literals across 1,245 lines of
 * useROS.js, which is why introducing a per-robot namespace was a grep job.
 * Here `rosNames(namespace)` is the single edit point: pass '' for the current
 * one-bridge-per-robot topology, or 'amr_01' if the fleet later moves to a
 * shared bridge with namespaced topics.
 *
 * See docs/WEB_UI_REDESIGN_AUDIT.md section 12, stage 4.
 */

export interface RosNames {
  topics: {
    map: string
    costmap: string
    tf: string
    tfStatic: string
    amclPose: string
    slamPose: string
    odom: string
    plan: string
    scan: string
    particleCloud: string
    robotDescription: string
    robotStatus: string
    batteryState: string
    dockStatus: string
    cmdVel: string
    goalPose: string
    initialPose: string
    zones: string
    missionPayload: string
    /** Where the browser publishes drive commands. Never /cmd_vel directly:
     *  the agent relays and stops the robot when the stream goes quiet. */
    teleopCmdVel: string
    /** The agent's own state, published at 1 Hz so a late subscriber learns it. */
    robotModeStatus: string
    /**
     * What became of the goal.
     *
     * Goals go out on /goal_pose, which is a topic: bt_navigator wraps it into
     * an action internally, so nothing on this side holds a handle to wait on.
     * The action server publishes its own status here, and reading it is what
     * turns "Goal sent" into an answer.
     */
    navGoalStatus: string
  }
  services: {
    mapSave: string
    loadMap: string
    saveMap: string
    dockCommand: string
    stationConfig: string
    missionConfirm: string
    robotMode: string
    cancelNavGoal: string
  }
  actions: {
    missionPlan: string
    navigateToPose: string
  }
}

export interface RosMessageTypes {
  occupancyGrid: string
  tfMessage: string
  poseWithCovarianceStamped: string
  odometry: string
  path: string
  laserScan: string
  particleCloud: string
  string: string
  robotStatus: string
  batteryState: string
  twist: string
  poseStamped: string
  goalStatusArray: string
  missionPlanFeedback: string
}

export const MESSAGE_TYPES: RosMessageTypes = {
  occupancyGrid: 'nav_msgs/msg/OccupancyGrid',
  tfMessage: 'tf2_msgs/msg/TFMessage',
  poseWithCovarianceStamped: 'geometry_msgs/msg/PoseWithCovarianceStamped',
  odometry: 'nav_msgs/msg/Odometry',
  path: 'nav_msgs/msg/Path',
  laserScan: 'sensor_msgs/msg/LaserScan',
  particleCloud: 'nav2_msgs/msg/ParticleCloud',
  string: 'std_msgs/msg/String',
  robotStatus: 'custom_interfaces/msg/RobotStatus',
  batteryState: 'sensor_msgs/msg/BatteryState',
  twist: 'geometry_msgs/msg/Twist',
  poseStamped: 'geometry_msgs/msg/PoseStamped',
  goalStatusArray: 'action_msgs/msg/GoalStatusArray',
  missionPlanFeedback: 'custom_interfaces/action/MissionPlan_FeedbackMessage',
}

export const SERVICE_TYPES = {
  loadMap: 'nav2_msgs/srv/LoadMap',
  saveMap: 'slam_toolbox/srv/SaveMap',
  dockCommand: 'custom_interfaces/srv/DockCommand',
  stationConfig: 'custom_interfaces/srv/StationConfig',
  trigger: 'std_srvs/srv/Trigger',
  robotMode: 'custom_interfaces/srv/RobotMode',
  cancelGoal: 'action_msgs/srv/CancelGoal',
} as const

export const ACTION_TYPES = {
  missionPlan: 'custom_interfaces/action/MissionPlan',
  navigateToPose: 'nav2_msgs/action/NavigateToPose',
} as const

/**
 * Suggested subscription rates, in milliseconds. 0 means unthrottled.
 *
 * The old project left /scan and /particle_cloud unthrottled (useROS.js:439,
 * 448), which put thousands of marker updates per second on the main thread of
 * a machine also running the robot stack.
 */
export const THROTTLE_MS = {
  tf: 33,
  costmap: 500,
  scan: 100,
  particleCloud: 500,
  odom: 100,
  battery: 1000,
} as const

function join(namespace: string, name: string): string {
  if (!namespace) return name
  const ns = namespace.replace(/^\/+|\/+$/g, '')
  return `/${ns}${name}`
}

export function rosNames(namespace = ''): RosNames {
  const n = (name: string) => join(namespace, name)
  return {
    topics: {
      map: n('/map'),
      costmap: n('/global_costmap/costmap'),
      // /tf and /tf_static stay global even under namespacing; frame prefixes
      // carry the robot identity instead.
      tf: '/tf',
      tfStatic: '/tf_static',
      amclPose: n('/amcl_pose'),
      slamPose: n('/pose'),
      odom: n('/odom'),
      plan: n('/plan'),
      scan: n('/scan'),
      particleCloud: n('/particle_cloud'),
      robotDescription: n('/robot_description'),
      robotStatus: n('/robot_status'),
      batteryState: n('/battery_state'),
      dockStatus: n('/dock_status'),
      cmdVel: n('/cmd_vel'),
      goalPose: n('/goal_pose'),
      navGoalStatus: n('/navigate_to_pose/_action/status'),
      initialPose: n('/initialpose'),
      zones: n('/amr/zones'),
      missionPayload: n('/amr/mission_payload'),
      teleopCmdVel: n('/teleop/cmd_vel'),
      robotModeStatus: n('/robot_mode_status'),
    },
    services: {
      mapSave: n('/map_save'),
      loadMap: n('/map_server/load_map'),
      saveMap: n('/slam_toolbox/save_map'),
      dockCommand: n('/dock_command'),
      stationConfig: n('/station_config'),
      missionConfirm: n('/mission_confirm'),
      robotMode: n('/robot_mode'),
      cancelNavGoal: n('/navigate_to_pose/_action/cancel_goal'),
    },
    actions: {
      missionPlan: n('/mission_plan'),
      navigateToPose: n('/navigate_to_pose'),
    },
  }
}

/** Latched topics must be subscribed with transient_local durability. */
export const LATCHED_QOS = {
  durability: 'transient_local',
  reliability: 'reliable',
  history: 'keep_last',
  depth: 1,
} as const
