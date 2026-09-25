# Phase 4K — Directional Resistance and Stop Dynamics Report

Date: 2026-09-18  
Project: Cafe Service AMR, ROS 2 Jazzy, Gazebo Harmonic  
Scope: production Cafe AMR motion/contact diagnostics only  
Phase 5: **DEFERRED**

## 1. Executive summary

The production Cafe AMR remains **BLOCKED** at the physical-motion gate.
Gazebo wheel joints and native DiffDrive kinematics are correct: the expected
pure-turn wheel speed is `0.933333 rad/s` with opposite signs, and the measured
joint velocities reach that value. The first directional divergence is after
the wheel joints, in physical contact/chassis motion.

The controlled caster A/B test isolates the active front caster as the main
cause of the repeatable CCW yaw deficit. With only the front caster active,
CCW settled yaw was `74.98°` versus `/odom` `91.67°`; with only the rear caster
active, it was `91.06°` versus `91.65°`. A mirror control did not provide a
robust production fix. Slip/friction candidates either destabilized the test
or failed to reach the requested simulation-time windows.

No production contact change was applied in Phase 4K because the only clearly
effective A/B change was disabling a caster collision, which conflicts with
the Phase 4J correction freeze. Production remains unchanged apart from the
existing diagnostic-only joint-state publisher added for this investigation.

The high-resolution timestamped test also separates command release from
settled stop: after zero command, wheel velocity decayed to approximately zero
by `0.50 s`, while the physical model continued moving for approximately
`0.039–0.040 m` during the following `0.50 s` in the captured run. The normal
Phase 4G probe measured approximately `0.028–0.032 m` residual movement after
its `0.8 s` settle window.

## 2. Git safety and repository identity

Repository checks confirmed the requested project before runtime work:

- root: `/home/deden/Documents/my-project/ros2-software-amr`
- ROS workspace: `ros2_ws`
- simulation package: `ros2_ws/src/amr_simulation`
- current Cafe AMR Harmonic model: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- authoritative runtime report: `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`
- branch: `main`
- HEAD: `3ddde28b668d646fed8f9e39188a9f1153e74a28`

No commit, push, reset, clean, stash, or branch switch was performed. Existing
Phase 0–4 work was preserved. Disposable candidate SDFs were generated under
`/tmp` or inside disposable containers only.

## 3. Phase 4J baseline

Phase 4J production evidence before this directional investigation:

| Test | Average error | Worst error | Result |
|---|---:|---:|---|
| Forward | `2.448%` | `2.559%` | PASS |
| Reverse | `2.409%` | `2.550%` | PASS |
| CCW | `18.097°` | `18.097°` | BLOCKED |
| CW | `0.444°` | `0.448°` | PASS |
| Stop | zero command reached zero pose delta | — | PASS |

Phase 4J had already changed the front and rear caster collision radii from
`0.020 m` to the visual/support radius `0.055 m`. Phase 4K did not revert that
production correction.

## 4. Wheel symmetry

Static XML/SDF audit:

| Property | Left | Right | Result |
|---|---:|---:|---|
| wheel centre X | `0.000 m` | `0.000 m` | PASS |
| wheel centre Y | `+0.210 m` | `-0.210 m` | PASS |
| wheel centre Z | `0.090 m` | `0.090 m` | PASS |
| collision radius | `0.090 m` | `0.090 m` | PASS |
| collision length | `0.045 m` | `0.045 m` | PASS |
| joint axis | `0 0 1` | `0 0 1` | PASS |
| ODE `mu/mu2` | `1.0/1.0` | `1.0/1.0` | PASS |
| ODE `slip1/slip2` | `0.035/0.0` | `0.035/0.0` | PASS |

The wheel separation is `0.420 m`; the radius is `0.090 m`.

## 5. Caster symmetry

Both passive casters are structurally symmetric:

| Property | Front | Rear | Result |
|---|---:|---:|---|
| centre X | `+0.240 m` | `-0.240 m` | PASS |
| centre Y | `0.000 m` | `0.000 m` | PASS |
| centre Z | `0.055 m` | `0.055 m` | PASS |
| visual/collision radius | `0.055/0.055 m` | `0.055/0.055 m` | PASS |
| ODE `mu/mu2` | `0.01/0.01` | `0.01/0.01` | PASS |
| ODE `slip1/slip2` | `0.2/0.2` | `0.2/0.2` | PASS |
| joint type | ball | ball | PASS |

