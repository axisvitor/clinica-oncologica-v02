---
id: T04
parent: S04
milestone: M002
provides:
  - Backend and frontend staff-auth seams now use first-party password/session behavior only: password change verifies the current local password, updates the local hash, revokes DB + Redis sessions by canonical user_id, Firebase verify/debug seams are removed from runtime, and the settings UI clears stale session state after password rotation.
key_files:
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/schemas/v2/auth.py
  - backend-hormonia/app/api/v2/routers/debug/auth.py
  - backend-hormonia/app/services/websocket/connection_manager.py
  - backend-hormonia/app/middleware/csrf.py
  - backend-hormonia/app/middleware/config.py
  - frontend-hormonia/src/hooks/useSettings.ts
  - frontend-hormonia/src/features/settings/sections/SecuritySettings.tsx
  - frontend-hormonia/tests/unit/hooks/useSettings.test.tsx
key_decisions:
  - Password change now follows the same first-party credential rules as reset-confirm: verify current password locally, reuse shared password-strength validation, stamp last_password_change/force_change_password, then revoke active sessions by canonical user_id.
  - Firebase verify/debug/websocket compatibility was removed from shipped runtime surfaces instead of tombstoned in-place, because S04 proof already protects the hard cut and the remaining residue is documentation/e2e guidance reserved for T05.
patterns_established:
  - Session-revoking auth mutations should update persistent state first, invalidate Redis by canonical user_id second, and return stable auth error payloads with error/message/request_id rather than Firebase-origin failures.
  - Frontend password-change UX should submit only current_password + new_password, surface user-safe backend diagnostics, and clear local session artifacts immediately after success so stale browser state cannot masquerade as a live session.
observability_surfaces:
  - /api/v2/auth/password
  - /api/v2/auth/logout-all
  - /api/v2/debug/auth/token
  - backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py
  - backend-hormonia/tests/api/test_websocket_session_auth_contract.py
  - frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx
  - frontend-hormonia/tests/unit/hooks/useSettings.test.tsx
  - frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts
  - structured auth error payloads (error/message/request_id)
duration: 0h35m
verification_result: passed
completed_at: 2026-03-12T14:20:00-03:00
blocker_discovered: false
---

# T04: Replace remaining Firebase-only auth seams with first-party password and session behavior

**Hard-cut the remaining staff-auth runtime seams so password change, logout-all, debug token inspection, and websocket auth all behave as first-party session/local-auth surfaces instead of Firebase compatibility paths.**

## What Happened

I completed the functional runtime cut described in T04.

On the backend, `backend-hormonia/app/api/v2/routers/auth.py` no longer exposes a live `/api/v2/auth/firebase/verify` route. The router now imports only the first-party login/reset/password contracts, and the password-change endpoint was rewritten to use `PasswordChangeRequest` plus local credential verification. It loads the canonical user from the current session, verifies `current_password` against the stored local hash, rejects invalid current passwords with a stable `AUTH_PASSWORD_CURRENT_PASSWORD_INVALID` payload, validates `new_password` through the shared admin/password-reset strength validator, updates the local password hash, stamps `last_password_change`, clears `force_change_password`, unlocks/reset-failure counters, and revokes active sessions in both the database and Redis using canonical `user_id`.

`/api/v2/auth/logout-all` now invalidates Redis sessions by `user_id` even when `firebase_uid` is missing, which matches the session-first contract established earlier in the milestone. The shared cache helper in the auth router was renamed semantically from Firebase-specific identity handling to canonical identity handling, but it still tolerates compatibility cache adapters that can match either `user_id` or `firebase_uid` internally.

I also removed Firebase-auth runtime seams outside the main auth router. `backend-hormonia/app/api/v2/routers/debug/auth.py` no longer calls Firebase token verification; it now decodes JWT structure, validates first-party HS256 tokens when applicable, masks sensitive claims, and returns stable debug diagnostics without any Firebase token inspection language. `backend-hormonia/app/services/websocket/connection_manager.py` was simplified to session/JWT-era behavior only: no Firebase verifier helper, no `_authenticate_with_firebase`, and no `auth_type="firebase"` / `auto` compatibility path in the shipped manager. The middleware exemption/config residue for `/api/v2/auth/firebase/verify` was also removed from `backend-hormonia/app/middleware/csrf.py` and `backend-hormonia/app/middleware/config.py`.

On the frontend, `frontend-hormonia/src/hooks/useSettings.ts` already posted to `/api/v2/auth/password`, but it still behaved like a generic mutation. I rewired it so successful password changes clear local session artifacts, disconnect the websocket manager, show a stable “log in again” toast, and schedule a redirect to `/login` outside the test environment. Failure handling now normalizes backend auth diagnostics through `toUserSafeAuthError` so the UI shows stable user-safe messages from the first-party backend contract. `frontend-hormonia/src/features/settings/sections/SecuritySettings.tsx` was updated to enforce the stronger local-password rules in the form schema and to keep the submit flow async-aware before resetting the form.

