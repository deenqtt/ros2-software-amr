"""Disposable Phase 4H minimal differential-drive physics launch."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _launch_gazebo(context):
    world = LaunchConfiguration("world").perform(context)
    gui = LaunchConfiguration("gui").perform(context).lower() == "true"
    headless = LaunchConfiguration("headless").perform(context).lower() == "true"
    server_only = headless or not gui
    gz_args = ("-s -r " if server_only else "-r ") + world
    gz_launch = PathJoinSubstitution([
        FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"
    ])
    return [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gz_launch),
        launch_arguments={"gz_args": gz_args, "gz_version": "8", "on_exit_shutdown": "true"}.items(),
    )]


def generate_launch_description():
    package = FindPackageShare("amr_simulation")
    world = PathJoinSubstitution([package, "worlds", "amr_physics_test.sdf"])
    model = PathJoinSubstitution([package, "models", "amr_robot_physics_test", "model.sdf"])
    bridge = PathJoinSubstitution([package, "config", "bridge_phase4h.yaml"])
    return LaunchDescription([
        DeclareLaunchArgument("world", default_value=world),
        DeclareLaunchArgument("gui", default_value="false"),
        DeclareLaunchArgument("headless", default_value="true"),
        OpaqueFunction(function=_launch_gazebo),
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="phase4h_bridge",
            output="screen",
            parameters=[{"config_file": bridge}],
        ),
        TimerAction(period=2.0, actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                FindPackageShare("ros_gz_sim"), "launch", "gz_spawn_model.launch.py"
            ])),
            launch_arguments={
                "world": "amr_physics_test",
                "file": model,
                "entity_name": "amr_robot_physics_test",
                "allow_renaming": "false",
                "x": "0.0", "y": "0.0", "z": "0.0",
                "R": "0.0", "P": "0.0", "Y": "0.0",
            }.items(),
        )]),
    ])
