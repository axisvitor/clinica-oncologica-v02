---
estimated_steps: 14
estimated_files: 5
skills_used: []
---

# T01: Make DB session state authoritative for cache hits and cache misses

Why: Product auth must not authorize stale Redis data after PostgreSQL says the session is revoked/expired, and it must recover active DB sessions after Redis cache miss without accepting header/Bearer transports.

Expected executor skills_used frontmatter: `tdd`, `security-review`, `verify-before-complete`.
Estimated scope: about 8 steps / 5 files.

Do:
1. Add `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py` cases for cache-hit DB validation, cache-miss DB fallback, revoked/expired DB denial, Redis timeout/error fallback, DB timeout/error fail-closed, inactive user denial, and cookie-only legacy transport rejection.
2. Extend `auth_session_cache.resolve_session_user_data()` so `not session_data` uses PostgreSQL fallback/rehydration instead of immediate 401, while no active DB session still returns 401.
3. Validate PostgreSQL session state before accepting Redis cache hits using `load_user_from_db_by_session(session_id)` or an equivalent callback that checks `is_active`, `revoked_at is null`, `expires_at > now`, and active user.
4. Preserve cookie-only staff auth in `auth_session_contract.py`; do not re-enable `X-Session-ID`, query `session_id`, or `Authorization: Bearer` as accepted staff-session transports.
5. Wire the validator/fallback through `auth_dependencies.get_current_user_from_session()` and map DB outages to fail-closed 503 diagnostics rather than stale authorization.
6. Bring `auth_session_shared.get_user_data_from_session()` to parity for direct helper users: cache hit validates DB session state, cache miss uses DB fallback, revoked/expired DB rows deny before embedded Redis user data is trusted.
7. Keep existing canonical identity behavior passing and avoid new raw session/cookie/password/email/DSN logs.

Failure Modes (Q5): Redis error/timeout -> PostgreSQL session fallback; Redis cache miss -> PostgreSQL session fallback; PostgreSQL timeout/error -> 503 fail closed; malformed session ID -> 401; inactive user -> 403; missing cookie with legacy headers only -> 401.
Load Profile (Q6): one narrow DB session-state query per authenticated cache hit plus optional Redis activity update/rehydration; at 10x load DB pool pressure breaks first, so avoid broad scans.
Negative Tests (Q7): stale Redis with revoked DB row, stale Redis with expired DB row, cache miss with active DB row, cache miss with revoked DB row, Redis timeout, DB timeout, inactive user, Bearer-only request, and `X-Session-ID`-only request.

## Inputs

- `backend-hormonia/app/dependencies/auth_session_cache.py`
- `backend-hormonia/app/dependencies/auth_session_contract.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/api/v2/auth_session_shared.py`
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`

## Expected Output

- `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py`
- `backend-hormonia/app/dependencies/auth_session_cache.py`
- `backend-hormonia/app/dependencies/auth_session_contract.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/api/v2/auth_session_shared.py`

## Verification

cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q

## Observability Impact

Strengthens auth diagnostics by distinguishing `redis_fallback`, `cache_miss_fallback`, `db_session_revoked`, `db_session_expired`, `db_unavailable`, and legacy transport rejection in safe logs/tests without exposing session material.
