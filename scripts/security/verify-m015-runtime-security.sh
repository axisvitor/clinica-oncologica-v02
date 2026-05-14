#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# M015 synthetic runtime security harness.
# Public entrypoint for milestone M015 runtime seams. The DB and session seams
# are implemented; every other seam must fail closed before setup starts.

SCRIPT_REL="scripts/security/verify-m015-runtime-security.sh"
HARNESS_DIR="scripts/security/m015-runtime"
COMPOSE_FILE="${HARNESS_DIR}/docker-compose.yml"
RUNTIME_DIR=".m015-runtime"
CERT_DIR="${RUNTIME_DIR}/certs"
LOG_DIR="${RUNTIME_DIR}/logs"
ENV_FILE="${RUNTIME_DIR}/m015.env"
EVIDENCE_ROOT="${HARNESS_DIR}/evidence"
DB_EVIDENCE_OUTPUT_DIR="backend-hormonia/docs/reports/security/m015"
DB_EVIDENCE_JSON="${DB_EVIDENCE_OUTPUT_DIR}/db-seam-evidence.json"
DB_SUMMARY_MD="${DB_EVIDENCE_OUTPUT_DIR}/db-seam-summary.md"
SESSION_EVIDENCE_OUTPUT_DIR="backend-hormonia/docs/reports/security/m015"
SESSION_EVIDENCE_JSON="${SESSION_EVIDENCE_OUTPUT_DIR}/session-seam-evidence.json"
SESSION_SUMMARY_MD="${SESSION_EVIDENCE_OUTPUT_DIR}/session-seam-summary.md"

SEAM=""
KEEP_STACK="false"
TEARDOWN_ONLY="false"
API_PORT="${M015_API_PORT:-18080}"
POSTGRES_PORT="${M015_POSTGRES_PORT:-15432}"
PROJECT_NAME="${M015_PROJECT_NAME:-}"
CORRELATION_ID="${M015_CORRELATION_ID:-m015-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
LAST_PHASE="argument-parse"
FAILURE_CLASS="none"
STARTED="false"
EVIDENCE_DIR=""
EVIDENCE_FILE=""

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/security/verify-m015-runtime-security.sh --seam {db|session} [options]

Implemented seams:
  db                         Start the isolated M015 DB runtime substrate, prove readiness, and tear down.
  session                    Prove cookie-backed staff sessions, Redis fallback/revocation, and Taskiq DB re-checks.

Options:
  --seam {db|session}        Required. Unknown or omitted seams fail closed and do not start services.
  --list-seams               Print implemented seams and exit.
  --help, -h                 Show this help and exit.
  --keep-stack               Leave the Docker Compose stack running for manual inspection.
  --teardown-only            Run idempotent compose teardown for the selected project/seam and exit.
  --api-port PORT            Host port for FastAPI readiness (default: $M015_API_PORT or 18080).
  --postgres-port PORT       Host port for PostgreSQL TLS access (default: $M015_POSTGRES_PORT or 15432).
  --project-name NAME        Compose project name (default: $M015_PROJECT_NAME or unique per run).

Examples:
  ./scripts/security/verify-m015-runtime-security.sh --list-seams
  ./scripts/security/verify-m015-runtime-security.sh --seam db
  ./scripts/security/verify-m015-runtime-security.sh --seam session
  M015_API_PORT=18180 ./scripts/security/verify-m015-runtime-security.sh --seam db --keep-stack
  ./scripts/security/verify-m015-runtime-security.sh --seam session --project-name m015-debug --teardown-only
USAGE
}

list_seams() {
  printf 'db\nsession\n'
}

