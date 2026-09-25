# Phase 4H Physics Isolation Report

Date: 2026-09-17  
Scope: Cafe Service AMR ROS 2 Jazzy / Gazebo Harmonic only.  
Decision: Gate A **BLOCKED**. Phase 5 was not started.

## 1. Repository confirmation and safety

The repository was confirmed before testing:

- Repository root: `/home/deden/Documents/my-project/ros2-software-amr`
- ROS workspace: `ros2_ws`
- Simulation package: `ros2_ws/src/amr_simulation`
- Production Cafe model: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Authoritative runtime report: `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`
- Previous calibration report: `PHASE_4G_MOTION_CALIBRATION_REPORT.md`
- Branch: `main`
- HEAD at inspection: `3ddde28b668d646fed8f9e39188a9f1153e74a28`

No commit, push, reset, clean, stash, or branch switch was performed. The production
Cafe model was not modified in Phase 4H.

## 2. Objective and acceptance gate

Phase 4H isolates the physical-motion blocker with a disposable differential-drive
model before any Cafe-specific physics is reintroduced. The exact command matrix
was used, with three repeats for T1–T4:

| Test | Command | Duration |
|---|---:|---:|
| T1 forward | `linear.x = +0.20 m/s` | 5 s |
| T2 reverse | `linear.x = -0.20 m/s` | 5 s |
| T3 CCW | `angular.z = +0.40 rad/s` | 4 s |
| T4 CW | `angular.z = -0.40 rad/s` | 4 s |
| T5 stop | zero command and settle observation | 5 s |

Gate A requires translational error <=5%, rotational error <=5 degrees, repeatable
three-repeat behavior, correct forward/reverse direction, sufficiently symmetric
CW/CCW motion, reliable stopping, and no severe contact instability.

## 3. Independent Gazebo ground truth

[`scripts/phase4g_motion_probe.py`](/home/deden/Documents/my-project/ros2-software-amr/scripts/phase4g_motion_probe.py)
was extended with selectable model, command-topic, and odometry-topic arguments.
For Phase 4H it queried:

```text
gz model -m amr_robot_physics_test -p
```

and independently sampled ROS `/odom`. Ground truth was not derived from `/odom`,
the command, or the Gazebo DiffDrive odometry stream. Position error is compared
using XY displacement; yaw error is compared using the wrapped yaw delta.

## 4. Diagnostic setup

The disposable setup contains:

- a 10 kg rigid chassis;
- two 0.09 m drive wheels at `y = +0.21 m` and `y = -0.21 m`;
- wheel cylinders rolled `-pi/2`, giving their native local-Z axis the expected
  lateral wheel axis;
- revolute joints with axis `0 0 1` and no additional joint pose;
- native `gz-sim-diff-drive-system` with separation `0.42 m` and radius `0.09 m`;
- a minimal plane and 1 ms physics step;
- no sensors, trays, casters, anti-tip supports, Nav2, SLAM, docking, or Web UI.

The setup is launched headlessly with:

- [`ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.sdf`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.sdf)
- [`ros2_ws/src/amr_simulation/worlds/amr_physics_test.sdf`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/worlds/amr_physics_test.sdf)
- [`ros2_ws/src/amr_simulation/launch/phase4h_minimal.launch.py`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/launch/phase4h_minimal.launch.py)
- [`ros2_ws/src/amr_simulation/config/bridge_phase4h.yaml`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/config/bridge_phase4h.yaml)

## 5. Initial measurements: diagnostic candidate with rear support

The first minimal candidate included one low-friction rear support ball. It was
removed after the results below showed pitch and failed rotation behavior.

| Test | Average translational error | Worst translational error | Average rotational error | Observation |
|---|---:|---:|---:|---|
| T1 forward | 25.692% | 37.612% | 0.01 deg | one near-nominal repeat, two short repeats |
| T2 reverse | 37.615% | 37.617% | 0.11 deg | consistently short physical travel |
| T3 CCW | 100% metric | 100% metric | 91.86 deg | physical yaw remained 0 deg |
| T4 CW | 100% metric | 100% metric | 91.88 deg | physical yaw remained 0 deg |

After the run, the model pose had approximately `pitch = +0.3026 rad` (17.3 deg).
The physical chassis had tipped while `/odom` continued to report commanded
DiffDrive motion.

## 6. Diagnostic measurements: candidate without passive support

The exact matrix was repeated after removing the support ball. No production file
was changed.

