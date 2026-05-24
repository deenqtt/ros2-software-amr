"""
Launch TurtleBot3 in Gazebo with the AMR warehouse world.

Usage:
  ros2 launch amr_simulation sim.launch.py
  ros2 launch amr_simulation sim.launch.py use_sim_time:=true
"""

import os

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_amr_simulation = FindPackageShare("amr_simulation")
    pkg_turtlebot3_gazebo = FindPackageShare("turtlebot3_gazebo")
    pkg_turtlebot3_description = FindPackageShare("turtlebot3_description")
    pkg_gazebo_ros = FindPackageShare("gazebo_ros")

    # ── Arguments ─────────────────────────────────────────────────────────────
    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time", default_value="true"
    )
    declare_robot_model = DeclareLaunchArgument(
        "robot_model", default_value="waffle_pi"
    )
    declare_x_pose = DeclareLaunchArgument("x_pose", default_value="0.0")
    declare_y_pose = DeclareLaunchArgument("y_pose", default_value="0.0")

    # ── Environment ────────────────────────────────────────────────────────────
    set_tb3_model = SetEnvironmentVariable(
        "TURTLEBOT3_MODEL", LaunchConfiguration("robot_model")
    )

    # Add custom models path so Gazebo finds aruco_dock model + its textures
    models_dir = PathJoinSubstitution([pkg_amr_simulation, "models"])
    set_gazebo_model_path = SetEnvironmentVariable(
        "GAZEBO_MODEL_PATH",
        [models_dir, ":/opt/ros/humble/share/turtlebot3_gazebo/models"],
    )

    # ── Gazebo ─────────────────────────────────────────────────────────────────
    world_file = PathJoinSubstitution(
        [pkg_amr_simulation, "worlds", "amr_world.world"]
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([pkg_gazebo_ros, "launch", "gazebo.launch.py"])
        ),
        launch_arguments={
            "world": world_file,
            "verbose": "true",
            "gui": "true",
        }.items(),
    )

    # ── robot_state_publisher (publishes TF: base_footprint → base_scan etc.) ─
    # Pakai URDF kustom yang kameranya sudah dipindah ke belakang
    urdf_file = PathJoinSubstitution(
        [pkg_amr_simulation, "urdf", "amr_robot.urdf"]
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[
            {
                "use_sim_time": LaunchConfiguration("use_sim_time"),
                "robot_description": ParameterValue(
                    Command(["xacro ", urdf_file, " namespace:="]),
                    value_type=str
                ),
            }
        ],
    )

    # ── Spawn Robot in Gazebo ─────────────────────────────────────────────────
    # Kita panggil spawn_entity secara langsung agar dia mengambil model
    # dari topik 'robot_description' (yang sudah berisi URDF kustom kita).
    spawn_robot = Node(
        package="gazebo_ros",
        executable="spawn_entity.py",
        name="spawn_entity",
        output="screen",
        arguments=[
            "-entity", LaunchConfiguration("robot_model"),
            "-topic", "robot_description",
            "-x", LaunchConfiguration("x_pose"),
            "-y", LaunchConfiguration("y_pose"),
            "-z", "0.01",
        ],
    )

    return LaunchDescription(
        [
            declare_use_sim_time,
            declare_robot_model,
            declare_x_pose,
            declare_y_pose,
            set_tb3_model,
            set_gazebo_model_path,
            gazebo,
            robot_state_publisher,
            spawn_robot,
        ]
    )
