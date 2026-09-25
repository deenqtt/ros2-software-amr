# PHASE 5A — SLAM READINESS, LAUNCH BASELINE & RUNTIME AUDIT REPORT

Repository: /home/deden/Documents/my-project/ros2-software-amr
ROS workspace: ros2_ws
Environment: Ubuntu 24.04 host / Docker / ROS 2 Jazzy / Gazebo Harmonic (Gazebo Sim 8)
Audit date: 2026-09-20
Status vocabulary: PASS, FAIL, BLOCKED, DEFERRED, NOT TESTED

## 1. Executive Summary

Decision: PHASE 5A: SLAM READINESS VERIFIED — PHASE 5B READY.

The current Cafe Service AMR production simulator starts from the existing
Docker/Compose path after rebuilding a stale image whose install space did not
contain the active Xacro asset. The rebuilt runtime starts Gazebo Harmonic,
spawns the production AMR, publishes the required simulation and sensor topics,
and provides a non-duplicated pre-SLAM TF tree.

The existing SLAM launch is not a missing-feature placeholder: Jazzy
slam_toolbox starts with the existing YAML, registers /scan, publishes /map and
/pose, and establishes map → odom during the short smoke test. This is readiness
evidence only. Full exploration, map-quality acceptance, map-save/reload, and
any navigation work remain Phase 5B scope.

No Phase 4 physics, production SDF field, ROS-facing sensor topic, or frame was
changed in Phase 5A. The three existing gz_frame_id Gazebo parser warnings
remain DEFERRED.

## 2. Repository / Git Safety

Status: PASS

| Item | Evidence |
| --- | --- |
| Repository root | /home/deden/Documents/my-project/ros2-software-amr |
| Workspace | /home/deden/Documents/my-project/ros2-software-amr/ros2_ws |
| Required package | ros2_ws/src/amr_simulation present |
| Production model | ros2_ws/src/amr_simulation/models/amr_robot_harmonic present |
| Phase 4 authority | PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md present |
| Branch | main |
| HEAD | 3ddde28b668d646fed8f9e39188a9f1153e74a28 |
| Remote relation | main...origin/main |

The worktree already contained broad Phase 0–4 tracked and untracked changes
before this audit. Those changes were preserved. No reset, clean, stash, restore,
checkout, switch, commit, or push was run. The pre-existing tracked diff stat
is recorded in docs/evidence/phase5a/validation/git-diff-stat.txt; this Phase
5A change set adds the report, runbook, plan, and runtime/validation evidence.

Production SDF verification:

~~~text
dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37
~~~

Evidence: docs/evidence/phase5a/validation/production-sdf-sha.txt.

Because the worktree was already dirty and the production model directory is
untracked, a clean Git before/after comparison for every Phase 4 field was not
available. The Phase 5A provenance check is therefore the approved Phase 4P
SHA/reference plus the unchanged current SHA and the Phase 5A patch scope;
clean Git provenance for the pre-existing worktree is NOT TESTED.

## 3. Frozen Phase 4 Baseline

Status: PASS

The authoritative Phase 4P report records the production slip calibration and
physical motion gate as complete. The Phase 5A audit did not edit wheel or
caster geometry, wheel radius/separation, slip1, slip2, friction, anti-tip
supports, mass, inertia, COM, DiffDrive settings, world physics, or the
production SDF. The current SDF hash is unchanged at the approved value above.

Phase 4 sensor and interface contracts were rechecked against the active
runtime. Existing gz_frame_id warnings on LiDAR, IMU, and camera are still
present and are DEFERRED, not a Phase 5A physics change.

## 4. Existing Navigation / Mapping Source Inventory

Status: PASS

Already present:

- amr_simulation/launch/sim.launch.py: production Gazebo Harmonic server,
  bridge, spawn, and robot-state publisher only.
- amr_simulation/launch/slam.launch.py: SLAM Toolbox online async launch,
  nav2_map_server map saver, and lifecycle manager.
- amr_simulation/config/slam_params.yaml: existing online mapping parameters.
- amr_navigation/launch/navigation.launch.py and config/nav2_params.yaml:
  Nav2 configuration exists but was not started.
- amr_bringup/launch/bringup.launch.py: broad application bringup that can
  select SLAM or Nav2 and also starts application/docking/web processes; it was
  not used for the Phase 5A baseline.
