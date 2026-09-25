# Phase 4G Physical Motion Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Calibrate the native Gazebo Sim physical wheel/contact model so independent Gazebo ground truth agrees with `/odom` at low speed before Phase 5 navigation.

**Architecture:** Use a headless Python/rclpy probe to publish `/cmd_vel`, subscribe to `/odom`, and query independent world pose through `gz model -m amr_robot -p`. Run the fixed T1–T5 matrix before and after one mechanical change at a time; do not alter odometry numerically to hide contact errors.

**Tech Stack:** ROS 2 Jazzy, Gazebo Sim 8/Harmonic, `rclpy`, `geometry_msgs`, `nav_msgs`, Docker, Python standard library.

## Global Constraints

- Preserve body dimensions, mass, wheel radius, and wheel separation unless test evidence identifies a mechanical error.
- Do not start Nav2, SLAM Toolbox, AMCL, docking, ArUco, Web UI, mission integration, or cafe-world redesign.
- Ground truth must come from Gazebo world/model state, not from DiffDrive odometry or a derivative of it.
- Run headless and repeat forward, reverse, CCW, and CW tests three times when practical.
- Do not commit, push, reset, clean, stash, or switch branches.
- Stop with BLOCKED if realistic physics cannot meet the acceptance thresholds.

---

### Task 1: Capture repository state and add the reproducible probe

**Files:**
- Create: `scripts/phase4g_motion_probe.py`
- Read: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Read: `ros2_ws/src/amr_simulation/config/bridge_phase4.yaml`

- [ ] Record `git status`, `git branch --show-current`, `git rev-parse HEAD`, and `git diff --stat` in the Phase 4G report notes.
- [ ] Implement a probe that publishes finite-rate Twist commands, samples `/odom`, calls `gz model -m amr_robot -p`, converts quaternion yaw, and writes JSON results containing start/final poses and errors.
- [ ] Run `python3 -m py_compile scripts/phase4g_motion_probe.py` before any SDF change.

### Task 2: Run the independent baseline matrix

**Files:**
- Verify: `scripts/phase4g_motion_probe.py`
- Create: `/tmp/phase4g-baseline.json` inside the disposable test container

- [ ] Start the current model headless in a disposable Docker container.
- [ ] Run T1 forward at `linear.x=+0.20` m/s, T2 reverse at `-0.20` m/s, T3 CCW at `+0.40` rad/s, T4 CW at `-0.40` rad/s, and T5 zero-command settle.
- [ ] Repeat T1–T4 three times and capture independent Gazebo start/final pose, `/odom` start/final pose, translational error, yaw error, and stop residual.
- [ ] Inspect wheel/caster/anti-tip link positions and SDF contact/friction values before proposing a fix.

### Task 3: Form and test one mechanical hypothesis

**Files:**
- Modify only the evidence-supported SDF area in `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`.

- [ ] Compare the baseline against wheel geometry, joint axis/placement, caster clearance, anti-tip clearance, friction, mass/inertia, and physics timing.
- [ ] State one root-cause hypothesis in the report before editing.
- [ ] Apply the smallest single mechanical correction.
- [ ] Rebuild and rerun the same matrix; retain the previous JSON results for before/after comparison.

### Task 4: Repeat until accepted or blocked

**Files:**
- Modify: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf` only when a new hypothesis is supported.
- Modify: `PHASE_4G_MOTION_CALIBRATION_REPORT.md`

- [ ] Require forward/reverse direction correctness, stable CCW/CW, reliable stop, no obvious tipping, and no severe caster or anti-tip drag.
- [ ] Require translation error ≤5% for approximately 1 m tests and yaw error ≤5° for approximately 90° tests.
- [ ] Stop and mark BLOCKED if realistic contact cannot reach the thresholds after evidence-led hypotheses.

### Task 5: Sensor, performance, and final regression

**Files:**
- Verify: `ros2_ws/src/amr_simulation/launch/sim.launch.py`
- Verify: `docs/ROS_INTERFACE_CONTRACT.md`
- Modify: `docs/JAZZY_DEPENDENCY_STATUS.md` only if evidence requires a Phase 4G note.

- [ ] Recheck `/clock`, `/cmd_vel`, `/odom`, `/tf`, `/tf_static`, `/scan`, `/imu`, `/camera/image_raw`, and `/camera/camera_info`.
- [ ] Capture `docker stats --no-stream` and `free -h` without launching GUI.
- [ ] Run full `rosdep install --from-paths src --ignore-src -y --rosdistro jazzy` and `colcon build --symlink-install`.
- [ ] Run XML/Xacro/shell syntax and `git diff --check` verification.
- [ ] Remove disposable test containers and record final `git diff --stat`.

### Task 6: Write the required report and stop gate

**Files:**
- Create: `PHASE_4G_MOTION_CALIBRATION_REPORT.md`

- [ ] Include all 31 required sections, baseline and final tables, individual repeat results, root cause, files changed, warnings, resource use, and an explicit PASS or BLOCKED recommendation.
- [ ] Do not start Phase 5 automatically; wait for explicit approval after reporting.
