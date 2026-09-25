# AMR Simulation Commands

This runbook is for the Cafe Service AMR ROS 2 Jazzy / Gazebo Harmonic
simulation in Docker. Commands were checked against the current repository and
the production amr-sim container during Phase 5A and Phase 5B.

The default ROS domain is 42. Run Docker commands on the host. Run ROS and
Gazebo inspection commands inside the running amr-sim container unless a
command says otherwise.

## 1. Repository

Host:

~~~bash
cd /home/deden/Documents/my-project/ros2-software-amr
~~~

## 2. Build Docker Image

Host; rebuilds the current AMR image and workspace from repository source:

~~~bash
docker compose build amr-sim
~~~

Expected result: Image amr-sim:jazzy Built and a five-package colcon build.

The repository wrapper is also available, but builds all Compose services:

~~~bash
bash scripts/docker_run.sh build
~~~

## 3. Simple Runtime Commands

The recommended host entry point is the wrapper. Commands that start a runtime
stay in the foreground; press Ctrl-C to stop it.

Gazebo GUI only:

~~~bash
bash scripts/docker_run.sh gazebo
~~~

Headless Gazebo foundation only:

~~~bash
bash scripts/docker_run.sh headless
~~~

Full SLAM/mapping runtime, including rosbridge and web video:

~~~bash
bash scripts/docker_run.sh slam
~~~

Full Navigation2 runtime using the saved map:

~~~bash
bash scripts/docker_run.sh nav maps/amr_map.yaml
~~~

Stop only AMR simulation containers:

~~~bash
bash scripts/docker_run.sh down
~~~

The equivalent low-level commands are still available with
`docker compose`, but the wrapper is preferred because it selects the correct
launch branch and passes the GUI/headless arguments consistently.

## 4. Start With GUI (low-level equivalent)

Host with a working X11 display and Docker X11 permission:

~~~bash
SIM_GUI=true SIM_HEADLESS=false docker compose up amr-sim
~~~

The launch file gives headless mode precedence. Both variables must therefore
be set as shown. The current host may still require an X11 authorization setup;
if Gazebo reports Authorization required, use headless mode.

## 5. Start Headless (low-level equivalent)

Host; this is the recommended low-resource mode:

~~~bash
SIM_GUI=false SIM_HEADLESS=true docker compose up amr-sim
~~~

The Compose defaults are already equivalent to this command. This starts only
the simulator foundation, not SLAM or Nav2.

## 6. Enter Running ROS Container

Host, interactive:

~~~bash
docker compose exec amr-sim bash --rcfile /entrypoint.sh
~~~

Expected result: a shell inside amr-sim. The entrypoint sources Jazzy and sets
the simulator resource path.

For non-interactive checks from the host:

~~~bash
docker compose exec -T amr-sim bash -lc 'source /opt/ros/jazzy/setup.bash
source /ros2_ws/install/setup.bash
ros2 node list'
~~~

## 7. Source ROS Environment

Container:

~~~bash
source /opt/ros/jazzy/setup.bash
source /ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
~~~

The first two source commands are already applied by /entrypoint.sh; source
them explicitly in diagnostic shells for reproducibility.

## 8. Check ROS Nodes

Container:

~~~bash
ros2 node list
~~~

Expected production baseline:

~~~text
/phase4_bridge
/robot_state_publisher
~~~

During a deliberate SLAM smoke test, /slam_toolbox, /map_saver, and
/lifecycle_manager_slam are also expected. They are not part of the default
production simulation launch.

## 9. Check ROS Topics

Container:

~~~bash
ros2 topic list -t
~~~

The production baseline must include /clock, /cmd_vel, /odom, /tf,
/tf_static, /scan, /imu, /camera/image_raw, and /camera/camera_info.

## 10. Check Robot Motion Topics

Container:

~~~bash
ros2 topic info /cmd_vel --verbose
ros2 topic info /odom --verbose
ros2 topic info /tf --verbose
ros2 topic info /tf_static --verbose
ros2 topic echo /odom --once
~~~

Expected frames are odom and base_footprint. phase4_bridge owns the dynamic
odometry TF; robot_state_publisher owns the fixed robot TF tree.

## 11. Check Sensors

Container:

