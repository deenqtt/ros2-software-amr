# Phase 3 — Gazebo Harmonic Foundation Report

Tanggal: 2026-09-17  
Scope: Gazebo Sim/Harmonic foundation, world migration, and robot spawn only.  
Status gate: **PASS** for the Phase 3 foundation; Phase 4+ remains deferred.

## 1. Executive summary

The active AMR simulation path now uses ROS 2 Jazzy with Gazebo Sim 8.15.0
(Harmonic line) rather than Gazebo Classic. A migrated SDF world starts, the
`amr_robot` foundation model spawns successfully, and `/clock` is bridged
into ROS 2. The default is server-only/headless mode; GUI is opt-in.

No sensor, DiffDrive, odometry, Nav2, SLAM, docking, RViz, Web UI, or backend
behavior was activated in this phase. The ROS application contract remains
frozen and the physical-robot mapping remains TBD.

## 2. Pre-write Git state

Safety checks before Phase 3 writes recorded:

```text
branch: main
HEAD: 3ddde28b668d646fed8f9e39188a9f1153e74a28
tracking: main...origin/main
staged files:
c5h/   c5h2a/ c5h2b/ c5h2c/ c5h2d/ c5h2e/  none
```

Existing Phase 0/1/2 modifications and untracked reports were preserved. No
reset, checkout, clean, stash, commit, push, or branch switch was performed.

## 3. Files changed for Phase 3

- `ros2_ws/src/amr_simulation/launch/sim.launch.py`
- `ros2_ws/src/amr_simulation/worlds/amr_world.sdf`
- `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf`
- `ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.config`
- `ros2_ws/src/amr_simulation/models/aruco_dock/model.sdf`
- `ros2_ws/src/amr_simulation/models/aruco_dock/model.config`
- `ros2_ws/src/amr_simulation/package.xml`
- `docker/Dockerfile`
- `docker/entrypoint.sh`
- `docker-compose.yml`
- `scripts/docker_run.sh`
- `docs/JAZZY_DEPENDENCY_STATUS.md`
- `docs/ROS_INTERFACE_CONTRACT.md`
- this report.

The legacy `amr_robot.urdf` and `amr_world.world` were not deleted or
modified as active references; they remain rollback/comparison artifacts.

## 4. Gazebo Classic audit

The former active chain was `gazebo_ros/launch/gazebo.launch.py` plus
`gazebo_ros/spawn_entity.py`. The old URDF used Classic DiffDrive, ray, IMU,
and camera plugins. The old world used `libgazebo_ros_state.so`, Classic
material scripts, and a Classic model include.

Direct validation of the old `.world` under Gazebo Sim 8.15.0 failed with
repeated missing `<script><uri>` errors and `Failed to load a world`. This
is why the Phase 3 path uses a separate SDF world/model instead of pretending
that the Classic files are already Harmonic-compatible.

## 5. Classic → Harmonic mapping

| Classic component | Phase 3 disposition | Phase |
| --- | --- | --- |
| `gazebo_ros` launch | `ros_gz_sim/launch/gz_sim.launch.py` | PHASE 3 |
| `gazebo_ros/spawn_entity.py` | `ros_gz_sim/launch/gz_spawn_model.launch.py` / `create` | PHASE 3 |
| `amr_world.world` | New `worlds/amr_world.sdf` | PHASE 3 |
| Classic robot URDF asset | New plugin-free `models/amr_robot_harmonic/model.sdf` | PHASE 3 representation; behavior PHASE 4 |
| `GAZEBO_MODEL_PATH` | `GZ_SIM_RESOURCE_PATH` | PHASE 3 |
| `libgazebo_ros_state.so` | Removed from active world; no current consumer | REMOVE |
| Classic DiffDrive plugin | Gazebo Sim DiffDrive system plus ROS bridge | PHASE 4 |
| Classic ray sensor plugin | Gazebo Sim lidar system plus ROS bridge | PHASE 4 |
| Classic IMU plugin | Gazebo Sim IMU system plus ROS bridge | PHASE 4 |
| Classic camera plugin | Gazebo Sim camera/image bridge | PHASE 4 |
| `/clock` | `ros_gz_bridge/parameter_bridge` | PHASE 3 |

## 6. Dependency changes

`amr_simulation` now declares `ros_gz_sim` and `ros_gz_bridge` for the
active launch path. Active `gazebo_ros` and `gazebo_ros_pkgs` declarations
were removed. TurtleBot3 description/simulation packages remain available for
meshes and historical/reference assets. No new sensor or control dependency
was introduced.

