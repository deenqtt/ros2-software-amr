# Phase 4J Production Support/COM Fix Plan

## Goal

Make one evidence-backed support/COM change to the production Cafe AMR Harmonic
model, then validate static stability, physical motion versus odometry, sensors,
build, and headless runtime without starting Phase 5 systems.

## Safety baseline

- Work only in `/home/deden/Documents/my-project/ros2-software-amr`.
- Preserve existing uncommitted work; do not reset, clean, stash, commit, push,
  or switch branch.
- Do not start Nav2, SLAM Toolbox, AMCL, docking, ArUco runtime, mission
  integration, Web UI integration, or redesign the Cafe world.
- Keep wheel radius `0.09 m`, wheel separation `0.42 m`, ROS topic names, and TF
  contract unchanged.

## Work sequence

1. Record repository identity, worktree state, production-model checksum, and
   inspect the production SDF and prior Phase 4H/4I evidence.
2. Extract production physical links, masses, link/inertial poses, collision
   support geometry, friction, and DiffDrive settings. Compute total mass and
   empty-model COM in the model frame, and compare it to the actual support
   polygon.
3. Extend the motion probe metrics with a defined body-forward reference point,
   raw world XY, ground distance magnitude, odom distance magnitude, lateral
   drift, wrapped yaw, and caster-origin arc accounting. Add a focused test
   first, run it failing, then implement the smallest probe change and run it
   passing.
4. Select one minimum credible production support/COM/contact change based on
   measured geometry. Apply only that change to the production SDF; do not copy
   diagnostic values blindly and do not scale odometry.
5. Run a static headless settling gate before commands: roll/pitch/yaw, z, COM
   and support geometry, drift/rocking, drive-wheel contact, intended support
   contact, anti-tip non-dragging, and stability. If it fails, do not run motion
   tests and report BLOCKED.
6. Run the smoke matrix, then three independent repeats for forward, reverse,
   CW, CCW, and zero stop. Capture command, wall/sim time, ground pose, odom,
   body-forward/lateral displacement, yaw, wheel joints when available, and
   roll/pitch.
7. Run fresh sensor/ROS interface regression, XML/SDF/Xacro/YAML/Python checks,
   full rosdep, full colcon, compose validation, headless spawn, resource
   snapshots, and `git diff --check`.
8. Write `PHASE_4J_PRODUCTION_SUPPORT_COM_FIX_REPORT.md` with evidence, exact
   changes, before/after tables, all required pass/fail/not-tested states,
   changed files, diff stat, risks, and PASS/BLOCKED recommendation. Stop.

## Acceptance

- Straight physical distance versus odometry error <= 5% (preferred <= 3%).
- Approximately 90-degree CW/CCW yaw error <= 5 degrees (preferred <= 3%).
- Correct direction, lateral drift <= 0.05 m per ~1 m (preferred <= 0.03 m),
  repeatable turns, no wheel lift/large pitch or roll, no severe slip/caster
  lockup/anti-tip drag, and reliable stop.
- PASS only with runtime evidence for support geometry, static stability, motion,
  sensors, interfaces, headless execution, rosdep, and colcon. Otherwise use
  BLOCKED/FAIL/NOT TESTED/DEFERRED as applicable and do not start Phase 5.
