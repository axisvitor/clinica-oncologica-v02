#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend-hormonia"
FRONTEND_DIR="$ROOT_DIR/frontend-hormonia"
SEED_SCRIPT="$SCRIPT_DIR/seed-proof-user.py"
BACKEND_PYTHON="$BACKEND_DIR/.venv/bin/python"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_BASE_URL="http://localhost:${BACKEND_PORT}"
E2E_BASE_URL="http://localhost:${FRONTEND_PORT}"
RUNTIME_DIR="${MOUNTED_PROOF_RUNTIME_DIR:-/tmp/gsd-s06-mounted-proof}"
MASKED_ENV_FILE="${MOUNTED_PROOF_MASKED_ENV_FILE:-/tmp/gsd-s06-proof.env}"
BOOTSTRAP_HELPER="${MOUNTED_PROOF_BOOTSTRAP_HELPER:-/tmp/gsd-s06-browser-bootstrap}"
STATUS_FILE="$RUNTIME_DIR/status.json"
BACKEND_LOG="$RUNTIME_DIR/backend.log"
FRONTEND_LOG="$RUNTIME_DIR/frontend.log"
LIVE_AUTH_PROBE_LOG="$RUNTIME_DIR/live-auth-probe.log"
RUNNER_WUZAPI_TOKEN='mounted-proof-local-token'
BACKEND_RUNTIME_TEST="${MOUNTED_PROOF_BACKEND_RUNTIME_TEST:-tests/runtime/test_mounted_final_schema_proof.py}"

backend_pid=''
frontend_pid=''
current_phase='init'
action=''
preserve_runtime_on_exit='false'
preflight_phase='preflight'
seed_phase='seed'
seed_base_url="$E2E_BASE_URL"
PREFLIGHT_HOLD_SECONDS="${MOUNTED_PROOF_PREFLIGHT_HOLD_SECONDS:-10}"

log() {
  local phase="$1"
  shift
  printf '[mounted-proof][%s] %s\n' "$phase" "$*"
}

update_status() {
  local phase="$1"
  local status="$2"
  local message="$3"
  python3 - "$STATUS_FILE" "$phase" "$status" "$message" "$BACKEND_LOG" "$FRONTEND_LOG" "$MASKED_ENV_FILE" "$BOOTSTRAP_HELPER" "$LIVE_AUTH_PROBE_LOG" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_file = Path(sys.argv[1])
status_file.parent.mkdir(parents=True, exist_ok=True)
payload = {
    'phase': sys.argv[2],
    'status': sys.argv[3],
    'message': sys.argv[4],
    'timestamp': datetime.now(timezone.utc).astimezone().isoformat(),
    'paths': {
        'backend_log': sys.argv[5],
        'frontend_log': sys.argv[6],
        'masked_env_file': sys.argv[7],
        'bootstrap_helper': sys.argv[8],
        'live_auth_probe_log': sys.argv[9],
    },
}
status_file.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
PY
}

fail_phase() {
  local message="$1"
  update_status "$current_phase" failed "$message"
  log "$current_phase" "FAILED: $message"
  log "$current_phase" "status_file=$STATUS_FILE"
  log "$current_phase" "backend_log=$BACKEND_LOG"
  log "$current_phase" "frontend_log=$FRONTEND_LOG"
  log "$current_phase" "live_auth_probe_log=$LIVE_AUTH_PROBE_LOG"
  log "$current_phase" "masked_env_file=$MASKED_ENV_FILE"
  log "$current_phase" "bootstrap_helper=$BOOTSTRAP_HELPER"
  exit 1
}

