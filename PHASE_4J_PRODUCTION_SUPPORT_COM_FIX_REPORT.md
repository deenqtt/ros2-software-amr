# Phase 4J — Production Support / COM Fix Report

Date: 2026-09-17  
Project: Cafe Service AMR, ROS 2 Jazzy, Gazebo Harmonic  
Decision: **BLOCKED**  
Phase 5: **DEFERRED**

## 1. Scope and stop gate

This phase applied one controlled support/contact change to the real Cafe AMR
Harmonic production model. It did not start Nav2, SLAM Toolbox, AMCL, docking,
ArUco runtime, mission integration, Web UI integration, or a Cafe-world redesign.
No fake odometry scaling was used.

The production motion gate remains **BLOCKED** because the corrected model is
static-stable and tracks straight motion, but its repeated CCW rotation is not
within the acceptance threshold and forward/reverse stopping has measurable
physical settling drift.

## 2. Repository confirmation

- Repository root: `/home/deden/Documents/my-project/ros2-software-amr`
- ROS workspace: `ros2_ws`
- Simulation package: `ros2_ws/src/amr_simulation`
- Production Cafe model: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Authoritative runtime report: `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`
- Prior reports read: `PHASE_4G_MOTION_CALIBRATION_REPORT.md`,
  `PHASE_4H_PHYSICS_ISOLATION_REPORT.md`, `PHASE_4I_DIFFDRIVE_ROOT_CAUSE_REPORT.md`
- ROS contract read: `docs/ROS_INTERFACE_CONTRACT.md`
- Branch: `main`
- HEAD at Phase 4J baseline: `3ddde28b668d646fed8f9e39188a9f1153e74a28`

The repository identity matched the requested Cafe AMR project before any
production modification.

## 3. Safety baseline

No `reset`, `clean`, `stash`, `commit`, `push`, or branch switch was performed.
Existing uncommitted Phase 0–4 work was preserved. The initial production model
checksum was:

```text
b2c29743a07ecfafb117026e1f89f5dddfb8adca4e7ecb412b71b423b4c248b3
```

The final production model checksum after the single support change is:

```text
c0cd6ff388a58c4eb987b8b3307a0e8bd829cf0c219dfc6fb3357189765f9e81
```

## 4. Root cause

The production model visually contained two front/rear passive caster spheres,
but their collision spheres were only `0.02 m` radius while their link centres
were at `z=0.055 m`. Their lowest collision point was therefore `z=0.035 m` and
they were not ground supports. The four anti-tip spheres were also elevated:
their lowest point was `z=0.050 m`.

The only normal ground contacts were the two drive wheels. This produced a
degenerate two-point support line under a tall Cafe stack. The empty-model COM
projection was not inside a valid 2D support polygon. The pre-change model
settled with a large pitch and the physical body diverged from DiffDrive
odometry, matching the Phase 4H/4I diagnosis.

## 5. Independent Gazebo ground truth method

Ground truth was obtained independently with:

```text
gz model -m amr_robot -p
```

The probe sampled `/odom` independently and did not derive Gazebo pose from
odometry, command velocity, wheel integration, or an odometry scale factor. The
probe reference point is explicitly:

```text
base_footprint/model_origin
```

Raw world-frame `x/y` deltas are retained. Ground distance magnitude, odometry
distance magnitude, body-forward displacement, body-lateral displacement,
wrapped yaw deltas, and model-origin arc are reported separately. The small
model-origin arc during caster-supported pure rotation is therefore visible and
not silently treated as an odometry correction.

## 6. Production support geometry audit before the fix

| Support | XY (m) | Centre Z (m) | Collision radius (m) | Lowest point (m) | Ground contact |
|---|---:|---:|---:|---:|---|
| left drive wheel | `(0,+0.21)` | 0.090 | 0.090 | 0.000 | PASS |
| right drive wheel | `(0,-0.21)` | 0.090 | 0.090 | 0.000 | PASS |
| front caster | `(+0.24,0)` | 0.055 | 0.020 | 0.035 | FAIL |
| rear caster | `(-0.24,0)` | 0.055 | 0.020 | 0.035 | FAIL |
| four anti-tip spheres | `(±0.24,±0.24)` | 0.090 | 0.040 | 0.050 | DEFERRED |