- custom_interfaces: application interfaces are present and unchanged.
- Existing map files are present under maps/.

Not active in the Phase 5A production baseline:

- Nav2 planner/controller/behavior stack.
- AMCL, docking, ArUco runtime, mission runtime, and Web UI integration.
- RViz launch. The current application uses Vue/Leaflet and rosbridge; RViz is
  not launched by the current simulator path.
- robot_localization/EKF or another odometry TF owner.
- static_transform_publisher as an ad-hoc TF source.

## 5. Current Launch Architecture

Status: PASS

Verified path:

~~~text
host
  → docker compose up -d amr-sim
  → docker/entrypoint.sh
  → ros2 launch amr_simulation sim.launch.py
  → ros_gz_sim/gz_sim.launch.py with amr_world.sdf
  → ros_gz_sim spawn of amr_robot_harmonic/model.sdf
  → ros_gz_bridge phase4_bridge
  → robot_state_publisher from amr_robot_harmonic.urdf.xacro
~~~

sim.launch.py starts server-only Gazebo by default. GUI is opt-in and headless
mode takes precedence if both launch arguments are true. The wrapper
scripts/docker_run.sh up invokes the same Compose service in the foreground.

## 6. Docker Runtime Architecture

Status: PASS

The current service is amr-sim, image amr-sim:jazzy, built from
docker/Dockerfile with ros:jazzy-ros-base-noble. Effective Compose values
include:

- ROS_DOMAIN_ID=42;
- SIM_GUI=false, SIM_HEADLESS=true by default;
- host networking for DDS discovery;
- read-only source mount ./ros2_ws/src:/ros2_ws/src;
- persistent bind mount ./maps:/maps;
- /dev/dri and privileged Gazebo runtime settings.

The Dockerfile installs ros-jazzy-slam-toolbox, Nav2, map server/lifecycle
packages, Gazebo bridge/image packages, robot-state publisher, Xacro, and the
workspace dependencies. A fresh image build resolved rosdep and built all five
workspace packages.

The initial audit found the existing container restart-looping because its old
install space lacked the active Xacro file. Rebuilding the image from current
source fixed that runtime packaging issue without modifying repository physics.

## 7. ROS Node Inventory

Status: PASS

Fresh default production baseline:

| Node | Role |
| --- | --- |
| /phase4_bridge | Gazebo ↔ ROS topics and dynamic odometry TF |
| /robot_state_publisher | Fixed body, wheel, sensor, tray TF and robot description |

Fresh SLAM smoke additions:

| Node | Role |
| --- | --- |
| /slam_toolbox | Online async SLAM |
| /map_saver | Lifecycle map saver server |
| /lifecycle_manager_slam | Map saver lifecycle management |

The smoke nodes were stopped and a post-smoke check returned only the two
production baseline nodes. Evidence: runtime/final-runtime-nodes.txt and
runtime/post-map-odom-smoke-nodes.txt.

## 8. ROS Topic Inventory

Status: PASS

The default live graph exposed:

| Topic | Type | Current producer |
| --- | --- | --- |
| /clock | rosgraph_msgs/msg/Clock | phase4_bridge |
| /cmd_vel | geometry_msgs/msg/Twist | command input to bridge |
| /odom | nav_msgs/msg/Odometry | phase4_bridge |
| /tf | tf2_msgs/msg/TFMessage | phase4_bridge + robot state publisher |
| /tf_static | tf2_msgs/msg/TFMessage | robot state publisher |
| /scan | sensor_msgs/msg/LaserScan | phase4_bridge |
| /imu | sensor_msgs/msg/Imu | phase4_bridge |
| /camera/image_raw | sensor_msgs/msg/Image | phase4_bridge |
| /camera/camera_info | sensor_msgs/msg/CameraInfo | phase4_bridge |
| /joint_states | sensor_msgs/msg/JointState | no active publisher in baseline; RSP subscription exists |
| /robot_description | std_msgs/msg/String | robot state publisher |

Smoke-only topics included /map, /map_metadata, /pose, and the map saver
lifecycle transition topic.

## 9. /clock Audit

Status: PASS

/clock is rosgraph_msgs/msg/Clock, published by one phase4_bridge endpoint with
best-effort reliability and transient-local durability. The fresh rate sample
was approximately 998 Hz after DDS discovery. /clock payload was received and
the simulator launch passes use_sim_time:=true.

