# Phase 4I DiffDrive Root-Cause Investigation Report

Date: 2026-09-17  
Scope: Cafe Service AMR ROS 2 Jazzy / Gazebo Harmonic only.  
Investigation result: **PASS** for root-cause identification.  
Production model result: **DEFERRED**; `amr_robot_harmonic/model.sdf` was not modified.

## 1. Executive summary

Phase 4I established that the approximately 50% physical-distance mismatch is
not caused by simulation time running at half speed and is not reproduced by the
official Gazebo Harmonic differential-drive reference in straight motion.

The first demonstrated divergence is Layer 4, physical contact/chassis motion:

```text
/cmd_vel → DiffDrive wheel target → wheel joint state → physical chassis contact → /odom
                                                        ^ divergence begins here
```

In the no-support diagnostic model, the wheels reach the expected angular
velocity and position, `/odom` integrates approximately 1.0 m, but the physical
model travels approximately 0.48 m and develops about 0.3026 rad pitch. The
two-wheel mechanism has only a degenerate support line and its COM is on that
line. A reviewed three-point disposable candidate with COM shifted 50 mm toward
the caster restored approximately 1.01 m physical straight travel and stable
90-degree turns. This candidate was not applied to the production Cafe model.

The official reference has a separate measurement caveat: its fixed ball caster
causes the model origin to travel on an arc during pure rotation while yaw still
matches odometry. Therefore strict XY comparison of the model-origin pose is not
valid for pure-turn acceptance without defining the odometry reference point.

## 2. Repository and Git safety

Confirmed repository:

- Root: `/home/deden/Documents/my-project/ros2-software-amr`
- ROS workspace: `ros2_ws`
- Simulation package: `ros2_ws/src/amr_simulation`
- Production model: `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- Runtime report: `PHASE_4_CAFE_AMR_ROBOT_RUNTIME_REPORT.md`
- Phase 4G report: `PHASE_4G_MOTION_CALIBRATION_REPORT.md`
- Phase 4H report: `PHASE_4H_PHYSICS_ISOLATION_REPORT.md`
- ROS contract: `docs/ROS_INTERFACE_CONTRACT.md`
- Branch: `main`
- HEAD: `3ddde28b668d646fed8f9e39188a9f1153e74a28`

Baseline `git diff --stat` and final cumulative tracked statistic remained:

```text
18 files changed, 282 insertions(+), 312 deletions(-)
```

No reset, clean, stash, commit, push, or branch switch was performed. The
production model checksum was recorded before diagnosis as
`b2c29743a07ecfafb117026e1f89f5dddfb8adca4e7ecb412b71b423b4c248b3`; the final
verification returned the same checksum. It was not targeted by any Phase 4I
operation.

## 3. Installed Gazebo and ROS versions

The diagnostic image is the repository's `amr-sim:jazzy` image.

| Component | Evidence |
|---|---|
| ROS distro | `ROS_DISTRO=jazzy` |
| Gazebo Sim | `Gazebo Sim, version 8.15.0` |
| `gz sim --versions` | `8.15.0` |
| `ros_gz_sim` | package XML version `1.0.24` |
| `ros_gz_bridge` | package XML version `1.0.24` |
| Harmonic family | gz-sim 8.x; gz-math 7.x; gz-msgs 10.x; gz-physics 7.x; sdformat 14.x family |
| Physics engine | `gz::physics::dartsim::Plugin` loaded from `gz-physics-7` |

`ros2 --version` is not supported by this ROS 2 CLI build; the sourced
environment and package paths identify the distro as Jazzy. Gazebo Harmonic is
the official gz-sim 8.x release family; the repository runtime report also
records ROS 2 Jazzy / Ubuntu Noble.

## 4. Known-good reference source

The reference is the official gz-sim 8 branch example, copied into a disposable
container and executed without editing the upstream repository:

- Source: [official gz-sim8 `examples/worlds/diff_drive.sdf`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/examples/worlds/diff_drive.sdf)
- Branch commit observed: `618e5529b5c433e9b8a40d678e21a78521d92435`
- Disposable copy SHA-256: `6d6a182ed978681656cf8ffa24b62fe102ec14459e7d2d2fa205cfb299a17375`
- Reference documentation: [Gazebo Harmonic moving robot](https://gazebosim.org/docs/harmonic/moving_robot/)

The reference was run headlessly with the same ROS-Gazebo bridge pattern and the
same independent `gz model` pose versus ROS `/odom` probe.

## 5. Known-good reference architecture

The official world contains two equivalent models, `vehicle_blue` and
`vehicle_green`. `vehicle_blue` was measured.

| Property | Official reference |
|---|---|
| World physics | `<max_step_size>0.001</max_step_size>`, `<real_time_factor>1.0</real_time_factor>` |
| Engine | DART plugin loaded by Harmonic runtime |
| Chassis | Box `2.01142 × 1 × 0.568726 m`; chassis link pose `(-0.151427, 0, 0.175)` |
| Chassis mass/inertia | `1.14395 kg`; `ixx=.126164`, `iyy=.416519`, `izz=.481014` |
| Drive wheels | Spheres, radius `0.3 m`, mass `2 kg` each |
| Wheel poses | `x=.554283`, `y=±.625029`, `z=-.025`, roll `-1.5707` |
| Wheel joints | Revolute, no joint pose, axis `0 0 1` |
| Wheel friction | ODE `mu=1`, `mu2=1`, `slip1=.035`, `slip2=0`, `fdir1=0 0 1`; Bullet friction also specified |
| Passive support | Sphere radius `.2 m`, mass `1 kg`, ball joint, pose `(-.957138,0,-.125)` |
| DiffDrive | `left_wheel_joint`, `right_wheel_joint`, separation `1.25 m`, radius `.3 m` |
| DiffDrive limits | linear acceleration ±1, angular acceleration ±2, linear velocity ±.5, angular velocity ±1 |

The official source includes a passive ball support and therefore is not a pure
two-wheel differential-drive mechanism. Its caster/contact reference point is
important when interpreting model-origin XY during pure turns.

## 6. Reference test results

The exact matrix was executed with the same probe: T1/T2/T3/T4, three repeats
in the first run and an instrumented one-repeat run with timing. Reference
straight results were:

| Test | Repeat results | Ground vs odom interpretation |
|---|---|---|
| T1 forward | `0.999`, `1.0024`, `1.0006 m` | matched to measurement precision |
| T2 reverse | `0.9996`, `1.0000`, `1.0000 m` | matched to measurement precision |
| T3 CCW | yaw about `91.9°` each repeat | yaw error about `0.004°`; model-origin XY about `.797–.803 m` |
| T4 CW | yaw about `-91.9°` each repeat | yaw error about `0.004°`; model-origin XY about `.795–.803 m` |
| T5 stop | zero ground movement, zero odom velocity | PASS |

The reference disproves the specific hypothesis that native Harmonic DiffDrive
or this wall-time duration inherently produces half physical travel. It does
not pass the raw pure-turn XY metric because the reference model origin follows
an arc around its constrained ball support. Its yaw behavior is repeatable and
correct.

## 7. Ground-truth methodology

Ground truth was queried independently with:

```text
gz model -m <model> -p
```

Odometry was sampled independently from ROS `/odom`. The probe did not derive
either measurement from the other. Joint state was queried through Gazebo's
Harmonic `JointStatePublisher` system, using:

```text
/world/amr_physics_test/model/amr_robot_physics_test/joint_state
```

The official Harmonic API documents that this system publishes joint position
and velocity in a Gazebo `gz.msgs.Model` message; the [JointStatePublisher API](https://gazebosim.org/api/sim/7/classgz_1_1sim_1_1systems_1_1JointStatePublisher.html)
was used as the mechanism reference.

## 8. Simulation-time versus wall-time

The instrumented probe records both `time.monotonic()` wall duration and ROS
`/clock` simulation duration. Representative results were:

| Run | Command | Wall duration | Simulation elapsed | `v × sim time` |
|---|---|---:|---:|---:|
| Minimal | T1 | 5.001 s | 5.408 s | 1.082 m |
| Minimal | T2 | 5.000 s | 5.341 s | 1.068 m |
| Minimal | T3 | 4.000 s | 4.344 s | 1.738 rad equivalent command-time product |
| Minimal | T4 | 4.001 s | 4.332 s | 1.733 rad equivalent command-time product |
| Reference | T1 | 5.001 s | 5.373 s | 1.075 m |
| Reference | T2 | 5.000 s | 5.377 s | 1.075 m |

The simulation advanced at approximately real time or slightly faster during
these samples, not at half real time. Even using measured simulation elapsed
time, the minimal model's expected straight travel is approximately 1.07–1.08 m,
while its physical travel is approximately 0.48 m. Timing cannot explain the
short physical distance.

The probe's simulation end sample includes a small post-command callback window;
this is retained as diagnostic timing slack and is not used to hide the physical
mismatch.

## 9. Probe timing audit

Before Phase 4I, `publish_for` used a wall-clock monotonic deadline. That was not
automatically classified as a bug because the clock comparison was required
first. Phase 4I added:

- `/clock` subscription with compatible best-effort QoS;
- `wall_elapsed_s` per trial;
- `simulation_elapsed_s` per trial;
- explicit `/clock` readiness timeout;
- preservation of the existing wall-time command loop.

The initial clock instrumentation exposed an incompatible QoS warning; changing
the diagnostic subscriber to best-effort resolved that instrumentation issue.
The measured wall/simulation relationship proves the harness was not commanding
for only 2.5 simulation seconds.

The harness has a separate measurement limitation: it compares world-frame XY
vectors directly. A small physical-vs-odom heading offset can inflate the vector
error even when displacement magnitudes agree. Pure-turn model-origin motion
from a constrained caster is also reported as translation. This limitation is
documented and is not used to claim a production PASS.

## 10. Expected differential-drive mathematics

For straight motion:

```text
omega_wheel = v / r
             = 0.20 / 0.09
             = 2.2222 rad/s
