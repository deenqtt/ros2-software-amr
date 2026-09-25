# PHASE 4O — SLIP1 RESPONSE CURVE & PRODUCTION CALIBRATION DECISION

Date: 2026-09-20
Project: Cafe Service AMR — ROS 2 Jazzy / Gazebo Harmonic
Workspace: `ros2_ws`
Production model: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`

Status vocabulary: `PASS`, `FAIL`, `BLOCKED`, `DEFERRED`, `NOT TESTED`.

## 1. Executive Summary

Phase 4O tested identical drive-wheel `slip1` values `0.000`, `0.010`,
`0.020`, and `0.035` with all other production physics frozen. Each value had
three fresh CCW, CW, forward, and reverse repeats. Independent physical pose
came from `/world/amr_world/dynamic_pose/info`; `/odom` was comparison output.

The response is monotonic and strongly nonlinear: increasing `slip1` worsens
turn, straight, and D2 error. Only `slip1=0.000` passed every numerical gate.
It is the numerical and simulator calibration recommendation, but it was not
applied to production.

**PHASE 4O: PRODUCTION CALIBRATION VALUE RECOMMENDED — NOT YET APPLIED**

Candidate motion gate: `PASS`. Production motion gate: `BLOCKED` pending an
authorized application and fresh production revalidation.

## 2. Repository / Git Safety

- Repository root: `/home/deden/Documents/my-project/ros2-software-amr`
- ROS workspace: `ros2_ws`
- Simulation package: `ros2_ws/src/amr_simulation`
- Current Harmonic model: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Authoritative runtime report: `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`
- Branch: `main`
- HEAD: `3ddde28b668d646fed8f9e39188a9f1153e74a28`

No reset, clean, stash, restore, checkout, switch, commit, or push was run.
The pre-existing tracked diff was `23 files changed, 352 insertions(+), 358
deletions(-)`. Existing user changes were preserved.

Status: `PASS`.

## 3. Phase 4N Proven Baseline

Phase 4N already established the causal contribution of both drive-wheel
`slip1=0.035`. Its fresh baseline was approximately `17.753°` CCW error,
`17.732°` CW error, `10.659%` straight error in both directions, and D2 of
`0.070291 m` forward / `0.072957 m` reverse. The `slip1=0` disposable
candidate corrected those failures while preserving wheel tracking.

Phase 4O therefore measured the response curve rather than repeating the
causal-discovery claim.

Status: `PASS`.

## 4. Calibration Question

The question was whether a tested nonzero `slip1` value could meet all motion
gates and have a stronger physical justification than zero. The required
series was `0.000`, `0.010`, `0.020`, `0.035`, applied identically to both drive
wheels.

Status: `PASS`.

## 5. slip1 Runtime Semantics

Local Jazzy files did not contain useful prose documentation for `slip1`.
Runtime evidence identified Gazebo Sim Server `8.15.0` with the DART physics
plugin. The world uses `max_step_size=0.001`; its physics `type` is ignored by
Gazebo Sim, so this report does not call the runtime Gazebo Classic ODE.

The SDFormat collision specification defines ODE `slip1` as force-dependent
slip in the first friction-pyramid direction, equivalent to inverse viscous
damping, with units `m/s/N`; zero means infinitely viscous in that modeled
direction. `slip2` is the corresponding second direction. See the [SDFormat
collision specification](https://sdformat.org/spec/1.12/collision/).

For this runtime, `slip1=0` is technically legitimate simulator input. It does
not mean a real tire has literally zero physical slip. `0.035` is a simulator
compliance parameter, not a measured tire coefficient. No real-robot
calibration evidence is available.

Status: `PASS` for documented semantics; `NOT TESTED` for real-robot transfer.

## 6. Production Physics Freeze

Production SHA before and after:

```text
56c347599eb0f078aa4b0107578655fe98681d034e0a88e945269cbfc92b89fb
```

Both production drive wheels remained `mu=1.0`, `mu2=1.0`, `slip1=0.035`,
`slip2=0.0`. No production SDF edit was made.

Status: `PASS`.

## 7. Candidate Generator

Added `scripts/phase4o_make_slip_candidates.py`, which reuses the Phase 4N
generator, starts from the production SDF, writes the four candidate copies,
and emits manifests containing source SHA, candidate SHA, and the two exact
wheel-field changes. Added unit coverage in
`scripts/test_phase4o_make_slip_candidates.py`.

Status: `PASS` — `5 passed` for the Phase 4N/4O generator tests.

## 8. Structural Diff Validation

Every candidate was structurally checked before runtime. The only relevant
changes were:

```text
wheel_left_link  slip1  0.035 -> candidate
wheel_right_link slip1  0.035 -> candidate
```

`mu`, `mu2`, `slip2`, geometry, contact, caster, anti-tip, mass, inertia,
DiffDrive, sensors, topics, frames, and world settings were unchanged.
The `0.035` candidate is byte-identical to production.

Status: `PASS`.

## 9. Experimental Matrix

| slip1 | CCW | CW | forward | reverse | matrix status |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0.000 | 3 | 3 | 3 | 3 | `PASS` |
| 0.010 | 3 | 3 | 3 | 3 | `PASS` |
| 0.020 | 3 | 3 | 3 | 3 | `PASS` |
| 0.035 | 3 | 3 | 3 | 3 | `PASS` |

All final repeats used fresh isolated Docker simulations. One invalid
`slip1=0.000` forward trace had non-monotonic event markers (`T4<T3`); it was
excluded and replaced by a valid fresh rerun. It was not silently counted.

Status: `PASS`.

## 10. Ground-Truth Method

The probe sampled independent Gazebo dynamic pose from
`/world/amr_world/dynamic_pose/info`, wheel joint state, `/odom`, and command
phases T0–T5. Ground-pose freshness was recorded; valid matrix samples had
maximum observed pose age approximately `0.107 s`. `/odom` was never used as
ground truth.

Commands and windows remained fixed: CCW/CW `angular.z=+/-0.40 rad/s`,
forward/reverse `linear.x=+/-0.20 m/s`, with the Phase 4M/4N T0–T5 and D1–D3
definitions.

Status: `PASS`.

## 11. slip1=0.000 Results

- CCW: mean `0.183°`, worst `0.298°`; yaw ratio `1.0017`.
- CW: mean `0.092°`, worst `0.137°`; yaw ratio `1.0008`.
- Forward: mean translation error `0.195%`, worst `0.376%`.
- Reverse: mean `0.347%`, worst `0.521%`.
- D1/D2/D3: forward `0.042268/0.0000225/0.0000090 m`; reverse
  `0.040734/0.0000198/0.0000123 m`.

All numerical gates passed.

Status: `PASS`.

## 12. slip1=0.010 Results

- CCW: mean `9.448°`, worst `9.654°`; yaw ratio `0.9139`.
- CW: mean `9.459°`, worst `9.700°`; yaw ratio `0.9140`.
- Forward/reverse worst translation error: `3.118%` / `3.524%`.
- D2 forward/reverse: `0.010306 m` / `0.010641 m`.

Straight passed, but turn and D2 failed.

Status: `FAIL` for the complete candidate gate.

## 13. slip1=0.020 Results

- CCW: mean `13.846°`, worst `13.997°`; yaw ratio `0.8741`.
- CW: mean `13.885°`, worst `14.160°`; yaw ratio `0.8734`.
- Forward/reverse worst translation error: `6.148%` / `6.444%`.
- D2 forward/reverse: `0.033635 m` / `0.033892 m`.

Turn, straight, and D2 failed.

Status: `FAIL`.

## 14. slip1=0.035 Results

- CCW: mean `18.021°`, worst `18.258°`; yaw ratio `0.8358`.
- CW: mean `17.946°`, worst `18.144°`; yaw ratio `0.8364`.
- Forward/reverse worst translation error: `11.373%` / `11.211%`.
- D2 forward/reverse: `0.073156 m` / `0.073243 m`.

Turn, straight, and D2 failed. This reproduces the production failure curve.

Status: `FAIL`.

## 15. Optional Intermediate Results

No intermediate values were run. The required four-point series already
showed a clear boundary: zero passed, while the smallest tested nonzero value
failed turn and D2. Additional sweep was not justified.

Status: `DEFERRED`.

## 16. Turn Response Curve

| slip1 | CCW mean | CCW worst | CW mean | CW worst |
| ---: | ---: | ---: | ---: | ---: |
| 0.000 | 0.183° | 0.298° | 0.092° | 0.137° |
| 0.010 | 9.448° | 9.654° | 9.459° | 9.700° |
| 0.020 | 13.846° | 13.997° | 13.885° | 14.160° |
| 0.035 | 18.021° | 18.258° | 17.946° | 18.144° |

Status: `PASS` for response characterization.

## 17. Straight Response Curve

| slip1 | forward mean/worst | reverse mean/worst |
| ---: | ---: | ---: |
| 0.000 | 0.195% / 0.376% | 0.347% / 0.521% |
| 0.010 | 2.920% / 3.118% | 3.257% / 3.524% |
| 0.020 | 6.014% / 6.148% | 6.226% / 6.444% |
| 0.035 | 11.280% / 11.373% | 10.998% / 11.211% |

Status: `PASS` for response characterization.

## 18. D1 Response

| slip1 | forward D1 | reverse D1 |
| ---: | ---: | ---: |
| 0.000 | 0.042268 m | 0.040734 m |
| 0.010 | 0.061152 m | 0.059460 m |
| 0.020 | 0.067428 m | 0.067474 m |
| 0.035 | 0.073728 m | 0.073406 m |

D1 increases monotonically with `slip1` in this series.

Status: `PASS`.

## 19. D2 Response

| slip1 | forward D2 | reverse D2 |
| ---: | ---: | ---: |
| 0.000 | 0.0000225 m | 0.0000198 m |
| 0.010 | 0.010306 m | 0.010641 m |
| 0.020 | 0.033635 m | 0.033892 m |
| 0.035 | 0.073156 m | 0.073243 m |

The `0.010` value misses the `0.010 m` target slightly in both directions.

Status: `PASS` for measurement characterization.

## 20. D3 Response

| slip1 | forward D3 | reverse D3 |
| ---: | ---: | ---: |
| 0.000 | 0.0000090 m | 0.0000123 m |
| 0.010 | 0.001261 m | 0.000955 m |
| 0.020 | 0.002075 m | 0.002438 m |
| 0.035 | 0.003518 m | 0.003420 m |

Status: `PASS`.

## 21. Wheel Tracking

The active-command wheel tracking gate passed at every value after excluding
acceleration and zero-command transition samples from the steady-state
comparison. This corrected an earlier diagnostic false failure caused by
including T1/T2 transition samples. Maximum reported velocity/position errors
were respectively:

| slip1 | velocity | position |
| ---: | ---: | ---: |
| 0.000 | `1.44e-9 rad/s` | `1.35e-9 rad` |
| 0.010 | `1.59e-7 rad/s` | `0.00222 rad` |
| 0.020 | `1.93e-7 rad/s` | `0.00187 rad` |
| 0.035 | `4.45e-10 rad/s` | `0.00667 rad` |

Wheel signs and left/right kinematic symmetry remained valid.

Status: `PASS`.

## 22. CCW/CW Symmetry

Maximum physical mirror yaw error was `0.367°`, `0.733°`, `0.779°`, and
`0.414°` for `0.000`, `0.010`, `0.020`, and `0.035`. No severe directional
asymmetry appeared.

Status: `PASS`.

## 23. Straight Stability

All candidates remained stable. Worst lateral drift was below `2.5e-9 m` in
the straight matrix, and yaw drift remained negligible. No pitch/roll
instability, caster lockup, or anti-tip drag was observed in the motion traces.

Status: `PASS`.

## 24. Contact Telemetry

Disposable contact clones were generated for `0.000`, `0.010`, and `0.035`.
They added eight contact sensors only; manifests record no physics or
controller changes. The primary wheel/caster contact topics were ready in all
three runs; anti-tip contact topics remained inactive.

Representative active contact data:

| value | wheel L/R max normal force | caster F/R max normal force | anti-tip |
| ---: | ---: | ---: | --- |
| 0.000 | 70.002 / 63.718 N | 50.500 / 47.874 N | inactive |
| 0.010 | 70.020 / 63.856 N | 50.189 / 47.859 N | inactive |
| 0.035 | 70.014 / 63.939 N | 50.198 / 47.874 N | inactive |

Contact depth was approximately `1.9–2.6e-9 m`, and all primary contacts were
active throughout the sampled run. Contact-clone versus no-contact CCW yaw
differences were below `0.4°` in the representative comparisons. No reliable
tangential force or tangential slip velocity was available; normal force was
not used as its substitute.

Status: `PASS` for contact instrumentation neutrality and normal-contact
capture; `NOT TESTED` for direct tangential slip telemetry.

## 25. History-Dependence Check

The main matrix was not contaminated by sequential runs. A narrow representative
check at `slip1=0.010` ran forward first and then CW in the same simulation.
The sequential CW error was `8.875°`, compared with fresh-start CW errors
`9.219°`, `9.458°`, and `9.700°`. The result is non-identical but does not
show a severe history-induced change relative to fresh repeat spread.

The sequential forward run had `D2=0.010231 m` and `4.268%` translation error;
it was diagnostic only and not part of the response curve.

Status: `PASS` for the narrow check; fresh starts remain mandatory for final
calibration results.

## 26. Acceptance-Gate Matrix

| slip1 | Turn gate | Straight gate | D2 gate | Symmetry | Wheel tracking | Stability | Overall |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 0.000 | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 0.010 | FAIL | PASS | FAIL | PASS | PASS | PASS | FAIL |
| 0.020 | FAIL | FAIL | FAIL | PASS | PASS | PASS | FAIL |
| 0.035 | FAIL | FAIL | FAIL | PASS | PASS | PASS | FAIL |

Overall is `PASS` only when every required gate passes.

## 27. Numerical Best Candidate

`slip1=0.000` is the only candidate passing all numerical gates. It has the
lowest turn, straight, D1, D2, and D3 errors, with good repeatability and no
observed stability penalty.

Status: `PASS`.

## 28. Physical-Justification Analysis

Zero is legitimate under the documented simulator semantics: it removes
force-dependent velocity compliance in the first modeled friction direction.
It is not a measured claim that the real robot has zero tire slip. The tested
nonzero values have no observed numerical benefit and no real-robot evidence
supports selecting one of them.

Therefore the recommendation is simulator calibration only. Transfer to a
physical AMR remains unproven.

Status: `PASS` for simulator justification; `NOT TESTED` for real-robot
physical validation.

## 29. Production Calibration Recommendation

Recommendation category: **A — RECOMMEND ZERO**.

Recommended value: `slip1=0.000` on both drive wheels, as a proposed
production-calibration value only. It is recommended because it is the only
tested value that passes turn, straight, D2, symmetry, wheel-tracking, and
stability gates. No tested nonzero value passes all gates, and no real-robot
measurement requires nonzero compliance.

No production file was edited.

Status: `PASS` for recommendation; production application is `DEFERRED`.

## 30. What Is Proven

- The response to `slip1` is repeatable across fresh isolated simulations.
- Increasing `slip1` worsens physical-vs-odometry turn and straight agreement.
- The response includes a strong post-stop D2 increase.
- `slip1=0.000` passes the defined simulator motion gates.
- Wheel tracking, directional symmetry, and stability remained valid.
- Contact instrumentation did not materially alter representative motion.

Status: `PASS`.

## 31. What Is Not Proven

- `slip1=0.000` is not proven to be the real robot's tire parameter.
- No real-robot calibration evidence is available.
- Tangential force/slip velocity was not directly measured.
- Production behavior after applying the value was not tested.
- The full low-level DART/contact response mechanism is not isolated beyond
  the controlled `slip1` response.

Status: `NOT TESTED`.

## 32. Production Changes

Production SDF: unchanged. No production physics, controller, topics, TF,
sensors, world, or Docker runtime settings were modified for Phase 4O.

Phase 4O artifacts added/generated:

- `scripts/phase4o_make_slip_candidates.py`
- `scripts/test_phase4o_make_slip_candidates.py`
- `scripts/phase4o_metrics.py`
- `scripts/test_phase4o_metrics.py`
- `docs/evidence/phase4o/`
- this report

The current `git diff --stat` remains the pre-existing tracked diff:

```text
23 files changed, 352 insertions(+), 358 deletions(-)
```

Status: `PASS`.

## 33. Sensor Regression

Unchanged production runtime exposed the required contracts:

```text
/clock                 rosgraph_msgs/msg/Clock
/cmd_vel               geometry_msgs/msg/Twist
/odom                  nav_msgs/msg/Odometry
/tf                    tf2_msgs/msg/TFMessage
/tf_static             tf2_msgs/msg/TFMessage
/scan                  sensor_msgs/msg/LaserScan
/imu                   sensor_msgs/msg/Imu
/camera/image_raw      sensor_msgs/msg/Image
/camera/camera_info    sensor_msgs/msg/CameraInfo
```

`/scan`, `/imu`, and `/camera/image_raw` produced payloads. The image was
`640×480` with frame `camera_rgb_optical_frame`. The camera TF chain remained
`camera_link → camera_rgb_frame → camera_rgb_optical_frame`.

The camera-info topic had a publisher and correct type but did not yield a
payload to `echo --once` in the server-only headless runtime. This is the
known Phase 4 headless rendering limitation, not a new Phase 4O physics
failure. Existing `gz_frame_id` warnings remain deferred.

Topic contract: `PASS`. Full camera payload regression: `BLOCKED`.

## 34. Build Validation

- Phase 4O + prior diagnostic tests: `28 passed` — `PASS`.
- Python compilation: `PASS`.
- SDF/XML validation: 6 files — `PASS`.
- YAML validation: 8 files — `PASS`.
- `docker compose config -q`: `PASS`.
- `git diff --check`: `PASS`.
- `rosdep update`: `PASS`.
- `rosdep install --from-paths src --ignore-src -r -y`: `PASS`.
- full disposable `colcon build --symlink-install`: 5 packages — `PASS`.

## 35. Resource Snapshot

Representative Phase 4O history runtime snapshot:

```text
Docker CPU: 208.13%
Docker RAM: 468.2 MiB / 15.24 GiB
Docker PIDs: 75
Host memory available at final check: 6.3 GiB
Host swap available at final check: 1.6 GiB
```

All disposable Phase 4O containers were removed. No unrelated container or
service was modified.

Status: `PASS`.

## 36. Remaining Risks

- Applying zero to production could expose differences between disposable and
  production launch environments; Phase 4P must revalidate it.
- Gazebo Sim/DART contact behavior is simulator-specific.
- Camera-info payload remains blocked in server-only headless rendering.
- Existing `gz_frame_id` warnings remain deferred.
- No real-robot wheel/tire calibration data exists.
- Sequential history produced small non-identical variation; final results
  correctly use fresh starts.

Status: `DEFERRED` for the listed follow-up risks.

## 37. Phase 4 Motion-Gate Decision

Candidate `slip1=0.000` motion gate: `PASS`.
Production motion gate: `BLOCKED`, because the recommended value was not
applied and production revalidation is not authorized in Phase 4O.

Final decision:

```text
PHASE 4O: PRODUCTION CALIBRATION VALUE RECOMMENDED — NOT YET APPLIED
```

## 38. Recommended Next Phase

Recommend **Phase 4P — Apply Selected slip1 Calibration + Full Production
Motion Revalidation**. It may apply exactly the approved two-wheel value,
repeat the complete fresh motion matrix, and rerun sensor/build/resource
regression. Do not start Phase 4P automatically.

Phase 5, Nav2, SLAM Toolbox, AMCL, docking, ArUco runtime, mission runtime,
and Web UI integration were not started.

Status: `DEFERRED`.

## Required Final Answers

1. **Production SDF changed?** `PASS` — no.
2. **Phase 5 started?** `PASS` — no.
3. **Production SHA before/after?** Identical: `56c347599eb0f078aa4b0107578655fe98681d034e0a88e945269cbfc92b89fb`.
4. **Exact tested slip values?** `0.000`, `0.010`, `0.020`, `0.035`.
5. **Repeat count per value?** 3 CCW, 3 CW, 3 forward, 3 reverse.
6. **Were all candidates one-variable-only?** `PASS` — only both drive-wheel `slip1` fields changed.
7. **`slip1=0` CCW mean/worst?** `0.183° / 0.298°`.
8. **`slip1=0` CW mean/worst?** `0.092° / 0.137°`.
9. **`slip1=.01` CCW mean/worst?** `9.448° / 9.654°`.
10. **`slip1=.01` CW mean/worst?** `9.459° / 9.700°`.
11. **`slip1=.02` CCW mean/worst?** `13.846° / 13.997°`.
12. **`slip1=.02` CW mean/worst?** `13.885° / 14.160°`.
13. **`slip1=.035` CCW mean/worst?** `18.021° / 18.258°`.
14. **`slip1=.035` CW mean/worst?** `17.946° / 18.144°`.
15. **Straight mean/worst error for every value?** `0.000: F 0.195/0.376%, R 0.347/0.521%; 0.010: F 2.920/3.118%, R 3.257/3.524%; 0.020: F 6.014/6.148%, R 6.226/6.444%; 0.035: F 11.280/11.373%, R 10.998/11.211%`.
16. **Forward D2 for every value?** `0.0000225, 0.010306, 0.033635, 0.073156 m` for `0.000, .010, .020, .035`.
17. **Reverse D2 for every value?** `0.0000198, 0.010641, 0.033892, 0.073243 m` for `0.000, .010, .020, .035`.
18. **Physical/odom yaw ratio for every value?** CCW/CW: `0: 1.0017/1.0008; .01: .9139/.9140; .02: .8741/.8734; .035: .8358/.8364`.
19. **Was response monotonic?** `PASS` — error increased with `slip1`.
20. **Approximately linear or nonlinear?** Strongly nonlinear/threshold-like near zero; four points do not justify a fitted curve.
21. **Did wheel tracking remain valid?** `PASS` — all values.
22. **Did any candidate introduce instability?** `PASS` — none observed.
23. **Did any anti-tip contact occur?** `PASS` — no; anti-tip topics remained inactive.
24. **Was direct contact telemetry obtained?** `PASS` for normal contact/depth; `NOT TESTED` for tangential force/slip velocity.
25. **Was history dependence reproduced?** `PASS` — small non-identical sequential variation remained; it did not contaminate the fresh matrix.
26. **Which values pass turn gate?** `0.000` only.
27. **Which values pass straight gate?** `0.000` and `0.010`.
28. **Which values pass D2 gate?** `0.000` only.
29. **Which values pass ALL numerical gates?** `0.000` only.
30. **What is the numerical best candidate?** `slip1=0.000` on both drive wheels.
31. **What does `slip1=0` mean in this simulator?** Zero force-dependent slip/compliance in the first friction-pyramid direction, equivalent to infinitely viscous damping under the SDFormat definition.
32. **Is zero technically legitimate?** `PASS` — yes for this simulator configuration.
33. **Is there real-robot evidence requiring nonzero slip?** `NOT TESTED` — no real-robot calibration evidence is available.
34. **What is the recommended production value?** `0.000` on both drive wheels, recommendation only.
35. **Why over alternatives?** It is the only tested value passing every motion gate; all nonzero tested values fail at least turn or D2.
36. **Confidence level?** High for this simulator response curve; low for real-robot transfer.
37. **What remains unproven?** Real-robot validity, tangential contact mechanism, and post-application production behavior.
38. **Sensor regression result?** Topic contract `PASS`; full camera payload regression `BLOCKED` by headless camera-info availability.
39. **Build validation result?** `PASS` — tests, compile, SDF/XML, YAML, compose, diff check, rosdep, and 5-package colcon build.
40. **Resource snapshot?** 208.13% Docker CPU, 468.2 MiB RAM, 75 PIDs; host 6.3 GiB memory and 1.6 GiB swap available.
41. **Final Phase 4O decision?** `PHASE 4O: PRODUCTION CALIBRATION VALUE RECOMMENDED — NOT YET APPLIED`.
42. **Recommended next phase?** `DEFERRED`: Phase 4P — Apply Selected slip1 Calibration + Full Production Motion Revalidation.

STOP CONDITION: Phase 4O complete. No production change, Phase 4P, or Phase 5 was started.
