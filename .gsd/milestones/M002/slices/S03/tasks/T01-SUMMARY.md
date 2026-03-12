---
id: T01
parent: S03
milestone: M002
provides:
  - Red proof suites for session-first browser auth, recovery-route cutover, and websocket session-auth drift.
key_files:
  - frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx
  - frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx
  - frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts
  - backend-hormonia/tests/api/test_websocket_session_auth_contract.py
key_decisions:
  - Lock S03 to first-party session semantics by asserting direct `/api/v2/auth/login`, routed reset pages, `/medico/login` email-first compatibility, and websocket auth without Firebase-token or `firebase_uid` dependencies.
patterns_established:
  - Add focused red cutover proofs before runtime refactors so browser auth, recovery UX, and websocket session auth each fail at one named boundary instead of through a broad hybrid-auth haze.
observability_surfaces:
  - `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
duration: 59m
verification_result: partial
completed_at: 2026-03-12T10:42:00-03:00
blocker_discovered: false
---

# T01: Add failing cutover proof suites for session auth, recovery, and realtime

**Added the four planned S03 proof files and verified they fail on the current Firebase-era auth, recovery, and websocket cutover gaps.**

## What Happened

Created the planned proof suites before runtime refactoring so T02-T05 must satisfy the real S03 boundary instead of preserving the existing hybrid behavior.

### Frontend auth proof
Created `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` covering:
- direct `apiClient.auth.login()` expectations against `/api/v2/auth/login`
- `remember_me` propagation
- cookie/session restore through `checkAuth`
- logout cleanup
- inspectable auth diagnostics (`error`, `request_id`)
- explicit failure if the flow still depends on `/api/v2/auth/firebase/verify`, Firebase listeners, or Firebase persistence controls

### Recovery + physician route proof
Created `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx` covering:
- required routed reset-request / reset-confirm public paths
- rejection of the current support-email forgot-password placeholder
- rejection of the CRM-only `/medico/login` surface in favor of the canonical email-first entrypoint

### Frontend realtime proof
Created `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` covering:
- red proof that the current browser websocket handshake still appends `token=<firebase_jwt>`
- reconnect/resubscribe expectations remaining present in the websocket manager
- red proof that stable invalid-session diagnostics (`AUTH_WEBSOCKET_SESSION_INVALID`, `connection_id`) are still missing on the frontend websocket auth path

### Backend realtime proof
Created `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` covering:
- websocket happy-path auth from `session_id` + canonical `user_id`
- explicit failure if session auth still relies on `firebase_uid`
- invalid-session diagnostics with stable websocket error metadata

## Verification

Ran:
- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`

Observed:
- frontend auth proof fails because `src/lib/api-client/auth.ts` still throws `login is not supported in the Firebase-based authentication flow`, and `AuthContext` still registers Firebase listeners / persistence and routes login/logout through Firebase-era services
- recovery proof fails because reset-request/reset-confirm routes are missing from `publicRoutes`, `LoginPage` still opens the support-email placeholder, and `MedicoLogin` is still CRM-only
- frontend realtime proof fails because `src/lib/websocket.ts` still appends `token` to the websocket URL and does not yet carry `AUTH_WEBSOCKET_SESSION_INVALID` / `connection_id` diagnostics
- backend websocket proof fails because `app/api/websockets.py` does not authenticate the `session_id` happy path from canonical `user_id` alone and emits no explicit invalid-session auth error payload

Status:
- The new proof files exist.
- The focused verification is red in the intended cutover areas.
- Verification is recorded as partial because the frontend realtime proof was reduced to source-level contract assertions instead of a runtime websocket harness.

## Diagnostics

Primary inspection commands:
- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`

How to read failures:
- `session-first-cutover.test.tsx` -> browser auth API/auth-provider cutover drift
- `recovery-and-physician-routes-cutover.test.tsx` -> missing reset UX and `/medico/login` compatibility drift
- `session-websocket-cutover.test.ts` -> browser websocket bootstrap still shaped around Firebase tokens / missing stable auth diagnostics
- `test_websocket_session_auth_contract.py` -> backend websocket session-auth still not honoring canonical `user_id` happy path

## Deviations

- The frontend realtime proof currently uses source-level assertions against `src/lib/websocket.ts` instead of a full runtime websocket harness. I attempted a runtime mock-socket path first, but the current `wsManager.connect()` promise did not settle reliably under the existing test harness, so I kept the proof focused on the explicit cutover contract for T01 and left stronger runtime coverage for follow-up tightening if needed.

## Known Issues

- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` is intentionally narrower than the slice plan’s ideal runtime websocket proof; if T03 needs stronger pre-implementation pressure on hooks/manager behavior, the next agent should replace the source-level assertions with a stable runtime harness once the websocket manager is easier to drive under test.
- The frontend auth proof currently mixes one direct API-client contract assertion with AuthProvider-driven assertions; once T02 lands, it would be worth tightening those assertions to remove any remaining incidental dependence on the legacy provider shape.

## Files Created/Modified

- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` — red proof for first-party login, remember-me payloads, session restore, logout cleanup, and inspectable auth diagnostics.
- `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx` — red proof for routed recovery UX and `/medico/login` email-first compatibility.
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` — red proof for Firebase-token websocket handshake drift and missing stable websocket auth diagnostics.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — red backend proof for canonical websocket session auth without `firebase_uid` on the happy path.
- `.gsd/milestones/M002/slices/S03/S03-PLAN.md` — marked T01 complete for slice tracking.
