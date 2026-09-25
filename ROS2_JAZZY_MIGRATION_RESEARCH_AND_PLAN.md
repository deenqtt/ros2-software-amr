# ROS 2 Jazzy Migration Research and Architecture Plan

**Repository:** `ros2-software-amr`  
**Audit date:** 2026-09-17  
**Scope:** research, architecture audit, compatibility assessment, and migration planning only  
**Implementation status:** no source migration performed

## 1. Executive Summary

### Findings

1. **[VERIFIED]** This repository is an AMR simulation stack, not only a Vue web application. It contains a ROS 2 workspace, Gazebo world and robot model, simulated LiDAR/IMU/camera, SLAM Toolbox, Nav2, custom simulation nodes, docking logic, rosbridge, FastAPI, SQLite, maps, and a Vue UI.
2. **[VERIFIED]** The current ROS baseline is ROS 2 Humble on an Ubuntu 22.04/Jammy container. The repository hard-codes Humble in Dockerfiles, Compose, shell scripts, environment paths, and documentation.
3. **[VERIFIED]** The current simulator is Gazebo Classic through `gazebo_ros`/`gazebo_ros_pkgs`. The URDF loads `libgazebo_ros_diff_drive.so`, `libgazebo_ros_ray_sensor.so`, `libgazebo_ros_imu_sensor.so`, and `libgazebo_ros_camera.so`.
4. **[VERIFIED]** The current application does not explicitly launch `rviz2`. There is an image asset named `images/rviz_ui.jpeg`, but no RViz launch invocation or RViz configuration file was found. RViz is therefore optional and currently not part of the runtime path.
5. **[VERIFIED]** The current docking runtime is custom Python logic using `/dock_command`, `/station_config`, Nav2 `NavigateToPose`, `/cmd_vel`, and `/odom`. The installed `docking_params.yaml` and `opennav_docking` dependency are not wired into the master launch path.
6. **[VERIFIED]** The backend's mode-switch endpoint invokes `scripts/docker_run.sh`, while the backend container has no Docker CLI or Docker socket declared in `docker-compose.yml`. This is an existing deployment/design risk independent of Jazzy.
7. **[VERIFIED]** ROS 2 Jazzy targets Ubuntu 24.04/Noble as its Tier 1 Ubuntu platform and has binary Docker images such as `ros:jazzy-ros-base-noble`. ROS 2 Humble targets Ubuntu 22.04/Jammy as its Tier 1 Ubuntu platform.
8. **[VERIFIED]** Gazebo Classic reached end-of-life in January 2025 and `gazebo_ros_pkgs` is archived/deprecated. Gazebo Harmonic is the recommended Gazebo release for ROS 2 Jazzy.
9. **[VERIFIED]** The official Gazebo migration path replaces direct `gazebo_ros_pkgs` plugins with Gazebo Sim systems plus `ros_gz`/`ros_gz_bridge` integration. This affects the current world, launch file, URDF/SDF, sensor publication, spawning, and command/odometry paths.
10. **[VERIFIED]** ROS 2 does not guarantee communication between different ROS distributions. Keeping this simulation on Humble while integrating it as if it were a Jazzy robot is not a supported production compatibility strategy.

### Architecture decision

The recommended target is:

```text
Ubuntu 24.04 Noble host
└── Docker Compose
    ├── amr-sim
    │   ├── ROS 2 Jazzy
    │   ├── Gazebo Harmonic / Gazebo Sim
    │   ├── custom AMR robot and warehouse world
    │   ├── Nav2
    │   ├── SLAM Toolbox
    │   ├── custom battery/mission/docking nodes
    │   ├── rosbridge_server
    │   └── web_video_server
    ├── amr-backend
    │   └── FastAPI + SQLite
    └── web-ui
        └── Vue development server or static production server

Optional on a graphical development workstation:
  Gazebo GUI and RViz2

Headless server mode:
  Gazebo server/headless rendering, no RViz, remote Web UI
```

This is a **single ROS simulation container** plus separate backend/UI services. Gazebo, Nav2, SLAM, custom ROS nodes, and rosbridge should remain in the same primary ROS container initially. Splitting those into separate containers would add DDS and GUI complexity without a demonstrated benefit for this repository.

### Final recommendation

**Should this repository migrate to ROS 2 Jazzy? Yes.**

The migration should be staged and should include a real Gazebo Sim/Harmonic port, not a global Humble-to-Jazzy text replacement. The simulation should continue to use Docker for reproducibility. ROS 2 Jazzy should be the single ROS distribution used by the simulation stack so that its interfaces are representative of the eventual Jazzy target.

**Implementation readiness:** `READY FOR MIGRATION` after review of this report. The repository is not ready to claim runtime compatibility until the acceptance tests in this document pass; that is a validation condition, not a blocker to beginning the planned migration.

## 2. Current Repository Architecture

### Top-level components

| Component | Location | Status |
|---|---|---|
| ROS 2 workspace | `ros2_ws/src/` | **[VERIFIED]** five packages |
| Simulation model/world | `ros2_ws/src/amr_simulation/` | **[VERIFIED]** custom URDF, world, SDF dock model, sensors |
| Navigation | `ros2_ws/src/amr_navigation/` | **[VERIFIED]** Nav2 launch/config and custom nodes |
| Docking | `ros2_ws/src/amr_docking/` | **[VERIFIED]** custom Python state machine plus unused OpenNav config/dependency |
| Bringup | `ros2_ws/src/amr_bringup/` | **[VERIFIED]** master launch |
| Interfaces | `ros2_ws/src/custom_interfaces/` | **[VERIFIED]** custom action, messages, and services |
| Web UI | `web-ui/` | **[VERIFIED]** Vue 3, Pinia, Leaflet, roslibjs |
| Backend | `backend/` | **[VERIFIED]** FastAPI, SQLite, REST API |
| Docker | `docker/`, `docker-compose.yml` | **[VERIFIED]** ROS simulation and backend containers |
| Maps | `maps/` | **[VERIFIED]** YAML/PGM occupancy maps |
| RViz | `images/rviz_ui.jpeg` only | **[NOT FOUND]** runtime/config integration |
| Physical drivers | repository-wide | **[NOT FOUND]** no motor, CAN, serial, physical LiDAR, physical IMU, or physical camera driver stack |

### Current master launch flow

`amr_bringup/launch/bringup.launch.py` launches:

1. `amr_simulation/launch/sim.launch.py` immediately.
2. `amr_simulation/launch/slam.launch.py` after 3 seconds when `use_slam=true`.
3. `amr_navigation/launch/navigation.launch.py` after 10 seconds when `use_slam=false`.
4. `rosbridge_server/rosbridge_websocket` on port 8765.
5. `web_video_server` on port 8080.
6. `battery_sim_node.py` as a direct Python process.
7. `docking_manager_node.py` as a direct Python process.
8. `aruco_detector_node.py` as a direct Python process.
9. `mission_manager_node.py` as a direct Python process.

The `foxglove_port` launch argument is declared but not used to configure a Foxglove bridge. The actual bridge launched by this file is rosbridge WebSocket.

### Current architecture map

```text
                          [VERIFIED]
Browser
  │
  ├── HTTP REST :3001 ───────────────► FastAPI backend
  │                                      │
  │                                      ├── SQLite metadata
  │                                      ├── map file management
  │                                      └── mode switch invokes docker_run.sh
  │
  └── WebSocket :8765 ────────────────► rosbridge_server
                                         │
                                         ├── /goal_pose
                                         ├── /cmd_vel
                                         ├── /initialpose
                                         ├── /mission_plan action
                                         ├── /dock_command service
                                         ├── /station_config service
                                         └── subscriptions for map/TF/sensors/status

ROS 2 simulation graph
  ├── custom mission_manager_node
  │     └── NavigateToPose action client ──► Nav2 bt_navigator
  ├── custom docking_manager_node
  │     ├── NavigateToPose action client ──► Nav2
  │     └── /cmd_vel reverse control
  ├── keepout_mask_server ──► Nav2 costmap filter topics
  ├── battery_sim_node ──► /battery_state and /robot_status
  ├── aruco_detector_node ──► simulated camera input and docking state
  ├── SLAM Toolbox (mapping mode)
  ├── Nav2 (navigation mode)
  └── Gazebo Classic
        ├── simulated differential drive
        ├── simulated LiDAR
        ├── simulated IMU
        ├── simulated camera
        ├── /odom and TF through plugins/nodes
        └── custom warehouse and ArUco dock model
```

### Sensor and navigation flow

