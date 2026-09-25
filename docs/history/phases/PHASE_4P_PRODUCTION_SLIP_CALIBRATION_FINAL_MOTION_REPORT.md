# PHASE 4P — APPLY SELECTED SLIP1 CALIBRATION + FINAL PRODUCTION MOTION REVALIDATION

Date: 2026-09-20  
Project: Cafe Service AMR — ROS 2 Jazzy / Gazebo Harmonic  
Workspace: ros2_ws  
Production model: ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf

Status vocabulary: PASS, FAIL, BLOCKED, DEFERRED, NOT TESTED.

## 1. Executive Summary

The Phase 4O-approved calibration was applied to the actual production SDF:
both drive-wheel slip1 values changed from 0.035 to 0.000. No other
production field changed.

Twelve counted fresh production runs were completed: three CCW, three CW,
three forward, and three reverse. Independent ground truth came from
/world/amr_world/dynamic_pose/info; /odom remained comparison output.

All physical motion gates passed:

- worst CCW yaw error: 0.376°;
- worst CW yaw error: 0.573°;
- worst forward translation error: 0.463%;
- worst reverse translation error: 0.658%;
- worst forward D2: 0.00000250 m;
- worst reverse D2: 0.00000000 m.

PHASE 4P: PRODUCTION CALIBRATION APPLIED AND REVALIDATED — PASS

PHASE 4 PHYSICAL MOTION GATE: PASS

PHASE 4: COMPLETE

PHASE 5: READY FOR AUTHORIZATION — NOT STARTED

## 2. Repository / Git Safety

- Root: /home/deden/Documents/my-project/ros2-software-amr
- ROS workspace: ros2_ws
- Simulation package: ros2_ws/src/amr_simulation
- Production model: ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf
- Branch: main
- HEAD: 3ddde28b668d646fed8f9e39188a9f1153e74a28

Pre-existing workspace changes were preserved. No reset, clean, stash,
restore, checkout, switch, commit, or push was run. The tracked pre-existing
diff remained 23 files changed, 352 insertions(+), 358 deletions(-).

The production model path is untracked in the existing worktree, so its
production diff was audited byte-for-byte against the pre-write backup rather
than relying on git diff to display an untracked file.

Status: PASS.

## 3. Phase 4O Authorization

Phase 4O authorized exactly slip1=0.000 on both drive wheels. It was the only
tested value passing turn, straight, D2, symmetry, wheel-tracking, and
stability gates. Phase 4O required this separate authorized Phase 4P before
changing production.

Status: PASS.

## 4. Pre-Write Production Baseline

Before editing:

- wheel_left_link slip1 = 0.035
- wheel_right_link slip1 = 0.035

Pre-4P SHA:
56c347599eb0f078aa4b0107578655fe98681d034e0a88e945269cbfc92b89fb

A byte-preserving backup is retained at
docs/evidence/phase4p/pre-write/model.sdf.before.

Status: PASS.

## 5. Production Change

Exactly these two values changed:

- wheel_left_link: slip1 0.035 -> 0.000
- wheel_right_link: slip1 0.035 -> 0.000

No wheel radius/separation, caster, anti-tip, mass, inertia, COM, DiffDrive,
acceleration, deceleration, world, sensor, topic, TF, or Docker configuration
changed.

Status: PASS.

## 6. Structural Diff Audit

The backup-to-production comparison contains exactly two changed XML values.
The programmatic assertion verified that two old slip1 values were replaced by
two new slip1 values and that the resulting file equals the exact replacement
of those values, with no other byte changes.

Evidence:
docs/evidence/phase4p/pre-write/production-model.diff
docs/evidence/phase4p/pre-write/structural-audit.txt

Status: PASS.

## 7. Production SHA Transition

- pre-4P SHA: 56c347599eb0f078aa4b0107578655fe98681d034e0a88e945269cbfc92b89fb
- post-edit SHA: dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37
- final SHA: dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37

All 12 counted runtime containers independently reported the final SHA.

Status: PASS.

## 8. Build / Launch Validation

Every counted run built a fresh disposable workspace from the edited
production source with colcon build --symlink-install, then launched the
normal amr_simulation production path. A final full validation container also
completed rosdep and colcon successfully.

Status: PASS.

## 9. Fresh-Start Test Method

Each counted run used a fresh Docker container, fresh ROS domain, fresh Gazebo
partition, fresh workspace copy, fresh robot state, and the same world and
command windows. The probe used one-second pre-idle, four-second active
command, five-second post-zero observation, and 50 Hz requested sampling.

Invalid attempts were excluded:

- reverse-1: startup timeout waiting for /clock and /odom; rerun passed.
- forward-3 and reverse-3: probe path typo before runtime; corrected reruns
  passed.

