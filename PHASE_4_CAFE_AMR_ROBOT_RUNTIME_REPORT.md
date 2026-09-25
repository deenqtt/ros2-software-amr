# Phase 4 Cafe AMR Robot Runtime Report

**Date:** 2026-09-17  
**ROS baseline:** ROS 2 Jazzy / Ubuntu 24.04 Noble  
**Simulator:** Gazebo Sim 8.15.0 / Harmonic  
**Scope:** robot runtime foundation only; Nav2, SLAM, docking, Web UI, RViz, and people simulation are out of scope.

## 1. Executive summary

The Phase 4 Cafe Service AMR model is implemented as a native Gazebo Sim
runtime with a three-tray body, DiffDrive, odometry/TF, GPU LiDAR, IMU, and a
forward-facing RGB camera. ROS-facing names remain frozen. The headless
runtime spawned successfully and all requested sensor bridges produced live
messages.

The ROS command and odometry path is operational. A physical-pose correlation
probe found residual wheel/contact behavior that does not yet match odometry
well enough for a full physical-motion PASS. Nav2 should wait for that
calibration rather than treating `/odom` alone as proof of physical fidelity.

## 2. Product definition

This is a generic Cafe Service AMR simulation: compact mobile base, three
serving trays, forward perception, future payload attachment points, and a
charging-dock-ready world. It is not a commercial robot replica and does not
simulate payload objects, people, or sensor drivers.

## 3. Pre-write Git state

Before Phase 4 changes, the repository was on `main`, tracking `origin/main`,
with the approved Phase 0/1, Phase 2, and Phase 3 migration work uncommitted.
No commit, push, reset, clean, stash, or branch switch was performed during
Phase 4.

## 4. Existing robot audit

The previous active model was a Gazebo Sim foundation model, not a complete
Cafe AMR. The old Classic world/URDF remain inactive rollback/reference
artifacts. The legacy URDF mounted the camera toward the rear, so existing
ArUco/docking behavior cannot be assumed compatible with the new forward camera
orientation.

## 5. Physical design decisions

The SDF is authoritative for Gazebo geometry, collisions, inertials, joints,
motion systems, and sensors. The Xacro is a synchronized structural ROS
description used by `robot_state_publisher` for fixed TF only. Native Gazebo
DiffDrive owns dynamic `odom → base_footprint`.

The main camera points forward. The ROS frame chain and camera topics are not
renamed. A separate rear docking camera is reserved as a future extension and
is not implemented.

## 6. Dimensions

| Parameter | Implemented value |
| --- | ---: |
| Body width | 0.54 m |
| Body length | 0.62 m |
| Overall height | approximately 1.22 m |
| Ground clearance | 0.045 m |
| Drive wheel radius | 0.09 m |
| Wheel separation | 0.42 m |
| Tray size | 0.46 × 0.42 m |
| Tray heights | 0.48, 0.76, 1.04 m |

## 7. Tray design

Three tray links contain primitive serving surfaces and simple front/rear/side
lips. `tray_1_payload`, `tray_2_payload`, and `tray_3_payload` are empty future
attachment frames. Payload mass and payload collision are deliberately deferred.

## 8. Mass, inertia, and centre of mass

The chassis carries 18.0 kg and has the lowest major centre of mass. The SDF
contains positive inertia matrices for all physical links. Parsed link masses
sum to **24.7 kg** for the empty model, including trays, top cap, wheels,
casters, anti-tip supports, and sensor housings. This is an explicit simulation
assumption, not a measured hardware specification.

## 9. Collision architecture

Chassis and tray/support collisions use boxes and cylinders. Wheels use
cylinders. Primary casters use spheres with low-friction contact. Four raised
corner spheres act as low-friction anti-tip supports; they are not sensors and
do not publish odometry.

## 10. Sensor placement

| Sensor | Frame | Placement / configuration |
| --- | --- | --- |
| LiDAR | `base_scan` | body centre, z≈0.25 m, 270° horizontal FOV |
| IMU | `imu_link` | body centre, z≈0.25 m, 100 Hz |
| Main RGB camera | `camera_link` | front upper body, x=0.255 m, z≈0.98 m, 15 Hz |

## 11. Visual model implementation

The model uses a low chassis, four vertical tray supports, three visible
serving levels, a top cap, wheels, caster supports, and sensor housings. The
visual language is intentionally simple enough for a 16 GB-class development
laptop while still making the Cafe AMR geometry legible in Gazebo GUI.

