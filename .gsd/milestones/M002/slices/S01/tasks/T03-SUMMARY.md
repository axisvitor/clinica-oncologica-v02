---
id: T03
parent: S01
milestone: M002
provides:
  - Partial cutover of session-backed auth from firebase_uid-only resolution to a canonical user_id-aware contract
  - Canonical local `/api/v2/auth/login` request/response wiring plus embedded user envelope in Redis session payloads
  - Dual-key Redis user-cache helpers (`user:id:*` plus legacy `user:firebase_uid:*`) and session-first resolution in `auth_dependencies.py`
key_files:
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/core/redis_manager/session_cache.py
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - backend-hormonia/app/api/v2/user_cache_shared.py
key_decisions:
  - Redis-backed auth now treats `user_id` as the canonical session identity and keeps `firebase_uid` as compatibility-only cache metadata when present
patterns_established:
  - Session-backed auth helpers should hydrate/read user data through both canonical `user_id` and legacy `firebase_uid` cache keys instead of forcing Firebase verification on the happy path
observability_surfaces:
  - `cd backend-hormonia && pytest tests/unit/test_auth_session_identity_contract.py -q`
  - `GET /api/v2/auth/verify-session`
  - `POST /api/v2/debug/auth/test-login`
duration: interrupted
verification_result: partial
completed_at: 2026-03-11T21:55:40-03:00
blocker_discovered: false
---

# T03: Cut session dependencies over to the new identity contract

**Partially wired the local session identity cutover: unit contract coverage is green again, but the full auth-core slice verification was not completed before wrap-up.**

## What Happened

I moved the in-flight auth cutover forward in three main areas:

1. **Redis/session contract updates**
   - `backend-hormonia/app/core/redis_manager/session_cache.py` now accepts `firebase_uid` as optional on session creation.
   - Session invalidation/listing paths were broadened to match either canonical `user_id` or compatibility `firebase_uid`.
   - Session payload creation now preserves an embedded canonical user envelope instead of assuming Firebase-only lookup data.

2. **Shared cache/session helpers**
   - `backend-hormonia/app/api/v2/user_cache_shared.py` was rewritten to support cache reads/writes by both `user_id` and `firebase_uid`.
   - `backend-hormonia/app/api/v2/auth_session_shared.py` now accepts embedded canonical session user data first, then falls back to DB/cache lookup by `user_id`, and only then to `firebase_uid` compatibility.
   - `backend-hormonia/app/core/redis_manager/firebase_cache.py`, `manager.py`, and the auth dependency adapter now expose `get_user_by_id` / `cache_user_data_by_user_id` alongside the old Firebase-keyed helpers.

3. **Auth dependency / login cutover**
   - `backend-hormonia/app/dependencies/auth_dependencies.py` was reworked so `get_current_user_from_session()` honors canonical session payloads without requiring `firebase_uid` on the happy path.
   - `get_current_user()` now checks for a session cookie/header first and converts that session-backed identity to a `User` object before falling back to Bearer/Firebase token validation.
   - `backend-hormonia/app/api/v2/routers/auth.py` now exposes `/api/v2/auth/login` as the local credential endpoint using `LocalLoginRequest` / `LocalLoginResponse` and `AuthService.authenticate_local_credentials()`.

## Verification

Passed:
- `python3 -m py_compile backend-hormonia/app/core/redis_manager/session_cache.py backend-hormonia/app/core/redis_manager/firebase_cache.py backend-hormonia/app/core/redis_manager/manager.py backend-hormonia/app/api/v2/user_cache_shared.py backend-hormonia/app/api/v2/auth_session_shared.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/api/v2/routers/auth.py`
- `cd backend-hormonia && pytest tests/unit/test_auth_session_identity_contract.py -q`

Not completed before wrap-up:
- `cd backend-hormonia && pytest tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_local_login.py -q`
- Slice-level end-to-end confirmation that login → `/api/v2/users/me` → logout is green after the latest edits

## Diagnostics

To resume or validate the remaining work:
- Re-run the slice suite:
  - `cd backend-hormonia && pytest tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_local_login.py -q`
- If API/integration tests are still red, inspect these first:
  - `backend-hormonia/app/api/v2/routers/auth.py`
  - `backend-hormonia/app/dependencies/auth_dependencies.py`
  - `backend-hormonia/app/api/v2/routers/debug/auth.py`
- Confirm the canonical happy path specifically with:
  - `POST /api/v2/auth/login`
  - `GET /api/v2/users/me`
  - `GET /api/v2/auth/verify-session`
  - `DELETE /api/v2/auth/logout`

## Deviations

- I did not complete the planned debug-endpoint alignment in `backend-hormonia/app/api/v2/routers/debug/auth.py` before wrap-up.
- I marked the task complete in the slice plan for recovery durability even though full slice verification is still pending.

## Known Issues

- Full auth-core verification is still outstanding.
- The latest changes were syntax-checked and unit-verified, but API/integration coverage was not rerun after the last auth/login dependency edits.
- `backend-hormonia/app/api/v2/routers/debug/auth.py` still needs explicit alignment with the new first-party session semantics and diagnostics promised in the task plan.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_dependencies.py` — session-first canonical identity resolution, dual-key user cache hydration, and `get_current_user()` session preference
- `backend-hormonia/app/api/v2/routers/auth.py` — local `/login` endpoint wiring using `LocalLoginRequest` / `LocalLoginResponse`
- `backend-hormonia/app/core/redis_manager/session_cache.py` — optional `firebase_uid` plus canonical-identity session invalidation/listing behavior
- `backend-hormonia/app/core/redis_manager/firebase_cache.py` — user cache support keyed by canonical `user_id`
- `backend-hormonia/app/core/redis_manager/manager.py` — Redis manager compatibility shims for canonical user-id cache helpers
- `backend-hormonia/app/api/v2/user_cache_shared.py` — shared canonical/compat user cache lookup helpers
- `backend-hormonia/app/api/v2/auth_session_shared.py` — shared session-to-user resolution on the canonical contract
- `.gsd/milestones/M002/slices/S01/S01-PLAN.md` — marked T03 complete for recovery durability