```text
Gazebo sensor systems [VERIFIED]
  ├── LaserScan  ──► /scan ──► SLAM Toolbox and Nav2 costmaps
  ├── IMU       ──► /imu  ──► available for consumers; no current fusion node found
  └── Camera    ──► /camera/image_raw ──► ArUco detector and web_video_server

Gazebo differential drive [VERIFIED]
  └── /cmd_vel ──► simulated base ──► /odom + TF

SLAM mode [VERIFIED]
  /scan + odom TF ──► slam_toolbox ──► /map, /pose, map→odom TF

Navigation mode [VERIFIED]
  map + /scan + odom TF ──► AMCL/Nav2 ──► /plan, costmaps, /cmd_vel

Web UI [VERIFIED]
  └── reads /map, TF, scan, costmap, camera/status topics
  └── publishes goals, teleop commands, initial pose, and custom control data
```

## 3. Current ROS Dependency Inventory

### Workspace packages

| Package | Purpose | Declared dependencies | Relevant runtime files |
|---|---|---|---|
| `amr_bringup` | Master simulation bringup | `amr_simulation`, `amr_navigation`, `rosbridge_server`, `web_video_server` | `launch/bringup.launch.py` |
| `amr_simulation` | Gazebo Classic robot/world/sensors and SLAM launch | `rclpy`, standard messages, `gazebo_ros`, `gazebo_ros_pkgs`, TurtleBot3, `slam_toolbox`, teleop | `launch/`, `urdf/`, `worlds/`, `models/`, `scripts/` |
| `amr_navigation` | Nav2 launch/config, mission and keepout nodes | `navigation2`, `nav2_bringup`, map/lifecycle/costmap packages | `launch/navigation.launch.py`, `config/nav2_params.yaml`, Python nodes |
| `amr_docking` | Custom docking nodes and OpenNav config | `opennav_docking`, `opennav_docking_msgs`, `custom_interfaces`, messages, `cv_bridge` | `docking_manager_node.py`, `aruco_detector_node.py`, `config/docking_params.yaml` |
| `custom_interfaces` | Custom ROS interfaces | `rosidl_default_generators/runtime` | `MissionPlan.action`, `RobotStatus.msg`, three services |

### Docker apt inventory

`docker/Dockerfile` installs:

- `ros-humble-desktop`
- `ros-humble-gazebo-ros-pkgs`
- `ros-humble-gazebo-ros2-control`
- `ros-humble-turtlebot3`
- `ros-humble-turtlebot3-gazebo`
- `ros-humble-turtlebot3-simulations`
- `ros-humble-slam-toolbox`
- `ros-humble-navigation2`
- `ros-humble-nav2-bringup`
- `ros-humble-rosbridge-suite`
- `ros-humble-web-video-server`
- `colcon`, `rosdep`, `vcstool`, Git, Wget, and Curl

The `ros-humble-gazebo-ros2-control` package is installed, but **[NOT FOUND]** in the actual URDF: no `gz_ros2_control`/`gazebo_ros2_control` system or controller configuration is used by the current robot model. This should not be treated as evidence that the simulation is ros2_control-based.

### Dependency declaration gaps

The implementation imports or uses several packages that are not declared directly in the matching `package.xml`, including combinations of `rclpy`, `geometry_msgs`, `nav_msgs`, `lifecycle_msgs`, `std_srvs`, `tf2_ros`, and custom interfaces. The broad desktop Docker install masks some of these gaps. A Jazzy migration should make package manifests complete enough for `rosdep install --from-paths src --ignore-src --rosdistro jazzy` to work without relying on unrelated metapackages.

## 4. Current Gazebo Dependency and Plugin Inventory

### Gazebo architecture

**[VERIFIED]** The current project uses Gazebo Classic:

- `amr_simulation/package.xml` declares `gazebo_ros`, `gazebo_ros_pkgs`, and `turtlebot3_gazebo`.
- `sim.launch.py` finds `gazebo_ros`, includes `gazebo_ros/launch/gazebo.launch.py`, and spawns through `gazebo_ros/spawn_entity.py`.
- The world file is `amr_world.world` and describes Gazebo Classic materials and plugins.
- The URDF embeds Classic `<gazebo>` plugin blocks.

### Plugins and functionality

| Current plugin/file | Location | Function | Migration impact |
|---|---|---|---|
| `libgazebo_ros_state.so` | `worlds/amr_world.world` | Publishes Gazebo model/link state interfaces such as model and link states | Replace or remove if not consumed; no current UI/node subscription found |
| `libgazebo_ros_diff_drive.so` | `urdf/amr_robot.urdf` | Differential-drive actuation from `/cmd_vel`, odometry, and odometry TF | Replace with Gazebo Sim `DiffDrive` system plus ROS/Gazebo bridge; parameter semantics are not identical |
| `libgazebo_ros_ray_sensor.so` | `urdf/amr_robot.urdf` | Simulated ray/LDS sensor published as `sensor_msgs/LaserScan` on `/scan` | Convert to Gazebo Sim ray/GPU lidar sensor and bridge `gz.msgs.LaserScan` to ROS `sensor_msgs/msg/LaserScan` |
| `libgazebo_ros_imu_sensor.so` | `urdf/amr_robot.urdf` | Simulated IMU output on `/imu` | Convert to Gazebo Sim IMU system/sensor and bridge `gz.msgs.IMU` to `sensor_msgs/msg/Imu` |
| `libgazebo_ros_camera.so` | `urdf/amr_robot.urdf` | Simulated camera output on `/camera/image_raw` and camera info | Convert to Gazebo Sim camera sensor and bridge image/camera-info messages or use `ros_gz_image` where appropriate |
| `gazebo_ros/spawn_entity.py` | `sim.launch.py` | Spawns URDF from `robot_description` | Replace with `ros_gz_sim create` or the corresponding Jazzy/Gazebo Sim spawn path |
| `gazebo_ros/launch/gazebo.launch.py` | `sim.launch.py` | Starts Gazebo Classic server and GUI | Replace with `ros_gz_sim` launch and `gz sim` server/GUI handling |
| `GAZEBO_MODEL_PATH` | Docker/launch | Resolves custom and TurtleBot3 Classic model paths | Replace/augment with `GZ_SIM_RESOURCE_PATH` and installed model/resource hooks |

The project uses a custom `aruco_dock` SDF model and a Classic `.world`. Their visual/material/resource URI behavior must be validated when converted to modern SDF/Gazebo Sim. The ArUco PNG asset itself is not ROS-distribution-specific, but the rendering and resource lookup are simulator-specific.

### Verified migration mapping

The official Gazebo migration guide describes the conceptual change:

- `gazebo_ros_pkgs` directly loads ROS-aware Classic plugins into Gazebo Classic.
- `ros_gz` primarily bridges Gazebo Transport topics to ROS 2 topics.
- Classic `libgazebo_ros_diff_drive.so` maps to Gazebo Sim's `gz-sim-diff-drive-system`, but parameters such as wheel acceleration are not one-to-one.
- Sensors are represented by Gazebo Sim systems and exposed through `ros_gz_bridge`/related bridge packages.

The actual topic bridge configuration for this repository must be authored and tested; it cannot be safely inferred by renaming library files.

## 5. Current Nav2 Architecture

### Launch and runtime

`amr_navigation/launch/navigation.launch.py` includes `nav2_bringup/launch/bringup_launch.py` with:

- the repository's `nav2_params.yaml`
- map path
- `use_sim_time`

It also launches `keepout_mask_server.py`.

The current navigation parameter file configures:

- AMCL
- BT navigator
- controller server with Regulated Pure Pursuit
- local and global costmaps
- static, obstacle, voxel, inflation, and keepout filter layers
- map server and map saver
- planner server with NavFn
- smoother server
- behavior server
- waypoint follower
- velocity smoother
- collision monitor
- lifecycle managers

### Custom navigation nodes

`mission_manager_node.py` provides a custom `MissionPlan` action server, sends sequential `NavigateToPose` goals to Nav2, supports manual confirmation through `/mission_confirm`, and publishes mission feedback/status.

`keepout_mask_server.py` subscribes to `/amr/keepout_zones` as JSON and publishes a transient-local keepout mask and `CostmapFilterInfo` for Nav2.

### Current Nav2 findings

| Finding | Status |
|---|---|
| Uses standard Nav2 launch architecture | **[VERIFIED]** |
| Uses a custom BT XML file | **[NOT FOUND]**; default Nav2 BTs are used unless selected indirectly by Nav2 |
| Uses custom C++ Nav2 plugins | **[NOT FOUND]** |
| Uses standard Nav2 planners/controllers/costmap plugins | **[VERIFIED]** |
| Uses `geometry_msgs/Twist` for current command path | **[VERIFIED]** |
| Uses `TwistStamped` | **[NOT FOUND]** |
| Collision Monitor configuration is explicitly Jazzy-tested | **[UNVERIFIED]** |
| Nav2 parameters have been tested on Jazzy | **[UNVERIFIED]** |

