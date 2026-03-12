# S02: Account Recovery And Migration

**Goal:** Ship secure email-backed recovery and first-access flows so existing and newly admin-created staff users can set a first-party password without Firebase Auth or manual account recreation.
**Demo:** A Firebase-era user with `hashed_password=None` and a newly admin-created user both receive a reset/activation email, complete `POST /api/v2/auth/password/reset-confirm`, have prior sessions revoked, and then log in through S01’s local auth contract; `POST /api/v2/auth/password/reset-request` never reveals whether an email exists, and the new backend-first admin provisioning path no longer depends on plaintext temporary passwords as the canonical recovery contract.

## Must-Haves

- `POST /api/v2/auth/password/reset-request` accepts `{ email }`, returns a generic non-enumerating success response, generates a signed reset/first-access token for eligible users, and dispatches email through typed SMTP-backed notification settings with stable operational diagnostics.
- `POST /api/v2/auth/password/reset-confirm` verifies the signed token, enforces one shared password-strength rule, sets a local password, migrates Firebase-era users onto the local provider contract, clears lockout state, updates password-change markers, and revokes all active DB + Redis sessions by canonical `user_id`.
- Admin-created accounts can be provisioned into first-access state and admin-triggered recovery reuses the same email-backed flow instead of treating plaintext temporary passwords as the canonical backend path.
- Focused verification proves existing users, Firebase-era users, and admin-created users can all recover through the same backend contract while failure paths stay inspectable and redacted.

## Proof Level

- This slice proves: integration (with focused contract coverage on public recovery endpoints, admin provisioning/recovery, and migration-state/session invalidation behavior)
- Real runtime required: no
- Human/UAT required: no

## Verification

