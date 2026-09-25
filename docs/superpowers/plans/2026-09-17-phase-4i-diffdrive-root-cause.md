# Phase 4I DiffDrive Root-Cause Investigation Plan

> **For agentic workers:** Execute this plan task-by-task with verification checkpoints. No commit step is included because the task explicitly forbids commits.

**Goal:** Identify the first layer at which the known-good Gazebo Harmonic differential-drive pipeline and the Cafe AMR diagnostic pipeline diverge, without modifying the production Cafe model.

**Architecture:** Use a disposable diagnostic workspace/container and an official Gazebo Harmonic reference model. Measure the same command through `/cmd_vel`, DiffDrive target/joint state, physical Gazebo pose, and `/odom`; separately measure simulation time versus wall time. Only evidence-backed disposable-model experiments are permitted.

**Tech Stack:** ROS 2 Jazzy, Gazebo Sim Harmonic/gz-sim 8.x, `ros_gz_bridge`, native `gz-sim-diff-drive-system`, Gazebo CLI, Python probe, Docker.

## Global Constraints

- Only the Cafe Service AMR ROS 2 Jazzy / Gazebo Harmonic repository is in scope.
- `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf` must remain untouched.
- Do not start Nav2, SLAM, AMCL, docking, ArUco, missions, Web UI, cafe-world work, or production physics redesign.
- Do not reset, clean, stash, commit, push, or switch branch.
- Use one meaningful diagnostic variable per experiment.
- Report unsupported measurements as `NOT TESTED` or `BLOCKED`; do not infer contact forces.

### Task 1: Capture safety and installed-version baseline

**Files:**
- Read only: `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`
- Read only: `PHASE_4G_MOTION_CALIBRATION_REPORT.md`
- Read only: `PHASE_4H_PHYSICS_ISOLATION_REPORT.md`
- Read only: `docs/ROS_INTERFACE_CONTRACT.md`

- [ ] **Step 1: Confirm repository identity and Git safety state.**

