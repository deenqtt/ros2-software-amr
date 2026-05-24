"""
Launch SLAM Toolbox for online mapping.

Usage:
  ros2 launch amr_simulation slam.launch.py
  ros2 launch amr_simulation slam.launch.py use_sim_time:=true slam_params_file:=/path/to/params.yaml

After mapping, save the map:
  ros2 run nav2_map_server map_saver_cli -f ~/maps/amr_map
"""

import os

from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_slam_toolbox = FindPackageShare("slam_toolbox")
    pkg_amr_simulation = FindPackageShare("amr_simulation")

    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time",
        default_value="true",
        description="Use simulation clock",
    )
    declare_slam_params = DeclareLaunchArgument(
        "slam_params_file",
        default_value=PathJoinSubstitution(
            [pkg_amr_simulation, "config", "slam_params.yaml"]
        ),
        description="Path to slam_toolbox parameters file",
    )

    slam_toolbox = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [pkg_slam_toolbox, "launch", "online_async_launch.py"]
            )
        ),
        launch_arguments={
            "use_sim_time": LaunchConfiguration("use_sim_time"),
            "slam_params_file": LaunchConfiguration("slam_params_file"),
        }.items(),
    )

    map_saver_server = Node(
        package='nav2_map_server',
        executable='map_saver_server',
        name='map_saver',
        output='screen',
        parameters=[{
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'save_map_timeout': 5.0,
            'free_thresh_default': 0.25,
            'occupied_thresh_default': 0.65,
        }],
    )

    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_slam',
        output='screen',
        parameters=[{
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'autostart': True,
            'node_names': ['map_saver'],
        }],
    )

    return LaunchDescription(
        [
            declare_use_sim_time,
            declare_slam_params,
            slam_toolbox,
            map_saver_server,
            lifecycle_manager,
        ]
    )
