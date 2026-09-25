# Phase 4 Cafe AMR Runtime Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Evolve the Phase 3 plugin-free AMR foundation into a lightweight Cafe Service AMR with three trays, stable differential-drive motion, odometry/TF, LiDAR, IMU, and a forward-facing RGB camera while preserving the ROS interface contract.

**Architecture:** Keep Gazebo Sim SDF authoritative for physical geometry, collisions, inertials, joints, and sensors. Use Gazebo Sim native systems for motion and sensing, and `ros_gz_bridge` as the ROS compatibility boundary. Use a synchronized minimal URDF/Xacro plus `robot_state_publisher` only for structural TF that is not already owned by Gazebo.

**Tech Stack:** ROS 2 Jazzy, Ubuntu Noble, Gazebo Sim 8/Harmonic, SDF 1.9, `ros_gz_sim`, `ros_gz_bridge`, `nav_msgs`, `sensor_msgs`, `robot_state_publisher`, Docker Compose.

## Global Constraints

- Preserve the existing ROS-facing names: `/cmd_vel`, `/odom`, `/scan`, `/imu`, `/camera/image_raw`, `/camera/camera_info`.
- Preserve structural frames: `base_footprint`, `base_link`, `base_scan`, `imu_link`, `camera_link`, `camera_rgb_frame`, `camera_rgb_optical_frame`.
- The main camera points forward; do not add a rear camera in Phase 4.
- Audit and document that legacy ArUco/docking behavior may assume a rear camera; docking behavior remains deferred.
- Do not start Nav2, SLAM, docking, mission logic, Web UI integration, RViz, or dynamic people simulation.
- Keep visual geometry moderately detailed and all primary collisions primitive/simple.
- Keep the default runtime headless and suitable for a 16 GB-class development laptop.
- Do not modify, delete, reset, clean, stash, commit, push, or switch branches.
- Run an independent runtime gate after each stage before starting the next stage.

## File map

- Modify `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`: authoritative cafe AMR geometry, joints, inertials, Gazebo systems, and sensors.
- Create `ros2_ws/src/amr_simulation/urdf/amr_robot_harmonic.urdf.xacro`: structural ROS description and frame chain synchronized with the SDF.
- Modify `ros2_ws/src/amr_simulation/launch/sim.launch.py`: start the model, `robot_state_publisher`, and the required bridge mappings without activating later application nodes.
- Create `ros2_ws/src/amr_simulation/config/bridge_phase4.yaml`: explicit Gazebo↔ROS mappings for clock, velocity, odometry, LiDAR, IMU, image, and camera info.
- Modify `ros2_ws/src/amr_simulation/package.xml`: declare the Phase 4 launch, description, message, bridge, and image dependencies.
- Modify `ros2_ws/src/amr_simulation/CMakeLists.txt`: install the Xacro and bridge configuration.
- Modify `docker/Dockerfile`, `docker/entrypoint.sh`, and `docker-compose.yml` only if headless camera rendering or dependency installation requires it.
- Modify `docs/ROS_INTERFACE_CONTRACT.md`: record forward camera orientation, Phase 4 ownership, and docking-camera caveat without renaming interfaces.
- Modify `docs/JAZZY_DEPENDENCY_STATUS.md`: record validated Phase 4 runtime dependencies.
- Create `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`: required evidence and final gate report.

### Task 1: Audit and freeze physical design parameters

**Files:**
- Read: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Read: `ros2_ws/src/amr_simulation/urdf/amr_robot.urdf`
- Read: `ros2_ws/src/amr_simulation/worlds/amr_world.sdf`
- Read: `docs/ROS_INTERFACE_CONTRACT.md`
- Create: `docs/superpowers/designs/2026-09-17-cafe-amr-physical-design.md`