cli_error() {
  printf 'error: %s\n\n' "$1" >&2
  usage >&2
  exit 64
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --help|-h)
        usage
        exit 0
        ;;
      --list-seams)
        list_seams
        exit 0
        ;;
      --seam)
        [[ $# -ge 2 ]] || cli_error "--seam requires a value"
        SEAM="$2"
        shift 2
        ;;
      --seam=*)
        SEAM="${1#--seam=}"
        shift
        ;;
      --keep-stack)
        KEEP_STACK="true"
        shift
        ;;
      --teardown-only)
        TEARDOWN_ONLY="true"
        shift
        ;;
      --api-port)
        [[ $# -ge 2 ]] || cli_error "--api-port requires a value"
        API_PORT="$2"
        shift 2
        ;;
      --api-port=*)
        API_PORT="${1#--api-port=}"
        shift
        ;;
      --postgres-port)
        [[ $# -ge 2 ]] || cli_error "--postgres-port requires a value"
        POSTGRES_PORT="$2"
        shift 2
        ;;
      --postgres-port=*)
        POSTGRES_PORT="${1#--postgres-port=}"
        shift
        ;;
      --project-name)
        [[ $# -ge 2 ]] || cli_error "--project-name requires a value"
        PROJECT_NAME="$2"
        shift 2
        ;;
      --project-name=*)
        PROJECT_NAME="${1#--project-name=}"
        shift
        ;;
      *)
        cli_error "unknown argument: $1"
        ;;
    esac
  done

  [[ -n "$SEAM" ]] || cli_error "fail-closed: no seam selected; pass --seam db or --seam session"
  case "$SEAM" in
    db|session) ;;
    *) cli_error "unknown seam '${SEAM}'. Implemented seams: db, session" ;;
  esac
  [[ "$API_PORT" =~ ^[0-9]+$ ]] || cli_error "--api-port must be numeric"
  [[ "$POSTGRES_PORT" =~ ^[0-9]+$ ]] || cli_error "--postgres-port must be numeric"
}

normalize_project_name() {
  local raw="$1"
  local normalized
  normalized="$(printf '%s' "$raw" \
    | tr '[:upper:]_' '[:lower:]-' \
    | sed -E 's/[^a-z0-9-]+/-/g; s/^-+//; s/-+$//; s/-+/-/g' \
    | cut -c1-63)"
  if [[ -z "$normalized" ]]; then
    normalized="m015-runtime"
  fi
  printf '%s' "$normalized"
}

sanitize_stream() {
  sed -E \
    -e 's#postgres(ql)?(\+[A-Za-z0-9_]+)?://[^[:space:]]+#postgresql://<redacted>#g' \
    -e 's#redis://[^[:space:]]+#redis://<redacted>#g' \
    -e 's#rediss://[^[:space:]]+#rediss://<redacted>#g' \
    -e 's#([A-Za-z0-9_]*(PASSWORD|TOKEN|SECRET|KEY)[A-Za-z0-9_]*=)[^[:space:]]+#\1<redacted>#g' \
    -e 's#(Authorization: Bearer )[A-Za-z0-9._~+/-]+#\1<redacted>#g' \
    -e 's#([Ss]et-[Cc]ookie:[[:space:]]*)[^[:cntrl:]]+#\1<redacted>#g' \
    -e 's#(^|[[:space:]])([Cc]ookie:[[:space:]]*)[^[:cntrl:]]+#\1\2<redacted>#g' \
    -e 's#/mnt/c/[^[:space:]]+#<redacted-host-path>#g' \
    -e 's#/m015-certs/[^[:space:]]+#<redacted-cert-path>#g'
}

sanitize_inline() {
  printf '%s' "$1" | sanitize_stream | tr '\n' ' '
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/ }"
  printf '%s' "$value"
}

timestamp() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

emit_evidence() {
  [[ -n "${EVIDENCE_FILE}" ]] || return 0
  local ts phase status message escaped_message
  ts="$(timestamp)"
  phase="$1"
  status="$2"
  message="$(sanitize_inline "$3")"
  escaped_message="$(json_escape "$message")"
  printf '{"timestamp":"%s","correlation_id":"%s","seam":"%s","phase":"%s","status":"%s","failure_class":"%s","message":"%s"}\n' \
    "$ts" "$(json_escape "$CORRELATION_ID")" "$(json_escape "$SEAM")" \
    "$(json_escape "$phase")" "$(json_escape "$status")" \
    "$(json_escape "$FAILURE_CLASS")" "$escaped_message" >>"$EVIDENCE_FILE"
}

