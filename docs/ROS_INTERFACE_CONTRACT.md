# Current Simulator ROS Interface Contract

**Status:** Frozen simulator contract; Phase 3 implementation notes appended  
**Scope:** current simulator only; this is not a contract for the future physical robot  
**ROS baseline:** ROS 2 Jazzy in the Docker/Noble setup  
**Last audited:** 2026-09-17

This document records the interfaces exposed or consumed by the current AMR
simulation. Names and types are preserved as the application currently expects
them. The Jazzy migration should preserve these contracts where practical and
use explicit adapters when Gazebo or the future robot requires a different
internal interface.

## Runtime and network contract

| Item | Current value | Evidence/notes |
| --- | --- | --- |
| ROS distribution | Jazzy | Current Dockerfile, scripts, and launch environment |
| Container OS | Ubuntu 24.04 Noble | `ros:jazzy-ros-base-noble` |
| Host ROS | Not required; `ros2` was not on the local host PATH during audit | Docker-first workflow |
| `ROS_DOMAIN_ID` image default | `0` | Dockerfile and entrypoint |
| `ROS_DOMAIN_ID` Compose value | `42` | `docker-compose.yml`; this is the effective Compose value |
| ROS WebSocket | `0.0.0.0:8765` | `rosbridge_server/rosbridge_websocket` |
| Video HTTP server | `:8080` | `web_video_server` |
| FastAPI backend | `:3001` | `backend` container and Web UI API wrapper |
| Vue/Vite development server | `:3000` | Native development workflow |
| Gazebo launch path | `amr_simulation/launch/sim.launch.py` → `ros_gz_sim/launch/gz_sim.launch.py` → `amr_world.sdf` | Gazebo Sim 8 / Harmonic; Phase 3 foundation |
| SLAM launch path | `amr_bringup` → `amr_simulation/launch/slam.launch.py` → `slam_toolbox/launch/online_async_launch.py` | `use_slam:=true` |
| Nav2 launch path | `amr_bringup` → `amr_navigation/launch/navigation.launch.py` → `nav2_bringup/launch/bringup_launch.py` | `use_slam:=false` |

## Topics

The type spelling below uses the ROS 2 canonical form (`pkg/msg/Type`). The
browser-side `roslibjs` code uses the equivalent slash form where applicable.

