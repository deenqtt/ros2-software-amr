#!/usr/bin/env bash
# Validate the supported local prerequisites for the Docker-first Jazzy setup.
#
# This repository intentionally does not install or remove native ROS packages
# on the host. Use scripts/docker_run.sh for the ROS 2 Jazzy environment.

set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $*"; }
fail() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

if [[ ! -r /etc/os-release ]]; then
  fail 'Cannot identify the host operating system.'
fi
# shellcheck disable=SC1091
source /etc/os-release

[[ "${ID:-}" == 'ubuntu' ]] || fail "Supported host is Ubuntu 24.04 Noble; detected ${PRETTY_NAME:-unknown}."
[[ "${VERSION_CODENAME:-}" == 'noble' ]] || fail "Supported host codename is noble; detected ${VERSION_CODENAME:-unknown}."

command -v docker >/dev/null 2>&1 || fail 'Docker is not installed. Install Docker Engine/Desktop, then retry.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose is unavailable.'

info "Host prerequisite check passed: ${PRETTY_NAME}"
info 'ROS 2 is provided by the official Jazzy/Noble Docker image.'
info 'Next commands:'
info '  bash scripts/docker_run.sh build'
info '  bash scripts/docker_run.sh foundation'