~~~bash
ros2 topic info /scan --verbose
ros2 topic echo /scan --once
ros2 topic info /imu --verbose
ros2 topic echo /imu --once
ros2 topic info /camera/image_raw --verbose
ros2 topic echo /camera/image_raw --once
ros2 topic info /camera/camera_info --verbose
ros2 topic echo /camera/camera_info --once
~~~

The LiDAR frame is base_scan. The camera-info frame is
camera_rgb_optical_frame and the current image is 640x480.

## 12. Check Topic Rates

Container; stop each command with Ctrl-C:

~~~bash
ros2 topic hz /scan
ros2 topic hz /imu
ros2 topic hz /camera/image_raw
ros2 topic hz /odom
~~~

Expected approximate rates from the Phase 5A runtime are /scan 9–10 Hz,
/imu about 95–100 Hz, /camera/image_raw about 10–15 Hz under host load, and
/odom about 28–30 Hz. A first discovery warning can occur before samples
arrive; wait for the rate samples.

For simulation time:

~~~bash
ros2 topic hz /clock
ros2 topic echo /clock --once
~~~

## 13. Inspect TF

Container; each command can be stopped with Ctrl-C:

~~~bash
ros2 run tf2_ros tf2_echo odom base_footprint
ros2 run tf2_ros tf2_echo base_footprint base_link
ros2 run tf2_ros tf2_echo base_link base_scan
ros2 run tf2_ros tf2_echo base_link imu_link
ros2 run tf2_ros tf2_echo base_link camera_link
ros2 run tf2_ros tf2_echo camera_link camera_rgb_frame
ros2 run tf2_ros tf2_echo camera_rgb_frame camera_rgb_optical_frame
~~~

Generate a graph snapshot:

~~~bash
ros2 run tf2_tools view_frames
~~~

The pre-SLAM graph is odom → base_footprint → base_link, with sensor fixed
children. Do not add a static map → odom; SLAM Toolbox must own that edge.

## 14. Manual Robot Movement

Container; these are bounded commands. The last command in every sequence is
an explicit stop.

Move forward slowly for approximately two seconds:

~~~bash
ros2 topic pub --rate 10 --times 20 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.05}, angular: {z: 0.0}}"
ros2 topic pub --rate 10 --times 5 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.0}}"
~~~

Rotate slowly for approximately two seconds:

~~~bash
ros2 topic pub --rate 10 --times 20 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.2}}"
ros2 topic pub --rate 10 --times 5 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.0}}"
~~~

## 15. Emergency Command Stop

Container; repeat a few zero messages so the bridge receives the stop:

~~~bash
ros2 topic pub --rate 10 --times 5 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
~~~

## 16. Gazebo Physical Pose

Container after sourcing Jazzy; this is independent of ROS /odom:

~~~bash
gz topic -e -n 1 --json-output \
  -t /world/amr_world/dynamic_pose/info
~~~

For a short live sample:

~~~bash
timeout 5 gz topic -e --json-output \
  -t /world/amr_world/dynamic_pose/info
~~~

Use the amr_robot pose from this Gazebo topic as physical ground truth. Do not
use /odom as an independent ground-truth source.

## 17. SLAM Commands

The repository already contains a working, limited SLAM launch. Container:

~~~bash
ros2 launch amr_simulation slam.launch.py use_sim_time:=true
~~~

This starts SLAM Toolbox and the map saver. It is a mapping runtime command for
Phase 5B validation; Phase 5A only smoke-tested startup, /map, and map → odom.
Prerequisites: the production `amr-sim` service is healthy and no other SLAM
Toolbox instance is running. Do not run it concurrently with another SLAM
instance.

Expected result: `/slam_toolbox`, `/map_saver`, and
`/lifecycle_manager_slam` appear; `/map` is published with frame `map` and
the configured 0.05 m/cell resolution. Stop it with Ctrl-C in the shell that
owns the launch process, then verify no `/slam_toolbox` node remains.

The default amr-sim Compose command intentionally starts simulation only.

## 18. Save Map

After a real mapping run, with `slam.launch.py` active, use the authoritative
map saver CLI from the container:

~~~bash
ros2 run nav2_map_server map_saver_cli -f /maps/amr_map
~~~

Expected host files are maps/amr_map.yaml and maps/amr_map.pgm. The current
SLAM launch exposes `/map_saver/save_map` with type `nav2_msgs/srv/SaveMap`.
The active Jazzy SLAM Toolbox also exposes `/slam_toolbox/save_map` with type
`slam_toolbox/srv/SaveMap`, which matches the existing Web UI source contract.
The CLI above remains the authoritative operator path for Phase 5B because it
was the host-persistence path verified in the acceptance run.