- [ ] Record chosen envelope: width 0.54 m, length 0.62 m, total height 1.22 m, ground clearance 0.045 m, wheel radius 0.09 m, wheel separation 0.42 m.
- [ ] Record three tray dimensions of 0.46 m × 0.42 m and tray heights 0.48 m, 0.76 m, and 1.04 m.
- [ ] Record the design rationale: low battery/chassis mass, broad base, narrow cafe clearance, usable tray spacing, and forward sensor visibility.
- [ ] Record attachment frames `tray_1_payload`, `tray_2_payload`, and `tray_3_payload` as future extension points only.
- [ ] Record front camera orientation and the possible future `rear_docking_camera_link` extension without implementing it.

### Task 2: Implement the cafe AMR physical model (Phase 4A)

**Files:**
- Modify: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Modify: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.config`

- [ ] Replace the TurtleBot-sized body with a chassis, vertical supports, three tray visuals, tray edge collisions, sensor housings, drive wheels, and caster/support wheels.
- [ ] Use primitive collision shapes for the chassis, supports, trays, and sensor housings; keep mesh geometry visual-only.
- [ ] Define realistic masses and positive-definite inertias with most mass in the low chassis.
- [ ] Keep drive joints named `wheel_left_joint` and `wheel_right_joint`; add `base_footprint`, `base_link`, `base_scan`, `imu_link`, `camera_link`, `camera_rgb_frame`, and `camera_rgb_optical_frame`.
- [ ] Add future payload attachment links with negligible placeholder geometry only if they do not affect collision or dynamics.
- [ ] Parse SDF and run Phase 4A headless and GUI spawn tests before adding motion.

### Task 3: Add structural ROS description and launch ownership

**Files:**
- Create: `ros2_ws/src/amr_simulation/urdf/amr_robot_harmonic.urdf.xacro`
- Modify: `ros2_ws/src/amr_simulation/launch/sim.launch.py`
- Modify: `ros2_ws/src/amr_simulation/CMakeLists.txt`
- Modify: `ros2_ws/src/amr_simulation/package.xml`

- [ ] Define the same frame relationships in Xacro: `base_footprint → base_link → base_scan`, `imu_link`, and `camera_link → camera_rgb_frame → camera_rgb_optical_frame`.
- [ ] Use `robot_state_publisher` for fixed structural TF only; do not duplicate dynamic `odom → base_footprint`.
- [ ] Launch the Xacro-derived `robot_state_publisher` with `use_sim_time`.
- [ ] Keep the SDF as the physics/visual/sensor authority and document the split.
- [ ] Verify `/robot_description`, `/tf_static`, and the expected fixed frame chain.

### Task 4: Add Gazebo Sim DiffDrive and ROS command bridge (Phase 4B)

**Files:**
- Modify: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Create: `ros2_ws/src/amr_simulation/config/bridge_phase4.yaml`
- Modify: `ros2_ws/src/amr_simulation/launch/sim.launch.py`

- [ ] Add the native Gazebo Sim DiffDrive system using `wheel_left_joint`, `wheel_right_joint`, wheel radius 0.09 m, and wheel separation 0.42 m.
- [ ] Configure the Gazebo command topic and bridge it bidirectionally to `/cmd_vel` as `geometry_msgs/msg/Twist`.
- [ ] Do not load `libgazebo_ros_diff_drive.so` or any Classic plugin.
- [ ] Publish low-speed commands in a headless test and verify forward, stop, rotation, and stop behavior.

### Task 5: Add odometry and TF (Phase 4C)

**Files:**
- Modify: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Modify: `ros2_ws/src/amr_simulation/config/bridge_phase4.yaml`
- Modify: `ros2_ws/src/amr_simulation/launch/sim.launch.py`

- [ ] Configure DiffDrive odometry output and bridge it to `/odom` as `nav_msgs/msg/Odometry`.
- [ ] Set `frame_id=odom` and `child_frame_id=base_footprint` in the Gazebo system.
- [ ] Ensure one dynamic owner for `odom → base_footprint`; keep robot_state_publisher fixed-only.
- [ ] Compare short controlled Gazebo displacement and odometry displacement for forward and rotation tests.
- [ ] Verify timestamps advance with simulation time and TF lookup succeeds.

### Task 6: Add LiDAR (Phase 4D)

**Files:**
- Modify: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Modify: `ros2_ws/src/amr_simulation/config/bridge_phase4.yaml`

- [ ] Add one native Gazebo Sim 2D LiDAR at `base_scan`, height 0.25 m, 270° horizontal FOV, 720 samples, 0.12–12.0 m range, and 10 Hz.
- [ ] Bridge its Gazebo scan to `/scan` as `sensor_msgs/msg/LaserScan`.
- [ ] Validate type, frame, rate, and scan response near the existing world walls/shelves while moving and rotating.

### Task 7: Add IMU (Phase 4E)

**Files:**
- Modify: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Modify: `ros2_ws/src/amr_simulation/config/bridge_phase4.yaml`

- [ ] Add one native Gazebo Sim IMU near the chassis center at `imu_link`, update rate 100 Hz.
- [ ] Bridge its Gazebo IMU message to `/imu` as `sensor_msgs/msg/Imu`.
- [ ] Validate type, frame, rate, gravity/acceleration fields, and angular velocity during rotation.

### Task 8: Add forward RGB camera (Phase 4F)

**Files:**
- Modify: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Modify: `ros2_ws/src/amr_simulation/config/bridge_phase4.yaml`
- Modify: `ros2_ws/src/amr_simulation/launch/sim.launch.py`
- Modify: `docker-compose.yml` only if rendering environment needs a declared setting

- [ ] Add one forward-facing RGB camera at `camera_link`, approximately 0.98 m high, 640×480, 15 FPS, and a conservative horizontal FOV.
- [ ] Preserve `camera_link → camera_rgb_frame → camera_rgb_optical_frame`; use a ROS optical-axis rotation without renaming frames.
- [ ] Bridge image data to `/camera/image_raw` and camera metadata to `/camera/camera_info`.
- [ ] Use Gazebo headless rendering support so image flow works without GUI.
- [ ] Do not start `aruco_detector_node`; document that old docking may assume rear observation and may require a future rear camera.
- [ ] Validate image type, dimensions, encoding, camera-info dimensions, and rate in headless mode.

### Task 9: Documentation and cafe future requirements

**Files:**
- Modify: `docs/ROS_INTERFACE_CONTRACT.md`
- Modify: `docs/JAZZY_DEPENDENCY_STATUS.md`
- Create: `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`

- [ ] Document every selected dimension, mass/inertia assumption, sensor position, and SDF/URDF ownership rule.
- [ ] Add the explicit bridge table for clock, command, odometry, LiDAR, IMU, image, and camera info.
- [ ] Document cafe future requirements: tables, chairs, kitchen/pickup, charging dock, narrow corridors, people, multi-stop missions, payload state, and safety behaviors.
- [ ] Document the forward-camera decision and legacy docking-camera caveat.
- [ ] Record all resource snapshots from robot-only, motion/odom, LiDAR, IMU, and camera stages.

### Task 10: Full regression and stop gate

**Files:**
- Verify: all Phase 4 files and Docker runtime.

- [ ] Run full Jazzy rosdep and full colcon build.
- [ ] Run headless Harmonic startup, physical stability, `/clock`, `/cmd_vel`, motion, `/odom`, TF, `/scan`, `/imu`, image, and camera-info tests.
- [ ] Run GUI smoke where display access permits.
- [ ] Search active launch/model files for Classic plugin references.
- [ ] Run `git diff --check`, collect `git diff --stat`, and verify no test containers remain.
- [ ] Mark only evidence-backed results as PASS; use FAIL, BLOCKED, DEFERRED, or NOT TESTED for everything else.
- [ ] Stop after Phase 4F and report the Phase 5 recommendation without implementing Phase 5.
