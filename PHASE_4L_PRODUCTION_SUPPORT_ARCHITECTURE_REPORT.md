# PHASE 4L — Production Support Architecture Report

Date: 2026-09-18
Project: Cafe Service AMR, ROS 2 Jazzy, Gazebo Harmonic
Branch: `main`
Decision scope: support architecture and stop-dynamics evidence only

## 1. Executive summary

Status: BLOCKED

Phase 4L validated the current four-point support, a rear-three-point candidate, and a front-three-point candidate using disposable SDFs and independent Gazebo dynamic-pose ground truth. No candidate satisfied every support, static-stability, directional-motion, and repeatability gate. Production was therefore not changed.

The current four-point model remains the safest geometric architecture, but its measured CCW result is still outside the rotation gate. The rear-three-point candidate improved static drive behavior but placed the recomputed COM outside its support polygon, introduced approximately 9.72 degrees static pitch, exceeded the reverse translational gate, and retained a large CCW error. The front-three-point candidate had a marginal rear support margin and large lateral drift.

The correct Phase 4L outcome is BLOCKED. Phase 5 was not started.

## 2. Repository/Git safety

Status: PASS

Repository root: `/home/deden/Documents/my-project/ros2-software-amr`

ROS workspace: `ros2_ws`

Simulation package: `ros2_ws/src/amr_simulation`