Geometry is symmetric statically; dynamic resistance is not symmetric by
direction because the front-caster-only and rear-caster-only A/B runs differ.

## 6. Production joint instrumentation

The production model contains a diagnostic-only Harmonic
`JointStatePublisher` for `wheel_left_joint` and `wheel_right_joint`. It
publishes the Gazebo topic:

```text
/world/amr_world/model/amr_robot/joint_state
```

This is not part of the ROS application contract and does not alter ROS-facing
topics, frames, odometry, or sensor configuration. The parser records Gazebo
message timestamps, joint position, and joint velocity.

## 7. Expected wheel kinematics

For the high-resolution pure-turn command:

```text
v = 0.40 m/s equivalent angular command
separation = 0.42 m
radius = 0.09 m
omega_left  = -(0.40 * 0.42 / 2) / 0.09 = -0.933333 rad/s  [CCW]
omega_right = +(0.40 * 0.42 / 2) / 0.09 = +0.933333 rad/s  [CCW]
```

CW has the opposite signs. Straight `0.20 m/s` expects both wheels at
`2.222222 rad/s`. The pure helper tests and live joint samples agree with
these values: **PASS**.

## 8. CCW wheel-state results

Timestamped production high-resolution sample:

| Window | Left velocity | Right velocity | Position sign relation |
|---|---:|---:|---|
| `0.25 s` | `-0.5763` | `+0.5763` | opposite |
| `0.50 s` | `-0.9333` | `+0.9333` | opposite |
| `1.00 s` | `-0.9333` | `+0.9333` | opposite |
| `2.00 s` | `-0.9333` | `+0.9333` | opposite |
| `4.00 s` | `-0.9333` | `+0.9333` | opposite |
| zero `0.50 s` | approximately `0` | approximately `0` | settled |

Wheel command and wheel state are correct: **PASS**. Physical CCW yaw remains
directionally deficient: **BLOCKED**.

## 9. CW wheel-state results

Timestamped production high-resolution sample:

| Window | Left velocity | Right velocity | Position sign relation |
|---|---:|---:|---|
| `0.25 s` | `+0.5787` | `-0.5787` | opposite |
| `0.50 s` | `+0.9333` | `-0.9333` | opposite |
| `1.00 s` | `+0.9333` | `-0.9333` | opposite |
| `2.00 s` | `+0.9333` | `-0.9333` | opposite |
| `4.00 s` | `+0.9333` | `-0.9333` | opposite |
| zero `0.50 s` | approximately `0` | approximately `0` | settled |

CW wheel command and wheel state are correct: **PASS**.

## 10. First divergence layer

The evidence locates the first divergence after the wheel joints:

```text
/cmd_vel
  -> native DiffDrive target
  -> wheel joint position/velocity       PASS
  -> wheel/caster/chassis contact        first directional divergence
  -> physical base pose                  CCW deficit
  -> /odom integration                   kinematically consistent
```

No fake odometry scale or angular multiplier was introduced. Root-cause layer:
physical contact/chassis motion: **PASS**.

## 11. Time-window turn analysis

Ground truth was streamed from
`/world/amr_world/dynamic_pose/info` and parsed by model name, independently of
`/odom`. Ground-pose timestamp age was generally `0.002–0.018 s`; the initial
pre-command sample could be older because it was the last stream sample before
the probe window and was not used as a fresh command sample.

Production high-resolution relative yaw from command start:

| Window | CCW ground | CCW odom | CW ground | CW odom |
|---|---:|---:|---:|---:|
| `0.25 s` | `0.04°` | `1.72°` | `-1.64°` | `-1.70°` |
| `0.50 s` | `0.41°` | `6.50°` | `-6.77°` | `-6.46°` |
| `1.00 s` | `3.11°` | `18.18°` | `-18.27°` | `-18.14°` |
| `2.00 s` | `22.87°` | `40.77°` | `-41.01°` | `-40.66°` |
| `4.00 s` | `68.6°` | `86.7°` | `-86.8°` | `-86.7°` |

The direction-dependent divergence is already visible before zero command:
**BLOCKED**.

## 12. Caster directional-resistance test

