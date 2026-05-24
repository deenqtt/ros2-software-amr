#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# Phase 0 → 1: Clean install ROS2 Humble + all AMR packages
#
# Run as: bash scripts/install_ros2.sh
# Tested on: Ubuntu 22.04 (Jammy)
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
section() { echo -e "\n${GREEN}══════════════════════════════════════${NC}"; echo -e "${GREEN}  $*${NC}"; echo -e "${GREEN}══════════════════════════════════════${NC}"; }

# ── Phase 0: Cleanup ────────────────────────────────────────────────────────

section "Phase 0 — Cleanup existing ROS2 / Gazebo"

warn "This will remove all existing ROS2 Humble and Gazebo packages."
read -rp "Continue? [y/N] " confirm
[[ "${confirm,,}" != "y" ]] && { echo "Aborted."; exit 0; }

info "Removing ROS2 Humble packages..."
sudo apt remove -y ~nros-humble* 2>/dev/null || true
sudo apt autoremove -y

info "Removing Gazebo packages..."
sudo apt remove -y ~ngazebo* ~nignition* ~nlibgz* 2>/dev/null || true
sudo apt autoremove -y

info "Cleaning up ROS directories..."
sudo rm -rf /opt/ros/humble || true
rm -rf ~/.ros || true

info "Removing ROS env from shell configs..."
for f in ~/.bashrc ~/.zshrc ~/.bash_profile; do
  if [[ -f "$f" ]]; then
    # Remove lines containing ROS source commands
    sed -i '/source.*ros.*setup/d' "$f"
    sed -i '/source.*ros2.*setup/d' "$f"
    sed -i '/TURTLEBOT3_MODEL/d' "$f"
    info "  Cleaned $f"
  fi
done

info "Phase 0 complete. Verifying..."
if command -v ros2 &>/dev/null; then
  warn "ros2 still found at $(which ros2) — manual removal may be needed."
else
  info "  'ros2' command not found — clean!"
fi

# ── Phase 1: ROS2 Humble install ─────────────────────────────────────────────

section "Phase 1 — Install ROS2 Humble"

info "Setting up ROS2 apt repository..."
sudo apt update && sudo apt install -y software-properties-common curl
sudo add-apt-repository -y universe
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  | sudo gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

info "Installing ROS2 Humble Desktop..."
sudo apt update
sudo apt install -y ros-humble-desktop

info "Installing AMR-specific ROS2 packages..."
sudo apt install -y \
  ros-humble-turtlebot3 \
  ros-humble-turtlebot3-gazebo \
  ros-humble-turtlebot3-simulations \
  ros-humble-slam-toolbox \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-foxglove-bridge \
  ros-humble-web-video-server \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-gazebo-ros2-control \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-vcstool

info "Installing opennav_docking (from source — not yet in apt)..."
mkdir -p /tmp/opennav_ws/src
cd /tmp/opennav_ws/src
git clone https://github.com/open-navigation/opennav_docking.git || warn "git clone failed — skip opennav_docking"
if [[ -d opennav_docking ]]; then
  cd /tmp/opennav_ws
  source /opt/ros/humble/setup.bash
  rosdep update
  rosdep install --from-paths src -i -y
  colcon build --symlink-install
  info "opennav_docking built successfully"
  info "  Source /tmp/opennav_ws/install/setup.bash in your shell or add to ~/.bashrc"
fi

# ── Shell config ─────────────────────────────────────────────────────────────

section "Setting up shell environment"

SHELL_RC="$HOME/.bashrc"
[[ -n "${ZSH_VERSION:-}" ]] && SHELL_RC="$HOME/.zshrc"

cat >> "$SHELL_RC" << 'SHELLEOF'

# ── ROS2 Humble ──────────────────────────────────────────────────────────────
source /opt/ros/humble/setup.bash

# opennav_docking (if built from source)
[[ -f /tmp/opennav_ws/install/setup.bash ]] && source /tmp/opennav_ws/install/setup.bash

# TurtleBot3 model
export TURTLEBOT3_MODEL=waffle_pi

# Gazebo model path for TurtleBot3
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/humble/share/turtlebot3_gazebo/models
SHELLEOF

info "Shell config updated: $SHELL_RC"
info "Run 'source $SHELL_RC' or open a new terminal."

section "Installation complete!"
info "Next: Build the AMR workspace"
info "  cd ros-software/ros2_ws"
info "  colcon build --symlink-install"
info "  source install/setup.bash"
info ""
info "Then launch the simulation:"
info "  ros2 launch amr_bringup bringup.launch.py"
