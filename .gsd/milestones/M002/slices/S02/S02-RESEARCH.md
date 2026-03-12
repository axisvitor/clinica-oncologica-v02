# M002/S02 — Research

**Date:** 2026-03-12

## Summary

S02 owns **R007 (existing-user recovery)**, **R008 (admin-managed provisioning remains canonical)**, and **R009 (email reset link)**, and materially supports **R012 (inspectable auth failures)**. The codebase already has most of the backend primitives needed to ship this slice without inventing a new auth subsystem: local password hashing, canonical user-id-centric sessions from S01, signed reset-token helpers, account security fields on `User`, Redis session invalidation keyed by canonical identity, and an SMTP-capable notification service.

What is missing is contract wiring and migration alignment. There is currently **no public first-party reset flow** on `/api/v2/auth/password/*`; the old legacy reset routes are explicitly asserted as `404`, and `frontend-hormonia` still treats password reset as a Firebase/admin-only concern. The current admin user-management path is also misaligned with S02: it still creates password-first accounts and resets passwords by generating/displaying plaintext temporary passwords in the browser, which is the opposite of the required email-backed first-access flow.

The highest-risk hidden issue is operational, not conceptual: `backend-hormonia/app/services/notification_service.py` expects `SMTP_*` settings, but those fields are **not declared in the typed settings modules**. In practice, that means email delivery for reset links is likely to fall back to defaults/empty credentials unless S02 explicitly fixes configuration ingestion. That is the main delivery risk for R009.

## Recommendation

Implement S02 as a **backend-first recovery slice** with two public endpoints and one admin-provisioning contract shift:

1. **`POST /api/v2/auth/password/reset-request`**
   - Accept `{ email }`.
   - Normalize email and look up the user by email.
   - Always return a **generic success response** (`202` or `200`) regardless of whether the account exists, to avoid email enumeration.
   - For eligible users, generate a signed token with `app/core/security.py` and send an email through `NotificationService`.
   - Emit stable diagnostics (`request_id`, structured error codes for true operational failures only) without leaking account existence.
   - Apply public rate limiting consistent with `AUTH_PASSWORD_RESET_CONFIG` intent.

2. **`POST /api/v2/auth/password/reset-confirm`**
   - Accept `{ token, new_password }`.
   - Reuse `verify_password_reset_token()` for signature/expiry validation.
   - After resolving the user by email, set a real local password and complete the migration state transition:
     - `hashed_password` = new hash
     - `auth_provider` = `LOCAL`
     - `force_change_password` = `False`
     - `last_password_change` = now
     - clear `failed_login_attempts`, `is_locked`, `locked_until`
   - Revoke all active sessions in **both DB and Redis** using the canonical `user_id` contract from S01.
   - Emit audit/diagnostic signals for completion.

3. **Admin-created accounts should land in first-access state, not temp-password state**
   - Recommended contract: admin provisioning should create an account that requires the email-backed activation/reset flow instead of exposing a plaintext password.
   - Safest migration path: either
     - make admin create support a first-access mode (password omitted, activation email sent), or
     - keep create as-is temporarily but immediately support a first-access/reset email path for the created email and stop treating client-generated temporary passwords as canonical.

For execution, prefer **focused backend tests** first: existing local users, Firebase-era users with `hashed_password=None`, and newly admin-created users must all complete the same reset-confirm path and then log in through S01’s local-login contract.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Signed password-reset token format | `backend-hormonia/app/core/security.py` (`create_password_reset_token`, `verify_password_reset_token`) | Already includes issuer, audience, expiry, and `jti`; keeps S02 aligned with existing tests and security helpers. |
| Email delivery | `backend-hormonia/app/services/notification_service.py` | SMTP sending already exists; S02 should add auth-specific usage/templates instead of inventing another mailer. |
| Canonical password hashing | `backend-hormonia/app/utils/security.py` via existing auth/admin services | Keeps login/reset behavior consistent with S01 local auth. |
| Session revocation | `backend-hormonia/app/core/redis_manager/session_cache.py` + `backend-hormonia/app/repositories/session.py` patterns | Redis + DB invalidation already exists; reset-confirm should reuse the same session model rather than introducing a parallel token/session story. |

## Existing Code and Patterns

