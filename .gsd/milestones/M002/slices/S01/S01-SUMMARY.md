---
id: S01
parent: M002
milestone: M002
provides:
  - first-party backend email/password login at POST /api/v2/auth/login with canonical DB + Redis + HttpOnly session issuance
  - session-backed verify-session, logout, and protected-route auth using canonical user_id identity instead of firebase_uid on the happy path
  - stable auth failure diagnostics with error codes plus request_id/debug-step visibility
requires: []
affects:
  - M002/S02
  - M002/S03
  - M002/S04
key_files:
  - backend-hormonia/app/services/auth.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - backend-hormonia/app/api/v2/user_cache_shared.py
  - backend-hormonia/app/core/redis_manager/session_cache.py
  - backend-hormonia/app/api/v2/router.py
  - backend-hormonia/app/api/v2/routers/debug/auth.py
  - backend-hormonia/tests/api/v2/test_auth_local_login.py
  - backend-hormonia/tests/unit/test_auth_session_identity_contract.py
  - backend-hormonia/tests/integration/test_local_auth_core_flow.py
key_decisions:
  - reuse the existing Session row plus Redis session cache instead of introducing a parallel local-auth token mechanism
  - make user_id the canonical session identity and keep firebase_uid as compatibility-only metadata
  - expose canonical authenticated-user endpoints under /api/v2/users/* while keeping hidden /api/v2/auth/* aliases during the cutover
patterns_established:
  - auth contract tests must assert stable error codes and redact password, hash, and raw session-secret material from responses
  - session-backed auth should hydrate users from embedded session payload or user_id cache/DB lookup before any Firebase compatibility fallback
  - admin debug login diagnostics should return stable auth error codes plus ordered step lists instead of opaque pass/fail
observability_surfaces:
  - cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py -q
  - POST /api/v2/auth/login
  - GET /api/v2/auth/verify-session
  - DELETE /api/v2/auth/logout
  - POST /api/v2/debug/auth/test-login
drill_down_paths:
  - .gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T03-SUMMARY.md
duration: 2h30m
verification_result: passed
completed_at: 2026-03-11T22:05:11-03:00
---

# S01: Local Auth Core

**First-party backend login now issues the canonical Redis + HttpOnly session and all focused auth-core verification is green on the user_id-centric session contract.**

## What Happened

S01 started by pinning the cutover with three red suites: the canonical local login API contract, the session-identity dependency contract, and an integration flow covering login → `/api/v2/users/me` → logout. Those tests made the real gaps explicit: `/api/v2/auth/login` still expected Firebase-shaped input, session auth still treated `firebase_uid` as mandatory on the happy path, and protected routes still would not accept a session-backed identity on its own.

The implementation work then replaced the backend login path with first-party email/password authentication while preserving the existing DB-session + Redis-session + HttpOnly-cookie architecture. Local auth schemas and service helpers were added, the canonical `/api/v2/auth/login` endpoint was rewired to authenticate against `users.hashed_password`, successful logins now create the database session row plus Redis session payload, and the returned user/session envelope is normalized for downstream frontend consumption.

The session/auth cutover then moved the happy path to canonical `user_id` identity. Redis session payloads and shared user-cache helpers now resolve by `user_id` first, with `firebase_uid` retained only as compatibility metadata. `get_current_user_from_session()` and the shared auth/session helpers now accept embedded canonical user data or user-id cache/DB lookup without forcing Firebase token verification. This made `verify-session`, protected-route access, and logout all work from the same local session contract.

Slice closeout fixed the remaining regressions that still blocked green verification: `LocalAuthFailure` now initializes correctly instead of collapsing into `503`, invalid-credential responses use the stable redacted message `Invalid credentials`, failed-attempt tracking falls back cleanly when the test Redis double lacks atomic counter methods, the canonical authenticated-user router is mounted at `/api/v2/users/*` while `/api/v2/auth/*` remains as a hidden legacy alias, and the admin debug login probe now reports stable auth error codes plus ordered local-auth step diagnostics.

## Verification

Verified with:

- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py -q`
- `cd backend-hormonia && python3 -m py_compile app/api/v2/routers/debug/auth.py app/schemas/v2/debug.py app/services/auth.py app/api/v2/router.py`

Observed result:

- all 9 focused S01 auth-core tests passed
- login success returns the canonical session cookie and normalized user/session payload
- invalid credentials and inactive-account failures return stable structured diagnostics without password leakage
- session-backed auth reaches `GET /api/v2/users/me` without Firebase token exchange
- logout revokes both DB and Redis session state on the same contract

## Requirements Advanced

- R005 — The backend staff login path is now first-party email/password instead of Firebase token exchange on the normal API path.
- R006 — The existing Redis + HttpOnly session model now works on the first-party identity contract for login, verify-session, protected-route auth, and logout.
- R012 — The auth core now exposes stable failure diagnostics (`error`, `request_id`, debug-step lists) instead of opaque auth failures.

## Requirements Validated

- none

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

Kept `/api/v2/auth/*` aliases for authenticated-user profile endpoints as hidden compatibility routes while exposing the canonical `/api/v2/users/*` surface required by the slice contract. This avoids breaking current callers before S03 completes the frontend cutover.

## Known Limitations

- Password reset / first-access flows are not part of S01 and remain for S02.
- Frontend dashboard and realtime bootstrap still depend on Firebase SDK/token-era behavior until S03.
- Firebase compatibility paths such as `/firebase/verify` and legacy aliases still exist; the hard cut is not complete until S04.

## Follow-ups

- Build S02 reset-request / reset-confirm flows and admin-created-account first-access handling on top of the shipped local auth core.
- Move frontend/session bootstrap code in S03 to the canonical session-backed contract and decide when legacy `/api/v2/auth/*` profile aliases can be removed.
- Remove remaining Firebase Auth compatibility/runtime paths in S04 after downstream consumers are cut over.

## Files Created/Modified

- `backend-hormonia/tests/api/v2/test_auth_local_login.py` — contract coverage for local login success/failure, cookie issuance, verify-session, and logout.
- `backend-hormonia/tests/unit/test_auth_session_identity_contract.py` — unit coverage for user-id-centric session auth and session-first dependency resolution.
- `backend-hormonia/tests/integration/test_local_auth_core_flow.py` — integration coverage for login → protected route → logout with DB + Redis invalidation assertions.
- `backend-hormonia/app/schemas/v2/auth.py` — local login request/response schemas and normalized authenticated-user envelope.
- `backend-hormonia/app/services/auth.py` — local credential verification, failed-attempt handling, lock-state enforcement, and canonical session TTL helpers.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical `/api/v2/auth/login`, verify-session, logout, and stable auth error payload helpers.
- `backend-hormonia/app/core/redis_manager/session_cache.py` — canonical session payload support with optional compatibility `firebase_uid`.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — session-to-user resolution on embedded user data or canonical `user_id` lookup.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — dual-key cache helpers for canonical `user_id` and compatibility `firebase_uid` lookups.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — session-first current-user resolution without Firebase dependency on the happy path.
- `backend-hormonia/app/api/v2/router.py` — canonical `/api/v2/users/*` router mount plus hidden legacy `/api/v2/auth/*` alias.
- `backend-hormonia/app/api/v2/routers/debug/auth.py` — debug login diagnostics aligned to first-party local-auth error codes and step reporting.

## Forward Intelligence

### What the next slice should know
- The core local-auth/session contract is now stable: S02 can build reset and first-access flows against the canonical `/api/v2/auth/login`, `/api/v2/auth/verify-session`, `/api/v2/auth/logout`, and `/api/v2/users/me` behavior without preserving Firebase happy-path assumptions.

### What's fragile
- Frontend callers still using `/api/v2/auth/me` are surviving only because of the hidden alias — S03 needs to cut over deliberately and then remove the compatibility surface in S04.
- Auth diagnostics are now structured, but request IDs are still best-effort and depend on upstream middleware/header propagation.

### Authoritative diagnostics
- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py -q` — this is the authoritative proof that the S01 contract is still intact.
- `POST /api/v2/debug/auth/test-login` — this is the fastest admin-only surface for seeing which local-auth step failed without creating a real session.

### What assumptions changed
- The old assumption that authenticated-user routes lived only under `/api/v2/auth/*` changed — the canonical slice contract now lives under `/api/v2/users/*`, with the `/auth/*` path intentionally retained only as a temporary hidden alias.