cleanup() {
  local exit_code=$?

  if [[ "$preserve_runtime_on_exit" == 'true' ]] && [[ "$exit_code" -eq 0 ]]; then
    local preserved_backend_pid="$backend_pid"
    local preserved_frontend_pid="$frontend_pid"
    local preserved_backend_port="$BACKEND_PORT"
    local preserved_frontend_port="$FRONTEND_PORT"
    local hold_seconds="$PREFLIGHT_HOLD_SECONDS"

    (
      sleep "$hold_seconds"

      if [[ -n "$preserved_frontend_pid" ]] && kill -0 "$preserved_frontend_pid" 2>/dev/null; then
        kill "$preserved_frontend_pid" >/dev/null 2>&1 || true
        wait "$preserved_frontend_pid" >/dev/null 2>&1 || true
      fi
      if [[ -n "$preserved_backend_pid" ]] && kill -0 "$preserved_backend_pid" 2>/dev/null; then
        kill "$preserved_backend_pid" >/dev/null 2>&1 || true
        wait "$preserved_backend_pid" >/dev/null 2>&1 || true
      fi

      frontend_port_pids="$(lsof -tiTCP:"$preserved_frontend_port" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -n "$frontend_port_pids" ]]; then
        kill $frontend_port_pids >/dev/null 2>&1 || true
      fi

      backend_port_pids="$(lsof -tiTCP:"$preserved_backend_port" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -n "$backend_port_pids" ]]; then
        kill $backend_port_pids >/dev/null 2>&1 || true
      fi
    ) >/dev/null 2>&1 &

    backend_pid=''
    frontend_pid=''
    exit "$exit_code"
  fi

  if [[ -n "$frontend_pid" ]] && kill -0 "$frontend_pid" 2>/dev/null; then
    kill "$frontend_pid" >/dev/null 2>&1 || true
    wait "$frontend_pid" >/dev/null 2>&1 || true
  fi
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid" >/dev/null 2>&1 || true
    wait "$backend_pid" >/dev/null 2>&1 || true
  fi

  if [[ -n "$frontend_pid" ]]; then
    frontend_port_pids="$(lsof -tiTCP:"$FRONTEND_PORT" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$frontend_port_pids" ]]; then
      kill $frontend_port_pids >/dev/null 2>&1 || true
    fi
  fi
  if [[ -n "$backend_pid" ]]; then
    backend_port_pids="$(lsof -tiTCP:"$BACKEND_PORT" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$backend_port_pids" ]]; then
      kill $backend_port_pids >/dev/null 2>&1 || true
    fi
  fi

  exit "$exit_code"
}
trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage: bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh [--preflight|--seed|--auth|--smoke|--backend-proof|--all]

Modes:
  --preflight      Start the mounted no-Firebase stack, probe runtime truth surfaces, seed the proof user, and keep the stack alive briefly for immediate follow-up curls.
  --seed           Seed/update the proof admin and refresh masked replay artifacts without starting the stack.
  --auth           Run the canonical session-first Playwright acceptance on the mounted stack.
  --smoke          Run the routed no-Firebase runtime smoke on the mounted stack.
  --backend-proof  Start only the backend, seed the proof admin, and run the live backend auth/runtime proof against uvicorn.
  --all            Run preflight + auth + smoke on one mounted stack.
EOF
}

require_command() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || fail_phase "missing required command: $cmd"
}

prepare_runtime_dir() {
  rm -rf "$RUNTIME_DIR"
  mkdir -p "$RUNTIME_DIR"
  : > "$BACKEND_LOG"
  : > "$FRONTEND_LOG"
  : > "$LIVE_AUTH_PROBE_LOG"
}

port_in_use() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

ensure_port_available() {
  local port="$1"
  local label="$2"
  if port_in_use "$port"; then
    local pid
    pid="$(lsof -tiTCP:"$port" -sTCP:LISTEN | tr '\n' ' ' | sed 's/[[:space:]]\+$//')"
    fail_phase "$label port ${port} already in use by pid(s): ${pid}"
  fi
}

wait_for_http() {
  local url="$1"
  local timeout_seconds="$2"
  local started_at
  started_at="$(date +%s)"

  while true; do
    if curl --silent --show-error --fail "$url" >/dev/null 2>&1; then
      return 0
    fi
    if (( $(date +%s) - started_at >= timeout_seconds )); then
      return 1
    fi
    sleep 1
  done
}