| Test | Repeat 1 | Repeat 2 | Repeat 3 | Average | Worst |
|---|---:|---:|---:|---:|---:|
| T1 translation error | 48.39% | 52.17% | 52.76% | 51.107% | 52.756% |
| T2 translation error | 52.76% | 52.76% | 52.76% | 52.761% | 52.762% |
| T3 rotation error | 37.49 deg | 0.95 deg | 62.79 deg | 33.742 deg | 62.787 deg |
| T4 rotation error | 86.24 deg | 7.61 deg | 7.48 deg | 33.775 deg | 86.240 deg |

The no-support candidate physical displacements were approximately 0.48–0.52 m
for T1/T2 instead of the expected 1.0 m. Physical turning was partial and
non-repeatable: T3 reached 54.28, 91.00, and 28.98 deg; T4 reached -5.57,
-84.16, and -84.31 deg. `/odom` remained close to +/-91.8 deg for the turn
commands.

## 7. Wheel and joint findings

The minimal wheel geometry is internally coherent at the ROS/Gazebo interface:

- wheel centers are symmetric at `y = +/-0.21 m`;
- wheel radius and DiffDrive radius are both `0.09 m`;
- wheel separation and DiffDrive separation are both `0.42 m`;
- wheel link roll is `-pi/2`;
- joint axis is `0 0 1`;
- the joint has no extra pose, so the axis is co-located with the child link frame.

This rules out the previously observed obvious wheel-frame lateral-motion error as
the only explanation. The same coherent wheel semantics still generated chassis
pitch, short translation, and unstable turning in the minimal model.

## 8. Caster findings

There are no casters in the Phase 4H minimal model. Therefore caster lockup or
caster friction cannot explain the diagnostic failure. Cafe caster behavior was
not reintroduced because Gate A failed.

## 9. Anti-tip findings

There are no anti-tip supports in the final Phase 4H minimal candidate. The first
candidate's single rear support was removed; with it present, the model developed
approximately 17.3 deg pitch and pure turns did not produce physical yaw. The
support was therefore identified as a contributing contact risk, but its removal
did not make Gate A pass.

## 10. Friction and slip findings

The drive-wheel contact used ODE `mu = 1.0`, `mu2 = 1.0`, `slip1 = 0.035`, and
`slip2 = 0.0`. No friction value was tuned to force an acceptance result. The
large mismatch persisted with and without the passive support, indicating that a
single support change or odometry scale adjustment is not an adequate fix.

## 11. Mass and inertia findings

The diagnostic chassis uses mass `10.0 kg` and positive diagonal inertia
`ixx = 0.220`, `iyy = 0.255`, `izz = 0.448`; each wheel uses mass `0.5 kg`.
There are no tall Cafe trays or sensor housings in this candidate. Despite this
simple mass distribution, the chassis/wheel contact system pitched and did not
track the native odometry. Therefore the failure is below the Cafe payload stack,
although the production model may amplify it.

## 12. DiffDrive findings

The native Gazebo DiffDrive plugin was used with named joints and the physically
matching separation/radius values. `/cmd_vel` was bridged to
`/model/amr_robot_physics_test/cmd_vel`; `/odom` was bridged from
`/model/amr_robot_physics_test/odometry`. The bridge and plugin topics were live.

The evidence shows that the plugin can publish the expected commanded odometry,
while the physical chassis does not follow it. No fake odometry scaling was added.

## 13. Physics and contact findings

The world used a 1 ms step, real-time factor 1, explicit physics, and solver
configuration. Gazebo exposed pose and odometry topics, but no contact topic was
listed for this world/model, so direct contact-wrench telemetry was **NOT TESTED**
and cannot be claimed.

The observable physical signature is a wheel/contact/chassis constraint problem:
the chassis develops a large pitch, drive distance is about half the odometric
distance without the support, and differential turns become partial or fail while
the odometry continues to rotate. This is the demonstrated Gate A root cause:
the minimal physical wheel-contact dynamics do not reproduce the DiffDrive
kinematics. The exact split between contact solver behavior, wheel loading, and
two-wheel chassis balance remains **NOT TESTED**.

## 14. Root cause determination

The first failing component is the disposable two-wheel physical mechanism itself,
not a Cafe-specific component. Both minimal candidates failed before any Cafe
trays, casters, anti-tip supports, lidar, IMU, camera, or production collision
geometry were reintroduced.

The root cause for the Phase 4H gate is therefore **BLOCKED** at minimal
wheel/contact/chassis dynamics. A more specific production diagnosis would be
unsupported because the minimal candidate does not pass Gate A.

## 15. Reintroduction ladder

The requested ladder was not entered because Gate A failed:

| Candidate | Component | Result |
|---|---|---|
| A | minimal two-wheel chassis | BLOCKED |
| B | caster geometry/contact | NOT TESTED |
| C | anti-tip supports | NOT TESTED |
| D | tall tray/body stack | NOT TESTED |
| E | lidar | NOT TESTED |
| F | IMU | NOT TESTED |
| G | front camera | NOT TESTED |
| H | Cafe production collision/inertia | NOT TESTED |
| I | final production candidate | NOT TESTED |

No “first Cafe component introducing instability” can be named from this run.

## 16. Exact changes made

Phase 4H added only the disposable diagnostic assets and probe configurability:

- added `models/amr_robot_physics_test/model.config`;
- added `models/amr_robot_physics_test/model.sdf`;
- added `worlds/amr_physics_test.sdf`;
- added `config/bridge_phase4h.yaml`;
- added `launch/phase4h_minimal.launch.py`;
- modified `scripts/phase4g_motion_probe.py` to select model and topics.

The rear support was removed from the diagnostic model between the two Gate A
runs. `models/amr_robot_harmonic/model.sdf` was intentionally left unchanged in
Phase 4H.

## 17. Before/after motion table

“Before” is the final Phase 4G Cafe candidate. “After” is the best Phase 4H
minimal result; it is not a production fix.

| Test | Phase 4G Cafe candidate | Phase 4H minimal candidate | Gate |
|---|---|---|---|
| T1 forward | 89.01% average, 145.78% worst | 51.107% average, 52.756% worst | FAIL |
| T2 reverse | 38.80% average, 67.52% worst | 52.761% average, 52.762% worst | FAIL |
| T3 CCW | 90.98 deg average, 168.84 deg worst | 33.742 deg average, 62.787 deg worst | FAIL |
| T4 CW | 0.40 deg angular average, but non-zero translation | 33.775 deg average, 86.240 deg worst | FAIL |
| T5 stop | standalone stop was zero, but in-motion settling was unreliable | zero ground movement and zero odom velocity | FAIL |

The minimal model reduced some error relative to Phase 4G but did not meet the
acceptance gate or establish a trustworthy physics foundation.

## 18. Three-repeat forward results

| Repeat | Ground displacement | Odom displacement | Translation error | Ground yaw error | Stop displacement |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.5179 m | approximately 1.00 m | 48.39% | 0.12 deg | 0.0002 m |
| 2 | 0.4803 m | approximately 1.00 m | 52.17% | 3.86 deg | 0.0002 m |
| 3 | 0.4841 m | approximately 1.00 m | 52.76% | 0 deg | 0.0002 m |

Average translational error: **51.107%**. Worst-case translational error:
**52.756%**. Result: **FAIL**.

## 19. Three-repeat reverse results

| Repeat | Ground displacement | Odom displacement | Translation error | Ground yaw error | Lateral displacement |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.4823 m | approximately 1.00 m | 52.76% | approximately 0 deg | -0.0361 m |
| 2 | 0.4825 m | approximately 1.00 m | 52.76% | approximately 0 deg | -0.0362 m |
| 3 | 0.4830 m | approximately 1.00 m | 52.76% | approximately 0 deg | -0.0361 m |

Average translational error: **52.761%**. Worst-case translational error:
**52.762%**. Result: **FAIL**.

## 20. Three-repeat CW results

| Repeat | Ground yaw | Odom yaw | Rotational error | Ground XY displacement |
|---:|---:|---:|---:|---:|
| 1 | -5.57 deg | approximately -91.8 deg | 86.24 deg | 0.0223 m |
| 2 | -84.16 deg | approximately -91.8 deg | 7.61 deg | 0.1463 m |
| 3 | -84.31 deg | approximately -91.8 deg | 7.48 deg | 0.1273 m |

Average rotational error: **33.775 deg**. Worst-case rotational error:
**86.240 deg**. Result: **FAIL**.

## 21. Three-repeat CCW results

| Repeat | Ground yaw | Odom yaw | Rotational error | Ground XY displacement |
|---:|---:|---:|---:|---:|
| 1 | 54.28 deg | approximately +91.8 deg | 37.49 deg | 0.0397 m |
| 2 | 91.00 deg | approximately +91.9 deg | 0.95 deg | 0.2436 m |
| 3 | 28.98 deg | approximately +91.9 deg | 62.79 deg | 0.0239 m |

Average rotational error: **33.742 deg**. Worst-case rotational error:
**62.787 deg**. Result: **FAIL**.

## 22. Stop behavior and repeatability

T5 produced zero measured ground movement and zero odometry velocity after the
zero command in the final minimal run. This isolated stop observation is **PASS**.
However, the complete motion gate remains **FAIL** because the preceding motion
was not physically correct, and the turning trials were not repeatable.

