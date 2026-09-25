# Phase 4N Contact / Slip Causal Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Determine whether production drive-wheel `slip1=0.035` materially causes the Phase 4M physical-versus-odometry turn error and/or post-wheel-stop D2, without modifying production physics.

**Architecture:** Preserve `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf` as the immutable baseline. Add a small repository diagnostic generator that creates a disposable SDF candidate with only both drive-wheel `slip1` values changed to `0.0`, validate its structural diff, then run the existing Phase 4M independent Gazebo pose / wheel-state / `/odom` trace methodology in isolated Docker runtimes. Record raw JSON evidence and an auditable report; classify causal contribution without selecting a production value.

**Tech Stack:** ROS 2 Jazzy, Gazebo Harmonic 8.15, Docker, Python 3, `rclpy`, Gazebo dynamic-pose and joint-state topics, existing Phase 4M trace/contact/diagnostic tools, pytest.

## Global Constraints

- Production physics remains frozen; do not edit the production SDF for candidate tests.
- Candidate files are disposable and generated under `/tmp` only.
- The first candidate changes only both drive-wheel ODE `slip1` fields from `0.035` to `0.0`.
- Preserve `mu`, `mu2`, `slip2`, wheel geometry, caster geometry/physics, anti-tip geometry, mass, inertia, COM, DiffDrive, acceleration, world physics, ROS topics, and TF frames.
- Use Gazebo dynamic pose as independent physical ground truth; `/odom` is only the comparison signal.
- Reuse Phase 4M event and distance definitions: T0–T5 and D1–D3.
- Do not start Phase 5, Nav2, SLAM Toolbox, AMCL, docking, ArUco runtime, mission runtime, or Web UI integration.
- Do not run `git reset`, `git clean`, `git stash`, `git restore`, `git checkout`, `git switch`, `git commit`, or `git push`.
- Preserve existing user changes and the unrelated `amr-sim` container.

---

### Task 1: Freeze and document the experiment baseline

**Files:**
- Read: `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`
- Read: `PHASE_4I_DIFFDRIVE_ROOT_CAUSE_REPORT.md`
- Read: `PHASE_4J_PRODUCTION_SUPPORT_COM_FIX_REPORT.md`
- Read: `PHASE_4K_DIRECTIONAL_RESISTANCE_REPORT.md`
- Read: `PHASE_4L_PRODUCTION_SUPPORT_ARCHITECTURE_REPORT.md`
- Read: `PHASE_4M_CONTINUOUS_CONTACT_DIRECTIONAL_DYNAMICS_REPORT.md`
- Read: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Create: `PHASE_4N_CONTACT_SLIP_CAUSAL_ISOLATION_REPORT.md`

**Interfaces:**
- Consumes: production model, current branch/HEAD, Phase 4M trace definitions, and current Gazebo/ROS runtime.
- Produces: recorded repository identity, production SDF SHA-256, exact wheel/caster friction parameters, and a report skeleton with sections 1–33.

- [ ] Record `git status --short`, branch, HEAD, `git diff --stat`, and production model SHA-256 before runtime work.
- [ ] Extract and record both wheel surface blocks and caster surface blocks directly from production SDF, including `mu`, `mu2`, `slip1`, `slip2`, geometry, and poses.
- [ ] Write the report skeleton with explicit `PASS`, `FAIL`, `BLOCKED`, `DEFERRED`, and `NOT TESTED` status values, leaving causal conclusions for measured evidence.

### Task 2: Add disposable slip candidate generation and structural validation

**Files:**
- Create: `scripts/phase4n_make_slip_candidate.py`
- Create: `scripts/test_phase4n_make_slip_candidate.py`
- Modify: `PHASE_4N_CONTACT_SLIP_CAUSAL_ISOLATION_REPORT.md`

**Interfaces:**
- Consumes: `--source-model PATH`, `--output-model PATH`, and `--slip1 FLOAT`.
- Produces: a disposable model with exactly two drive-wheel ODE `slip1` edits, plus a machine-readable manifest containing source/output hashes and changed XML paths.

- [ ] Write tests covering exactly two matching drive-wheel edits, preservation of `mu`, `mu2`, `slip2`, caster values, and failure when the source does not contain exactly two expected drive-wheel `slip1` fields.
- [ ] Run `PYTHONPATH=scripts pytest -q scripts/test_phase4n_make_slip_candidate.py` and verify the tests fail before implementation.
- [ ] Implement XML parsing with link names `wheel_left_link` and `wheel_right_link`; reject any candidate that changes fields other than the two intended `slip1` elements.
- [ ] Run the focused tests again and generate the candidate under `/tmp/phase4n-slip1-zero/`.
- [ ] Validate the candidate with XML/SDF parsing and a structural diff that reports only the two intended `0.035 → 0.0` changes.

### Task 3: Add metric aggregation for A/B evidence

**Files:**
- Create: `scripts/phase4n_metrics.py`
- Create: `scripts/test_phase4n_metrics.py`
- Modify: `PHASE_4N_CONTACT_SLIP_CAUSAL_ISOLATION_REPORT.md`

**Interfaces:**
- Consumes: Phase 4M-compatible trace JSON files and optional contact traces.
- Produces: per-trace yaw error, physical/odom yaw ratio, mirror error, D1/D2/D3/total, wheel tracking metrics, contact force summaries, and A/B deltas.

