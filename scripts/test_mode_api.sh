#!/usr/bin/env bash
set -euo pipefail

base_url="${AMR_BACKEND_URL:-http://localhost:3001}"
tmp_file="$(mktemp)"
original="$(curl -sS "$base_url/api/mode")"
trap 'rm -f "$tmp_file"' EXIT

restore_mode() {
  local mode map_file
  mode="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["mode"])' <<<"$original")"
  map_file="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("map_file", ""))' <<<"$original")"
  local payload
  if [[ "$mode" == "navigation" && -n "$map_file" ]]; then
    payload="{\"mode\":\"navigation\",\"map_file\":\"$map_file\"}"
  else
    payload="{\"mode\":\"$mode\"}"
  fi
  curl -sS -X POST "$base_url/api/mode/switch" \
    -H 'Content-Type: application/json' -d "$payload" >/dev/null || true
}
trap 'restore_mode; rm -f "$tmp_file"' EXIT

status="$(curl -sS -o "$tmp_file" -w '%{http_code}' \
  -X POST "$base_url/api/mode/switch" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"slam"}')"
test "$status" = 200
python3 - "$tmp_file" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["mode"] == "slam"
assert "docker_run.sh slam" in payload["message"]
PY

status="$(curl -sS -o "$tmp_file" -w '%{http_code}' \
  -X POST "$base_url/api/mode/switch" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"navigation","map_file":"/maps/amr_map.yaml"}')"
test "$status" = 200
python3 - "$tmp_file" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["mode"] == "navigation"
assert payload["map_file"] == "/maps/amr_map.yaml"
PY

status="$(curl -sS -o /dev/null -w '%{http_code}' \
  -X POST "$base_url/api/mode/switch" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"invalid"}')"
test "$status" = 400

echo "mode API contract: PASS"
