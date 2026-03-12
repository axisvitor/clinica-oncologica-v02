# S03: Frontend And Realtime Cutover

**Goal:** Cut the browser and realtime staff-auth path over to first-party session semantics so login, session restore, password recovery, physician entrypoints, and websocket bootstrap no longer depend on Firebase tokens.
**Demo:** From `/login` or the legacy `/medico/login` entrypoint, a staff user signs in with email + password, the app restores that session after refresh through `verify-session`, reset / first-access screens use the backend reset APIs, and realtime connections come up through the session-authenticated websocket path without Firebase SDK state.

## Must-Haves

- `frontend-hormonia/src/lib/api-client/auth.ts`, `AuthContext`, and `MedicoAuthContext` consume the S01/S02 first-party endpoints directly: `POST /api/v2/auth/login`, `GET /api/v2/auth/verify-session`, `DELETE /api/v2/auth/logout`, `DELETE /api/v2/auth/logout-all`, `POST /api/v2/auth/password/reset-request`, and `POST /api/v2/auth/password/reset-confirm`.
- Browser remember-me, refresh restore, logout, and protected-route bootstrap run on backend session semantics; Firebase persistence, auth listeners, and Firebase-token exchange are no longer control points for the happy path.
- Realtime bootstrap (`wsManager`, `useWebSocket`, `useMetricsWebSocket`, and `backend-hormonia/app/api/websockets.py`) authenticates from the canonical session contract, not Firebase JWTs, and the websocket happy path no longer requires `firebase_uid`.
- The login and recovery UX is real, not placeholder: `LoginPage` launches reset-request flow, reset-confirm has its own route/page, and `/medico/login` no longer preserves CRM-only / Firebase-era behavior.
- Frontend startup, monitoring, and build/config surfaces stop treating Firebase Auth runtime config as required for staff auth, and the slice leaves an explicit removal map for S04.
- Login, reset, restore, and realtime auth failures remain inspectable through stable UI or connection diagnostics without leaking passwords, reset tokens, raw session secrets, or Firebase credentials.

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` — direct first-party login, remember-me payload, session restore, logout, and inspectable auth failures without Firebase bridge calls.
- `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx` — reset-request / reset-confirm UI plus `/medico/login` compatibility flow on the email-first surface.
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` — `wsManager`, `useWebSocket`, and `useMetricsWebSocket` bootstrap from session auth and surface invalid-session diagnostics.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — websocket session auth resolves the canonical `user_id` contract without requiring `firebase_uid` on the happy path.
- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
- `cd frontend-hormonia && npm run build`

## Observability / Diagnostics

- Runtime signals: structured auth/realtime logs carry phase markers (`login`, `restore`, `reset-request`, `reset-confirm`, `websocket-auth`) plus backend `error` / `request_id` or websocket auth error codes instead of Firebase-state ambiguity.
- Inspection surfaces: login/reset alert states in the routed UI, `GET /api/v2/auth/verify-session`, websocket `authenticated` / `error` messages, and the focused frontend/backend proof suites.
- Failure visibility: invalid credentials, expired reset token, invalid session restore, and websocket auth failures expose a stable message/code path rather than silent logout or reconnect loops.
- Redaction constraints: never log or render plaintext passwords, raw reset tokens, full session secrets, or Firebase credential values.

## Integration Closure

- Upstream surfaces consumed: S01 `POST /api/v2/auth/login`, `GET /api/v2/auth/verify-session`, `DELETE /api/v2/auth/logout`, `DELETE /api/v2/auth/logout-all`, canonical `/api/v2/users/me`, and S02 `POST /api/v2/auth/password/reset-request` / `POST /api/v2/auth/password/reset-confirm`.
- New wiring introduced in this slice: `LoginPage` / `AuthContext` / `MedicoAuthContext` → first-party auth API client; websocket manager and hooks → cookie-first session-auth handshake; reset routes/pages → S02 recovery endpoints; `/medico/login` → canonical email-first auth surface; startup/service checks → session-auth wording and status.
- What remains before the milestone is truly usable end-to-end: S04 must delete or tombstone the remaining Firebase auth modules/tests/env residue, remove temporary compatibility seams, and run final assembled login → restore → protected access → reset → logout proof.

## Tasks