## 7. Launch architecture

`sim.launch.py` declares world, GUI/headless, simulation-time, robot entity,
and spawn-pose arguments. It includes the installed Jazzy `ros_gz_sim`
launch, starts only one direct `/clock` bridge, and delays model creation by
two seconds so the world is ready. If `headless:=true`, server-only mode wins
even when `gui:=true`.

## 8. World migration

`amr_world.sdf` is SDF 1.9 and preserves the 10 m room, four walls, four
shelves, and ArUco dock layout. Classic script materials and the Classic world
plugin were removed. Native SDF ambient/diffuse materials, scene settings,
light, and physics settings are used instead.

The ArUco dock model was also made SDF 1.9-compatible. Its camera marker
texture is intentionally deferred to the sensor/camera phase.

## 9. Resource paths

The image and entrypoint use `GZ_SIM_RESOURCE_PATH` with the project models
and ROS share roots. The runtime smoke command additionally exported:

```text
/ros2_ws/src/amr_simulation/models:/opt/ros/jazzy/share:/opt/ros/jazzy/share/turtlebot3_gazebo/models
```

This resolves both the project `aruco_dock` include and TurtleBot3 mesh URIs.

## 10. Robot spawn

`amr_robot_harmonic/model.sdf` contains the base, wheels, casters, primitive
collisions, inertials, and joints. It is deliberately plugin-free. The active
spawn path uses the installed `ros_gz_sim` `create` executable with entity
name `amr_robot`, world `amr_world`, and default pose `(0, 0, 0.05)`.

## 11. Plugin handling

No Classic plugin library is loaded by the active Phase 3 world or robot model.
The model is a physical/rendering foundation only. DiffDrive, sensors, bridges,
and application consumers are explicitly deferred so Phase 3 cannot falsely
claim odometry or navigation readiness.

## 12. Clock

The launch starts:

```text
/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock
```

Runtime log evidence:

```text
Creating GZ->ROS Bridge: [/clock (gz.msgs.Clock) -> /clock (rosgraph_msgs/msg/Clock)]
```

The `/clock` bridge is simulation-time infrastructure and does not alter the
frozen application interface contract.

## 13. GUI mode

GUI is opt-in with `gui:=true headless:=false` or Compose
`SIM_GUI=true` and `SIM_HEADLESS=false`. A short GUI run with X11 access
enabled initialized Qt successfully and stayed alive until it was explicitly
stopped after the smoke window. An earlier run without X authorization
produced the expected Qt/XCB connection failure; the X11 permission setup in
`scripts/docker_run.sh` is therefore required for local GUI use.

## 14. Headless mode

Headless is the default. Runtime process evidence:

```text
/bin/sh -c ruby .../gz sim -s -r .../amr_world.sdf --force-version 8
gz sim -s -r .../amr_world.sdf
```

No `gz-gui` process was present. This is the recommended default for server
and robot mini-computer deployment.

## 15. Docker Compose

The `amr-sim` service now launches only `amr_simulation sim.launch.py` with
Jazzy/Harmonic foundation arguments. Compose keeps host networking, X11/GPU
access, and source hot-reload. `FOUNDATION_ONLY=true` remains available as a
container smoke mode. Backend, Web UI, teleop, Nav2, and SLAM services were
not started as part of this Phase 3 gate.

## 16. Full rosdep

Command:

```bash
docker run --rm -v "$PWD/ros2_ws/src:/verify_ws/src:ro" amr-sim:jazzy \
  bash -lc 'source /opt/ros/jazzy/setup.bash; cd /verify_ws; \
  rosdep install --from-paths src --ignore-src -y --rosdistro jazzy'
```

Result:

```text
#All required rosdeps installed successfully
```

Status: **PASS**.

## 17. Full colcon

The same clean verification workspace ran:

```bash
colcon build --symlink-install
```

Result:

```text
Summary: 5 packages finished [24.8s]
```

Status: **PASS**.

## 18. Gazebo version evidence

```text
Gazebo Sim, version 8.15.0
```

The launch forces Gazebo version 8 through the supported Jazzy
`ros_gz_sim` launch argument. This is the tested Gazebo Sim/Harmonic runtime.

## 19. World runtime test

The world started through the active launch in both direct Docker and Compose
tests. The Compose service reached `Up ... (healthy)` and its log contained
no matching error, failed, warning, or warn lines.