Run:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git diff --stat
```

Expected: repository root is the Cafe AMR project, branch remains `main`, and no destructive Git operation is performed.

- [ ] **Step 2: Capture simulator and ROS package versions.**

Run in the Jazzy diagnostic environment:

```bash
source /opt/ros/jazzy/setup.bash
gz sim --versions || gz sim --help
ros2 doctor --report | sed -n '1,160p'
dpkg-query -W -f='${Package} ${Version}\n' 'ros-jazzy-ros-gz*' 'ros-jazzy-gz-*' 2>/dev/null || true
```

Record exact Gazebo Sim, gz-sim, physics engine, ROS distro, and `ros_gz` versions.

### Task 2: Execute an official known-good Harmonic reference

**Files:**
- Create only disposable diagnostic copy outside the production model path if needed.
- Modify: none in the production repository.

- [ ] **Step 1: Locate the version-matched official reference.**

Inspect installed examples/resources and the official Harmonic `moving_robot` / `diff_drive.sdf` source. Record the source URL or installed path and exact upstream version.

- [ ] **Step 2: Copy the reference into a disposable diagnostic location.**

Do not edit the upstream source. Keep the copy isolated from `amr_robot_harmonic/model.sdf` and `amr_robot_physics_test/model.sdf`.

- [ ] **Step 3: Launch the reference headlessly with the same bridge/test environment.**

Verify the reference model spawns and exposes its native odometry and pose. If the exact reference cannot be run because of missing version-compatible assets, record `BLOCKED` and stop before geometry changes.

### Task 3: Prove timing and the existing harness

**Files:**
- Read/modify only if evidence requires it: `scripts/phase4g_motion_probe.py`
- Create if needed: a disposable timing capture helper under `/tmp`.

- [ ] **Step 1: Audit probe timing.**

Inspect every duration wait and record whether it uses wall-clock sleep, ROS time, or Gazebo time. Do not label wall-clock sleep a bug until simulator elapsed time is measured.

- [ ] **Step 2: Capture both clocks around each command.**

For each reference and minimal-model trial record wall start/end, `/clock` start/end, Gazebo timestamp start/end, real-time factor, command duration, and `velocity * simulation_elapsed`.

- [ ] **Step 3: Run reference T1–T4 with three repeats where practical.**

Use exactly `+0.20 m/s`, `-0.20 m/s`, `+0.40 rad/s`, and `-0.40 rad/s` with the same independent `gz model` pose versus `/odom` method. If reference is approximately 50% short too, stop geometry comparison and investigate timing/semantics only.

### Task 4: Instrument the command-to-odometry layers

**Files:**
- Modify only diagnostic assets or probe; never production Cafe SDF.
- Create/modify diagnostic bridge or launch only if required to expose joint state.

- [ ] **Step 1: Determine the Harmonic joint-state mechanism.**

Inspect available Gazebo topics/services/plugins. Use the supported joint-state publisher/query mechanism for `wheel_left_joint` and `wheel_right_joint`; record position and velocity, and effort only if actually exposed.

- [ ] **Step 2: Capture the four-layer data flow.**

For each trial capture command, DiffDrive target if exposed, actual wheel angular velocity, joint position delta, ground-truth displacement/yaw, and `/odom` displacement/yaw.

- [ ] **Step 3: Calculate expected kinematics.**

For straight motion calculate `0.20 / 0.09 = 2.222 rad/s`. For pure rotation calculate wheel linear speed as `0.40 * 0.42 / 2 = 0.084 m/s` and wheel angular speed as `0.084 / 0.09 = 0.933 rad/s`, with signs reversed for CW. Compare these values to measured joint state.

### Task 5: Evaluate static balance and contact without guessing

**Files:**
- Modify only disposable diagnostic model/world candidates.

- [ ] **Step 1: Compute the minimal model support geometry.**

Document chassis COM, wheel axle line, wheel-ground contact points, chassis Z, and the support polygon. Determine whether a two-wheel chassis is statically supportable.

- [ ] **Step 2: Inspect contact evidence.**

List Gazebo contact topics/services for the selected physics engine. If unavailable, use only pose, wheel-ground geometry, pitch/roll, and joint state as indirect evidence and mark direct load measurement `NOT TESTED`.

- [ ] **Step 3: If two-wheel balance is proven invalid, create one three-point candidate.**

Add one physically reviewed passive caster/support with an explicit COM/support-polygon rationale. Verify idle roll/pitch and drift before motion. Do not reuse the previous arbitrary support without documenting its geometry and contact assumptions.

### Task 6: Perform structural comparison and evidence-backed disposable tests

**Files:**
- Read-only reference model copy.
- Read/modify only: `ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.sdf` or separate disposable copies.

- [ ] **Step 1: Build a property-by-property comparison table.**

Compare chassis dimensions/Z/inertia, wheel geometry/Z/roll/axis/joint pose, collision, friction/slip, physics/solver/contact settings, support geometry, self-collision/canonical link, and DiffDrive radius/separation.

- [ ] **Step 2: State one hypothesis before each candidate.**

Test only one evidence-backed difference at a time: exact reference wheel/contact parameters, vertical geometry, valid support polygon, COM placement, or joint frame semantics.

- [ ] **Step 3: Repeat the same measurement matrix after each candidate.**

Record changed property, expected effect, measured result, and whether the divergence layer moved. Do not apply any candidate to the production Cafe model.

### Task 7: Write and verify the root-cause report

**Files:**
- Create: `PHASE_4I_DIFFDRIVE_ROOT_CAUSE_REPORT.md`

- [ ] **Step 1: Include all 27 required report sections.**

The report must contain version evidence, official reference architecture/source, reference measurements, timing audit, kinematics, four-layer observations, structural diff, support/contact analysis, hypotheses, root cause, optional diagnostic fix, before/after results, files/diff stat, uncertainty, and production recommendation.

- [ ] **Step 2: Run final verification.**

Run:

```bash
python3 -m py_compile scripts/phase4g_motion_probe.py
docker compose config --quiet
git diff --check
git status --short
git branch --show-current
git rev-parse HEAD
```

Expected: syntax/config/diff checks pass, branch/HEAD are unchanged, production SDF has no Phase 4I modification, and no Phase 5 runtime is started.

- [ ] **Step 3: Stop after the report.**

Do not start Phase 5 and wait for explicit approval before any production model change.

