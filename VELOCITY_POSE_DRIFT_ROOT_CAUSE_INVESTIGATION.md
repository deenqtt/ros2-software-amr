# VELOCITY / POSE DRIFT ROOT-CAUSE INVESTIGATION

## 1. Executive Summary

**INVESTIGATION: INCONCLUSIVE**

The source-level telemetry path is established, but the runtime reproduction could
not be measured because Computer B had Isaac Sim running without the AMR ROS launch
stack. The active ROS graph contained only `/parameter_events` and `/rosout`; no
`/cmd_vel`, `/odom`, `/tf`, `/tf_static`, or rosbridge `:8765` endpoint was active.

The frontend is not shown to synthesize velocity or integrate velocity into pose.
The main source-level risk identified is a possible dynamic TF authority conflict:
Gazebo DiffDrive is configured to publish `odom→base_link` while EKF is also
configured with `publish_tf: true`. This remains unverified for the actual Isaac
runtime and cannot be called the root cause.

## 2. Observed Symptom

The reported symptom is small changing Web UI linear/angular velocity after joystick
release and apparent Web UI pose/orientation drift while the simulator appears still.
No fresh motion sample was collected in this run.

## 3. Architecture

Intended path:

`Browser → rosbridge :8765 → ROS 2 → simulator/estimator → /odom and TF → ROSLIB → Pinia → MapView`

FastAPI is a separate HTTP API path and does not carry ROS telemetry in the inspected
source.

## 4. Investigation Method

Read-only source tracing, local git/runtime inventory, remote workspace/runtime
inventory, bounded ROS graph queries, and launch/configuration tracing were used.
No application source was changed, no robot command was published, and no mode,
mission, navigation, docking, SLAM save, simulator, node, Docker, or Web UI action
was triggered.

## 5. Local Git Baseline

Computer A was on `main` at `3ddde28b668d646fed8f9e39188a9f1153e74a28` with a dirty
working tree before investigation. `web-ui/src/composables/useROS.js` was already
modified before this work. Existing user changes were preserved.

## 6. Remote Workspace Baseline

Computer B was `gspe-ai3-MS-7E32`, workspace `~/ros2_gprp_amr_ws`, branch
`desktop_test`, commit `73d4fd1bd66529111bc0aa8d8e6aacd34aa00d26`, ROS Jazzy,
`ROS_DOMAIN_ID=10`, and dirty before investigation.

## 7. Frontend Telemetry Data Lineage

**VERIFIED FROM SOURCE**

| UI value | Source | Field/logic |
|---|---|---|
| Linear velocity | `/odom` | `twist.twist.linear.x`, `useROS.js:412-420` |
| Angular velocity | `/odom` | `twist.twist.angular.z`, `useROS.js:412-420` |
| Robot X/Y | `/tf` primary; `/amcl_pose` or `/pose` fallback | composed transform, `useROS.js:346-409` |
| Robot yaw | `/tf` primary; pose fallback | quaternion-to-yaw then TF composition |

`/odom.pose` is not used by the frontend for robot position. `/odom` is used for
velocity only.

## 8. Backend Role

**VERIFIED FROM SOURCE:** FastAPI exposes database/map/mission/configuration HTTP
routes and system stats. No ROSLIB, rclpy, rosbridge proxy, `/odom`, `/cmd_vel`,
or TF subscription was found. Backend is not on the telemetry path for this issue.

## 9. ROS Graph

**VERIFIED AT RUNTIME:** Current Computer B graph exposed only `/parameter_events`
and `/rosout`. AMR topics and nodes were absent. This is a runtime availability
finding, not proof that the normal launch graph is incorrect.

## 10. `/cmd_vel` Authority

**NOT VERIFIED AT RUNTIME:** `/cmd_vel` did not exist in the current graph, so the
publisher count was zero for the current inactive graph and unavailable for the
bug reproduction. Source shows the Gazebo bridge maps simulator command input to
`/cmd_vel`; the Web UI can publish a Twist when teleop is used.

## 11. `/odom` Authority

**NOT VERIFIED AT RUNTIME:** `/odom` did not exist in the current graph. Source
shows Gazebo DiffDrive/bridge as an intended odometry source, while EKF consumes
`/odom` and is configured to publish filtered output rather than a second `/odom`
message.

## 12. TF Authority

**NOT VERIFIED AT RUNTIME:** `/tf` and `/tf_static` were absent. Source shows:

- Gazebo DiffDrive: dynamic `odom→base_link` TF enabled.
- EKF: `publish_tf: true`, also targeting `odom→base_link`.
- robot_state_publisher: structural fixed-frame TF.

The first two are a potential dynamic authority conflict if launched together.

## 13. Idle Baseline

**NOT VERIFIED:** no idle message sample was possible because the AMR ROS graph was
not active.

## 14. Manual Motion Test

**NOT PERFORMED:** no motion was requested or initiated by the investigation.

## 15. Post-Joystick `/cmd_vel`

**NOT VERIFIED:** no post-release sample exists.

## 16. Post-Joystick `/odom.twist`

**NOT VERIFIED:** no post-release sample exists.

## 17. Post-Joystick `/odom.pose`

**NOT VERIFIED:** no post-release sample exists. Also, the frontend does not consume
this field for its displayed pose.

## 18. Post-Joystick TF

**NOT VERIFIED:** no post-release TF sample exists.

## 19. Simulator Ground Truth

