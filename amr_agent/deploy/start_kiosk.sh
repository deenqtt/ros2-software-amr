#!/usr/bin/env bash
#
# Started by amr-kiosk.service inside cage (a full-screen Wayland compositor
# with no desktop around it). Sources ROS so the kiosk can import rclpy, then
# runs it from the venv install_robot.sh made.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

set +u
# shellcheck disable=SC1090
source "/opt/ros/${AMR_ROS_DISTRO:-jazzy}/setup.bash"
if [[ -f "${AMR_ROS_WS:-}/install/setup.bash" ]]; then
    # shellcheck disable=SC1091
    source "$AMR_ROS_WS/install/setup.bash"
fi
set -u

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"

# shellcheck disable=SC2086
exec "$HERE/.venv/bin/python" "$HERE/kiosk/kiosk_app.py" ${AMR_KIOSK_ARGS:-}
