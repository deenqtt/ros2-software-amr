# Phase 4O Slip1 Response Curve Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Map disposable drive-wheel `slip1` response at `0.000`, `0.010`, `0.020`, and `0.035`, then recommend—but do not apply—a production calibration value.

**Architecture:** Extend the Phase 4N byte-preserving candidate generator and pure metrics tooling. Run each final matrix cell in a fresh Docker/Gazebo Harmonic runtime, using Gazebo dynamic pose as independent ground truth and `/odom` only as comparison output. Store compact traces and the report under `docs/evidence/phase4o/`.

**Tech Stack:** Python 3, pytest, ROS 2 Jazzy, Gazebo Harmonic/Gazebo Sim 8, SDF/XML, Docker, existing Phase 4M trace probe, Phase 4N metrics.

## Global Constraints

- Production `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf` remains unchanged.
- Frozen production SHA is `56c347599eb0f078aa4b0107578655fe98681d034e0a88e945269cbfc92b89fb` before and after.
- Candidates are exactly `0.000`, `0.010`, `0.020`, `0.035`, identically on both drive wheels.
- Only drive-wheel `slip1` may differ; all other SDF, DiffDrive, world, topic, TF, sensor, and timing values stay frozen.
- Final matrix: 3 fresh CCW, 3 fresh CW, 3 fresh forward, 3 fresh reverse per value.
- Commands and Phase 4M/4N metrics remain unchanged: turns ±0.40 rad/s, straight ±0.20 m/s, T0–T5, D1–D3.
- Do not start Phase 4P, Phase 5, Nav2, SLAM Toolbox, AMCL, docking, ArUco, mission runtime, or Web UI integration.
- Do not reset, clean, stash, restore, checkout, switch branch, commit, or push.
- DNS-only rosdep failure is reported as environment `BLOCKED`, not hidden.

---

### Task 1: Freeze and inspect the Phase 4N baseline

**Files:**
- Read: `PHASE_4M_CONTINUOUS_CONTACT_DIRECTIONAL_DYNAMICS_REPORT.md`
- Read: `PHASE_4N_CONTACT_SLIP_CAUSAL_ISOLATION_REPORT.md`
- Read: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Create: `docs/evidence/phase4o/baseline/repository-state.txt`

**Interfaces:** Produces verified SHA, git state, exact wheel contact parameters, and the Phase 4N reference metrics.

- [ ] Record `git status --short`, branch, HEAD, `git diff --stat`, and `sha256sum` into the evidence file.
- [ ] Confirm both drive wheels are `mu=1.0`, `mu2=1.0`, `slip1=0.035`, `slip2=0.0`.
- [ ] Confirm no `phase4o-*` container is treated as production state.
- [ ] Confirm Phase 4N already established causality; do not repeat root-cause discovery.

### Task 2: Add a tested multi-value candidate generator

**Files:**
- Modify: `scripts/phase4n_make_slip_candidate.py`
- Modify: `scripts/test_phase4n_make_slip_candidate.py`
- Create: `scripts/phase4o_make_slip_candidates.py`
- Create: `scripts/test_phase4o_make_slip_candidates.py`

**Interfaces:**
- Preserve `generate_candidate(source: Path, output: Path, slip1: float) -> dict`.
- Add `generate_series(source: Path, output_root: Path, values: list[float]) -> list[dict]`.
- Each manifest records source/output SHA, candidate value, exactly two changed fields, and both link names.

- [ ] Write failing tests for four outputs, exact two-field changes, source SHA, and rejection of values outside `[0.0, 1.0]`.
- [ ] Run `PYTHONPATH=scripts pytest -q scripts/test_phase4o_make_slip_candidates.py` and verify the expected missing-API failure.
- [ ] Implement the minimal wrapper by reusing the Phase 4N generator; do not duplicate SDF parsing.
- [ ] Run both Phase 4N generator tests and Phase 4O generator tests; expected result: all pass.

CLI contract:

```bash
python3 scripts/phase4o_make_slip_candidates.py \
  --source ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf \
  --output-root docs/evidence/phase4o/candidates \
  --slip1 0.000 0.010 0.020 0.035
```

### Task 3: Add tested response aggregation and gates

**Files:**
- Create: `scripts/phase4o_metrics.py`
- Create: `scripts/test_phase4o_metrics.py`
- Read/Reuse: `scripts/phase4n_metrics.py`

**Interfaces:**
- `aggregate_value(traces: list[dict]) -> dict` returns repeat count, mean/worst turn error, yaw ratio, translation error, D1/D2/D3, settle intervals, and wheel/stability fields.
- `build_response_curve(groups: dict[float, list[dict]]) -> list[dict]` returns numeric slip1 order.
- `evaluate_acceptance(row: dict) -> dict[str, str]` applies turn ≤5°, straight ≤5%, D2 ≤0.010 m, symmetry, wheel, and stability gates.

