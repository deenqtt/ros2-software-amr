# ROS 2 Jazzy Dependency Status

**Scope:** Phase 0/1 foundation, Phase 2 package compatibility, and Phase 3 Gazebo Sim foundation  
**Audited:** 2026-09-17  
**Base checked:** official `ros:jazzy-ros-base-noble` image on amd64

This inventory separates packages available in the Jazzy/Noble foundation from
dependencies that still require later sensor, control, Nav2, SLAM, or docking
work. The active Phase 3 simulator path uses Gazebo Sim/Harmonic; retained
Classic files are rollback/reference material and are not active launch inputs.

Classification:

- **A — Directly available:** package/key resolves for Jazzy and no Phase 0/1
  migration is required.
- **B — Available, but API/configuration requires migration:** package exists,
  but current launch/config/source usage must be validated or updated.
- **C — Gazebo Classic dependency:** current usage requires the dedicated
  Gazebo Harmonic/Gazebo Sim migration phase.
- **D — Obsolete/unnecessary:** current repository declares or installs it, but
  source inspection found no active use in the current simulation path.
- **E — Unresolved:** no Jazzy rosdep rule or package was found in the audited
  repository/image context.

## Repository and foundation dependencies

| Dependency | Humble usage | Jazzy status | Classification | Required action |
| --- | --- | --- | --- | --- |
| `ros-humble-ros-base-jammy` | Docker base image | `ros:jazzy-ros-base-noble` is available | A | Use Jazzy/Noble image |
| `ros-humble-desktop` | GUI/debug tools | `ros-jazzy-desktop` available | A | Installed in Jazzy foundation image |
| `python3-colcon-common-extensions` | Workspace build | Available in Noble | A | Keep |
| `python3-rosdep` | Dependency resolution | Available in Noble | A | Keep |
| `python3-vcstool` | Workspace tooling | Available in Noble | A | Keep |
| `robot_state_publisher` | Robot TF | `ros-jazzy-robot-state-publisher` available | A | Keep; validate with migrated model later |
| `xacro` | Robot description expansion | `ros-jazzy-xacro` available | A | Keep |
| `cv_bridge` | ArUco camera processing | `ros-jazzy-cv-bridge` available | A | Keep; validate image encoding later |
| `tf2_ros` | TF consumers/helpers | Jazzy package available | A | Keep |
| `teleop_twist_keyboard` | Manual mapping control | Jazzy package available | A | Keep |
| OpenCV / NumPy | ArUco node runtime | Noble Python packages available | A | Keep; validate ArUco API later |

## ROS application dependencies

| Dependency | Humble usage | Jazzy status | Classification | Required action |
| --- | --- | --- | --- | --- |
| `navigation2` | Nav2 stack | `ros-jazzy-navigation2` resolves | B | Load current YAML on Jazzy and audit plugins/parameters in Phase 5 |
| `nav2_bringup` | Standard Nav2 launch | `ros-jazzy-nav2-bringup` resolves | B | Validate launch arguments and lifecycle startup later |
| `nav2_map_server` | Map load/save | `ros-jazzy-nav2-map-server` available | B | Validate service names and map behavior later |
| `nav2_lifecycle_manager` | Lifecycle startup | Jazzy package available | B | Validate node list and transitions later |
| `nav2_costmap_2d` | Costmaps/filters | Jazzy package available | B | Validate keepout filter parameters later |
| `nav2_msgs` | Nav2 actions/messages | Jazzy package available | B | Preserve current UI/action contract; validate action behavior later |
| `slam_toolbox` | Online mapping | `ros-jazzy-slam-toolbox` resolves | B | Preserve configuration; validate scan/TF/clock in Phase 6 |
| `rosbridge_server` | Browser ROS boundary | `ros-jazzy-rosbridge-server` resolves | A | Keep WebSocket contract; validate QoS/actions later |
| `web_video_server` | Camera HTTP stream | `ros-jazzy-web-video-server` resolves | A | Keep port/topic contract; validate after camera migration |
| `custom_interfaces` | Mission/status/services | Clean Jazzy generation, introspection, and consumer imports validated | A | Keep frozen definitions; `RobotMode.srv` is now included in generation |
| `opennav_docking` | Previous declaration/config only | `opennav_docking` is available in the Jazzy image, but current runtime uses custom Python docking and does not launch OpenNav | B/D | Keep as a future architectural option, not a dependency of the current custom docking package |
| `opennav_docking_msgs` | Previous declaration only | No standalone Jazzy apt package, rosdep rule, or installed package was found; `nav2_msgs/action/DockRobot` is installed | D/E | Removed stale project declaration; revisit only if OpenNav architecture is explicitly approved |

