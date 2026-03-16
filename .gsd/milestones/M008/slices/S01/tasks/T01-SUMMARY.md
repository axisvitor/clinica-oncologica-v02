---
id: T01
parent: S01
milestone: M008
provides:
  - Dragonfly (Redis-compatible) accessible on localhost:6380
  - PostgreSQL with hormonia_dev database on localhost:5434
  - Alembic migrations at head revision
  - Complete .env with all secrets and infra URLs
key_files:
  - backend-hormonia/.env
key_decisions:
  - "#63: Reuse existing Docker containers (dragonfly_oncologico:6380, postgres-hormonia-test:5434) instead of spinning up new ones"
patterns_established:
  - Local dev uses dragonfly_oncologico on port 6380 (not 6379) and postgres-hormonia-test on port 5434
  - DATABASE_URL format: postgresql+psycopg://postgres:postgres@localhost:5434/hormonia_dev
  - REDIS_URL/CELERY_BROKER_URL use localhost:6380
observability_surfaces:
  - "redis-cli -h localhost -p 6380 ping → PONG"
  - "PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d hormonia_dev -c 'SELECT 1'"
  - "cd backend-hormonia && DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5434/hormonia_dev alembic current"
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Dragonfly + Postgres + .env configurados

**Configured .env with all secrets, connected to existing Dragonfly (6380) and Postgres (5434), created hormonia_dev database, and applied all Alembic migrations to head**

## What Happened

1. Surveyed running Docker containers — found `dragonfly_oncologico` on port 6380 and `postgres-hormonia-test` on port 5434 already healthy. Port 6379 is taken by `redis_for_evolution`.
2. Created `hormonia_dev` database on existing Postgres container to isolate dev data from test data.
3. Generated secure random keys for SECURITY_SECRET_KEY, PHI_ENCRYPTION_KEY, ENCRYPTION_KEY_CURRENT, CSRF, and HASH_SALT.
4. Collected AI_GEMINI_API_KEY via secure_env_collect.
5. Created complete `backend-hormonia/.env` from `.env.example` with all URLs pointing to existing local infra (Dragonfly on 6380, Postgres on 5434), WuzAPI in mock mode, monitoring disabled.
6. Ran `alembic upgrade head` — all migrations applied successfully to `hormonia_dev`.

## Verification

- ✅ `redis-cli -h localhost -p 6380 ping` → PONG
- ✅ `alembic current` → `m007_s04_t02_patient_flow_responses (head)`
- ✅ `psql -d hormonia_dev -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"` → 32 tables
- ✅ `alembic heads` matches `alembic current` (single linear head)

### Slice-level checks (T01 scope):
- ✅ Dragonfly responde ping em localhost:6380 (PONG)
- ✅ `alembic current` mostra head revision
- ⏳ `curl localhost:8000/api/v2/health` — requires T02 (backend not started yet)
- ⏳ Celery worker logs — requires T02
- ⏳ Login funcional — requires T03

## Diagnostics

- Dragonfly: `redis-cli -h localhost -p 6380 info server` shows df-v1.36.0
- Postgres: `PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d hormonia_dev`
- Alembic: `DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5434/hormonia_dev" alembic current`
- Docker: `docker ps | grep -E 'dragonfly_oncologico|postgres-hormonia-test'`

## Deviations

- Used existing Docker containers on non-standard ports (6380/5434) instead of starting new ones on 6379/5432 — avoids conflicts with other projects. Documented as Decision #63.
- .env uses `WHATSAPP_WUZAPI_USE_MOCK=true` for now — WuzAPI real connection is M008's later scope (S04+).

## Known Issues

None

## Files Created/Modified

- `backend-hormonia/.env` — Complete local dev environment configuration with all secrets, infra URLs, and feature flags