- [ ] Write failing synthetic-trace tests for ordering, mean/worst aggregation, missing telemetry, and all-gates-required behavior.
- [ ] Run the focused test and verify RED because the module/API is missing.
- [ ] Implement pure aggregation without changing T0–T5 or D1–D3 definitions.
- [ ] Run all Phase 4N and Phase 4O unit tests; expected result: all pass.

### Task 4: Generate and admit only structurally valid candidates

**Files:**
- Create: `docs/evidence/phase4o/candidates/slip-000/`
- Create: `docs/evidence/phase4o/candidates/slip-010/`
- Create: `docs/evidence/phase4o/candidates/slip-020/`
- Create: `docs/evidence/phase4o/candidates/slip-035/`
- Create: `docs/evidence/phase4o/structural-diff.txt`

- [ ] Generate all candidates from the frozen production SDF.
- [ ] Verify every manifest has the frozen source SHA and exactly two drive-wheel changes.
- [ ] Run `diff -u` against production for each candidate and record the combined result.
- [ ] Reject any candidate with a diff beyond the two intended `slip1` substitutions.
- [ ] Recompute the production SHA and stop if it differs.

### Task 5: Run the fresh 48-trace response matrix

**Files:**
- Create: `docs/evidence/phase4o/slip-000/`
- Create: `docs/evidence/phase4o/slip-010/`
- Create: `docs/evidence/phase4o/slip-020/`
- Create: `docs/evidence/phase4o/slip-035/`
- Create: `docs/evidence/phase4o/runtime-manifest.json`

**Interfaces:** Each value contains 3 fresh CCW, 3 fresh CW, 3 fresh forward, and 3 fresh reverse trace JSON files, with concise build/runtime/resource logs.

- [ ] Implement or reuse one disposable-container runner that copies the candidate, builds with `colcon build --symlink-install`, launches headless `amr_simulation sim.launch.py`, runs `phase4m_trace_probe.py`, copies evidence, captures `docker stats`, and removes the container.
- [ ] Run one `slip1=0.010` pilot and verify topic readiness, command magnitude, sample count, freshness, and T0–T5 before continuing.
- [ ] Run exactly 48 final fresh traces with commands `+0.40/-0.40 rad/s` and `+0.20/-0.20 m/s`.
- [ ] Exclude startup failures, wrong command magnitudes, and sequential-history runs from valid counts; retain concise failure evidence.
- [ ] Aggregate each completed value immediately; never treat missing repeats as zero.

### Task 6: Contact subset, history, semantics, and production regression

**Files:**
- Create: `docs/evidence/phase4o/contact/`
- Create: `docs/evidence/phase4o/history/`
- Create: `docs/evidence/phase4o/semantics/`
- Create: `docs/evidence/phase4o/production-regression/`

- [ ] Inspect installed Gazebo/SDFormat docs/schemas for `slip1`; consult official Gazebo/SDFormat docs only if local evidence is incomplete, and record sources/limitations.
- [ ] Run contact telemetry for `slip1=0.000`, `slip1=0.035`, and the leading nonzero candidate if available; record active state, normal force, depth, and tangential data only when actually available.
- [ ] Verify contact instrumentation does not materially change turn, straight, static pose, or wheel tracking before interpreting it.
- [ ] Compare fresh-start CW with CW after prior motion for one representative value; keep it outside the main curve.
- [ ] Run unchanged production topic/TF regression for `/clock`, `/cmd_vel`, `/odom`, `/tf`, `/tf_static`, `/scan`, `/imu`, `/camera/image_raw`, `/camera/camera_info`, preserving the known headless camera limitation and `gz_frame_id` warning.

### Task 7: Report, validation, recommendation, and stop

**Files:**
- Create: `PHASE_4O_SLIP1_RESPONSE_CURVE_PRODUCTION_CALIBRATION_REPORT.md`
- Create: `docs/evidence/phase4o/validation/`

- [ ] Generate response-curve and acceptance tables from raw JSON: turn mean/worst, yaw ratio, straight mean/worst, D1/D2/D3, T2→T3, T3→T4, wheel, symmetry, stability.
- [ ] Classify response shape only from measured points and spread; do not force a curve fit.
- [ ] Choose exactly one recommendation category: recommend zero, recommend nonzero calibrated value, or no production value yet.
- [ ] Include required report sections 1–38 and final answers 1–42, with exactly one Phase 4O decision string.
- [ ] Run final tests, Python compilation, XML/SDF/YAML validation, `docker compose config -q`, `git diff --check`, full rosdep, full colcon, `free -h`, and final SHA verification.
- [ ] Remove all `phase4o-*` containers; do not edit production, apply a candidate, start Phase 4P, or start Phase 5.
