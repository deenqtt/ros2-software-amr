# Phase 5B SLAM Mapping Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Prove the production Cafe Service AMR can perform real SLAM Toolbox exploration, produce a usable cafe map, save it to the host, stop mapping, reload it with Nav2 map server only, and document the evidence.

**Architecture:** Keep the verified Phase 5A production simulator as the only Gazebo startup path. Run SLAM Toolbox in a dedicated container shell, drive the robot only with bounded `/cmd_vel` commands, save through the authoritative `nav2_map_server` CLI, then stop SLAM before starting a standalone `nav2_map_server` reload process. Evidence is captured under `docs/evidence/phase5b/`; the operator runbook and a new Phase 5B report record only commands and results actually observed.

**Tech Stack:** Ubuntu 24.04 host, Docker Compose, ROS 2 Jazzy, Gazebo Harmonic, SLAM Toolbox 2.8.5, Nav2 map server, Python standard-library metric helpers where needed, Markdown evidence.

## Global Constraints

- Preserve the production SDF SHA `dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37` before and after.
- Do not modify Phase 4 physics, TF ownership, sensor topics, frames, or mapping parameters merely to force acceptance.
- Do not start Nav2 planners/controllers, AMCL, docking, ArUco runtime, mission runtime, Web UI integration, or Phase 6.
- Do not run `git reset`, `git clean`, `git stash`, `git restore`, `git checkout`, `git switch`, `git commit`, or `git push`.
- Preserve existing user work and existing maps; back up any pre-existing `maps/amr_map.*` as evidence before an authorized map-save overwrite.
- Every runtime claim must have fresh command output; use only PASS, FAIL, BLOCKED, DEFERRED, or NOT TESTED for gate statuses.

---

### Task 1: Establish baseline and evidence layout

**Files:**
- Create: `docs/evidence/phase5b/{baseline,mapping,tf,map,save,reload,logs,resources,validation}/`
- Create: this plan file
- Read-only: `PHASE_5A_SLAM_READINESS_AND_RUNTIME_AUDIT_REPORT.md`, `docs/runbooks/AMR_SIMULATION_COMMANDS.md`, `docs/ROS_INTERFACE_CONTRACT.md`, `PHASE_4P_PRODUCTION_SLIP_CALIBRATION_FINAL_MOTION_REPORT.md`

- [x] Capture `git status --short`, branch, HEAD, diff stat, production SDF SHA, and current map file metadata.
- [x] Copy existing `maps/amr_map.yaml` and `maps/amr_map.pgm` into the Phase 5B baseline evidence directory without deleting or altering the originals.
- [x] Verify `docker compose config -q` and confirm no AMR containers are running before startup.
- [x] Stop and report a BLOCKED gate if the production SDF SHA differs from the frozen value.

### Task 2: Start production runtime and pass the pre-SLAM health gate

**Files:**
- Create: `docs/evidence/phase5b/baseline/` runtime captures
- Read-only runtime: `docker-compose.yml`, `sim.launch.py`, production SDF

- [x] Run `docker compose up -d amr-sim` using the existing Compose path.
- [x] Capture `docker compose ps`, recent simulator logs, Docker stats, host memory, and all required topic types/payloads.
- [x] Verify `/clock`, `/cmd_vel`, `/odom`, `/tf`, `/tf_static`, `/scan`, `/imu`, `/camera/image_raw`, and `/camera/camera_info`.
- [x] Verify `odom → base_footprint → base_link → base_scan` and confirm no pre-existing `map → odom` authority.
- [x] Stop before SLAM if the required sensor/TF gate fails or duplicate `map → odom` authority is found.

### Task 3: Start one SLAM Toolbox instance and capture initialization evidence

**Files:**
- Create: `docs/evidence/phase5b/mapping/`, `docs/evidence/phase5b/tf/`, `docs/evidence/phase5b/logs/`
- Read-only: `ros2_ws/src/amr_simulation/launch/slam.launch.py`, `config/slam_params.yaml`

