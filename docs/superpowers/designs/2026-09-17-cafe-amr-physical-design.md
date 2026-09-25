# Cafe Service AMR Physical Design

Date: 2026-09-17  
Status: approved for Phase 4 implementation by the project owner.

## Product intent

The model is a generic cafe/restaurant service AMR, not a replica of a
commercial platform. It carries three future payload trays, navigates a cafe
footprint, and leaves room for later docking and perception work.

## Physical envelope

| Parameter | Selected value | Rationale |
| --- | ---: | --- |
| Overall width | 0.54 m | Leaves a compact footprint while providing tray width and wheel clearance |
| Overall length | 0.62 m | Stable fore/aft support and usable tray depth |
| Overall height | 1.22 m | Three visible serving levels and elevated forward camera |
| Ground clearance | 0.045 m | Clears small floor irregularities without raising the center of mass |
| Drive wheel radius | 0.09 m | More realistic service-robot wheel scale than the Phase 3 TurtleBot asset |
| Drive wheel separation | 0.42 m | Gives controlled turning while remaining inside the 0.54 m envelope |
| Tray size | 0.46 m × 0.42 m | Fits inside the body envelope with a visible serving lip |
| Tray heights | 0.48, 0.76, 1.04 m | Three usable levels with 0.28 m vertical separation |

The dimensions are engineering design values for this project, not claims about
any named commercial robot.

## Structure and dynamics

The low chassis contains the majority of mass: 18 kg chassis/battery, 1.2 kg
per tray, 0.8 kg vertical supports, 0.35 kg per drive wheel, and 0.15 kg per
primary caster. The implemented SDF also includes a 0.35 kg top cap, 0.4 kg
of low-mass anti-tip supports, and 0.55 kg of sensor housings, for an explicit
empty-model mass of 24.7 kg. Payload mass is not simulated in Phase 4.

The chassis center of mass is kept near (0, 0, 0.18) in the robot body
coordinate system. Each visual component has a simple collision counterpart,
and tray/support collisions are boxes or cylinders. Visual meshes are not used
as the primary collision geometry.

Drive joints remain wheel_left_joint and wheel_right_joint. Two passive rear
caster assemblies support the chassis without owning dynamic odometry.

## Sensor placement

- LiDAR: base_scan, centered above the chassis at z=0.25 m, horizontal
  visibility around the robot.
- IMU: imu_link, near the chassis center at z=0.25 m.
- Main camera: camera_link at the front of the upper body, z=0.98 m,
  forward-facing.
- Camera frames remain
  camera_link → camera_rgb_frame → camera_rgb_optical_frame; the optical
  frame uses the standard ROS optical-axis rotation.

The existing application contract describes a rear camera because the old
Classic URDF mounted it at the rear. Phase 4 intentionally changes only the
physical orientation of the main camera. Legacy ArUco/docking behavior is not
assumed compatible; a separate rear docking camera remains a future extension
point and is not implemented now.

## Representation ownership

The SDF is authoritative for Gazebo geometry, collisions, inertials, joints,
motion systems, and sensors. The synchronized Xacro is authoritative only for
the ROS structural description and fixed TF chain. robot_state_publisher must
not publish the dynamic odom → base_footprint transform owned by the Gazebo
DiffDrive system. The primary drive wheels use standard left/right placement;
low-friction primary ball casters and raised corner anti-tip supports are
included to keep the tall tray stack from snagging or tipping in the simple
simulation world.

## Reference research

- Gazebo Sim's official DiffDrive example configures named wheel joints, wheel
  separation/radius, velocity/acceleration limits, and odometry frequency:
  https://github.com/gazebosim/gz-sim/blob/main/examples/worlds/diff_drive.sdf
- The official Gazebo migration guidance maps Classic ray sensors to gpu_lidar,
  adds gz_frame_id, and uses native camera/IMU systems:
  https://github.com/gazebosim/docs/blob/master/migrating_gazebo_classic_ros2_packages.md
- The official ros_gz_bridge README documents YAML bridge entries, direction,
  QoS, camera info, and optical-frame overrides:
  https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md