log_phase() {
  local phase="$1"
  local status="$2"
  local message="$3"
  LAST_PHASE="$phase"
  local safe_message
  safe_message="$(sanitize_inline "$message")"
  printf '[%s] correlation_id=%s seam=%s phase=%s status=%s %s\n' \
    "$(timestamp)" "$CORRELATION_ID" "$SEAM" "$phase" "$status" "$safe_message"
  emit_evidence "$phase" "$status" "$safe_message"
}

fail_phase() {
  local phase="$1"
  local class="$2"
  local message="$3"
  local code="${4:-1}"
  FAILURE_CLASS="$class"
  log_phase "$phase" "failed" "failure_class=${class} remediation=${message}"
  exit "$code"
}

setup_workspace() {
  mkdir -p "$CERT_DIR" "$LOG_DIR" "$EVIDENCE_ROOT" "$DB_EVIDENCE_OUTPUT_DIR" "$SESSION_EVIDENCE_OUTPUT_DIR"
  chmod 700 "$RUNTIME_DIR" "$CERT_DIR" "$LOG_DIR" 2>/dev/null || true
  EVIDENCE_DIR="${EVIDENCE_ROOT}/${CORRELATION_ID}"
  mkdir -p "$EVIDENCE_DIR"
  EVIDENCE_FILE="${EVIDENCE_DIR}/runner-events.jsonl"
  : >"$EVIDENCE_FILE"
  log_phase "setup" "started" "workspace=runtime-scratch evidence=repo-local-sanitized project=${PROJECT_NAME} api_port=${API_PORT} postgres_port=${POSTGRES_PORT}"
}

require_command() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    fail_phase "setup" "missing-tool" "install ${tool} and retry; no services were started" 127
  fi
}

require_tools() {
  require_command docker
  require_command openssl
  require_command python3

  if ! docker compose version >"${LOG_DIR}/docker-compose-version.log" 2>&1; then
    fail_phase "setup" "missing-compose" "Docker Compose v2 is unavailable; no services were started" 127
  fi

  if ! docker info >"${LOG_DIR}/docker-info.log" 2>"${LOG_DIR}/docker-info.err"; then
    fail_phase "setup" "docker-unavailable" "Docker daemon is not reachable; no services were started" 1
  fi

  log_phase "setup" "ready" "required tools detected: docker compose openssl"
}