assert_ready_payload() {
  local payload_file="$1"
  python3 - "$payload_file" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert payload.get('status') == 'ready', payload
assert 'firebase' not in payload.get('dependencies', []), payload
assert 'session_auth' in payload.get('dependencies', []), payload
PY
}

assert_config_payload() {
  local payload_file="$1"
  python3 - "$payload_file" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert all(not key.startswith('VITE_FIREBASE_') for key in payload.keys()), payload
assert 'firebase' not in json.dumps(payload).lower(), payload
PY
}

assert_wuzapi_payload() {
  local payload_file="$1"
  python3 - "$payload_file" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert payload.get('connected') is True, payload
assert payload.get('logged_in') is True, payload
assert payload.get('mock') is True, payload
PY
}

start_backend() {
  current_phase="$preflight_phase"
  update_status "$current_phase" running 'starting backend'
  log "$current_phase" "starting backend on port $BACKEND_PORT"

  (
    cd "$BACKEND_DIR"
    export PYTHONUNBUFFERED=1
    export APP_ENVIRONMENT='development'
    export ENVIRONMENT='development'
    unset TESTING
    unset PYTEST_CURRENT_TEST
    export FIREBASE_ADMIN_PROJECT_ID=''
    export FIREBASE_ADMIN_CLIENT_EMAIL=''
    export FIREBASE_ADMIN_PRIVATE_KEY=''
    export FIREBASE_PROJECT_ID=''
    export WHATSAPP_WUZAPI_TOKEN="$RUNNER_WUZAPI_TOKEN"
    export WHATSAPP_WUZAPI_USE_MOCK='true'
    exec "$BACKEND_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT"
  ) >"$BACKEND_LOG" 2>&1 &
  backend_pid="$!"

  if ! wait_for_http "${BACKEND_BASE_URL}/health/ready" 90; then
    fail_phase "backend did not become ready on port ${BACKEND_PORT}"
  fi
}

start_frontend() {
  current_phase="$preflight_phase"
  update_status "$current_phase" running 'starting frontend'
  log "$current_phase" "starting frontend on port $FRONTEND_PORT"

  (
    cd "$FRONTEND_DIR"
    export VITE_API_URL="http://localhost:${BACKEND_PORT}"
    export VITE_API_BASE_URL="http://localhost:${BACKEND_PORT}"
    export VITE_WS_BASE_URL="ws://localhost:${BACKEND_PORT}/ws"
    export VITE_FIREBASE_API_KEY=''
    export VITE_FIREBASE_PROJECT_ID=''
    export VITE_FIREBASE_APP_ID=''
    export VITE_FIREBASE_AUTH_DOMAIN=''
    exec npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"
  ) >"$FRONTEND_LOG" 2>&1 &
  frontend_pid="$!"

  if ! wait_for_http "${E2E_BASE_URL}/login" 90; then
    fail_phase "frontend did not become ready on port ${FRONTEND_PORT}"
  fi
}

probe_runtime_contract() {
  current_phase="$preflight_phase"
  update_status "$current_phase" running 'probing runtime truth surfaces'

  local ready_payload="$RUNTIME_DIR/health-ready.json"
  local config_payload="$RUNTIME_DIR/system-config.json"
  local wuzapi_payload="$RUNTIME_DIR/wuzapi-status.json"

  curl --silent --show-error --fail "${BACKEND_BASE_URL}/health/ready" > "$ready_payload" \
    || fail_phase 'failed to fetch /health/ready'
  assert_ready_payload "$ready_payload" || fail_phase '/health/ready did not report session_auth-ready no-Firebase state'

  curl --silent --show-error --fail "${BACKEND_BASE_URL}/api/v2/system/config" > "$config_payload" \
    || fail_phase 'failed to fetch /api/v2/system/config'
  assert_config_payload "$config_payload" || fail_phase '/api/v2/system/config still advertises Firebase config'

  curl --silent --show-error --fail "${BACKEND_BASE_URL}/api/v2/monitoring/wuzapi/session/status" > "$wuzapi_payload" \
    || fail_phase 'failed to fetch /api/v2/monitoring/wuzapi/session/status'
  assert_wuzapi_payload "$wuzapi_payload" || fail_phase 'mocked WuzAPI session status did not report connected/logged_in=true'

  log "$current_phase" "ready_surface=$ready_payload"
  log "$current_phase" "config_surface=$config_payload"
  log "$current_phase" "wuzapi_surface=$wuzapi_payload"
}

