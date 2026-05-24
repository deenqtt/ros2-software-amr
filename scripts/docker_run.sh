#!/usr/bin/env bash
# Helper script untuk build dan run AMR simulation di Docker.
#
# Usage:
#   bash scripts/docker_run.sh build    # build image
#   bash scripts/docker_run.sh up       # start simulation
#   bash scripts/docker_run.sh slam     # start in SLAM/mapping mode
#   bash scripts/docker_run.sh nav      # start in navigation mode (need map)
#   bash scripts/docker_run.sh teleop   # start + keyboard teleop
#   bash scripts/docker_run.sh down     # stop semua container
#   bash scripts/docker_run.sh logs     # lihat logs
#   bash scripts/docker_run.sh shell    # buka bash di container

set -euo pipefail
cd "$(dirname "$0")/.."

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[AMR]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

# Update database mode agar Web UI sinkron dengan CLI
update_db_mode() {
  local mode=$1
  local map_file=${2:-""}
  local db_file="data/amr.db"
  
  if [[ -f "$db_file" ]]; then
    # Menggunakan sqlite3 jika terinstall di host, atau biarkan saja jika tidak ada
    if command -v sqlite3 >/dev/null 2>&1; then
      sqlite3 "$db_file" "INSERT OR REPLACE INTO settings (key, value) VALUES ('ros_mode', '$mode');"
      if [[ -n "$map_file" ]]; then
        sqlite3 "$db_file" "INSERT OR REPLACE INTO settings (key, value) VALUES ('ros_map_file', '$map_file');"
      fi
    fi
  fi
}

CMD="${1:-up}"

# Allow X11 from Docker
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  xhost +local:root >/dev/null 2>&1 || true
  xhost +local:$(id -un) >/dev/null 2>&1 || true
fi

export DISPLAY="${DISPLAY:-:0}"

case "$CMD" in
  build)
    info "Building AMR Docker image (ROS2 Humble)..."
    docker compose build --progress=plain
    ;;

  up|slam)
    info "Starting AMR simulation (SLAM mode)..."
    update_db_mode "slam"
    USE_SLAM=true docker compose up
    ;;

  nav)
    MAP="${2:-/maps/amr_map.yaml}"
    LOCAL_MAP="maps/$(basename "$MAP")"
    if [[ ! -f "$LOCAL_MAP" ]]; then
      warn "Map file not found: $LOCAL_MAP"
      warn "Run SLAM mode first, save the map, then use nav mode."
      exit 1
    fi
    info "Starting AMR simulation (Navigation mode, map: $MAP)..."
    update_db_mode "navigation" "$MAP"
    USE_SLAM=false docker compose run --rm \
      -e MAP_FILE="/maps/$(basename "$MAP")" \
      amr-sim \
      ros2 launch amr_bringup bringup.launch.py use_slam:=false map:="/maps/$(basename "$MAP")"
    ;;

  teleop)
    info "Starting simulation + teleop keyboard..."
    USE_SLAM=true docker compose --profile teleop up
    ;;

  down)
    info "Stopping all containers..."
    docker compose down
    # Stop juga container dari 'docker compose run' yang tidak ter-stop oleh 'down'
    docker ps -q --filter "name=ros-software-amr-sim" | xargs -r docker stop
    docker ps -aq --filter "name=ros-software-amr-sim" | xargs -r docker rm
    ;;

  logs)
    docker compose logs -f amr-sim
    ;;

  shell)
    info "Opening shell in amr-sim container..."
    docker compose exec amr-sim bash --rcfile /entrypoint.sh || \
      docker compose run --rm amr-sim bash --rcfile /entrypoint.sh
    ;;

  save-map)
    NAME="${2:-amr_map}"
    info "Saving map as maps/${NAME}..."
    docker compose exec amr-sim bash -c \
      "source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash && \
       ros2 run nav2_map_server map_saver_cli -f /maps/${NAME}"
    ;;

  *)
    echo "Usage: $0 {build|up|slam|nav [map.yaml]|teleop|down|logs|shell|save-map [name]}"
    exit 1
    ;;
esac