check_port_free() {
  local port="$1"
  local label="$2"
  if (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then
    fail_phase "setup" "port-collision" "${label} port ${port} is already accepting connections; choose another port" 1
  fi
}

rand_base64() {
  openssl rand -base64 "$1" | tr -d '\n'
}

rand_urlsafe() {
  rand_base64 "$1" | tr '+/' '-_'
}

generate_env() {
  local tmp_file
  tmp_file="${ENV_FILE}.tmp"

  local postgres_password app_db_password denied_password
  local security_secret csrf_secret fernet_key phi_key hash_salt
  local wuzapi_token webhook_secret gemini_key quiz_secret

  postgres_password="$(openssl rand -hex 32)"
  app_db_password="$(openssl rand -hex 32)"
  denied_password="$(openssl rand -hex 32)"
  security_secret="$(rand_urlsafe 64)"
  csrf_secret="$(rand_urlsafe 48)"
  fernet_key="$(rand_base64 32 | tr '+/' '-_')"
  phi_key="$(rand_base64 32)"
  hash_salt="$(rand_urlsafe 48)"
  wuzapi_token="$(rand_urlsafe 48)"
  webhook_secret="$(rand_urlsafe 48)"
  gemini_key="synthetic-gemini-$(openssl rand -hex 24)"
  quiz_secret="$(rand_urlsafe 48)"

  umask 077
  cat >"$tmp_file" <<EOF
# Generated by ${SCRIPT_REL} for synthetic M015 runtime only.
# This file is ignored by git and must never contain production credentials.
M015_COMPOSE_PROJECT_NAME=${PROJECT_NAME}
M015_CORRELATION_ID=${CORRELATION_ID}
M015_EVIDENCE_OUTPUT_DIR=/m015-evidence-output
M015_API_PORT=${API_PORT}
M015_POSTGRES_PORT=${POSTGRES_PORT}
M015_POSTGRES_IMAGE=postgres:16-alpine
M015_DRAGONFLY_IMAGE=docker.dragonflydb.io/dragonflydb/dragonfly:latest
M015_BACKEND_CONTEXT=../../../backend-hormonia
M015_POSTGRES_DB=m015_hormonia
M015_APP_DB_USER=hormonia_app
M015_RLS_DENIED_USER=m015_rls_denied
POSTGRES_DB=m015_hormonia
POSTGRES_USER=postgres
POSTGRES_PASSWORD=${postgres_password}
M015_APP_DB_PASSWORD=${app_db_password}
M015_RLS_DENIED_PASSWORD=${denied_password}
DATABASE_URL=postgresql+psycopg://hormonia_app:${app_db_password}@postgres:5432/m015_hormonia?sslmode=verify-full&sslrootcert=/m015-certs/ca.crt&ssl_min_protocol_version=TLSv1.2
M015_DATABASE_URL=postgresql+psycopg://hormonia_app:${app_db_password}@postgres:5432/m015_hormonia?sslmode=verify-full&sslrootcert=/m015-certs/ca.crt&ssl_min_protocol_version=TLSv1.2
M015_DATABASE_PSQL_CONN=host=postgres port=5432 dbname=m015_hormonia user=hormonia_app password=${app_db_password} sslmode=verify-full sslrootcert=/m015-certs/ca.crt ssl_min_protocol_version=TLSv1.2
M015_RLS_DENIED_PSQL_CONN=host=postgres port=5432 dbname=m015_hormonia user=m015_rls_denied password=${denied_password} sslmode=verify-full sslrootcert=/m015-certs/ca.crt ssl_min_protocol_version=TLSv1.2
REDIS_URL=redis://dragonfly:6379/0
REDIS_HOST=dragonfly
REDIS_PORT=6379
RATE_LIMIT_REDIS_URL=redis://dragonfly:6379/3
CELERY_BROKER_URL=redis://dragonfly:6379/0
CELERY_RESULT_BACKEND=redis://dragonfly:6379/1
TASKIQ_BROKER_URL=redis://dragonfly:6379/0
APP_ENVIRONMENT=production
APP_ENABLE_DEBUG=false
ALLOW_AI_SIMULATION=false
SESSION_ENABLE_COOKIE_SECURE=true
SESSION_ENABLE_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=lax
SESSION_COOKIE_NAME=session_id
SECURITY_ENABLE_SSL_REDIRECT=true
SECURITY_SECRET_KEY=${security_secret}
SECURITY_CSRF_SECRET_KEY=${csrf_secret}
ENCRYPTION_KEY_CURRENT=${fernet_key}
PHI_ENCRYPTION_KEY=${phi_key}
HASH_SALT=${hash_salt}
SECURITY_ALLOW_WEAK_KEYS=false
CORS_FRONTEND_URL=https://m015.localhost.invalid
CORS_QUIZ_URL=https://m015-quiz.localhost.invalid
CORS_ALLOWED_ORIGINS=["https://m015.localhost.invalid"]
FIREBASE_ALLOWED_DOMAINS=[]
WHATSAPP_ENABLE_SERVICE=false
WHATSAPP_WUZAPI_USE_MOCK=false
WHATSAPP_WUZAPI_TOKEN=${wuzapi_token}
WHATSAPP_WUZAPI_WEBHOOK_SECRET=${webhook_secret}
WHATSAPP_ENABLE_ON_REGISTRATION=false
WHATSAPP_ENABLE_WELCOME_MESSAGE=false
AI_GEMINI_API_KEY=${gemini_key}
AI_ENABLE_HUMANIZATION=false
AI_HUMANIZATION_ENABLE_FALLBACK=false
AI_LANGCHAIN_ENABLE_TRACING_V2=false
QUIZ_TOKEN_SECRET=${quiz_secret}
RATE_LIMIT_ENABLE_SERVICE=true
RATE_LIMIT_FAIL_CLOSED=true
REDIS_ENABLE_SERVICE=true
REDIS_ENABLE_SSL=false
LOGGING_LEVEL=INFO
LOGGING_ENABLE_REQUEST_LOGGING=false
LOGGING_ENABLE_STACK_TRACES=false
ERROR_ENABLE_TRACKING=false
MONITORING_ENABLE_SERVICE=false
MONITORING_ENABLE_DEBUG=false
UPLOAD_DIRECTORY=/tmp/hormonia-m015-public-uploads
EOF
  mv "$tmp_file" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  log_phase "setup" "ready" "generated synthetic env file with production-like posture and redacted secrets"
}

generate_certs() {
  log_phase "certs" "started" "generating local-only CA and postgres server certificate"
  rm -f "${CERT_DIR}"/ca.crt "${CERT_DIR}"/ca.key "${CERT_DIR}"/ca.srl \
        "${CERT_DIR}"/server.crt "${CERT_DIR}"/server.csr "${CERT_DIR}"/server.key \
        "${CERT_DIR}"/server-openssl.cnf

  cat >"${CERT_DIR}/server-openssl.cnf" <<'EOF'
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
CN = postgres

[v3_req]
subjectAltName = @alt_names
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = postgres
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

  if ! openssl req -x509 -newkey rsa:4096 -days 7 -nodes \
      -subj "/CN=M015 Synthetic Runtime CA" \
      -addext "basicConstraints=critical,CA:TRUE" \
      -addext "keyUsage=critical,keyCertSign,cRLSign" \
      -keyout "${CERT_DIR}/ca.key" \
      -out "${CERT_DIR}/ca.crt" \
      >"${LOG_DIR}/openssl-ca.log" 2>&1; then
    fail_phase "certs" "cert-generation" "failed to generate synthetic CA before service startup" 1
  fi

  if ! openssl req -new -nodes -newkey rsa:4096 \
      -keyout "${CERT_DIR}/server.key" \
      -out "${CERT_DIR}/server.csr" \
      -config "${CERT_DIR}/server-openssl.cnf" \
      >"${LOG_DIR}/openssl-server-csr.log" 2>&1; then
    fail_phase "certs" "cert-generation" "failed to generate synthetic postgres server CSR before service startup" 1
  fi

  if ! openssl x509 -req -days 7 \
      -in "${CERT_DIR}/server.csr" \
      -CA "${CERT_DIR}/ca.crt" \
      -CAkey "${CERT_DIR}/ca.key" \
      -CAcreateserial \
      -out "${CERT_DIR}/server.crt" \
      -extensions v3_req \
      -extfile "${CERT_DIR}/server-openssl.cnf" \
      >"${LOG_DIR}/openssl-server-sign.log" 2>&1; then
    fail_phase "certs" "cert-generation" "failed to sign synthetic postgres server certificate before service startup" 1
  fi

  chmod 600 "${CERT_DIR}/ca.key" "${CERT_DIR}/server.key"
  chmod 644 "${CERT_DIR}/ca.crt" "${CERT_DIR}/server.crt"
  log_phase "certs" "ready" "certificates created with SANs DNS:postgres DNS:localhost IP:127.0.0.1"
}

compose_cmd() {
  local args=(compose)
  if [[ -f "$ENV_FILE" ]]; then
    args+=(--env-file "$ENV_FILE")
  fi
  args+=(-p "$PROJECT_NAME" -f "$COMPOSE_FILE")
  docker "${args[@]}" "$@"
}

record_versions() {
  local docker_version compose_version openssl_version
  docker_version="$(docker version --format '{{.Server.Version}}' 2>/dev/null || printf 'unknown')"
  compose_version="$(docker compose version --short 2>/dev/null || printf 'unknown')"
  openssl_version="$(openssl version 2>/dev/null || printf 'unknown')"
  cat >"${EVIDENCE_DIR}/runtime-substrate.txt" <<EOF
correlation_id=${CORRELATION_ID}
seam=${SEAM}
project=${PROJECT_NAME}
docker_server_version=${docker_version}
docker_compose_version=${compose_version}
openssl_version=${openssl_version}
postgres_image=postgres:16-alpine
dragonfly_image=docker.dragonflydb.io/dragonflydb/dragonfly:latest
backend_context=backend-hormonia
database_url_policy=sslmode=verify-full,generated-ca-mount,tlsmin=TLSv1.2
redis_policy=dragonfly-local-no-auth-synthetic-network-only
provider_policy=no-live-provider-service-whatsapp-disabled
EOF
  log_phase "evidence" "recorded" "runtime substrate version manifest written without DSNs or secrets"
}

capture_failure_diagnostics() {
  [[ -n "$EVIDENCE_DIR" ]] || return 0
  {
    printf 'correlation_id=%s\n' "$CORRELATION_ID"
    printf 'seam=%s\n' "$SEAM"
    printf 'last_phase=%s\n' "$LAST_PHASE"
    printf 'failure_class=%s\n' "$FAILURE_CLASS"
    printf 'timestamp=%s\n' "$(timestamp)"
  } >"${EVIDENCE_DIR}/last-failure.txt"

  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    compose_cmd ps >"${EVIDENCE_DIR}/compose-ps.txt" 2>&1 || true
    compose_cmd logs --no-color --tail=120 postgres dragonfly api worker 2>&1 \
      | sanitize_stream >"${EVIDENCE_DIR}/compose-tail.log" || true
    log_phase "$LAST_PHASE" "diagnostics" "sanitized compose status/log tail saved under ${EVIDENCE_ROOT}/${CORRELATION_ID}"
  fi
}

update_teardown_result() {
  local result="$1"
  local note="$2"
  local evidence_json summary_md
  case "$SEAM" in
    db)
      evidence_json="$DB_EVIDENCE_JSON"
      summary_md="$DB_SUMMARY_MD"
      ;;
    session)
      evidence_json="$SESSION_EVIDENCE_JSON"
      summary_md="$SESSION_SUMMARY_MD"
      ;;
    *)
      return 0
      ;;
  esac
  [[ -f "$evidence_json" ]] || return 0
  python3 - "$evidence_json" "$summary_md" "$result" "$note" <<'PY'
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

