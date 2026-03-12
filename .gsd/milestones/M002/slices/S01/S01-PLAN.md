# S01: Local Auth Core

**Goal:** Ship first-party email/password login plus session verification, logout, and protected-route auth on a local session identity contract.
**Demo:** A staff user with a locally stored password logs in through `POST /api/v2/auth/login`, receives the canonical HttpOnly session cookie, can call `GET /api/v2/auth/verify-session` and `GET /api/v2/users/me` without Firebase token exchange, and failed auth returns inspectable error codes without leaking secrets.

## Must-Haves

- `POST /api/v2/auth/login` authenticates local email/password against `users.hashed_password`, enforces active/lock state, issues the canonical DB + Redis session, and returns normalized user/session metadata for frontend consumption.
- `GET /api/v2/auth/verify-session` and `DELETE /api/v2/auth/logout` work from the first-party session contract without requiring `firebase_uid` on the happy path.
- `auth_dependencies.py` resolves authenticated users from canonical session identity data so protected routes can authorize session-backed requests without Firebase token verification.
- Auth failure paths expose stable diagnostics (`error`, `request_id`, or debug-step signal) while keeping passwords, hashes, and raw session secrets out of responses/logs.

## Proof Level

- This slice proves: integration (with focused contract coverage on auth API and dependency surfaces)
- Real runtime required: no
- Human/UAT required: no

## Verification

- `backend-hormonia/tests/api/v2/test_auth_local_login.py` — local login, verify-session, logout, cookie contract, and failure diagnostics.
- `backend-hormonia/tests/unit/test_auth_session_identity_contract.py` — user-id-centric session payload and auth dependency resolution without `firebase_uid` on the happy path.
- `backend-hormonia/tests/integration/test_local_auth_core_flow.py` — login → protected route (`/api/v2/users/me`) → logout with DB + Redis session invalidation.
- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py -q`

## Observability / Diagnostics

- Runtime signals: standardized auth error payloads use stable `error` codes plus `request_id`, and the admin-only debug login probe records local-auth step outcomes instead of opaque pass/fail.
- Inspection surfaces: `POST /api/v2/debug/auth/test-login`, `GET /api/v2/auth/verify-session`, and the new focused pytest suites.
- Failure visibility: invalid-credentials, inactive/locked-account, and invalid-session paths expose a deterministic error code / debug step instead of generic 500s.
- Redaction constraints: never return or log plaintext passwords, `hashed_password`, full session tokens, or raw Redis payloads.

## Integration Closure

- Upstream surfaces consumed: `backend-hormonia/app/models/user.py`, `backend-hormonia/app/models/session.py`, `backend-hormonia/app/repositories/user.py`, `backend-hormonia/app/core/redis_manager/session_cache.py`, `backend-hormonia/app/api/v2/routers/users.py`.
- New wiring introduced in this slice: `POST /api/v2/auth/login` → local credential verification in `AuthService` → session row + Redis cache write → session-backed resolution in `auth_dependencies.py` / shared auth helpers → `verify-session`, `users/me`, and `logout` on the same contract.
- What remains before the milestone is truly usable end-to-end: password reset / first-access flows, admin-created account activation, frontend and websocket cutover, and Firebase Auth runtime cleanup.

## Tasks

- [x] **T01: Add failing local-auth contract tests** `est:45m`
  - Why: Lock R005/R006 against the exact login/session/protected-route behavior S01 must ship before changing the auth stack.
  - Files: `backend-hormonia/tests/api/v2/test_auth_local_login.py`, `backend-hormonia/tests/unit/test_auth_session_identity_contract.py`, `backend-hormonia/tests/integration/test_local_auth_core_flow.py`
  - Do: Create focused pytest coverage for local email/password login, normalized session/user response shape, HttpOnly cookie issuance, session-backed protected-route access, logout invalidation, and inspectable auth failure responses; reuse existing test user and Redis/session fixtures instead of inventing parallel scaffolding.
  - Verify: `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py -q`
  - Done when: the new suites exist and fail only because the local-auth/session-identity contract has not been implemented yet.
- [x] **T02: Implement local login and canonical session issuance** `est:1h15m`
  - Why: Replace the canonical v2 login path with first-party email/password while preserving the Redis + HttpOnly session model the milestone keeps.
  - Files: `backend-hormonia/app/services/auth.py`, `backend-hormonia/app/schemas/v2/auth.py`, `backend-hormonia/app/api/v2/routers/auth.py`
  - Do: Add local-login request/response models (including remember-me intent), implement credential verification plus active/lock handling in `AuthService`, reset/record failed attempts, and issue DB + Redis sessions plus normalized response/cookie headers from `POST /api/v2/auth/login`; keep `/firebase/verify` explicitly compatibility-only for later removal.
  - Verify: `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py -q`
  - Done when: local login success/failure contract tests pass and responses never leak password material.
- [x] **T03: Cut session dependencies over to the new identity contract** `est:1h20m`
  - Why: The slice is not real until verify-session, logout, and protected routes can authorize a local session without depending on `firebase_uid`-centric happy-path resolution.
  - Files: `backend-hormonia/app/core/redis_manager/session_cache.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`, `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/v2/routers/debug/auth.py`
  - Do: Make Redis session payloads user-id-centric with compat-only optional `firebase_uid`, update shared auth helpers to fetch/cache users from canonical session identity data, make `get_current_user_from_session` and `get_current_user` honor session-backed auth on the happy path, align `verify-session`/`logout` with that payload, and expose stable failure diagnostics via error codes plus debug login steps without secret leakage.
  - Verify: `cd backend-hormonia && pytest tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_local_login.py -q`
  - Done when: all planned auth-core suites pass and a locally authenticated user can reach `GET /api/v2/users/me` using only the session cookie.

## Files Likely Touched

- `backend-hormonia/app/services/auth.py`
- `backend-hormonia/app/schemas/v2/auth.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/core/redis_manager/session_cache.py`
- `backend-hormonia/app/api/v2/auth_session_shared.py`
- `backend-hormonia/app/api/v2/user_cache_shared.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/api/v2/routers/debug/auth.py`
- `backend-hormonia/tests/api/v2/test_auth_local_login.py`
- `backend-hormonia/tests/unit/test_auth_session_identity_contract.py`
- `backend-hormonia/tests/integration/test_local_auth_core_flow.py`
