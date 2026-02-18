#!/usr/bin/env bash
set -euo pipefail

# Run backend components with explicit environment split:
# - Oncologico system in staging mode
# - Evolution API local and real (no mock)
export APP_ENVIRONMENT="${APP_ENVIRONMENT:-staging}"
export WHATSAPP_EVOLUTION_USE_MOCK="${WHATSAPP_EVOLUTION_USE_MOCK:-false}"
export WHATSAPP_EVOLUTION_API_URL="${WHATSAPP_EVOLUTION_API_URL:-http://127.0.0.1:8080}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

if [[ -d "${VENV_DIR}" ]]; then
  export PATH="${VENV_DIR}/bin:${PATH}"
fi

UVICORN_BIN="${VENV_DIR}/bin/uvicorn"
CELERY_BIN="${VENV_DIR}/bin/celery"

if [[ ! -x "${UVICORN_BIN}" ]]; then
  UVICORN_BIN="uvicorn"
fi

if [[ ! -x "${CELERY_BIN}" ]]; then
  CELERY_BIN="celery"
fi

role="${1:-api}"

echo "APP_ENVIRONMENT=${APP_ENVIRONMENT}"
echo "WHATSAPP_EVOLUTION_USE_MOCK=${WHATSAPP_EVOLUTION_USE_MOCK}"
echo "WHATSAPP_EVOLUTION_API_URL=${WHATSAPP_EVOLUTION_API_URL}"
echo "ROLE=${role}"
echo "UVICORN_BIN=${UVICORN_BIN}"
echo "CELERY_BIN=${CELERY_BIN}"

case "${role}" in
  api)
    exec "${UVICORN_BIN}" app.main:app --host 0.0.0.0 --port 8000 --reload
    ;;
  worker)
    exec "${CELERY_BIN}" -A app.celery_app worker --loglevel=info
    ;;
  beat)
    exec "${CELERY_BIN}" -A app.celery_app beat --loglevel=info
    ;;
  *)
    echo "Usage: $0 [api|worker|beat]" >&2
    exit 1
    ;;
esac
