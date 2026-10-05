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
#   ./run_agent_gprp.sh [--kiosk] <robot_id> <backend_url> [ros_ws]
#
# --kiosk also starts the screen on the robot (kiosk/kiosk_app.py) next to the
# agent, and stops it when the agent stops. It needs a display (the robot's
# desktop session, or a compositor such as cage) and PySide6.
#
# Example:
#   ./run_agent_gprp.sh --kiosk 7fc87960-8c98-4d98-8a83-a4401d6bef0a http://192.168.2.84:3002
#
# Environment (optional):
#   AMR_CONFIRM_TIMEOUT  seconds a `confirm` stop waits before driving on (120)
#   AMR_KIOSK_NAME       name on the kiosk's status bar (AMR)
#   AMR_KIOSK_PIN        staff PIN on the kiosk (1234 — change it)
#   AMR_KIOSK_ARGS       extra kiosk arguments, e.g. "--lang en --estop-topic /estop"
#
set -euo pipefail

KIOSK=0
ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "--kiosk" ]]; then KIOSK=1; else ARGS+=("$arg"); fi
done
set -- "${ARGS[@]+"${ARGS[@]}"}"

ROBOT_ID="${1:-}"
BACKEND_URL="${2:-}"
ROS_WS="${3:-$HOME/ros2_gprp_amr_ws}"

if [[ -z "$ROBOT_ID" || -z "$BACKEND_URL" ]]; then
    echo "usage: $0 [--kiosk] <robot_id> <backend_url> [ros_ws]" >&2
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

# The kiosk is its own process, on purpose: a screen that hangs or crashes must
# not take the robot's missions with it, and it can be restarted on its own.
KIOSK_PID=""
if [[ "$KIOSK" == 1 ]]; then
    if python3 -c 'import PySide6' 2>/dev/null; then
        # shellcheck disable=SC2086
        python3 "$HERE/kiosk/kiosk_app.py" ${AMR_KIOSK_ARGS:-} &
        KIOSK_PID=$!
        echo "kiosk started (pid $KIOSK_PID)"
    else
        echo "PySide6 is not installed; starting without the kiosk (pip install PySide6)" >&2
    fi
fi

# A double parameter: ROS refuses "90" for it, so it always carries a decimal.
CONFIRM_TIMEOUT="${AMR_CONFIRM_TIMEOUT:-120}"
[[ "$CONFIRM_TIMEOUT" == *.* ]] || CONFIRM_TIMEOUT="$CONFIRM_TIMEOUT.0"

stop_kiosk() {
    if [[ -n "$KIOSK_PID" ]]; then kill "$KIOSK_PID" 2>/dev/null || true; fi
}
trap stop_kiosk EXIT

python3 "$HERE/robot_agent_node.py" --ros-args \
    -p managed_mode:=true \
    -p use_sim_time_arg:=true \
    -p "backend_url:=$BACKEND_URL" \
    -p "robot_id:=$ROBOT_ID" \
    -p "map_cache_dir:=$HOME/map_cache" \
    -p "state_dir:=$HERE/state" \
    -p "zone_mask_script:=$HERE/zone_mask_server.py" \
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
    -p mission_via:=nav \
    -p "confirm_timeout:=$CONFIRM_TIMEOUT"
