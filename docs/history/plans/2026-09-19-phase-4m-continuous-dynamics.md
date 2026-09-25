# Phase 4M Continuous Contact and Directional Dynamics Investigation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Capture continuous Gazebo/ROS evidence for mirrored CCW/CW asymmetry and production forward/reverse stop dynamics without changing production physics.

**Architecture:** Reuse the persistent Gazebo dynamic-pose JSON stream and existing diagnostic-only wheel joint publisher. Add focused Phase 4M parsing/trace/metric helpers and unit tests. Use disposable runtime containers and, only after baseline capture, attempt a disposable contact-sensor clone if the existing telemetry inventory cannot expose contacts.

**Tech Stack:** ROS 2 Jazzy, Gazebo Harmonic/gz-sim 8, Docker, Python 3, pytest, SDF.

## Global Constraints

- Stay in `/home/deden/Documents/my-project/ros2-software-amr`, branch `main`.
- Do not commit, push, reset, clean, stash, restore, checkout, switch branch, or alter unrelated user work.
- Do not modify the production SDF physics, support architecture, wheel geometry, mass/inertia/COM, friction/slip, acceleration, topics, or frames.
- Do not start Nav2, SLAM, AMCL, docking, ArUco runtime, mission runtime, Web UI integration, or Phase 5.
- Preserve byte identity of `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`.
- Use formal outcomes only: PASS, FAIL, BLOCKED, DEFERRED, NOT TESTED.

### Task 1: Baseline and telemetry inventory

- [ ] Record repository status, branch, HEAD, diff stat, production SDF SHA-256.
- [ ] Read Phase 4 reports and inspect production SDF/world/bridge/launch/diagnostic scripts.
- [ ] Run disposable production runtime.
- [ ] Inventory `gz topic -l`, relevant `gz topic -i`, model/world sensors/plugins, physics timing, and available pose/joint/contact channels.
- [ ] Do not add instrumentation before inventory is recorded.

### Task 2: Trace data model and tests

- [ ] Add tests first for deterministic JSON/CSV event parsing, mirrored metrics, event markers, stop segmentation, and idle-noise thresholds.
- [ ] Run tests red.
- [ ] Implement minimal `scripts/phase4m_diagnostics.py` helpers.
- [ ] Run tests green.

### Task 3: Continuous production trace

- [ ] Add `scripts/phase4m_trace_probe.py` using simulation time and persistent dynamic-pose JSON.
- [ ] Capture command, wheel joint state, ground truth, odometry, body pose/velocity, and timestamps at a documented rate.
- [ ] Run three fresh CCW and three fresh CW traces with identical magnitude/duration and controlled reset.
- [ ] Analyze first divergence and mirrored wheel/pose metrics.

### Task 4: Production stop trace

- [ ] Run three independent forward-stop and three reverse-stop traces on unchanged production.
- [ ] Capture at least 1 s pre-zero and 5 s post-zero.
- [ ] Identify T0–T5, D1/D2/D3, wheel residual motion, body residual motion, and odometry behavior.

### Task 5: Contact telemetry attempt

- [ ] Try existing Gazebo contact topics/components first.
- [ ] If unavailable, create disposable contact-instrumented clone with no physics/control changes.
- [ ] Validate one baseline/instrumented motion for non-interference.
- [ ] Mark contact evidence invalid or NOT TESTED if usable contact data is unavailable.

### Task 6: Report and final validation

- [ ] Create `PHASE_4M_CONTINUOUS_CONTACT_DIRECTIONAL_DYNAMICS_REPORT.md` with the required 43 sections.
- [ ] Run diagnostics, compile, XML/SDF/Xacro/URDF, YAML, compose, rosdep, colcon, diff-check, sensor regression, and resource checks.
- [ ] Recheck branch/HEAD/SDF SHA and remove disposable containers.
- [ ] Final decision must be one of the required Phase 4M formats and production remains BLOCKED.