- [x] Start exactly `ros2 launch amr_simulation slam.launch.py use_sim_time:=true` in a dedicated container process.
- [x] Verify `/slam_toolbox`, `/map_saver`, and `/lifecycle_manager_slam` appear once.
- [x] Verify `/map` has frame `map`, resolution `0.05`, nonzero dimensions, and `map → odom` resolves.
- [x] Capture `/scan`, `/odom`, `/map`, and TF rates/payloads plus SLAM logs.
- [x] Classify startup-only warnings versus persistent transform/scan-registration failures; stop on a persistent failure.

### Task 4: Perform bounded manual exploration and measure the live map

**Files:**
- Create: `docs/evidence/phase5b/mapping/`, `docs/evidence/phase5b/map/`, `docs/evidence/phase5b/resources/`
- Use: verified bounded commands in `docs/runbooks/AMR_SIMULATION_COMMANDS.md`

- [x] Use a controlled sequence of short forward, stop, turn, stop, and return-near-prior-area commands; never leave an unbounded publisher running.
- [x] Cover straight corridors, turns, open areas, walls, corners, representative obstacles/furniture, and a return loop where safe.
- [x] Periodically capture `/scan`, `/odom`, `/map` rates, `tf2_echo map base_footprint`, and live map metrics.
- [x] Record simulation-only, active-SLAM, active-mapping, and map-save resource snapshots.
- [x] Evaluate map structure for duplicated/split walls, ghosting, discontinuities, smearing, and room/corridor integrity; do not claim PASS from existence alone.

### Task 5: Save and validate the host-persisted map

**Files:**
- Modify: `maps/amr_map.yaml`, `maps/amr_map.pgm` only through the authorized runtime map saver
- Create: `docs/evidence/phase5b/save/`
- Potentially modify later: `web-ui/src/composables/useROS.js` only if a minimal safe contract correction is justified by runtime inspection

- [x] Inspect exact runtime service types, including `/map_saver/save_map`, and record the existing Web UI `/slam_toolbox/save_map` mismatch.
- [x] Run `ros2 run nav2_map_server map_saver_cli -f /maps/amr_map`.
- [x] Verify host `maps/amr_map.yaml` and `maps/amr_map.pgm` exist, are nonzero, and correspond to the final `/map` metadata.
- [x] Validate YAML fields, image reference, PGM header/dimensions, and intensity distribution.
- [x] Choose the smallest safe source/config contract action: correct Web UI only if it can be validated without broad UI redesign; otherwise document the exact deferred decision.

### Task 6: Stop mapping and reload the saved map with map server only

**Files:**
- Create: `docs/evidence/phase5b/reload/`
- Modify: `docs/runbooks/AMR_SIMULATION_COMMANDS.md` after exact commands succeed

- [x] Stop the single SLAM launch cleanly and verify no stale `/map` publisher or `/slam_toolbox` remains.
- [x] Start only `nav2_map_server` map server with the saved YAML and manually configure/activate its lifecycle; do not start planner/controller/AMCL/Nav2 bringup.
- [x] Verify `/map` reappears with frame `map`, preserved resolution/dimensions/origin, and meaningful occupancy counts.
- [x] Compare pre-save final map metadata/counts against reloaded map and explain expected trinary representation differences.
- [x] Stop map server cleanly and capture post-reload process state.

### Task 7: Run regression/resource/static validation and write report

**Files:**
- Modify: `docs/runbooks/AMR_SIMULATION_COMMANDS.md`
- Create: `PHASE_5B_SLAM_MAPPING_RUNTIME_ACCEPTANCE_REPORT.md`
- Create: `docs/evidence/phase5b/validation/` and final evidence index

- [x] Recheck sensor payloads and physics sanity after mapping/reload; classify existing `gz_frame_id` warnings as DEFERRED unless behavior changed.
- [x] Run Python AST/compile, XML/SDF/URDF/Xacro, YAML, active Xacro, `docker compose config -q`, `git diff --check`, rosdep, and full five-package colcon build without modifying Phase 4 physics.
- [x] Update the runbook with verified host/container prerequisites, expected results, stop commands, and Quick Mapping Demo.
- [x] Write all required Phase 5B report sections, result table, 50 final answers, remaining risks, and PASS/BLOCKED recommendation.
- [x] Recompute production SDF SHA and `git diff --stat`; stop at Phase 5B and do not begin Phase 6.
