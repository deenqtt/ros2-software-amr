# Phase 4G Motion Calibration Report

Date: 2026-09-17
Scope: physical motion and odometry calibration gate for the Cafe Service AMR in Gazebo Harmonic / ROS 2 Jazzy.

## 1. Executive summary

Phase 4G is **BLOCKED**. The final candidate can sometimes produce straight motion and accurate CW rotation, but repeated trials are not stable. The independent Gazebo ground-truth pose and ROS `/odom` diverge well beyond the approved thresholds.

No Nav2, SLAM, AMCL, docking, ArUco, Web UI, mission logic, or cafe-world redesign was started.

## 2. Original blocker

Before Phase 4G, `/odom` was not trustworthy as a physical-pose proxy. Forward/reverse commands produced lateral motion, and commanded rotations did not match the model pose. Therefore Nav2 and localization work was intentionally held back.

## 3. Pre-write Git state

- Branch: `main`
- HEAD: `3ddde28b668d646fed8f9e39188a9f1153e74a28`
- The worktree already contained cumulative Phase 0–4 tracked and untracked changes.
- No commit, push, reset, clean, stash, or branch switch was performed.

## 4. Ground-truth measurement method

The probe samples the robot pose independently through:

```text
gz model -m amr_robot -p
```

ROS odometry is sampled separately from `/odom`. Neither measurement is derived from the other. The probe compares XY displacement and yaw delta after each command.

