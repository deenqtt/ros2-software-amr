# PHASE 5B — SLAM TOOLBOX MAPPING RUNTIME ACCEPTANCE, SAVE & RELOAD

Repository: `/home/deden/Documents/my-project/ros2-software-amr`
ROS workspace: `ros2_ws`
Environment: Ubuntu 24.04 host / Docker / ROS 2 Jazzy / Gazebo Harmonic / SLAM Toolbox 2.8.5
Execution date: 2026-09-20
Status vocabulary: PASS, FAIL, BLOCKED, DEFERRED, NOT TESTED

## 1. Executive Summary

The production Cafe Service AMR completed a real bounded mapping exploration
using the existing Phase 5A runtime path. SLAM Toolbox registered the
production LiDAR, published a populated `map`, and maintained the
`map → odom` transform during runtime observation. The resulting map was saved
to the host bind mount, the SLAM runtime was stopped cleanly, and the saved map
was reloaded successfully by a standalone Nav2 map server without starting
AMCL or the rest of Nav2.

**PHASE 5B: SLAM MAPPING, SAVE & RELOAD ACCEPTANCE — PASS**
**PHASE 5 MAPPING GATE: PASS**
**PHASE 5: COMPLETE**

No Phase 4 physics or production SDF field was changed. Phase 6 was not started.

## 2. Repository / Git Safety

Status: PASS

| Item | Result |
| --- | --- |
| Repository root | `/home/deden/Documents/my-project/ros2-software-amr` |
| ROS workspace | `ros2_ws` |
| Required package | `ros2_ws/src/amr_simulation` present |
| Production model | `ros2_ws/src/amr_simulation/models/amr_robot_harmonic` present |
| Phase 4 authority | `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md` present |
| Branch | `main` |
| HEAD before work | `3ddde28b668d646fed8f9e39188a9f1153e74a28` |
| Worktree | Already dirty before Phase 5B; preserved |
| Destructive Git commands | None run |

Evidence: `docs/evidence/phase5b/baseline/`.

The existing dirty/untracked worktree contains earlier Phase 0–5A work. No
reset, clean, stash, restore, checkout, switch, commit, or push was performed.
The existing `maps/amr_map.*` files were backed up under
`docs/evidence/phase5b/baseline/` before the authorized runtime map save.

## 3. Frozen Phase 4 Baseline

Status: PASS

Production SDF SHA before:

```text
dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37
```

Production SDF SHA after:

```text
dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37
```

The following remained frozen: wheel geometry, wheel radius and separation,
slip1/slip2, friction, caster geometry/contact, anti-tip supports, mass,
inertia, COM, DiffDrive settings, and world physics. Only map output files,
evidence, the runbook, and this report changed during Phase 5B.

## 4. Phase 5A Baseline

Status: PASS

Phase 5A had already verified the production Docker path, core sensor topics,
the pre-SLAM TF chain, SLAM startup, `/map` existence, and `map → odom` smoke
resolution. It explicitly deferred full exploration, map-quality acceptance,
map save/reload, and Web UI save integration. Phase 5B used that same
`docker compose up -d amr-sim` plus `slam.launch.py` path.

## 5. Production Runtime Startup

Status: PASS

Exact simulator command:

```bash
docker compose up -d amr-sim
```

Observed result: `amr-sim` became healthy with restart count `0`. The runtime
started Gazebo Harmonic, `/phase4_bridge`, the production AMR model, and
`robot_state_publisher`. Existing three `gz_frame_id` parser warnings appeared
unchanged from Phase 5A.

## 6. Pre-SLAM Health Gate

Status: PASS

The following were verified from inside `amr-sim`: `/clock`, `/cmd_vel`,
`/odom`, `/tf`, `/tf_static`, `/scan`, `/imu`, `/camera/image_raw`, and
`/camera/camera_info`.

Representative values:

- `/scan`: `sensor_msgs/msg/LaserScan`, frame `base_scan`, approximately 9.7 Hz,
  720 samples, range `0.12–12.0 m`.