These attempts produced no motion trace and were not counted as physical
failures.

Status: PASS.

## 10. Ground-Truth Method

The independent physical pose source was
/world/amr_world/dynamic_pose/info. /odom was used only for comparison.
Wheel joint state, command, simulation time, pose age, T0-T5 markers, and D1-D3
were recorded in every trace.

Maximum ground-pose age was 0.092 s in forward, 0.021 s in reverse,
0.023 s in CCW, and 0.088 s in CW.

Status: PASS.

## 11. CCW Production Results

| Run | Physical yaw | /odom yaw | Error | Ratio |
| --- | ---: | ---: | ---: | ---: |
| CCW-1 | 87.636° | 87.261° | 0.376° | 1.0043 |
| CCW-2 | 86.803° | 86.528° | 0.275° | 1.0032 |
| CCW-3 | 86.757° | 86.826° | 0.069° | 0.9992 |
| Mean | — | — | 0.240° | — |
| Worst | — | — | 0.376° | — |

Status: PASS.

## 12. CW Production Results

| Run | Physical yaw | /odom yaw | Error | Ratio |
| --- | ---: | ---: | ---: | ---: |
| CW-1 | 87.709° | 87.353° | 0.356° | 1.0041 |
| CW-2 | 87.055° | 87.009° | 0.046° | 1.0005 |
| CW-3 | 87.032° | 86.459° | 0.573° | 1.0066 |
| Mean | — | — | 0.325° | — |
| Worst | — | — | 0.573° | — |

Status: PASS.

## 13. Turn Acceptance

Both worst turn errors are below the 5.0° gate. Maximum mirrored CCW/CW
physical yaw error was 0.390°; no historical directional failure reappeared.

Status: PASS.

## 14. Forward Production Results

| Run | Translation error | D1 | D2 | D3 |
| --- | ---: | ---: | ---: | ---: |
| Forward-1 | 0.463% | 0.036960 m | 0.00000250 m | 0.00000250 m |
| Forward-2 | 0.026% | 0.040095 m | 0.00000000 m | 0.00000450 m |
| Forward-3 | 0.316% | 0.040886 m | 0.00000000 m | 0.00001350 m |
| Mean | 0.268% | 0.039314 m | 0.00000083 m | 0.00000683 m |
| Worst | 0.463% | 0.040886 m | 0.00000250 m | 0.00001350 m |

Worst lateral drift was 1.22e-12 m; worst yaw drift was 2.13e-10°.

Status: PASS.

## 15. Reverse Production Results

| Run | Translation error | D1 | D2 | D3 |
| --- | ---: | ---: | ---: | ---: |
| Reverse-1 | 0.000006% | 0.041867 m | 0.00000000 m | 0.00003250 m |
| Reverse-2 | 0.396% | 0.041873 m | 0.00000000 m | 0.00002700 m |
| Reverse-3 | 0.658% | 0.040700 m | 0.00000000 m | 0.00000000 m |
| Mean | 0.351% | 0.041480 m | 0.00000000 m | 0.00001983 m |
| Worst | 0.658% | 0.041873 m | 0.00000000 m | 0.00003250 m |

Worst lateral drift was 8.38e-13 m; worst yaw drift was 1.16e-10°.

Status: PASS.

## 16. Straight Acceptance

Forward worst translation error was 0.463%; reverse worst was 0.658%.
Both are below the 5.0% gate.

Status: PASS.

## 17. D1 Results

Forward D1 mean/worst: 0.039314 / 0.040886 m.  
Reverse D1 mean/worst: 0.041480 / 0.041873 m.

D1 remains nonzero but is consistent and materially below the old production
slip1=0.035 response.

Status: PASS.

## 18. D2 Results

Forward D2 mean/worst: 0.00000083 / 0.00000250 m.  
Reverse D2 mean/worst: 0.00000000 / 0.00000000 m.

Both are below the 0.010 m gate in every counted run.

Status: PASS.

## 19. D3 Results

Forward D3 mean/worst: 0.00000683 / 0.00001350 m.  
Reverse D3 mean/worst: 0.00001983 / 0.00003250 m.

Status: PASS.

## 20. Stop Acceptance

The D2 stop gate passed forward and reverse in all three fresh repeats. No bad
repeat was hidden by averaging.

Status: PASS.

## 21. Wheel Tracking

Steady-state samples were evaluated after T1+0.1 s and before the zero-command
transition. Expected wheel targets used the unchanged wheel radius 0.09 m and
separation 0.42 m.

- Turn target magnitude: 0.933333 rad/s.
- Straight target magnitude: 2.222222 rad/s.
- Maximum active-command velocity error: approximately 1.44e-9 rad/s.
- Wheel position changes had correct signs and mirrored left/right behavior.
- CCW/CW and forward/reverse wheel positions remained kinematically valid.

