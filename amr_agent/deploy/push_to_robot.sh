#!/usr/bin/env bash
#
# From your computer: copy amr_agent to a robot and install the agent and the
# kiosk there (deploy/install_robot.sh). The robot's own stack is not touched.
#
#   ./amr_agent/deploy/push_to_robot.sh user@192.168.2.133 [install options…]
#
# e.g. a first install:
#   ./amr_agent/deploy/push_to_robot.sh robot@192.168.2.133 \
#       --robot-id 7fc87960-… --backend http://192.168.2.84/backend --name AMR-02
#
# and every update after that:
#   ./amr_agent/deploy/push_to_robot.sh robot@192.168.2.133
#
# The robot's own files are never overwritten: state/ (unsent run reports,
# cached registry), station_data.yaml and its .venv.
set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" || "$TARGET" == -* ]]; then
    sed -n '2,16p' "$0" >&2
    exit 64
fi
shift

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "→ copying amr_agent to $TARGET:~/amr_agent"
rsync -az --delete \
    --exclude '.venv/' --exclude '__pycache__/' --exclude '.pytest_cache/' \
    --exclude 'state/' --exclude 'station_data.yaml' --exclude 'tests/' \
    "$HERE/" "$TARGET:~/amr_agent/"

echo "→ installing on $TARGET"
# -t: the installer may ask for sudo's password.
# shellcheck disable=SC2029
ssh -t "$TARGET" "cd ~/amr_agent && ./deploy/install_robot.sh $(printf '%q ' "$@")"
