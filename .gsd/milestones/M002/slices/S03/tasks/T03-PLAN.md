---
estimated_steps: 4
estimated_files: 6
---

# T03: Rewire websocket auth to the canonical session contract

**Slice:** S03 — Frontend And Realtime Cutover
**Milestone:** M002

## Description

Finish the cutover at the realtime boundary by aligning the backend websocket handshake to the canonical session identity contract and teaching the frontend websocket manager/hooks to authenticate from first-party session state instead of Firebase JWT lifecycle rules.

## Steps

1. Update `backend-hormonia/app/api/websockets.py` to authenticate websocket connections from the canonical session contract, reusing `backend-hormonia/app/api/v2/auth_session_shared.py` so cookie-backed sessions (with in-memory `session_id` fallback only if needed) resolve users by `user_id` rather than `firebase_uid`.
2. Refactor `frontend-hormonia/src/lib/websocket.ts` so connect/reconnect logic uses session-based auth bootstrap, drops JWT-expiry/Firebase-token assumptions from the happy path, and keeps room subscription replay intact.
3. Update `frontend-hormonia/src/hooks/useWebSocket.ts`, `frontend-hormonia/src/hooks/useMetricsWebSocket.ts`, and any shared websocket types to consume session auth from `AuthContext` / `apiClient` instead of `getFirebaseToken` / `refreshToken`.
4. Run the backend websocket contract suite and frontend realtime cutover suite until connection, reconnect, and invalid-session diagnostics all pass without Firebase token usage in the browser path.

## Must-Haves

- [ ] The websocket happy path no longer requires `token=<firebase_jwt>` from the browser.
- [ ] Backend websocket session auth succeeds when session data carries canonical `user_id` and embedded user info, even when `firebase_uid` is absent on the happy path.
- [ ] Reconnect and room resubscription still work after the auth bootstrap changes.
- [ ] Invalid-session / auth-failure websocket paths emit stable, inspectable diagnostics rather than silently disconnecting.

## Verification

- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/auth/session-first-cutover.test.tsx`

## Observability Impact

- Signals added/changed: Websocket auth transitions become traceable through stable `authenticated` / `error` payloads and session-auth-specific logging instead of JWT refresh heuristics.
- How a future agent inspects this: Run the focused websocket suites or inspect websocket handshake URLs/messages and the backend auth response payloads.
- Failure state exposed: Session lookup failures, reconnect drift, and room replay regressions are localized to websocket auth rather than surfacing as generic UI staleness.

## Inputs

- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — failing backend proof for canonical websocket session auth.
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` — failing frontend proof for websocket bootstrap and diagnostics.

## Expected Output

- `backend-hormonia/app/api/websockets.py` — websocket handshake aligned to the canonical session identity contract.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — shared session-auth helper reused at the websocket boundary.
- `frontend-hormonia/src/lib/websocket.ts` — session-based websocket manager.
- `frontend-hormonia/src/hooks/useWebSocket.ts` and `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` — hooks aligned to session auth rather than Firebase token refresh.
- `frontend-hormonia/src/types/websocket.ts` — protocol typings updated for the new auth/bootstrap semantics.