The active normal support polygon was only the line segment between the two drive
wheels at `x=0`, not a valid area.

## 7. Empty-model mass and COM calculation

All production SDF links with inertial mass were included. Empty-model total mass
was `24.700 kg`. The weighted COM in the model frame was:

```text
COM = (x=+0.002581 m, y=0.000000 m, z=0.297713 m)
```

Main contributors included the `18.0 kg` chassis at `z=0.180 m`, three `1.2 kg`
trays at `z=0.480/0.760/1.040 m`, the `0.35 kg` top cap at `z=1.160 m`, and the
forward camera at `x=0.255 m, z=0.980 m`.

With only the two wheel contacts, the support set was degenerate and the COM
projection was outside that line because `x=+0.002581 m`. After enabling the
existing caster collisions, the support points become:

```text
(0,+0.21), (0,-0.21), (+0.24,0), (-0.24,0)
```

This is a valid diamond. The COM projection satisfies
`abs(x)/0.24 + abs(y)/0.21 = 0.01075`, so it is inside the post-fix polygon.

## 8. Caster and anti-tip contact audit

The existing caster visual radius was `0.055 m`; only its collision radius was
undersized. Both caster collision radii were changed to `0.055 m`, placing their
lowest points at the ground plane while preserving link locations, visual design,
ball joints, and low-friction contact settings.

The anti-tip supports were not changed. Their `0.05 m` clearance makes them
secondary supports rather than normal load-bearing contacts in the level static
configuration. Direct normal-force/contact-wrench telemetry was unavailable in
the active world topic list and is **NOT TESTED**.

## 9. Wheel geometry/contact findings

Wheel geometry remains internally coherent:

- left/right wheel centres: `y=+0.21/-0.21 m`;
- wheel radius: `0.09 m`;
- wheel separation: `0.42 m`;
- rolled cylinder orientation: `-1.5707963 rad`;
- joint axis: `0 0 1`;
- wheel lowest point: `z=0`;
- drive-wheel contact friction: `mu=1.0`, `mu2=1.0`, `slip1=0.035`, `slip2=0.0`.

No wheel radius, separation, axis, or contact friction was changed in Phase 4J.
No wheel-lift telemetry was available; geometry and static pose indicate the
drive wheels remain grounded, while direct normal load is **NOT TESTED**.

## 10. Friction and slip findings

Caster friction remained `mu=0.01`, `mu2=0.01`, `slip1=0.2`, `slip2=0.2`.
This is intentionally low to avoid caster drag. Straight travel has no observed
lateral drift in the three repeats, but the repeatable CCW undershoot indicates
the ball-caster/support mechanism still has direction-dependent dynamic
resistance. Detailed contact-slip decomposition is **NOT TESTED** because no
contact telemetry was exposed.

## 11. Mass and inertia findings

No production mass, COM, or inertia values were modified. The post-fix static
model remained level, so the existing positive inertial matrices are sufficient
for this controlled support test. Payload-free operation was tested; payload
behaviour remains **DEFERRED**.

## 12. DiffDrive findings

The native Gazebo DiffDrive configuration was preserved exactly:

```text
left_joint       = wheel_left_joint
right_joint      = wheel_right_joint
wheel_separation = 0.42 m
wheel_radius     = 0.09 m
```

The ROS-facing topics remained `/cmd_vel` and `/odom`, and no odometry scaling or
fake pose correction was introduced. Straight odometry agrees within the target
threshold after the support change. CCW physical yaw does not yet agree with the
DiffDrive odometry target.

## 13. Physics findings

The world physics was unchanged: `max_step_size=0.001 s`, real-time factor `1.0`,
and update rate `1000 Hz`. Static level settling after the caster change shows
that support geometry was the first credible production correction. The remaining
CCW asymmetry and forward/reverse post-stop drift need a separate controlled
physics/contact investigation and must not be solved by odometry manipulation.

## 14. Exact production change

Only these two matching production collision geometry entries changed:

```diff
- <caster_front_link> collision sphere radius 0.02
+ <caster_front_link> collision sphere radius 0.055
- <caster_rear_link> collision sphere radius 0.02
+ <caster_rear_link> collision sphere radius 0.055
```