This follows the Gazebo Harmonic DiffDrive model contract: the plugin uses named wheel joints, wheel separation, wheel radius, and publishes odometry independently of the command interface. See the [official Harmonic moving-robot tutorial](https://github.com/gazebosim/docs/blob/master/harmonic/moving_robot.md) and [official Gazebo DiffDrive example](https://github.com/gazebosim/gz-sim/blob/main/examples/worlds/diff_drive.sdf).

## 5. Test harness

Added [`scripts/phase4g_motion_probe.py`](/home/deden/Documents/my-project/ros2-software-amr/scripts/phase4g_motion_probe.py).

The harness executes:

- T1 forward: `+0.20 m/s` for 5 s
- T2 reverse: `-0.20 m/s` for 5 s
- T3 CCW: `+0.40 rad/s` for 4 s
- T4 CW: `-0.40 rad/s` for 4 s
- T5 stop: zero command and settle observation
- T1–T4 repeated three times

## 6. Initial baseline measurements

The original baseline showed a consistent geometry failure:

| Test | Physical observation | Odometry observation | Result |
|---|---|---|---|
| T1 forward | About 0.10–0.24 m, predominantly lateral | About 0.97–1.00 m forward | FAIL |
| T2 reverse | About 0.23–0.24 m, predominantly lateral | About 0.97–1.00 m reverse | FAIL |
| T3 CCW | About 13–26° physical yaw | About 89–90° odom yaw | FAIL |
| T4 CW | About 14–36° physical yaw | About 90–91° odom yaw | FAIL |

Representative baseline translational errors were approximately 98–104%; rotational errors were approximately 101–126° in the turn trials.

## 7. Wheel contact findings

The four main wheel centers and radius are geometrically intended as:

- left: `y = +0.21 m`
- right: `y = -0.21 m`
- wheel radius: `0.09 m`
- wheel bottom: approximately `z = 0`

The baseline wheel link frame was rotated `+π/2` while its joint axis was not expressed consistently with that frame. This was sufficient to explain the observed lateral motion and unstable constraint behavior.

## 8. Caster findings

The two passive caster visual spheres remain separate from their smaller collision spheres. Their collision friction is intentionally low. They are not sufficient to explain away the large odometry mismatch, but they can affect post-command settling when the tall model tilts.

## 9. Anti-tip findings

Four raised corner support spheres remain present as a stability aid. Their nominal bottom is above the floor, so they should not be primary drive contacts. Their interaction during tilt is a remaining physics risk and was not further tuned in this gate.

## 10. Friction/slip findings

Drive wheels use ODE `mu = 1.0`, `mu2 = 1.0`, and the existing slip values. Lowering or changing friction was not used as a substitute for correcting the joint-frame geometry.

## 11. Mass/inertia findings

The current SDF mass sum is approximately 24.7 kg. The upper trays make the model tall and increase sensitivity to unintended contact and constraint torque. No mass or inertia values were changed during Phase 4G.

## 12. DiffDrive findings

The plugin configuration names the two drive joints, uses `wheel_separation = 0.42 m`, and `wheel_radius = 0.09 m`. The ROS bridge maps `/cmd_vel` to the Gazebo command topic and Gazebo odometry to `/odom`.

## 13. Physics settings findings

The world uses a 1 ms physics step and real-time factor 1.0. An idle model inspection showed non-zero pitch and, in some candidates, spontaneous pose drift. This is evidence of an unresolved physical-contact or joint-constraint issue, not a ROS topic naming issue.

## 14. Changes made

Three isolated hypotheses were tested:

1. Add joint pose and change axis to `0 0 1`: this removed the lateral-only pattern in a short trial but retained severe drift and constraint problems.
2. Remove the added joint pose while retaining axis `0 0 1`: this matches the SDF semantics in which joint pose is specified relative to the child joint frame. The short trial produced straight but sign-reversed motion.
3. Change both wheel link rolls from `+π/2` to `-π/2`: this matches the orientation pattern used by the official Gazebo DiffDrive example and corrected the rolling direction in short trials.

The current model contains only hypotheses 2 and 3. No other Phase 4G production change was made.

## 15. Before/after comparison

The short checks improved the nominal geometry:

| Candidate | Forward/reverse geometry | Rotation | Repeatability |
|---|---|---|---|
| Baseline | Lateral motion | Wrong magnitude/sign | FAIL |
| H1 | Still lateral/unstable | Still wrong | FAIL |
| H2 | Straight, reversed sign | Partially improved | FAIL |
| H3 | Straight and correct sign in short trial | CW close; CCW poor | FAIL |

## 16. Forward tests

Final 3-repeat candidate results:

| Repeat | Ground XY (m) | Odom XY (m) | Translation error | Ground yaw | Odom yaw |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.8279 | 0.8760 | 8.02% | 36.35° | 0.85° |
| 2 | 0.2096 | 0.9462 | 113.24% | 0.84° | -0.00° |
| 3 | 2.1888 | 1.0149 | 145.78% | -34.73° | 0.85° |

Average translational error: 89.01%. Worst: 145.78%. Status: **FAIL**.

## 17. Reverse tests

| Repeat | Ground XY (m) | Odom XY (m) | Translation error | Ground yaw | Odom yaw |
|---:|---:|---:|---:|---:|---:|
| 1 | 3.0154 | 0.9878 | 67.52% | -33.63° | 0.00° |
| 2 | 1.8941 | 0.9952 | 47.57% | -32.57° | 0.00° |
| 3 | 0.9456 | 0.9414 | 1.31% | 0.00° | 0.85° |

Average translational error: 38.80%. Worst: 67.52%. Status: **FAIL**.

## 18. CW rotation tests

| Repeat | Ground yaw | Odom yaw | Rotational error | Ground XY |
---:|---:|---:|---:|---:|
| 1 | -90.79° | -90.34° | 0.45° | 0.0336 m |
| 2 | -90.59° | -91.12° | 0.53° | 0.0257 m |
| 3 | -90.53° | -90.32° | 0.21° | 0.0330 m |

Average rotational error: 0.40°. However, the non-zero physical XY displacement makes the full motion gate fail. Status: **FAIL**.

## 19. CCW rotation tests

| Repeat | Ground yaw | Odom yaw | Rotational error | Ground XY |
---:|---:|---:|---:|---:|
| 1 | 72.88° | 89.61° | 16.73° | 0.0312 m |
| 2 | -77.64° | 91.19° | 168.84° | 0.2392 m |
| 3 | 2.78° | 90.16° | 87.38° | 0.0062 m |

Average rotational error: 90.98°. Worst: 168.84°. Status: **FAIL**.

## 20. Stop behavior

The standalone idle T5 test reported zero ground displacement and effectively zero odometry velocity. During motion trials, however, post-command ground displacement was sometimes large (up to about 2.04 m in the captured candidate output), showing that the robot did not reliably settle after a motion command. Status: **FAIL** for the motion gate.

## 21. Repeatability

The same command and duration produced materially different physical trajectories across repeats. This is the decisive blocker: a calibration cannot be accepted when one trial is near nominal and the next trial changes direction, yaw, or displacement substantially.

## 22. Final translational error

Acceptance threshold: ≤5%. Final candidate result: forward average 89.01%, reverse average 38.80%, with individual failures up to 145.78%. Status: **FAIL**.

## 23. Final rotational error

Acceptance threshold: ≤5°. CW average was 0.40°, but CCW average was 90.98° and individual CCW error reached 168.84°. Status: **FAIL**.

## 24. Sensor regression

Fresh headless launch confirmed the ROS topics remained available:

| Interface | Observed/configured behavior | Status |
|---|---|---|
| `/scan` | Approximately 9.44–9.62 Hz; configured 10 Hz | PASS |
| `/imu` | Approximately 96.83–98.70 Hz; configured 100 Hz | PASS |
| `/camera/image_raw` | Approximately 13.76–14.82 Hz; configured 15 Hz | PASS |
| `/camera/camera_info` | Approximately 14.26–15.09 Hz; configured 15 Hz | PASS |
| `/scan` frame | `base_scan` | PASS |
| `/imu` frame | `imu_link` | PASS |
| Camera frames | `camera_rgb_optical_frame` | PASS |

The camera contract remains `camera_link → camera_rgb_frame → camera_rgb_optical_frame`; no rear camera was added.

## 25. Rosdep, colcon, and resource regression

The fresh headless verification container produced:

```text
#All required rosdeps installed successfully
Summary: 5 packages finished [29.3s]
```

Status for full rosdep: **PASS**. Status for full colcon build: **PASS**.

Fresh `docker stats --no-stream` during the running headless simulation:

```text
CPU: 201.65%
Memory: 819.3MiB / 15.24GiB (5.25%)
PIDs: 88
```

Fresh host `free -h` during the same run:

```text
Mem:  15Gi total, 10Gi used, 932Mi free, 4.6Gi available
Swap: 4.0Gi total, 3.6Gi used, 419Mi free
```

The resource usage does not explain the motion mismatch. Quantitative resource regression status: **PASS**.

## 26. ROS interface contract impact

No ROS-facing command, odometry, sensor, or camera frame names were changed. The failure is below the ROS interface layer, in the Gazebo physical model behavior.

## 27. Files changed

Phase 4G added or changed only:

- [`ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf) — isolated wheel joint/orientation hypotheses.
- [`scripts/phase4g_motion_probe.py`](/home/deden/Documents/my-project/ros2-software-amr/scripts/phase4g_motion_probe.py) — independent ground-truth probe and T5 output.
- [`PHASE_4G_MOTION_CALIBRATION_REPORT.md`](/home/deden/Documents/my-project/ros2-software-amr/PHASE_4G_MOTION_CALIBRATION_REPORT.md) — this report.

## 28. Git diff/stat

The tracked cumulative worktree diff before adding this report remained:

```text
18 files changed, 282 insertions(+), 312 deletions(-)
```

This is cumulative Phase 0–4 work, not a Phase 4G-only diff. `git diff --check`, shell syntax checks, and `docker compose config --quiet` passed. The current branch remains `main`; no commit or push was performed.

## 29. Remaining risks

- Wheel joint geometry is improved but the model still has unstable repeated physical behavior.
- The tall fixed service stack, passive caster constraints, raised stability spheres, and contact solver interactions need a deliberate mechanics review.
- `/odom` must not be treated as a valid physical-pose source until the independent gate passes.
- Nav2, SLAM, AMCL, docking, ArUco, and mission validation remain blocked by this prerequisite.
- Gazebo logs still warn that `gz_frame_id` is not part of the base SDF schema for the lidar, IMU, and camera sensors; the bridge/frame outputs remain operational and this warning is retained for compatibility tracking.

## 30. Validation matrix

| Gate | Status |
|---|---|
| Independent Gazebo ground truth | PASS |
| Reproducible T1–T5 harness | PASS |
| Forward translational error ≤5% | FAIL |
| Reverse translational error ≤5% | FAIL |
| CCW rotational error ≤5° | FAIL |
| CW rotational error ≤5° (angular component) | PASS |
| CW pure-turn translation | FAIL |
| Repeatability across three trials | FAIL |
| Sensor/topic regression | PASS |
| Full rosdep install | PASS |
| Full colcon build | PASS |
| Headless runtime spawn | PASS |
| Resource measurement | PASS |
| Phase 4G calibration gate | BLOCKED |
| Nav2/SLAM/AMCL start | DEFERRED |
| Docking/ArUco runtime | DEFERRED |

## 31. Recommendation for Phase 5

Do not begin Phase 5 navigation or localization. Stop here for approval and a focused physics-model review. The next authorized effort should isolate the remaining contact/joint instability using a minimal known-good differential-drive chassis, then reintroduce the Cafe Service AMR stack components one at a time. No further Phase 4G patch was applied after the failed repeatability gate.
