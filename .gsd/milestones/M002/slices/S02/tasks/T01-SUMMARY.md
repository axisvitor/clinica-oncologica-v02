---
id: T01
parent: S02
milestone: M002
provides:
  - Red proof suites for public password recovery, admin first-access, and migration/session-revocation behavior.
key_files:
  - backend-hormonia/tests/api/v2/test_auth_password_recovery.py
  - backend-hormonia/tests/api/v2/test_admin_first_access.py
  - backend-hormonia/tests/integration/test_password_reset_migration_flow.py
key_decisions:
  - Lock S02 to `/api/v2/auth/password/reset-request` and `/api/v2/auth/password/reset-confirm` with generic reset-request success, stable auth diagnostics, canonical `user_id` revocation, and no plaintext temporary-password responses.
patterns_established:
  - Add focused red contract suites before implementation so missing auth/admin wiring fails at one boundary each instead of through broad end-to-end breakage.
observability_surfaces:
  - `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`
duration: 55m
verification_result: partial
completed_at: 2026-03-11T22:45:00-03:00
blocker_discovered: false
---

# T01: Add failing recovery and first-access proof suites

**Added the three red proof suites that define S02’s recovery, first-access, and migration/session-revocation contract.**

## What Happened

Created the three planned pytest files and pinned the intended S02 backend contract before implementation work starts.

- `test_auth_password_recovery.py` locks public recovery to:
  - `POST /api/v2/auth/password/reset-request` returning a generic non-enumerating success response
  - redacted delivery-failure diagnostics
  - weak-password rejection on reset-confirm
  - invalid/expired token diagnostics with stable `error` + `request_id` style assertions
- `test_admin_first_access.py` locks admin provisioning/recovery to:
  - passwordless first-access creation
  - admin-triggered recovery returning delivery metadata instead of plaintext passwords
  - admin-created users completing the same public reset-confirm path and then logging in through S01 local auth
- `test_password_reset_migration_flow.py` locks the integration path to:
  - Firebase-era and admin-created users resetting through the same confirm flow
  - migration to local auth state
  - DB session revocation plus Redis invalidation by canonical `user_id`
  - successful local login after reset

The first verification run produced the intended contract failures for the missing implementation:
- public recovery tests failed with `404` because `/api/v2/auth/password/reset-request` and `/api/v2/auth/password/reset-confirm` do not exist yet
- admin first-access tests failed with `422` because admin create/reset still require password-first payloads
- integration tests initially failed on CSRF instead of the recovery contract, so I added a `_csrf_headers()` helper to the integration suite to keep future reruns focused on recovery wiring rather than middleware noise

## Verification

Ran:
- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`

Observed before timeout:
- 6 failures from missing public recovery routes (`404`)
- 3 failures from admin schema mismatch (`422` requiring `password` / `new_password`)
- 2 integration failures caused by missing CSRF headers (`403`), then patched by adding `_csrf_headers()` in the integration suite

Status:
- The proof suites exist and are red against the missing S02 behavior.
- The final full-suite rerun after the CSRF helper patch was not completed before timeout, so verification is recorded as partial.

## Diagnostics

Primary inspection surface:
- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`

How to read failures:
- `test_auth_password_recovery.py` -> public auth contract/wiring
- `test_admin_first_access.py` -> admin provisioning/reset contract shift away from plaintext passwords
- `test_password_reset_migration_flow.py` -> migration state transition + DB/Redis revocation + local login handoff

Important note for the next agent:
- rerun the three suites first to confirm the integration suite now fails on recovery implementation rather than CSRF middleware

## Deviations

- Added an integration-only `_csrf_headers()` helper after the first verification run exposed a middleware failure that was unrelated to the intended S02 recovery contract.

## Known Issues

- Full verification was not rerun after the CSRF helper patch, so the latest recorded pytest output still includes the pre-patch integration `403` failures.

## Files Created/Modified

- `backend-hormonia/tests/api/v2/test_auth_password_recovery.py` — red contract coverage for reset-request/reset-confirm, non-enumeration, redacted diagnostics, and token/password failure paths.
- `backend-hormonia/tests/api/v2/test_admin_first_access.py` — red admin provisioning/recovery contract coverage that rejects plaintext temporary-password responses.
- `backend-hormonia/tests/integration/test_password_reset_migration_flow.py` — red migration flow coverage for Firebase-era and admin-created users, canonical `user_id` revocation assertions, and local-login handoff.
