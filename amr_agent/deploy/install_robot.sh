#!/usr/bin/env bash
#
# Install the robot agent and the kiosk on a robot (Jetson), as two services.
#
# Only those two. The robot's own stack — ROS 2, Nav2, rosbridge, its
# workspace, how the OS boots — belongs to the robot team: this checks that it
# is there and says what is missing, and installs none of it.
#
# Run on the robot, from the copied amr_agent folder, as the robot's normal
# user (it asks for sudo where needed). Safe to run again: everything already
# in place is left alone, and the services are restarted onto the new files.
#
#   ./deploy/install_robot.sh --robot-id <id> --backend http://<server>/backend
#
# Options:
#   --robot-id ID       the id the web UI shows for this robot
#   --backend URL       http://<server>/backend
#   --agent-token TOKEN credential for the backend (web UI: Robot -> Details ->
#                       Agent token). Prompted for if missing; may be left empty
#                       (the backend will then refuse the agent). Visible in
#                       `ps` while this runs: prefer the prompt.
#   --name NAME         name on the kiosk's status bar (default: AMR)
#   --ros-ws PATH       ROS workspace with custom_interfaces
#                       (default: ~/ros2_gprp_amr_ws)
#   --domain N          ROS_DOMAIN_ID (default: 10)
#   --no-kiosk          the agent only (a robot without a screen)
#   --check             only report what is missing; change nothing
#
# Settings end up in /etc/amr/robot.env; later edits go there.
set -euo pipefail

AGENT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${SUDO_USER:-$USER}"
ENV_FILE=/etc/amr/robot.env

ROBOT_ID=""
BACKEND=""
AGENT_TOKEN=""
NAME="AMR"
ROS_WS="$HOME/ros2_gprp_amr_ws"
DOMAIN=10
KIOSK=1
CHECK=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --robot-id) ROBOT_ID="$2"; shift 2 ;;
        --backend) BACKEND="$2"; shift 2 ;;
        --agent-token) AGENT_TOKEN="$2"; shift 2 ;;
        --name) NAME="$2"; shift 2 ;;
        --ros-ws) ROS_WS="$2"; shift 2 ;;
        --domain) DOMAIN="$2"; shift 2 ;;
        --no-kiosk) KIOSK=0; shift ;;
        --check) CHECK=1; shift ;;
        -h|--help) sed -n '2,29p' "$0"; exit 0 ;;
        *) echo "unknown option: $1 (see --help)" >&2; exit 64 ;;
    esac
done

if [[ $EUID -eq 0 && -z "${SUDO_USER:-}" ]]; then
    echo "Run this as the robot's user, not as root; it uses sudo itself." >&2
    exit 1
