#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend-hormonia"
BACKEND_PYTHON="$BACKEND_DIR/.venv/bin/python"
MOUNTED_HELPER="$ROOT_DIR/.gsd/milestones/M004/slices/S06/run-mounted-proof.sh"

DEFAULT_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test'
PROOF_DATABASE_URL="${FINAL_SCHEMA_PROOF_DATABASE_URL:-${TEST_DATABASE_URL:-${DATABASE_URL:-$DEFAULT_DATABASE_URL}}}"
RUNTIME_ROOT="${FINAL_SCHEMA_PROOF_RUNTIME_ROOT:-/tmp/gsd-m005-s04-final-schema-proof}"
LOCK_FILE="${FINAL_SCHEMA_PROOF_LOCK_FILE:-${RUNTIME_ROOT}/serial.lock}"

MODE=''
HISTORY=''
current_phase='init'

RUN_DIR=''
STATUS_FILE=''
CANONICAL_LOG=''
CANONICAL_FINGERPRINT=''
PYTEST_REPLAY_LOG=''
MOUNTED_HELPER_LOG=''
MOUNTED_RUNTIME_DIR=''
MOUNTED_STATUS_FILE=''
MOUNTED_BACKEND_LOG=''
MOUNTED_PROBE_LOG=''
MOUNTED_MASKED_ENV_FILE=''
MOUNTED_BOOTSTRAP_HELPER=''

log() {
  local phase="$1"
  shift
  printf '[final-schema-proof][%s][%s] %s\n' "$HISTORY" "$phase" "$*"
}

