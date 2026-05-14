---
estimated_steps: 13
estimated_files: 5
skills_used: []
---

# T02: Invalidate Redis on explicit session revocation

Why: `/api/v2/users/sessions/{session_id}` currently updates the DB row but can leave `session:<id>` in Dragonfly. It must invalidate cache at the revocation boundary, while DB revocation remains the hard fail-closed source if cache deletion fails.

Expected executor skills_used frontmatter: `tdd`, `security-review`, `verify-before-complete`.
Estimated scope: about 6 steps / 5 files.

Do:
1. Extend `test_m015_s02_session_runtime_contract.py` for user-initiated revocation: DB state changes, Redis cache is invalidated, and subsequent profile access with the same cookie fails closed.
2. Move/extract `_invalidate_session_cache` from `auth.py` into `backend-hormonia/app/dependencies/auth_session_invalidation.py` to avoid router import cycles.
3. Support wrapper methods (`invalidate_session`, `delete_session`) and raw Redis clients; raw fallback must delete the actual `session:{session_id}` key used by `session_cache.py` (and may also delete the raw ID for compatibility).
4. Update `auth.py` logout/logout-all imports to use the shared helper without changing public responses.
5. Update `users.py` `revoke_session()` to depend on `get_redis_cache`, invalidate after DB commit, and return the existing response shape without raw cache details.
6. If cache invalidation fails after DB commit, log a sanitized warning and rely on T01 DB validation so later requests still deny.

Failure Modes (Q5): Redis unavailable -> DB revocation remains authoritative; invalid/foreign session -> no cache side effect; helper signature mismatch -> try next method; DB commit failure -> no invalidation success claim.
Load Profile (Q6): one targeted cache delete per revoked session; at 10x revocation load Dragonfly latency and DB commits break first, so avoid broad scans for single-session revoke.
Negative Tests (Q7): missing session row, foreign session row, raw Redis `delete`, wrapper `invalidate_session`, cache exception, and direct-DB stale cache denial.

## Inputs

- `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/api/v2/routers/users.py`
- `backend-hormonia/app/core/redis_manager/session_cache.py`

## Expected Output

- `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py`
- `backend-hormonia/app/dependencies/auth_session_invalidation.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/api/v2/routers/users.py`

## Verification

cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/api/v2/test_auth.py -q

## Observability Impact

Adds a shared cache-invalidation seam and sanitized cache failure warnings while keeping PostgreSQL revocation as the hard authorization source.