- `/odom`: `nav_msgs/msg/Odometry`, `odom → base_footprint`, approximately
  28.7–29.0 Hz.
- `/imu`: frame `imu_link`, payload received.
- Camera info: frame `camera_rgb_optical_frame`, `640×480`.

Before SLAM, `/map` had no publisher and `map → odom` did not resolve. This
confirmed that no unrelated map authority was present.

## 7. SLAM Startup

Status: PASS

Exact command:

```bash
ros2 launch amr_simulation slam.launch.py use_sim_time:=true
```

Exactly one SLAM instance was started. Nodes observed:

```text
/slam_toolbox
/map_saver
/lifecycle_manager_slam
```

SLAM Toolbox registered `Custom Described Lidar`. `/map` was published as an
`nav_msgs/msg/OccupancyGrid` with frame `map` and configured resolution
`0.05 m/cell`.

## 8. TF Ownership

Status: PASS

| Edge | Owner | Evidence |
| --- | --- | --- |
| `map → odom` | SLAM Toolbox | `tf2_echo` resolved after initialization |
| `odom → base_footprint` | `phase4_bridge` | dynamic `/tf` payload |
| `base_footprint → base_link` | `robot_state_publisher` | `/tf_static` payload |
| `base_link → base_scan` | `robot_state_publisher` | production fixed tree |
| Camera chain | `robot_state_publisher` | existing contract preserved |

No static fake `map → odom`, EKF, second odometry publisher, or sensor
republisher was introduced.

## 9. Mapping Exploration Method

Status: PASS

The robot was driven with bounded ROS commands at `0.15 m/s` and approximately
`0.2 rad/s` turns. Every segment ended with five zero-velocity messages. The
sequence included:

- east approximately 3.2 m;
- 90-degree turn and north approximately 3.2 m;
- 90-degree turn and west approximately 6.4 m;
- 90-degree turn and south approximately 6.4 m;
- 90-degree turn and east approximately 6.4 m;
- a return north/west route near the previously observed start region.

Total commanded translational path was approximately 32 m. No unbounded
publisher was left running and no intentional collision was used.

## 10. Exploration Coverage

Status: PASS

The route exercised the 10 m × 10 m room perimeter, straight corridors,
corners, open areas, four shelving obstacles, outer walls, and a return near a
previously observed region. Qualitatively, the scan-observable perimeter and
the representative furniture layout were covered; an exact percentage of free
space coverage was not computed.

## 11. Scan / Odom Runtime Health

Status: PASS

During and after exploration:

| Topic | Observed result |
| --- | --- |
| `/scan` | approximately 10.8–12.0 Hz in the active mapping capture; payload remained valid |
| `/odom` | approximately 29.0 Hz; pose changed with commanded motion |
| `/map` | populated latched OccupancyGrid; live `topic hz` is not meaningful after motion stops because the map is not continuously republished |

The `/map` payload was accepted directly using a transient-local subscriber,
which matches the documented map QoS contract.

## 12. Live Map Metrics

Status: PASS

Final live map metrics before save:

| Metric | Value |
| --- | ---: |
| Frame | `map` |
| Resolution | `0.050000000745 m/cell` |
| Width | `207 cells` |
| Height | `206 cells` |
| Physical width | `10.350000 m` |
| Physical height | `10.300000 m` |
| Occupied cells | `3,135` (`7.35%`) |
| Free cells | `36,799` (`86.30%`) |
| Unknown cells | `2,708` (`6.35%`) |
| Total cells | `42,642` |
| Origin | approximately `[-5.399187, -5.067682, 0]` |

The map had both occupied and free cells and retained a small expected unknown
region. Evidence: `docs/evidence/phase5b/map/final-live-map-metrics.txt`.

## 13. Map Structural Quality

Status: PASS

The saved map preview shows a continuous outer-room boundary and four distinct
shelf structures. No severe duplicated walls, split walls, global ghosting,
rotation jump, large discontinuity, or unexpected smearing was visible. The
map image is retained at `docs/evidence/phase5b/map/final-map-preview.png`.

