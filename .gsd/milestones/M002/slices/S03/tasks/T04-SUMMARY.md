---
id: T04
parent: S03
milestone: M002
provides:
  - Routed password recovery and first-access pages on the public auth surface, plus `/medico/login` compatibility on the canonical email-first login flow.
key_files:
  - frontend-hormonia/src/pages/LoginPage.tsx
  - frontend-hormonia/src/pages/auth/PasswordResetRequestPage.tsx
  - frontend-hormonia/src/pages/auth/PasswordResetConfirmPage.tsx
  - frontend-hormonia/src/app/routes/routeConfig.ts
  - frontend-hormonia/src/app/routes/routeDefinitions.tsx
  - frontend-hormonia/src/pages/medico/MedicoLogin.tsx
  - frontend-hormonia/src/app/routes/MedicoRoutes.tsx
  - frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx
  - frontend-hormonia/tests/unit/pages/LoginPage.comprehensive.test.tsx
  - frontend-hormonia/src/pages/medico/__tests__/MedicoLogin.test.tsx
key_decisions:
  - Keep `/medico/login` as a compatibility entrypoint that renders the shared email-first login surface instead of preserving CRM-only doctor auth behavior.
  - Publish real public recovery routes for both canonical and legacy backend email links by wiring `/auth/password/reset-request`, `/auth/password/reset-confirm`, `/reset-password`, and `/primeiro-acesso` to the new reset pages.
  - Surface reset failures with stable backend diagnostics (`error`, `request_id`) while keeping success copy generic enough to avoid account-enumeration leaks.
patterns_established:
  - Reuse the canonical login page through small entrypoint props (`entryPoint`, `defaultRedirectPath`) instead of forking another physician-only login form.
  - Treat legacy auth URLs as thin public-route aliases/redirects that land on the canonical session-first UX rather than maintaining parallel logic.
observability_surfaces:
  - Login page auth-phase log `reset-request navigate`
  - Password reset page auth-phase logs `reset-request` and `reset-confirm`
  - Routed alert states exposing backend `error` and `request_id` for actionable recovery failures
  - Focused inspection commands: `cd frontend-hormonia && npx vitest run tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/unit/pages/LoginPage.comprehensive.test.tsx src/pages/medico/__tests__/MedicoLogin.test.tsx`
  - Slice verification commands: `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`, `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`, `cd frontend-hormonia && npm run build`
duration: 2h10m
verification_result: passed
completed_at: 2026-03-12 12:01 GMT-3
blocker_discovered: false
---

# T04: Ship reset and first-access UX plus physician login route alignment

**Shipped real routed password recovery/first-access pages, rewired the login screen away from the support-email placeholder, and aligned `/medico/login` to the shared email-first session auth surface.**

## What Happened

T04 turned the cutover proof into shipped browser behavior.

First, `frontend-hormonia/src/pages/LoginPage.tsx` stopped opening the old support-email placeholder. The forgot-password action now navigates to the routed reset-request screen and logs an explicit `reset-request navigate` auth phase. The page also gained a small entrypoint abstraction so the same canonical login surface can serve both the normal staff login and the physician compatibility entrypoint without cloning auth logic.

Second, two real public recovery pages were added:

- `frontend-hormonia/src/pages/auth/PasswordResetRequestPage.tsx`
- `frontend-hormonia/src/pages/auth/PasswordResetConfirmPage.tsx`

Those pages call the S02 endpoints directly through `apiClient.auth.requestPasswordReset()` and `apiClient.auth.confirmPasswordReset()`.

That closes the task must-haves as follows:

- **Forgot-password now uses the shipped reset-request/reset-confirm flow** instead of support-email instructions or Firebase helpers.
- **Recovery success messaging stays generic** (`Se existir uma conta...`) so the UI does not reveal whether an account exists.
- **Recovery failures are actionable and inspectable**: delivery failures, invalid/expired tokens, and weak-password failures surface visible alert states with stable backend `error` / `request_id` metadata when available.
- **The public routed surface now includes real reset / first-access pages** by wiring canonical and legacy-compatible paths into route config/definitions.

Third, route wiring was extended in `routeConfig.ts` and `routeDefinitions.tsx` to publish:

- `/auth/password/reset-request`
- `/auth/password/reset-confirm`
- `/reset-password`
- `/primeiro-acesso`
- `/medico/login`
- legacy `/medico/*` compatibility redirects toward the canonical physician dashboard surface

That lets S02-generated email links land on a real browser page today, while also preserving compatibility with the backend’s legacy frontend-path defaults until S04 cleanup.