## 6. Current SLAM Architecture

`amr_simulation/launch/slam.launch.py` includes `slam_toolbox/launch/online_async_launch.py` and passes:

- `use_sim_time=true`
- `slam_params.yaml`

It separately launches `nav2_map_server/map_saver_server` and a lifecycle manager for map saving.

The SLAM parameters configure the standard 2D pipeline around:

- `/scan` input
- odometry and TF
- `map` frame
- simulated time
- asynchronous online mapping

**[VERIFIED]** The stored maps are standard YAML/PGM occupancy maps. No serialized SLAM pose graph is stored in the repository.

**[VERIFIED]** The current SLAM design is conceptually portable to Jazzy. The main migration risk is not the algorithm but the Gazebo-generated `LaserScan`, TF, clock, odometry, QoS, and launch integration.

## 7. Current Docking Architecture

### Actual runtime path

```text
Web UI
  └── /station_config service
  └── /dock_command service
        ▼
docking_manager_node.py
  ├── registers stations in an in-memory/custom state store
  ├── uses Nav2 NavigateToPose for approach/undock
  ├── publishes direct reverse /cmd_vel during docking
  ├── tracks distance from /odom
  ├── subscribes to /amcl_pose for map pose
  ├── temporarily changes collision_monitor lifecycle state
  └── publishes /dock_status

aruco_detector_node.py
  ├── subscribes to simulated camera image/camera info
  ├── uses OpenCV ArUco detection
  └── publishes detection-related data used by docking logic
```

### Important distinction

`amr_docking/config/docking_params.yaml` describes an `opennav_docking::SimpleChargingDock` configuration, but the master bringup does not launch an `opennav_docking` server and the current UI calls custom `/dock_command` services instead. The source-of-truth for current simulation docking is therefore the custom Python state machine, not the OpenNav configuration.

### Recommended target for this phase

Keep the custom docking flow for simulation during the first Jazzy migration. It models the current UI contract and avoids making the simulation depend on a production docking server before the basic simulator is stable. Treat OpenNav docking as a separately validated optional integration later.

## 8. Web, Backend, and ROS Communication Flow

### Web UI to ROS

`web-ui/src/composables/useROS.js` creates a `ROSLIB.Ros` connection directly to rosbridge WebSocket. It subscribes to:

- `/map`
- `/tf`, `/tf_static`
- `/amcl_pose`, `/pose`, `/odom`
- `/plan`
- `/scan`
- `/particle_cloud`
- `/robot_description`
- `/global_costmap/costmap`
- `/dock_status`
- `/battery_state`
- `/robot_status`
- mission action status and feedback topics

It publishes/calls:

- `/goal_pose`
- `/cmd_vel`
- `/initialpose`
- `/amr/keepout_zones`
- `/mission_plan`
- `/dock_command`
- `/station_config`
- `/robot_mode`
- `/mission_confirm`
- map load/save services

The UI uses standard ROS message types plus `custom_interfaces` types. No DDS code exists in the browser.

### Backend role

The FastAPI backend handles:

- map metadata and file storage
- missions
- destinations
- dock records
- keepout records
- persisted application mode
- static map file serving

The backend does not act as the ROS message bridge. The browser connects to rosbridge directly.

### Existing mode-switch concern

`backend/routers/mode.py` starts a background subprocess that invokes `scripts/docker_run.sh`. The backend Docker image only contains Python dependencies. The Compose service does not mount `/var/run/docker.sock`, the repository scripts, or the host Docker CLI into the backend container. Therefore:

- **[VERIFIED]** the code attempts backend-driven Docker orchestration;
- **[VERIFIED]** the Compose definition does not provide the needed Docker execution surface;
- **[UNVERIFIED]** runtime mode switching has not been executed in this audit;
- **[RECOMMENDED]** separate simulation lifecycle orchestration from the backend API or explicitly provide a controlled host-side supervisor in a later hardening phase.

## 9. ROS 2 Jazzy Research

### Platform and lifecycle

ROS 2 Jazzy Jalisco targets Ubuntu 24.04/Noble as its Tier 1 Ubuntu platform for amd64 and arm64. REP-2000 lists Jazzy's lifecycle as May 2024 through May 2029. Humble's Tier 1 Ubuntu target is Ubuntu 22.04/Jammy.

This aligns with the audited host:

```text
Local host: Ubuntu 24.04.4 LTS, codename noble
Docker: 29.6.1
ROS 2 command on host: not installed/on PATH
```

### Binary and Docker availability

The official ROS Docker image publishes `jazzy-ros-base-noble`, including amd64 and arm64 variants. This supports a reproducible Noble/Jazzy simulation container without installing ROS directly on the laptop.

### Relevant Jazzy changes for this repository

Only changes with direct impact on this repository are included here:

1. Jazzy's normal Ubuntu binary target matches the local Noble host.
2. Jazzy's recommended Gazebo integration is modern Gazebo/Harmonic rather than the repository's Gazebo Classic path.
3. Nav2 Jazzy has migration-impacting changes around BehaviorTree.CPP 4.5, command message options, Collision Monitor configuration, plugin naming, and docking.
4. The standard ROS package names change from `ros-humble-*` to `ros-jazzy-*`, but package availability for the current TurtleBot3 Classic simulation packages must be verified during the implementation phase.
5. Cross-distro ROS communication is not guaranteed; simulation and target integration should use a single ROS distribution wherever they share a ROS graph.

## 10. Gazebo and Jazzy Research

### Recommended version

For ROS 2 Jazzy, Gazebo Harmonic is the recommended supported Gazebo release. Gazebo Harmonic provides binaries for Ubuntu Jammy and Noble, and the official Gazebo documentation lists Harmonic as the recommended combination for ROS 2 Jazzy.

Gazebo Classic 11 reached end-of-life in January 2025. The `gazebo_ros_pkgs` repository is archived and explicitly deprecated. Continuing to use Classic can be a temporary compatibility tactic only, not the recommended long-term Jazzy target.

### A. Keep Gazebo Classic temporarily

**Benefits**

- Lowest short-term source change.
- Existing `.world`, URDF plugin blocks, and launch flow remain conceptually familiar.
- May be useful for a short baseline comparison if a working Humble image already exists.

**Costs and risks**

- The current Classic integration is deprecated/archived.
- It does not represent the Gazebo architecture expected by a Jazzy deployment.
- Classic and modern Gazebo package/plugin assumptions are not interchangeable.
- It preserves the largest future migration debt.

**Decision:** not selected as the final target. It may be kept in a temporary branch or baseline image only for regression comparison.

### B. Migrate to Gazebo Harmonic

**Benefits**

- Matches the official Jazzy recommendation.
- Uses the active Gazebo Sim ecosystem and `ros_gz` integration.
- Better represents the expected modern ROS 2 simulation architecture.
- Supports both GUI and headless workflows.

**Costs and risks**

- High migration effort for world, robot model, sensor systems, bridge mappings, spawn flow, and topic/QoS behavior.
- Direct ROS-aware Classic plugins become Gazebo systems plus bridges.
- Camera and lidar rendering require graphics/EGL validation in headless mode.
- TurtleBot3 package branch/version availability must be verified rather than assumed.

**Decision:** selected.

### C. Use another Gazebo combination

Possible alternatives include running a legacy Fortress/Humble stack or a newer Gazebo release outside the Jazzy recommended pairing.

**Decision:** not selected. It would create a second compatibility axis and would not improve this repository's alignment with Jazzy.

### Concrete migration mapping

| Current Classic mechanism | Jazzy/Harmonic target | Validation required |
|---|---|---|
| `gazebo_ros/launch/gazebo.launch.py` | `ros_gz_sim`/`gz sim` launch | Server starts and loads world |
| `gazebo_ros/spawn_entity.py` | `ros_gz_sim create` or equivalent spawn utility | Robot appears from `robot_description` |
| `libgazebo_ros_diff_drive.so` | `gz::sim::systems::DiffDrive` | `/cmd_vel` moves robot and odometry matches expected frames |
| ROS-aware ray plugin | Gazebo Sim ray/GPU lidar + `ros_gz_bridge` | `/scan` type, frame, timestamp, QoS |
| ROS-aware IMU plugin | Gazebo Sim IMU sensor/system + bridge | `/imu` type, frame, rate, covariance |
| ROS-aware camera plugin | Gazebo Sim camera + bridge or image bridge | Image/camera info and ArUco detection |
| `libgazebo_ros_state.so` | Gazebo transport/state tools or removed | Confirm no consumer needs it |
| `GAZEBO_MODEL_PATH` | `GZ_SIM_RESOURCE_PATH` and package resource hooks | World and `aruco_dock` resources resolve |
| Classic `.world` | Gazebo Sim SDF world | World visual and collision parity |

