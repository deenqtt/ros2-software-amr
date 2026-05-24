"""
Launch Navigation2 stack for the AMR.

Usage:
  ros2 launch amr_navigation navigation.launch.py map:=/maps/amr_map.yaml
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

NAV2_BRINGUP_DIR = get_package_share_directory('nav2_bringup')
AMR_NAV_DIR = get_package_share_directory('amr_navigation')

PARAMS_FILE = os.path.join(AMR_NAV_DIR, 'config', 'nav2_params.yaml')
BRINGUP_LAUNCH = os.path.join(NAV2_BRINGUP_DIR, 'launch', 'bringup_launch.py')


def generate_launch_description():
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true'
    )
    declare_map = DeclareLaunchArgument(
        'map',
        default_value='',
        description='Full path to map yaml file',
    )

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(BRINGUP_LAUNCH),
        launch_arguments={
            'map': LaunchConfiguration('map'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'params_file': PARAMS_FILE,
        }.items(),
    )

    keepout_mask_server = Node(
        package='amr_navigation',
        executable='keepout_mask_server.py',
        name='keepout_mask_server',
        output='screen',
        parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}],
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_map,
        nav2,
        keepout_mask_server,
    ])