The initial rate command can print a discovery warning before samples arrive;
this is documented in the runbook. SLAM Toolbox, map saver, and any future
mapping nodes must use simulation time.

## 10. /scan Audit

Status: PASS

Fresh runtime findings:

| Property | Result |
| --- | --- |
| Type | sensor_msgs/msg/LaserScan |
| Frame | base_scan |
| QoS | best effort, volatile, depth unknown in ROS introspection |
| Rate | approximately 9–10 Hz; fresh windows ranged about 8.98–9.94 Hz |
| Angle range | -2.35619 to +2.35619 rad |
| Samples | 720 horizontal samples, one vertical sample from production SDF |
| Range | 0.12 to 12.0 m |
| Payload | received; finite range values observed in the sample |

The production SDF configures a 10 Hz, 720-sample LiDAR. Evidence:
runtime/topic-info-core.txt, runtime/payload-samples.txt, and
runtime/hz-scan.txt.

## 11. /odom Audit

Status: PASS

Fresh runtime findings:

| Property | Result |
| --- | --- |
| Type | nav_msgs/msg/Odometry |
| header.frame_id | odom |
| child_frame_id | base_footprint |
| Publisher | one phase4_bridge publisher |
| QoS | reliable, volatile, depth unknown in ROS introspection |
| Rate | approximately 28–29 Hz in a fresh window |
| Payload | received; zero-state and commanded-motion samples valid |

The bounded readiness motion changed /odom to approximately 0.15845 m and the
explicit zero command returned the reported twist to zero. This was only a
short interface/readiness probe, not a replacement for the Phase 4 motion gate.

## 12. TF Tree

Status: PASS

The verified pre-SLAM tree is:

~~~text
odom
└── base_footprint
    └── base_link
        ├── base_scan
        ├── imu_link
        ├── camera_link
        │   └── camera_rgb_frame
        │       └── camera_rgb_optical_frame
        ├── wheel_left_link
        ├── wheel_right_link
        ├── tray_1
        ├── tray_2
        └── tray_3
~~~

map is intentionally absent before SLAM. The static camera chain remains
camera_link → camera_rgb_frame → camera_rgb_optical_frame, with no ROS-facing
rename.

## 13. TF Ownership

Status: PASS

| Transform | Expected owner | Actual publisher(s) | Status |
| --- | --- | --- | --- |
| map → odom | SLAM Toolbox during mapping | none in default baseline; SLAM Toolbox by launch/runtime semantics during smoke | PASS |
| odom → base_footprint | production odometry | phase4_bridge | PASS |
| base_footprint → base_link | robot description | robot_state_publisher | PASS |
| base_link → base_scan | robot description | robot_state_publisher | PASS |
| base_link → imu_link | robot description | robot_state_publisher | PASS |
| camera chain | robot description | robot_state_publisher | PASS |

tf2_tools view_frames showed odom as parent of base_footprint, with the fixed
body/sensor chain below it. The corrected direct edge capture is
runtime/tf-required-edges-verified.txt. An earlier failed helper probe that ran
ros2 outside the container is retained as diagnostic history and is excluded
from the PASS claim.

## 14. Duplicate TF Risk

Status: PASS

No duplicate dynamic authority was observed for odom → base_footprint, and no
second odom → base_link owner was found. The two /tf publishers have separate
roles: phase4_bridge provides dynamic odometry and robot_state_publisher
provides robot-description transforms. /tf_static has one robot-state publisher.

During the SLAM smoke test, the map → odom transform appeared only after the
SLAM launch initialized, and no static transform was fabricated. ROS 2 topic
introspection reports topic-level publishers, not the owner of each individual
TFMessage transform; the edge attribution is therefore based on the
slam.launch.py ownership contract plus the active smoke result. Future Phase
5B must keep this ownership boundary and should add a dedicated per-transform
authority check if stricter provenance is required.

## 15. SLAM Toolbox Dependency

Status: PASS

The production image contains:

- slam_toolbox prefix: /opt/ros/jazzy;
- installed version: 2.8.5-1noble.20260905.070219;
- executables including async_slam_toolbox_node;
- nav2_map_server installed;
- nav2_lifecycle_manager installed.

The dependency is declared in the Dockerfile and amr_simulation/package.xml;
no manual package installation was performed in the running container.

