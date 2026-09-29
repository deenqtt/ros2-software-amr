#!/usr/bin/env bash
# Simple host entry point for the Cafe Service AMR ROS 2 Jazzy simulation.

set -euo pipefail
cd "$(dirname "$0")/.."

# Which backend this robot reports to, and which robot it is. On a real robot
# these come from a config file written once at commissioning — never typed.
# `.env` is the development equivalent; the shell still wins, so a one-off can
# be passed inline without editing anything.
if [[ -f .env ]]; then
  # Read rather than source: a value already in the environment must win, so a
  # one-off `AMR_ROBOT_ID=other bash scripts/docker_run.sh ...` works without
  # editing the file. `source` would quietly overwrite it.
  while IFS='=' read -r key value; do
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue   # skips blanks and comments
    [[ -n "${!key:-}" ]] && continue
    export "$key=$value"
  done < .env
fi

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
  bash scripts/docker_run.sh managed               Simulation + rosbridge, no mode yet;
                                                   robot_agent starts SLAM or Nav2 on
                                                   request via /robot_mode
  bash scripts/docker_run.sh teleop                Keyboard teleoperation
  bash scripts/docker_run.sh save-map [maps/name]  Save the current /map
  bash scripts/docker_run.sh down                   Stop AMR simulation containers
  bash scripts/docker_run.sh logs                   Follow named simulation logs
  bash scripts/docker_run.sh shell                  Open a shell in the image

Environment:
  AMR_BACKEND_URL   Backend base URL, e.g. http://192.168.1.10:3002
  AMR_ROBOT_ID      This robot's id in the backend registry
                    Both are needed before the agent publishes or fetches maps.

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
  local managed="${3:-false}"
  local gui="${SIM_GUI:-false}"
  local headless="${SIM_HEADLESS:-true}"
  local map_arg=()

  # In managed mode no stack is started at boot, but Nav2 still needs a map to
  # fall back on when one is requested without an explicit path.
  if [[ "$use_slam" == false || "$managed" == true ]]; then
    map_arg=("map:=${map_path:-/maps/amr_map.yaml}")
  fi

  # ros2 launch rejects `name:=` with an empty value, so an unset backend has
  # to mean "omit the argument" rather than "pass nothing for it".
  local backend_arg=()
  if [[ -n "${AMR_BACKEND_URL:-}" ]]; then
    backend_arg+=("backend_url:=${AMR_BACKEND_URL}")
  fi
  if [[ -n "${AMR_ROBOT_ID:-}" ]]; then
    backend_arg+=("robot_id:=${AMR_ROBOT_ID}")
  fi

  # Managed mode without a backend runs, surveys, and saves — to the robot's own
  # disk, where the map list will never see it. That failure is invisible until
  # someone finishes a survey and finds nothing, so say it up front.
  if [[ "$managed" == true && ( -z "${AMR_BACKEND_URL:-}" || -z "${AMR_ROBOT_ID:-}" ) ]]; then
    warn "AMR_BACKEND_URL / AMR_ROBOT_ID not set — maps saved from the UI will"
    warn "stay on this robot and never reach the registry. Set both, e.g.:"
    warn "  AMR_BACKEND_URL=http://localhost:3002 AMR_ROBOT_ID=<robot id> $0 managed"
  fi

  stop_sim_containers
  allow_x11
  if [[ "$managed" == true ]]; then
    info "Starting Cafe AMR runtime: MANAGED (robot_agent owns the mode)"
  else
    info "Starting Cafe AMR runtime: $([[ "$use_slam" == true ]] && echo SLAM || echo NAVIGATION)"
  fi
  info "Gazebo GUI=$gui, headless=$headless"

  docker compose run --rm --no-deps --service-ports \
    -e "SIM_GUI=$gui" \
    -e "AMR_BACKEND_URL=${AMR_BACKEND_URL:-}" \
    -e "AMR_ROBOT_ID=${AMR_ROBOT_ID:-}" \
    -e "SIM_HEADLESS=$headless" \
    -e FOUNDATION_ONLY=false \
    amr-sim \
    ros2 launch amr_bringup bringup.launch.py \
      "use_slam:=$use_slam" \
      "managed_mode:=$managed" \
      "${backend_arg[@]}" \
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
  managed|agent)
    # Neither stack starts. Ask for one with:
    #   ros2 service call /robot_mode custom_interfaces/srv/RobotMode "{robot_mode: 'map'}"
    run_bringup true "" true
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