seed_contract() {
  current_phase="$seed_phase"
  update_status "$current_phase" running 'seeding proof admin and refreshing masked replay artifacts'
  log "$current_phase" 'refreshing proof admin contract'

  local exports
  exports="$(
    export FIREBASE_ADMIN_PROJECT_ID=''
    export FIREBASE_ADMIN_CLIENT_EMAIL=''
    export FIREBASE_ADMIN_PRIVATE_KEY=''
    export WHATSAPP_WUZAPI_TOKEN="$RUNNER_WUZAPI_TOKEN"
    export WHATSAPP_WUZAPI_USE_MOCK='true'
    "$BACKEND_PYTHON" "$SEED_SCRIPT" \
      --base-url "$seed_base_url" \
      --write-masked-env "$MASKED_ENV_FILE" \
      --write-bootstrap "$BOOTSTRAP_HELPER" \
      --emit-shell-exports
  )" || fail_phase 'seed helper failed'

  eval "$exports"

  if [[ -z "${E2E_SESSION_FIRST_EMAIL:-}" || -z "${E2E_SESSION_FIRST_PASSWORD:-}" || -z "${E2E_SESSION_FIRST_RESET_TOKEN:-}" ]]; then
    fail_phase 'seed helper did not export the expected E2E_SESSION_FIRST_* variables'
  fi

  log "$current_phase" "masked_env_file=$MASKED_ENV_FILE"
  log "$current_phase" "bootstrap_helper=$BOOTSTRAP_HELPER"
}

run_playwright_spec() {
  local spec_path="$1"
  local label="$2"

  current_phase="$label"
  update_status "$current_phase" running "running ${spec_path}"
  log "$current_phase" "running ${spec_path}"

  if ! (
    cd "$FRONTEND_DIR"
    export E2E_BASE_URL="$E2E_BASE_URL"
    export E2E_SESSION_FIRST_EMAIL="$E2E_SESSION_FIRST_EMAIL"
    export E2E_SESSION_FIRST_PASSWORD="$E2E_SESSION_FIRST_PASSWORD"
    export E2E_SESSION_FIRST_ROTATED_PASSWORD="${E2E_SESSION_FIRST_ROTATED_PASSWORD:-}"
    export E2E_SESSION_FIRST_RESET_TOKEN="${E2E_SESSION_FIRST_RESET_TOKEN:-}"
    export VITE_FIREBASE_API_KEY=''
    export VITE_FIREBASE_PROJECT_ID=''
    export VITE_FIREBASE_APP_ID=''
    export VITE_FIREBASE_AUTH_DOMAIN=''
    export FIREBASE_ADMIN_PROJECT_ID=''
    export FIREBASE_ADMIN_CLIENT_EMAIL=''
    exec npx playwright test "$spec_path" --config tests/e2e/playwright.config.e2e.ts --project=chromium
  ); then
    fail_phase "Playwright ${label} failed for ${spec_path}"
  fi

  log "$current_phase" "playwright_artifacts=$FRONTEND_DIR/test-results"
}