- [x] **T01: Add failing cutover proof suites for session auth, recovery, and realtime** `est:50m`
  - Why: Lock the slice boundary before refactoring so the implementation has to prove first-party browser auth, websocket session auth, and real recovery UX instead of preserving hidden Firebase-era behavior.
  - Files: `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx`, `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx`, `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts`, `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`
  - Do: Create focused failing tests that assert direct `apiClient.auth.login()` usage with `remember_me`, cookie/session restore through `verify-session`, logout cleanup, reset-request/reset-confirm routed UX, `/medico/login` compatibility on email-first auth, websocket bootstrap without `token=<firebase_jwt>`, and stable invalid-session/auth diagnostics; reuse existing router/test utilities instead of inventing a parallel harness.
  - Verify: `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts && cd ../backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
  - Done when: the new suites exist and fail only on the missing first-party cutover behavior, not on fixture or import breakage.
- [x] **T02: Replace AuthContext with first-party session login, restore, and logout semantics** `est:1h20m`
  - Why: `AuthContext` is the canonical browser auth seam; the slice is not real until login, remember-me, refresh restore, and logout are driven directly by the shipped backend session contract.
  - Files: `frontend-hormonia/src/lib/api-client/auth.ts`, `frontend-hormonia/src/app/providers/AuthContext.tsx`, `frontend-hormonia/src/contexts/AuthContext.tsx`, `frontend-hormonia/src/hooks/useAuth.ts`, `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx`
  - Do: Implement first-party `login`, `requestPasswordReset`, and `confirmPasswordReset` methods in the auth API client; refactor `AuthContext` to keep CSRF bootstrap, auth locking, dashboard prefetch, and cookie-first restore while removing Firebase listeners/persistence/session-bridge logic from the happy path; preserve the shim import surface; adapt `useAuth` / `MedicoAuthContext` to session-based fields and expose backend diagnostics in a user-safe way.
  - Verify: `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx`
  - Done when: login/restore/logout/remember-me tests pass without calling Firebase auth services or storing auth state in Firebase-controlled persistence.
- [x] **T03: Rewire websocket auth to the canonical session contract** `est:1h15m`
  - Why: The milestone promise is not met if HTTP auth is green but realtime still depends on Firebase JWTs or `firebase_uid`-centric websocket auth.
  - Files: `backend-hormonia/app/api/websockets.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `frontend-hormonia/src/lib/websocket.ts`, `frontend-hormonia/src/hooks/useWebSocket.ts`, `frontend-hormonia/src/hooks/useMetricsWebSocket.ts`, `frontend-hormonia/src/types/websocket.ts`
  - Do: Teach the websocket backend to authenticate from the canonical session contract (prefer cookie-backed session handshake, with in-memory `session_id` query fallback only if deployment compatibility requires it), resolve users by `user_id` instead of `firebase_uid`, emit stable auth failure payloads, and update frontend websocket manager/hooks to connect/reconnect from session auth rather than Firebase token refresh logic while keeping room resubscription behavior intact.
  - Verify: `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q && cd ../frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/auth/session-first-cutover.test.tsx`
  - Done when: realtime proof passes with no Firebase token query param on the browser happy path and invalid-session websocket failures are inspectable.
- [x] **T04: Ship reset and first-access UX plus physician login route alignment** `est:1h20m`
  - Why: Migrated users need a real recovery path in the browser, and the legacy doctor entrypoint cannot keep CRM/Firebase assumptions after the cutover.
  - Files: `frontend-hormonia/src/pages/LoginPage.tsx`, `frontend-hormonia/src/pages/auth/PasswordResetRequestPage.tsx`, `frontend-hormonia/src/pages/auth/PasswordResetConfirmPage.tsx`, `frontend-hormonia/src/app/routes/routeConfig.ts`, `frontend-hormonia/src/app/routes/routeDefinitions.tsx`, `frontend-hormonia/src/pages/medico/MedicoLogin.tsx`, `frontend-hormonia/src/app/routes/MedicoRoutes.tsx`
  - Do: Replace the support-email forgot-password placeholder with navigation to a real reset-request page, add a routed reset-confirm page that consumes the S02 token contract and password validation, keep the UX accessible and email-first, and turn `/medico/login` into a compatibility entrypoint that redirects or reuses the canonical login surface instead of validating CRM-only credentials.
  - Verify: `cd frontend-hormonia && npx vitest run tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/unit/pages/LoginPage.comprehensive.test.tsx`
  - Done when: the browser auth surface offers real reset/first-access behavior and the legacy physician entrypoint no longer depends on CRM or Firebase-era assumptions.
- [x] **T05: Update operational auth surfaces and record the S04 Firebase removal map** `est:50m`
  - Why: This slice must materially reduce runtime dependence now and leave S04 an explicit, low-ambiguity cleanup path rather than another repo-wide scavenger hunt.
  - Files: `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx`, `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx`, `frontend-hormonia/src/lib/runtime-config.ts`, `frontend-hormonia/.env.example`, `frontend-hormonia/vite.config.ts`, `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md`
  - Do: Replace Firebase-auth-required operational checks and copy with first-party session / websocket readiness signals, remove Firebase-auth-specific build/env guidance that implies runtime credentials are mandatory for staff auth, and write a concrete removal map naming the remaining Firebase auth modules, env knobs, and test suites that S04 should delete or tombstone after the cutover proof is green.
  - Verify: `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts && npm run build`
  - Done when: startup/build surfaces no longer report Firebase Auth as required for staff access and the slice contains a concrete, reviewable S04 cleanup map.

## Files Likely Touched

- `frontend-hormonia/src/lib/api-client/auth.ts`
- `frontend-hormonia/src/app/providers/AuthContext.tsx`
- `frontend-hormonia/src/contexts/AuthContext.tsx`
- `frontend-hormonia/src/hooks/useAuth.ts`
- `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx`
- `frontend-hormonia/src/lib/websocket.ts`
- `frontend-hormonia/src/hooks/useWebSocket.ts`
- `frontend-hormonia/src/hooks/useMetricsWebSocket.ts`
- `frontend-hormonia/src/types/websocket.ts`
- `frontend-hormonia/src/pages/LoginPage.tsx`
- `frontend-hormonia/src/pages/auth/PasswordResetRequestPage.tsx`
- `frontend-hormonia/src/pages/auth/PasswordResetConfirmPage.tsx`
- `frontend-hormonia/src/pages/medico/MedicoLogin.tsx`
- `frontend-hormonia/src/app/routes/routeConfig.ts`
- `frontend-hormonia/src/app/routes/routeDefinitions.tsx`
- `frontend-hormonia/src/app/routes/MedicoRoutes.tsx`
- `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx`
- `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx`
- `frontend-hormonia/src/lib/runtime-config.ts`
- `frontend-hormonia/.env.example`
- `frontend-hormonia/vite.config.ts`
- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx`
- `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx`
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts`
- `backend-hormonia/app/api/websockets.py`
- `backend-hormonia/app/api/v2/auth_session_shared.py`
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`
- `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md`