## 16. Existing SLAM Configuration

Status: PASS

ros2_ws/src/amr_simulation/config/slam_params.yaml exists and was used
unchanged by the smoke test. Audited relevant values:

| Parameter | Value |
| --- | --- |
| odom_frame | odom |
| map_frame | map |
| base_frame | base_footprint |
| scan_topic | /scan |
| mode | mapping |
| use_map_saver | true |
| resolution | 0.05 m/cell |
| minimum_travel_distance | 0.1 m |
| minimum_travel_heading | 0.2 rad |
| transform_publish_period | 0.02 s |
| map_update_interval | 5.0 s |

It is usable unchanged for Phase 5A startup/readiness. Full mapping quality and
save/reload behavior are not claimed here.

## 17. Required SLAM Frames

Status: PASS

The configuration correctly uses base_footprint because the production odometry
edge terminates at base_footprint, while base_link is its fixed body child. The
required chain is odom → base_footprint → base_link → base_scan. SLAM Toolbox
owns map → odom; no static substitute is allowed.

Recommended frames for Phase 5B are therefore:

~~~text
map_frame:  map
odom_frame: odom
base_frame: base_footprint
scan_topic: /scan
~~~

## 18. Required QoS

Status: PASS

Current live QoS relevant to mapping:

- /clock: best effort, transient local publisher; mapping nodes use
  use_sim_time=true.
- /scan: best effort, volatile publisher; SLAM Toolbox successfully registered
  the sensor during smoke.
- /odom: reliable, volatile publisher.
- /tf: reliable, volatile dynamic transforms.
- /tf_static: reliable, transient-local static transforms.
- /map: SLAM Toolbox published reliable, transient-local occupancy data in the
  smoke test.

Consumers must use compatible QoS rather than introducing a second bridge or
republishing sensor topics.

## 19. Runtime Readiness Test

Status: PASS

The rebuilt production simulator exposed all required readiness interfaces:
/clock, /cmd_vel, /odom, /tf, /tf_static, /scan, /imu,
/camera/image_raw, and /camera/camera_info. Payloads were received for LiDAR,
odometry, and camera info; topic publishers and QoS were introspected.

A bounded forward command at 0.05 m/s for 20 messages changed /odom, and a
bounded zero command returned the odometry twist to zero. The production SDF
hash remained unchanged. This test did not start Nav2, AMCL, docking, mission
runtime, or Web UI integration.

## 20. SLAM Smoke Test

Status: PASS for readiness; DEFERRED for full mapping acceptance.

The existing ros2 launch amr_simulation slam.launch.py use_sim_time:=true
started successfully. Evidence showed:

- /slam_toolbox, /map_saver, and /lifecycle_manager_slam started;
- SLAM Toolbox registered the custom LiDAR;
- /map, /map_metadata, and /pose appeared;
- /map payload used frame map and 0.05 m resolution;
- tf2_echo map odom initially waited while frame initialization completed, then
  resolved an identity map → odom transform; the direct evidence is
  runtime/slam-map-odom-audit.txt;
- shutdown completed cleanly and no SLAM nodes remained.

The initial Invalid frame ID "map" message is a transient startup condition, not
a persistent transform failure. Full manual exploration and map acceptance were
intentionally not performed.

## 21. Map Storage Architecture

Status: PASS for local storage; DEFERRED for UI save integration.

Compose bind-mounts the host repository ./maps into /maps for both amr-sim and
amr-backend. The directory already contains YAML/PGM maps and is usable for
local runtime persistence. The existing map saver command is:

~~~bash
ros2 run nav2_map_server map_saver_cli -f /maps/amr_map
~~~

The host result is maps/amr_map.yaml plus maps/amr_map.pgm. The current
slam.launch.py exposes /map_saver/save_map, while
web-ui/src/composables/useROS.js references /slam_toolbox/save_map; this existing
endpoint mismatch must be resolved and validated in Phase 5B before Web UI map
saving is called complete.

## 22. Multi-PC Boundary

Status: PASS for local foundation; DEFERRED for multi-PC deployment.

Phase 5A keeps ROS-local mapping in the ROS/Docker machine. A future split may
place Web UI/FastAPI on Deden's machine and ROS/Gazebo or the robot stack on a
teammate machine. The future boundary is:

- ROS topics/services/actions cross hosts through the configured ROS/DDS or
  rosbridge boundary;
- the browser can use rosbridge at port 8765;
- backend map APIs use the backend's /maps mount;
- both machines must agree on map transfer/storage semantics.

No NFS, remote map synchronization, or full Web UI integration was implemented.

## 23. Operator Runbook

Status: PASS

Created and checked:

docs/runbooks/AMR_SIMULATION_COMMANDS.md

It documents host/container location, exact build/start/GUI/headless/stop
commands, ROS sourcing, topic and TF checks, rates, bounded movement and
emergency stop, independent Gazebo pose, SLAM smoke, map storage/save,
troubleshooting, and scoped cleanup. It does not recommend destructive Docker
cleanup.

## 24. Build Validation

Status: PASS

Fresh validation evidence:

| Check | Result |
| --- | --- |
| Python AST/compilation coverage | 1,050 Python files parsed, PASS |
| XML/SDF/URDF/Xacro XML parsing | 14 files, PASS |
| YAML parsing | 9 files, PASS |
| Active Xacro expansion | PASS |
| docker compose config -q | PASS, exit=0 captured |
| git diff --check | PASS, exit=0 captured |
| rosdep update --rosdistro jazzy | PASS; root warning only |
| full rosdep install | PASS |
| full colcon build | 5 packages, PASS |

Evidence is under docs/evidence/phase5a/validation/. The colcon/rosdep check
ran in a disposable Compose container so the active simulator install space was
not disturbed.

## 25. Resource Snapshot

Status: PASS for current run; DEFERRED for production sizing.

Fresh snapshots while the headless simulator was healthy:

~~~text
Latest sample: amr-sim CPU 159.90%, memory 785.7 MiB / 15.24 GiB (5.03%),
112 PIDs; host memory 15 GiB total with 4.6 GiB available; host swap 4.0 GiB
total with 2.9 GiB used and 1.1 GiB free. An earlier captured sample was
175.75% CPU and 783.8 MiB, so CPU load is workload-sensitive.
~~~

CPU is multi-core percentage and the current sensor-heavy simulator is
resource-intensive. Full SLAM mapping and GUI should be profiled before a
mini-computer deployment decision. Evidence: validation/final-resource-snapshot.txt,
validation/final-docker-stats.txt, and validation/final-free-h.txt.

## 26. Blockers

Status: DEFERRED

No blocker prevents Phase 5B SLAM implementation. Remaining risks and gaps are:

1. Full mapping exploration, stable cafe-map quality, and save/reload are not
   yet accepted.
2. The Web UI save path references /slam_toolbox/save_map, while the current
   smoke runtime exposes /map_saver/save_map.
3. GUI was not accepted on this host because X11 authorization is environment
   dependent; headless mode is the verified path.
4. Existing gz_frame_id parser warnings remain deferred.
5. Resource use, especially CPU and swap pressure, requires profiling before a
   constrained robot mini-computer deployment.
6. Nav2, AMCL, docking, ArUco, mission, and multi-PC integration are outside
   Phase 5A.

## 27. Phase 5B Implementation Scope

Status: DEFERRED

Recommended next phase:

PHASE 5B — SLAM TOOLBOX MAPPING IMPLEMENTATION & RUNTIME ACCEPTANCE

Scope:

1. Preserve the current production SDF and TF ownership.
2. Run the production simulator plus the existing SLAM launch under
   use_sim_time=true.
3. Perform bounded manual exploration using the documented safe commands or a
   dedicated teleop process.
4. Evaluate scan matching, loop closure, map coverage, unknown/free/occupied
   quality, and transform continuity.
5. Save a named map to /maps, verify host persistence, and reload it through a
   controlled map-server test.
6. Reconcile /map_saver/save_map with the Web UI contract only when that
   integration is explicitly in scope.
7. Record resource use and sensor/TF regression after mapping.

Do not start Nav2, AMCL, docking, ArUco runtime, mission runtime, or full Web UI
integration as part of this Phase 5A report.

## 28. Final Decision

~~~text
PHASE 5A: SLAM READINESS VERIFIED — PHASE 5B READY
~~~

Phase 5B is ready to be explicitly started. It was not started automatically.

## Required Final Answers