Expected result: the command exits `0`, reports `Map saved successfully`, and
the host bind mount contains both files. The CLI exits after saving.

## 19. Map Files

The current Compose architecture mounts:

~~~text
host:      /home/deden/Documents/my-project/ros2-software-amr/maps
container: /maps
~~~

Both amr-sim and amr-backend use this bind mount. /maps is therefore usable and
persistent for the local Docker workflow. Do not add NFS or a multi-PC map
service in this phase.

## 20. Stop Simulation

Host; stops only the simulator service and leaves other Compose services alone:

~~~bash
docker compose stop amr-sim
~~~

For a foreground bash scripts/docker_run.sh up, press Ctrl-C first.

## 21. Phase 5B Verified Mapping Workflow

The following sequence was run successfully on 2026-09-20. It is intentionally
headless and does not start Nav2 planners, controllers, AMCL, docking, or the
Web UI.

### 21.1 Start and check mapping

Host prerequisite: repository root and Docker are available.

~~~bash
docker compose up -d amr-sim
docker compose exec -T amr-sim bash -lc \
  'source /opt/ros/jazzy/setup.bash &&
   source /ros2_ws/install/setup.bash &&
   export ROS_DOMAIN_ID=42 &&
   ros2 node list --spin-time 3'
~~~

Expected result: `/phase4_bridge` and `/robot_state_publisher` are present
before SLAM. Start SLAM in a second container shell:

~~~bash
docker compose exec amr-sim bash --rcfile /entrypoint.sh
source /opt/ros/jazzy/setup.bash
source /ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=42
ros2 launch amr_simulation slam.launch.py use_sim_time:=true
~~~

Expected result: `/slam_toolbox`, `/map_saver`, and
`/lifecycle_manager_slam` appear. Stop this launch with Ctrl-C after mapping.

### 21.2 Check mapping health

Container prerequisite: the SLAM launch is active.

~~~bash
ros2 topic info /map --verbose
ros2 topic echo /map --once
ros2 run tf2_ros tf2_echo map odom
ros2 run tf2_ros tf2_echo map base_footprint
ros2 topic hz /scan
ros2 topic hz /odom
~~~

Expected result: `/map` is `nav_msgs/msg/OccupancyGrid`, frame is `map`,
resolution is 0.05, scan and odometry are active, and `map → odom` resolves.
Stop rate/TF commands with Ctrl-C.

### 21.3 Quick Mapping Demo

Container prerequisite: SLAM is active and the robot has clear space. Use
bounded segments and send the zero command after every movement. The Phase 5B
exploration used this same pattern at 0.15 m/s and included forward motion,
90-degree turns, a perimeter loop, and a return-near-start segment.

~~~bash
# Forward, approximately 1.5 m; then stop.
ros2 topic pub --rate 10 --times 100 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.15}, angular: {z: 0.0}}"
ros2 topic pub --rate 10 --times 5 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"

# Turn approximately 90 degrees; then stop.
ros2 topic pub --rate 10 --times 79 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.2}}"
ros2 topic pub --rate 10 --times 5 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
~~~

Repeat short movement/turn/stop segments to cover corridors, walls, corners,
open areas, obstacles, and a return near an already mapped area. Never leave an
unbounded `/cmd_vel` publisher running. Emergency stop:

~~~bash
ros2 topic pub --rate 10 --times 5 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
~~~

### 21.4 Save and verify host files

Container prerequisite: an acceptable `/map` is visible and SLAM remains
active.

~~~bash
ros2 run nav2_map_server map_saver_cli -f /maps/amr_map
~~~

Expected result: `Map saved successfully`, followed on the host by:

~~~bash
stat maps/amr_map.yaml maps/amr_map.pgm
sed -n '1,20p' maps/amr_map.yaml
file maps/amr_map.pgm
~~~

Expected host files: `maps/amr_map.yaml` and `maps/amr_map.pgm`; the YAML image
reference resolves to the PGM, dimensions match `/map`, and the PGM is a
nonblank `P5` image. The CLI exits by itself.

### 21.5 Stop SLAM and reload the saved map

Container prerequisite: save completed. Stop the SLAM launch with Ctrl-C and
verify `/slam_toolbox` and `/map_saver` are gone before starting reload.

