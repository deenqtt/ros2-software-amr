"""
Master bringup launch — starts the full AMR simulation stack.

Mode SLAM (default — untuk mapping):
  ros2 launch amr_bringup bringup.launch.py
  → Gazebo + SLAM toolbox + Foxglove + web_video_server
  → Gunakan teleop untuk gerakkan robot dan build map
  → Simpan map: ros2 run nav2_map_server map_saver_cli -f /maps/amr_map

Mode Navigation (setelah punya map):
  ros2 launch amr_bringup bringup.launch.py use_slam:=false map:=/maps/amr_map.yaml
  → Gazebo + Nav2 (AMCL + planner + controller) + Foxglove + web_video_server
"""

import os

from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_amr_simulation = FindPackageShare("amr_simulation")
    pkg_amr_navigation = FindPackageShare("amr_navigation")

    # ── Arguments ─────────────────────────────────────────────────────────────
    declare_use_slam = DeclareLaunchArgument(
        "use_slam",
        default_value="true",
        description="true=SLAM mapping mode | false=navigation with pre-built map",
    )
    declare_map = DeclareLaunchArgument(
        "map",
        default_value="",
        description="Path to map yaml (hanya dipakai saat use_slam:=false)",
    )
    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time", default_value="true"
    )
    declare_gui = DeclareLaunchArgument(
        "gui",
        default_value="false",
        description="Enable Gazebo GUI when a local display is available",
    )
    declare_headless = DeclareLaunchArgument(
        "headless",
        default_value="true",
        description="Run Gazebo server-only; takes precedence over gui",
    )
    declare_foxglove_port = DeclareLaunchArgument(
        "foxglove_port", default_value="8765"
    )

    # When true, neither SLAM nor Nav2 is started at boot: the robot_agent
    # owns them and brings up whichever mode is asked for over /robot_mode.
    #
    # Defaults to false so every existing command keeps behaving exactly as it
    # does today. `docker_run.sh slam` and `docker_run.sh nav` are unaffected
    # until they opt in.
    # Where the agent publishes maps and reads its assignment from. Empty by
    # default: a robot with no backend still maps and navigates, it simply
    # publishes nowhere.
    declare_backend_url = DeclareLaunchArgument(
        "backend_url",
        default_value="",
        description="Base URL of the AMR backend, e.g. http://192.168.1.10:3002",
    )
    declare_robot_id = DeclareLaunchArgument(
        "robot_id",
        default_value="",
        description="This robot's id in the backend registry",
    )
    declare_map_cache = DeclareLaunchArgument(
        "map_cache_dir",
        default_value="/maps/cache",
        description="Where downloaded and saved maps live on this robot",
    )

    declare_managed_mode = DeclareLaunchArgument(
        "managed_mode",
        default_value="false",
        description="Let robot_agent own SLAM/Nav2 instead of launching one at boot",
    )

    # ── 1. Gazebo simulation ───────────────────────────────────────────────────
    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([pkg_amr_simulation, "launch", "sim.launch.py"])
        ),
        launch_arguments={
            "use_sim_time": LaunchConfiguration("use_sim_time"),
            "gui": LaunchConfiguration("gui"),
            "headless": LaunchConfiguration("headless"),
        }.items(),
    )

    # ── 2. SLAM toolbox — hanya saat use_slam:=true ───────────────────────────
    slam = TimerAction(
        period=3.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution(
                        [pkg_amr_simulation, "launch", "slam.launch.py"]
                    )
                ),
                # Started at boot only when the agent is not in charge.
                condition=IfCondition(
                    PythonExpression([
                        "'", LaunchConfiguration("use_slam"), "' == 'true' and ",
                        "'", LaunchConfiguration("managed_mode"), "' != 'true'",
                    ])
                ),
                launch_arguments={
                    "use_sim_time": LaunchConfiguration("use_sim_time"),
                }.items(),
            )
        ],
    )

    # ── 3. Navigation2 — hanya saat use_slam:=false ───────────────────────────
    # SLAM mode tidak butuh Nav2. Nav2 dijalankan setelah map sudah ada.
    navigation = TimerAction(
        period=10.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution(
                        [pkg_amr_navigation, "launch", "navigation.launch.py"]
                    )
                ),
                condition=IfCondition(
                    PythonExpression([
                        "'", LaunchConfiguration("use_slam"), "' != 'true' and ",
                        "'", LaunchConfiguration("managed_mode"), "' != 'true'",
                    ])
                ),
                launch_arguments={
                    "use_sim_time": LaunchConfiguration("use_sim_time"),
                    "map": LaunchConfiguration("map"),
                }.items(),
            )
        ],
    )

    # ── 4. rosbridge_websocket (compatible dengan roslibjs) ───────────────────
    foxglove_bridge = Node(
        package="rosbridge_server",
        executable="rosbridge_websocket",
        name="rosbridge_websocket",
        output="screen",
        parameters=[
            {
                "port": 8765,
                "address": "0.0.0.0",
                "use_sim_time": LaunchConfiguration("use_sim_time"),
            }
        ],
    )

    # ── 5. web_video_server ───────────────────────────────────────────────────
    web_video = Node(
        package="web_video_server",
        executable="web_video_server",
        name="web_video_server",
        output="screen",
        parameters=[{"port": 8080}],
    )

    # ── 6. Battery simulator + Docking manager ────────────────────────────────
    # Pakai ExecuteProcess langsung dari source — tidak perlu rebuild image
    from launch.actions import ExecuteProcess
    battery_sim = ExecuteProcess(
        cmd=[
            'python3',
            '/ros2_ws/src/amr_simulation/scripts/battery_sim_node.py',
        ],
        output='screen',
    )

    docking_manager = ExecuteProcess(
        cmd=[
            'python3',
            '/ros2_ws/src/amr_docking/scripts/docking_manager_node.py',
        ],
        output='screen',
    )

    # ArUco detector — starts with sim; only active when camera publishes images
    aruco_detector = ExecuteProcess(
        cmd=[
            'python3',
            '/ros2_ws/src/amr_docking/scripts/aruco_detector_node.py',
        ],
        output='screen',
    )

    # ── 7. Robot agent — owns /robot_mode ────────────────────────────────────
    robot_agent = ExecuteProcess(
        cmd=[
            'python3',
            '/ros2_ws/src/amr_bringup/scripts/robot_agent_node.py',
            '--ros-args',
            '-p', ['managed_mode:=', LaunchConfiguration('managed_mode')],
            '-p', ['use_sim_time_arg:=', LaunchConfiguration('use_sim_time')],
            # `map` declares an empty default, and `-p default_map:=` is not a
            # valid parameter override — rcl refuses to start at all. Substitute
            # a usable path so the agent always has something to fall back on.
            '-p', PythonExpression([
                "'default_map:=' + ('", LaunchConfiguration('map'),
                "' or '/maps/amr_map.yaml')",
            ]),
            # Quoted: an empty value is a valid setting here (no backend), but
            # an empty parameter override is not — rcl refuses to start at all.
            '-p', PythonExpression([
                '"backend_url:=" + repr("', LaunchConfiguration('backend_url'), '")',
            ]),
            '-p', PythonExpression([
                '"robot_id:=" + repr("', LaunchConfiguration('robot_id'), '")',
            ]),
            '-p', ['map_cache_dir:=', LaunchConfiguration('map_cache_dir')],
        ],
        output='screen',
    )

    # ── 8. Mission manager — action server /mission_plan ─────────────────────
    mission_manager = ExecuteProcess(
        cmd=[
            'python3',
            '/ros2_ws/src/amr_navigation/scripts/mission_manager_node.py',
        ],
        output='screen',
    )

    return LaunchDescription(
        [
            declare_use_slam,
            declare_map,
            declare_use_sim_time,
            declare_gui,
            declare_headless,
            declare_foxglove_port,
            declare_managed_mode,
            declare_backend_url,
            declare_robot_id,
            declare_map_cache,
            sim,
            slam,
            navigation,
            foxglove_bridge,
            web_video,
            battery_sim,
            docking_manager,
            aruco_detector,
            robot_agent,
            mission_manager,
        ]
    )