run_backend_runtime_proof() {
  current_phase='live_auth_probe'
  update_status "$current_phase" running "running ${BACKEND_RUNTIME_TEST}"
  log "$current_phase" "running ${BACKEND_RUNTIME_TEST}"

  if ! (
    cd "$BACKEND_DIR"
    export MOUNTED_PROOF_BASE_URL="$BACKEND_BASE_URL"
    export MOUNTED_PROOF_EMAIL="$E2E_SESSION_FIRST_EMAIL"
    export MOUNTED_PROOF_PASSWORD="$E2E_SESSION_FIRST_PASSWORD"
    export MOUNTED_PROOF_HISTORY="${FINAL_SCHEMA_PROOF_HISTORY:-mounted}"
    export MOUNTED_PROOF_RUNTIME_DIR="$RUNTIME_DIR"
    exec "$BACKEND_PYTHON" -m pytest -q "$BACKEND_RUNTIME_TEST"
  ) >"$LIVE_AUTH_PROBE_LOG" 2>&1; then
    fail_phase "backend runtime proof failed for ${BACKEND_RUNTIME_TEST}"
  fi

  log "$current_phase" "live_auth_probe_log=$LIVE_AUTH_PROBE_LOG"
}

run_backend_preflight() {
  current_phase="$preflight_phase"
  update_status "$current_phase" running 'preparing mounted runtime proof'
  prepare_runtime_dir
  require_command curl
  require_command python3
  [[ -x "$BACKEND_PYTHON" ]] || fail_phase "missing backend virtualenv python at $BACKEND_PYTHON"
  [[ -f "$SEED_SCRIPT" ]] || fail_phase "missing seed helper at $SEED_SCRIPT"
  ensure_port_available "$BACKEND_PORT" 'backend'
  start_backend
  probe_runtime_contract
}

run_preflight() {
  run_backend_preflight
  require_command npm
  [[ -d "$FRONTEND_DIR/node_modules" ]] || fail_phase 'frontend node_modules not present'
  ensure_port_available "$FRONTEND_PORT" 'frontend'
  start_frontend
}

case "${1:-}" in
  --preflight)
    action='preflight'
    run_preflight
    seed_contract
    ;;
  --seed)
    action='seed'
    prepare_runtime_dir
    require_command python3
    [[ -x "$BACKEND_PYTHON" ]] || fail_phase "missing backend virtualenv python at $BACKEND_PYTHON"
    seed_contract
    ;;
  --auth)
    action='auth'
    run_preflight
    seed_contract
    run_playwright_spec 'tests/e2e/auth/session-first-hard-cut.spec.ts' 'auth'
    ;;
  --smoke)
    action='smoke'
    run_preflight
    seed_contract
    run_playwright_spec 'tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts' 'smoke'
    ;;
  --backend-proof)
    action='backend-proof'
    preflight_phase='mounted_backend'
    seed_phase='mounted_backend'
    seed_base_url="$BACKEND_BASE_URL"
    run_backend_preflight
    seed_contract
    run_backend_runtime_proof
    ;;
  --all)
    action='all'
    run_preflight
    seed_contract
    run_playwright_spec 'tests/e2e/auth/session-first-hard-cut.spec.ts' 'auth'
    run_playwright_spec 'tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts' 'smoke'
    ;;
  --help|-h|'')
    usage
    exit 0
    ;;
  *)
    usage
    fail_phase "unknown argument: ${1}"
    ;;
esac

final_status_message="${action} completed"
if [[ "$action" == 'preflight' ]]; then
  preserve_runtime_on_exit='true'
  final_status_message="preflight completed; runtime preserved for ${PREFLIGHT_HOLD_SECONDS}s for follow-up probes"
fi

update_status "${current_phase}" passed "$final_status_message"
log "${current_phase}" 'PASS'
if [[ "$action" == 'preflight' ]]; then
  log "${current_phase}" "runtime_preserved_for=${PREFLIGHT_HOLD_SECONDS}s"
fi
log "${current_phase}" "status_file=$STATUS_FILE"
log "${current_phase}" "backend_log=$BACKEND_LOG"
log "${current_phase}" "frontend_log=$FRONTEND_LOG"
log "${current_phase}" "live_auth_probe_log=$LIVE_AUTH_PROBE_LOG"
log "${current_phase}" "masked_env_file=$MASKED_ENV_FILE"
log "${current_phase}" "bootstrap_helper=$BOOTSTRAP_HELPER"