update_status() {
  local phase="$1"
  local status="$2"
  local message="$3"
  python3 - "$STATUS_FILE" "$HISTORY" "$phase" "$status" "$message" \
    "$CANONICAL_LOG" "$CANONICAL_FINGERPRINT" "$PYTEST_REPLAY_LOG" "$MOUNTED_HELPER_LOG" \
    "$MOUNTED_STATUS_FILE" "$MOUNTED_BACKEND_LOG" "$MOUNTED_PROBE_LOG" \
    "$MOUNTED_MASKED_ENV_FILE" "$MOUNTED_BOOTSTRAP_HELPER" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_file = Path(sys.argv[1])
status_file.parent.mkdir(parents=True, exist_ok=True)
payload = {
    'history': sys.argv[2],
    'phase': sys.argv[3],
    'status': sys.argv[4],
    'message': sys.argv[5],
    'timestamp': datetime.now(timezone.utc).astimezone().isoformat(),
    'paths': {
        'canonical_log': sys.argv[6],
        'canonical_fingerprint': sys.argv[7],
        'pytest_replay_log': sys.argv[8],
        'mounted_helper_log': sys.argv[9],
        'mounted_status_file': sys.argv[10],
        'backend_log': sys.argv[11],
        'live_auth_probe_log': sys.argv[12],
        'masked_env_file': sys.argv[13],
        'bootstrap_helper': sys.argv[14],
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
  log "$current_phase" "canonical_log=$CANONICAL_LOG"
  log "$current_phase" "pytest_replay_log=$PYTEST_REPLAY_LOG"
  log "$current_phase" "mounted_helper_log=$MOUNTED_HELPER_LOG"
  log "$current_phase" "mounted_status_file=$MOUNTED_STATUS_FILE"
  log "$current_phase" "backend_log=$MOUNTED_BACKEND_LOG"
  log "$current_phase" "live_auth_probe_log=$MOUNTED_PROBE_LOG"
  log "$current_phase" "masked_env_file=$MOUNTED_MASKED_ENV_FILE"
  exit 1
}

usage() {
  cat <<'EOF'
Usage: bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh [--fresh|--existing]

Modes:
  --fresh     Prepare the canonical base -> head history, replay the focused pytest packs, then run the mounted backend proof.
  --existing  Prepare the canonical boundary -> head history, replay the focused pytest packs, then run the mounted backend proof.
EOF
}

require_command() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || fail_phase "missing required command: $cmd"
}

prepare_runtime_dir() {
  rm -rf "$RUN_DIR"
  mkdir -p "$RUN_DIR"
}

read_mounted_status_field() {
  local field="$1"
  python3 - "$MOUNTED_STATUS_FILE" "$field" <<'PY'
import json
import sys
from pathlib import Path

status_file = Path(sys.argv[1])
field = sys.argv[2]
if not status_file.exists():
    raise SystemExit(1)
payload = json.loads(status_file.read_text(encoding='utf-8'))
current = payload
for part in field.split('.'):
    current = current[part]
print(current)
PY
}

run_canonical_history_prepare() {
  current_phase='canonical_head'
  update_status "$current_phase" running 'preparing canonical history'
  log "$current_phase" 'preparing canonical history'

  if ! (
    cd "$BACKEND_DIR"
    export DATABASE_URL="$PROOF_DATABASE_URL"
    exec "$BACKEND_PYTHON" - "$PROOF_DATABASE_URL" "$HISTORY" "$CANONICAL_FINGERPRINT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

import sqlalchemy as sa

from tests.migrations.test_canonical_schema_head_convergence import (
    EXISTING_UPGRADE_START,
    _make_alembic_config,
    _run_phase,
)

db_url = sys.argv[1]
history = sys.argv[2]
fingerprint_path = Path(sys.argv[3])
seed_revision = None if history == 'fresh' else EXISTING_UPGRADE_START
config = _make_alembic_config(db_url)
engine = sa.create_engine(db_url)
try:
    fingerprint = _run_phase(
        config,
        engine,
        phase=history,
        seed_revision=seed_revision,
    )
finally:
    engine.dispose()

payload = {
    'history': history,
    'seed_revision': seed_revision or 'base',
    'head': fingerprint['head'],
    'fingerprint': fingerprint,
}
fingerprint_path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
print(
    f"canonical_head history={history} seed_revision={payload['seed_revision']} "
    f"head={payload['head']} fingerprint={fingerprint_path}"
)
PY
  ) >"$CANONICAL_LOG" 2>&1; then
    fail_phase "canonical history preparation failed (see $CANONICAL_LOG)"
  fi

  log "$current_phase" "canonical_fingerprint=$CANONICAL_FINGERPRINT"
}

run_pytest_replay() {
  current_phase='pytest_replay'
  update_status "$current_phase" running 'replaying focused pytest packs on final head'
  log "$current_phase" 'replaying focused pytest packs on final head'

  if ! (
    cd "$BACKEND_DIR"
    export TEST_DATABASE_URL="$PROOF_DATABASE_URL"
    export FINAL_SCHEMA_PROOF_HISTORY="$HISTORY"
    exec "$BACKEND_PYTHON" -m pytest -q \
      tests/api/v2/test_system_auth_hard_cut_operational.py \
      tests/integration/test_local_auth_core_flow.py \
      tests/integration/test_auth_hard_cut_end_to_end.py
  ) >"$PYTEST_REPLAY_LOG" 2>&1; then
    fail_phase "pytest replay failed (see $PYTEST_REPLAY_LOG)"
  fi
}

run_mounted_backend_proof() {
  current_phase='mounted_backend'
  update_status "$current_phase" running 'starting mounted backend proof helper'
  log "$current_phase" 'starting mounted backend proof helper'

  if ! (
    cd "$ROOT_DIR"
    export DATABASE_URL="$PROOF_DATABASE_URL"
    export FINAL_SCHEMA_PROOF_HISTORY="$HISTORY"
    export MOUNTED_PROOF_RUNTIME_DIR="$MOUNTED_RUNTIME_DIR"
    export MOUNTED_PROOF_MASKED_ENV_FILE="$MOUNTED_MASKED_ENV_FILE"
    export MOUNTED_PROOF_BOOTSTRAP_HELPER="$MOUNTED_BOOTSTRAP_HELPER"
    export MOUNTED_PROOF_BACKEND_RUNTIME_TEST='tests/runtime/test_mounted_final_schema_proof.py'
    exec bash "$MOUNTED_HELPER" --backend-proof
  ) >"$MOUNTED_HELPER_LOG" 2>&1; then
    if [[ -f "$MOUNTED_STATUS_FILE" ]]; then
      current_phase="$(read_mounted_status_field 'phase' || printf '%s' "$current_phase")"
      local helper_message
      helper_message="$(read_mounted_status_field 'message' || printf 'mounted helper failed')"
      fail_phase "${helper_message} (see $MOUNTED_HELPER_LOG and $MOUNTED_STATUS_FILE)"
    fi
    fail_phase "mounted backend proof failed before status publication (see $MOUNTED_HELPER_LOG)"
  fi

  if [[ -f "$MOUNTED_STATUS_FILE" ]]; then
    current_phase="$(read_mounted_status_field 'phase' || printf '%s' 'live_auth_probe')"
  else
    current_phase='live_auth_probe'
  fi
  update_status "$current_phase" passed 'final-schema proof completed'
}

case "${1:-}" in
  --fresh)
    MODE='fresh'
    HISTORY='fresh'
    ;;
  --existing)
    MODE='existing'
    HISTORY='existing'
    ;;
  --help|-h|'')
    usage
    exit 0
    ;;
  *)
    usage
    exit 1
    ;;