- `backend-hormonia/app/core/security.py` — ready-to-use reset-token helper. Token currently carries `sub=email`, `exp`, `iss`, `aud`, and `jti`.
- `backend-hormonia/app/models/user.py` — already has the right state fields for S02: `hashed_password`, `force_change_password`, `last_password_change`, `failed_login_attempts`, `is_locked`, `locked_until`, `auth_provider`, and compatibility `firebase_uid`.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical auth surface after S01. This is the right place for `reset-request` and `reset-confirm`, and it already has `_auth_error_content()` / `_auth_security_headers()` patterns for stable diagnostics.
- `backend-hormonia/app/services/auth.py` — canonical local-auth service. S02 should follow its state-reset conventions when a password becomes valid again.
- `backend-hormonia/app/core/redis_manager/session_cache.py` — `invalidate_all_user_sessions(identity)` already supports **either `user_id` or `firebase_uid`**; this matches the S01 decision that `user_id` is canonical.
- `backend-hormonia/app/repositories/session.py` — `revoke_all_user_sessions(user_id)` already exists for DB-side invalidation.
- `backend-hormonia/app/api/v2/routers/admin/users.py` — current admin create path still requires a password and does **not** put the account into first-access state.
- `backend-hormonia/app/api/v2/routers/admin/actions.py` — current admin reset path sets a new password directly and can set `force_change_password`, but it does **not** model email-backed first access, does not update `last_password_change`, and does not revoke all sessions.
- `backend-hormonia/app/services/firebase_user_sync_service.py` — existing Firebase-era users may legitimately have `hashed_password=None` and `auth_provider=FIREBASE`; S02 must migrate these users through reset-confirm instead of assuming local credentials already exist.
- `frontend-hormonia/src/app/routes/AdminRoutes.tsx` — forgot-password currently shows a “contact admin” toast, proving there is no first-party recovery UX yet.
- `frontend-hormonia/src/lib/api-client/auth.ts` and `frontend-hormonia/src/hooks/useAuth.ts` — password-reset methods are explicitly unsupported today; S03 will need to consume the S02 backend contract.
- `frontend-hormonia/src/features/admin/users/UserDetailsModal.tsx` and `frontend-hormonia/src/hooks/admin/useUserMutations.ts` — admin reset still generates and reveals plaintext temporary passwords client-side; this is the pattern S02 should retire, not extend.

## Constraints

- S02 must build on the **S01 user-id-centric auth contract**. Recovery cannot assume Firebase token verification or `firebase_uid` on the happy path.
- The shipped reset flow must support **existing Firebase-era staff users** who currently have no local password (`hashed_password=None`).
- The milestone boundary explicitly requires **admin-created accounts** to be compatible with first-access/reset flows; S02 cannot stop at “existing users only.”
- `frontend-hormonia` is not yet ready to consume reset endpoints. S02 should therefore prove the contract with backend tests and leave UI consumption for S03.
- `backend-hormonia/tests/api/v2/test_auth.py` currently asserts that legacy endpoints like `/api/v2/auth/password/reset` and `/api/v2/auth/password/reset/confirm` are `404`. S02 should add the new contract on **`/reset-request`** and **`/reset-confirm`**, not silently revive the legacy paths unless the team explicitly chooses aliases.
- `User` already stores `force_change_password` and `last_password_change`, but current `/api/v2/users/me` serialization does **not** expose them. S02 verification should therefore assert DB state transitions directly, not depend on user-profile payloads.
- `backend-hormonia/app/services/notification_service.py` reads `SMTP_*` values through `getattr(settings, ...)`, but the typed settings modules do not currently declare these fields. This is a real operational constraint for email delivery.
- Password-policy validation is currently inconsistent across code paths. `PasswordResetConfirm` in `backend-hormonia/app/schemas/v2/auth.py` does **not** enforce a strength validator today, while admin validators do. S02 needs a single shared rule.

## Common Pitfalls

