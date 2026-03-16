---
id: T03
parent: S01
milestone: M008
provides:
  - Admin/doctor seed user (admin@hormonia.dev) in database for local auth
  - Functional login via POST /api/v2/auth/login returning session with cookie
  - Session persisted in Dragonfly (Redis-compatible cache)
  - Alembic migration aligning sessions table with Session ORM model
key_files:
  - backend-hormonia/scripts/seed_admin_user.py
  - backend-hormonia/alembic/versions/m008_s01_t03_sessions_align.py
key_decisions:
  - "#65: Align sessions table with Session model via Alembic migration — added missing columns (session_token, expires_at, ip_address, etc.)"
patterns_established:
  - "Seed script pattern: `cd backend-hormonia && source .venv/bin/activate && python -m scripts.seed_admin_user` — idempotent, skips if user exists"
  - "Seed credentials (local dev only): email=admin@hormonia.dev password=Admin@1234 role=admin"
observability_surfaces:
  - "POST /api/v2/auth/login — returns session_id, user payload, sets session_id cookie"
  - "GET /api/v2/auth/verify-session — validates session via cookie"
  - "redis-cli -h localhost -p 6380 keys '*session*' — shows active sessions in Dragonfly"
  - "PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d hormonia_dev -c 'SELECT id, email, role FROM users' — seed user in DB"
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T03: Usuário admin/médico seed e login funcional

**Created admin/doctor seed user, aligned sessions schema, and verified full login → session → verify-session flow against live stack**

## What Happened

1. **Explored auth system**: Read auth router, AuthService, User model, Session model, and password hashing to understand the login flow.

2. **Created seed script** (`backend-hormonia/scripts/seed_admin_user.py`): Idempotent script that creates an admin user (`admin@hormonia.dev` / `Admin@1234`) with role=admin, auth_provider=local, specialty=Oncologia. Re-running skips creation; fixes missing password or locked state if found.

3. **Ran seed script**: User created successfully (id=8e53a8f6-d17f-47e8-8d98-aae3f6be4eee).

4. **Hit login failure**: First login attempt returned 503 with `column "session_token" of relation "sessions" does not exist`. The Session ORM model defines 14+ columns (session_token, refresh_token, expires_at, ip_address, user_agent, device_*, location, revoked_at, revocation_reason, is_suspicious, risk_score, session_metadata) that were never added to the database table.

5. **Created Alembic migration** (`m008_s01_t03_sessions_align`): Added all missing columns with proper types, indexes, and backfill logic for existing rows. Applied with `alembic upgrade head`.

6. **Verified login**: POST /api/v2/auth/login returns 200 with valid=true, session_id, user payload, and set-cookie header. Session persisted in Dragonfly. verify-session endpoint works with cookie.

## Verification

All slice-level checks passing:

- ✅ `curl -s http://localhost:8000/api/v2/health | python3 -m json.tool` → `{"status": "healthy", ...}`
- ✅ `redis-cli -h localhost -p 6380 ping` → PONG
- ✅ `alembic current` → `m008_s01_t03_sessions_align (head)`
- ⏭️ Celery worker ready — verified in T02 (not re-started in T03 scope)
- ✅ `POST /api/v2/auth/login` with seed credentials → `{"valid": true, "session_id": "...", "user": {...}}`
- ✅ Session cookie set: `set-cookie: session_id=...; HttpOnly; Max-Age=432000; Path=/; SameSite=lax`
- ✅ Session persisted in Dragonfly: `redis-cli keys *session*` → `session:<uuid>`
- ✅ `GET /api/v2/auth/verify-session` with cookie → returns full session/user payload

## Diagnostics

- **Seed user**: `PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d hormonia_dev -c "SELECT id, email, role, is_active FROM users"`
- **Active sessions**: `redis-cli -h localhost -p 6380 keys '*session*'`
- **Session detail**: `redis-cli -h localhost -p 6380 get 'session:<session_id>'`
- **Login test**: `curl -s http://localhost:8000/api/v2/auth/login -X POST -H 'Content-Type: application/json' -d '{"email":"admin@hormonia.dev","password":"Admin@1234"}' | python3 -m json.tool`
- **Session verify**: `curl -s http://localhost:8000/api/v2/auth/verify-session -H 'Cookie: session_id=<session_id>' | python3 -m json.tool`

## Deviations

- **Added Alembic migration** (not in task plan): The sessions table was missing 14 columns the Session model expects. Created `m008_s01_t03_sessions_align` migration to align DB schema. This was necessary for login to work — not a plan change but a prerequisite discovery.

## Known Issues

- None

## Files Created/Modified

- `backend-hormonia/scripts/__init__.py` — Package init for scripts module
- `backend-hormonia/scripts/seed_admin_user.py` — Idempotent seed script for admin/doctor user
- `backend-hormonia/alembic/versions/m008_s01_t03_sessions_align.py` — Migration aligning sessions table with Session ORM model