helper_dir = Path("scripts/security/m015-runtime").resolve()
sys.path.insert(0, str(helper_dir))
from redaction import write_validated_json, write_validated_text  # noqa: E402

evidence_path = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
result = sys.argv[3]
note = sys.argv[4]
timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

data = json.loads(evidence_path.read_text(encoding="utf-8"))
data["teardown"] = {"result": result, "timestamp": timestamp, "notes": note}
write_validated_json(evidence_path, data)

if summary_path.exists():
    text = summary_path.read_text(encoding="utf-8")
    replacement = f"- Teardown: `{result}`"
    updated = re.sub(r"^- Teardown: `[^`]+`$", replacement, text, flags=re.MULTILINE)
    if updated == text:
        updated = text.rstrip() + f"\n\n## Runner Teardown\n\n- Result: `{result}`\n- Timestamp: `{timestamp}`\n- Note: {note}\n"
    write_validated_text(summary_path, updated)
PY
}

teardown_stack() {
  log_phase "teardown" "started" "compose down requested project=${PROJECT_NAME}"
  if compose_cmd down --volumes --remove-orphans >"${LOG_DIR}/compose-down.log" 2>&1; then
    STARTED="false"
    log_phase "teardown" "complete" "compose down completed idempotently"
    update_teardown_result "complete" "compose down completed idempotently" || \
      log_phase "evidence" "failed" "teardown evidence update failed redaction validation"
    return 0
  fi
  compose_cmd down --remove-orphans >>"${LOG_DIR}/compose-down.log" 2>&1 || true
  log_phase "teardown" "failed" "compose down returned non-zero; sanitized details available in runtime logs"
  update_teardown_result "failed" "compose down returned non-zero" || true
  return 1
}