The official Gazebo migration documentation warns that the parameter mapping for differential drive is approximate. In particular, Classic wheel acceleration and Gazebo Sim whole-vehicle acceleration are not identical. This is a simulation fidelity issue, not just a build issue.

## 11. Nav2 Jazzy Compatibility Analysis

### Repository files affected

Primary file: `ros2_ws/src/amr_navigation/config/nav2_params.yaml`.

The header currently says `Compatible with Navigation2 Humble`. Plugin declarations use the older slash-style names in several places, including:

- `nav2_bt_navigator/NavigateToPoseNavigator`
- `nav2_controller::SimpleProgressChecker` mixed with slash-style plugins
- `nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController`
- costmap, planner, smoother, behavior, waypoint, and velocity smoother plugins

### Migration-impacting items

| Area | Current repository state | Jazzy impact | Required action |
|---|---|---|---|
| BehaviorTree.CPP | No custom BT XML found; default Nav2 behavior appears to be used | Jazzy migration documents a move to BehaviorTree.CPP 4.5+ and XML/source changes for custom trees | Verify default BT startup; no custom XML port expected unless later introduced |
| BT plugin naming | Mixed slash and `::` names in YAML | Jazzy standardizes plugin naming toward `::` | Audit every plugin string against installed Jazzy plugin names |
| `cmd_vel` | UI and custom nodes use `geometry_msgs/Twist` | Jazzy/Nav2 provides stamped-command support; modern simulator integrations may use `TwistStamped` | Keep an explicit unstamped contract for this simulation initially, or bridge/convert consistently; test end-to-end |
| Collision Monitor | Uses `FootprintApproach`, footprint topic, `min_points`, and no explicit point string | Jazzy migration changes the polygon point representation when point lists are configured and adds related options | Validate configuration on Jazzy; update only fields rejected or semantically changed |
| RPP | Uses `use_interpolation` nowhere in current YAML | Jazzy deprecates/removes that parameter behavior | No direct change found; still validate controller behavior |
| Costmaps | Standard static/obstacle/voxel/inflation/keepout layers | Plugin APIs and parameter defaults can change by distro | Start Nav2 and verify lifecycle, topic names, and costmap values |
| Lifecycle manager | Explicit node lists | Node names may change if bringup composition/defaults differ | Validate lifecycle activation and no missing-node warnings |
| Nav2 launch | Includes `nav2_bringup/launch/bringup_launch.py` by path | Launch arguments may evolve | Verify launch arguments and defaults on Jazzy |
| Docking | Custom docking runtime; OpenNav config unused | Jazzy has current OpenNav/Nav2 docking documentation and package releases | Keep custom sim flow first; separately test OpenNav later |

### Specific risk

The current YAML is not sufficient evidence of Jazzy compatibility. The configuration must be loaded by the Jazzy Nav2 binaries and tested with a real Jazzy Gazebo-generated topic graph. Static syntax validation alone is insufficient because plugin loader names, lifecycle behavior, message type, and QoS all matter.

## 12. SLAM Toolbox Compatibility Analysis

SLAM Toolbox is a ROS 2 package with a Jazzy release/documentation path and remains the appropriate 2D SLAM choice for this repository.

The current repository uses the standard `online_async_launch.py`, `/scan`, odometry TF, `map` frame, and `use_sim_time`. These concepts are not inherently Humble-specific.

### Expected migration status

| Item | Assessment |
|---|---|
| Package availability in Jazzy | **LOW risk**, official Jazzy package/release documentation exists |
| Current online async launch concept | **LOW risk**, verify launch argument names |
| Current map YAML/PGM files | **LOW risk**, standard map format |
| TF requirements | **MEDIUM risk**, depends on converted Gazebo odometry and frame IDs |
| LaserScan QoS and timestamp | **MEDIUM risk**, depends on `ros_gz_bridge` sensor mapping |
| `use_sim_time` | **LOW risk**, but `/clock` must be present and consumed consistently |
| Serialized pose-graph portability | **UNVERIFIED**, no serialized graph currently committed |

No SLAM algorithm replacement is recommended. The migration should preserve the current SLAM contract and focus on topic, TF, clock, and QoS validation.

## 13. Docking Compatibility Analysis

### Current simulation contract

The current UI depends on custom interfaces and custom status topics. The actual simulation docking state machine uses direct reverse `/cmd_vel`, odometry distance tracking, and Nav2 approach/undock actions.

### Jazzy/Open Navigation research

The Open Navigation docking project states that Humble users should use its `humble` branch; non-Humble users should follow the current path. Jazzy Nav2 documentation includes a docking server tutorial and Jazzy package documentation exposes `opennav_docking`.

However, the repository's current runtime does not actually launch the OpenNav docking server. Switching to it during the ROS/Gazebo migration would combine two independent changes:

1. ROS/Gazebo distribution migration.
2. Docking architecture migration.

That would make failures harder to isolate.

### Decision

For the first Jazzy simulation milestone:

- Keep `docking_manager_node.py` as the simulated docking implementation.
- Keep the existing custom UI service/action contract unless a Jazzy build proves a message/API issue.
- Validate the custom node with Jazzy `rclpy`, Nav2, `Twist`, `/odom`, lifecycle services, and camera topics.
- Treat `docking_params.yaml` and the `opennav_docking` dependency as a separate cleanup/optional integration decision.
- Do not claim that OpenNav docking is active merely because its YAML exists.

## 14. rosbridge and Web Communication Compatibility

`rosbridge_suite` has a ROS 2 branch and Jazzy release packages. Its rosbridge v2 protocol is designed to expose ROS topics, services, and actions through JSON/WebSocket, and `roslibjs` is a supported client type.

### Expected result

The current browser-side architecture should remain:

```text
Vue/roslibjs ──WebSocket JSON──► rosbridge_server ──► ROS 2 Jazzy graph
```

No web rewrite is justified by the ROS distribution migration alone.

### Validation risks

- The current UI relies on explicit QoS for transient-local `/map` and `/robot_description` subscriptions.
- The UI manually uses action protocol operations and comments that ordinary roslibjs action result/feedback behavior is unreliable in this project.
- Jazzy Nav2 action topic names and message types must be verified after the Nav2 launch starts.
- `web_video_server` has Jazzy documentation and can remain the camera HTTP streamer, subject to image topic and encoding validation.

The Web UI should remain the primary operator visualization. rosbridge should remain a boundary adapter, not a replacement for a real ROS graph.

## 15. Docker Architecture Analysis

### Option A — One simulation container, backend/UI services separate

**Selected.**

```text
amr-sim container:
  ROS 2 Jazzy + Gazebo Harmonic + Nav2 + SLAM + custom nodes + rosbridge

amr-backend container:
  FastAPI + SQLite + map files

web-ui:
  native Vite in development, optional static server in production
```

**Why selected:** The ROS graph is small, tightly coupled, and needs shared time, TF, topics, and process startup. One ROS container makes the initial DDS graph and Gazebo integration easier to reason about while preserving backend/UI separation.

### Option B — Native ROS 2 Jazzy, containerized backend

Not selected for this phase. It can be useful later for a physical mini computer, but this repository is simulation-first and the host does not currently have ROS installed. Native installation would make workstation reproduction less consistent.

### Option C — Separate Gazebo, ROS application, bridge, backend, and UI containers

Not selected initially. It would require explicit DDS networking, bridge placement, shared volumes, GUI ownership, clock handling, and more failure modes. The repository does not currently need independent scaling or independent release cadence for those ROS processes.

### Option D — All services in one container

Not selected. It would couple Python backend lifecycle to ROS/Gazebo and make web service observability, restart policy, and security worse.

### Docker engineering requirements

The current Compose file uses:

- `network_mode: host`
- X11 socket mount
- `/dev/dri`
- `privileged: true`
- shared map/source volumes
- fixed `ROS_DOMAIN_ID=42`

For a single-host development simulation, host networking is acceptable as a first implementation because it avoids common DDS multicast and port-mapping issues. It should be documented as a deliberate single-host choice, not treated as a general deployment default.

`privileged: true` is broader than necessary for a long-term design. The migration should first make the simulation work, then reduce privileges to the exact graphics/device capabilities needed.

## 16. GUI, GPU, and Headless Analysis

### Graphical workstation

The current project expects X11 through `/tmp/.X11-unix` and `DISPLAY`. Ubuntu 24.04 may use Wayland with XWayland compatibility. This should be validated on the actual laptop rather than assumed.

