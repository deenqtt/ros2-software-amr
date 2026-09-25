"""Launch the Phase 4 Cafe Service AMR runtime.

This launch file intentionally starts only:

* Gazebo Sim / Harmonic server (GUI optional);
* the Gazebo-to-ROS bridge for clock, motion, odometry, and core sensors;
* the Cafe Service AMR SDF model;
* the fixed structural TF description.

Nav2, SLAM, docking, and application nodes remain later phase work. The legacy
``amr_robot.urdf`` and ``amr_world.world`` are retained for comparison/rollback
and are not used by this active path.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _launch_gazebo(context):
    """Select server-only or GUI mode using the supported ros_gz launch file."""
    world = LaunchConfiguration("world").perform(context)
    gui = LaunchConfiguration("gui").perform(context).lower() == "true"
    headless = LaunchConfiguration("headless").perform(context).lower() == "true"

    # Headless wins if both flags are true. GUI is opt-in for the resource-aware
    # default and uses the same world/server process with the Gazebo GUI enabled.
    server_only = headless or not gui
    gz_args = ("-s -r " if server_only else "-r ") + world

    gz_launch = PathJoinSubstitution([
        FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"
    ])
    return [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gz_launch),
        launch_arguments={
            "gz_args": gz_args,
            "gz_version": "8",
            "on_exit_shutdown": "true",
        }.items(),
    )]


def generate_launch_description():
    pkg_simulation = FindPackageShare("amr_simulation")
    world_file = PathJoinSubstitution([pkg_simulation, "worlds", "amr_world.sdf"])
    robot_file = PathJoinSubstitution([
        pkg_simulation, "models", "amr_robot_harmonic", "model.sdf"
    ])
    robot_description_file = PathJoinSubstitution([
        pkg_simulation, "urdf", "amr_robot_harmonic.urdf.xacro"
    ])
    bridge_config_file = PathJoinSubstitution([
        pkg_simulation, "config", "bridge_phase4.yaml"
    ])
    declare_world = DeclareLaunchArgument(
        "world", default_value=world_file,
        description="Gazebo Sim SDF world file",
    )
    declare_gui = DeclareLaunchArgument(
        "gui", default_value="false",
        description="Enable Gazebo GUI; false keeps the default lightweight",
    )
    declare_headless = DeclareLaunchArgument(
        "headless", default_value="true",
        description="Run server-only Gazebo; takes precedence over gui",
    )
    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time", default_value="true",
        description="Retained for the later ROS node integration phases",
    )
    declare_robot_model = DeclareLaunchArgument(
        "robot_model", default_value="amr_robot",
        description="Gazebo entity name",
    )
    declare_x_pose = DeclareLaunchArgument("x_pose", default_value="0.0")
    declare_y_pose = DeclareLaunchArgument("y_pose", default_value="0.0")
    declare_z_pose = DeclareLaunchArgument("z_pose", default_value="0.05")

    gazebo = OpaqueFunction(function=_launch_gazebo)

    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="phase4_bridge",
        output="screen",
        parameters=[
            {"config_file": bridge_config_file},
            {"use_sim_time": LaunchConfiguration("use_sim_time")},
            {"qos_overrides./clock.publisher.durability": "transient_local"},
        ],
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[
            {"robot_description": Command([
                FindExecutable(name="xacro"), " ", robot_description_file
            ])},
            {"use_sim_time": LaunchConfiguration("use_sim_time")},
        ],
    )

    spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([
            FindPackageShare("ros_gz_sim"), "launch", "gz_spawn_model.launch.py"
        ])),
        launch_arguments={
            "world": "amr_world",
            "file": robot_file,
            "entity_name": LaunchConfiguration("robot_model"),
            "allow_renaming": "false",
            "x": LaunchConfiguration("x_pose"),
            "y": LaunchConfiguration("y_pose"),
            "z": LaunchConfiguration("z_pose"),
            "R": "0.0",
            "P": "0.0",
            "Y": "0.0",
        }.items(),
    )

    return LaunchDescription([
        declare_world,
        declare_gui,
        declare_headless,
        declare_use_sim_time,
        declare_robot_model,
        declare_x_pose,
        declare_y_pose,
        declare_z_pose,
        gazebo,
        bridge,
        robot_state_publisher,
        TimerAction(period=2.0, actions=[spawn]),
    ])