on_exit() {
  local code=$?
  set +e
  if [[ $code -ne 0 ]]; then
    capture_failure_diagnostics
  fi
  if [[ "$STARTED" == "true" && "$KEEP_STACK" != "true" ]]; then
    if ! teardown_stack; then
      code=1
    fi
  elif [[ "$STARTED" == "true" && "$KEEP_STACK" == "true" ]]; then
    log_phase "teardown" "skipped" "--keep-stack set; run --seam ${SEAM} --project-name ${PROJECT_NAME} --teardown-only when done"
    update_teardown_result "skipped_keep_stack" "debug keep-stack was explicitly requested" || true
  fi
  exit "$code"
}

compose_up() {
  log_phase "compose" "started" "building and starting isolated services postgres dragonfly api worker"
  if ! compose_cmd up -d --build cert-init postgres dragonfly api worker >"${LOG_DIR}/compose-up.log" 2>&1; then
    fail_phase "compose" "compose-up" "docker compose up failed; inspect sanitized evidence and local compose logs" 1
  fi
  STARTED="true"
  compose_cmd ps >"${EVIDENCE_DIR}/compose-ps.txt" 2>&1 || true
  log_phase "compose" "ready" "services submitted to Docker Compose project=${PROJECT_NAME}"
}

retry_until() {
  local timeout_seconds="$1"
  local interval_seconds="$2"
  shift 2
  local deadline=$((SECONDS + timeout_seconds))
  while ((SECONDS < deadline)); do
    if "$@" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$interval_seconds"
  done
  "$@" >/dev/null 2>&1
}

