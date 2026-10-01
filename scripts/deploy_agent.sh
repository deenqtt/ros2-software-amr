#!/usr/bin/env bash
#
# Assemble the robot agent into amr_agent/, and optionally send it to a robot.
#
# The agent is not a colcon package — it is two Python files and a runner that
# a robot executes directly. Deploying it is copying that directory.
#
# The directory is built here rather than kept in git on purpose. A second
# checked-in copy is a second source of truth, and the two drift the first time
# someone edits the one they happened to open. The files under ros2_ws/src are
# the originals; this only ever copies them.
#
# Usage:
#   ./scripts/deploy_agent.sh                 assemble amr_agent/ only
#   ./scripts/deploy_agent.sh user@host       assemble, then copy to ~/amr_agent
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/ros2_ws/src/amr_bringup/scripts"
OUT="$REPO/amr_agent"
FILES=(robot_agent_node.py agent_state.py backend_client.py run_agent_gprp.sh)

for f in "${FILES[@]}"; do
    [[ -f "$SRC/$f" ]] || { echo "missing: $SRC/$f" >&2; exit 1; }
done

# Only the files this script owns are replaced. The directory may also hold a
# robot's runtime state (state/, station_data.yaml) when it is run in place,
# and wiping that would lose unsent run reports.
mkdir -p "$OUT"
rm -f "$OUT/MANIFEST"
for f in "${FILES[@]}"; do
    cp -p "$SRC/$f" "$OUT/$f"
done
chmod +x "$OUT/robot_agent_node.py" "$OUT/run_agent_gprp.sh"

# Stamped so a robot's copy can be identified later. Checksums rather than a
# version: there is no release process here, and a checksum is the only thing
# that answers "is the file on that robot the file I have".
{
    echo "# Assembled by scripts/deploy_agent.sh on $(date -Is)"
    echo "# Source: ros2_ws/src/amr_bringup/scripts — edit there, not here."
    echo "#"
    echo "# Run on the robot:"
    echo "#   ./run_agent_gprp.sh <robot_id> http://<backend-host>:3002"
    echo
    (cd "$OUT" && md5sum "${FILES[@]}")
} > "$OUT/MANIFEST"

echo "assembled $OUT"
(cd "$OUT" && md5sum "${FILES[@]}" | sed 's/^/  /')

TARGET="${1:-}"
[[ -z "$TARGET" ]] && exit 0

echo
echo "copying to $TARGET:~/amr_agent/"
ssh "$TARGET" 'mkdir -p ~/amr_agent'
# Named files only: a glob would also try to send __pycache__/ (scp refuses a
# directory without -r, and set -e then aborts mid-deploy) or runtime state.
scp -p "${FILES[@]/#/$OUT/}" "$OUT/MANIFEST" "$TARGET:~/amr_agent/"
ssh "$TARGET" 'chmod +x ~/amr_agent/robot_agent_node.py ~/amr_agent/run_agent_gprp.sh'
echo
echo "verifying"
ssh "$TARGET" "cd ~/amr_agent && md5sum ${FILES[*]}" | sed 's/^/  /'
