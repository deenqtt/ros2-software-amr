#!/usr/bin/env bash
# Build the AMR ROS2 workspace with colcon.
#
# Usage: bash scripts/build_ws.sh [--clean]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_DIR="$(dirname "$SCRIPT_DIR")/ros2_ws"

GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${GREEN}[BUILD]${NC} $*"; }

if [[ "${1:-}" == "--clean" ]]; then
  info "Cleaning build artifacts..."
  rm -rf "$WS_DIR/build" "$WS_DIR/install" "$WS_DIR/log"
fi

# Source ROS 2 Jazzy
if [[ -f /opt/ros/jazzy/setup.bash ]]; then
  source /opt/ros/jazzy/setup.bash
else
  echo "ERROR: /opt/ros/jazzy/setup.bash not found. Use the Jazzy Docker foundation first."
  exit 1
fi

# Source opennav_docking if built
[[ -f /tmp/opennav_ws/install/setup.bash ]] && source /tmp/opennav_ws/install/setup.bash

info "Building workspace: $WS_DIR"
cd "$WS_DIR"

# Install dependencies
rosdep update --rosdistro jazzy 2>/dev/null || true
rosdep install --from-paths src --ignore-src -y --rosdistro jazzy

colcon build \
  --symlink-install \
  --cmake-args -DCMAKE_BUILD_TYPE=Release \
  --event-handlers console_cohesion+

info "Build complete!"
info "Source the workspace:"
info "  source $WS_DIR/install/setup.bash"
