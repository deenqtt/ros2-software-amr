#!/usr/bin/env bash
# Start backend + web UI for local development (no Docker needed)
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── Backend ───────────────────────────────────────────────────────────────────
if ! lsof -i:3001 -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "[start_dev] Starting AMR backend on :3001..."
  mkdir -p "$ROOT/data"
  cd "$ROOT/backend"
  DB_PATH="$ROOT/data/amr.db" \
  MAPS_DIR="$ROOT/maps" \
  ROS_MAPS_PATH="$ROOT/maps" \
  .venv/bin/uvicorn main:app --host 0.0.0.0 --port 3001 --reload \
    > /tmp/amr-backend.log 2>&1 &
  BACKEND_PID=$!
  echo "  PID=$BACKEND_PID  log=/tmp/amr-backend.log"
else
  echo "[start_dev] Backend already running on :3001"
fi

# ── Web UI ────────────────────────────────────────────────────────────────────
if ! lsof -i:3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "[start_dev] Starting Web UI on :3000..."
  cd "$ROOT/web-ui"
  npm run dev > /tmp/amr-webui.log 2>&1 &
  WEBUI_PID=$!
  echo "  PID=$WEBUI_PID  log=/tmp/amr-webui.log"
else
  echo "[start_dev] Web UI already running on :3000"
fi

echo ""
echo "  Web UI  → http://localhost:3000"
echo "  Backend → http://localhost:3001"
echo "  API docs → http://localhost:3001/docs"
echo ""
echo "Stop with: kill \$(lsof -t -i:3000 -i:3001)"