Minor pixel noise is present at some boundaries and is acceptable for this
simulation acceptance. This is a mapping-quality acceptance, not a claim of
real-robot map quality.

## 14. TF / Pose Continuity

Status: PASS

`tf2_echo map odom` resolved after normal SLAM initialization. After the
exploration, `tf2_echo map base_footprint` remained stable for repeated samples
at approximately:

```text
translation [1.899, -1.239, 0.000]
yaw 90.892 degrees
```

No NaN, solver failure, persistent transform timeout, or discontinuous map pose
was found in the captured runtime/log evidence. The initial `Invalid frame ID
map` messages occurred only while SLAM initialized the map frame.

## 15. SLAM Logs

Status: PASS

The SLAM log showed sensor registration, normal activation, and clean
unregistration on SIGINT. No scan queue overflow, solver error, serialization
failure, or persistent transform failure was found. The Google logging warning
(`Logging before InitGoogleLogging()`) is non-blocking and did not affect
runtime. Evidence: `docs/evidence/phase5b/logs/slam-final.log`.

## 16. Map Save

Status: PASS

Exact command:

```bash
ros2 run nav2_map_server map_saver_cli -f /maps/amr_map
```

Observed result: exit `0`, `Map saved successfully`, `207 X 206 map @ 0.05
m/pix`. Host files were created/updated:

```text
maps/amr_map.yaml  129 bytes
maps/amr_map.pgm   42657 bytes
```

## 17. Saved YAML Validation

Status: PASS

The saved YAML contains:

```yaml
image: amr_map.pgm
mode: trinary
resolution: 0.050
origin: [-5.399, -5.068, 0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
```

The image reference resolves to the host `maps/amr_map.pgm`. Origin precision
is rounded by the map saver to three decimals; the reloaded map used the same
saved values.

## 18. Saved PGM Validation

Status: PASS

`file` identified the image as `PGM 207x206`, raw 8-bit grayscale. The PGM
header is `P5`, max value `255`, payload is `42,642` bytes, and three intensity
values are present:

```text
254: 36,799 cells (free)
0:       3,135 cells (occupied)
205:     2,708 cells (unknown)
```

The image is nonblank and its dimensions match the OccupancyGrid.

## 19. Map Save Service Contract

Status: PASS

Runtime inspection found both endpoints:

| Endpoint | Type | Result |
| --- | --- | --- |
| `/map_saver/save_map` | `nav2_msgs/srv/SaveMap` | present |
| `/slam_toolbox/save_map` | `slam_toolbox/srv/SaveMap` | present |

The existing Web UI call to `/slam_toolbox/save_map` and request field `name`
matches the active Jazzy service type. The authoritative Phase 5B operator path
was still the verified `map_saver_cli` command because it proved host file
persistence. No Web UI source change was necessary and no UI redesign was
performed.

## 20. SLAM Shutdown

Status: PASS

The single SLAM launch was interrupted with SIGINT. `/slam_toolbox`,
`/map_saver`, and `/lifecycle_manager_slam` exited. A post-shutdown check showed
no `/map` publisher and only `/phase4_bridge` plus
`/robot_state_publisher` remained.

## 21. Map Reload

Status: PASS

Exact standalone reload command:

```bash
ros2 run nav2_map_server map_server \
  --ros-args -p yaml_filename:=/maps/amr_map.yaml -p use_sim_time:=true
```

The lifecycle node was configured and activated manually:

```bash
ros2 service call /map_server/change_state lifecycle_msgs/srv/ChangeState \
  "{transition: {id: 1}}"
ros2 service call /map_server/change_state lifecycle_msgs/srv/ChangeState \
  "{transition: {id: 3}}"
```

The node reached `active`, loaded `/maps/amr_map.yaml` and
`/maps/amr_map.pgm`, and published `/map`. No planner, controller, behavior
server, AMCL, or full Nav2 launch was started.

## 22. Reloaded Map Validation

Status: PASS