No anti-tip geometry, wheel geometry, mass/inertia, friction, DiffDrive
configuration, sensor topic, frame, or ROS contract was renamed or changed.

## 15. Static headless validation after the fix

The robot was launched headlessly and observed before any motion command. Three
settled samples were:

| Sample | X (m) | Y (m) | Z (m) | Roll (rad) | Pitch (rad) | Yaw (rad) |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.000000 | 0.000000 | -0.000001 | ~0 | ~0 | ~0 |
| 2 | 0.000000 | 0.000000 | -0.000001 | ~0 | ~0 | ~0 |
| 3 | 0.000000 | 0.000000 | -0.000001 | ~0 | ~0 | ~0 |

Static result: **PASS** for level settling, no observed drift/rocking, valid
post-fix support geometry, and stable model pose. Direct contact normal force is
**NOT TESTED**.

For comparison, the pre-change production baseline settled at approximately
`pitch=0.147966 rad` (`8.48°`) and was stopped before motion testing by the
Phase 4J static gate.

## 16. Probe metric test-first result

The pure metric test was intentionally run before the implementation and failed
with `ModuleNotFoundError` because the metric module did not exist. The minimal
implementation was then added and the test passed:

```text
PYTHONPATH=scripts python3 scripts/test_phase4g_motion_metrics.py
phase4g motion metric tests passed
```

The probe now reports raw world XY, ground/odom distance magnitudes, body-frame
forward/lateral displacement, wrapped yaw error, an explicit reference point,
and `ground_origin_arc_m` for caster-induced model-origin motion.

## 17. Smoke matrix

One fresh headless smoke run used the required commands:

| Test | Command | Duration | Result |
|---|---:|---:|---|
| T1 forward | `linear.x=+0.20 m/s` | 5 s | FAIL threshold; motion direction correct |
| T2 reverse | `linear.x=-0.20 m/s` | 5 s | FAIL threshold; motion direction correct |
| T3 CCW | `angular.z=+0.40 rad/s` | 4 s | FAIL |
| T4 CW | `angular.z=-0.40 rad/s` | 4 s | PASS angular threshold |
| T5 stop | zero command, 2 s observation | 2 s | PASS standalone zero observation |

The full gate is **BLOCKED** despite the standalone T5 observation.

## 18. Repeat protocol

Three independent repeats were obtained by reinitializing the headless Gazebo
container/model before each complete T1–T4 sequence. Every segment published
commands for the requested wall duration, captured simulation elapsed time, then
published zero velocity and measured the post-command settling window. Gazebo
pose was captured independently and `/odom` was sampled separately.

Wheel joint state capture was **NOT TESTED** as a usable runtime signal: the
production `/joint_states` topic had no message during the check. The prior
diagnostic JointStatePublisher was not inserted into production.

## 19. Three-repeat forward results

| Repeat | Ground distance (m) | Odom distance (m) | Error | Forward (m) | Lateral (m) | Stop drift (m) |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.961303 | 0.983800 | 2.287% | +0.961303 | 0.000000 | 0.019697 |
| 2 | 0.965474 | 0.990200 | 2.497% | +0.965474 | 0.000000 | 0.021777 |
| 3 | 0.912242 | 0.936200 | 2.559% | +0.912242 | 0.000000 | 0.021158 |

Average translation error: **2.448%**. Worst: **2.559%**. Result: **PASS** for
distance and direction; post-stop drift remains a risk.

## 20. Three-repeat reverse results

| Repeat | Ground distance (m) | Odom distance (m) | Error | Forward (m) | Lateral (m) | Stop drift (m) |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.963784 | 0.989000 | 2.550% | -0.963784 | 0.000000 | 0.022207 |
| 2 | 0.974190 | 0.998400 | 2.425% | -0.974190 | 0.000000 | 0.020631 |
| 3 | 0.968871 | 0.991200 | 2.253% | -0.968871 | 0.000000 | 0.019883 |

Average translation error: **2.409%**. Worst: **2.550%**. Result: **PASS** for
distance and direction; post-stop drift remains a risk.

## 21. Three-repeat CCW results

