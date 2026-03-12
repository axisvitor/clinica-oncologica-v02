---
estimated_steps: 4
estimated_files: 7
---

# T02: Implement public password recovery and migration wiring

**Slice:** S02 — Account Recovery And Migration
**Milestone:** M002

## Description

Implement the reusable backend recovery contract for existing users and Firebase-era users: request a reset link, confirm a new password, transition onto local auth, and revoke every active session on the canonical `user_id` identity contract.

## Steps

1. Add a shared `backend-hormonia/app/services/password_reset_service.py` that normalizes email lookup, creates signed reset tokens, validates reset-confirm requests, updates password/migration fields, clears lockout counters, and revokes all active sessions through the existing DB and Redis invalidation primitives.
2. Extend `backend-hormonia/app/schemas/v2/auth.py` and `backend-hormonia/app/api/v2/routers/auth.py` with `POST /api/v2/auth/password/reset-request` and `POST /api/v2/auth/password/reset-confirm`, including generic non-enumerating success, shared password-strength validation, rate limiting, and stable error diagnostics with `request_id`-style visibility.
3. Add typed SMTP/auth-reset configuration in `backend-hormonia/app/config/settings/integrations.py` and `backend-hormonia/app/config/settings/__init__.py`, then update `backend-hormonia/app/services/notification_service.py` to send reset/first-access emails without depending on undeclared `getattr` fallbacks or logging raw tokens/credentials.
4. Run the public recovery suites, fix contract gaps, and stop only when existing local users and Firebase-era users can both request/reset through the new auth routes and return to the S01 local-login path.

## Must-Haves

- [ ] `reset-confirm` clears `failed_login_attempts`, `is_locked`, and `locked_until`, sets `last_password_change`, clears `force_change_password`, and moves Firebase-era users onto the local auth-provider contract.
- [ ] `reset-request` returns the same user-facing success response whether the email exists or not; only true operational failures surface inspectable diagnostics.
- [ ] Password-strength validation is shared with the admin path instead of introducing another auth-only rule.
- [ ] Missing SMTP configuration or delivery failure becomes an inspectable operational error surface without leaking credentials, account existence, or raw reset tokens.

## Verification

- `cd backend-hormonia && pytest tests/api/v2/test_auth_password_recovery.py tests/integration/test_password_reset_migration_flow.py -k 'existing or firebase' -q`
- Confirm the existing-user and Firebase-era scenarios complete reset-confirm and then authenticate through `POST /api/v2/auth/login` before the admin-created-user scenario is wired in T03.

## Observability Impact

- Signals added/changed: Public recovery endpoints now emit stable error payloads for token/validation/delivery failures, and successful reset-confirm writes durable user-state transitions that tests can inspect directly.
- How a future agent inspects this: Use the focused recovery pytest files, inspect auth JSON responses, and query user/session state when a reset flow fails.
- Failure state exposed: Token invalidity, weak-password rejection, SMTP misconfiguration, and session-revocation drift become directly attributable instead of collapsing into generic auth failure.

## Inputs

- `backend-hormonia/app/core/security.py` — signed reset-token helper that should remain the token primitive for S02.
- `backend-hormonia/app/services/auth.py`, `backend-hormonia/app/repositories/session.py`, and `backend-hormonia/app/core/redis_manager/session_cache.py` — canonical password/session logic from S01 that reset-confirm must reuse rather than parallel.
- `backend-hormonia/app/services/notification_service.py` and `backend-hormonia/app/config/settings/integrations.py` — current mailer/config surfaces with the SMTP typing gap called out in research.

## Expected Output

- `backend-hormonia/app/services/password_reset_service.py` — reusable recovery/migration orchestration for public and later admin flows.
- `backend-hormonia/app/api/v2/routers/auth.py` and `backend-hormonia/app/schemas/v2/auth.py` — shipped public recovery endpoints and request/response contracts.
- `backend-hormonia/app/services/notification_service.py` plus typed settings files — explicit, inspectable email-delivery configuration for reset/first-access mail.
