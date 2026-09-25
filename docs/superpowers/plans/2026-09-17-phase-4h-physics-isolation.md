# Phase 4H Minimal Differential-Drive Physics Isolation Implementation Plan

> **For agentic workers:** Execute this plan inline with checkpoints. Do not use Nav2, SLAM, AMCL, docking, ArUco, missions, Web UI integration, or cafe environment work.

**Goal:** Determine whether the intended wheel geometry and Gazebo Harmonic DiffDrive pass on a minimal chassis, then identify the first Cafe physical component that introduces instability without replacing the production candidate.

**Architecture:** Add a disposable diagnostic SDF/world/launch path under `amr_simulation` and keep `amr_robot_harmonic/model.sdf` unchanged unless the minimal chassis passes and a later ladder proves a production fix. Reuse the independent `gz model` versus ROS `/odom` probe with a configurable model name and preserve the existing thresholds.

**Tech Stack:** ROS 2 Jazzy, Gazebo Sim 8 / Harmonic, SDF 1.9, `ros_gz_bridge`, native Gazebo DiffDrive, Python `rclpy`, Docker.

## Global Constraints

- Repository scope is only the Cafe Service AMR ROS 2 Jazzy / Gazebo Harmonic project.
- Keep `amr_robot_harmonic/model.sdf` as the current production candidate.
- Do not commit, push, reset, clean, stash, or switch branches.
- Do not weaken the acceptance thresholds: ≤5% straight-motion error and ≤5° rotation error.
- Stop at Gate A if the minimal chassis fails.

### Task 1: Create diagnostic model and runtime path

**Files:**
- Create: `ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.sdf`
- Create: `ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.config`
- Create: `ros2_ws/src/amr_simulation/worlds/amr_physics_test.sdf`
- Create: `ros2_ws/src/amr_simulation/config/bridge_phase4h.yaml`
- Create: `ros2_ws/src/amr_simulation/launch/phase4h_minimal.launch.py`

**Interfaces:**
- Diagnostic model name: `amr_robot_physics_test`.
- Diagnostic ROS topics: `/cmd_vel`, `/odom`, and `/clock`.
- Diagnostic Gazebo topics: `/model/amr_robot_physics_test/cmd_vel` and `/model/amr_robot_physics_test/odometry`.
- The SDF contains one box chassis, two cylinder wheels, one low-friction spherical passive support, and one native DiffDrive system.

- [ ] Validate that the model contains no sensors, trays, upper structure, anti-tip spheres, decorative collision, or Cafe-specific geometry.
- [ ] Validate XML and package installation through the existing `install(DIRECTORY launch worlds config urdf models ...)` rule.

### Task 2: Make the probe reusable

**Files:**
- Modify: `scripts/phase4g_motion_probe.py`

**Interfaces:**
- Add `--model`, default `amr_robot`.
- Add `--cmd-topic`, default `/cmd_vel`.
- Add `--odom-topic`, default `/odom`.
- Preserve the existing default behavior and thresholds for the production Cafe model.

- [ ] Compile the probe with `python3 -m py_compile scripts/phase4g_motion_probe.py`.
- [ ] Confirm output records the selected model and still contains T1–T5 data.

### Task 3: Verify wheel semantics before motion testing

**Files:**
- Inspect: `ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.sdf`
- Reference: installed/official Gazebo Harmonic DiffDrive example.

- [ ] Record wheel link poses, cylinder local axis, joint axis, parent, child, and joint-frame meaning.
- [ ] Confirm `wheel_left_link` is at `y=+0.21 m`, `wheel_right_link` at `y=-0.21 m`, both centers at `z=0.09 m`, and both radii are `0.09 m`.
- [ ] Explain in the report why `+linear.x` rolls both wheels so chassis X increases and why `+angular.z` commands opposite wheel velocities for CCW rotation.
- [ ] Do not change the production model during this task.

### Task 4: Run Gate A

**Files:**
- Create: `PHASE_4H_PHYSICS_ISOLATION_REPORT.md`

- [ ] Run full rosdep and full colcon build in a disposable container.
- [ ] Launch `phase4h_minimal.launch.py` headless.
- [ ] Run three repeats each at the exact Phase 4G command durations and one zero-command settling test.
- [ ] Record independent ground pose, odometry, displacement error, yaw error, pure-turn XY displacement, and repeatability.
- [ ] Capture `docker stats --no-stream`, `free -h`, and `git diff --check`.
- [ ] If Gate A fails, mark the diagnostic result `BLOCKED`, identify the likely wheel/joint/contact/configuration issue, and stop without touching Cafe physics.

### Task 5: Controlled reintroduction only if Gate A passes

**Files:**
- Modify or create diagnostic-only candidates under `ros2_ws/src/amr_simulation/models/`.
- Update: `PHASE_4H_PHYSICS_ISOLATION_REPORT.md`

- [ ] Test candidates in order: A minimal supports, B Cafe chassis mass/dimensions, C lower structural body, D vertical supports, E tray 1, F tray 2, G tray 3/top structure, H production caster arrangement, I anti-tip supports.
- [ ] Run the same short forward, reverse, CCW, CW, and stop matrix after every candidate.
- [ ] Stop the ladder at the first candidate that becomes unstable.
- [ ] Record caster contact, anti-tip clearance/contact, body roll/pitch, left/right normal-load symmetry, wheel contact, and CW/CCW symmetry.

### Task 6: Production fix gate

**Files:**
- Modify only if proven: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Update: `PHASE_4H_PHYSICS_ISOLATION_REPORT.md`

- [ ] Apply only the minimum fix demonstrated by the ladder.
- [ ] Re-run the original production Phase 4G three-repeat matrix.
- [ ] Run sensor regression only after production mechanical PASS.
- [ ] If production remains below threshold, mark final recommendation `BLOCKED` and stop.

### Task 7: Final report and safety verification

- [ ] Include all required Phase 4H report sections: minimal architecture, semantics, Gate A, ladder, first failing component, root cause, production comparison, stop behavior, repeatability, sensor regression, rosdep/colcon, resource usage, files, diff stat, warnings, risks, and final `PASS` / `BLOCKED` recommendation.
- [ ] Verify no Phase 5 system was launched.
- [ ] Verify no prohibited Git operation occurred.
- [ ] Run XML parse, Python compile, `git diff --check`, and `docker compose config --quiet`.