| Repeat | Ground yaw (deg) | Odom yaw (deg) | Yaw error | Ground origin arc (m) |
|---:|---:|---:|---:|---:|
| 1 | +72.682 | +90.779 | 18.097° | 0.016971 |
| 2 | +73.484 | +91.582 | 18.097° | 0.017275 |
| 3 | +73.072 | +91.169 | 18.097° | 0.017115 |

Average yaw error: **18.097°**. Worst: **18.097°**. Result: **FAIL**. The
undershoot is highly repeatable, so it is not random startup noise.

## 22. Three-repeat CW results

| Repeat | Ground yaw (deg) | Odom yaw (deg) | Yaw error | Ground origin arc (m) |
|---:|---:|---:|---:|---:|
| 1 | -90.946 | -90.504 | 0.441° | 0.015124 |
| 2 | -90.609 | -90.161 | 0.448° | 0.015535 |
| 3 | -91.016 | -90.573 | 0.443° | 0.015302 |

Average yaw error: **0.444°**. Worst: **0.448°**. Result: **PASS** for angular
accuracy, but CW/CCW symmetry as a pair is **FAIL** because CCW is outside the
threshold.

## 23. Stop behaviour

The standalone T5 zero-command observation reported zero ground displacement and
zero odometry linear/angular velocity. T1/T2 post-command settling windows,
however, showed physical drift of `0.0197–0.0222 m` while odometry velocity was
effectively zero. Therefore standalone stop is **PASS**, but motion-to-stop
settling behaviour is **FAIL** for a strict “reliably stops physical motion” gate.

## 24. Repeatability

Forward, reverse, and CW results are repeatable. CCW produces the same
approximately `18.1°` error in all three independent runs. Repeatability of the
observed failure is **PASS** as evidence; overall motion-gate repeatability is
**FAIL** because the two turn directions are not sufficiently symmetric.

## 25. Before/after motion table

The pre-change Phase 4J production run was correctly prevented from motion
testing because its static pose failed. The historical Phase 4G production
metrics are included as context; they used an older metric definition and are
not directly interchangeable with the frame-aware Phase 4J values.

| Test | Historical Phase 4G production | Phase 4J after caster collision fix | Gate |
|---|---|---|---|
| T1 forward | 89.01% average error | 2.448% average, 2.559% worst | PASS |
| T2 reverse | 38.80% average error | 2.409% average, 2.550% worst | PASS |
| T3 CCW | 90.98° average angular error | 18.097° average/worst | FAIL |
| T4 CW | 0.40° angular error, translation caveat | 0.444° average, 0.448° worst | PASS |
| T5 stop | unreliable in full motion gate | standalone PASS; T1/T2 settling FAIL | BLOCKED |

The Phase 4J controlled change materially corrected the support/COM failure for
static pose and straight travel, but did not complete the full production gate.

## 26. Translational and rotational error summary

- Forward average/worst translational error: **2.448% / 2.559%**.
- Reverse average/worst translational error: **2.409% / 2.550%**.
- CW average/worst rotational error: **0.444° / 0.448°**.
- CCW average/worst rotational error: **18.097° / 18.097°**.
- Straight lateral drift: **0.000 m** in all six straight-motion repeats.
- Pure-turn model-origin arc: approximately `0.015–0.017 m`; this is reported
  separately and is not used to claim straight translational accuracy.

## 27. Sensor regression

Fresh headless topic checks produced messages on:

| Interface | Result |
|---|---|
| `/clock` | PASS |
| `/cmd_vel` bridge subscription | PASS |
| `/odom` | PASS |
| `/tf` | PASS |
| `/tf_static` | PASS |
| `/scan` | PASS |
| `/imu` | PASS |
| `/camera/image_raw` | PASS |
| `/camera/camera_info` | PASS |

The static TF output preserved the required camera chain:

```text
camera_link → camera_rgb_frame → camera_rgb_optical_frame
```

No ROS-facing camera topic or frame was renamed. The camera remained the forward
main camera. Rear-camera and ArUco/docking behaviour remain **DEFERRED**.

## 28. XML/SDF/Xacro/YAML/Python validation

- Production and diagnostic SDF/XML parse: **PASS**.
- Xacro expansion of `amr_robot_harmonic.urdf.xacro`: **PASS**.
- ROS bridge YAML parse: **PASS**.
- Python metric tests: **PASS**.
- Probe/metric Python compilation in Jazzy container: **PASS**.
- `docker compose config --quiet`: **PASS**.
- `git diff --check`: **PASS**.

