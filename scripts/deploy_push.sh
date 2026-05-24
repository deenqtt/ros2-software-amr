#!/usr/bin/env bash
# =============================================================================
# deploy_push.sh — Build web UI dan SCP semua file ke Jetson robot
#
# Usage:
#   bash scripts/deploy_push.sh <robot-ip>
#   bash scripts/deploy_push.sh <robot-ip> <username>   (default: amr)
#
# Contoh:
#   bash scripts/deploy_push.sh 192.168.1.50
#   bash scripts/deploy_push.sh 192.168.1.50 ubuntu
# =============================================================================
set -euo pipefail

ROBOT_IP="${1:-}"
ROBOT_USER="${2:-amr}"
REMOTE_DIR="/opt/amr"

if [[ -z "$ROBOT_IP" ]]; then
  echo "Usage: $0 <robot-ip> [username]"
  echo "  Contoh: $0 192.168.1.50"
  echo "  Contoh: $0 192.168.1.50 ubuntu"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "======================================================"
echo " AMR Deploy Push"
echo " Target: $ROBOT_USER@$ROBOT_IP:$REMOTE_DIR"
echo "======================================================"

# ── 1. Build web UI ──────────────────────────────────────────────────────────
echo ""
echo "[1/4] Building web UI..."
cd "$REPO_ROOT/web-ui"
npm run build
echo "  → dist/ siap"

# ── 2. Pastikan remote dir ada ───────────────────────────────────────────────
echo ""
echo "[2/4] Menyiapkan direktori di Jetson..."
ssh "$ROBOT_USER@$ROBOT_IP" "mkdir -p $REMOTE_DIR/backend $REMOTE_DIR/web-ui/dist $REMOTE_DIR/maps $REMOTE_DIR/data"

# ── 3. Sync files ────────────────────────────────────────────────────────────
echo ""
echo "[3/4] Mengirim files ke Jetson..."

# Backend Python code (skip __pycache__, DB file)
echo "  → backend/"
rsync -az --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '*.db' \
  --exclude '.env' \
  "$REPO_ROOT/backend/" \
  "$ROBOT_USER@$ROBOT_IP:$REMOTE_DIR/backend/"

# Web UI dist (hasil build)
echo "  → web-ui/dist/"
rsync -az --delete \
  "$REPO_ROOT/web-ui/dist/" \
  "$ROBOT_USER@$ROBOT_IP:$REMOTE_DIR/web-ui/dist/"

# Deploy script (biar bisa dijalankan langsung dari Jetson)
echo "  → deploy_jetson.sh"
scp "$SCRIPT_DIR/deploy_jetson.sh" \
  "$ROBOT_USER@$ROBOT_IP:$REMOTE_DIR/deploy_jetson.sh"
ssh "$ROBOT_USER@$ROBOT_IP" "chmod +x $REMOTE_DIR/deploy_jetson.sh"

# ── 4. Selesai ───────────────────────────────────────────────────────────────
echo ""
echo "[4/4] Done!"
echo ""
echo "======================================================"
echo " Selanjutnya, SSH ke Jetson dan jalankan:"
echo ""
echo "   ssh $ROBOT_USER@$ROBOT_IP"
echo "   sudo $REMOTE_DIR/deploy_jetson.sh"
echo "======================================================"