| Kind | Name | Type | Direction | Consumer/Producer | Purpose |
| --- | --- | --- | --- | --- | --- |
| Topic | `/cmd_vel` | `geometry_msgs/msg/Twist` | UI/custom nodes → simulator | Vue teleop, mission/docking nodes → ROS-Gazebo bridge → native Gazebo Sim DiffDrive | Velocity command |
| Topic | `/odom` | `nav_msgs/msg/Odometry` | simulator → consumers | Native Gazebo Sim DiffDrive → ROS-Gazebo bridge → battery, docking, SLAM/Nav2, UI | Odometry and velocity |
| Topic | `/scan` | `sensor_msgs/msg/LaserScan` | simulator → consumers | Native Gazebo Sim GPU LiDAR → ROS-Gazebo bridge → SLAM, Nav2 costmaps, UI | 2D LiDAR |
| Topic | `/imu` | `sensor_msgs/msg/Imu` | simulator → consumers | Native Gazebo Sim IMU system → ROS-Gazebo bridge; no active application consumer found | Simulated IMU |
| Topic | `/camera/image_raw` | `sensor_msgs/msg/Image` | simulator → consumers | Forward-facing native Gazebo Sim camera → ROS-Gazebo bridge → future ArUco/video consumers | Main forward camera; ROS topic unchanged |
| Topic | `/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | simulator → consumers | Native Gazebo Sim camera → ROS-Gazebo bridge → future ArUco consumer | Camera intrinsics |
| Topic | `/map` | `nav_msgs/msg/OccupancyGrid` | SLAM/map server → consumers | SLAM or Nav2 map server → UI, keepout server, Nav2 | Occupancy map; transient-local subscription is expected by UI/keepout |
| Topic | `/tf` | `tf2_msgs/msg/TFMessage` | TF publishers → consumers | SLAM/Nav2, robot state publisher, simulator → UI and ROS consumers | Dynamic transforms |
| Topic | `/tf_static` | `tf2_msgs/msg/TFMessage` | static TF publisher → consumers | Robot state publisher → UI and ROS consumers | Static sensor/body transforms |
| Topic | `/amcl_pose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | AMCL → consumers | Nav2 AMCL → docking manager and UI fallback | Localized pose |
| Topic | `/pose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | SLAM Toolbox → consumers | SLAM Toolbox → UI fallback | SLAM pose fallback |
| Topic | `/particle_cloud` | `nav2_msgs/msg/ParticleCloud` | AMCL → UI | UI localization visualization | AMCL particles |
| Topic | `/plan` | `nav_msgs/msg/Path` | Nav2 → UI | Planner/controller path → map view | Planned path |
| Topic | `/global_costmap/costmap` | `nav_msgs/msg/OccupancyGrid` | Nav2 → UI | Global costmap → map view | Costmap visualization |
| Topic | `/robot_description` | `std_msgs/msg/String` | robot state publisher → UI | Robot description → UI model consumer | URDF string |
| Topic | `/battery_state` | `sensor_msgs/msg/BatteryState` | battery simulator → UI | `battery_sim_node` → UI fallback | Battery state |
| Topic | `/battery_percent` | `std_msgs/msg/Float32` | battery simulator → consumers | `battery_sim_node`; no direct Web UI subscription found | Battery percentage |
| Topic | `/robot_status` | `custom_interfaces/msg/RobotStatus` | mission manager → UI | `mission_manager_node` → UI | Dock/charge/status flags |
| Topic | `/dock_status` | `std_msgs/msg/String` | docking/mission nodes → consumers | custom docking and mission manager → UI and battery simulator | Docking state string |
| Topic | `/aruco/detected` | `std_msgs/msg/Bool` | ArUco detector → consumers | `aruco_detector_node`; no direct Web UI subscription found | Marker visibility |
| Topic | `/aruco/marker_pose` | `geometry_msgs/msg/PoseStamped` | ArUco detector → consumers | `aruco_detector_node`; no direct Web UI subscription found | Marker pose |
| Topic | `/aruco/distance` | `std_msgs/msg/Float32` | ArUco detector → docking | Detector → docking manager | Marker depth in metres |
| Topic | `/aruco/lateral_offset` | `std_msgs/msg/Float32` | ArUco detector → docking | Detector → docking manager | Marker lateral offset |
| Topic | `/aruco/debug_image` | `sensor_msgs/msg/Image` | ArUco detector → consumers | Detector; no direct Web UI subscription found | Annotated debug image |
| Topic | `/amr/keepout_zones` | `std_msgs/msg/String` | UI → keepout server | JSON polygon list → mask server | Keepout zone updates |
| Topic | `/costmap_filter_info` | `nav2_msgs/msg/CostmapFilterInfo` | keepout server → Nav2 | Keepout mask server → Nav2 KeepoutFilter | Filter metadata; transient-local |
| Topic | `/keepout_filter_mask` | `nav_msgs/msg/OccupancyGrid` | keepout server → Nav2 | Keepout mask server → Nav2 KeepoutFilter | Generated mask; transient-local |
| Topic | `/goal_pose` | `geometry_msgs/msg/PoseStamped` | UI → Nav2 | Vue → Nav2 goal-pose consumer | Single navigation goal |
| Topic | `/initialpose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | UI → AMCL | Vue → AMCL | Initial localization pose |
| Topic | `/amr/mission_payload` | `std_msgs/msg/String` | UI → ROS graph | Vue publishes JSON payload; no current ROS subscription found | Mission metadata/payload |
| Action status | `/navigate_to_pose/_action/status` | `action_msgs/msg/GoalStatusArray` | Nav2 → UI | Vue status observer | Single goal status |
| Action status | `/mission_plan/_action/status` | `action_msgs/msg/GoalStatusArray` | mission manager → UI | Vue mission observer | Mission status |
| Action feedback | `/mission_plan/_action/feedback` | `custom_interfaces/action/MissionPlan_FeedbackMessage` | mission manager → UI | Vue mission observer | Mission state feedback |

## Services