## Gazebo and simulator dependencies

| Dependency | Humble usage | Jazzy status | Classification | Required action |
| --- | --- | --- | --- | --- |
| `gazebo_ros` | Legacy Classic launch and spawn | No Jazzy rosdep rule found; no active manifest/launch use | D/C | Retain only in historical references; active path uses `ros_gz_sim` |
| `gazebo_ros_pkgs` | Legacy Classic package umbrella | No Jazzy rosdep rule found; removed from active manifest | D/C | Do not reintroduce; historical `.world`/URDF remain for rollback |
| `gazebo_ros/spawn_entity.py` | Spawn URDF into Classic | Not used by active Jazzy launch | D/C | Replaced by validated `ros_gz_sim` create flow |
| `libgazebo_ros_diff_drive.so` | Classic differential drive plugin | No direct Jazzy equivalent plugin contract | C | Port to Gazebo Sim DiffDrive system plus bridge later |
| `libgazebo_ros_ray_sensor.so` | Classic LiDAR plugin | No direct Jazzy equivalent plugin contract | C | Port to Gazebo Sim lidar plus bridge later |
| `libgazebo_ros_imu_sensor.so` | Classic IMU plugin | No direct Jazzy equivalent plugin contract | C | Port to Gazebo Sim IMU plus bridge later |
| `libgazebo_ros_camera.so` | Classic camera plugin | No direct Jazzy equivalent plugin contract | C | Port to Gazebo Sim camera/image bridge later |
| `gazebo_ros2_control` | Installed by old Dockerfile | No active URDF/controller use found | D | Do not carry forward unless ros2_control becomes an explicit design requirement |
| `turtlebot3_gazebo` | Classic package in current manifest/path | Jazzy package resolves and is Gazebo Sim-based | B | Keep foundation availability; update current launch/model usage only in Gazebo phase |
| `turtlebot3_description` | Robot description dependency | Jazzy package resolves | A | Keep if required by migrated model |
| `turtlebot3_simulations` | Old metapackage/install convenience | Jazzy package resolves | B | Verify whether custom model needs it; avoid using it as evidence that current Classic launch works |
| `ros_gz_sim` | Not used by current code | `ros-jazzy-ros-gz-sim` available | A | Active Phase 3 server, world, and spawn launch |
| `ros_gz_bridge` | Not used by current code | `ros-jazzy-ros-gz-bridge` available | A | Active Phase 3 `/clock` bridge; sensor bridges deferred |
| `ros_gz_image` | Not used by current code | `ros-jazzy-ros-gz-image` available | A | Installed as future camera integration option |
| Gazebo Harmonic | Not used by current code | Gazebo Sim 8.15.0 available in tested Jazzy image | A/B | Phase 3 world/spawn foundation PASS; sensors and control remain Phase 4 |

## Phase 2 evidence

The four local application packages were audited against their actual launch and
Python imports. Missing runtime declarations were added to the relevant
manifests. `amr_docking` no longer declares OpenNav packages because its active
nodes import `custom_interfaces`, `rclpy`, `cv_bridge`, standard message types,
and `nav2_msgs`, but do not import or launch OpenNav.

The `StationConfig` consumer in `docking_manager_node.py` was corrected to use
the committed fields (`station_id`, `type`, `x_pose`, `y_pose`, `yaw_pose`,
`action`). Since the frozen service has no approach-pose fields, the node derives
a 0.5 m approach pose internally. The Web UI already sends the committed field
names through `useROS.js`.