postgres_tls_ready() {
  compose_cmd run --rm -T db-probe python -c \
    'import os, psycopg; conn=psycopg.connect(os.environ["M015_DATABASE_PSQL_CONN"], connect_timeout=5, application_name="m015_runner_tls_ready"); cur=conn.cursor(); cur.execute("select current_user"); raise SystemExit(0 if cur.fetchone()[0] == "hormonia_app" else 1)'
}

dragonfly_ready() {
  local pong
  pong="$(compose_cmd exec -T dragonfly redis-cli ping 2>/dev/null | tr -d '\r' || true)"
  [[ "$pong" == "PONG" ]]
}

api_health_ready() {
  compose_cmd exec -T api python -c \
    'import json, urllib.request; data=json.load(urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=3)); raise SystemExit(0 if data.get("status") == "healthy" else 1)'
}

worker_running() {
  local cid running
  cid="$(compose_cmd ps -q worker 2>/dev/null || true)"
  [[ -n "$cid" ]] || return 1
  running="$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null || true)"
  [[ "$running" == "true" ]]
}

wait_for_readiness() {
  log_phase "readiness" "started" "checking postgres TLS, dragonfly ping, api health, worker liveness"

  if ! retry_until 90 3 postgres_tls_ready; then
    fail_phase "readiness" "postgres-tls-timeout" "postgres TLS readiness timed out; verify certs, pg_hba, and port ${POSTGRES_PORT}" 1
  fi
  log_phase "readiness" "ready" "postgres accepted verify-full TLS connection for synthetic app role"

  if ! retry_until 60 2 dragonfly_ready; then
    fail_phase "readiness" "dragonfly-timeout" "dragonfly ping timed out" 1
  fi
  log_phase "readiness" "ready" "dragonfly responded to ping"

  if ! retry_until 120 3 api_health_ready; then
    fail_phase "readiness" "api-health-timeout" "FastAPI /health readiness timed out on port ${API_PORT}" 1
  fi
  log_phase "readiness" "ready" "FastAPI /health returned healthy"

  if ! retry_until 60 2 worker_running; then
    fail_phase "readiness" "worker-not-running" "worker process did not remain running" 1
  fi
  log_phase "readiness" "ready" "worker container is running"
}

