#!/usr/bin/env bash
# Simple host entry point for the Cafe Service AMR ROS 2 Jazzy simulation.

set -euo pipefail
cd "$(dirname "$0")/.."

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
info() { echo -e "${GREEN}[AMR]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

usage() {
  cat <<'EOF'
Usage:
  bash scripts/docker_run.sh build                 Build ROS 2 Jazzy image
  bash scripts/docker_run.sh gazebo                Gazebo Harmonic GUI only
  bash scripts/docker_run.sh headless              Gazebo server-only
  bash scripts/docker_run.sh slam                  Full simulation + SLAM + rosbridge
  bash scripts/docker_run.sh nav [map.yaml]        Full simulation + Nav2 + rosbridge
  bash scripts/docker_run.sh teleop                Keyboard teleoperation
  bash scripts/docker_run.sh save-map [maps/name]  Save the current /map
  bash scripts/docker_run.sh down                   Stop AMR simulation containers
  bash scripts/docker_run.sh logs                   Follow named simulation logs
  bash scripts/docker_run.sh shell                  Open a shell in the image

The Web UI and backend are separate services. Start them from web-ui/ and
backend/ as documented in docs/runbooks/AMR_SIMULATION_COMMANDS.md.
The SLAM/Nav2 commands stay in the foreground; press Ctrl-C to stop them.
EOF
}

allow_x11() {
  if [[ "${OSTYPE:-}" == linux-gnu* ]] && command -v xhost >/dev/null 2>&1; then
    xhost +local:root >/dev/null 2>&1 || true
    xhost +local:"$(id -un)" >/dev/null 2>&1 || true
  fi
  export DISPLAY="${DISPLAY:-:0}"
}

stop_sim_containers() {
  # docker compose scopes this lookup to the current project directory, so a
  # second checkout or unrelated Compose project cannot be stopped.
  local ids
  ids="$(docker compose ps -q --status running --all amr-sim)"
  if [[ -n "$ids" ]]; then
    docker stop $ids >/dev/null
  fi
}

map_container_path() {
  local requested="${1:-maps/amr_map.yaml}"
  local filename
  case "$requested" in
    /maps/*.yaml|/maps/*.yml)
      filename="${requested##*/}"
      ;;
    maps/*.yaml|maps/*.yml|*.yaml|*.yml)
      filename="${requested##*/}"
      ;;
    *)
      warn "Map harus berupa file .yaml/.yml, contoh: maps/amr_map.yaml"
      return 2
      ;;
  esac
  if [[ ! -f "maps/$filename" ]]; then
    warn "Map tidak ditemukan di host: maps/$filename"
    return 2
  fi
  printf '/maps/%s' "$filename"
}

map_output_path() {
  local requested="${1:-maps/amr_map}"
  local filename="${requested##*/}"
  if [[ "$filename" != *.yaml && "$filename" != *.yml ]]; then
    filename="${filename}.yaml"
  fi
  if [[ "$filename" == .* || "$filename" == */* || "$filename" == *..* ]]; then
    warn "Nama output map tidak valid: $requested"
    return 2
  fi
  printf '/maps/%s' "$filename"
}

run_bringup() {
  local use_slam="$1"
  local map_path="${2:-}"
  local gui="${SIM_GUI:-false}"
  local headless="${SIM_HEADLESS:-true}"
  local map_arg=()

  if [[ "$use_slam" == false ]]; then
    map_arg=("map:=$map_path")
  fi

  stop_sim_containers
  allow_x11
  info "Starting Cafe AMR runtime: $([[ "$use_slam" == true ]] && echo SLAM || echo NAVIGATION)"
  info "Gazebo GUI=$gui, headless=$headless"

  docker compose run --rm --no-deps --service-ports \
    -e "SIM_GUI=$gui" \
    -e "SIM_HEADLESS=$headless" \
    -e FOUNDATION_ONLY=false \
    amr-sim \
    ros2 launch amr_bringup bringup.launch.py \
      "use_slam:=$use_slam" \
      "gui:=$gui" \
      "headless:=$headless" \
      "use_sim_time:=true" \
      "${map_arg[@]}"
}

CMD="${1:-help}"
case "$CMD" in
  help|-h|--help)
    usage
    ;;
  build)
    info "Building AMR Docker image (ROS 2 Jazzy / Ubuntu Noble)..."
    docker compose --progress=plain build
    ;;
  gazebo)
    allow_x11
    info "Starting Gazebo Harmonic GUI only..."
    SIM_GUI=true SIM_HEADLESS=false FOUNDATION_ONLY=false \
      docker compose up --force-recreate amr-sim
    ;;
  headless|up|foundation)
    info "Starting Gazebo Harmonic server-only..."
    SIM_GUI=false SIM_HEADLESS=true FOUNDATION_ONLY=false \
      docker compose up --force-recreate amr-sim
    ;;
  slam|mapping)
    run_bringup true
    ;;
  nav|navigation)
    map_path="$(map_container_path "${2:-maps/amr_map.yaml}")"
    run_bringup false "$map_path"
    ;;
  teleop)
    info "Starting keyboard teleoperation (Ctrl-C to stop)..."
    docker compose run --rm --no-deps --service-ports teleop
    ;;
  save-map)
    output_path="$(map_output_path "${2:-maps/amr_map}")"
    output_path="${output_path%.yaml}"
    output_path="${output_path%.yml}"
    info "Saving /map to $output_path..."
    docker compose run --rm --no-deps amr-sim \
      ros2 run nav2_map_server map_saver_cli -f "$output_path"
    ;;
  down)
    info "Stopping AMR simulation containers..."
    stop_sim_containers
    ;;
  logs)
    docker compose logs -f amr-sim
    ;;
  shell)
    info "Opening shell in amr-sim image..."
    docker compose run --rm --no-deps amr-sim bash
    ;;
  *)
    warn "Unknown command: $CMD"
    usage
    exit 2
    ;;
esac