fi

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
todo() { printf '  \033[33m•\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }

MISSING=0

# ── 1. The robot's stack (checked, never installed) ─────────────────────────
step "1. Robot stack (from the robot team)"
DISTRO="${AMR_ROS_DISTRO:-}"
if [[ -z "$DISTRO" ]]; then
    # The newest installed distro, by directory name order (humble < jazzy).
    DISTRO="$(find /opt/ros -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | tail -1)"
fi
if [[ -z "$DISTRO" || ! -f "/opt/ros/$DISTRO/setup.bash" ]]; then
    fail "No ROS 2 in /opt/ros — the robot stack is not installed yet (robot team)."
    exit 1
fi
ok "ROS 2 $DISTRO"

set +u
# shellcheck disable=SC1090
source "/opt/ros/$DISTRO/setup.bash"
if [[ -f "$ROS_WS/install/setup.bash" ]]; then
    # shellcheck disable=SC1091
    source "$ROS_WS/install/setup.bash"
    ok "workspace $ROS_WS"
else
    fail "workspace $ROS_WS is not built (no install/setup.bash) — pass --ros-ws, or ask the robot team"
    MISSING=1
fi
set -u

# What the agent and kiosk import or call. Part of the robot's stack.
ROS_PKGS=(rclpy std_msgs std_srvs sensor_msgs geometry_msgs nav_msgs action_msgs
          nav2_msgs nav2_map_server custom_interfaces)
for pkg in "${ROS_PKGS[@]}"; do
    if ros2 pkg prefix "$pkg" >/dev/null 2>&1; then
        ok "$pkg"
    else
        fail "$pkg — missing from the robot stack (robot team)"
        MISSING=1
    fi
done

# ── 2. What the agent and kiosk need from the system ────────────────────────
step "2. System packages for the agent and kiosk"
SYS_PKGS=(python3-venv python3-pip alsa-utils espeak-ng)
if [[ $KIOSK == 1 ]]; then
    # cage, and the libraries the PySide6 wheel expects from the system.
    SYS_PKGS+=(cage libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3
               libwayland-client0 libwayland-egl1 libwayland-cursor0)
fi
APT_SYS=()
for pkg in "${SYS_PKGS[@]}"; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
        ok "$pkg"
    else
        todo "$pkg — will install"
        APT_SYS+=("$pkg")
    fi
done

if [[ $MISSING == 1 && $CHECK == 0 ]]; then
    fail "The robot stack is incomplete (✗ above). Nothing was installed."
    exit 1
fi
if [[ ${#APT_SYS[@]} -gt 0 && $CHECK == 0 ]]; then
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends "${APT_SYS[@]}"
fi

# ── 3. Python packages (requirements.txt) ───────────────────────────────────
step "3. Python packages"
VENV="$AGENT/.venv"
SYS_PY="$(command -v python3)"
if [[ -x "$VENV/bin/python" ]] \
    && [[ "$("$VENV/bin/python" -c 'import sys;print(sys.version_info[:2])')" == \
          "$("$SYS_PY" -c 'import sys;print(sys.version_info[:2])')" ]]; then
    ok "venv $VENV"
else
    todo "venv $VENV — will create (sees rclpy from ROS)"
    if [[ $CHECK == 0 ]]; then
        rm -rf "$VENV"
        "$SYS_PY" -m venv --system-site-packages "$VENV"
    fi
fi
if [[ -x "$VENV/bin/python" ]]; then
    # Only what is not satisfied yet; pip says so without downloading anything.
    while IFS= read -r requirement; do
        name="${requirement%%[<>=!~ ]*}"
        if "$VENV/bin/python" - "$requirement" <<'PY' 2>/dev/null
import sys
from importlib.metadata import version
from pip._vendor.packaging.requirements import Requirement
req = Requirement(sys.argv[1])
sys.exit(0 if req.specifier.contains(version(req.name), prereleases=True) else 1)
PY
        then
            ok "$name $("$VENV/bin/python" -c "from importlib.metadata import version;print(version('$name'))")"
        else
            todo "$requirement — will install"
            if [[ $CHECK == 0 ]]; then
                "$VENV/bin/pip" install --quiet "$requirement" || {
                    fail "pip could not install $requirement."
                    echo "    On Ubuntu 24.04 the apt packages work instead:" >&2
                    echo "    sudo apt install python3-pyside6.qtquick python3-pyside6.qtsvg" >&2
                    exit 1
                }
                ok "$name installed"
            fi
        fi
    done < <(grep -Ev '^\s*(#|$)' "$AGENT/requirements.txt")
fi

if [[ $CHECK == 1 ]]; then
    step "Check only: nothing was changed."
    exit "$MISSING"
fi
if [[ $MISSING == 1 ]]; then
    fail "Fix the items marked ✗ above, then run this again."
    exit 1
fi

# ── 4. Settings ─────────────────────────────────────────────────────────────
step "4. Settings ($ENV_FILE)"
if sudo test -f "$ENV_FILE"; then
    if [[ -n "$AGENT_TOKEN" ]]; then
        # Rewrite just the token line, through the environment and stdin so it
        # is on no command line. Mode and owner are set again: tee keeps the
        # file's own, but this makes the intent explicit.
        # Created private from the first byte: the token must never sit in a
        # world-readable file, even for the moment before the chmod below.
        sudo install -m 600 -o root -g root /dev/null "$ENV_FILE.new"
        sudo cat "$ENV_FILE" \
            | AMR_TOKEN_VALUE="$AGENT_TOKEN" awk '
                /^AMR_AGENT_TOKEN=/ { print "AMR_AGENT_TOKEN=" ENVIRON["AMR_TOKEN_VALUE"]; seen = 1; next }
                { print }
                END { if (!seen) print "AMR_AGENT_TOKEN=" ENVIRON["AMR_TOKEN_VALUE"] }' \
            | sudo tee "$ENV_FILE.new" >/dev/null
        sudo chown "root:$RUN_USER" "$ENV_FILE.new"
        sudo chmod 640 "$ENV_FILE.new"
        sudo mv "$ENV_FILE.new" "$ENV_FILE"
        ok "kept the existing $ENV_FILE, updated agent token"
    else
        ok "kept the existing $ENV_FILE"
    fi
else
    [[ -n "$ROBOT_ID" ]] || read -rp "  Robot id (from the web UI): " ROBOT_ID
    [[ -n "$BACKEND" ]] || read -rp "  Backend URL (http://<server>/backend): " BACKEND
    if [[ -z "$AGENT_TOKEN" ]]; then
        read -rsp "  Agent token (web UI: Robot -> Details; Enter to skip): " AGENT_TOKEN
        echo
    fi
    [[ -n "$AGENT_TOKEN" ]] || todo "no agent token: the backend will refuse this agent until AMR_AGENT_TOKEN is set in $ENV_FILE"
    # Not `tr </dev/urandom | head`: under pipefail its SIGPIPE ends the script.
    PIN="$(shuf -i 1000-9999 -n 1)"
    sudo mkdir -p /etc/amr
    sed -e "s#^AMR_ROBOT_ID=.*#AMR_ROBOT_ID=$ROBOT_ID#" \
        -e "s#^AMR_BACKEND_URL=.*#AMR_BACKEND_URL=$BACKEND#" \
        -e "s#^AMR_ROS_WS=.*#AMR_ROS_WS=$ROS_WS#" \
        -e "s#^AMR_ROS_DISTRO=.*#AMR_ROS_DISTRO=$DISTRO#" \
        -e "s#^ROS_DOMAIN_ID=.*#ROS_DOMAIN_ID=$DOMAIN#" \
        -e "s#^AMR_KIOSK_NAME=.*#AMR_KIOSK_NAME=$NAME#" \
        -e "s#^AMR_KIOSK_PIN=.*#AMR_KIOSK_PIN=$PIN#" \
        "$AGENT/deploy/robot.env.example" \
        | AMR_TOKEN_VALUE="$AGENT_TOKEN" awk '/^AMR_AGENT_TOKEN=/ { print "AMR_AGENT_TOKEN=" ENVIRON["AMR_TOKEN_VALUE"]; next } { print }' \
        | sudo tee "$ENV_FILE" >/dev/null
    # The PIN and the agent token are in here. The services run as the robot's
    # user, so the file stays 640 root:<user> (not 600 root-only, which would
    # lock the service out): readable by that user, not by everyone.
    sudo chown "root:$RUN_USER" "$ENV_FILE"
    sudo chmod 640 "$ENV_FILE"
    ok "wrote $ENV_FILE — kiosk staff PIN: $PIN"
fi

# ── 5. Services ─────────────────────────────────────────────────────────────
step "5. Services"
# The kiosk needs the display, input and sound devices.
sudo usermod -aG video,render,input,audio "$RUN_USER" 2>/dev/null || true

SERVICES=(amr-agent)
[[ $KIOSK == 1 ]] && SERVICES+=(amr-kiosk)
for service in "${SERVICES[@]}"; do
    sed -e "s#@USER@#$RUN_USER#g" -e "s#@AGENT@#$AGENT#g" \
        "$AGENT/deploy/$service.service.in" | sudo tee "/etc/systemd/system/$service.service" >/dev/null
done
chmod +x "$AGENT/run_agent_gprp.sh" "$AGENT/deploy/"*.sh
sudo systemctl daemon-reload
for service in "${SERVICES[@]}"; do
    sudo systemctl enable "$service" >/dev/null 2>&1
    # restart, not start: a second run picks up the files just copied.
    sudo systemctl restart "$service"
done

if [[ $KIOSK == 1 ]] && systemctl is-active --quiet display-manager 2>/dev/null; then
    # How the robot boots is the robot team's call; just say where it is.
    todo "a desktop is running too; the kiosk is on tty7 (Ctrl+Alt+F7)."
fi

# ── Done ────────────────────────────────────────────────────────────────────
step "Status"
sleep 3
for service in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$service"; then
        ok "$service running"
    else
        fail "$service not running — journalctl -u $service -n 50"
    fi
done
cat <<EOF

Logs:      journalctl -u amr-agent -f      (or amr-kiosk)
Settings:  sudo nano $ENV_FILE && sudo systemctl restart ${SERVICES[*]}
Update:    copy the new amr_agent folder, then run this script again.
EOF