Finally, I replaced the placeholder hook unit file with focused tests that exercise the actual T04 behavior: first-party password-change payload shape, success-path local session cleanup, and failure-path preservation of current session state plus stable backend diagnostics.

## Verification

Task-plan verification passed:

- `cd backend-hormonia && pytest tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_password_recovery.py -q`
  - Result: **passed**
- `cd frontend-hormonia && npx vitest run tests/integration/auth/hard-cut-cleanup-proof.test.tsx tests/unit/hooks/useSettings.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - Result: **passed**

Additional slice-level partial verification passed:

- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx tests/integration/auth/hard-cut-cleanup-proof.test.tsx`
  - Result: **passed**

Additional slice-level residue guard check:

- `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
  - Result: **still fails, but only on T05-owned docs/e2e guidance** (`frontend-hormonia/tests/e2e/README.md`, `docs/frontend/guides/configuration/ENVIRONMENT_GUIDE.md`, `docs/frontend/guides/deployment/DEPLOYMENT_GUIDE.md`). The T04 runtime seams this task targeted are no longer the failing part.

I did **not** rerun the final slice-wide build/backend integration/Playwright gate here; that remains for T05 as planned.

## Diagnostics

Future agents can inspect this task through:

- `backend-hormonia/app/api/v2/routers/auth.py` for password change, logout-all, and removed Firebase verify runtime behavior
- `backend-hormonia/app/api/v2/routers/debug/auth.py` for non-Firebase token diagnostics
- `backend-hormonia/app/services/websocket/connection_manager.py` for websocket auth-mode hard cut
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`
- `frontend-hormonia/src/hooks/useSettings.ts`
- `frontend-hormonia/src/features/settings/sections/SecuritySettings.tsx`
- `frontend-hormonia/tests/unit/hooks/useSettings.test.tsx`
- `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx`

Most useful runtime signals:

- `PUT /api/v2/auth/password` wrong current password → `400` with `error=AUTH_PASSWORD_CURRENT_PASSWORD_INVALID`
- `PUT /api/v2/auth/password` weak password → `400` with `error=AUTH_PASSWORD_WEAK`
- successful password change → local hash updated, `last_password_change` stamped, sessions revoked, frontend clears `session_id` and disconnects websocket state
- `DELETE /api/v2/auth/logout-all` → `sessions_deleted` now comes from canonical `user_id` invalidation, not `firebase_uid`
- websocket invalid session path remains inspectable through `AUTH_WEBSOCKET_SESSION_INVALID` and `connection_id`

## Deviations

- I also updated `backend-hormonia/app/schemas/v2/auth.py` to remove the Firebase verify request/response schemas because the runtime route itself was removed in T04. That schema cleanup was not explicitly called out in the T04 file list but was necessary to keep the auth contract honest and satisfy the residue guard.
- I replaced the pre-existing placeholder-style `frontend-hormonia/tests/unit/hooks/useSettings.test.tsx` with focused T04 hook tests instead of incrementally editing the old mock-only file, because the old file was not exercising the shipped hook behavior in any meaningful way.

## Known Issues

- `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh` is still red on Firebase references in docs/e2e guidance. That is a real remaining slice task, but it belongs to T05 rather than T04 runtime work.
- Legacy backend tests outside the new hard-cut proof still exist elsewhere in the repository that mention `/api/v2/auth/firebase/verify`; they were not cleaned up in this task because T04 focused on shipped runtime behavior and its dedicated proof suites.
- Final slice-wide verification (`npm run build`, extended backend integration gate, Playwright no-Firebase stack acceptance) was not rerun here and remains the T05 closeout gate.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/auth.py` — removed the live Firebase verify route, rewrote password change for first-party verification/hash update, and switched logout-all cache invalidation to canonical user identity.
- `backend-hormonia/app/schemas/v2/auth.py` — removed Firebase verify schemas and kept only the first-party auth/password contracts.
- `backend-hormonia/app/api/v2/routers/debug/auth.py` — replaced Firebase token inspection with first-party JWT diagnostics.
- `backend-hormonia/app/services/websocket/connection_manager.py` — removed Firebase websocket auth helpers/modes so shipped auth is session/JWT-only.
- `backend-hormonia/app/middleware/csrf.py` — removed the Firebase verify CSRF exemption.
- `backend-hormonia/app/middleware/config.py` — removed the legacy Firebase verify path from compatibility middleware config.
- `frontend-hormonia/src/hooks/useSettings.ts` — normalized password-change diagnostics and cleared local session/websocket state after successful rotation.
- `frontend-hormonia/src/features/settings/sections/SecuritySettings.tsx` — aligned client-side password validation and async submit behavior with the new first-party contract.
- `frontend-hormonia/tests/unit/hooks/useSettings.test.tsx` — added focused tests for first-party password change success/failure behavior.
- `.gsd/DECISIONS.md` — recorded the T04 hard-cut decisions for downstream T05 work.