The decisive repeatability result is that identical commands produced materially
different physical yaw and displacement. T1/T2 were consistently short, while
T3/T4 varied from near nominal to almost no rotation. Overall repeatability is
**FAIL**.

## 23. Sensor and ROS regression

The Phase 4H minimal model intentionally contains no sensors. Fresh Phase 4H
sensor execution was therefore **NOT TESTED**. The previously completed Phase 4
Cafe runtime report recorded live `/scan`, `/imu`, `/camera/image_raw`, and
`/camera/camera_info`, with the documented camera frame chain unchanged. Those
earlier results do not substitute for a fresh Phase 4H production regression.

The final minimal headless topic list contained `/clock`, `/cmd_vel`, `/odom`,
`/parameter_events`, and `/rosout`; `/clock`, `/cmd_vel`, and `/odom` were
operational. `/tf`, `/tf_static`, `/scan`, `/imu`, `/camera/image_raw`, and
`/camera/camera_info` were **NOT TESTED** in this sensor-free isolation run.

## 24. Rosdep, build, runtime, and resource verification

Full rosdep in the Jazzy verification container returned:

```text
#All required rosdeps installed successfully
```

Full colcon build returned:

```text
Summary: 5 packages finished [1.28s]
```

Headless Gazebo launch, bridge startup, model spawn, and the 12 motion trials plus
T5 completed. Resource snapshots during the final running container were:

```text
docker stats --no-stream
CPU: 112.06%
Memory: 173.9MiB / 15.24GiB (1.11%)
PIDs: 51

free -h
Mem:  15Gi total, 9.8Gi used, 1.5Gi free, 5.4Gi available
Swap: 4.0Gi total, 3.8Gi used, 210Mi free
```

`git diff --check` returned no output and no error. Resource usage does not explain
the physical/odometry mismatch. Verification result: **PASS** for rosdep, build,
headless spawn, resource capture, and diff check.

## 25. Files changed and diff summary

Phase 4H files changed or added:

- [`PHASE_4H_PHYSICS_ISOLATION_REPORT.md`](/home/deden/Documents/my-project/ros2-software-amr/PHASE_4H_PHYSICS_ISOLATION_REPORT.md)
- [`ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.config`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.config)
- [`ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.sdf`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.sdf)
- [`ros2_ws/src/amr_simulation/worlds/amr_physics_test.sdf`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/worlds/amr_physics_test.sdf)
- [`ros2_ws/src/amr_simulation/config/bridge_phase4h.yaml`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/config/bridge_phase4h.yaml)
- [`ros2_ws/src/amr_simulation/launch/phase4h_minimal.launch.py`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/launch/phase4h_minimal.launch.py)
- [`scripts/phase4g_motion_probe.py`](/home/deden/Documents/my-project/ros2-software-amr/scripts/phase4g_motion_probe.py)

The cumulative tracked worktree diff remains:

```text
18 files changed, 282 insertions(+), 312 deletions(-)
```

Because the Phase 4H assets and prior reports are untracked in this worktree,
`git diff --stat` does not include their contents. No unrelated project or
protocol was inspected or changed.

## 26. Remaining risks and warnings

- The minimal wheel/contact/chassis dynamics remain unresolved.
- Direct contact telemetry was unavailable from the listed Gazebo topics.
- The production Cafe model may contain additional caster, anti-tip, tall-stack,
  collision, and inertia interactions, but these were deliberately not tested
  after Gate A failed.
- Production `/odom` must not be treated as a physical-pose truth source.
- Fresh sensor regression for the production model is **NOT TESTED** in Phase 4H.
- Nav2, SLAM Toolbox, AMCL, docking, ArUco runtime, mission integration, Web UI
  integration, and Phase 5 remain **DEFERRED**.

## 27. Final recommendation and stop gate

| Gate | Result |
|---|---|
| Independent Gazebo ground truth | PASS |
| Reproducible T1–T5 harness | PASS |
| Minimal Gate A forward | FAIL |
| Minimal Gate A reverse | FAIL |
| Minimal Gate A CW | FAIL |
| Minimal Gate A CCW | FAIL |
| Stop observation | PASS |
| Three-repeat repeatability | FAIL |
| Sensor regression in Phase 4H | NOT TESTED |
| Full rosdep | PASS |
| Full colcon build | PASS |
| Headless runtime and spawn | PASS |
| Phase 4H physics isolation gate | BLOCKED |
| Phase 5 start | DEFERRED |

Recommendation: **BLOCKED**. The next approved action should be a focused
read-only/mechanics investigation of the minimal wheel-contact system, including
joint state/contact instrumentation or a known-good Gazebo differential-drive
reference, before any Cafe physics changes. This report is the stopping point;
Phase 5 was not started.