## 12. Stability validation

The model remained spawned and upright during idle and low-speed runtime
checks. The raised corner supports were added after a first rotation probe
showed excessive roll from a tall tray stack supported only along the centre
line. High-speed or loaded-payload stability is not validated.

## 13. DiffDrive

The native `gz::sim::systems::DiffDrive` system uses
`wheel_left_joint`, `wheel_right_joint`, radius 0.09 m, separation 0.42 m,
linear limits ±0.6 m/s, angular limits ±1.2 rad/s, and odometry frequency
30 Hz. No Gazebo Classic drive plugin is loaded.

## 14. Motion validation

`/cmd_vel` is bridged from ROS `geometry_msgs/msg/Twist` to the model command
topic. Controlled low-speed commands changed native odometry for both forward
and rotational commands. The physical-pose probe still showed residual
wheel/contact mismatch, so full ground-truth motion fidelity remains a gate
before Nav2.

## 15. Odometry

The bridged `/odom` message was observed as `nav_msgs/msg/Odometry` with
`frame_id=odom` and `child_frame_id=base_footprint`. A controlled probe changed
the odometry position by approximately 0.2–0.36 m under low-speed forward
commands and changed yaw under rotational commands.

## 16. TF

`/tf` contains one dynamic `odom → base_footprint` transform from DiffDrive.
`/tf_static` contains the fixed body, tray, sensor, and camera transforms from
`robot_state_publisher`. No second dynamic odometry owner was added.

## 17. Robot description

`amr_robot_harmonic.urdf.xacro` converts successfully and publishes the
structural description. The authoritative physics remains in SDF; Xacro is not
used to duplicate Gazebo sensors or DiffDrive.

## 18. LiDAR

The native `gpu_lidar` publishes 720 horizontal samples from -135° to +135°,
range 0.12–12.0 m, at 10 Hz. A live ROS sample had `frame_id=base_scan`, 720
range values, and visible wall/shelf returns.

## 19. IMU

The native IMU system publishes through `ros_gz_bridge` as
`sensor_msgs/msg/Imu`. A live sample had `frame_id=imu_link` and approximately
9.8 m/s² gravity on the Z axis. Measured runtime rate was approximately 99 Hz.

## 20. Camera

The main camera is physically mounted at the front and publishes to the
unchanged ROS topics `/camera/image_raw` and `/camera/camera_info`. The image
sample was `640×480`, `rgb8`, with `camera_rgb_optical_frame`.

## 21. Headless camera

Headless Gazebo server mode produced live image and camera-info messages. The
observed image rate was approximately 14–15 Hz. No ArUco detector was launched.

## 22. Bridge table

| ROS topic | Gazebo topic | ROS type | Direction |
| --- | --- | --- | --- |
| `/clock` | `/clock` | `rosgraph_msgs/msg/Clock` ↔ `gz.msgs.Clock` | GZ → ROS |
| `/cmd_vel` | `/model/amr_robot/cmd_vel` | `geometry_msgs/msg/Twist` ↔ `gz.msgs/Twist` | ROS → GZ |
| `/odom` | `/model/amr_robot/odometry` | `nav_msgs/msg/Odometry` ↔ `gz.msgs.Odometry` | GZ → ROS |
| `/tf` | `/model/amr_robot/tf` | `tf2_msgs/msg/TFMessage` ↔ `gz.msgs/Pose_V` | GZ → ROS |
| `/scan` | `/model/amr_robot/scan` | `sensor_msgs/msg/LaserScan` ↔ `gz.msgs.LaserScan` | GZ → ROS |
| `/imu` | `/model/amr_robot/imu` | `sensor_msgs/msg/Imu` ↔ `gz.msgs.IMU` | GZ → ROS |
| `/camera/image_raw` | `/model/amr_robot/camera/image_raw` | `sensor_msgs/msg/Image` ↔ `gz.msgs.Image` | GZ → ROS |
| `/camera/camera_info` | `/model/amr_robot/camera/camera_info` | `sensor_msgs/msg/CameraInfo` ↔ `gz.msgs.CameraInfo` | GZ → ROS |

## 23. Contract impact