Gazebo still emits three existing `gz_frame_id` SDF warnings for the lidar, IMU,
and camera sensor elements. Sensor output and ROS frame checks remained live, but
the warning cleanup is **DEFERRED** because it is outside the one-variable
physics fix.

## 29. rosdep and colcon

Executed in the Jazzy container:

```text
rosdep install --from-paths src --ignore-src -r -y --rosdistro jazzy
#All required rosdeps installed successfully

colcon build --symlink-install
Summary: 5 packages finished [1.11s]
```

Result: **PASS**.

The attempted fresh Docker image rebuild was **BLOCKED** by a Docker Hub DNS
timeout while resolving `ros:jazzy-ros-base-noble`. Runtime verification used the
existing local Jazzy image with a fresh full colcon build over the mounted source;
this network limitation does not invalidate the container runtime evidence.

## 30. Headless runtime and resource usage

Headless Gazebo Harmonic spawn and bridge startup: **PASS**. The final resource
snapshot during active headless runtime was:

```text
docker stats --no-stream amr-sim-phase4j
CPU: 179.64%
Memory: 518.2 MiB / 15.24 GiB (3.32%)
PIDs: 91

free -h
Mem: 15 GiB total, 10 GiB used, 1.4 GiB free, 5.1 GiB available
Swap: 4.0 GiB total, approximately 7.5 MiB free
```

Memory availability is adequate for this run. Host swap is nearly exhausted and
is a remaining resource warning; it did not correlate with the repeatable CCW
motion error. GUI smoke was **NOT TESTED** because the headless physics gate did
not pass.

## 31. Files changed by Phase 4J

Phase 4J added or changed:

- `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
  — two existing caster collision radii changed `0.02 → 0.055 m`;
- `scripts/phase4g_motion_probe.py`
  — frame-aware metrics integration and clock QoS alignment;
- `scripts/phase4g_motion_metrics.py`
  — pure metric implementation;
- `scripts/test_phase4g_motion_metrics.py`
  — focused TDD regression tests;
- `docs/superpowers/plans/2026-09-17-phase-4j-production-support-com.md`
  — execution plan;
- `PHASE_4J_PRODUCTION_SUPPORT_COM_FIX_REPORT.md`
  — this report.

All earlier Phase 0–4G/4H/4I files and uncommitted user changes were preserved.

## 32. Git diff stat

The cumulative tracked worktree diff at completion remained:

```text
18 files changed, 282 insertions(+), 312 deletions(-)
```

`git diff --stat` does not include the untracked Phase 0–4J reports, diagnostic
models, plans, and probe files. The production SDF is also an existing untracked
Phase 4 artifact, so its Phase 4J change is represented in the final checksum and
the exact-change section rather than in the tracked diff stat.

## 33. Remaining risks

- CCW rotation remains `18.097°` below the approximately 90° odometry target.
- Forward/reverse post-stop physical drift is approximately `0.02 m` in the
  probe's 0.8-second settling window while odometry velocity is zero.
- Direct wheel/caster normal forces and contact-wrench/slip telemetry are
  **NOT TESTED**.
- Production `/joint_states` did not provide a usable message and is
  **NOT TESTED** for wheel-position capture.
- Empty payload-free model only; loaded tray dynamics are **DEFERRED**.
- Existing Gazebo `gz_frame_id` warnings remain.
- GUI smoke is **NOT TESTED**.
- Docker Hub image rebuild is **BLOCKED** by external DNS timeout.

## 34. Final recommendation

Production support/COM static gate: **PASS**.  
Straight forward/reverse distance gate: **PASS**.  
CW rotation gate: **PASS**.  
CCW rotation gate: **FAIL**.  
CW/CCW symmetry gate: **FAIL**.  
Strict motion-to-stop gate: **FAIL**.  
Sensor and ROS interface regression: **PASS**.  
Rosdep/colcon/headless checks: **PASS**.  
Overall Phase 4J production motion gate: **BLOCKED**.

Do not start Phase 5. The next authorized action should be a separately approved
contact/directional-resistance investigation, changing one meaningful variable at
a time. This report is the Phase 4J stopping point.