run_db_probe() {
  log_phase "migrations" "started" "running DB seam probe for migrations, FastAPI DB readiness, TLS evidence, RLS allow/deny, and redacted artifacts"
  local probe_log failed_line failed_phase failed_class
  probe_log="${LOG_DIR}/db-probe.log"
  if compose_cmd run --rm -T db-probe >"$probe_log" 2>&1; then
    sanitize_stream <"$probe_log" >"${EVIDENCE_DIR}/db-probe.log"
    log_phase "migrations" "ready" "Alembic graph applied by DB seam probe"
    log_phase "tls" "ready" "DB seam probe recorded pg_stat_ssl protocol and cipher"
    log_phase "rls" "ready" "DB seam probe proved app-role allow and denied-role RLS block"
    log_phase "evidence" "ready" "DB seam evidence JSON and summary written with redaction validation"
    return 0
  fi

  sanitize_stream <"$probe_log" >"${EVIDENCE_DIR}/db-probe.log" || true
  failed_line="$(awk '/status=failed/ {line=$0} END {print line}' "${EVIDENCE_DIR}/db-probe.log" 2>/dev/null || true)"
  failed_phase="$(printf '%s' "$failed_line" | sed -E 's/.*phase=([^ ]+).*/\1/' 2>/dev/null || true)"
  failed_class="$(printf '%s' "$failed_line" | sed -E 's/.*failure_class=([^ ]+).*/\1/' 2>/dev/null || true)"
  [[ -n "$failed_phase" && "$failed_phase" != "$failed_line" ]] || failed_phase="evidence"
  [[ -n "$failed_class" && "$failed_class" != "$failed_line" ]] || failed_class="db-probe-failed"
  fail_phase "$failed_phase" "$failed_class" "DB seam probe failed; sanitized log saved under ${EVIDENCE_ROOT}/${CORRELATION_ID}/db-probe.log" 1
}

run_session_probe() {
  log_phase "session-probe" "started" "running session seam probe for cookie auth, cache fallback, revocation, and Taskiq worker DB re-check"
  local probe_log failed_line failed_phase failed_class
  probe_log="${LOG_DIR}/session-probe.log"
  if compose_cmd run --rm -T session-probe >"$probe_log" 2>&1; then
    sanitize_stream <"$probe_log" >"${EVIDENCE_DIR}/session-probe.log"
    log_phase "session-probe" "ready" "current cookie-backed synthetic session succeeded through FastAPI"
    log_phase "cache-fallback" "ready" "cache miss fell back to PostgreSQL and rehydrated Dragonfly"
    log_phase "revocation" "ready" "revoked and expired sessions failed closed and explicit revocation invalidated Dragonfly"
    log_phase "worker" "ready" "Taskiq worker denied queued work after PostgreSQL session re-check"
    log_phase "evidence" "ready" "session seam evidence JSON and summary written with redaction validation"
    return 0
  fi

  sanitize_stream <"$probe_log" >"${EVIDENCE_DIR}/session-probe.log" || true
  failed_line="$(awk '/status=failed/ {line=$0} END {print line}' "${EVIDENCE_DIR}/session-probe.log" 2>/dev/null || true)"
  failed_phase="$(printf '%s' "$failed_line" | sed -E 's/.*phase=([^ ]+).*/\1/' 2>/dev/null || true)"
  failed_class="$(printf '%s' "$failed_line" | sed -E 's/.*failure_class=([^ ]+).*/\1/' 2>/dev/null || true)"
  [[ -n "$failed_phase" && "$failed_phase" != "$failed_line" ]] || failed_phase="session-probe"
  [[ -n "$failed_class" && "$failed_class" != "$failed_line" ]] || failed_class="session-probe-failed"
  fail_phase "$failed_phase" "$failed_class" "Session seam probe failed; sanitized log saved under ${EVIDENCE_ROOT}/${CORRELATION_ID}/session-probe.log" 1
}

run_selected_seam() {
  if [[ -z "$PROJECT_NAME" ]]; then
    PROJECT_NAME="$(normalize_project_name "m015-runtime-${CORRELATION_ID}")"
  else
    PROJECT_NAME="$(normalize_project_name "$PROJECT_NAME")"
  fi

  trap on_exit EXIT
  setup_workspace
  require_tools

  if [[ "$TEARDOWN_ONLY" == "true" ]]; then
    teardown_stack
    return 0
  fi

  check_port_free "$API_PORT" "FastAPI"
  check_port_free "$POSTGRES_PORT" "PostgreSQL"
  generate_env
  generate_certs
  record_versions
  compose_up
  wait_for_readiness
  case "$SEAM" in
    db) run_db_probe ;;
    session) run_session_probe ;;
    *) fail_phase "setup" "unknown-seam" "unknown seam ${SEAM}" 64 ;;
  esac
}

main() {
  parse_args "$@"
  run_selected_seam
}

main "$@"