Isaac Sim process PID 39534 was observed, but no ROS topic/API ground-truth sample
was collected. Numerical simulator ground truth is **NOT VERIFIED**. Visual
stationarity remains only operator visual evidence.

## 20. rosbridge Observation

**VERIFIED AT RUNTIME:** no listener on remote TCP port `8765` was found. Source
confirms the intended server is `rosbridge_websocket` on port `8765`, launched by
the mapping/navigation launch files.

## 21. Browser Raw Data

**NOT VERIFIED:** no local Web UI process/browser session was active during the
inspection, so raw WebSocket frames could not be compared with ROS messages.

## 22. Pinia State

**VERIFIED FROM SOURCE, NOT VERIFIED AT RUNTIME:** `robotVelocity` is directly
assigned from `/odom` values; `robotPose` is directly assigned from composed TF or
fallback pose callbacks. Runtime duplicate callbacks/stale state were not tested.

## 23. MapView Rendering

**VERIFIED FROM SOURCE, NOT VERIFIED AT RUNTIME:** MapView watches `robotPose`,
maps X/Y to Leaflet, and applies `Math.PI / 2 - theta` as a CSS rotation. It removes
an existing `rotate(...)` before appending the current rotation, so source shows no
accumulated CSS yaw.

## 24. Quaternion/Yaw Analysis

The formula is the standard planar yaw formula:

`atan2(2(wz + xy), 1 - 2(y² + z²))`

It uses ROS quaternion fields correctly and radians consistently. The implementation
does not normalize quaternions explicitly; ROS producers normally provide normalized
quaternions. The TF composition adds parent and child yaw rather than accumulating
across callbacks. A timestamp is not retained per transform, so mixed-time latest
TF components remain a source-level limitation, not a verified cause.

## 25. Duplicate Subscription Analysis

`useROS()` uses one module-level ROS singleton. Multiple component calls do not by
themselves create multiple connections. Reconnect closes the prior ROS object and
creates new subscriptions, but there is no explicit unsubscribe registry. Source
therefore leaves a reconnect-duplication hypothesis open; browser WebSocket and
rosbridge client counts are required to prove or disprove it.

## 26. Cross-Machine Comparison

The required comparison could not be made. Computer B had no active ROS telemetry,
and Computer A had no active Web UI/rosbridge/backend process at inspection time.

## 27. First Divergence

**NOT IDENTIFIED.** No runtime data crossed the first meaningful boundary during the
reproduction window. Source tracing alone cannot distinguish command residual,
simulator odometry, TF conflict, transport, Pinia, or rendering divergence.

## 28. Root Cause

**NOT IDENTIFIED.** The evidence is insufficient for a root-cause claim.

## 29. Contributing Factors

**INFERRED FROM SOURCE:**

1. Potential duplicate dynamic TF authority between Gazebo DiffDrive and EKF.
2. Frontend TF buffer stores latest transforms without timestamps and composes them
   without validating common timestamps.
3. Reconnect path does not explicitly unsubscribe old topic objects.

These are hypotheses/contributing risks, not confirmed causes.

## 30. What Is NOT the Cause

The following are excluded as primary telemetry participants by source inspection:

- FastAPI backend telemetry transformation/proxying.
- Frontend integration of velocity into pose.
- Frontend use of `/odom.pose` to render robot pose.
- CSS yaw accumulation in the inspected MapView watcher.

They are not fully excluded as runtime integration issues until a browser sample is
available.

## 31. Evidence Matrix

| Layer | Evidence | Status |
|---|---|---|
| Joystick → `/cmd_vel` | no active graph | NOT VERIFIED |
| `/cmd_vel` → simulator | launch/source mapping only | SOURCE ONLY |
| Simulator pose | Isaac process only; no numeric ground truth | NOT VERIFIED |
| `/odom` twist/pose | topic absent | NOT VERIFIED |
| TF | topic absent; source suggests possible conflict | NOT VERIFIED / HYPOTHESIS |
| rosbridge | source says `:8765`; port absent | NOT VERIFIED |
| ROSLIB | source traced | VERIFIED FROM SOURCE |
| Pinia | source traced | VERIFIED FROM SOURCE |
| MapView | source traced | VERIFIED FROM SOURCE |

## 32. Recommended Fix Direction

Design only, no implementation:

1. Reproduce with the normal ROS launch already used by the operator.
2. Measure `/cmd_vel`, `/odom`, and TF in one post-release window.
3. If runtime confirms two dynamic `odom→base_link` publishers, choose one owner
   and disable the other.
4. If ROS data is stable but UI drifts, inspect browser frames, callback counts,
   Pinia updates, and MapView rendering next.
5. Apply velocity-display deadband only after pose/TF authority is proven healthy.

## 33. Remaining Unknowns

- Which exact launch/session produced the original symptom.
- Whether Isaac Sim is configured with ROS 2 bridge and matching domain 10.
- Runtime `/cmd_vel` publisher count after teleop release.
- Runtime `/odom` publisher count, values, timestamps, and frequency.
- Runtime TF publisher authority and duplicate-frame conflicts.
- Numeric simulator ground truth.
- Browser WebSocket count and raw rosbridge payloads.
- Pinia callback count and rendered marker behavior.

## 34. Final Decision

**INVESTIGATION: INCONCLUSIVE**

The first divergence and root cause are not supportable from current evidence. The
next safe evidence window requires the operator to have the already-used ROS launch
stack active without changing mode through this investigation, then manually move
and release the joystick while the passive samples are captured.