The production four-support run has both casters active. The A/B candidates
were exact disposable copies of the current production SDF.

| Candidate | Active caster contact | Settled CCW ground | Settled CCW odom | Error | Result |
|---|---|---:|---:|---:|---|
| Production | front + rear | `73.58°` | `91.67°` | `18.10°` | BLOCKED |
| Front-only | front | `74.98°` | `91.67°` | `16.69°` | BLOCKED |
| Rear-only | rear | `91.06°` | `91.65°` | `0.59°` | PASS |

This is the strongest causal evidence in Phase 4K. The front caster contact is
the primary contributor to the CCW deficit.

## 13. Mirror test

The disposable mirror candidate swapped front/rear caster X poses while
preserving the same radius, friction, joint, mass, and DiffDrive values.

| Candidate | Settled CCW ground | Settled CCW odom | Difference | Result |
|---|---:|---:|---:|---|
| Mirrored caster poses | `91.74°` | `92.31°` | `0.58°` | PASS |

This was one run and does not establish repeatability. It supports a
front/rear contact-location hypothesis but is insufficient by itself for a
production change: **NOT TESTED** for a three-repeat mirror gate.

## 14. Front-only candidate

The front-only candidate kept front radius `0.055 m` and lifted the rear
collision radius to `0.015 m` in a disposable copy. Its settled results were:

| Direction | Ground | Odom | Error |
|---|---:|---:|---:|
| Forward | `0.9657 m` | `0.9998 m` | `3.41%` |
| Reverse | `0.9458 m` | `1.0002 m` | `5.44%` |
| CCW | `74.98°` | `91.67°` | `16.69°` |
| CW | `-92.12°` | `-91.67°` | `0.44°` |

The candidate is not a production fix: **BLOCKED**.

## 15. Rear-only candidate

The rear-only candidate kept rear radius `0.055 m` and lifted the front
collision radius to `0.015 m` in a disposable copy. Its settled results were:

| Direction | Ground | Odom | Error |
|---|---:|---:|---:|
| Forward | `0.9756 m` | `1.0002 m` | `2.46%` |
| Reverse | `0.9482 m` | `0.9978 m` | `4.97%` |
| CCW | `91.06°` | `91.65°` | `0.59°` |
| CW | `-92.09°` | `-91.65°` | `0.44°` |

The result is diagnostically strong but the structural support change is not
applied to production under the Phase 4J freeze: **DEFERRED**.

## 16. Four-point versus three-point support hypothesis

The current production model has four intended low-level contacts: two drive
wheels and front/rear passive spheres. The A/B evidence shows that the
three-point rear-only support has substantially better CCW behavior than the
four-point production arrangement. The result is consistent with an
overconstrained passive support/contact system, but direct contact forces were
not available to prove the exact constraint force distribution: **BLOCKED**.

The four anti-tip spheres remain raised secondary supports, not normal static
load-bearing contacts.

## 17. Contact telemetry

`gz topic -l` and topic inspection were attempted for contact/collision
telemetry. No usable world contact-wrench topic was exposed in the active
runtime. Direct normal-force, tangential-force, and slip-ratio measurements
were therefore unavailable: **NOT TESTED**.

## 18. Stop-command timing

The high-resolution probe captures command release at the exact simulation
deadline. At `first_zero_command`, the wheel velocity was still at the command
target (`±2.2222 rad/s` for translation or `±0.9333 rad/s` for the turn).
This is expected command/actuator deceleration behavior, not an odometry scale
hack: **PASS**.

## 19. Wheel stopping behavior

In the timestamped production run, both drive-wheel velocities were near zero
by the `zero_0.50s` sample after zero command. The wheel-state stream therefore
shows a reliable stop: **PASS**.

## 20. Physical stopping behavior

Physical pose did not settle at the same instant as the wheel joints. In the
forward and reverse high-resolution samples, the chassis continued moving
after the wheels reached approximately zero velocity. The final production
probe measured residual physical movement after its `0.8 s` settle period of
`0.0279–0.0322 m`; the high-resolution probe measured approximately
`0.039–0.040 m` during the later half-second after wheel stop: **BLOCKED**.

## 21. Braking and settling distance

High-resolution timestamped release-to-settle movement from the end of the
command was approximately:

