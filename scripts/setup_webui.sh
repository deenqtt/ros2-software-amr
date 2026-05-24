#!/usr/bin/env bash
# Set up and start the AMR web UI.
#
# Usage: bash scripts/setup_webui.sh [--dev | --build]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="$(dirname "$SCRIPT_DIR")/web-ui"

GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${GREEN}[WEBUI]${NC} $*"; }

cd "$UI_DIR"

# Check Node.js
if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js not found. Install via:"
  echo "  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
  echo "  sudo apt install -y nodejs"
  exit 1
fi

info "Node.js: $(node --version)"
info "npm: $(npm --version)"

# Install dependencies
info "Installing npm dependencies..."
npm install

MODE="${1:---dev}"

if [[ "$MODE" == "--build" ]]; then
  info "Building for production..."
  npm run build
  info "Build output in: $UI_DIR/dist/"
  info "Serve with: npx serve dist -p 3000"
else
  info "Starting dev server on http://localhost:3000 ..."
  info "Make sure Foxglove Bridge is running on ws://localhost:8765"
  npm run dev
fi