Reloaded `/map` had frame `map`, resolution `0.050000000745 m/cell`, width
`207`, height `206`, and the same occupancy counts. The map server log
confirmed `Read map /maps/amr_map.pgm: 207 X 206 map @ 0.05 m/cell`.

## 23. Pre-Save vs Reload Comparison

Status: PASS

| Metric | Final before save | Reloaded | Result |
| --- | ---: | ---: | --- |
| Resolution | 0.05 | 0.05 | equal |
| Width | 207 | 207 | equal |
| Height | 206 | 206 | equal |
| Occupied | 3,135 | 3,135 | equal |
| Free | 36,799 | 36,799 | equal |
| Unknown | 2,708 | 2,708 | equal |
| Origin | `[-5.399187,-5.067682]` | `[-5.399,-5.068]` | expected YAML rounding |

Exact byte equality was not required. The reloaded map preserved the saved
trinary representation and physical dimensions.

## 24. Sensor Regression

Status: PASS

After reload, representative payloads remained available:

| Topic | Result |
| --- | --- |
| `/clock` | payload received |
| `/odom` | `odom → base_footprint`, payload received |
| `/tf` | dynamic odometry payload received |
| `/tf_static` | fixed robot/sensor payload received |
| `/scan` | frame `base_scan`, payload and approximately 9.9 Hz |
| `/imu` | frame `imu_link`, payload received |
| `/camera/image_raw` | `480×640`, `rgb8` payload fields received |
| `/camera/camera_info` | `480×640`, `camera_rgb_optical_frame` payload received |

The map server reload intentionally did not recreate `map → odom`; that edge
belongs to SLAM or a later localization system, not a standalone map server.

## 25. Physics Sanity

Status: PASS

No production physics was changed. After the final zero command, `/odom`
reported approximately `linear.x=-5.1e-11 m/s` and `angular.z=-2.4e-10 rad/s`,
which is effectively stopped. No instability or persistent motion was observed
during the mapping route.

## 26. Resource Profile

Status: PASS

| Runtime condition | Docker CPU | Docker memory | PIDs | Host available RAM | Host swap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Simulation only | 125.89% | 551 MiB | 113 | 6.0 GiB | 469 MiB free |
| Active SLAM | 212.74% | 640.7 MiB | 182 | 5.9 GiB | 469 MiB free |
| Active mapping movement | 198.99% | 686 MiB | 198 | 5.8 GiB | 469 MiB free |

The highest observed container memory was `686 MiB`; the host snapshot showed
`3.5 GiB` swap used and `469 MiB` free. These values are suitable for this
host acceptance but remain a deployment risk for a constrained robot computer.

## 27. Operator Runbook Update

Status: PASS

Updated `docs/runbooks/AMR_SIMULATION_COMMANDS.md` with verified sections for:

- start SLAM mapping;
- mapping health;
- bounded manual movement and emergency stop;
- map save and host-file verification;
- clean SLAM stop;
- standalone map-server reload and lifecycle activation;
- reloaded map verification and shutdown;
- Quick Mapping Demo;
- prerequisites, expected results, and stop behavior.

## 28. Build / Static Validation

Status: PASS

| Check | Result |
| --- | --- |
| Python AST validation | 1,039 files, PASS |
| XML/SDF/URDF/Xacro parse | 29 files, PASS |
| YAML parse | 17 files, PASS |
| `docker compose config -q` | exit 0, PASS |
| `git diff --check` | exit 0, PASS |
| `rosdep update --rosdistro jazzy` | PASS; root warning only |
| Full rosdep install | all required rosdeps installed, PASS |
| Full colcon build | 5 packages finished, PASS |

The fresh colcon result was `custom_interfaces`, `amr_simulation`,
`amr_docking`, `amr_navigation`, and `amr_bringup` all finished.

## 29. Remaining Risks

Status: DEFERRED

- Existing `gz_frame_id` parser warnings for LiDAR, IMU, and camera remain
  unchanged from Phase 5A.
- SLAM/map resource cost is high for a small robot computer: active mapping
  used approximately 686 MiB and 198% CPU in the observed sample.
