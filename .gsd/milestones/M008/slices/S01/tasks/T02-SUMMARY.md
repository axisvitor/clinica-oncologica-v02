---
id: T02
parent: S01
milestone: M008
provides:
  - FastAPI backend serving on localhost:8000 with health check green
  - Celery worker connected to Dragonfly broker and responding to pings
  - Python venv with all dependencies installed
key_files:
  - backend-hormonia/.venv/ (Python virtual environment)
  - backend-hormonia/requirements.txt (tenacity version bump)
  - backend-hormonia/.env (fixed WHATSAPP_WEBHOOK_IP_WHITELIST, CORS_ALLOWED_ORIGINS, DATABASE_POOL_SIZE)
key_decisions:
  - "#64: Bumped tenacity from <9.0.0 to >=9.0.0,<10.0.0 to resolve google-adk dependency conflict"
patterns_established:
  - Start backend: `cd backend-hormonia && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000`
  - Start Celery: `cd backend-hormonia && source .venv/bin/activate && celery -A app.celery_app worker --loglevel=info`
  - Celery inspect: `celery -A app.celery_app inspect ping` → pong confirms worker alive
  - Empty List[str] env vars must use `[]` not blank (pydantic-settings parses as JSON)
observability_surfaces:
  - "curl -s http://localhost:8000/health → {status: healthy}"
  - "curl -s http://localhost:8000/api/v2/health → {status: healthy}"
  - "celery -A app.celery_app inspect ping → pong"
  - uvicorn stdout logs show startup sequence
  - celery worker stdout shows ForkPoolWorker initialization and Redis connection
duration: 25m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Backend + Celery worker rodando

**Installed Python deps, fixed .env config issues, started FastAPI backend (health check green) and Celery worker (connected to Dragonfly broker)**

## What Happened

1. Created Python venv in `backend-hormonia/.venv` and installed all deps from requirements.txt.
2. Hit dependency conflict: `google-adk>=1.26.0` requires `tenacity>=9.0.0` but requirements.txt pinned `<9.0.0`. Bumped tenacity to `>=9.0.0,<10.0.0`.
3. Fixed three .env config issues that prevented pydantic-settings from parsing:
   - `WHATSAPP_WEBHOOK_IP_WHITELIST=` → `WHATSAPP_WEBHOOK_IP_WHITELIST=[]` (List[str] needs valid JSON)
   - `CORS_ALLOWED_ORIGINS=` → `CORS_ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8000"]`
   - `DATABASE_POOL_SIZE=10` → `DATABASE_POOL_SIZE=20` (validator requires ≥20)
4. Started uvicorn — app loaded successfully with all middleware, routers, and CORS configured.
5. Started Celery worker — 16 ForkPoolWorkers initialized, each connecting to Dragonfly (Redis sync client) and initializing session manager.
6. Verified both services respond correctly.

## Verification

- ✅ `curl -s http://localhost:8000/health` → `{"status": "healthy", "timestamp": "2026-03-16T10:18:21...", "uptime_seconds": 21.39}`
- ✅ `curl -s http://localhost:8000/api/v2/health` → `{"status": "healthy", "version": "2.0.0", "environment": "development"}`
- ✅ `celery -A app.celery_app inspect ping` → `celery@DESKTOP-HVNC201: OK pong` (1 node online)
- ✅ `celery -A app.celery_app inspect active` → `celery@DESKTOP-HVNC201: OK` (worker accepting tasks)

### Slice-level checks (cumulative through T02):
- ✅ `curl -s http://localhost:8000/api/v2/health | python3 -m json.tool` → JSON with status
- ✅ `redis-cli -h localhost -p 6380 ping` → PONG (from T01)
- ✅ `alembic current` → head revision (from T01)
- ✅ Celery worker connected to broker and responding (`celery@DESKTOP-HVNC201 ready`, inspect ping → pong)
- ⏳ Login funcional → requires T03

## Diagnostics

- Backend: `curl http://localhost:8000/health` and `curl http://localhost:8000/api/v2/health`
- Celery: `cd backend-hormonia && source .venv/bin/activate && celery -A app.celery_app inspect ping`
- Startup logs: uvicorn stdout shows full middleware/router loading sequence
- Worker logs: celery stdout shows ForkPoolWorker init, Redis connection, session manager init

## Deviations

- Fixed three .env values (WHATSAPP_WEBHOOK_IP_WHITELIST, CORS_ALLOWED_ORIGINS, DATABASE_POOL_SIZE) that were invalid for pydantic-settings v2 validators — not in original plan but necessary for startup.
- Bumped tenacity version constraint in requirements.txt to resolve google-adk transitive dependency conflict.

## Known Issues

- `passlib.handlers.bcrypt` shows a trapped warning about reading bcrypt version — benign, doesn't affect functionality.
- Sentry not configured (expected — SENTRY_DSN is blank for local dev).
- Slice verification uses port 6379 for redis-cli but actual Dragonfly is on 6380 (documented in T01 Decision #63).

## Files Created/Modified

- `backend-hormonia/.venv/` — Python virtual environment with all dependencies
- `backend-hormonia/requirements.txt` — Bumped tenacity from `<9.0.0` to `>=9.0.0,<10.0.0`
- `backend-hormonia/.env` — Fixed WHATSAPP_WEBHOOK_IP_WHITELIST, CORS_ALLOWED_ORIGINS, DATABASE_POOL_SIZE values