Gazebo GUI is useful during world, model, sensor, collision, and docking development. It should be an optional runtime mode, not a condition for headless tests.

### Headless server

Gazebo Sim supports server-only execution and headless rendering through EGL for sensor workloads that need rendering. This allows the same image to run on a dedicated server without opening a GUI, subject to GPU/EGL driver configuration.

Recommended modes:

```text
development:
  Gazebo GUI enabled
  RViz optional
  Web UI enabled

headless:
  Gazebo server/headless rendering
  RViz disabled
  rosbridge + web_video_server enabled
  Web UI accessed remotely
```

The headless mode must be an explicit launch/Compose profile. It must not depend on a fake `DISPLAY=:0` being available.

## 17. RViz Decision

### Current state

- **[VERIFIED]** no `rviz2` executable is launched by repository launch files.
- **[NOT FOUND]** no `.rviz` configuration is tracked.
- **[VERIFIED]** the Web UI renders maps, robot pose, laser data, costmaps, paths, and status through rosbridge.
- **[INFERRED]** `images/rviz_ui.jpeg` is a screenshot/reference asset, not runtime configuration.

### Decision

**RViz: optional development/debugging component.**

RViz is valuable for:

- TF tree and frame correctness
- LaserScan and camera/debug overlays
- occupancy grid and costmaps
- global/local paths
- footprint and localization
- Nav2 initial pose and goals

It should be installed in the graphical development image/profile and documented as a debugging tool. It should not be required for the headless server or treated as the operator UI. The Web UI remains the primary application interface.

## 18. Humble-Jazzy Interoperability Analysis

The official ROS documentation states that nodes are not guaranteed to communicate across ROS distributions. A Humble node communicating with an Iron node is explicitly given as an unsupported example; the same principle applies to Humble/Jazzy.

### Decision

Do not make this architecture depend on:

```text
Humble simulator  ◄──DDS/ROS graph──►  Jazzy robot/application
```

A simple topic may appear to work when message definitions, QoS, middleware, and names align, but this is not a supported compatibility contract. Actions, services, plugin APIs, parameters, and simulator bridges increase the risk.

Use Jazzy for the simulation now so that the simulation's ROS graph, Nav2 behavior, topic types, and bridge expectations align with the eventual Jazzy target.

## 19. Compatibility Matrix

| Area | Current | Jazzy target | Risk | Complexity | Required action |
|---|---|---|---|---|---|
| Host OS | Ubuntu 24.04 local host | Ubuntu 24.04 Noble | LOW | LOW | Keep host; verify graphics stack |
| Container OS | Jammy through Humble image | Noble through Jazzy image | LOW | LOW | Change base image and package prefix |
| ROS distribution | Humble | Jazzy | MEDIUM | MEDIUM | Build and source entire workspace with Jazzy |
| ROS apt packages | `ros-humble-*` | `ros-jazzy-*` | MEDIUM | LOW | Re-resolve every package with rosdep/apt |
| Gazebo | Gazebo Classic 11 | Gazebo Harmonic | HIGH | HIGH | Port world, model, launch, spawn, systems, and bridges |
| `gazebo_ros` | Direct Classic integration | `ros_gz_sim` / `ros_gz_bridge` | HIGH | HIGH | Replace launch and bridge architecture |
| Differential drive | `libgazebo_ros_diff_drive.so` | Gazebo Sim `DiffDrive` | HIGH | MEDIUM | Port SDF/URDF and retune limits |
| LiDAR | Classic ray + ROS plugin | Gazebo Sim lidar + bridge | HIGH | MEDIUM | Verify `/scan`, frame, QoS, clock |
| IMU | Classic IMU + ROS plugin | Gazebo Sim IMU + bridge | HIGH | MEDIUM | Verify message/frame/rate |
| Camera | Classic camera + ROS plugin | Gazebo Sim camera + bridge | HIGH | MEDIUM | Verify image/camera info and ArUco |
| World/materials | Classic `.world` and resources | Gazebo Sim SDF/resources | HIGH | HIGH | Convert and validate visual/collision parity |
| Robot model | URDF with Classic `<gazebo>` blocks | URDF/SDF with Sim systems | HIGH | HIGH | Retain geometry, replace simulator integration |
| Nav2 | Humble config | Jazzy Nav2 | MEDIUM | MEDIUM | Audit plugin names, params, lifecycle, actions |
| Behavior Trees | No custom XML found | Jazzy BT stack | LOW/MEDIUM | LOW/MEDIUM | Verify defaults; port only if custom trees appear |
| Collision Monitor | Humble parameter format | Jazzy parameter behavior | MEDIUM | MEDIUM | Validate polygon/config and command type |
| `cmd_vel` | `geometry_msgs/Twist` | Explicit Twist contract or consistent stamped bridge | MEDIUM | MEDIUM | Decide and test one message type end-to-end |
| SLAM Toolbox | Humble package/launch | Jazzy package/launch | LOW/MEDIUM | LOW | Preserve config; verify TF/scan/clock |
| Map files | YAML/PGM | YAML/PGM | LOW | LOW | Re-test load/save only |
| Docking | Custom Python simulation | Custom Python on Jazzy initially | MEDIUM | MEDIUM | Build/test custom nodes; defer OpenNav change |
| OpenNav dependency | Declared but runtime server unused | Jazzy package exists, branch/API must be chosen | MEDIUM/HIGH | MEDIUM | Resolve dependency strategy explicitly |
| rosbridge | Humble server + roslibjs | Jazzy server + same protocol | LOW/MEDIUM | LOW | Re-test QoS/actions/services |
| web video | Humble package | Jazzy package | LOW | LOW | Re-test camera topic and HTTP stream |
| Backend | Python/FastAPI | Unchanged | LOW | LOW | Keep; fix mode orchestration separately |
| Web UI | Vue/Pinia/Leaflet/roslibjs | Unchanged | LOW/MEDIUM | LOW | Keep; validate ROS message/action contracts |
| Docker networking | Host networking | Host networking initially | MEDIUM | LOW | Keep for single host; document limitation |
| GUI | X11 socket + `/dev/dri` + privileged | Optional GUI profile | MEDIUM/HIGH | MEDIUM | Validate X11/XWayland/GPU; reduce privileges later |
| Headless mode | Not explicitly separated | Gazebo server/headless profile | MEDIUM | MEDIUM | Add and test server profile |
| RViz | Not launched/configured | Optional dev profile | LOW | LOW | Add optional config only if useful |
| Tests | No automated simulation acceptance suite found | Startup/topic/navigation tests | HIGH | HIGH | Add staged acceptance tests |

## 20. Migration Risks

| Risk | Why it exists | Mitigation |
|---|---|---|
| Gazebo port changes robot behavior | DiffDrive limits and sensor timing are not exact plugin-for-plugin translations | Record baseline behavior, port one subsystem at a time, compare `/odom`, `/scan`, and movement |
| World fails to load | Classic materials, URIs, plugins, and `.world` syntax differ | Port world in isolation and validate resource paths before Nav2 integration |
| Sensor topics silently mismatch | `ros_gz_bridge` requires explicit type mappings and QoS | Add topic/type/rate/frame acceptance tests |
| Camera rendering fails headless | Camera and ArUco require a rendering backend | Test graphical and EGL/headless paths separately |
| Nav2 fails during configure | Plugin names/parameters/lifecycle behavior changed | Start with minimal Nav2, then reintroduce custom layers and collision monitor |
| Twist/TwistStamped mismatch | Jazzy/Gazebo ecosystems increasingly expose stamped commands | Choose one command contract and bridge/convert explicitly |
| Docking regression | Current custom code bypasses/changes Collision Monitor lifecycle and relies on `/odom` | Test docking states, timeout, cancel, and reactivation separately |
| OpenNav dependency blocks build | Package manifest declares OpenNav while current Docker does not install it explicitly | Make dependency/runtime decision before final build image |
| Backend cannot control Compose | Backend container lacks Docker CLI/socket | Move orchestration to host supervisor or redesign mode switching |
| DDS discovery fails | Host network, container isolation, multicast, or domain mismatch | Keep one ROS container first; pin `ROS_DOMAIN_ID`; add graph smoke test |
| Privileged GUI is unsafe | Current Compose grants broad privileges | Keep only during baseline if needed, then narrow devices/capabilities |
| No regression suite | A successful image build would not prove simulation correctness | Implement acceptance suite before declaring migration complete |

## 21. Architecture Decisions

### Decision 1 — ROS distribution

**DECISION:** Migrate from Humble to Jazzy.  
**RATIONALE:** Jazzy aligns with the intended future robot and the local Ubuntu 24.04 host. Cross-distro ROS communication is not guaranteed.  
**TRADE-OFF:** Requires Nav2 and Gazebo compatibility work now.  
**IMPACT:** All ROS package names, source paths, build scripts, and simulation integration must be audited.