Jazzy/Noble OpenCV is 4.6.0. It provides `cv2.aruco.Dictionary_get` and
`DetectorParameters_create`, but not `cv2.aruco.drawAxis`; the node now uses
the available `cv2.drawFrameAxes` API.

The Phase 2 eligible build completed for `custom_interfaces`, `amr_docking`,
and `amr_navigation`. `amr_simulation` remains the Gazebo Classic boundary,
and `amr_bringup` is transitively coupled to it through its launch dependency.

## Build and resolution status

The official Jazzy/Noble image was pulled and checked. `ROS_DISTRO=jazzy` was
confirmed. The following `rosdep resolve` results were observed:

```text
gazebo_ros             -> no rosdep rule
gazebo_ros_pkgs        -> no rosdep rule
turtlebot3_gazebo      -> ros-jazzy-turtlebot3-gazebo
turtlebot3_description  -> ros-jazzy-turtlebot3-description
opennav_docking        -> ros-jazzy-opennav-docking
opennav_docking_msgs   -> no rosdep rule
navigation2            -> ros-jazzy-navigation2
nav2_bringup           -> ros-jazzy-nav2-bringup
slam_toolbox           -> ros-jazzy-slam-toolbox
rosbridge_server       -> ros-jazzy-rosbridge-server
web_video_server       -> ros-jazzy-web-video-server
cv_bridge              -> ros-jazzy-cv-bridge
```

The full workspace rosdep gate previously failed only on the intentionally
retained Gazebo Classic key `gazebo_ros_pkgs`; that paragraph is the historical
Phase 2 result. Phase 3 removed the active Classic declarations and validated
the full workspace against Jazzy without skip keys. The Dockerfile now defaults
to `BUILD_WORKSPACE=true`.

## Phase 3 evidence

The active `amr_simulation` launch uses `ros_gz_sim` and `ros_gz_bridge` with
Gazebo Sim 8.15.0. The migrated SDF world starts, `amr_robot` spawns, and a
live `/clock` sample is received. The full verification result was:

```text
#All required rosdeps installed successfully
Summary: 5 packages finished [24.8s]
```

The Phase 3 model was intentionally plugin-free. Phase 4 now validates the
native runtime systems listed below; Nav2, SLAM, docking, and RViz remain
later-phase work. `amr_world.world` and `amr_robot.urdf` remain only as inactive
rollback/reference artifacts.

## Phase 4 runtime evidence

The Cafe Service AMR runtime was implemented against Gazebo Sim/Harmonic with
the following native systems and bridge dependencies:

| Capability | Gazebo Sim implementation | ROS-facing result | Status |
| --- | --- | --- | --- |
| Differential drive | `gz::sim::systems::DiffDrive` | `/cmd_vel`, `/odom`, `/tf` through `ros_gz_bridge` | PASS |
| 2D LiDAR | Native `gpu_lidar` plus Gazebo sensors system | `/scan`, 720 samples, approximately 10 Hz | PASS |
| IMU | Native IMU sensor plus `gz::sim::systems::Imu` | `/imu`, approximately 100 Hz, `imu_link` frame | PASS |
| Main camera | Native RGB camera plus Gazebo sensors system | `/camera/image_raw`, `/camera/camera_info`, 640×480, approximately 15 Hz | PASS |
| Static TF | `robot_state_publisher` from Xacro | `base_link → camera_link → camera_rgb_frame → camera_rgb_optical_frame` | PASS |
| Docking / ArUco runtime | Not launched or redesigned | Audit and behavior validation deferred | DEFERRED |

The camera is forward-facing physically while retaining the frozen ROS topics
and frame chain. A future rear docking camera can be added as a separate link
without renaming the current ROS-facing camera interfaces.

The runtime emits parser warnings for the Gazebo extension element
`gz_frame_id`; the extension is preserved because it supplies sensor frame
metadata used by the Gazebo-to-ROS conversion. These warnings are documented
for cleanup during a later Gazebo/SDF compatibility audit and are not package
resolution failures.
