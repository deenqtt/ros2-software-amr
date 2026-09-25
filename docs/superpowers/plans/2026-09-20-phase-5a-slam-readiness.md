# Phase 5A — SLAM Readiness, Launch Baseline & Operator Runbook

## Goal

Audit the existing Cafe Service AMR ROS 2 Jazzy / Gazebo Harmonic simulation, establish the launch and TF baseline required by SLAM Toolbox, record runtime evidence, and create the permanent operator runbook without changing the frozen Phase 4 physics or starting Phase 5 navigation work.

## Scope boundaries

- Inspect and test only the current Cafe Service AMR repository.
- Preserve the Phase 4 production SDF and motion-calibration physics.
- Do not implement Nav2, AMCL, docking, ArUco runtime, mission integration, Web UI integration, or cafe-world redesign.
- Do not run destructive Git commands or commit, push, switch, reset, clean, stash, restore, or checkout.
- Run an optional SLAM smoke test only if the installed dependency, configuration, and TF ownership are demonstrably safe.

## Tasks

### 1. Establish repository and frozen-baseline evidence

- Verify repository root, ROS workspace, `amr_simulation`, production model, and the Phase 4 authority reports.
- Capture Git branch/status/diff-stat without modifying pre-existing work.
- Read the required Phase 4 reports and ROS/Jazzy contract documents.
- Verify the production SDF hash remains `dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37`.

### 2. Inventory launch, Docker, navigation, mapping, and storage sources

- Inspect launch files, Docker Compose/Dockerfile/scripts, package manifests, SLAM parameters, map paths, and existing navigation/mapping sources.
- Determine exact headless/GUI startup, shell, stop, build, ROS domain, workspace sourcing, and evidence commands.
- Identify whether SLAM Toolbox and supporting packages are already present; do not install packages as part of this audit.

### 3. Run the production simulator and record the ROS baseline

- Start only the current project simulator using its existing production launch path.
- Record container, node, topic/type, QoS/publisher, `/clock`, `/scan`, `/odom`, `/tf`, `/tf_static`, and sensor evidence.
- Inspect actual TF messages and publisher ownership, including whether any SLAM-required edge is already published or duplicated.
- Run a bounded, safe command-velocity probe only for readiness/stop behavior; always issue an explicit zero command.

### 4. Assess SLAM readiness and map architecture

- Compare the live topics, QoS, and TF graph against the existing SLAM Toolbox configuration and required `map -> odom -> base_link -> laser` contract.
- Determine whether a no-change SLAM smoke test is safe. If not, record the precise blocker and leave runtime untouched.
- Document map save/load paths, volume persistence, and the boundary between simulator/container and future operator/host machines.

### 5. Validate and capture resource evidence

- Run syntax/config checks relevant to the repository: Python compile, XML/Xacro/SDF, YAML, Docker Compose config, `git diff --check`, rosdep, and colcon.
- Capture `docker stats --no-stream` and `free -h` while the simulator is running.
- Preserve all output under `docs/evidence/phase5a/` and distinguish fresh results from historical Phase 4 evidence.

### 6. Produce deliverables and final gate

- Create `docs/runbooks/AMR_SIMULATION_COMMANDS.md` with exact operator commands and safety notes.
- Create `PHASE_5A_SLAM_READINESS_AND_RUNTIME_AUDIT_REPORT.md` with all required sections and final answers.
- Review the report against the 28 required sections and 43 required final-answer items.
- Run final `git diff --check`, inspect changed-file scope, and stop without beginning Phase 5B.

## Verification commands

The final verification will include the repository-specific checks discovered in Task 2, plus:

```bash
git diff --check
docker compose config
python3 -m compileall -q <repository Python sources>
rosdep update
rosdep install --from-paths ros2_ws/src --ignore-src -r -y
colcon build --symlink-install --base-paths ros2_ws
docker stats --no-stream
free -h
```

All claims in the report will be marked `PASS`, `FAIL`, `BLOCKED`, `DEFERRED`, or `NOT TESTED` where applicable and supported by captured evidence.