No wheel radius, separation, controller, or odometry scaling was changed.

Status: PASS.

## 22. Directional Symmetry

Maximum physical mirror yaw error was 0.390°. Maximum same-wheel mirrored
velocity mismatch was 0.0257 rad/s, small relative to the 0.933333 rad/s
turn target and without a directional failure pattern.

Status: PASS.

## 23. Static / Dynamic Stability

Across the 12 motion traces:

- maximum absolute roll: 2.42e-10 rad;
- maximum absolute pitch: 1.42e-9 rad;
- ground-height range: 8.27e-7 m;
- no caster lockup, anti-tip drag, unexpected settling, or support instability
  was observed.

Status: PASS.

## 24. Contact Sanity Check

A production-equivalent disposable clone was generated from the edited model.
Its manifest records the final production SHA and no physics/controller
changes. In the representative CCW runtime:

- left drive contact: active, max normal force 69.998 N;
- right drive contact: active, max normal force 63.717 N;
- front caster contact: active, max normal force 50.499 N;
- rear caster contact: active, max normal force 47.874 N;
- contact depth: approximately 1.9-2.6e-9 m;
- anti-tip contacts: no payload observed.

Tangential force/slip velocity was unavailable.

Status: PASS for primary contact sanity; tangential telemetry NOT TESTED.

## 25. Sensor Regression

The edited production runtime provided the required types and representative
payloads:

| Topic | Result |
| --- | --- |
| /clock | PASS |
| /cmd_vel | PASS, subscription |
| /odom | PASS |
| /tf | PASS |
| /tf_static | PASS |
| /scan | PASS |
| /imu | PASS |
| /camera/image_raw | PASS |
| /camera/camera_info | PASS |

Observed rates were approximately /scan 9.62 Hz, /imu 96.42 Hz,
/camera/image_raw 13.65 Hz, and /camera/camera_info 14.41 Hz. Image and
camera-info payloads were available, including 640x480 and frame
camera_rgb_optical_frame.

Status: PASS.

## 26. ROS Interface Contract

No ROS-facing topic or frame was renamed. Camera TF remained:

camera_link -> camera_rgb_frame -> camera_rgb_optical_frame

LiDAR frame base_scan and IMU frame imu_link resolved from base_link.
Existing gz_frame_id parser warnings remained unchanged and are not caused by
the two slip1 edits.

Status: PASS for contract; DEFERRED for existing warnings.

## 27. Build Validation

- Diagnostic/unit tests: 28 passed — PASS.
- Python compilation: PASS.
- SDF/XML validation: 6 files — PASS.
- Xacro XML and expansion: PASS.
- YAML validation: 8 files — PASS.
- docker compose config -q: PASS.
- git diff --check: PASS.
- rosdep update: PASS.
- rosdep install --from-paths src --ignore-src -r -y: PASS.
- Full colcon build --symlink-install: 5 packages — PASS.

## 28. Resource Snapshot

Representative single edited-production sensor runtime:

Docker CPU 195.58%  
Docker RAM 563.5 MiB / 15.24 GiB  
Docker PIDs 103  
Host RAM 15 GiB total, 6.9 GiB available  
Host swap 4.0 GiB total, 1.2 GiB available

Concurrent motion batches peaked at approximately 379.31% CPU, 521.2 MiB,
and 105 PIDs. The contact-instrumented clone peaked at 549.60% CPU, 559.6
MiB, and 172 PIDs; this is instrumentation and concurrent-runtime overhead,
not a production physics regression.

All disposable Phase 4P containers were removed.

Status: PASS.

## 29. Remaining Risks

- slip1=0.000 is simulator-calibrated; real-robot tire transfer remains
  unproven.
- Tangential contact force/slip velocity remains unavailable.
- Existing gz_frame_id warnings remain deferred.
- Current model has no variable cafe-payload mass model; payload variation was
  not introduced in Phase 4P.
- Camera validation passed in this runtime, but renderer-dependent behavior
  should still be checked in deployment environments.

Status: DEFERRED.

## 30. What Is Proven

- The authorized two-field production change was applied.
- The actual edited production model passed 12 fresh motion runs.
- Turn, straight, D2, wheel tracking, symmetry, and stability gates passed.
- The production runtime retained the ROS interface and sensor contract.
- The final production SHA is stable after validation.

Status: PASS.

## 31. What Is Not Proven

- Real-robot physical validity of simulator slip1=0.000.
- Direct tangential contact slip velocity or force.
- Behavior under variable cafe payload mass, which is not modeled here.
- Navigation-level behavior; Nav2, SLAM, and AMCL were not started.

Status: NOT TESTED.

## 32. Final Production Diff

The final production change is exactly two occurrences of:

- old: <slip1>0.035</slip1>
- new: <slip1>0.000</slip1>