| Direction | Ground at command end | Ground at zero `1.0 s` | Release/settle movement |
|---|---:|---:|---:|
| Forward | `0.8123 m` | `0.9355 m` | `0.1232 m` |
| Reverse | `0.1101 m` | `-0.0129 m` | `0.1230 m` |

The standard Phase 4G probe measures a later settled residual and therefore
reports the smaller `0.028–0.032 m` post-settle drift. These are different
windows, not contradictory measurements. Stop dynamics require further
contact/physics investigation: **BLOCKED**.

## 22. Root cause

Root cause for the directional turn gate is direction-dependent passive
contact resistance from the front caster in the current four-support
configuration. The wheel joints, DiffDrive signs, wheel radius, wheel
separation, odometry integration, mass/inertia, and static caster geometry do
not explain the first divergence.

Root cause for residual stop motion is physical chassis/contact coasting after
zero command while DiffDrive wheel velocity decays. The exact contact force
mechanism remains unresolved because contact telemetry is unavailable: 
**BLOCKED**.

## 23. Production fix if justified

No production physics/contact fix was justified for application in Phase 4K.
The rear-only A/B result is effective but requires disabling the front caster
collision, conflicting with the instruction not to undo the Phase 4J caster
correction. A front-caster high-slip candidate produced CW error about `30.39°`
and forward yaw drift; a zero-friction candidate and a `mu=0.001` candidate
failed to reach the requested simulation-time windows. No artificial odometry
or angular scaling was used: **DEFERRED**.

## 24. Final forward repeats

Fresh production regression with the current model and diagnostic publisher:

| Repeat | Ground | Odom | Error |
|---:|---:|---:|---:|
| 1 | `0.6692 m` | `0.7002 m` | `4.428%` |
| 2 | `0.6632 m` | `0.6932 m` | `4.333%` |
| 3 | `0.6603 m` | `0.6960 m` | `5.131%` |
| Average / worst | — | — | `4.631% / 5.131%` |

Average is within the `5%` threshold; worst case exceeds it: **BLOCKED**.

## 25. Final reverse repeats

| Repeat | Ground | Odom | Error |
|---:|---:|---:|---:|
| 1 | `-0.6704 m` | `-0.7028 m` | `4.607%` |
| 2 | `-0.6181 m` | `-0.6506 m` | `4.988%` |
| 3 | `-0.6231 m` | `-0.6544 m` | `4.776%` |
| Average / worst | — | — | `4.791% / 4.988%` |

Forward/reverse sign is correct, but the requested worst-case margin is not
met robustly: **BLOCKED**.

## 26. Final CCW repeats

| Repeat | Ground yaw | Odom yaw | Error |
|---:|---:|---:|---:|
| 1 | `46.21°` | `64.31°` | `18.097°` |
| 2 | `67.26°` | `67.27°` | `0.000°` |
| 3 | `73.50°` | `65.16°` | `8.343°` |
| Average / worst | — | — | `8.813° / 18.097°` |

Repeatability is not acceptable and the worst case is far outside the `5°`
gate: **BLOCKED**.

## 27. Final CW repeats

| Repeat | Ground yaw | Odom yaw | Error |
|---:|---:|---:|---:|
| 1 | `-60.33°` | `-64.84°` | `4.505°` |
| 2 | `-67.08°` | `-67.08°` | `0.000°` |
| 3 | `-69.33°` | `-65.96°` | `3.373°` |
| Average / worst | — | — | `2.626° / 4.505°` |

CW is within the numerical gate in this run, but directional symmetry with
CCW is not: **BLOCKED**.

## 28. Final stop

The standalone zero-command pose test remained stationary with zero ground
delta and zero reported odometry linear/angular velocity: **PASS**. The
dynamic release test still shows physical settling after a moving command:
**BLOCKED**. The two statements refer to standalone idle stop versus moving
stop dynamics.

## 29. Static stability

The post-Phase-4J static support geometry remains level and stable in the
tested empty model. Production mass is `24.7 kg`; weighted COM is approximately
`(0.002581, 0, 0.297713) m`. Active support points are the two drive wheels and
two caster spheres; anti-tip spheres have approximately `0.050 m` clearance.
Loaded-payload stability was not simulated: **PASS** for empty idle/low-speed
static stability; **DEFERRED** for payload behavior.

## 30. Sensor regression