esac

RUN_DIR="$RUNTIME_ROOT/$MODE"
STATUS_FILE="$RUN_DIR/status.json"
CANONICAL_LOG="$RUN_DIR/canonical-head.log"
CANONICAL_FINGERPRINT="$RUN_DIR/canonical-head.json"
PYTEST_REPLAY_LOG="$RUN_DIR/pytest-replay.log"
MOUNTED_HELPER_LOG="$RUN_DIR/mounted-backend.log"
MOUNTED_RUNTIME_DIR="$RUN_DIR/mounted-backend"
MOUNTED_STATUS_FILE="$MOUNTED_RUNTIME_DIR/status.json"
MOUNTED_BACKEND_LOG="$MOUNTED_RUNTIME_DIR/backend.log"
MOUNTED_PROBE_LOG="$MOUNTED_RUNTIME_DIR/live-auth-probe.log"
MOUNTED_MASKED_ENV_FILE="$RUN_DIR/proof.env"
MOUNTED_BOOTSTRAP_HELPER="$RUN_DIR/browser-bootstrap"

prepare_runtime_dir
current_phase='init'
update_status "$current_phase" running 'waiting for serial lock'

require_command bash
require_command flock
require_command python3
[[ -x "$BACKEND_PYTHON" ]] || fail_phase "missing backend virtualenv python at $BACKEND_PYTHON"
[[ -f "$MOUNTED_HELPER" ]] || fail_phase "missing mounted helper at $MOUNTED_HELPER"

mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
log 'lock' "acquiring serial database lock $LOCK_FILE"
flock 9
log 'lock' "acquired serial database lock $LOCK_FILE"

run_canonical_history_prepare
run_pytest_replay
run_mounted_backend_proof

log "$current_phase" 'PASS'
log "$current_phase" "status_file=$STATUS_FILE"
log "$current_phase" "canonical_log=$CANONICAL_LOG"
log "$current_phase" "pytest_replay_log=$PYTEST_REPLAY_LOG"
log "$current_phase" "mounted_helper_log=$MOUNTED_HELPER_LOG"
log "$current_phase" "mounted_status_file=$MOUNTED_STATUS_FILE"
log "$current_phase" "backend_log=$MOUNTED_BACKEND_LOG"
log "$current_phase" "live_auth_probe_log=$MOUNTED_PROBE_LOG"
log "$current_phase" "masked_env_file=$MOUNTED_MASKED_ENV_FILE"
