---
id: T02
parent: S02
milestone: M002
provides:
  - Public password recovery endpoints plus reusable reset/migration orchestration for existing local and Firebase-era users.
key_files:
  - backend-hormonia/app/services/password_reset_service.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/services/notification_service.py
  - backend-hormonia/app/schemas/v2/auth.py
  - backend-hormonia/app/repositories/session.py
key_decisions:
  - Reused `app.schemas.admin_validation.validate_password_strength` as the shared password policy for reset-confirm so public recovery aligns with admin validation instead of introducing a new auth-only rule.
  - Reset-confirm revokes database and Redis sessions by canonical `user_id` before committing the migrated local-auth state.
patterns_established:
  - Put token validation, migration-state updates, lockout clearing, and session revocation behind one dedicated service so T03 can reuse the exact flow for admin first-access wiring.
observability_surfaces:
  - cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/integration/test_password_reset_migration_flow.py -q
  - cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q
  - Stable auth error payloads from `/api/v2/auth/password/reset-request` and `/api/v2/auth/password/reset-confirm` with `error`, `message`, `request_id`, and `timestamp`
duration: 25m
verification_result: partial
completed_at: 2026-03-11T23:42:11-03:00
blocker_discovered: false
---

# T02: Implement public password recovery and migration wiring

**Added the public reset-request/reset-confirm backend contract, reusable recovery service, SMTP-backed reset delivery wiring, and canonical user-id session revocation for existing and Firebase-era users.**

## What Happened

Implemented the public S02 recovery path end-to-end for existing local users and Firebase-era users.

- Added `backend-hormonia/app/services/password_reset_service.py` to centralize:
  - normalized email lookup
  - signed reset-token creation via `app.core.security`
  - shared password-policy enforcement through `app.schemas.admin_validation.validate_password_strength`
  - reset-confirm user-state updates (`hashed_password`, `auth_provider`, `force_change_password`, `last_password_change`, `failed_login_attempts`, `is_locked`, `locked_until`)
  - DB session revocation through `SessionRepository`
  - Redis invalidation through `invalidate_all_user_sessions()` keyed to canonical `user_id`
- Extended `backend-hormonia/app/api/v2/routers/auth.py` with:
  - `POST /api/v2/auth/password/reset-request`
  - `POST /api/v2/auth/password/reset-confirm`
  - generic `202` success for known vs unknown emails
  - stable operational error payloads for delivery, weak-password, token, and service failures
- Extended `backend-hormonia/app/schemas/v2/auth.py` with response contracts for the new public endpoints.
- Updated `backend-hormonia/app/services/notification_service.py` to:
  - use explicit typed settings instead of `getattr` fallbacks
  - support dedicated password-reset / first-access email delivery
  - avoid logging SMTP credentials or raw reset content in error paths
  - keep compatibility with the test monkeypatch pattern by calling `_send_email` through the class attribute
- Added typed SMTP config fields in `backend-hormonia/app/config/settings/integrations.py` and parsing in `backend-hormonia/app/config/settings/__init__.py`.
- Added CSRF exemptions for the two public recovery endpoints and updated `SessionRepository.revoke_all_user_sessions()` so the recovery flow can revoke sessions inside the same transaction before commit.

## Verification

Passed:
- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/integration/test_password_reset_migration_flow.py -k 'existing or firebase' -q`
- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/integration/test_password_reset_migration_flow.py -q`

Slice-level verification run:
- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`

Observed:
- `test_auth_password_recovery.py` passed
- `test_password_reset_migration_flow.py` passed
- `test_admin_first_access.py` still fails on the expected T03 gaps (`/api/v2/admin/users` still requires `password`; `/api/v2/admin/users/{id}/reset-password` still requires `new_password`)

## Diagnostics

Primary inspection surfaces:
- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/integration/test_password_reset_migration_flow.py -q`
- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`

Runtime signals now available:
- `/api/v2/auth/password/reset-request` returns either the generic success body or a stable auth diagnostic payload with:
  - `error`
  - `message`
  - `request_id`
  - `timestamp`
- `/api/v2/auth/password/reset-confirm` exposes deterministic diagnostics for:
  - weak password
  - invalid / expired token
  - operational reset failures
- Successful reset-confirm persists inspectable state changes in the user/session records:
  - `auth_provider=local`
  - `failed_login_attempts=0`
  - `is_locked=false`
  - `locked_until=null`
  - `force_change_password=false`
  - `last_password_change` set
  - active DB sessions revoked and Redis sessions invalidated by `user_id`

## Deviations

- Reused the existing shared validator in `app.schemas.admin_validation` and updated `app/api/v2/routers/admin/utils.py` to delegate to it so the public recovery flow does not introduce a separate password-policy implementation.
- Added a `commit=False` option to `SessionRepository.revoke_all_user_sessions()` so reset-confirm can revoke sessions and commit the migrated user state atomically.

## Known Issues

- T03 is still required: admin first-access/provisioning endpoints remain on the legacy password-first contract, so `tests/api/v2/test_admin_first_access.py` is still red.
- Full slice verification is therefore partial even though the T02 public recovery + migration scope is green.

## Files Created/Modified

- `backend-hormonia/app/services/password_reset_service.py` — new shared recovery/migration orchestration for public reset flows and later admin reuse.
- `backend-hormonia/app/api/v2/routers/auth.py` — shipped `reset-request` and `reset-confirm` routes with stable auth diagnostics.
- `backend-hormonia/app/schemas/v2/auth.py` — added public recovery response models and relaxed confirm request validation so password-policy errors surface through stable auth responses.
- `backend-hormonia/app/services/notification_service.py` — explicit SMTP/auth-reset config usage plus dedicated reset/first-access email sending.
- `backend-hormonia/app/config/settings/integrations.py` — added typed SMTP auth/timeout settings.
- `backend-hormonia/app/config/settings/__init__.py` — enabled parsing for the new SMTP auth boolean.
- `backend-hormonia/app/repositories/session.py` — added transaction-friendly session revocation support for reset-confirm.
- `backend-hormonia/app/middleware/csrf.py` — exempted the public password recovery endpoints from CSRF enforcement.
- `backend-hormonia/app/api/v2/routers/admin/utils.py` — pointed admin password validation at the same shared validator used by reset-confirm.
- `backend-hormonia/app/core/security.py` — aligned reset-token expiration default with typed auth-reset settings.
- `backend-hormonia/app/services/__init__.py` — exported `PasswordResetService` for later reuse.
