---
id: T03
parent: S02
milestone: M002
provides:
  - Admin user creation can provision first-access accounts without storing or returning a plaintext password, and admin password reset can reuse the shared email-backed recovery contract with redacted delivery metadata.
key_files:
  - backend-hormonia/app/schemas/v2/admin.py
  - backend-hormonia/app/api/v2/routers/admin/users.py
  - backend-hormonia/app/api/v2/routers/admin/actions.py
  - backend-hormonia/app/services/password_reset_service.py
  - backend-hormonia/app/api/v2/routers/admin/utils.py
key_decisions:
  - Kept direct admin-set passwords as an explicit legacy compatibility path for the pre-S03 admin SPA, while making shared email-backed recovery the canonical backend contract for first-access provisioning and admin-triggered recovery.
patterns_established:
  - Extend the shared password-reset service with redacted delivery-result metadata, then have admin routes compose that shared flow instead of inventing a separate temporary-password backend path.
observability_surfaces:
  - Admin create/reset responses now expose structured first-access or delivery metadata; admin recovery failures return stable auth diagnostics with error, message, request_id, and timestamp; focused verification remains `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`.
duration: 35m
verification_result: passed
completed_at: 2026-03-11T23:54:31-03:00
blocker_discovered: false
---

# T03: Wire admin provisioning onto the first-access recovery contract

**Shipped admin first-access provisioning and admin-triggered recovery on top of the shared password-reset service, with redacted delivery metadata replacing plaintext temporary-password responses on the canonical backend path.**

## What Happened

Updated `backend-hormonia/app/schemas/v2/admin.py` so admin create now supports two explicit provisioning modes: legacy direct-password creation and first-access provisioning via `send_activation_email=true`. The same schema update also changed admin password reset requests so the canonical path can be `send_email=true`, while direct `new_password` resets remain available only as an explicit compatibility boundary for the still-unmigrated admin SPA.

Extended `backend-hormonia/app/services/password_reset_service.py` with a reusable `PasswordResetDeliveryResult` plus a `request_password_reset_for_user()` entrypoint. That let admin routes trigger the same token/email flow already used by public recovery, while surfacing inspectable delivery metadata without exposing raw token or password material.

Reworked `backend-hormonia/app/api/v2/routers/admin/users.py` so first-access admin-created users are persisted with `hashed_password=None`, `auth_provider=local`, and `force_change_password=True`, then immediately routed through the shared reset-email service before commit. Successful responses now include a `first_access` block with `required`, `delivery`, `channel`, `ready_for_login`, and optional opaque `message_id` fields. Delivery failures roll back creation and return stable redacted diagnostics.

Reworked `backend-hormonia/app/api/v2/routers/admin/actions.py` so `POST /api/v2/admin/users/{user_id}/reset-password` triggers the shared email-backed recovery flow when `send_email=true`, returning `202 Accepted` plus a `delivery` block instead of any plaintext password. The old direct-password reset path was preserved deliberately and labeled in logs/audit data as a legacy compatibility mode for pre-S03 callers.

Added `backend-hormonia/app/api/v2/routers/admin/utils.py` helpers so admin recovery failures use the same stable diagnostic shape as public auth recovery (`error`, `message`, `request_id`, `timestamp`).

## Verification

Passed the full slice verification command:

- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_admin_first_access.py tests/integration/test_password_reset_migration_flow.py -q`

Also ran a focused compatibility regression sweep for legacy admin contracts that still exercise direct-password create/reset paths:

- `cd backend-hormonia && pytest tests/api/v2/test_admin.py -q -k 'create_user or reset_password'`

Verified behaviors covered by the green suites:

- Admin create with `send_activation_email=true` no longer requires or returns plaintext password data.
- Admin-triggered recovery returns redacted email delivery metadata and no plaintext temporary password.
- A newly admin-created user can complete `/api/v2/auth/password/reset-confirm` and then log in through the local auth contract.
- Firebase-era users and admin-created users still migrate through the same reset-confirm/session-revocation contract.

## Diagnostics

Inspect later with:

- `cd backend-hormonia && pytest tests/api/v2/test_admin_first_access.py -q`
- `cd backend-hormonia && pytest tests/integration/test_password_reset_migration_flow.py -q`

Runtime inspection surfaces added/retained:

- `POST /api/v2/admin/users` first-access responses include a `first_access` object with redacted delivery state.
- `POST /api/v2/admin/users/{user_id}/reset-password` email-backed responses include `delivery.channel`, `delivery.status`, and optional opaque `delivery.message_id`.
- Delivery/service failures return stable JSON diagnostics with `error`, `message`, `request_id`, and `timestamp`.
- Structured logs/audit payloads now distinguish `first_access_email`, `direct_password`, `reset_password_recovery`, and `reset_password_legacy_direct` paths without logging secrets.

## Deviations

None.

## Known Issues

None in the T03 backend scope. The legacy direct-password admin reset path remains intentionally present until S03 migrates the admin SPA off temporary-password UX.

## Files Created/Modified

- `backend-hormonia/app/schemas/v2/admin.py` — added first-access provisioning and redacted recovery-delivery response schemas while preserving the explicit legacy compatibility shape.
- `backend-hormonia/app/services/password_reset_service.py` — added reusable delivery-result metadata and a known-user reset entrypoint for admin flows.
- `backend-hormonia/app/api/v2/routers/admin/users.py` — wired admin create to provision first-access users through the shared recovery service.
- `backend-hormonia/app/api/v2/routers/admin/actions.py` — switched canonical admin reset to shared email-backed recovery while keeping a labeled legacy direct-password fallback.
- `backend-hormonia/app/api/v2/routers/admin/utils.py` — added stable admin recovery diagnostic helpers matching the shared auth error contract.
