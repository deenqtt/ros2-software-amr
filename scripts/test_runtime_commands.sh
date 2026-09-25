#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

help_output="$(bash scripts/docker_run.sh help 2>&1)"
grep -q "gazebo" <<<"$help_output"
grep -q "slam" <<<"$help_output"
grep -q "nav" <<<"$help_output"
grep -q "headless" <<<"$help_output"

compose_output="$(docker compose config)"
grep -q 'gui:' <<<"$compose_output"
grep -q 'headless:' <<<"$compose_output"

echo "runtime command contract: PASS"
