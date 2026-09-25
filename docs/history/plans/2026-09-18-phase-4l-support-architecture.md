# Phase 4L Production Support Architecture Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Independently validate the current four-point, rear three-point, and front three-point Cafe AMR support architectures, characterize stop dynamics, and apply a production support change only if the rear three-point candidate passes all required gates.

**Architecture:** Generate disposable SDF candidates from the production model without editing production. Use fresh headless containers and independent ground-truth plus `/odom` measurements. Recompute support polygons from the SDF and keep wheel, mass, inertia, DiffDrive, ROS topics, and frames frozen unless a gate-approved support change is required.

**Tech Stack:** ROS 2 Jazzy, Gazebo Harmonic/gz-sim 8, SDF, Docker, Python diagnostics, `ros_gz_bridge`, `rosdep`, `colcon`.

## Global Constraints

- Stay in `/home/deden/Documents/my-project/ros2-software-amr` on branch `main`.
- Do not commit, push, reset, clean, stash, or switch branch.
- Do not start Phase 5, Nav2, SLAM Toolbox, AMCL, docking, ArUco runtime, missions, Web UI, payload tests, or world redesign.
- Preserve the Phase 4J caster correction (`0.055 m` visual/collision radius) until a Phase 4L evidence gate authorizes a minimum support-role change.
- Do not change wheel radius `0.09 m`, separation `0.42 m`, axes, mass, inertia, COM, DiffDrive scaling, ROS topics, or TF frames.
- Use only formal statuses `PASS`, `FAIL`, `BLOCKED`, `DEFERRED`, and `NOT TESTED`.

### Task 1: Safety and production audit

**Files:**
- Read: `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`
- Read: `PHASE_4G_MOTION_CALIBRATION_REPORT.md`
- Read: `PHASE_4H_PHYSICS_ISOLATION_REPORT.md`
- Read: `PHASE_4I_DIFFDRIVE_ROOT_CAUSE_REPORT.md`
- Read: `PHASE_4J_PRODUCTION_SUPPORT_COM_FIX_REPORT.md`
- Read: `PHASE_4K_DIRECTIONAL_RESISTANCE_REPORT.md`
- Read: `docs/ROS_INTERFACE_CONTRACT.md`

- [ ] Record `git status`, branch, HEAD, diff stat, diff check, and production SDF SHA-256.
- [ ] Parse the production SDF and record wheels, casters, anti-tip spheres, masses, COM, support points, JointStatePublisher, and DiffDrive values.
- [ ] Verify no production file is modified during this audit.

### Task 2: Support polygon and candidate generator

**Files:**
- Create or modify: `scripts/phase4l_support_analysis.py`
- Create or modify: `scripts/test_phase4l_support_analysis.py`
- Use disposable outputs only under `/tmp`.

- [ ] Write tests for convex hull area, COM-inside classification, boundary distance, and front/rear margin for Candidates A/B/C.
- [ ] Run the tests and record the initial result.
- [ ] Implement exact geometry using drive points `(0,+0.21)`, `(0,-0.21)`, front `(0.24,0)`, rear `(-0.24,0)`, and recomputed COM.
- [ ] Generate Candidate B by preserving the front visual/link and raising only its collision clear of the ground; generate Candidate C analogously for the rear caster.
- [ ] Validate all disposable SDFs with `xmllint`.

### Task 3: Candidate static and perturbation runtime

**Files:**
- Create or modify: `scripts/phase4l_candidate_probe.py`
- Preserve: production model and ROS contract.

- [ ] Run fresh headless Gazebo for Candidates A/B/C.
- [ ] Record settled roll, pitch, yaw, X/Y/Z drift, support contact role, and short forward/reverse/CW/CCW pulses.
- [ ] Record whether the chassis rocks, tips, oscillates, or activates raised supports.
- [ ] Keep contact-wrench status `NOT TESTED` if Gazebo does not expose usable telemetry.

### Task 4: Three-repeat rear-only validation

**Files:**
- Reuse: `scripts/phase4k_turn_probe.py`, `scripts/phase4g_motion_probe.py`, and timestamped capture helpers.
- Create: disposable raw captures under `/tmp` or named JSON evidence files.

- [ ] Run three fresh independent Candidate B containers.
- [ ] Execute T1 forward, T2 reverse, T3 CCW, T4 CW, and T5 zero command.
- [ ] Capture independent Gazebo pose, `/odom`, joint states, wall/simulation time, body-forward/lateral displacement, yaw, roll/pitch, and stop timing.
- [ ] Compute average/worst error and repeatability without hiding accumulated pose.

### Task 5: Stop dynamics and acceleration analysis

**Files:**
- Modify only diagnostic helpers if required: `scripts/phase4k_turn_probe.py`, `scripts/phase4k_diagnostics.py`.
- Test: `scripts/test_phase4k_diagnostics.py`.

- [ ] Define wheel near-zero threshold `abs(velocity) < 0.02 rad/s`.
- [ ] Measure t0 command start, t1 zero command, t2 wheel deceleration, t3 wheel near-zero, and t4 physical settle.
- [ ] Separate commanded braking distance, post-wheel-stop coasting, and final contact settling.
- [ ] Calculate theoretical braking time/distance from `0.20 m/s` and configured `min_linear_acceleration=-0.5 m/s²`.
- [ ] Attempt one focused Gazebo contact telemetry query without invasive production changes.

### Task 6: Architecture decision and minimum production change

**Files:**
- Modify only if Candidate B passes: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`.
- Record exact SDF diff in the report.

- [ ] Do not modify production before Candidate B has valid polygon, COM, static, repeatability, direction, stop, and sensor evidence.
- [ ] If B passes, raise the front caster collision while preserving its visual component and role as a secondary anti-tip/emergency support; do not delete it.
- [ ] Change no unrelated wheel, caster friction, mass, inertia, DiffDrive, ROS, or TF parameter.
- [ ] If B fails, leave production unchanged and mark the architecture decision `BLOCKED`.

### Task 7: Production gate and regression

**Files:**
- Modify: `PHASE_4L_PRODUCTION_SUPPORT_ARCHITECTURE_REPORT.md`.
- Preserve all existing reports and raw evidence.

- [ ] Run three fresh production repeats only if a production support change was authorized; otherwise document the existing production baseline and stop.
- [ ] Run static, forward, reverse, CCW, CW, stop, sensor, resource, rosdep, colcon, compose, XML/SDF/Xacro/YAML, and diff-check validations.
- [ ] Confirm the frozen camera frame chain and ROS Interface Contract.
- [ ] Produce all 40 required report sections and a formal final decision.
- [ ] Never start Phase 5.

### Task 8: Final verification

- [ ] Re-run diagnostic tests, full build/rosdep, XML/YAML validation, compose validation, and `git diff --check`.
- [ ] Verify branch/HEAD, SDF checksum, files changed, and resource snapshot.
- [ ] Stop and report `PASS` or `BLOCKED` with explicit remaining risks.