in the left and right drive-wheel collision surfaces only.

Authoritative final SDF SHA:
dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37

Status: PASS.

## 33. Phase 4 Physical Motion Gate

| Gate | Result |
| --- | --- |
| CCW worst yaw error <= 5° | PASS |
| CW worst yaw error <= 5° | PASS |
| Forward worst translation error <= 5% | PASS |
| Reverse worst translation error <= 5% | PASS |
| Forward D2 <= 0.010 m | PASS |
| Reverse D2 <= 0.010 m | PASS |
| Wheel tracking | PASS |
| Directional symmetry | PASS |
| Stability | PASS |
| Fresh-run repeatability | PASS |

PHASE 4 PHYSICAL MOTION GATE: PASS

## 34. Phase 4 Final Status

PHASE 4P: PRODUCTION CALIBRATION APPLIED AND REVALIDATED — PASS

PHASE 4 PHYSICAL MOTION GATE: PASS

PHASE 4: COMPLETE

## 35. Recommendation / Phase 5 Readiness

Phase 5 may be authorized next, but it was not started automatically.

PHASE 5: READY FOR AUTHORIZATION — NOT STARTED

No Nav2, SLAM Toolbox, AMCL, docking, ArUco runtime, mission runtime, or Web
UI integration was started.

## Required Final Answers

1. Was production SDF edited? PASS — yes, authorized Phase 4P change.
2. Exactly what production fields changed? Both drive-wheel slip1 values, 0.035 -> 0.000.
3. Old production SHA? 56c347599eb0f078aa4b0107578655fe98681d034e0a88e945269cbfc92b89fb.
4. New production SHA? dd34b08457d696e6f1cb9702dc1d4119174d4c042eea56ded3d892f7fe4abc37.
5. Did anything besides the two drive-wheel slip1 fields change? PASS — no.
6. Final production slip1 left? 0.000.
7. Final production slip1 right? 0.000.
8. Number of fresh CCW runs? 3 counted runs.
9. CCW mean/worst yaw error? 0.240° / 0.376°.
10. Number of fresh CW runs? 3 counted runs.
11. CW mean/worst yaw error? 0.325° / 0.573°.
12. CCW/CW mirror error? Maximum 0.390°.
13. Forward mean/worst translation error? 0.268% / 0.463%.
14. Reverse mean/worst translation error? 0.351% / 0.658%.
15. Forward D1 mean/worst? 0.039314 / 0.040886 m.
16. Reverse D1 mean/worst? 0.041480 / 0.041873 m.
17. Forward D2 mean/worst? 0.00000083 / 0.00000250 m.
18. Reverse D2 mean/worst? 0.00000000 / 0.00000000 m.
19. Forward D3 mean/worst? 0.00000683 / 0.00001350 m.
20. Reverse D3 mean/worst? 0.00001983 / 0.00003250 m.
21. Wheel tracking result? PASS — velocity, position signs, and left/right behavior valid.
22. Directional symmetry result? PASS — maximum mirror yaw error 0.390°.
23. Static/dynamic stability result? PASS.
24. Were primary contacts sane? PASS — both wheels and both casters active.
25. Was anti-tip contact observed? PASS — no anti-tip payload observed.
26. Tangential slip telemetry available? NOT TESTED.
27. /clock result? PASS — correct topic type and runtime publisher.
28. /odom result? PASS — correct type and payload.
29. /tf and /tf_static result? PASS.
30. LiDAR result? PASS — payload, rate, and base_scan frame.
31. IMU result? PASS — payload, rate, and imu_link frame.
32. Camera image result? PASS — payload, approximately 13.65 Hz, 640x480.
33. Camera-info result? PASS — payload, approximately 14.41 Hz, 640x480.
34. ROS interface contract result? PASS — no topic/frame rename.
35. gz_frame_id warning status? DEFERRED — existing warning unchanged.
36. Unit/diagnostic test result? PASS — 28 tests passed.
37. rosdep result? PASS.
38. colcon result? PASS — 5 packages.
39. git diff check result? PASS.
40. Resource snapshot? Single production sensor runtime: 195.58% CPU, 563.5 MiB RAM, 103 PIDs; host 6.9 GiB RAM and 1.2 GiB swap available.
41. Are any required physical motion gates failing? PASS — none.
42. Phase 4 physical motion gate? PASS.
43. Phase 4 final status? PHASE 4: COMPLETE.
44. Is Phase 5 ready to be authorized? PASS — ready for explicit authorization, not started.
45. What remains deferred/unproven? Real-robot transfer, tangential contact telemetry, variable payload-mass behavior, existing gz_frame_id cleanup, and all Phase 5 functionality.

STOP CONDITION: Phase 4P complete. Phase 5 was not started.
