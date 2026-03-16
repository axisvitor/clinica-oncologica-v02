---
id: S01
parent: M008
milestone: M008
provides:
  - FastAPI backend serving on localhost:8000 with health checks green
  - Celery worker connected to Dragonfly broker (localhost:6380) and responding to pings
  - PostgreSQL with hormonia_dev database on localhost:5434, schema at Alembic head
  - Dragonfly (Redis-compatible) on localhost:6380
  - Complete .env with all secrets, infra URLs, and feature flags
  - Admin/doctor seed user (admin@hormonia.dev) with functional login and session persistence
  - Sessions table aligned with Session ORM model via Alembic migration
requires: []
affects:
  - S02
  - S03
  - S04
key_files:
  - backend-hormonia/.env
  - backend-hormonia/requirements.txt
  - backend-hormonia/scripts/seed_admin_user.py
  - backend-hormonia/alembic/versions/m008_s01_t03_sessions_align.py
key_decisions:
  - "#63: Reuse existing Docker containers (dragonfly_oncologico:6380, postgres-hormonia-test:5434) instead of spinning up new ones"
  - "#64: Bumped tenacity from <9.0.0 to >=9.0.0,<10.0.0 to resolve google-adk dependency conflict"
  - "#65: Align sessions table with Session model via Alembic migration — added 14 missing columns required for login"
patterns_established:
  - "Local dev uses dragonfly_oncologico on port 6380 (not 6379) and postgres-hormonia-test on port 5434 (not 5432)"
  - "DATABASE_URL format: postgresql+psycopg://postgres:postgres@localhost:5434/hormonia_dev"
  - "REDIS_URL/CELERY_BROKER_URL use localhost:6380"
  - "Empty List[str] env vars must use `[]` not blank (pydantic-settings v2 parses as JSON)"
  - "DATABASE_POOL_SIZE must be ≥20 (pydantic validator enforces minimum)"
  - "Seed script: `cd backend-hormonia && source .venv/bin/activate && python -m scripts.seed_admin_user` — idempotent"
  - "Start backend: `cd backend-hormonia && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000`"
  - "Start Celery: `cd backend-hormonia && source .venv/bin/activate && celery -A app.celery_app worker --loglevel=info`"
observability_surfaces:
  - "curl -s http://localhost:8000/api/v2/health → {status: healthy, version: 2.0.0}"
  - "curl -s http://localhost:8000/health → {status: healthy, uptime_seconds: N}"
  - "redis-cli -h localhost -p 6380 ping → PONG"
  - "celery -A app.celery_app inspect ping → pong (1 node online)"
  - "POST /api/v2/auth/login with admin@hormonia.dev → valid:true + session cookie"
  - "GET /api/v2/auth/verify-session with cookie → session/user payload"
  - "alembic current → m008_s01_t03_sessions_align (head)"
drill_down_paths:
  - .gsd/milestones/M008/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M008/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M008/slices/S01/tasks/T03-SUMMARY.md
duration: 55m
verification_result: passed
completed_at: 2026-03-16
---

# S01: Stack local rodando

**Full local stack operational: FastAPI backend (health green), Celery worker (connected to Dragonfly broker), PostgreSQL (schema at Alembic head), admin user seeded with functional login and session persistence**

## What Happened

**T01 — Infrastructure setup (15m):** Discovered existing Docker containers already running — `dragonfly_oncologico` on port 6380 and `postgres-hormonia-test` on port 5434. Created dedicated `hormonia_dev` database on the Postgres container to isolate dev data. Generated secure random keys for all crypto env vars. Collected AI_GEMINI_API_KEY via secure_env_collect. Created complete `.env` from `.env.example` with all URLs pointing to local infra. Ran `alembic upgrade head` — all migrations applied cleanly, schema has 32 tables.

**T02 — Backend + Celery (25m):** Created Python venv and installed all dependencies. Hit a transitive dependency conflict: `google-adk>=1.26.0` needs `tenacity>=9.0.0` but requirements.txt pinned `<9.0.0` — bumped to `>=9.0.0,<10.0.0`. Fixed three .env values that were invalid for pydantic-settings v2: `WHATSAPP_WEBHOOK_IP_WHITELIST` needed `[]` (not blank), `CORS_ALLOWED_ORIGINS` needed valid JSON array, `DATABASE_POOL_SIZE` needed ≥20. Started uvicorn — both `/health` and `/api/v2/health` green. Started Celery worker — 16 ForkPoolWorkers initialized, each connecting to Dragonfly. Worker responds to `celery inspect ping` with pong.

**T03 — Admin seed + login (15m):** Created idempotent seed script that provisions `admin@hormonia.dev` with role=admin. Hit a schema gap: the Session ORM model defines 14 columns (session_token, refresh_token, expires_at, ip_address, user_agent, device_*, location, etc.) that didn't exist in the sessions table — login INSERT was failing with `column "session_token" does not exist`. Created Alembic migration `m008_s01_t03_sessions_align` to add all missing columns. After migration, login works end-to-end: POST returns session with cookie, session is persisted in Dragonfly, verify-session validates the cookie.