Start only the Nav2 map server, with no lifecycle manager or full Nav2 stack:

~~~bash
docker compose exec -d amr-sim bash -lc \
  'source /opt/ros/jazzy/setup.bash &&
   source /ros2_ws/install/setup.bash &&
   export ROS_DOMAIN_ID=42 &&
   exec ros2 run nav2_map_server map_server
     --ros-args -p yaml_filename:=/maps/amr_map.yaml -p use_sim_time:=true'
~~~

Configure and activate it from a second container shell:

~~~bash
ros2 service call /map_server/change_state lifecycle_msgs/srv/ChangeState \
  "{transition: {id: 1}}"
ros2 service call /map_server/change_state lifecycle_msgs/srv/ChangeState \
  "{transition: {id: 3}}"
ros2 topic echo /map --once
~~~

Expected result: `/map_server` reaches `active`, publishes `/map` with frame
`map`, preserves 0.05 m/cell and the saved dimensions, and publishes the same
occupied/free/unknown cell populations. Stop the standalone server:

~~~bash
ros2 service call /map_server/change_state lifecycle_msgs/srv/ChangeState \
  "{transition: {id: 4}}"
ros2 service call /map_server/change_state lifecycle_msgs/srv/ChangeState \
  "{transition: {id: 2}}"
~~~

Then send SIGINT to the `map_server` process or press Ctrl-C if it was started
interactively. Verify only the production simulator nodes remain. Do not start
AMCL, planner/controller servers, or `nav2_bringup` for this reload check.

## 22. Cleanup Diagnostic Containers

The Phase 5A build check used a disposable Compose container with --rm. For an
explicit, scoped cleanup of a stopped simulator container:

~~~bash
docker compose rm -f amr-sim
~~~

Only run this after docker compose stop amr-sim and only when you intend to
recreate it with docker compose up. Do not use docker system prune -a.

## 23. Troubleshooting

### Container not running

Host:

~~~bash
docker compose ps -a
docker compose logs --tail=120 amr-sim
docker compose up -d amr-sim
~~~

If the log reports a missing installed model/Xacro file, rebuild the image:

~~~bash
docker compose build amr-sim
docker compose up -d amr-sim
~~~

### /clock missing

Container:

~~~bash
ros2 topic info /clock --verbose
ros2 topic echo /clock --once
~~~

Confirm the production phase4_bridge is running and that all mapping nodes use
use_sim_time:=true. A compatible /clock subscriber may need best-effort QoS
during early DDS discovery.

### /scan missing

Container:

~~~bash
ros2 topic info /scan --verbose
docker compose logs --tail=120 amr-sim
~~~

Confirm the bridge and the Gazebo production model are running. Do not start a
second sensor bridge.

### /odom missing

Container:

~~~bash
ros2 topic info /odom --verbose
ros2 topic echo /odom --once
~~~

Confirm the model spawned and phase4_bridge owns the production odometry bridge.
Send a bounded command only after checking the robot is safe to move.

### TF missing

Container:

~~~bash
ros2 topic info /tf --verbose
ros2 topic info /tf_static --verbose
ros2 run tf2_tools view_frames
~~~

Expected owners are phase4_bridge for odom → base_footprint and
robot_state_publisher for fixed body/sensor transforms. Do not repair the tree
with an ad-hoc static map → odom publisher.

### ROS_DOMAIN_ID mismatch

Host/container:

~~~bash
echo "$ROS_DOMAIN_ID"
docker compose exec -T amr-sim env | grep '^ROS_DOMAIN_ID='
~~~

The Compose value is 42. Host-side ROS tools must use the same domain if they
are used.

### Gazebo not starting

Host:

~~~bash
docker compose logs --tail=160 amr-sim
docker compose ps -a
~~~

Use headless mode first. Check that the image was built from the current source
and that /dev/dri and the privileged Docker runtime are available.

### GUI unavailable

Use headless mode. For GUI, verify DISPLAY, X11 socket access, and host X11
authorization before retrying the GUI command. GUI failure does not imply the
headless production simulator is unavailable.

### Permission errors

Use the configured Docker group and repository ownership. Do not add sudo
python, sudo pip, or sudo npm to the project workflow. If Docker itself
requires elevated host permissions, resolve that at the Docker/runtime level
rather than creating root-owned project artifacts.