```

For pure rotation:

```text
v_wheel = angular_z × separation / 2
         = 0.40 × 0.42 / 2
         = 0.084 m/s

omega_wheel = v_wheel / radius
             = 0.084 / 0.09
             = 0.9333 rad/s
```

The signs are opposite between left and right wheels for rotation and reverse
for CW versus CCW. Expected straight travel for five seconds is 1.0 m at the
nominal wall command duration, or approximately 1.07–1.08 m using the measured
simulation elapsed times.

## 11. Command observations: Layer 1

`/cmd_vel` was operational. The probe published the required ROS
`geometry_msgs/msg/Twist` commands, and Gazebo's DiffDrive log confirmed the
subscription to the diagnostic model command topic. No command remap or sign
conversion was introduced by Phase 4I.

Layer 1 result: **PASS** for command delivery. Direct command latency telemetry
was **NOT TESTED**.

## 12. DiffDrive target observations: Layer 2

The native plugin configuration used named joints and matching radius/separation
values. The plugin published `/model/amr_robot_physics_test/odometry`, which was
bridged to `/odom`. Harmonic does not expose a separate DiffDrive target-velocity
topic in this setup.

The target layer is therefore supported by plugin configuration, plugin startup,
and measured joint velocity, but a direct internal target command sample was
**NOT TESTED**. No fake odometry scale or alternate odometry owner exists.

## 13. Joint-state observations: Layer 3

The diagnostic `JointStatePublisher` produced position and velocity for both
wheel joints. In the no-support minimal run:

| Measurement | Left wheel | Right wheel |
|---|---:|---:|
| Maximum absolute velocity | `2.2222222221 rad/s` | `2.2222222221 rad/s` |
| Straight expected velocity | `2.2222222222 rad/s` | `2.2222222222 rad/s` |
| Rotation expected magnitude | `0.9333333333 rad/s` | `0.9333333333 rad/s` |
| Observed rotation velocity magnitude | approximately `.933 rad/s` | approximately `.933 rad/s` |
| Straight joint position change | approximately `11.11 rad` per 5 s segment | approximately `11.11 rad` per 5 s segment |

The three forward segments moved the average wheel position from about `0` to
`11.11`, `11.13` to `22.24`, and `22.24` to `33.36 rad`. Reverse segments
returned those positions. Joint position and velocity therefore reach the
expected wheel kinematics even while physical chassis travel is short.

Layer 3 result: **PASS** for reaching the expected wheel state.

## 14. Physical chassis observations: Layer 4

The final no-support minimal model showed:

- T1 ground travel approximately `0.478–0.484 m`;
- T2 ground travel approximately `0.478–0.480 m`;
- `/odom` travel approximately `0.998–1.010 m`;
- physical yaw nearly zero during turns while `/odom` rotated approximately 92°;
- final model pitch approximately `+0.302575 rad`;
- wheel links remained near `z=.09`, while the model chassis was no longer level.

The divergence appears after wheel joint motion and before the physical chassis
pose. This is Layer 4.

## 15. Odometry observations: Layer 5

The native DiffDrive odometry followed the expected kinematic command and wheel
state: approximately 1.0 m for straight commands and approximately ±92° for
four-second rotation commands. It did not represent the observed physical
chassis pose of the no-support model.

Layer 5 is not the first divergence. It is a kinematic estimate consistent with
the wheel state, while the physical contact system fails to realize that motion.

## 16. Divergence-layer analysis

| Layer | Evidence | Result |
|---|---|---|
| 1. Command | ROS `/cmd_vel` live; plugin subscribed | PASS |
| 2. DiffDrive target | native plugin/configuration and resulting joint state; no direct target topic | NOT TESTED direct, supported indirectly |
| 3. Joint | velocities ±2.222 and ±.933 rad/s; positions change as expected | PASS |
| 4. Contact/chassis | physical travel half expected; pitch and turn lockup | FAIL; first demonstrated divergence |
| 5. Odometry | matches kinematic wheel integration, not physical pose | downstream mismatch |

The defensible first divergence is Layer 4. Direct internal target telemetry and
direct contact wrench telemetry were **NOT TESTED** because the selected runtime
did not expose them on the listed topics.

## 17. Known-good versus minimal structural diff

| Property | Known-good reference | Our minimal model | Relevant difference? |
|---|---|---|---|
| Chassis dimensions | `2.01142×1×.568726 m` | `.54×.50×.12 m` | yes, but simple model still fails |
| Chassis Z | model `.325`, chassis `.175` | chassis `.14` | yes |
| Chassis mass/inertia | `1.14395 kg`, reference matrix | `10 kg`, `.220/.255/.448` | yes |
| Wheel geometry | sphere radius `.3` | cylinder radius `.09`, length `.045` | yes |
| Wheel Z | relative `-.025` plus model pose | center `.09` | yes |
| Wheel roll | `-1.5707` | `-1.5707963` | no meaningful difference |
| Joint axis | `0 0 1` | `0 0 1` | no |
| Joint pose | none | none | no |
| Wheel collision | sphere, ODE + Bullet friction | cylinder, ODE friction | yes |
| Wheel inertial | `2 kg`, reference values | `.5 kg`, positive diagonal | yes |
| Passive support | ball-jointed sphere | none in failing candidate | yes; structurally important |
| Self-collision | false by model behavior/source | false | no |
| Canonical/reference point | caster-constrained reference model | two-wheel chassis model | yes; affects pure-turn XY |
| DiffDrive separation | `1.25 m` | `.42 m` | expected dimensional difference |
| DiffDrive radius | `.3 m` | `.09 m` | expected dimensional difference |
| Physics step | `.001 s` | `.001 s` | no |
| Real-time factor | `1.0` | `1.0` | no |
| Physics engine | DART | DART | no |
| Direct contact topic | not used by reference | not listed by minimal | **NOT TESTED** |

The most relevant structural differences for this investigation are support
geometry, COM/support polygon, and wheel/contact geometry. Radius/separation are
internally consistent in the minimal model and were not used as an odometry
scaling shortcut.

## 18. Static balance and support-polygon analysis

The failing minimal candidate has drive-wheel ground contact points at
approximately `(0,+.21)` and `(0,-.21)` and chassis COM at approximately
`(0,0)`. The convex hull is a line segment of zero area. The COM lies on that
line, so the model is only marginally statically supportable; any numerical
perturbation, acceleration, or unequal contact load can pitch the chassis.

The rear-support candidate added a support but did not review COM/load geometry;
it developed approximately 17.3° pitch and pure-turn failure. This showed that
“add a ball” alone is not a valid support design.

The disposable three-point candidate used a 40 mm ball centred at `x=-.25 m`,
with the drive axle at `x=0`, and shifted chassis COM by `-.05 m` toward that
caster. The COM then lies inside the triangle formed by the two drive contacts
and the caster contact, providing a non-degenerate support polygon.

## 19. Contact and normal-load findings

The listed Gazebo topics included pose, clock, stats, and joint state, but no
contact topic for this world/model. Direct wheel-ground/caster-ground normal
loads were therefore **NOT TESTED**.

Indirect evidence is consistent with the support explanation:

- no-support chassis pitch reached `0.302575 rad`;
- both wheel joints continued to rotate at target speed;
- the physical chassis translated only about half as far;
- a support-polygon/COM candidate restored straight physical travel;
- the caster+COM candidate kept idle pose near zero roll/pitch and removed the
  persistent half-distance result in three-repeat distance measurements.

No contact force or load value is claimed.

## 20. Hypotheses tested

| Hypothesis | Single meaningful change | Result |
|---|---|---|
| H1: wall-time command is only half simulation time | measured `/clock` alongside wall time | FAIL; simulation was approximately real-time or faster |
| H2: official Harmonic DiffDrive itself causes half travel | executed official gz-sim8 reference | FAIL; reference straight travel matched odom |
| H3: wheel target/joints do not reach target | added JointStatePublisher and measured state | FAIL; target wheel state was reached |
| H4: two-wheel chassis is marginally balanced | computed support line and observed pitch | PASS as contributing root cause |
| H5: arbitrary rear support is sufficient | ran prior support candidate | FAIL; pitch and turn behavior remained wrong |
| H6: reviewed caster support plus COM shift restores contact kinematics | disposable caster, then one COM shift | PASS diagnostically; production not changed |
| H7: raw world-frame XY metric is sufficient for caster pure turns | compared reference/model-origin XY | FAIL; caster reference point travels on an arc |

## 21. Root cause

The primary root cause of the Phase 4H half-distance and non-repeatable rotation
is an invalid/marginal physical support configuration in the minimal mechanism:
two driven wheel contacts form only a support line, with COM on that line. Under
dynamic drive/turn commands the model pitches/rocks while wheel joints continue
to execute the DiffDrive target. Contact constraints then prevent the chassis
from realizing the wheel kinematics. Native odometry continues integrating the
wheel state, so `/odom` overstates physical chassis motion.

This is a Layer 4 wheel-contact/chassis-balance failure, not a ROS command,
DiffDrive radius, simulation-time, or odometry-scale problem. The candidate with
reviewed three-point support and COM shift is strong causal evidence because it
restored physical straight distance and stable yaw in the disposable model.

## 22. Diagnostic fix tested

Only the disposable model was changed:

1. Add one 40 mm passive ball support at `x=-.25 m`, `z=.04 m`, with low friction.
2. Verify idle pose before motion: roll and pitch approximately zero, no visible
   spontaneous drift.
3. Shift only the chassis inertial COM by `-0.05 m` toward that caster.
4. Repeat the motion matrix.

This fix was not copied to `amr_robot_harmonic/model.sdf`. Production fix status:
**DEFERRED** pending approval and a separate production-model validation plan.

## 23. Before/after diagnostic results

The comparison is between the final no-support minimal candidate and the
disposable caster+COM candidate. The raw probe translation percentage is shown
with the frame/reference caveat described above.

| Test | No-support minimal | Caster + COM disposable candidate | Interpretation |
|---|---:|---:|---|
| T1 forward | `51.107%` average raw error | distance mismatch about `0.04%` across three repeats | physical distance restored |
| T2 reverse | `52.761%` average raw error | distance mismatch about `0.04%` across three repeats | physical distance restored |
| T3 CCW | `33.742°` average / physical yaw unstable | `0.303–1.557°` yaw error; XY arc `.0219–.0245 m` | yaw restored; arc is support/reference effect |
| T4 CW | `33.775°` average / physical yaw unstable | `0.447–1.525°` yaw error; XY arc `.0220–.0246 m` | yaw restored; arc is support/reference effect |
| T5 stop | zero movement in isolated stop | zero ground movement and zero odom velocity | PASS |

The caster+COM candidate's raw vector error can reach `6.49%` in straight
repeats after accumulated physical/odom heading offset. This is a probe-frame
metric limitation; the forward-axis displacement and distance magnitude agree
within approximately `0.04%`.

## 24. Files changed

Phase 4I added or modified only diagnostic/reporting assets:

- [`PHASE_4I_DIFFDRIVE_ROOT_CAUSE_REPORT.md`](/home/deden/Documents/my-project/ros2-software-amr/PHASE_4I_DIFFDRIVE_ROOT_CAUSE_REPORT.md)
- [`ros2_ws/src/amr_simulation/config/bridge_phase4i_reference.yaml`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/config/bridge_phase4i_reference.yaml)
- [`ros2_ws/src/amr_simulation/config/bridge_phase4i_caster.yaml`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/config/bridge_phase4i_caster.yaml)
- [`ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.sdf`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/models/amr_robot_physics_test/model.sdf) — diagnostic JointStatePublisher only
- [`ros2_ws/src/amr_simulation/models/amr_robot_physics_test_caster/model.sdf`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/models/amr_robot_physics_test_caster/model.sdf) — disposable caster/COM candidate
- [`ros2_ws/src/amr_simulation/models/amr_robot_physics_test_caster/model.config`](/home/deden/Documents/my-project/ros2-software-amr/ros2_ws/src/amr_simulation/models/amr_robot_physics_test_caster/model.config)
- [`scripts/phase4g_motion_probe.py`](/home/deden/Documents/my-project/ros2-software-amr/scripts/phase4g_motion_probe.py) — `/clock` QoS and wall/simulation timing fields
- [`docs/superpowers/plans/2026-09-17-phase-4i-diffdrive-root-cause.md`](/home/deden/Documents/my-project/ros2-software-amr/docs/superpowers/plans/2026-09-17-phase-4i-diffdrive-root-cause.md)

The production Cafe model was not changed.

## 25. Git diff stat and final verification

The cumulative tracked diff remains:

```text
18 files changed, 282 insertions(+), 312 deletions(-)
```

This excludes untracked Phase 0–4 reports and Phase 4H/4I diagnostic assets,
because `git diff --stat` reports tracked modifications only in this worktree.

Final checks performed:

- Python probe compilation: **PASS**
- Diagnostic SDF/XML parse: **PASS**
- Bridge YAML parse: **PASS**
- Gazebo Harmonic headless reference execution: **PASS**
- Minimal joint-state instrumentation: **PASS**
- Three-repeat diagnostic candidate execution: **PASS**
- `docker compose config --quiet`: **PASS**
- `git diff --check`: **PASS**
- Phase 5 runtime start: **DEFERRED**

## 26. Remaining uncertainty

- Direct DiffDrive internal target velocity was not exposed: **NOT TESTED**.
- Direct contact normal force/load telemetry was unavailable: **NOT TESTED**.
- The exact numerical contribution of DART contact solver settings versus COM
  placement versus wheel collision shape remains **NOT TESTED** separately.
- The three-point candidate improves motion, but it is not a production Cafe
  design. Its caster friction, geometry, load distribution, tall-stack behavior,
  and interaction with the existing four anti-tip supports still require a
  separate controlled review.
- The existing probe should eventually compare a defined odometry reference
  point and body-frame displacement, rather than only raw world-frame XY model
  displacement, before a production motion gate is called.

## 27. Recommended production fix and stop gate

Recommended production direction: review the Cafe model's support polygon and COM
against a physically valid three-point or four-point base, then test one change at
a time. The disposable result supports adding a correctly located passive support
and ensuring the empty-model COM lies inside the support polygon. Do not change
wheel radius/separation or scale odometry to compensate.

Production model change: **DEFERRED**.  
Phase 5 navigation/localization: **DEFERRED**.  
Phase 4I investigation: **PASS**.  
Phase 4G production motion gate: **BLOCKED** until the approved production fix
is validated with a corrected, frame-aware ground-truth test.

This is the stopping point. No Nav2, SLAM, AMCL, docking, ArUco runtime, mission,
Web UI, cafe-world redesign, or production physics redesign was started.