Production model: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`

Authoritative runtime report: `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`

Branch was `main`; HEAD was `3ddde28b668d646fed8f9e39188a9f1153e74a28` at audit time. No reset, clean, stash, commit, push, or branch switch was performed. Existing user worktree changes were preserved.

The production SDF SHA-256 was `56c347599eb0f078aa4b0107578655fe98681d034e0a88e945269cbfc92b89fb` before and after the Phase 4L candidate audit.

## 3. Phase 4K established evidence

Status: PASS

Phase 4K established that the unchanged four-point production model was dynamically repeatable enough for continued investigation, but not fully accepted by the physical-motion gate. Its three-repeat baseline was:

| Motion | Errors | Average | Worst |
|---|---:|---:|---:|
| Forward | 4.428%, 4.333%, 5.131% | 4.631% | 5.131% |
| Reverse | 4.607%, 4.988%, 4.776% | 4.790% | 4.988% |
| CCW | 18.097°, 0°, 8.343° | 8.813° | 18.097° |
| CW | 4.505°, 0°, 3.373° | 2.626° | 4.505° |

Phase 4K also established that the direction asymmetry was not adequately explained by a simple static wheel-radius or wheel-separation correction. The Phase 4L work therefore focused on support-role architecture and stop dynamics without changing the frozen kinematic contract.

## 4. Current production support architecture

Status: PASS

Production has two driven wheels, a front caster, a rear caster, and four anti-tip spheres. The Phase 4J caster correction is preserved: both caster collision radii are `0.055 m`.

Drive support points are `(0,+0.21 m)` and `(0,-0.21 m)`. The front caster support point is `(+0.24 m,0)` and the rear caster support point is `(-0.24 m,0)`. Anti-tip spheres are at `(±0.24 m,±0.24 m)`, center `z=0.09 m`, radius `0.04 m`, leaving `0.05 m` clearance.

The production model retains its visual front and rear caster links. A diagnostic-only joint-state publisher for the wheel joints is present; it does not replace the production drive controller.

## 5. Recomputed mass/COM

Status: PASS

The SDF mass and inertial data were recomputed from the production model:

| Quantity | Value |
|---|---:|
| Total mass | 24.700000 kg |
| COM x | 0.002581 m |
| COM y | 0.000000 m |
| COM z | 0.297713 m |

The small positive COM x offset is material when comparing the candidate three-point polygons. It is not safe to infer support validity from a symmetric sketch alone.

## 6. Candidate A support polygon

Status: PASS

Candidate A is the unchanged production four-point support architecture. Its convex hull is `(-0.24,0)`, `(0,-0.21)`, `(0.24,0)`, `(0,0.21)`, with area `0.1008 m²`.

The recomputed COM is inside the polygon. Minimum signed boundary distance is `0.156342 m`; the front axial margin is `0.237419 m` and the rear axial margin is `0.242581 m`.

## 7. Candidate B support polygon

Status: BLOCKED

Candidate B raises the front caster collision clear of the ground while preserving its visual/link structure, leaving the rear caster and drive wheels as the primary three-point support.

Its convex hull is `(-0.24,0)`, `(0,-0.21)`, `(0,0.21)`, with area `0.0504 m²`. The recomputed COM is outside this polygon by `0.002581 m` at the front drive-wheel edge. The front axial margin is `-0.002581 m`; the rear margin is `0.242581 m`.

This is a geometric rejection independent of the dynamic trial results.

## 8. Candidate C support polygon

Status: BLOCKED

Candidate C raises the rear caster collision clear of the ground while preserving its visual/link structure, leaving the front caster and drive wheels as the primary three-point support.

Its convex hull is `(0,-0.21)`, `(0.24,0)`, `(0,0.21)`, with area `0.0504 m²`. The COM is technically inside, but the minimum boundary distance and rear axial margin are only `0.002581 m`. The front axial margin is `0.237419 m`.

The near-zero rear margin makes this architecture sensitive to modeling, contact, and payload changes.

## 9. COM margin comparison

Status: PASS

| Candidate | Area m² | COM inside | Minimum boundary margin | Front margin | Rear margin |
|---|---:|---|---:|---:|---:|
| A: four point | 0.1008 | yes | 0.156342 m | 0.237419 m | 0.242581 m |
| B: rear three point | 0.0504 | no | -0.002581 m | -0.002581 m | 0.242581 m |
| C: front three point | 0.0504 | yes | 0.002581 m | 0.237419 m | 0.002581 m |

The support-polygon result rules out selecting Candidate B as production architecture. Candidate C is formally inside but has no useful robustness margin. Candidate A has the only substantial static geometric margin.

## 10. Static perturbation results

Status: BLOCKED

Candidate A settled level, with roll and pitch near zero. Candidate B settled with repeatable static pitch of approximately `9.7156°`, which is incompatible with treating it as a neutral support architecture. Candidate C started with a yaw offset of approximately `-19.28°` and a nonzero initial pose offset; its static body attitude was near level, but the initial pose instability complicated dynamic comparison.

No usable Gazebo contact-wrench telemetry was obtained. Contact-specific claims are therefore NOT TESTED rather than inferred from pose alone.

## 11. Four-point results

Status: BLOCKED

Fresh Candidate A4 runtime evidence used the persistent `/world/amr_world/dynamic_pose/info` JSON stream as independent ground truth. Ground-pose age was approximately `0.001–0.018 s` for valid samples.

| Motion | Ground truth | Odometry | Result |
|---|---:|---:|---|
| Forward settled distance | 0.9485 m | 0.9742 m | 2.634% |
| Reverse settled distance | 0.9489 m | 0.9998 m | 5.090% |
| CCW settled yaw | 73.599° | 91.696° | 18.097° |
| CW settled yaw | -92.113° | -91.673° | 0.440° |

The forward result was within the preferred 3% target in this run, but reverse exceeded the 5% acceptance threshold and CCW exceeded the 5° rotation threshold.

## 12. Rear-three-point results

Status: BLOCKED

Candidate B was run as a disposable rear-only support variant. It produced near-zero straight-motion lateral displacement and repeatable CW behavior, but the static pitch and support-polygon failure make it unsuitable for production.

| Repeat | Forward error | Reverse error | CCW error | CW error |
|---|---:|---:|---:|---:|
| B4 | 2.860% | 5.428% | 16.837° | 0.444° |
| B5 | 2.794% | 5.369% | 16.837° | 0.444° |
| B6 | 2.804% | 5.417% | 16.837° | 0.444° |
| Average | 2.819% | 5.405% | 16.837° | 0.444° |
| Worst | 2.860% | 5.428% | 16.837° | 0.444° |

## 13. Front-three-point results

Status: BLOCKED

Candidate C2 had a forward settled error of `2.291%`, reverse settled error of `4.526%`, CCW error of `0.553°`, and CW error of `0.427°`. Those scalar errors are not sufficient for acceptance because the run accumulated approximately `0.321 m` of lateral displacement during forward motion and began with approximately `-19.28°` static yaw offset.

The candidate therefore demonstrated a potentially interesting turn response but failed the full behavior gate and has only `0.002581 m` rear COM margin.

## 14. Three-repeat rear-only validation

Status: BLOCKED

Three independent fresh Candidate B runs were valid under the live JSON ground-truth method. Ground-pose age was approximately `0.014–0.019 s`. The same static pitch and the same CCW error pattern were observed in all three repeats.

The repeatability is evidence that the result is a stable property of this candidate, not random measurement noise. It is not evidence that the candidate is acceptable: support geometry, reverse error, and CCW error all remain blocking findings.

## 15. Architecture comparison table

Status: BLOCKED

| Gate | A: four point | B: rear three point | C: front three point |
|---|---|---|---|
| COM inside | PASS | FAIL | PASS |
| Static attitude | PASS | FAIL | BLOCKED |
| Forward motion | PASS in fresh run | PASS | PASS with lateral drift |
| Reverse motion | FAIL | FAIL | PASS scalar / BLOCKED behavior |
| CCW rotation | FAIL | FAIL | PASS scalar / BLOCKED setup |
| CW rotation | PASS | PASS | PASS |
| Repeatability | BLOCKED overall | BLOCKED overall | NOT TESTED |
| Production recommendation | BLOCKED | BLOCKED | BLOCKED |

No candidate passes all gates. The production architecture remains unchanged pending a later, separately authorized motion/contact investigation.

## 16. Front caster role decision

Status: DEFERRED

The front caster remains a primary contact in production and a secondary anti-tip/emergency support candidate in the rear-only diagnostic concept. Candidate B showed that simply raising the front collision does not create an acceptable architecture: the COM leaves the support polygon and the chassis pitches.

The front caster must not be removed or raised in production on the current evidence. A future change would require a payload-aware support analysis and contact validation.

## 17. Anti-tip clearance analysis

Status: PASS

The four anti-tip spheres remain at `z=0.09 m` with radius `0.04 m`, providing `0.05 m` ground clearance in the nominal geometry. They are not primary support points in the support-polygon calculation.

No evidence showed improper anti-tip drag in the accepted four-point static geometry. Direct contact telemetry was unavailable, so the absence of drag under every perturbation is NOT TESTED.

## 18. DiffDrive acceleration configuration

Status: PASS

The production DiffDrive configuration remains frozen: linear velocity limits are approximately `-0.6` to `+0.6 m/s`, angular limits approximately `-1.2` to `+1.2 rad/s`, and linear acceleration limits are `+0.5` and `-0.5 m/s²`. Wheel radius remains `0.09 m`; wheel separation remains `0.42 m`.

No odometry scaling, wheel-radius edit, separation edit, or controller hack was introduced during Phase 4L.

## 19. Theoretical braking calculation

Status: PASS

For a commanded body speed of `0.20 m/s` and configured deceleration magnitude `0.5 m/s²`, ideal braking time is:

`t = v/a = 0.20/0.50 = 0.40 s`

Ideal commanded braking distance is:

`d = v²/(2a) = 0.20²/(2×0.50) = 0.040 m`

With a `0.09 m` wheel radius, the corresponding wheel angular speed is approximately `2.2222 rad/s`, angular deceleration is approximately `5.5556 rad/s²`, and ideal wheel angular displacement during braking is approximately `0.4444 rad`.

## 20. Command-to-wheel-stop timing

Status: PASS

Candidate B7 used the explicit wheel near-zero threshold `abs(velocity) < 0.02 rad/s` and added `zero_2.00s` observations. In both directions, wheel velocity reached the threshold by the `zero_0.50s` sample, approximately `0.50 s` after the first zero-command sample.

The exact instant at which wheel deceleration began was not isolated at sub-sample resolution and is NOT TESTED. The measured timing is consistent with the configured acceleration limit plus sampling/command-window latency, but is not a substitute for a continuous event trace.

## 21. Commanded braking distance

Status: PASS

Candidate B7 physical ground-truth movement from the first zero-command sample to the first near-zero-wheel sample was approximately `0.0859 m` forward and `0.0844 m` reverse. The wheel displacement over that interval was approximately `0.4433–0.4456 rad`.

These measured distances include command-window and sampling effects around the zero transition and are larger than the ideal `0.040 m` calculation. They are reported as measured braking-window distances, not as a claim that the ideal model is violated by exactly that amount.

## 22. Post-wheel-stop coasting

Status: BLOCKED

After the wheels reached the near-zero threshold, Candidate B7 still moved approximately `0.0385 m` during the following `0.50 s` window in both directions. During the next `1.00 s` window, movement was approximately `0.0226 m` forward and `0.0230 m` reverse.

Total movement from the first zero-command sample through the `2.00 s` observation was approximately `0.1470 m` forward and `0.1459 m` reverse. This is material residual physical motion after wheel velocity was near zero. Its exact cause—contact settling, body motion, remaining wheel motion below threshold, or measurement-window effects—was not isolated and remains BLOCKED.

## 23. Final contact settling

Status: NOT TESTED

The diagnostic run observed through `2.00 s` after zero command, but it did not prove a final asymptotic pose after all contact transients had ended. A longer-duration, event-based settling test with continuous ground truth and contact telemetry is required before declaring zero-command physical settling complete.

## 24. Contact telemetry attempt

Status: NOT TESTED

One focused attempt was made to obtain usable Gazebo contact information. No production-safe, model-level contact-wrench stream was available from the tested runtime path. No invasive production instrumentation was added, and no contact assertion was inferred from the absence of telemetry.

## 25. Selected production architecture

Status: BLOCKED

Selected architecture for the repository after Phase 4L is the unchanged Candidate A four-point production support. This is a preservation decision, not a motion-gate PASS. It has the strongest recomputed support margin and level static behavior, but its reverse and CCW motion results remain outside acceptance in the fresh Candidate A4 evidence.

Candidate B is rejected because its COM is outside the support polygon and it statically pitches. Candidate C is rejected because its rear margin is nearly zero and its runtime showed a large lateral drift and initial yaw offset.

## 26. Exact production change

Status: PASS

No production SDF change was authorized or made. The exact production model file remains `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`; its SHA-256 remains `56c347599eb0f078aa4b0107578655fe98681d034e0a88e945269cbfc92b89fb`.

Disposable Candidate B and Candidate C SDFs were generated under `/tmp` only. They did not alter the production model, ROS topics, frame names, wheel geometry, caster geometry, mass, inertia, COM, or DiffDrive values.

## 27. Production static regression

Status: PASS

The unchanged four-point production geometry remains statically level in the fresh Candidate A4 runtime. The recomputed COM is inside its support hull with `0.156342 m` minimum boundary margin. No production support/contact edit was introduced that would require a new static baseline.

## 28. Production forward repeats

Status: BLOCKED

Because production was not changed, the established Phase 4K three-repeat baseline remains the applicable production result: `4.428%`, `4.333%`, and `5.131%` error; average `4.631%`; worst `5.131%`.

The fresh Candidate A4 run measured `2.634%` settled error, but one fresh run cannot replace the required repeat set. The production forward repeat gate therefore remains BLOCKED by the established worst-case value above 5%.

## 29. Production reverse repeats

Status: BLOCKED

The unchanged production three-repeat baseline was `4.607%`, `4.988%`, and `4.776%`; average `4.790%`; worst `4.988%`. The fresh Candidate A4 run measured `5.090%`, also above the acceptance threshold.

The reverse gate is therefore BLOCKED, even though the earlier three-repeat baseline average was below 5%.

## 30. Production CCW repeats

Status: BLOCKED

The unchanged production three-repeat baseline was `18.097°`, `0°`, and `8.343°`; average `8.813°`; worst `18.097°`. The fresh Candidate A4 run measured `18.097°` error.

CCW rotation is the clearest unresolved production motion failure. No support candidate tested in Phase 4L produced a complete, valid replacement architecture.

## 31. Production CW repeats

Status: PASS

The unchanged production three-repeat baseline was `4.505°`, `0°`, and `3.373°`; average `2.626°`; worst `4.505°`, within the 5° acceptance threshold. Candidate A4 measured `0.440°` in its fresh run.

CW is not the blocking direction in the current evidence.

## 32. Production stop repeats

Status: BLOCKED

Earlier production stop observations showed approximately `0.028–0.032 m` residual movement over the prior stop window, with standalone zero-command ground displacement reported as zero in that specific measurement. Candidate B7, using a longer window and explicit wheel threshold, showed approximately `0.146–0.147 m` movement through `2.00 s` after zero command.

The measurements are not directly interchangeable because their windows and event definitions differ. A unified continuous stop test is still required; zero-command physical settling is therefore BLOCKED rather than declared PASS.

## 33. Sensor regression

Status: PASS

The established Phase 4K sensor regression remains valid for the unchanged production model: `/clock`, `/cmd_vel`, `/odom`, `/tf`, `/tf_static`, `/scan`, `/imu`, `/camera/image_raw`, and `/camera/camera_info` were operational. Prior observed rates were approximately `10.27 Hz` for the camera image and `11.59 Hz` for camera info.

Fresh headless runtime validation also found all nine required ROS topic types. Observed rates included `/clock` approximately `994 Hz`, `/scan` approximately `11.25 Hz`, `/imu` approximately `112.91 Hz`, `/camera/image_raw` approximately `14.80 Hz`, and `/camera/camera_info` approximately `15.01 Hz`. Fresh samples confirmed `/odom` frame `odom` to `base_footprint`, `/scan` frame `base_scan`, `/imu` frame `imu_link`, and camera-info frame `camera_rgb_optical_frame`.

The ROS camera frame contract remains `camera_link -> camera_rgb_frame -> camera_rgb_optical_frame`; fresh `/tf_static` output confirmed the chain and its optical-frame rotation. No Phase 4L change renamed a frame or ROS-facing topic.

## 34. Resource comparison

Status: PASS

The established Phase 4K runtime snapshots were approximately `383–421%` CPU, `550–553 MiB` resident memory out of `15.24 GiB`, and `108` processes. Swap use was approximately `4 GiB` at the time of those snapshots.

Fresh Phase 4L production runtime snapshot: `157.26%` CPU, `540.3 MiB / 15.24 GiB` memory, `87` PIDs. Host `free -h` reported `15 GiB` total RAM, `5.4 GiB` available, and `4.0 GiB` swap with `69 MiB` used at snapshot time. Candidate/build containers were disposable and removed after validation.

## 35. Build/validation

Status: PASS

The Phase 4L diagnostic tests cover the JSON Gazebo pose parser and support-polygon calculations. The validation set includes:

- `scripts/test_phase4k_diagnostics.py`
- `scripts/test_phase4l_support_analysis.py`
- Python compilation of the modified diagnostic scripts
- XML/SDF/Xacro/URDF validation
- YAML parsing
- `docker compose config`
- `git diff --check`
- containerized `rosdep` and `colcon build`

Fresh results: `9 passed in 0.01s` for the two diagnostic test files; Python compilation exit `0`; XML/SDF/Xacro/URDF validation exit `0`; YAML parsing exit `0`; `docker compose config -q` exit `0`; `git diff --check` exit `0`; containerized `rosdep update` and `rosdep install` completed successfully; containerized `colcon build --symlink-install` finished `5 packages` with exit `0`. The first runtime attempt against the stale image install-space failed before Gazebo startup because the new Xacro was not installed; the required full build corrected the disposable container environment and the repeated runtime passed. This stale-image warning is retained as an environment reproducibility risk, not hidden.

## 36. Files changed

Status: PASS

Phase 4L files added or modified by this work:

- `PHASE_4L_PRODUCTION_SUPPORT_ARCHITECTURE_REPORT.md`
- `docs/superpowers/plans/2026-09-18-phase-4l-support-architecture.md`
- `scripts/phase4l_support_analysis.py`
- `scripts/test_phase4l_support_analysis.py`
- `scripts/phase4k_diagnostics.py`
- `scripts/test_phase4k_diagnostics.py`
- `scripts/phase4k_turn_probe.py`

The candidate SDFs and runtime JSON captures used for analysis were disposable `/tmp` artifacts and are not production model changes.

## 37. Git diff stat

Status: PASS

The tracked `git diff --stat` at validation time was `18 files changed, 282 insertions(+), 312 deletions(-)`. Existing Phase 0 through Phase 4K worktree changes are included because this repository was intentionally not reset, cleaned, stashed, committed, or branched during Phase 4L. The Phase 4L report and other prior reports/scripts remain untracked user worktree files and are visible in `git status --short`.

## 38. Remaining risks

Status: BLOCKED

Remaining risks are:

- CCW physical yaw continues to disagree materially with `/odom`.
- Reverse translational error is at or above the 5% threshold in fresh evidence.
- Zero-command settling has measurable residual movement under the longer observation window.
- Gazebo contact-wrench telemetry was not obtained.
- Candidate B has invalid COM support geometry and static pitch.
- Candidate C has marginal support margin and large lateral drift.
- The Phase 4L measurements do not yet establish whether the CCW issue is contact anisotropy, joint/controller behavior, or another simulator interaction.
- `gz_frame_id` warnings for lidar, IMU, and camera remain DEFERRED; the ROS frame contract itself remains frozen.

No Nav2, SLAM Toolbox, AMCL, docking, ArUco runtime, mission, Web UI integration, payload test, or cafe-world redesign was started.

## 39. Final Phase 4 motion-gate decision

Status: BLOCKED

Phase 4L does not authorize Phase 5. The four-point production model remains in place because no replacement support architecture passed all gates, but the overall physical-motion/odometry gate is still BLOCKED by CCW error, reverse error, and unresolved stop settling.

This is not a claim that the full ROS sensor/runtime interface is broken. The sensor interface is operational; the physical motion correlation and support-architecture decision are incomplete.

## 40. Recommendation

Status: DEFERRED

Keep the current four-point production support unchanged. Before any navigation phase, run a separately authorized motion investigation with continuous ground truth, a unified stop-event definition, contact telemetry if available, and focused analysis of the CCW asymmetry. Re-run the full forward/reverse/CW/CCW/stop acceptance matrix after any meaningful physics or controller change.

Phase 5 is explicitly not started. Await explicit approval before proceeding.

## Final validation record

Status: BLOCKED

Fresh final record: branch `main`; HEAD `3ddde28b668d646fed8f9e39188a9f1153e74a28`; production SDF SHA-256 `56c347599eb0f078aa4b0107578655fe98681d034e0a88e945269cbfc92b89fb`; tests `9 passed`; rosdep exit `0`; colcon exit `0`; sensor runtime launched after build and was sampled; resource snapshot captured; `git diff --check` exit `0`. No production container remains running. The overall report remains BLOCKED because runtime motion gates, not build or sensor availability, are the unresolved issue.