### Decision 2 — Ubuntu baseline

**DECISION:** Noble/Ubuntu 24.04 for host and Jazzy container.  
**RATIONALE:** Official Tier 1 Jazzy Ubuntu target and current laptop baseline.  
**TRADE-OFF:** The old Humble/Jammy container cannot be reused as the final target.  
**IMPACT:** Base image becomes `ros:jazzy-ros-base-noble`; package resolution becomes Jazzy/Noble-specific.

### Decision 3 — Gazebo

**DECISION:** Gazebo Harmonic/Gazebo Sim with `ros_gz`.  
**RATIONALE:** It is the recommended Jazzy pairing; Classic is EOL/deprecated.  
**TRADE-OFF:** High migration effort and changed plugin/bridge semantics.  
**IMPACT:** World, URDF/SDF, launch, spawn, sensors, differential drive, resource paths, and topic bridges change.

### Decision 4 — Containerization

**DECISION:** Docker for the complete simulation stack.  
**RATIONALE:** The project is simulation-first, the host lacks native ROS, and reproducibility matters.  
**TRADE-OFF:** GUI/GPU/DDS and file permission handling require care.  
**IMPACT:** Keep Compose as the primary entry point, but make GUI/headless profiles explicit.

### Decision 5 — Container topology

**DECISION:** One ROS simulation container, separate backend, separate UI service/profile.  
**RATIONALE:** Keeps the ROS graph, Gazebo, Nav2, SLAM, custom nodes, and rosbridge cohesive while preserving service boundaries.  
**TRADE-OFF:** The ROS image is larger and has a broader process scope.  
**IMPACT:** Do not split Gazebo/Nav2/bridge until a concrete scaling or isolation need exists.

### Decision 6 — RViz

**DECISION:** Optional development/debugging tool.  
**RATIONALE:** Valuable for TF/Nav2 diagnosis, but Web UI is the application visualization and headless mode must not depend on RViz.  
**TRADE-OFF:** Developers have two visualization paths to maintain.  
**IMPACT:** Add only an optional launch/profile and configuration after the base Jazzy stack works.

### Decision 7 — Web/backend

**DECISION:** Keep the current conceptual architecture.  
**RATIONALE:** rosbridge/roslibjs and FastAPI solve separate concerns; Jazzy does not require a web rewrite.  
**TRADE-OFF:** Existing action/QoS workarounds remain and should be tested.  
**IMPACT:** Validate message/service/action contracts; separately redesign backend-driven Docker mode switching.

### Decision 8 — Development vs headless server

**DECISION:** One image with explicit graphical and headless profiles.  
**RATIONALE:** Same binaries and workspace should be tested in both environments.  
**TRADE-OFF:** Headless rendering requires EGL/GPU setup and additional acceptance tests.  
**IMPACT:** GUI must be optional; server mode must run without X11 and without RViz.

## 22. Proposed Target Architecture

### Development workstation

```text
Ubuntu 24.04 Noble host
│
├── Docker Compose: amr-sim
│   ├── ROS 2 Jazzy
│   ├── Gazebo Harmonic GUI
│   ├── custom AMR SDF/URDF and warehouse world
│   ├── Gazebo Sim differential drive
│   ├── Gazebo Sim LiDAR, IMU, camera
│   ├── ros_gz_bridge / ros_gz_sim
│   ├── robot_state_publisher
│   ├── SLAM Toolbox or Nav2
│   ├── custom AMR nodes
│   ├── rosbridge_server :8765
│   └── web_video_server :8080
│
├── Docker Compose: amr-backend
│   ├── FastAPI :3001
│   ├── SQLite
│   └── maps/data mounts
│
├── Web UI development server :3000
│
└── Optional RViz2
```

### Headless server

```text
Ubuntu 24.04 Noble server
└── Docker Compose headless profile
    ├── amr-sim
    │   ├── Gazebo Sim server/headless rendering
    │   ├── ROS 2 Jazzy/Nav2/SLAM/custom nodes
    │   ├── rosbridge :8765
    │   └── web_video_server :8080
    ├── amr-backend :3001
    └── web UI served remotely or by a static web server
```

### Data flow target

```text
Gazebo Sim
  ├── gz transport sensor topics
  ├── gz transport drive/odometry topics
  └── simulation clock
        │
        ▼
ros_gz_bridge / ros_gz_sim
        │
        ├── /scan, /imu, /camera/image_raw, /camera/camera_info
        ├── /cmd_vel, /odom, /clock
        └── ROS 2 TF and standard interfaces
                │
                ├── SLAM Toolbox
                ├── Nav2
                ├── custom mission/docking/battery nodes
                └── rosbridge → Vue UI
```

## 23. Repository Files That Must Eventually Change

### ROS distribution/container files

- `docker/Dockerfile`
- `docker/entrypoint.sh`
- `docker-compose.yml`
- `scripts/install_ros2.sh`
- `scripts/build_ws.sh`
- `scripts/docker_run.sh`
- `README.md`
- `docs/LAPORAN_PROGRESS.md`
- `INTEGRASI_ROBOT.txt`

### ROS package manifests

- `ros2_ws/src/amr_simulation/package.xml`
- `ros2_ws/src/amr_bringup/package.xml`
- `ros2_ws/src/amr_navigation/package.xml`
- `ros2_ws/src/amr_docking/package.xml`
- `ros2_ws/src/custom_interfaces/package.xml`

These should be updated for modern Gazebo package dependencies and complete direct imports. Exact Jazzy package names must be confirmed during implementation.

### Gazebo/model files

- `ros2_ws/src/amr_simulation/launch/sim.launch.py`
- `ros2_ws/src/amr_simulation/worlds/amr_world.world`
- `ros2_ws/src/amr_simulation/urdf/amr_robot.urdf`
- `ros2_ws/src/amr_simulation/models/aruco_dock/model.sdf`
- `ros2_ws/src/amr_simulation/models/aruco_dock/model.config`

Likely additions:

- `ros_gz_bridge` YAML configuration
- Gazebo Sim-compatible SDF/model resources
- optional bridge/launch helper

### Nav2/SLAM/docking files

- `ros2_ws/src/amr_navigation/config/nav2_params.yaml`
- `ros2_ws/src/amr_navigation/launch/navigation.launch.py`
- `ros2_ws/src/amr_simulation/config/slam_params.yaml`
- `ros2_ws/src/amr_simulation/launch/slam.launch.py`
- `ros2_ws/src/amr_docking/config/docking_params.yaml`
- `ros2_ws/src/amr_docking/scripts/docking_manager_node.py`
- `ros2_ws/src/amr_docking/scripts/aruco_detector_node.py`
- `ros2_ws/src/amr_navigation/scripts/mission_manager_node.py`
- `ros2_ws/src/amr_navigation/scripts/keepout_mask_server.py`

### Web/backend files expected to remain mostly stable

- `web-ui/src/composables/useROS.js`
- `web-ui/src/stores/robot.js`
- `backend/routers/maps.py`
- `backend/routers/mode.py`

`useROS.js` needs contract validation, not an automatic rewrite. `backend/routers/mode.py` needs a separate orchestration correction before production-quality mode switching.

## 24. Staged Migration Plan

### Phase 0 — Baseline and regression inventory

**Objective:** Freeze the current behavior contract before migration.

**Files/data:** current launch files, maps, topics/services/actions tables, Docker definitions, sample logs.

**Expected result:** a reproducible Humble baseline or a documented inability to run it.

**Validation:** record startup, `/tf`, `/scan`, `/odom`, `/map`, `/cmd_vel`, Nav2 goal, camera, map save, and custom docking behavior.

**Rollback:** no source change; retain current Git commit and image tag.

**Complexity:** Medium. Current ROS is not installed on the host, so baseline may require the existing image to be built first.

### Phase 1 — Jazzy/Noble Docker foundation

**Objective:** Build a Jazzy/Noble image with core ROS tools and a minimal `ros2_ws`.

**Files:** `docker/Dockerfile`, `docker/entrypoint.sh`, Compose, build/run scripts.

**Dependencies:** official `ros:jazzy-ros-base-noble`, Jazzy apt repository, colcon, rosdep.

**Expected result:** image builds and `ros2 doctor`/basic ROS commands run.

**Validation:** container starts, environment reports `ROS_DISTRO=jazzy`, `colcon list` sees all packages.

**Rollback:** keep the Humble Dockerfile/image under a separate baseline tag or branch.

**Complexity:** Low/Medium.

### Phase 2 — ROS package manifests and custom nodes

**Objective:** Make all custom packages resolve and build against Jazzy independently of Gazebo.