- `backend-hormonia/tests/api/v2/test_auth_password_recovery.py` — reset-request/reset-confirm contract, non-enumeration, password-policy enforcement, token failure diagnostics, and email dispatch behavior.
- `backend-hormonia/tests/api/v2/test_admin_first_access.py` — admin create/reset contract for first-access provisioning and email-backed recovery without plaintext temporary-password responses.
- `backend-hormonia/tests/integration/test_password_reset_migration_flow.py` — Firebase-era user and admin-created user complete reset-confirm, lose prior sessions in DB + Redis, and then log in through the S01 local-auth contract.
- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`

## Observability / Diagnostics

- Runtime signals: reset-request/reset-confirm and admin first-access flows emit stable auth error codes plus `request_id`, and record request/completion outcomes in audit/log surfaces without exposing raw tokens or passwords.
- Inspection surfaces: the focused pytest suites above, auth/admin JSON responses, user/session DB state, and notification-service logs for delivery failures.
- Failure visibility: invalid or expired token, weak-password rejection, SMTP misconfiguration/delivery failure, and session-revocation issues surface deterministic error payloads or persisted state changes rather than opaque 500s.
- Redaction constraints: never return or log account-existence hints, plaintext passwords, raw reset tokens, session secrets, or SMTP credentials.

## Integration Closure

- Upstream surfaces consumed: `backend-hormonia/app/core/security.py`, `backend-hormonia/app/services/auth.py`, `backend-hormonia/app/core/redis_manager/session_cache.py`, `backend-hormonia/app/repositories/session.py`, `backend-hormonia/app/services/notification_service.py`, `backend-hormonia/app/api/v2/routers/admin/users.py`, and `backend-hormonia/app/api/v2/routers/admin/actions.py`.
- New wiring introduced in this slice: public `reset-request` → signed token generation → SMTP notification; `reset-confirm` → shared password validation → user migration-state update → DB + Redis session revocation; admin create/reset flows → the same first-access/recovery service instead of standalone password generation.
- What remains before the milestone is truly usable end-to-end: frontend forgot-password/reset pages and admin SPA cutover in S03, then Firebase Auth runtime removal and final integrated proof in S04.

## Tasks

- [x] **T01: Add failing recovery and first-access proof suites** `est:50m`
  - Why: Lock R007/R008/R009 against the exact reset/migration behavior S02 must ship before production code changes start drifting.
  - Files: `backend-hormonia/tests/api/v2/test_auth_password_recovery.py`, `backend-hormonia/tests/api/v2/test_admin_first_access.py`, `backend-hormonia/tests/integration/test_password_reset_migration_flow.py`
  - Do: Create focused pytest coverage for non-enumerating reset-request responses, token/email dispatch behavior, weak-password and invalid-token diagnostics, migration state transitions, canonical DB + Redis session revocation, and admin-created first-access users completing the same recovery path without plaintext temporary-password responses.
  - Verify: `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`
  - Done when: the new suites exist and fail only because the recovery/migration contract has not been implemented yet.
- [x] **T02: Implement public password recovery and migration wiring** `est:1h20m`
  - Why: Existing and Firebase-era users cannot recover access until the public reset endpoints, shared password policy, session revocation, and deliverable email path are real.
  - Files: `backend-hormonia/app/services/password_reset_service.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/schemas/v2/auth.py`, `backend-hormonia/app/schemas/admin_validation.py`, `backend-hormonia/app/services/notification_service.py`, `backend-hormonia/app/config/settings/integrations.py`, `backend-hormonia/app/config/settings/__init__.py`
  - Do: Add a reusable password-reset service, wire `POST /api/v2/auth/password/reset-request` and `POST /api/v2/auth/password/reset-confirm` with generic success plus stable diagnostics, reuse one shared password-strength validator, update user migration/lockout fields on successful confirm, revoke all DB + Redis sessions by canonical `user_id`, and make SMTP settings/mail delivery explicitly configurable instead of implicit `getattr` fallbacks.
  - Verify: `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/integration/test_password_reset_migration_flow.py -k 'existing or firebase' -q`
  - Done when: existing users and Firebase-era users can request/reset through the new auth routes in tests, and public recovery failures are inspectable without leaking account existence or secrets.
- [x] **T03: Wire admin provisioning onto the first-access recovery contract** `est:1h10m`
  - Why: R008 is not satisfied until admin-created accounts use the same recoverable email-backed path instead of bespoke temporary-password handling.
  - Files: `backend-hormonia/app/schemas/v2/admin.py`, `backend-hormonia/app/api/v2/routers/admin/users.py`, `backend-hormonia/app/api/v2/routers/admin/actions.py`, `backend-hormonia/app/services/password_reset_service.py`, `backend-hormonia/tests/api/v2/test_admin_first_access.py`, `backend-hormonia/tests/integration/test_password_reset_migration_flow.py`
  - Do: Update admin create/reset contracts to support first-access provisioning and email-backed recovery, reuse the shared reset service from T02 so admin-created users enter a coherent first-access state, stop returning plaintext temporary passwords from the canonical backend path, and keep the compatibility boundary explicit for the still-unmigrated admin SPA until S03.
  - Verify: `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`
  - Done when: a newly admin-created user can complete reset-confirm and then log in locally in the integration suite, and no planned admin recovery response exposes a plaintext temporary password.

## Files Likely Touched

- `backend-hormonia/app/services/password_reset_service.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/schemas/v2/auth.py`
- `backend-hormonia/app/schemas/admin_validation.py`
- `backend-hormonia/app/schemas/v2/admin.py`
- `backend-hormonia/app/api/v2/routers/admin/users.py`
- `backend-hormonia/app/api/v2/routers/admin/actions.py`
- `backend-hormonia/app/services/notification_service.py`
- `backend-hormonia/app/config/settings/integrations.py`
- `backend-hormonia/app/config/settings/__init__.py`
- `backend-hormonia/tests/api/v2/test_auth_password_recovery.py`
- `backend-hormonia/tests/api/v2/test_admin_first_access.py`
- `backend-hormonia/tests/integration/test_password_reset_migration_flow.py`
