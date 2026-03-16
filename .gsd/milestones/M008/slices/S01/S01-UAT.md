# S01: Stack local rodando — UAT

**Milestone:** M008
**Written:** 2026-03-16

## UAT Type

- UAT mode: live-runtime
- Why this mode is sufficient: S01 delivers running infrastructure — all verification is against live services, not artifacts

## Preconditions

1. Docker containers `dragonfly_oncologico` (port 6380) and `postgres-hormonia-test` (port 5434) are running
2. Database `hormonia_dev` exists on the Postgres container
3. `backend-hormonia/.env` is configured (created by T01)
4. Python venv exists at `backend-hormonia/.venv` with deps installed (created by T02)

To start services if not running:
```bash
# Backend
cd backend-hormonia && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Celery (separate terminal)
cd backend-hormonia && source .venv/bin/activate && celery -A app.celery_app worker --loglevel=info

# Seed admin (one-time, idempotent)
cd backend-hormonia && source .venv/bin/activate && python -m scripts.seed_admin_user
```

## Smoke Test

```bash
curl -s http://localhost:8000/api/v2/health | python3 -m json.tool
```
**Expected:** JSON with `"status": "healthy"` and `"version": "2.0.0"`

## Test Cases

### 1. Dragonfly responds to ping

1. Run: `redis-cli -h localhost -p 6380 ping`
2. **Expected:** `PONG`

### 2. PostgreSQL is accessible with hormonia_dev database

1. Run: `PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d hormonia_dev -c 'SELECT count(*) FROM information_schema.tables WHERE table_schema='\''public'\'''`
2. **Expected:** Count ≥ 32 (all tables present)

### 3. Alembic migrations at head

1. Run: `cd backend-hormonia && source .venv/bin/activate && DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5434/hormonia_dev" alembic current`
2. **Expected:** Output shows `m008_s01_t03_sessions_align (head)` — single linear head, no multiple heads or pending migrations

### 4. Backend health check — root endpoint

1. Run: `curl -s http://localhost:8000/health | python3 -m json.tool`
2. **Expected:** JSON with `"status": "healthy"`, `uptime_seconds` > 0, `"service": "hormonia-backend"`

### 5. Backend health check — v2 API endpoint

1. Run: `curl -s http://localhost:8000/api/v2/health | python3 -m json.tool`
2. **Expected:** JSON with `"status": "healthy"`, `"version": "2.0.0"`, `"environment": "development"`

### 6. Celery worker is alive and connected to broker

1. Run: `cd backend-hormonia && source .venv/bin/activate && celery -A app.celery_app inspect ping`
2. **Expected:** `celery@<hostname>: OK pong` with `1 node online`

### 7. Admin user exists in database

1. Run: `PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d hormonia_dev -c "SELECT email, role, is_active FROM users WHERE email='admin@hormonia.dev'"`
2. **Expected:** One row with `admin@hormonia.dev | admin | t`

### 8. Login flow works end-to-end

1. Run:
   ```bash
   curl -s http://localhost:8000/api/v2/auth/login \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"email":"admin@hormonia.dev","password":"Admin@1234"}' \
     | python3 -m json.tool
   ```
2. **Expected:** JSON with `"valid": true`, `"session_id"` present, `"user"` object with `"role": "admin"`, `"email": "admin@hormonia.dev"`

### 9. Session persisted in Dragonfly

1. After test 8, run: `redis-cli -h localhost -p 6380 keys '*session*'`
2. **Expected:** At least one `session:<uuid>` key listed

### 10. Session verification via cookie

1. Capture session_id from test 8
2. Run:
   ```bash
   curl -s http://localhost:8000/api/v2/auth/verify-session \
     -H 'Cookie: session_id=<session_id_from_step_8>' \
     | python3 -m json.tool
   ```
3. **Expected:** JSON with user payload including `"email": "admin@hormonia.dev"` and session metadata

## Edge Cases

### Login with wrong password

1. Run:
   ```bash
   curl -s http://localhost:8000/api/v2/auth/login \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"email":"admin@hormonia.dev","password":"wrong"}' \
     | python3 -m json.tool
   ```
2. **Expected:** Non-200 status or `"valid": false`. No session created.

### Verify session with invalid cookie

1. Run:
   ```bash
   curl -s http://localhost:8000/api/v2/auth/verify-session \
     -H 'Cookie: session_id=00000000-0000-0000-0000-000000000000' \
     | python3 -m json.tool
   ```
2. **Expected:** 401 or error response — invalid session not accepted.

### Seed script is idempotent

1. Run: `cd backend-hormonia && source .venv/bin/activate && python -m scripts.seed_admin_user`
2. **Expected:** Script completes without error. Output indicates user already exists (skipped). No duplicate user created.

## Failure Signals

- `curl localhost:8000/health` returns connection refused → backend not running
- `redis-cli -h localhost -p 6380 ping` returns connection refused → Dragonfly not running
- `psql` connection refused → Postgres container not running
- `alembic current` shows something other than `m008_s01_t03_sessions_align (head)` → migrations incomplete
- `celery inspect ping` returns "No nodes replied" → Celery worker not running or not connected to broker
- Login returns 503 with column errors → sessions migration not applied
- Login returns 401 → seed user not created or password wrong

## Requirements Proved By This UAT

- R067 (Stack local roda ponta-a-ponta) — Tests 1-10 prove all S01 components of R067: health checks, broker connectivity, schema state, admin login

## Not Proven By This UAT

- WuzAPI connectivity (S02 scope)
- Template seeding (S03 scope)
- Patient creation and welcome message (S04 scope)
- Response capture and phase transition (S05 scope)
- Celery beat schedule or periodic task execution — only worker liveness proven, not scheduled dispatch

## Notes for Tester

- **Port numbers matter:** Dragonfly is on **6380** (not 6379), Postgres on **5434** (not 5432). These differ from the slice plan's original examples.
- **passlib bcrypt warning** in Celery logs is benign — does not affect functionality.
- **Sentry warnings** ("SENTRY_DSN not configured") are expected for local dev.
- **Backend must be running** for tests 4-5 and 8-10. Start it first if not already running.
- **Celery must be running** for test 6. Start it in a separate terminal.