**Files:** package manifests, CMake install rules, Python scripts.

**Dependencies:** Jazzy standard messages, `custom_interfaces`, `cv_bridge`, Nav2 interfaces.

**Expected result:** `rosdep install` and `colcon build` work without broad desktop-package masking.

**Validation:** build package-by-package; run custom interface generation; import-check Python nodes.

**Rollback:** revert only manifest/build changes; no Gazebo changes yet.

**Complexity:** Medium.

### Phase 3 — Gazebo Sim/Harmonic world foundation

**Objective:** Load the warehouse world in Gazebo Harmonic without the robot.

**Files:** world SDF, model resource paths, Docker Gazebo dependencies, launch.

**Dependencies:** Harmonic and `ros_gz_sim`.

**Expected result:** world loads visually and collision geometry is correct.

**Validation:** GUI and headless server launch; resource path checks; no Classic plugin load errors.

**Rollback:** retain the original Classic world in baseline history.

**Complexity:** High.

### Phase 4 — Robot model and simulated sensors

**Objective:** Port the robot and preserve the ROS topic contract.

**Files:** URDF/SDF, model assets, bridge YAML, simulation launch.

**Dependencies:** Gazebo Sim systems, `ros_gz_bridge`, `robot_state_publisher`.

**Expected result:** robot spawns and publishes `/scan`, `/imu`, `/camera/image_raw`, `/odom`, `/clock`, and TF.

**Validation:** topic types, frame IDs, rates, timestamps, QoS, visual/collision checks.

**Rollback:** isolate model/bridge changes from Nav2 changes.

**Complexity:** High.

### Phase 5 — Nav2 Jazzy integration

**Objective:** Run Nav2 against the new Gazebo topic graph.

**Files:** `nav2_params.yaml`, `navigation.launch.py`, lifecycle and keepout node manifests.

**Dependencies:** Jazzy Nav2 binaries and the new odometry/scan/map topics.

**Expected result:** AMCL/Nav2 lifecycle activates, costmaps update, and goals move the robot.

**Validation:** startup, initial pose, global/local costmaps, planner/controller outputs, goal success, cancel.

**Rollback:** use a minimal Nav2 parameter file, then reintroduce custom layers one at a time.

**Complexity:** Medium/High.

### Phase 6 — SLAM integration

**Objective:** Restore mapping and map save/load.

**Files:** `slam_params.yaml`, `slam.launch.py`, map scripts.

**Dependencies:** Jazzy SLAM Toolbox, correct `/scan`, odom TF, `/clock`.

**Expected result:** robot maps the world and saves a standard YAML/PGM map.

**Validation:** occupancy map changes while moving; saved map loads in navigation mode.

**Rollback:** keep Nav2 navigation test independent of SLAM using committed maps.

**Complexity:** Medium.

### Phase 7 — Custom docking and ArUco

**Objective:** Restore the existing simulated docking contract.

**Files:** custom docking nodes, camera bridge, custom model, docking config/dependencies.

**Dependencies:** OpenCV/cv_bridge, camera topic, Nav2 approach action, odometry.

**Expected result:** station registration, approach, reverse docking, dock state, undock, cancel, and timeout work.

**Validation:** full state-machine test and collision-monitor recovery.

**Rollback:** disable docking while retaining navigation/SLAM.

**Complexity:** High.

### Phase 8 — rosbridge/backend/Web UI

**Objective:** Restore the web contract after ROS graph stabilization.

**Files:** `useROS.js`, UI store/components only if contracts changed; backend separately.

**Dependencies:** Jazzy rosbridge, web_video_server, custom interfaces.

**Expected result:** Web UI connects, visualizes, sends goals/teleop, saves maps, and controls missions.

**Validation:** WebSocket, QoS-latched map, action/service calls, camera stream, reconnect behavior.

**Rollback:** use CLI ROS smoke tests independent of UI.

**Complexity:** Medium.

### Phase 9 — RViz/debug tooling

**Objective:** Add optional RViz2 support for diagnostics.

**Files:** optional RViz config and launch/profile.

**Dependencies:** Jazzy `rviz2` and standard Nav2 displays.

**Expected result:** TF, map, scan, costmaps, paths, robot model, and goals can be inspected.

**Validation:** GUI-only diagnostic test; no dependency in headless mode.

**Rollback:** remove profile/config without affecting core simulation.

**Complexity:** Low/Medium.

### Phase 10 — Integration test suite

**Objective:** Automate the acceptance tests below.

**Files:** test scripts, Compose health checks, CI workflow if desired.

**Expected result:** startup and core graph failures are detected automatically.

**Validation:** clean checkout, build, launch, topic/action/service assertions, teardown.

**Rollback:** tests are additive and can be disabled without changing runtime.

**Complexity:** High.

### Phase 11 — Headless/server mode

**Objective:** Run the exact Jazzy image without a GUI.

**Files:** Compose profile, launch arguments, environment, documentation.

**Expected result:** Gazebo server/headless rendering, ROS graph, rosbridge, web video, backend, and remote UI work without X11.

**Validation:** run on a server/VM or local headless mode; verify camera if EGL is enabled.

**Rollback:** graphical development profile remains unchanged.

**Complexity:** Medium/High.

## 25. Acceptance Tests

The following tests must pass before declaring the migration complete.

### Build and startup

- Clean Docker build succeeds with no unresolved Jazzy rosdep keys.
- `ROS_DISTRO` reports `jazzy` inside the simulation container.
- `docker compose up` starts the simulation and backend without crash loops.
- Health check confirms the ROS graph is alive.
- `ros2 node list` includes Gazebo bridge/simulation, robot state publisher, custom nodes, and the selected SLAM/Nav2 stack.

### Gazebo

- Harmonic world loads without Classic plugin errors.
- Custom `aruco_dock` resources and materials resolve.
- Robot spawns exactly once at the requested pose.
- Robot collision geometry and visual geometry are present.
- GUI profile opens Gazebo on a supported display stack.
- Headless profile starts without X11 when headless rendering is configured.

### TF and clock

- `/clock` is published and all simulation nodes use simulation time.
- Required TF chain exists: `map → odom → base_footprint → base_link` when SLAM/Nav2 is active.
- Static sensor frames exist: LiDAR, IMU, camera, and camera optical frame.
- No duplicate or conflicting odometry TF broadcasters exist.

### Sensors

- `/scan` is `sensor_msgs/msg/LaserScan` with expected frame and nonzero samples.
- `/imu` is `sensor_msgs/msg/Imu` with expected frame and update rate.
- `/camera/image_raw` and camera info are published.
- Camera data reaches `aruco_detector_node.py`.
- Web video server can stream the camera topic.

### Motion and odometry

- `/cmd_vel` message type is explicitly chosen and consistent across UI, Nav2, bridge, and Gazebo.
- A forward command moves the robot forward.
- A reverse command moves it backward.
- Zero command stops it.
- `/odom` position and velocity update with correct frame IDs.
- Odometry TF does not jump or reverse unexpectedly.

### SLAM and maps

- SLAM Toolbox starts with the configured Jazzy launch file.
- Driving the robot changes `/map`.
- Map saver writes YAML/PGM to the expected mounted path.
- Saved map is discoverable by backend and UI.
- Navigation mode loads the saved map.

### Nav2

- All lifecycle nodes configure and activate.
- AMCL accepts `/initialpose`.
- Global/local costmaps update from `/scan`.
- Keepout mask updates from `/amr/keepout_zones`.
- Planner publishes a path.
- Controller publishes the selected velocity message.
- Robot reaches a valid goal.
- Invalid/blocked goals fail cleanly.
- Cancel returns the robot to zero velocity and clears UI state.

### Docking

- A dock station can be registered through `/station_config`.
- ArUco marker detection is received when the marker is visible.
- Approach navigation reaches the approach pose.
- Reverse docking stops at the configured threshold.
- `/dock_status` transitions through expected states.
- Cancel stops reverse motion.
- Timeout produces error and zero velocity.
- Collision monitor is restored after docking/cancel/error.
- Undock returns to the approach pose.

### Mission and custom interfaces

- `custom_interfaces` builds and is discoverable.
- `/mission_plan` accepts an action goal.
- Feedback reaches the UI.
- Sequential waypoint execution works.
- Manual confirmation works.
- Action cancellation works.

### Web and backend

- UI connects to Jazzy rosbridge WebSocket.
- Latched `/map` is received after UI connection.
- TF pose updates in the map view.
- Teleop publishes the selected `/cmd_vel` type.
- Navigation goal and initial pose work.
- Mission and docking services/actions work.
- Map upload/list/load/save works.
- Camera feed works.
- Reconnecting rosbridge clears stale TF and restores keepout state safely.
- Backend mode switching either works through a deliberately supported supervisor or is clearly disabled until redesigned.