Status: **PASS**.

## 20. Spawn runtime test

Runtime log:

```text
[ros_gz_sim] Entity creation successful.
```

Gazebo model listing:

```text
ground_plane
wall_north
wall_south
wall_east
wall_west
shelf_1
shelf_2
shelf_3
shelf_4
aruco_dock
amr_robot
```

Status: **PASS**.

## 21. Clock runtime test

```text
Type: rosgraph_msgs/msg/Clock
Publisher count: 1
Subscription count: 1
clock:
  sec: 18
  nanosec: 489000000
```

The Compose test also received a live `/clock` sample. A second publisher in
the Compose query was from the intentionally still-running direct smoke
container at that moment; each isolated launch had one bridge publisher.

Status: **PASS**.

## 22. Headless runtime test

The default direct launch and Compose launch ran with
`gui:=false headless:=true`. The server process used `gz sim -s`; no GUI
process was present, and the robot spawned successfully.

Status: **PASS**.

## 23. GUI runtime test

The host provided `DISPLAY=:0` and `/tmp/.X11-unix/X0`. With temporary
scoped `xhost +local:root` access and Xauthority/socket mounts, Gazebo GUI
initialized without the previous Qt/XCB failure. The test was explicitly
stopped after the GUI startup smoke window.

Status: **PASS**.

## 24. Resource baseline

Host snapshot during the simulation:

```text
Mem: 15Gi total, 10Gi used, 437Mi free, 1.9Gi shared,
     6.0Gi buff/cache, 4.7Gi available
Swap: 4.0Gi total, 4.0Gi used, 11Mi free
```

Container snapshot:

```text
container=phase3-sim-test cpu=205.10% mem=246.1MiB / 15.24GiB mem_pct=1.58%
compose=amr-sim cpu=100.26% mem=152.6MiB / 15.24GiB mem_pct=0.98%
```

The CPU snapshot is environment-dependent and reflects real-time simulation
load; it is not a performance guarantee for a robot mini-computer.

## 25. Interface impact

No frozen application topic, service, action, field, namespace, or TF mapping
was changed. Only `/clock` was activated as the minimum simulation-time
bridge. The real-robot mapping remains entirely `TBD` in
`docs/ROS_INTERFACE_CONTRACT.md`.

## 26. Failures and blockers

- The old Classic `.world` fails under Gazebo Sim due to Classic material
  scripts; it remains inactive reference material.
- An initial GUI attempt without X authorization failed with Qt/XCB display
  authorization; the scoped X11 setup then passed the GUI startup smoke test.
- No Phase 3 implementation blocker remains.

## 27. Phase 4 deferred work

The following are intentionally not implemented here:

- Gazebo Sim DiffDrive and `/cmd_vel` bridge;
- `/odom` and `odom → base_footprint`;
- LiDAR, IMU, camera, image bridge, and camera marker texture;
- `robot_state_publisher`/sensor TF runtime;
- Nav2, SLAM Toolbox, docking, mission nodes, and Web UI integration;
- RViz configuration and visualization launch;
- map save/load and application mode orchestration.

## 28. Git diff stat

At the final check, tracked diff stat was:

```text
18 files changed, 264 insertions(+), 319 deletions(-)
```

This includes the pre-existing Phase 0/1/2 tracked changes. New untracked
Phase 3 artifacts are listed in Section 3 and shown by `git status --short`.

## 29. Validation matrix

| Gate | Status |
| --- | --- |
| Phase 3 scope adherence | PASS |
| SDF/XML parse | PASS |
| `git diff --check` | PASS |
| shell syntax checks | PASS |
| full rosdep on Jazzy | PASS |
| full colcon build (5 packages) | PASS |
| Gazebo Sim 8.15.0 available | PASS |
| world start | PASS |
| robot spawn | PASS |
| `/clock` bridge and sample | PASS |
| headless mode | PASS |
| GUI startup smoke | PASS |
| sensor/control runtime | DEFERRED |
| Nav2/SLAM/docking runtime | DEFERRED |
| RViz integration | DEFERRED |
| physical robot mapping | DEFERRED |

## 30. Recommendation for Phase 4

Proceed to Phase 4 only after review of this gate. The next implementation
should add one simulation capability at a time—starting with Gazebo Sim
DiffDrive and `/odom`, then sensor systems and bridges—while preserving the
frozen ROS interface contract and re-running the same headless smoke test after
each addition.