- **Revoking sessions by `firebase_uid` instead of canonical `user_id`** — `SessionCache.invalidate_all_user_sessions()` already supports both, but `auth.py`’s current logout-all helper still passes only `firebase_uid`. Reset-confirm must revoke by `user_id` so local-only users are fully logged out.
- **Treating reset tokens as one-time use when they are currently stateless** — `create_password_reset_token()` includes a `jti`, but `verify_password_reset_token()` does not enforce replay prevention. If S02 wants single-use semantics, it must store or blacklist used JTIs explicitly.
- **Reusing the current admin temp-password UX** — browser-generated temporary passwords shown in toasts are incompatible with “email-backed first access” and create unnecessary plaintext exposure.
- **Leaking account existence in reset-request** — returning `404`/different messages for unknown emails would create enumeration risk and conflict with a secure recovery flow.
- **Assuming all users already have a local password** — Firebase-era records created by `firebase_user_sync_service` do not.
- **Forgetting lockout cleanup on successful reset** — a new password should also clear `failed_login_attempts`, `is_locked`, and `locked_until`.
- **Using the current `PasswordResetConfirm` schema as-is** — it only enforces length today; S02 must add/attach real password-strength validation.

## Open Risks

- **Email delivery blocker:** unless S02 adds typed `SMTP_*` settings (or otherwise fixes mailer config ingestion), reset emails may not be deliverable even if the endpoint logic is correct.
- **Replay-risk decision:** the current token helper is signed and expiring, but not obviously one-time-use. Execution must decide whether expiry-only is acceptable or whether used-token tracking is required for launch.
- **Migration-state decision:** after reset-confirm, Firebase-era users should almost certainly move to `auth_provider=LOCAL`, but this should be implemented deliberately and covered by tests.
- **Frontend link target not yet defined:** there is no reset-password page/route today. S02 can still prove the backend and email payload shape, but S03 must consume the link contract.
- **Audit surface drift:** audit event types for `PASSWORD_RESET_REQUESTED` and `PASSWORD_RESET_COMPLETED` already exist, but some current admin flows only use app logging. S02 should keep reset outcomes inspectable, not just successful.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — install with `npx skills add wshobson/agents@fastapi-templates` |
| SQLAlchemy | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | available — install with `npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm` |
| Redis | `mindrally/skills@redis-best-practices` | available — install with `npx skills add mindrally/skills@redis-best-practices` |
| Redis | `redis/agent-skills@redis-development` | available — install with `npx skills add redis/agent-skills@redis-development` |
| SMTP / email delivery | `boomsystel-code/openclaw-workspace@imap-smtp-email` | available — install with `npx skills add boomsystel-code/openclaw-workspace@imap-smtp-email` |

## Sources

- S01 contract and downstream expectations — preloaded slice summary `M002/S01-SUMMARY.md`.
- Slice ownership and boundary contract — preloaded roadmap/context for `M002/S02`.
- Reset-token implementation details — `backend-hormonia/app/core/security.py`.
- User password/migration state fields — `backend-hormonia/app/models/user.py`.
- Canonical auth API/error/session patterns — `backend-hormonia/app/api/v2/routers/auth.py`.
- Local password verification/session semantics — `backend-hormonia/app/services/auth.py`.
- Redis bulk session invalidation contract — `backend-hormonia/app/core/redis_manager/session_cache.py`.
- DB-side session revocation contract — `backend-hormonia/app/repositories/session.py`.
- Current admin create/reset behavior — `backend-hormonia/app/api/v2/routers/admin/users.py`, `backend-hormonia/app/api/v2/routers/admin/actions.py`, `backend-hormonia/app/services/admin/admin_user_service/password_management.py`.
- Existing Firebase-era user creation shape (`hashed_password=None`) — `backend-hormonia/app/services/firebase_user_sync_service.py`.
- Current frontend reset gaps — `frontend-hormonia/src/app/routes/AdminRoutes.tsx`, `frontend-hormonia/src/lib/api-client/auth.ts`, `frontend-hormonia/src/hooks/useAuth.ts`.
- Current plaintext temp-password admin UX — `frontend-hormonia/src/features/admin/users/UserDetailsModal.tsx`, `frontend-hormonia/src/hooks/admin/useUserMutations.ts`.
- Legacy endpoint expectations — `backend-hormonia/tests/api/v2/test_auth.py`.
- Existing S01-style auth verification patterns — `backend-hormonia/tests/api/v2/test_auth_local_login.py`, `backend-hormonia/tests/integration/test_local_auth_core_flow.py`.
- Skill discovery results — `npx skills find "FastAPI"`, `npx skills find "SQLAlchemy"`, `npx skills find "Redis"`, `npx skills find "SMTP"`.