| Kind | Name | Type | Direction | Consumer/Producer | Purpose |
| --- | --- | --- | --- | --- | --- |
| Service | `/dock_command` | `custom_interfaces/srv/DockCommand` | UI → docking/mission node | Vue calls; custom nodes provide it | `dock`, `undock`, or `cancel` |
| Service | `/station_config` | `custom_interfaces/srv/StationConfig` | UI → docking/mission node | Vue calls; custom nodes provide it | Save/delete station metadata |
| Service | `/mission_confirm` | `std_srvs/srv/Trigger` | UI → mission manager | Vue calls; mission manager provides it | Continue a manually paused mission |
| Service | `/robot_mode` | `custom_interfaces/srv/RobotMode` | UI → mode orchestrator | Vue calls it; provider was not found in current ROS launch | Switch `map`/`nav` mode; current implementation is incomplete |
| Service | `/map_server/load_map` | `nav2_msgs/srv/LoadMap` | UI → Nav2 map server | Vue calls it in navigation workflows | Load a YAML map |
| Service | `/map_saver/save_map` | `nav2_msgs/srv/SaveMap` | UI → map saver | Vue calls it in mapping workflows | Save YAML/PGM map |
| Service | `/navigate_to_pose/_action/cancel_goal` | `action_msgs/srv/CancelGoal` | UI → Nav2 | Vue cancellation workaround | Cancel navigation goal |
| Internal service | `/collision_monitor/change_state` | `lifecycle_msgs/srv/ChangeState` | docking manager → Nav2 | Custom docking node calls it | Temporarily deactivate/reactivate collision monitor |

`DockCommand.srv`, `StationConfig.srv`, `RobotMode.srv`, and
`MissionPlan.action` are defined in `custom_interfaces`. Their exact request
and response fields are the source of truth for the simulator contract:

```text
DockCommand:
  request: string action, string station_id
  response: string result

StationConfig:
  request: string station_id, uint8 type, float32 x_pose, float32 y_pose,
           float32 yaw_pose, uint8 action
  response: string result

RobotMode:
  request: string robot_mode
  response: string result

MissionPlan:
  goal: string station_id, int8 dest_tasks, bool continue_mode
  result: string result
  feedback: string mission_sts
```

## Actions

| Name | Type | Server/client | Current use |
| --- | --- | --- | --- |
| `/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | Nav2 server; mission/docking nodes are clients | Approach, undock, and application navigation |
| `/mission_plan` | `custom_interfaces/action/MissionPlan` | `mission_manager_node` server; Vue/rosbridge client | Sequential mission waypoint execution |

Docking itself is not a separate ROS action in the current simulator. The UI
uses `/dock_command`; the custom node internally calls `/navigate_to_pose` and
publishes `/dock_status`.

## TF contract

| Relationship | Owner/use | Required meaning |
| --- | --- | --- |
| `map → odom` | SLAM Toolbox in mapping, AMCL/Nav2 in navigation | Global localization transform |
| `odom → base_footprint` | Current differential-drive simulator path | Odometry transform used by UI/SLAM/Nav2 |
| `base_footprint → base_link` | `robot_state_publisher` | Robot body fixed transform |
| `base_link → wheel_left_link` | `robot_state_publisher` | Left wheel geometry |
| `base_link → wheel_right_link` | `robot_state_publisher` | Right wheel geometry |
| `base_link → imu_link` | `robot_state_publisher` | IMU frame |
| `base_link → base_scan` | `robot_state_publisher` | LiDAR frame; `/scan` frame |
| `base_link → camera_link → camera_rgb_frame → camera_rgb_optical_frame` | `robot_state_publisher` | Main forward-camera chain; ArUco pose uses the unchanged optical frame |

The UI resolves pose primarily from `map → odom → base_footprint` and falls
back to `/amcl_pose` or `/pose`. Nav2 configuration uses `base_footprint` for
AMCL and `base_link` in costmaps, so duplicate or missing transforms are
application-breaking.

## Web dependency

The Vue application connects directly to rosbridge at `ws://localhost:8765` by
default. It consumes the topic, action-status, action-feedback, service, and
action interfaces listed above through `web-ui/src/composables/useROS.js`.
The UI publishes `/cmd_vel` as `geometry_msgs/msg/Twist`; this command type is
part of the current simulator-facing contract and must not be changed globally
without an explicit adapter/remap decision.

The Web UI's primary visualization is its Vue/Leaflet map view. RViz is not
launched by the current application and is not a Web UI dependency.

## Backend dependency

FastAPI on `:3001` owns application data and file operations: maps, missions,
destinations, docks, keepout records, and mode state. The browser calls the
backend over HTTP for those records, but connects directly to rosbridge for
ROS topics/services/actions. The backend is therefore not the current ROS
transport boundary.

