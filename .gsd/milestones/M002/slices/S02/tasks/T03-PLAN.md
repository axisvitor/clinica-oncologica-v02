---
estimated_steps: 4
estimated_files: 6
---

# T03: Wire admin provisioning onto the first-access recovery contract

**Slice:** S02 — Account Recovery And Migration
**Milestone:** M002

## Description

Extend the shared recovery flow to admin-managed onboarding so newly created staff accounts land in a recoverable first-access state and admin-triggered recovery uses the same email-backed backend contract instead of standalone temporary-password handling.

## Steps

1. Update `backend-hormonia/app/schemas/v2/admin.py` so admin provisioning can represent a first-access flow and admin-triggered recovery returns delivery/result metadata instead of a generated password.
2. Rework `backend-hormonia/app/api/v2/routers/admin/users.py` to create first-access users through the shared reset service, keeping new accounts inactive for local login until reset-confirm completes or otherwise marking them as recoverable-but-not-ready according to the existing user model.
3. Rework `backend-hormonia/app/api/v2/routers/admin/actions.py` to trigger the shared email-backed recovery flow instead of setting/displaying a canonical plaintext temporary password, while keeping the compatibility boundary explicit for the still-unmigrated admin SPA until S03.
4. Run the full S02 suite and tighten assertions until admin-created users, migrated Firebase-era users, and failure diagnostics all pass on the same backend contract.

## Must-Haves

- [ ] Admin create supports a first-access provisioning path that does not require storing or returning a plaintext password.
- [ ] Admin-triggered recovery reuses the same token/email flow as public reset-request rather than a bespoke password-generation path.
- [ ] Responses and logs expose delivery/result state that a future agent can inspect without leaking raw token or password material.
- [ ] The complete S02 verification suite passes, including local login after reset-confirm for a newly admin-created user.

## Verification

- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`
- Confirm the admin contract tests no longer surface plaintext temporary-password data and the integration suite proves admin-created users can activate via reset-confirm then log in locally.

## Observability Impact

- Signals added/changed: Admin create/reset responses now expose recoverable delivery metadata and reuse the same inspectable reset diagnostics as the public auth flow.
- How a future agent inspects this: Run the admin/API integration suites, inspect admin action responses, and verify user/session state after provisioning and reset-confirm.
- Failure state exposed: Provisioning-state drift, email dispatch failure, or regression back to temporary-password handling becomes directly visible in one of the focused suites.

## Inputs

- `backend-hormonia/app/services/password_reset_service.py` — shared reset orchestration introduced in T02 and reused here.
- `backend-hormonia/app/api/v2/routers/admin/users.py` and `backend-hormonia/app/api/v2/routers/admin/actions.py` — current admin create/reset endpoints that still model direct password setting.
- `backend-hormonia/tests/api/v2/test_admin_first_access.py` and `backend-hormonia/tests/integration/test_password_reset_migration_flow.py` — the red proof points this task must turn green.

## Expected Output

- `backend-hormonia/app/schemas/v2/admin.py`, `backend-hormonia/app/api/v2/routers/admin/users.py`, and `backend-hormonia/app/api/v2/routers/admin/actions.py` — admin APIs aligned to first-access provisioning and email-backed recovery.
- `backend-hormonia/tests/api/v2/test_admin_first_access.py` and `backend-hormonia/tests/integration/test_password_reset_migration_flow.py` — green proof that admin-created accounts complete the same recovery contract as existing users.
