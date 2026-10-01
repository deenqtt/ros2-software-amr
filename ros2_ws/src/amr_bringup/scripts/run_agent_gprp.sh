#!/usr/bin/env bash
#
# Run the robot agent against the gprp AMR stack (amr_description launch files),
# rather than the simulation stack in this repository.
#
# The agent is a plain script, not a colcon package, so deploying it to a robot
# is copying this directory and running this file. Both Python files must stay
# next to this script: Python puts the *script's* directory on sys.path, which
# is how robot_agent_node.py finds backend_client.py.
#
# Usage:
#   ./run_agent_gprp.sh <robot_id> <backend_url> [ros_ws]
#
# Example:
#   ./run_agent_gprp.sh 7fc87960-8c98-4d98-8a83-a4401d6bef0a http://192.168.2.84:3002
#
set -euo pipefail

ROBOT_ID="${1:-}"
BACKEND_URL="${2:-}"
ROS_WS="${3:-$HOME/ros2_gprp_amr_ws}"

if [[ -z "$ROBOT_ID" || -z "$BACKEND_URL" ]]; then
    echo "usage: $0 <robot_id> <backend_url> [ros_ws]" >&2
    echo "  e.g. $0 7fc87960-...-1bef0a http://192.168.2.84:3002" >&2
    exit 64
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -u is lifted across the sourcing and put back afterwards. ROS's own setup
# scripts are not written for it — /opt/ros/jazzy/setup.bash line 8 tests
# $AMENT_TRACE_SETUP_FILES with no default, so `set -u` aborts the script before
# it has sourced anything, with an error that names ament and looks like a broken
# ROS install rather than our own shell options.
set +u
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
# custom_interfaces lives here, and the agent will not import without it.
# shellcheck disable=SC1091
source "$ROS_WS/install/setup.bash"
set -u

# Fail here rather than inside rclpy. A missing workspace surfaces as an
# ImportError forty lines into a traceback, which reads like a broken agent.
python3 -c 'import custom_interfaces.srv' 2>/dev/null || {
    echo "custom_interfaces not importable — is $ROS_WS built?" >&2
    exit 69
}

exec python3 "$HERE/robot_agent_node.py" --ros-args \
    -p managed_mode:=true \
    -p use_sim_time_arg:=true \
    -p "backend_url:=$BACKEND_URL" \
    -p "robot_id:=$ROBOT_ID" \
    -p "map_cache_dir:=$HOME/map_cache" \
    -p "state_dir:=$HERE/state" \
    -p slam_launch_package:=amr_description \
    -p slam_launch_file:=amr_mapping_sim_launch.py \
    -p nav_launch_package:=amr_description \
    -p nav_launch_file:=amr_navigation_sim_launch.py \
    -p extra_launch_args:="launch_master_control:=false launch_websocket:=false launch_rviz:=false" \
    -p slam_extra_launch_args:="launch_scan_filter:=true scan_topic:=/scan_filtered" \
    -p map_save_via:=cli \
    -p map_save_timeout:=20.0 \
    -p "station_file:=$HOME/amr_agent/station_data.yaml" \
    -p dock_reload_service:=/docking_server/reload_database \
    -p dock_plugin:=simple_charging_dock \
    -p mission_via:=nav
