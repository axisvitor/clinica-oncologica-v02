---
estimated_steps: 4
estimated_files: 3
---

# T01: Add failing recovery and first-access proof suites

**Slice:** S02 — Account Recovery And Migration
**Milestone:** M002

## Description

Create the slice proof suite before changing production code so S02 is driven by the exact backend contract for existing-user recovery, email reset, admin-created first access, and inspectable failure paths.

## Steps

1. Add API tests in `backend-hormonia/tests/api/v2/test_auth_password_recovery.py` covering generic `reset-request` success, no email-enumeration for unknown accounts, reset-email dispatch, weak-password rejection, invalid/expired-token handling, and redacted auth diagnostics.
2. Add API tests in `backend-hormonia/tests/api/v2/test_admin_first_access.py` covering passwordless admin provisioning and admin-triggered recovery on the new first-access contract, including assertions that responses do not return plaintext temporary passwords.
3. Add an integration flow in `backend-hormonia/tests/integration/test_password_reset_migration_flow.py` that seeds a Firebase-era user and an admin-created user, exercises reset-request/reset-confirm, verifies user state transitions plus DB + Redis session revocation, and then logs in through the S01 local-auth contract.
4. Run the three suites, tighten assertions until failures isolate missing recovery wiring rather than broken fixtures, and leave them red for the implementation tasks.

## Must-Haves

- [ ] The public recovery suite pins a non-enumerating `POST /api/v2/auth/password/reset-request` contract and at least one stable failure-path signal (`error`, `request_id`, or equivalent).
- [ ] The integration suite asserts that reset-confirm revokes sessions by canonical `user_id` in both the session table and Redis cache.
- [ ] The admin suite proves admin-created first-access users recover through the same reset-confirm path as existing users.
- [ ] The tests explicitly reject plaintext temporary-password responses so the old backend pattern cannot quietly return.

## Verification

- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`
- Confirm the failures point at missing recovery/migration behavior, not at missing fixtures, imports, or unrelated legacy routes.

## Observability Impact

- Signals added/changed: The tests lock in redacted auth diagnostics, email-delivery failure visibility, and session-revocation assertions as required outputs.
- How a future agent inspects this: Run the three pytest files directly to see whether the regression is in the public auth contract, admin provisioning contract, or the assembled migration flow.
- Failure state exposed: Missing token generation, weak-password handling, SMTP wiring, user-state updates, or DB/Redis revocation drift show up as named assertions tied to one boundary each.

## Inputs

- `backend-hormonia/app/api/v2/routers/auth.py` — current auth surface where the new password reset endpoints will live.
- `backend-hormonia/app/api/v2/routers/admin/users.py` and `backend-hormonia/app/api/v2/routers/admin/actions.py` — current admin create/reset behavior that still assumes direct password handling.
- `backend-hormonia/tests/api/v2/test_auth_local_login.py` and `backend-hormonia/tests/integration/test_local_auth_core_flow.py` — the downstream S01 local-login contract the new recovery flow must hand back to.

## Expected Output

- `backend-hormonia/tests/api/v2/test_auth_password_recovery.py` — failing public recovery contract coverage for S02.
- `backend-hormonia/tests/api/v2/test_admin_first_access.py` — failing admin provisioning/recovery contract coverage.
- `backend-hormonia/tests/integration/test_password_reset_migration_flow.py` — failing end-to-end migration flow coverage for existing and admin-created users.