## Verification

All 6 slice-level checks from S01-PLAN pass:

- ✅ `curl -s http://localhost:8000/api/v2/health` → `{"status": "healthy", "version": "2.0.0", "environment": "development"}`
- ✅ `redis-cli -h localhost -p 6380 ping` → `PONG`
- ✅ `alembic current` → `m008_s01_t03_sessions_align (head)`
- ✅ `celery -A app.celery_app inspect ping` → `celery@DESKTOP-HVNC201: OK pong` (1 node online)
- ✅ `POST /api/v2/auth/login` with `admin@hormonia.dev` / `Admin@1234` → `{"valid": true, "session_id": "...", "user": {...}}`
- ✅ Session persisted in Dragonfly: `redis-cli keys *session*` → active sessions present

## Requirements Advanced

- R067 (Stack local roda ponta-a-ponta) — Stack is operational: backend serves health checks, Celery connects to broker, Postgres has schema at head, admin can login. WuzAPI not yet in scope (S02).

## Requirements Validated

- R067 — All S01 proof criteria met: health checks green, Celery worker connected, Alembic at head, .env configured, admin login functional with session persistence. The only remaining S01 criterion from the milestone definition ("WuzAPI") is scoped to S02, not S01.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- **Non-standard ports** (Decision #63): Dragonfly on 6380 (not 6379) and Postgres on 5434 (not 5432) because existing containers from other projects occupy the standard ports. All downstream slices must use these ports.
- **tenacity version bump** (Decision #64): requirements.txt pinned `<9.0.0` but google-adk needs `>=9.0.0`. Bumped to `>=9.0.0,<10.0.0`.
- **Sessions schema alignment** (Decision #65): Session ORM model had 14 columns not in the DB. Created an unplanned Alembic migration to make login work. This wasn't in the task plan but was a prerequisite discovery.
- **Pydantic-settings v2 strictness**: Three .env values needed fixing — empty List[str] fields need `[]` not blank, and DATABASE_POOL_SIZE has a minimum of 20. Not in plan but necessary for startup.

## Known Limitations

- WuzAPI is in mock mode (`WHATSAPP_WUZAPI_USE_MOCK=true`) — real WhatsApp connection is S02 scope.
- `passlib.handlers.bcrypt` emits a benign trapped warning about reading bcrypt version on Celery worker startup.
- Sentry is not configured (expected — SENTRY_DSN blank for local dev).
- Celery worker doesn't emit the exact `celery@<hostname> ready` log line expected by the plan — it silently finishes ForkPoolWorker init. Use `celery inspect ping` to verify worker liveness.

## Follow-ups

- S02 needs WuzAPI Docker container started and `.env` updated with real WHATSAPP_WUZAPI_BASE_URL and token.
- S03 depends on the Alembic head established here — `flow_kinds` and `flow_template_versions` tables are present.
- S04 needs both backend and Celery running simultaneously.

## Files Created/Modified

- `backend-hormonia/.env` — Complete local dev environment with all secrets, infra URLs, feature flags
- `backend-hormonia/requirements.txt` — tenacity version bump `>=9.0.0,<10.0.0`
- `backend-hormonia/scripts/__init__.py` — Package init for scripts module
- `backend-hormonia/scripts/seed_admin_user.py` — Idempotent admin/doctor seed script
- `backend-hormonia/alembic/versions/m008_s01_t03_sessions_align.py` — Migration aligning sessions table with Session ORM model

## Forward Intelligence

### What the next slice should know
- Ports are non-standard: Dragonfly on **6380**, Postgres on **5434**. Do not assume 6379/5432.
- The `.env` already exists and has `WHATSAPP_WUZAPI_USE_MOCK=true`. S02 just needs to flip that and set the real WuzAPI URL/token.
- Backend start command: `cd backend-hormonia && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Celery start command: `cd backend-hormonia && source .venv/bin/activate && celery -A app.celery_app worker --loglevel=info`
- Seed credentials (local dev only): `admin@hormonia.dev` / `Admin@1234`

### What's fragile
- `.env` parsing by pydantic-settings v2 is strict — List[str] fields need valid JSON (`[]`), not blank. Any new env var of list type will fail silently if left empty.
- The sessions migration (`m008_s01_t03_sessions_align`) added columns the ORM expects but the original schema didn't have. If there are other ORM model/table mismatches, they'll surface as column-not-found errors at runtime.

### Authoritative diagnostics
- `curl http://localhost:8000/api/v2/health` — single source of truth for backend liveness
- `celery -A app.celery_app inspect ping` — definitive Celery worker liveness check (don't rely on log parsing)
- `alembic current` — shows the exact migration head applied to the database
- `redis-cli -h localhost -p 6380 keys '*session*'` — shows active sessions in Dragonfly

### What assumptions changed
- Plan assumed standard ports (6379/5432) — actual infra uses 6380/5434 due to existing containers
- Plan assumed `alembic upgrade head` + startup would just work — actually needed a dependency bump, three .env fixes, and a schema alignment migration
- Plan assumed Celery logs show "ready" — actually the worker finishes init silently; use `inspect ping` instead
