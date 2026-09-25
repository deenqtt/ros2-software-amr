# Runtime GUI, Mode Switching, and Simple Command Plan

## Goal

Make the Cafe Service AMR simulation easy to operate from the host:

- `bash scripts/docker_run.sh gazebo` opens Gazebo GUI when X11/GPU is available.
- `bash scripts/docker_run.sh slam` starts the full SLAM runtime.
- `bash scripts/docker_run.sh nav maps/amr_map.yaml` starts the navigation runtime.
- Web UI mode changes persist UI/backend state without trying to execute a host
  script from inside the backend container.

## Design already approved

The host script is the runtime entry point. The backend remains an API/state
service and does not receive Docker-socket access. The existing ROS launch
files remain authoritative; the changes only expose GUI/headless arguments and
make the command wrapper select the existing SLAM/navigation branches.

## Execution steps

1. Add CLI and mode API contract tests; run them against the current code to
   capture the expected red state.
2. Fix the Gazebo compose command and expose `gui`/`headless` through the full
   bringup launch.
3. Replace deferred/ambiguous wrapper aliases with `gazebo`, `slam`, `nav`,
   `teleop`, `save-map`, `down`, and `logs` commands while preserving existing
   user changes.
4. Make backend mode switching persistence-only and update the Web UI header
   switch to call that API instead of the unavailable ROS `/robot_mode` service.
5. Run contract tests, compose validation, frontend/backend builds, and a
   runtime smoke test. Report any GUI limitation caused by the local display or
   GPU environment separately from source correctness.

## Safety boundaries

- Do not reset, clean, stash, switch branches, commit, or push.
- Do not change Gazebo physics, sensor contracts, docking behavior, Nav2
  parameters, or map contents.
- Do not start Phase 6 work.
