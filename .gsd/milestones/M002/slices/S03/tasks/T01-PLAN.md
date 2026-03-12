---
estimated_steps: 4
estimated_files: 4
---

# T01: Add failing cutover proof suites for session auth, recovery, and realtime

**Slice:** S03 — Frontend And Realtime Cutover
**Milestone:** M002

## Description

Create the slice proof before refactoring runtime code so the implementation is forced to satisfy the real browser, recovery, and websocket cutover contract instead of leaving Firebase-era behavior hidden behind compatibility shims.

## Steps

1. Add `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` covering direct `apiClient.auth.login()` usage, `remember_me` propagation, cookie/session restore via `checkAuth`, logout cleanup, and inspectable auth error handling without Firebase bridge calls.
2. Add `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx` covering routed reset-request / reset-confirm flows plus `/medico/login` compatibility on the canonical email-first login surface.
3. Add `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` and `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` covering websocket session handshake, reconnect/resubscribe behavior, invalid-session diagnostics, and the backend happy path without `firebase_uid`.
4. Run the focused frontend/backend suites, tighten assertions until failures localize to the missing cutover behavior rather than harness setup bugs, and leave them red for T02-T05 to close.

## Must-Haves

- [ ] The frontend auth suite explicitly fails if login still routes through `/api/v2/auth/firebase/verify`, Firebase listeners, or Firebase persistence controls.
- [ ] The recovery/route suite proves the slice needs real reset pages and rejects the current support-email placeholder / CRM-only doctor login behavior.
- [ ] The realtime suites fail if the browser websocket path still depends on `token=<firebase_jwt>` or the backend still requires `firebase_uid` on the happy path.
- [ ] At least one assertion in the new tests pins inspectable diagnostics (`error`, `request_id`, websocket auth error code, or connection identifier).

## Verification

- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`

## Observability Impact

- Signals added/changed: The new suites lock in structured auth/realtime diagnostics as part of the slice contract instead of treating them as optional UX.
- How a future agent inspects this: Run the four focused test files directly to see whether the break is in browser auth, recovery UX, or websocket session auth.
- Failure state exposed: Hidden Firebase bridge calls, placeholder recovery UX, and websocket/session identity drift fail as named assertions tied to one boundary each.

## Inputs

- `frontend-hormonia/src/app/providers/AuthContext.tsx` and `frontend-hormonia/src/lib/api-client/auth.ts` — current hybrid browser auth surfaces the tests must replace.
- `frontend-hormonia/src/lib/websocket.ts` and `backend-hormonia/app/api/websockets.py` — current realtime auth seam still shaped around Firebase tokens / `firebase_uid`.

## Expected Output

- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` — failing proof for login, restore, remember-me, logout, and auth diagnostics on first-party session semantics.
- `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx` — failing proof for reset UX and physician entrypoint alignment.
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` — failing proof for session-based websocket bootstrap.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — failing proof for canonical websocket session auth on the backend.
