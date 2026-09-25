# Phase 4K Directional Resistance Investigation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Identify the physical cause of production CW/CCW asymmetry and post-stop displacement, then apply at most one evidence-backed production fix and rerun the Phase 4 motion gate.

**Architecture:** Keep the production ROS contract and Phase 4J caster correction frozen while adding diagnostic-only joint-state and high-resolution probe instrumentation. Use disposable SDF candidates for mirror and caster A/B experiments; only promote a change after a causal result.

**Tech Stack:** ROS 2 Jazzy, Gazebo Sim 8/Harmonic, DART physics, native Gazebo DiffDrive, `ros_gz_bridge`, Python probe/tests, SDF/XML/YAML, Docker.

## Global Constraints

- Work only in `/home/deden/Documents/my-project/ros2-software-amr`.
- Do not reset, clean, stash, commit, push, or switch branch.
- Do not start Nav2, SLAM, AMCL, docking, ArUco, missions, Web UI integration, payload simulation, or Cafe-world redesign.
- Preserve wheel radius `0.09 m`, wheel separation `0.42 m`, wheel axes, DiffDrive odometry, production mass/inertia/COM, ROS topics, ROS frames, sensors, and the Phase 4J caster collision correction unless direct evidence proves one is the cause.
- No artificial angular multiplier, fake odometry scaling, or direction-specific compensation.
- Production changes are forbidden until disposable experiments establish causality.
- Use statuses only from `PASS`, `FAIL`, `BLOCKED`, `DEFERRED`, and `NOT TESTED`.

## Files and responsibilities

- Modify `scripts/phase4g_motion_probe.py` only for diagnostic-only measurement fields and high-resolution windows.
- Create `scripts/phase4k_joint_state_probe.py` only if runtime joint-state capture cannot be kept focused in the existing probe; subscribe to the diagnostic Gazebo joint-state topic without changing application topics.
- Create disposable models/configs under `ros2_ws/src/amr_simulation/models/` and `config/` for mirror and caster A/B experiments; do not edit the production SDF for these candidates.
- Modify `ros2_ws/src/amr_simulation/launch/` only to launch diagnostic candidates or instrumentation; keep `sim.launch.py` application behavior unchanged unless a production fix is justified.
- Create `PHASE_4K_DIRECTIONAL_RESISTANCE_REPORT.md` with the required 36 sections and raw evidence summaries.

## Execution sequence

### Task 1: Baseline and symmetry audit

- [ ] Record Git branch, HEAD, status, diff stat, and production SDF checksum.
- [ ] Parse production SDF numerically and compare left/right wheel link, visual/collision geometry, mass, inertia, joint parent/child, axis, limits, friction, slip, `fdir1`, and contact parameters.
- [ ] Compare front/rear caster position, visual/collision radius, mass, inertia, ball joint, friction, slip, and contact parameters.
- [ ] Write the exact symmetry table into the report before experiments.

### Task 2: Diagnostic joint-state instrumentation

- [ ] Add a diagnostic-only `JointStatePublisher` or equivalent proven Gazebo Harmonic system to a disposable copy/model, exposing `wheel_left_joint` and `wheel_right_joint`.
- [ ] Verify the diagnostic topic and exact joint names before motion.
- [ ] Add failing tests for expected CCW/CW sign and magnitude calculations using `r=0.09`, `L=0.42`, and `omega=0.40`, with expected wheel magnitude `0.933333 rad/s`.
- [ ] Implement the smallest pure kinematics helper and run the tests passing.

### Task 3: Baseline wheel kinematics and divergence layer

- [ ] Run fresh production-equivalent disposable forward, reverse, CCW, CW, and stop trials while recording joint velocity, position, timestamp, ground pose, odom pose, command transitions, roll, and pitch.
- [ ] Compare expected and measured left/right peak, steady, and integrated joint values.
- [ ] Decide whether CCW failure exists at wheel-joint level or first appears in support/contact physics; document evidence before any production edit.

### Task 4: High-resolution turn and stop windows

- [ ] Capture CCW and CW at pre-command, 0.25, 0.5, 1.0, 2.0 seconds, command end, and 0.25/0.5/1.0 seconds after zero.
- [ ] Capture the first zero command timestamp, wheel stop timestamp, odom velocity stop timestamp, physical displacement, physical velocity proxy, and settling distance/time.
- [ ] Classify stop behavior as command latency, continued wheel rotation, chassis coasting, contact settling, or configured acceleration/deceleration.

### Task 5: Caster experiments

- [ ] Run the current four-point candidate as the disposable A baseline.
- [ ] Create a front-caster-only candidate by keeping the front caster grounded and raising the rear caster above normal contact; preserve wheels and all other geometry.
- [ ] Create a rear-caster-only candidate by keeping the rear caster grounded and raising the front caster above normal contact; preserve wheels and all other geometry.
- [ ] Test idle, forward, reverse, CCW, CW, and stop for each candidate.
- [ ] Create a mirrored disposable caster/support candidate by mirroring only the relevant caster/support arrangement; document the exact coordinate changes and keep DiffDrive semantics unchanged.
- [ ] Interpret direction flip versus direction persistence without changing production.

### Task 6: Contact telemetry and causal decision

- [ ] Attempt focused Gazebo/DART contact telemetry for wheels and casters.
- [ ] If telemetry is unavailable, record `NOT TESTED` and rely on controlled A/B evidence.
- [ ] Select one single hypothesis supported by repeatable evidence.
- [ ] If no causal hypothesis is established, stop with production fix `DEFERRED` and overall `BLOCKED`.

### Task 7: Production change and regression

- [ ] Only after Task 6, apply the minimum production change justified by evidence; do not change frozen parameters without proof.
- [ ] Add or update a focused regression test before the production implementation if code behavior changes.
- [ ] Run fresh three-repeat forward, reverse, CCW, CW, and stop tests with braking/settling measurements.
- [ ] Run fresh `/clock`, `/cmd_vel`, `/odom`, `/tf`, `/tf_static`, `/scan`, `/imu`, `/camera/image_raw`, and `/camera/camera_info` checks.
- [ ] Run XML/SDF, Xacro, YAML, Python, rosdep, colcon, compose, headless runtime, resource, and `git diff --check` validation.

### Task 8: Report and stop

- [ ] Write `PHASE_4K_DIRECTIONAL_RESISTANCE_REPORT.md` with all required sections, tables, exact commands, raw measurements, statuses, files, cumulative diff stat, risks, and recommendation.
- [ ] Verify report claims with fresh command output.
- [ ] Stop without starting Phase 5.