Fourth, `frontend-hormonia/src/pages/medico/MedicoLogin.tsx` and `frontend-hormonia/src/app/routes/MedicoRoutes.tsx` were simplified into compatibility behavior instead of maintaining a CRM-only form. `/medico/login` now renders the same shared email/password login experience with physician-specific copy, and the old `/medico/*` routes redirect back toward the canonical physician surface instead of preserving Firebase-era or CRM-era validation rules.

Finally, the task’s focused proof files were updated to assert the shipped behavior directly, and the physician login unit coverage was rewritten around the new compatibility contract.

## Verification

Focused task verification passed:

- `cd frontend-hormonia && npx vitest run tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/unit/pages/LoginPage.comprehensive.test.tsx src/pages/medico/__tests__/MedicoLogin.test.tsx`
  - Passed: 23 tests

Slice-level verification required at this point also passed:

- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - Passed: 13 tests
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
  - Passed: 2 tests
- `cd frontend-hormonia && npm run build`
  - Passed production build

Real browser verification was also exercised against the built frontend preview:

- `/login` → explicit browser assertions passed for login visibility and forgot-password navigation to `/auth/password/reset-request`
- `/medico/login` → explicit browser assertions passed for physician compatibility copy plus shared email/password fields
- `/auth/password/reset-confirm` without a token rendered the expected expired-link / request-new-link state in the real browser DOM

## Diagnostics

Future agents can inspect this task through:

- Frontend proof suites:
  - `cd frontend-hormonia && npx vitest run tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/unit/pages/LoginPage.comprehensive.test.tsx src/pages/medico/__tests__/MedicoLogin.test.tsx`
- Slice auth/realtime proof:
  - `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- Backend websocket contract:
  - `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
- Routed UI surfaces:
  - `frontend-hormonia/src/pages/auth/PasswordResetRequestPage.tsx`
  - `frontend-hormonia/src/pages/auth/PasswordResetConfirmPage.tsx`
  - `frontend-hormonia/src/pages/medico/MedicoLogin.tsx`
- Structured auth logs:
  - `LoginPage` logs `reset-request navigate`
  - `PasswordResetRequestPage` logs `reset-request`
  - `PasswordResetConfirmPage` logs `reset-confirm`
- Inspectable UI failure state:
  - recovery request alert with backend `error` / `request_id`
  - invalid/expired token alert with stable `AUTH_RESET_TOKEN_INVALID_OR_EXPIRED`
  - weak-password field/server feedback during reset-confirm

## Deviations

- Added public-route aliases for `/reset-password` and `/primeiro-acesso` in addition to the explicitly requested canonical `/auth/password/*` paths so existing S02 email links land on working pages immediately.
- Added targeted physician login unit coverage in `src/pages/medico/__tests__/MedicoLogin.test.tsx` because the old CRM-form assertions no longer matched the compatibility contract.

## Known Issues

- Browser preview verification surfaced pre-existing CORS/network failures for `csrf-token` and `verify-session` requests when the built frontend preview pointed at the configured remote API without a matching local backend/CORS setup. The routed recovery/entrypoint UI checks still passed, and this did not block the task proof or build verification.

## Files Created/Modified

- `frontend-hormonia/src/pages/LoginPage.tsx` — routed forgot-password navigation, shared entrypoint props, physician compatibility messaging, and reset navigation observability.
- `frontend-hormonia/src/pages/auth/PasswordResetRequestPage.tsx` — new public reset-request / first-access request page with generic success copy and actionable failure alerts.
- `frontend-hormonia/src/pages/auth/PasswordResetConfirmPage.tsx` — new public reset-confirm / first-access completion page with token-aware failure states and password validation.
- `frontend-hormonia/src/app/routes/routeConfig.ts` — added auth and medico compatibility route constants.
- `frontend-hormonia/src/app/routes/routeDefinitions.tsx` — published public recovery routes plus medico compatibility redirects/entrypoint.
- `frontend-hormonia/src/pages/medico/MedicoLogin.tsx` — converted from CRM-only login form to canonical email-first compatibility entrypoint.
- `frontend-hormonia/src/app/routes/MedicoRoutes.tsx` — reduced legacy medico routes to compatibility redirects.
- `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx` — updated cutover proof to assert real recovery pages and physician compatibility behavior.
- `frontend-hormonia/tests/unit/pages/LoginPage.comprehensive.test.tsx` — aligned login-page coverage with routed recovery and canonical email-first login semantics.
- `frontend-hormonia/src/pages/medico/__tests__/MedicoLogin.test.tsx` — replaced CRM-era unit expectations with physician compatibility entrypoint coverage.