- Mapping quality was accepted in the deterministic simulation world, not on a
  real cafe or real sensor.
- The Web UI service contract is type-compatible in the active runtime, but a
  browser-level save click was not part of this Phase 5B acceptance.
- Exact coverage percentage and loop-closure error were not independently
  instrumented.

## 30. What Is Proven

Status: PASS

- The production simulator and SLAM Toolbox run together on the verified path.
- The production LiDAR and odometry support a populated, structurally usable
  map.
- The map can be saved to the host bind mount.
- The saved YAML/PGM pair is valid and nonblank.
- SLAM can be stopped without leaving a stale `/map` publisher.
- The saved map can be reloaded by standalone Nav2 map server.
- Reloaded map metadata and occupancy counts match the final map.
- Sensor and stop behavior remain valid after the workflow.

## 31. What Is Not Proven

Status: NOT TESTED

- Autonomous navigation, path planning, controller behavior, or obstacle
  avoidance under Nav2.
- AMCL localization or NavigateToPose.
- Docking, ArUco alignment, mission execution, or cafe service behavior.
- Real-robot mapping or transfer of this map to real sensors.
- Multi-PC Web UI mapping/save integration.
- Exact quantitative loop-closure error and full map coverage percentage.

## 32. Phase 5B Gate

| Gate | Result | Status |
| --- | --- | --- |
| Production physics unchanged | SDF SHA identical before/after | PASS |
| `/scan` healthy | Payload and approximately 10 Hz | PASS |
| `/odom` healthy | Payload and approximately 29 Hz | PASS |
| TF chain healthy | Required pre-SLAM chain resolved | PASS |
| SLAM starts | One `/slam_toolbox` instance | PASS |
| `/map` populated | 42,642 cells with occupied/free/unknown data | PASS |
| Map structural quality | Usable walls and shelf geometry | PASS |
| `map → odom` continuity | Resolved after init; no persistent failure | PASS |
| Map save | CLI exit 0 | PASS |
| Host persistence | YAML and PGM visible under `maps/` | PASS |
| YAML validation | Required fields and image reference valid | PASS |
| PGM validation | P5, 207×206, nonblank | PASS |
| Map reload | Standalone map server active | PASS |
| Reload equivalence | Dimensions/counts equal | PASS |
| Sensor regression | Required representative payloads present | PASS |
| Physics sanity | Zero command produced near-zero twist | PASS |
| Runbook updated | Verified workflow and Quick Mapping Demo | PASS |
| Build validation | rosdep/colcon/static checks pass | PASS |

## 33. Recommendation

**PHASE 5B: SLAM MAPPING, SAVE & RELOAD ACCEPTANCE — PASS**
**PHASE 5 MAPPING GATE: PASS**
**PHASE 5: COMPLETE**

Do not automatically start Phase 6. The recommended next phase, only after
explicit authorization, is:

```text
PHASE 6A — NAV2 READINESS, SAVED-MAP LOCALIZATION & COSTMAP CONTRACT AUDIT
```

It should first establish saved-map handling, localization strategy, TF
ownership, footprint, and costmap sensor contracts before autonomous navigation.

## Required Final Answers