### Headless

- No RViz process is required.
- No Gazebo GUI/X11 is required.
- ROS graph and Nav2 function.
- Web UI connects remotely.
- Camera stream works if headless rendering is part of the selected mode.

## 26. Open Questions and Unknowns

These items were not safely verifiable without installing/building Jazzy or running the migrated stack:

1. **[UNVERIFIED]** Exact availability and current branch behavior of every TurtleBot3 Jazzy/Gazebo Sim package needed by this custom robot model. The repository's custom URDF may not need the full TurtleBot3 Classic simulation package after the port.
2. **[UNVERIFIED]** Exact `ros_gz_bridge` message/QoS mapping for the selected Harmonic sensor systems and camera encoding.
3. **[UNVERIFIED]** Whether the current custom URDF can be converted directly or should be represented as SDF for Gazebo Sim while retaining a ROS `robot_description` URDF for TF.
4. **[UNVERIFIED]** Exact Jazzy Nav2 plugin loader acceptance for every current slash-style plugin string.
5. **[UNVERIFIED]** Whether current collision monitor parameters are accepted with identical semantics in the installed Jazzy Nav2 version.
6. **[UNVERIFIED]** Whether the custom docking node's lifecycle client and action behavior remain stable under Jazzy timing/executor behavior.
7. **[UNVERIFIED]** Whether the current rosbridge action protocol workaround behaves identically with the Jazzy rosbridge release.
8. **[UNVERIFIED]** Whether camera rendering works with the laptop's actual X11/XWayland/GPU stack and in headless EGL mode.
9. **[UNVERIFIED]** Whether Docker Compose backend mode switching is used in the intended workflow. Code inspection indicates a missing Docker execution surface inside the backend container.
10. **[UNVERIFIED]** Whether automated tests already exist outside tracked files. No test suite or CI workflow was found in the tracked repository.
11. **[UNVERIFIED]** Whether `opennav_docking` is intended to be active in this simulation or is legacy configuration. Current launch flow indicates the custom docking node is active instead.

## 27. Sources and Official Documentation

The following sources were consulted on 2026-09-17. URLs are included so the report remains reviewable independently of this session.

### ROS 2 and platform

1. ROS 2 Jazzy Ubuntu binary installation and Noble support:  
   https://docs.ros.org/en/jazzy/Installation/Alternatives/Ubuntu-Install-Binary.html
2. ROS 2 Jazzy release and supported platforms:  
   https://docs.ros.org/en/iron/Releases/Release-Jazzy-Jalisco.html
3. ROS 2 Humble release and supported platforms:  
   https://docs.ros.org/en/humble/Releases/Release-Humble-Hawksbill.html
4. REP-2000 ROS 2 releases and target platforms:  
   https://www.ros.org/reps/rep-2000.html
5. ROS 2 distributions and cross-distribution communication warning:  
   https://docs.ros.org/en/humble/Releases.html

### Docker

6. Official ROS Docker image tags, including `jazzy-ros-base-noble`:  
   https://hub.docker.com/_/ros
7. Official ROS Docker tag listing:  
   https://hub.docker.com/_/ros/tags?name=jazzy

### Gazebo

8. Gazebo Harmonic overview and supported Ubuntu platforms:  
   https://gazebosim.org/docs/harmonic/install/
9. Gazebo Harmonic Ubuntu binary installation:  
   https://gazebosim.org/docs/harmonic/install_ubuntu/
10. ROS 2 Jazzy/Harmonic integration and `ros_gz_bridge`:  
    https://gazebosim.org/docs/harmonic/ros2_integration/
11. Gazebo migration guide for ROS 2 packages using Gazebo Classic:  
    https://gazebosim.org/docs/all/migrating_gazebo_classic_ros2_packages/
12. Gazebo Sim demos for differential drive, camera, lidar, and IMU:  
    https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_sim_demos/README.md
13. Gazebo Classic EOL/archive notice:  
    https://github.com/ros-simulation/gazebo_ros_pkgs
14. Gazebo Classic EOL statement:  
    https://github.com/gazebosim/gazebo-classic
15. Gazebo Harmonic headless rendering:  
    https://gazebosim.org/api/sim/9/headless_rendering.html

### Nav2

16. Nav2 Jazzy quickstart and Gazebo change:  
    https://docs.nav2.org/jazzy/getting_started/quickstart/quickstart/
17. Nav2 migration guides:  
    https://docs.nav2.org/jazzy/configuration_and_development/migration_guides/
18. Nav2 Iron-to-Jazzy migration details:  
    https://docs.nav2.org/jazzy/configuration_and_development/migration_guides/iron/Iron/
19. Nav2 Jazzy Docker installation:  
    https://docs.nav2.org/jazzy/getting_started/build_and_install/docker_installation/
20. Nav2 Jazzy docking tutorial:  
    https://docs.nav2.org/jazzy/tutorials/general_tutorials/using_docking/
21. Nav2 Jazzy docking configuration:  
    https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/configuring_docking_server/

### SLAM Toolbox

22. SLAM Toolbox upstream repository:  
    https://github.com/SteveMacenski/slam_toolbox
23. SLAM Toolbox Jazzy package documentation/release path:  
    https://docs.ros.org/en/jazzy/p/slam_toolbox/

### Docking

24. Open Navigation docking repository:  
    https://github.com/open-navigation/opennav_docking
25. Open Navigation docking Jazzy package documentation:  
    https://docs.ros.org/en/ros2_packages/jazzy/api/opennav_docking/

### Web bridge and video

26. rosbridge_suite upstream repository and distro release notes:  
    https://github.com/RobotWebTools/rosbridge_suite
27. rosbridge v2 protocol specification:  
    https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md
28. rosbridge Jazzy package documentation:  
    https://docs.ros.org/en/jazzy/p/rosbridge_server/
29. web_video_server Jazzy documentation:  
    https://docs.ros.org/en/jazzy/p/web_video_server/

### TurtleBot3 reference

30. ROBOTIS TurtleBot3 simulation documentation:  
    https://emanual.robotis.com/docs/en/platform/turtlebot3/simulation/
31. ROBOTIS TurtleBot3 simulation repository:  
    https://github.com/ROBOTIS-GIT/turtlebot3_simulations

## FINAL RECOMMENDATION

**Should this repository migrate to ROS 2 Jazzy?**

**Yes.** The target should be a Jazzy-native simulation stack, because the eventual robot target is Jazzy, the development host is already Ubuntu 24.04, ROS cross-distribution communication is not guaranteed, and Gazebo Classic is deprecated/EOL.

Exact recommended stack:

- **Host OS:** Ubuntu 24.04 Noble
- **Container OS:** Ubuntu Noble through the official Jazzy image
- **ROS:** ROS 2 Jazzy
- **Gazebo:** Gazebo Harmonic / Gazebo Sim
- **Nav2:** Jazzy Nav2 binaries, then repository-specific parameter validation
- **SLAM:** Jazzy SLAM Toolbox
- **Docking:** custom Python simulated docking first; OpenNav docking as a later, separately validated integration
- **rosbridge:** Jazzy `rosbridge_suite`
- **Backend:** existing FastAPI + SQLite architecture, with mode orchestration redesigned separately
- **Web UI:** existing Vue + Pinia + Leaflet + roslibjs architecture
- **RViz:** optional development/debugging profile, not runtime-required
- **Docker topology:** one ROS simulation container plus separate backend and UI services
- **Development mode:** GUI Gazebo, optional RViz, Web UI, backend, and full acceptance checks
- **Headless/server mode:** Gazebo server/headless rendering, no RViz, remote Web UI, backend, and WebSocket/video endpoints

The migration must preserve the ROS-facing application contracts where possible, but it must explicitly port the Gazebo integration and validate Nav2, QoS, TF, clock, sensor, action, and docking behavior.

## IMPLEMENTATION READINESS

`READY FOR MIGRATION`

The architecture and staged plan are sufficiently defined to begin implementation after review. The following must be treated as implementation gates and not assumed:

- Harmonic world/model conversion passes.
- All simulated sensor topics and TF pass acceptance tests.
- Jazzy Nav2 config loads and navigates.
- SLAM maps and loads correctly.
- Custom docking passes its state-machine tests.
- rosbridge/Web UI contracts pass.
- Headless mode works without X11/RViz.
- Backend Docker mode switching is either fixed through a controlled supervisor or removed from the supported workflow.

Per the requested scope, this report stops before source migration. No source file, Dockerfile, Compose file, package manifest, launch file, URDF/SDF, Nav2 parameter, or runtime environment was modified by this audit.