1. Production SDF SHA still correct? PASS — yes, dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37.
2. Was production physics modified? PASS — no Phase 5A physics edit was made; a clean Git before/after comparison of the pre-existing dirty/untracked worktree is NOT TESTED.
3. What exact command starts production simulation? PASS — host: docker compose up -d amr-sim.
4. What exact command starts GUI mode? PASS — host: SIM_GUI=true SIM_HEADLESS=false docker compose up -d amr-sim.
5. What exact command starts headless mode? PASS — host: SIM_GUI=false SIM_HEADLESS=true docker compose up -d amr-sim.
6. What exact command enters the ROS runtime? PASS — host: docker compose exec amr-sim bash --rcfile /entrypoint.sh.
7. What is ROS_DOMAIN_ID? PASS — 42 in Compose.
8. Is /clock healthy? PASS — correct type, one bridge publisher, payload, approximately 998 Hz.
9. Is /scan healthy? PASS — payload and approximately 9–10 Hz.
10. /scan frame? PASS — base_scan.
11. /scan rate? PASS — approximately 9–10 Hz.
12. /scan QoS? PASS — best effort, volatile publisher.
13. Is /odom healthy? PASS — payload, motion response, and approximately 28–29 Hz.
14. /odom frame? PASS — odom.
15. /odom child frame? PASS — base_footprint.
16. Who publishes odom dynamic TF? PASS — phase4_bridge.
17. Does odom → base_footprint resolve? PASS.
18. Does base_footprint → base_link resolve? PASS.
19. Does base_link → base_scan resolve? PASS.
20. Who currently owns map → odom? PASS — no owner in the default baseline; slam_toolbox owns it when SLAM runs.
21. Is there any duplicate dynamic TF authority? PASS — none observed.
22. Is SLAM Toolbox installed? PASS — yes.
23. Exact SLAM Toolbox version/package? PASS — ros-jazzy-slam-toolbox, version 2.8.5-1noble.20260905.070219.
24. Is there an existing SLAM YAML? PASS — ros2_ws/src/amr_simulation/config/slam_params.yaml.
25. Is it usable unchanged? PASS — startup/smoke validation succeeded; full mapping acceptance is deferred.
26. Recommended SLAM base_frame? PASS — base_footprint.
27. Recommended odom_frame? PASS — odom.
28. Recommended map_frame? PASS — map.
29. Recommended scan_topic? PASS — /scan.
30. Is use_sim_time=true required? PASS — yes for Gazebo mapping.
31. Was a SLAM smoke test possible? PASS — yes, using existing launch/config.
32. Did /map appear? PASS — yes.
33. Did map → odom appear? PASS — yes, after SLAM initialization; initial frame wait was transient.
34. Were transform errors observed? PASS — only transient initial map frame wait; no persistent error.
35. What path should maps use? PASS — /maps in the container, backed by repository ./maps on the host.
36. Is /maps already usable? PASS — yes, bind-mounted and persistent.
37. What must Phase 5B implement? DEFERRED — full exploration, map quality, save/reload, resource profiling, and explicit map-save endpoint reconciliation.
38. Was docs/runbooks/AMR_SIMULATION_COMMANDS.md created? PASS — yes.
39. Are its commands verified against the actual repository? PASS — yes, startup, shell, sourcing, topics, TF, Gazebo pose, smoke, and validation paths were checked.
40. Build result? PASS — rosdep, XML/YAML/Xacro, Compose config, diff check, and five-package colcon build passed.
41. Resource snapshot? PASS — latest captured sample 159.90% CPU, 785.7 MiB, 112 PIDs; host 4.6 GiB available and 2.9 GiB swap used.
42. Final Phase 5A decision? PASS — PHASE 5A: SLAM READINESS VERIFIED — PHASE 5B READY.
43. Is Phase 5B ready to start? PASS — yes, but it is not started; explicit approval remains required.

## Files Created / Evidence

- PHASE_5A_SLAM_READINESS_AND_RUNTIME_AUDIT_REPORT.md
- docs/runbooks/AMR_SIMULATION_COMMANDS.md
- docs/superpowers/plans/2026-09-20-phase-5a-slam-readiness.md
- docs/evidence/phase5a/runtime/
- docs/evidence/phase5a/validation/

No Phase 4 physics/source file was changed by Phase 5A.

STOP CONDITION: Phase 5A complete. Phase 5B not started.