Fresh runtime checks:

| Interface | Evidence | Result |
|---|---|---|
| `/clock` | ROS type and active bridge publisher | PASS |
| `/cmd_vel` | probe changed physical pose and `/odom` | PASS |
| `/odom` | live messages and 3-repeat probe | PASS |
| `/tf` | live `TFMessage` | PASS |
| `/tf_static` | live `TFMessage` | PASS |
| `/scan` | live `LaserScan` | PASS |
| `/imu` | live `Imu` | PASS |
| `/camera/image_raw` | live rate about `10.27 Hz` in check window | PASS |
| `/camera/camera_info` | live rate about `11.59 Hz` in check window | PASS |

The known SDF warnings for `gz_frame_id` under LiDAR, IMU, and camera sensors
remain; they are outside the motion fix and are **DEFERRED**.

## 31. Resources

Final production container snapshot after the regression:

```text
docker stats --no-stream:
CPU 421.29%
memory 553.1MiB / 15.24GiB (3.54%)
PIDs 108

free -h:
Mem total 15Gi, used 10Gi, free 1.7Gi, available 4.7Gi
Swap total 4.0Gi, used 4.0Gi, free 200Ki
```

Gazebo remained CPU-heavy because the production runtime includes sensors;
resource margin and swap pressure are deployment risks: **BLOCKED**.

## 32. Build validation

| Check | Result |
|---|---|
| Full `rosdep install --from-paths /ros2_ws/src --ignore-src -r -y --rosdistro jazzy` | PASS |
| Full `colcon build --symlink-install` | PASS; 5 packages |
| XML/SDF/URDF/Xacro parse | PASS |
| YAML parse | PASS |
| Python compile and diagnostic tests | PASS; 5 tests |
| `docker compose config` | PASS |
| `git diff --check` | PASS |
| Headless runtime launch | PASS |

## 33. Files changed

Phase 4K added or changed the following in the existing working tree:

- [PHASE_4K_DIRECTIONAL_RESISTANCE_REPORT.md](./PHASE_4K_DIRECTIONAL_RESISTANCE_REPORT.md)
- [scripts/phase4k_diagnostics.py](./scripts/phase4k_diagnostics.py)
- [scripts/test_phase4k_diagnostics.py](./scripts/test_phase4k_diagnostics.py)
- [scripts/phase4k_turn_probe.py](./scripts/phase4k_turn_probe.py)
- [scripts/phase4k_make_candidate.py](./scripts/phase4k_make_candidate.py)
- [ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf](./ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf) — existing Phase 4J caster correction plus Phase 4K diagnostic-only wheel publisher
- [docs/superpowers/plans/2026-09-18-phase-4k-directional-resistance.md](./docs/superpowers/plans/2026-09-18-phase-4k-directional-resistance.md)
- raw diagnostic captures: `phase4k-timestamped.json` and `phase4k-final-production.json`

No production caster/contact parameter was changed during Phase 4K.

## 34. Git diff stat

The cumulative tracked working-tree statistic at completion is:

```text
18 files changed, 282 insertions(+), 312 deletions(-)
```

This is the tracked `git diff --stat` only. The Phase 0–4 reports, current
Harmonic model, diagnostic scripts, raw captures, and this report are existing
uncommitted work or new untracked evidence and are intentionally preserved.

## 35. Remaining risks

- front-caster directional contact force is not instrumented at contact level;
- moving-stop physical coasting is not within a clean, repeatable bound;
- final 3-repeat CCW behavior is non-repeatable and fails worst case;
- production CPU and host swap usage are high under sensor runtime;
- `gz_frame_id` SDF warnings remain for three sensors;
- payload mass, payload contact, loaded stability, and real hardware correlation
  are not tested;
- the rear-only structural support result needs an explicit architecture
  decision before any production model change;
- Nav2, SLAM, AMCL, docking, ArUco, mission, Web UI, and cafe-world redesign
  remain outside this gate.

## 36. Recommendation

Overall Phase 4K recommendation: **BLOCKED**.

The production model must not advance to Phase 5. The next authorized work
should resolve the front-caster contact architecture and moving-stop dynamics,
then repeat the exact three-repeat forward, reverse, CCW, CW, stop, sensor,
build, and resource gates. Phase 5 remains **DEFERRED** and was not started.
