---
estimated_steps: 5
estimated_files: 6
---

# T03: Cut session dependencies over to the new identity contract

**Slice:** S01 — Local Auth Core
**Milestone:** M002

## Description

Move the happy-path auth contract from `firebase_uid`-centric session resolution to a canonical local session identity so verify-session, logout, and protected routes actually run on the first-party model introduced in T02.

## Steps

1. Update `backend-hormonia/app/core/redis_manager/session_cache.py` so session payloads store canonical user identity data (`user_id` plus the minimal cached user envelope), keeping `firebase_uid` optional for compatibility instead of required for happy-path resolution.
2. Refactor `backend-hormonia/app/api/v2/auth_session_shared.py` and `backend-hormonia/app/api/v2/user_cache_shared.py` so shared session-auth helpers can fetch/cache active users from the canonical session identity contract instead of assuming `firebase_uid` lookup.
3. Change `backend-hormonia/app/dependencies/auth_dependencies.py` to resolve session-backed users from the new payload, and make `get_current_user` / `get_current_active_user` honor that session-backed path before any Firebase-specific fallback.
4. Align `backend-hormonia/app/api/v2/routers/auth.py` and `backend-hormonia/app/api/v2/routers/debug/auth.py` with the new contract so `verify-session`, `logout`, and debug login diagnostics all report the same first-party session semantics and stable failure signals.
5. Run the full auth-core suite until login → `GET /api/v2/users/me` → logout passes end to end and the diagnostic assertions stay green.

## Must-Haves

- [ ] Session validation and protected-route resolution succeed when Redis session data has no `firebase_uid` on the happy path.
- [ ] `get_current_user` / `get_current_active_user` no longer force Firebase token verification for session-backed requests.
- [ ] `verify-session` and `logout` use the same canonical session identity data emitted at login, with DB and Redis invalidation staying coherent.
- [ ] Debug / failure diagnostics expose enough information to distinguish invalid session, inactive user, and credential problems without leaking secrets.

## Verification

- `cd backend-hormonia && pytest tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_local_login.py -q`
- Confirm the integration test reaches `GET /api/v2/users/me` after login using only the session cookie, then fails `verify-session` after logout.

## Observability Impact

- Signals added/changed: Session-backed auth failures now surface as deterministic error codes / debug steps tied to the canonical session contract.
- How a future agent inspects this: Use the unit/integration suites, `GET /api/v2/auth/verify-session`, or admin-only `POST /api/v2/debug/auth/test-login` to see whether the break is in session lookup, user resolution, or session invalidation.
- Failure state exposed: Invalid-session, inactive-user, and protected-route resolution failures localize to a specific boundary instead of collapsing into generic Firebase auth errors.

## Inputs

- `backend-hormonia/app/api/v2/routers/users.py` — existing protected route used as the slice’s proof endpoint.
- `backend-hormonia/tests/unit/test_auth_session_identity_contract.py` and `backend-hormonia/tests/integration/test_local_auth_core_flow.py` — failing proofs that define the new identity contract and route-level behavior.

## Expected Output

- `backend-hormonia/app/dependencies/auth_dependencies.py` — session-first user resolution on the canonical contract.
- `backend-hormonia/app/api/v2/auth_session_shared.py` and `backend-hormonia/app/api/v2/user_cache_shared.py` — shared helpers aligned with user-id-centric sessions.
- `backend-hormonia/app/core/redis_manager/session_cache.py` / `backend-hormonia/app/api/v2/routers/auth.py` / `backend-hormonia/app/api/v2/routers/debug/auth.py` — session storage, auth endpoints, and diagnostics all speaking the same local-auth contract.