1. **Production SDF SHA before/after?** `dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37` both before and after.
2. **Was physics changed?** No; Phase 4 physics remained frozen.
3. **Exact simulator startup command?** `docker compose up -d amr-sim`.
4. **Exact SLAM startup command?** `ros2 launch amr_simulation slam.launch.py use_sim_time:=true`.
5. **Was `/scan` healthy during mapping?** Yes, payload active at approximately 10.8–12 Hz in the mapping capture.
6. **Was `/odom` healthy during mapping?** Yes, approximately 29 Hz with changing pose.
7. **Did `map → odom` remain available?** Yes, it resolved after SLAM initialization.
8. **Any duplicate TF authority?** No duplicate `map → odom` or odometry authority was observed.
9. **How was the robot explored?** Bounded forward/stop/turn/stop segments around the interior perimeter and back near start.
10. **Approximate explored coverage?** Perimeter and representative shelf/open-area scan coverage; exact percentage NOT TESTED.
11. **Final map resolution?** `0.05 m/cell`.
12. **Final map width/height cells?** `207×206`.
13. **Final physical map dimensions?** `10.35×10.30 m`.
14. **Occupied cell count?** `3,135`.
15. **Free cell count?** `36,799`.
16. **Unknown cell count?** `2,708`.
17. **Any severe duplicated walls?** No.
18. **Any severe ghosting?** No.
19. **Any severe map discontinuity?** No.
20. **Any persistent TF failure?** No.
21. **Did map save succeed?** Yes, exit `0` and `Map saved successfully`.
22. **Exact map save command?** `ros2 run nav2_map_server map_saver_cli -f /maps/amr_map`.
23. **Exact saved YAML path?** Host `maps/amr_map.yaml`; container `/maps/amr_map.yaml`.
24. **Exact saved image path?** Host `maps/amr_map.pgm`; container `/maps/amr_map.pgm`.
25. **Were files visible on host?** Yes.
26. **Saved YAML valid?** Yes.
27. **Saved image valid/nonblank?** Yes, P5 207×206 with three intensity values.
28. **Runtime save service endpoint?** `/map_saver/save_map` (`nav2_msgs/srv/SaveMap`) and `/slam_toolbox/save_map` (`slam_toolbox/srv/SaveMap`) both present.
29. **Web UI expected endpoint?** `/slam_toolbox/save_map` with `slam_toolbox/srv/SaveMap`.
30. **How was endpoint mismatch handled?** Runtime inspection found no missing endpoint; no source change was required. CLI remained authoritative for host persistence.
31. **Was SLAM stopped cleanly?** Yes, SIGINT removed all SLAM nodes and `/map` publisher.
32. **Was saved map reloaded?** Yes.
33. **Exact reload command?** `ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=/maps/amr_map.yaml -p use_sim_time:=true`, then lifecycle configure/activate calls.
34. **Did reloaded `/map` appear?** Yes.
35. **Reload resolution/dimensions?** `0.05 m/cell`, `207×206`.
36. **Pre-save/reload comparison?** Occupied/free/unknown counts and dimensions equal; origin differs only by expected YAML rounding.
37. **Sensor regression?** PASS for all required topics and representative payloads.
38. **Physics sanity?** PASS; final odometry twist was effectively zero after stop.
39. **`gz_frame_id` warning status?** DEFERRED; unchanged baseline warning.
40. **Simulation-only resource usage?** `125.89% CPU`, `551 MiB`, `113 PIDs`.
41. **Active mapping resource usage?** `198.99% CPU`, `686 MiB`, `198 PIDs`; active SLAM idle sample was `212.74%`, `640.7 MiB`, `182 PIDs`.
42. **Peak observed memory/swap?** `686 MiB` container memory; host snapshot `3.5 GiB` swap used and `469 MiB` free.
43. **Was runbook updated?** Yes.
44. **Was Quick Mapping Demo added?** Yes.
45. **rosdep result?** PASS; all required rosdeps installed.
46. **colcon result?** PASS; 5 packages finished.
47. **git diff check?** PASS, exit `0`.
48. **Phase 5B gate?** PASS.
49. **Phase 5 final status?** PHASE 5 COMPLETE.
50. **What remains for the next phase?** Explicit authorization before Phase 6A Nav2 readiness/localization/costmap contract audit; no automatic start.

## Evidence Index

- Baseline: `docs/evidence/phase5b/baseline/`
- Mapping: `docs/evidence/phase5b/mapping/`
- TF: `docs/evidence/phase5b/tf/`
- Map metrics/preview: `docs/evidence/phase5b/map/`
- Save: `docs/evidence/phase5b/save/`
- Reload: `docs/evidence/phase5b/reload/`
- Logs: `docs/evidence/phase5b/logs/`
- Resources: `docs/evidence/phase5b/resources/`
- Validation: `docs/evidence/phase5b/validation/`

STOP CONDITION: Phase 5B and Phase 5 are complete. Phase 6 was not started.