- [ ] Write tests for yaw error, `physical_yaw_magnitude / odom_yaw_magnitude`, stop-distance extraction, sign-corrected wheel symmetry, and safe handling of missing contact/tangential-slip fields.
- [ ] Run the focused tests to establish the failing state.
- [ ] Implement metrics without changing Phase 4M event definitions or using `/odom` as ground truth.
- [ ] Run the focused tests and validate the aggregator against existing Phase 4M evidence as a compatibility check.

### Task 4: Run fresh Baseline A in isolated Docker

**Files:**
- Create: `docs/evidence/phase4n/baseline/` raw JSON evidence
- Modify: `PHASE_4N_CONTACT_SLIP_CAUSAL_ISOLATION_REPORT.md`

**Interfaces:**
- Consumes: unchanged production model and existing Phase 4M trace/contact tooling.
- Produces: fresh baseline traces: one CCW, one CW, one forward-stop, and one reverse-stop; optional contact-clone traces where practical.

- [ ] Start one isolated baseline runtime with a unique `GZ_PARTITION` and ROS domain; do not attach to `amr-sim`.
- [ ] Run the exact Phase 4M command windows: CCW/CW `angular.z=±0.40`, forward/reverse `linear.x=±0.20`, same sample rates and T0–T5/D1–D3 definitions.
- [ ] Confirm ground-pose freshness, wheel state, `/odom`, and command timing for every trace.
- [ ] Compare fresh baseline against Phase 4M repeatability; if materially different, stop candidate testing and document reproducibility failure.
- [ ] Capture baseline resource usage and remove only the disposable runtime after evidence is copied.

### Task 5: Run Candidate B with `slip1=0.0`

**Files:**
- Create: `docs/evidence/phase4n/candidate-slip1-zero/` raw JSON evidence
- Modify: `PHASE_4N_CONTACT_SLIP_CAUSAL_ISOLATION_REPORT.md`

**Interfaces:**
- Consumes: disposable candidate model, unchanged world/launch/bridge/controller, and the same Phase 4M probe.
- Produces: one CCW, one CW, one forward-stop, and one reverse-stop candidate trace, plus contact traces if candidate instrumentation is available without altering the hypothesis.

- [ ] Start a fresh isolated runtime using the candidate model through a disposable launch/world copy, with a unique `GZ_PARTITION` and ROS domain.
- [ ] Run the same four primary traces and retain identical event/distance definitions.
- [ ] Verify wheel velocity/position tracking remains valid and record physical/odom yaw ratio, D1/D2/D3, contact forces, and pose freshness.
- [ ] If Candidate B shows a material effect, repeat with three CCW, three CW, three forward-stop, and three reverse-stop traces before classifying causality.
- [ ] Capture candidate resource usage and remove only disposable containers.

### Task 6: Run straight-motion sanity check and classify the hypothesis

**Files:**
- Create: `docs/evidence/phase4n/straight/` raw JSON evidence if required
- Modify: `PHASE_4N_CONTACT_SLIP_CAUSAL_ISOLATION_REPORT.md`

**Interfaces:**
- Consumes: fresh A/B traces and metrics.
- Produces: A/B matrix, ratio comparison, wheel/contact/straight-motion regression, causal classification, and Phase 4O recommendation.

- [ ] Run at least one `+0.20 m/s` straight candidate sanity trace if slip1 changes turn behavior materially; include reverse if directional behavior changes.
- [ ] Distinguish causal contribution from production suitability; do not edit production or select a production slip value.
- [ ] Classify `slip1` as strongly supported, partially supported, rejected as primary cause, or inconclusive using repeatability and effect size relative to fresh baseline variability.
- [ ] If rejected, select exactly one next hypothesis for Phase 4O from the evidence; do not test it in Phase 4N.

### Task 7: Sensor/build/resource regression and final report

**Files:**
- Modify: `PHASE_4N_CONTACT_SLIP_CAUSAL_ISOLATION_REPORT.md`

**Interfaces:**
- Consumes: final A/B evidence, production SHA before/after, validation outputs, resource snapshots, and candidate manifest.
- Produces: complete Phase 4N report and exact final decision line.

- [ ] Re-validate unchanged production runtime topics: `/clock`, `/cmd_vel`, `/odom`, `/tf`, `/tf_static`, `/scan`, `/imu`, `/camera/image_raw`, `/camera/camera_info`; confirm camera TF chain unchanged.
- [ ] Run diagnostic tests, Python compile, XML/SDF/Xacro/URDF validation, YAML parsing, `docker compose config -q`, rosdep, colcon, and `git diff --check`.
- [ ] Verify production SDF SHA before/after is identical and only disposable candidate files contain slip changes.
- [ ] Remove Phase 4N disposable containers; leave unrelated containers untouched.
- [ ] Complete all report sections and answer the required 34 questions explicitly.
- [ ] End with exactly one allowed Phase 4N decision and stop; do not start Phase 4O or Phase 5.

## Self-Review Checklist

- [ ] All Phase 4N requirements map to Tasks 1–7.
- [ ] No production physics edit is planned.
- [ ] Candidate changes are limited to both drive-wheel `slip1` values.
- [ ] Baseline and candidate use identical trace definitions.
- [ ] Repeatability is required before causal classification.
- [ ] Contact force limitations and missing tangential-slip telemetry are reported explicitly.
- [ ] Final report includes all 33 required sections and all 34 required answers.