The frozen ROS-facing topics and frames are preserved. The only intentional
physical change is camera direction: rear legacy mounting is replaced by a
forward-facing main camera. The old docking behavior is not considered
behaviorally compatible until its observation-direction assumptions are audited.

## 24. Resource usage by stage

The final headless full-suite snapshot was approximately **493 MiB container
memory**, **110% CPU** on the host accounting view, and 87 processes. Host
memory during testing was constrained, with approximately 0.9 GiB available and
4 GiB swap in use. Per-stage isolated resource snapshots were not collected;
future performance work should measure robot-only, motion, LiDAR/IMU, and
camera stages separately.

## 25. rosdep

The earlier full Jazzy/Noble workspace rosdep gate resolved all active package
dependencies after removing stale active Gazebo Classic declarations. Phase 4
uses packages already present in that gate: `ros_gz_sim`, `ros_gz_bridge`,
`robot_state_publisher`, `xacro`, `nav_msgs`, `sensor_msgs`,
`geometry_msgs`, `tf2_msgs`, and `rosgraph_msgs`.

## 26. colcon

The container build completed successfully after each Phase 4 runtime model
revision. The latest build summary was five packages finished, including
`amr_simulation`, `custom_interfaces`, `amr_docking`, `amr_navigation`, and
`amr_bringup`.

## 27. Final regression

Headless launch, entity creation, bridge creation, `/clock`, `/odom`, `/tf`,
`/tf_static`, `/scan`, `/imu`, image, and camera-info checks were rerun after
the final SDF edits. The active launch path contains no Classic Gazebo plugin.

## 28. Errors and warnings

No model parse or invalid-inertia error remained in the final spawn. Gazebo
prints parser warnings for the supported `gz_frame_id` extension because it is
not part of the base SDF schema. It also emitted display-authorization notices
in server mode while camera rendering initialized; image messages still flowed
headlessly. These are documented follow-up items, not silently ignored.

## 29. Remaining Classic references

The old `.world`, legacy URDF, and historical package references remain for
rollback/audit documentation. They are not active inputs to the Phase 4 launch
path. No Classic `libgazebo_ros_*` plugin is loaded by the active model/world.

## 30. Cafe future requirements

Future phases should add cafe tables/chairs, kitchen and pickup zones, charging
dock geometry, narrow-corridor tests, dynamic people, multi-stop mission
semantics, tray/payload state, speed limiting, collision behavior, and recovery
logic. These requirements are intentionally not implemented here.

## 31. Deferred work

ArUco runtime, docking redesign, legacy rear-camera assumption audit, optional
rear docking camera, Nav2, SLAM, RViz, Web UI integration, payload objects,
people simulation, and physical sensor-driver integration remain deferred.

## 32. Git diff stat

The worktree includes the approved uncommitted Phase 0/1–3 changes in addition
to Phase 4. A final `git diff --stat` must therefore be read as a cumulative
worktree statistic, not a Phase-4-only statistic. No commit or push was made.

## 33. Validation matrix

| Gate | Status |
| --- | --- |
| Cafe multi-tray visual model | PASS |
| SDF/XML parse | PASS |
| Entity spawn | PASS |
| ROS-Gazebo bridge startup | PASS |
| `/clock` | PASS |
| `/cmd_vel` bridge | PASS |
| `/odom` type/frame/live data | PASS |
| Dynamic `odom → base_footprint` TF | PASS |
| Fixed camera TF chain | PASS |
| LiDAR `/scan` type/frame/rate | PASS |
| IMU `/imu` type/frame/rate | PASS |
| Forward camera image | PASS |
| Camera info dimensions/frame | PASS |
| Headless image flow | PASS |
| Physical pose vs odometry correlation | BLOCKED |
| High-speed/loaded stability | NOT TESTED |
| ArUco runtime | DEFERRED |
| Docking behavior | DEFERRED |
| Nav2 | DEFERRED |
| SLAM | DEFERRED |
| RViz | DEFERRED |
| Web UI integration | DEFERRED |
| Dynamic people | DEFERRED |

## 34. Phase 5 recommendation

Do not start Nav2 yet. First isolate and calibrate the wheel/contact model until
low-speed ground-truth pose agrees with `/odom` for forward, reverse, and
rotation commands. After that gate passes, proceed to Nav2/SLAM integration with
the existing ROS contract. Docking remains a later phase and should audit the
forward-camera behavior before deciding whether to add the reserved rear camera.