The backend mode endpoint attempts to invoke `scripts/docker_run.sh`, but the
current backend container has no Docker CLI/socket declared. Mode orchestration
is consequently a known deployment gap and is not part of the ROS interface
contract itself.

## Phase 2 implementation notes

`StationConfig.srv` remains unchanged. `mission_manager_node.py` already used
the committed fields. `docking_manager_node.py` was corrected to use the same
fields, and derives a 0.5 m approach pose behind the target because the frozen
service contains no separate approach pose. The Web UI's `useROS.js` sends
`station_id`, `type`, `action`, `x_pose`, `y_pose`, and `yaw_pose` exactly as
defined here.

The custom interface generator now includes `RobotMode.srv`; all five
application-used interfaces were generated and introspected successfully on
Jazzy.

## Phase 3 Gazebo Sim implementation notes

The active launch path now starts only the Gazebo Sim server (or optional GUI),
the `ros_gz_bridge` `/clock` bridge, and a plugin-free `amr_robot` model. The
world is `amr_world.sdf`, and the robot is spawned through
`ros_gz_sim/launch/gz_spawn_model.launch.py`. The `/clock` bridge is simulator
time infrastructure and does not change the frozen application topic, service,
action, or TF contract.

The Phase 4 model adds native Gazebo Sim DiffDrive, GPU LiDAR, IMU, and RGB
camera systems. `ros_gz_bridge` owns the ROS-facing adapters, while
`robot_state_publisher` owns the fixed body/sensor transforms. The dynamic
`odom → base_footprint` transform is owned by the DiffDrive odometry bridge;
there must not be a second publisher for that edge.

The main camera is physically forward-facing, but its ROS topics and frame
chain remain unchanged. The legacy ArUco/docking implementation may have
behavioral assumptions about a rear camera or marker observation direction;
that audit and any redesign are deferred to the docking phase. The model is
kept extensible for a separate rear docking camera later, but no second camera
is implemented in Phase 4. The old `amr_world.world` and `amr_robot.urdf`
remain as inactive comparison/rollback artifacts only.

## Baseline inconsistencies to preserve and resolve explicitly later

These are recorded findings, not Phase 0 fixes:

1. `/robot_mode` is called by the Web UI but no provider is launched by the
   current bringup path.
2. `/amr/mission_payload` is published by the Web UI, but no current ROS
   subscriber was found.
3. The UI comments refer to Foxglove in places, while the current launch path
   starts `rosbridge_server`.

These inconsistencies must not be “fixed” by changing the future real-robot
interface. They should be handled as simulator-side cleanup or explicit
adapter work after the Jazzy foundation is validated.

## Real Robot Interface Mapping — Pending

The physical robot is developed separately. No real-robot interface is inferred
from this repository.

| Function | Simulator Interface | Real Robot Interface | Compatibility | Adapter Required |
| --- | --- | --- | --- | --- |
| Velocity command | `/cmd_vel` — `geometry_msgs/msg/Twist` | TBD | TBD | TBD |
| Odometry | `/odom` — `nav_msgs/msg/Odometry` | TBD | TBD | TBD |
| LiDAR | `/scan` — `sensor_msgs/msg/LaserScan` | TBD | TBD | TBD |
| IMU | `/imu` — `sensor_msgs/msg/Imu` | TBD | TBD | TBD |
| Camera | `/camera/image_raw` + `/camera/camera_info` | TBD | TBD | TBD |
| TF frames | `map`, `odom`, `base_footprint`, `base_link`, sensor frames | TBD | TBD | TBD |
| Navigation | `/navigate_to_pose` — `nav2_msgs/action/NavigateToPose` | TBD | TBD | TBD |
| Mission | `/mission_plan` — `custom_interfaces/action/MissionPlan` | TBD | TBD | TBD |
| Docking command | `/dock_command` — `custom_interfaces/srv/DockCommand` | TBD | TBD | TBD |
| Docking status | `/dock_status` — `std_msgs/msg/String` | TBD | TBD | TBD |
| Battery/status | `/battery_state`, `/battery_percent`, `/robot_status` | TBD | TBD | TBD |
| QoS and namespaces | Current root namespace and per-topic QoS above | TBD | TBD | TBD |

This mapping remains intentionally incomplete until the physical robot team
provides its documented ROS 2 Jazzy interfaces.
