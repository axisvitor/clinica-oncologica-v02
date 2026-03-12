---
id: T03
parent: S03
milestone: M002
provides:
  - Canonical session-authenticated websocket handshake on backend/frontend with stable auth diagnostics and reconnect-safe room replay.
key_files:
  - backend-hormonia/app/api/websockets.py
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - frontend-hormonia/src/lib/websocket.ts
  - frontend-hormonia/src/hooks/useWebSocket.ts
  - frontend-hormonia/src/hooks/useMetricsWebSocket.ts
  - frontend-hormonia/src/types/websocket.ts
key_decisions:
  - Websocket session identity now resolves through the shared session contract with cookie/header priority and `query_session_id` only as a last-resort compatibility fallback.
  - Frontend realtime bootstrap no longer appends `token=<firebase_jwt>`; invalid-session websocket errors now surface stable `AUTH_WEBSOCKET_SESSION_INVALID` diagnostics including `connection_id`.
patterns_established:
  - Keep the browser websocket happy path cookie-first while retaining a non-JWT in-memory `session_id` fallback and turning auth failures into explicit websocket `authenticated` / `error` payloads instead of reconnect haze.
observability_surfaces:
  - Backend websocket `authenticated` and `error` payloads with `AUTH_WEBSOCKET_SESSION_INVALID` / `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED`
  - Frontend websocket logs and reconnect suppression keyed by websocket auth error codes plus `connection_id`
  - `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
  - `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/auth/session-first-cutover.test.tsx`
  - `cd frontend-hormonia && npm run build`
duration: 1h05m
verification_result: passed
completed_at: 2026-03-12T11:26:00-03:00
blocker_discovered: false
---

# T03: Rewire websocket auth to the canonical session contract

**Cut the realtime auth boundary over to first-party session semantics so backend/frontend websocket bootstrap now works without Firebase JWT query params on the browser happy path.**

## What Happened

I updated the backend websocket handshake in `backend-hormonia/app/api/websockets.py` to authenticate from the canonical session contract instead of the old `firebase_uid`-centric lookup path.

Key backend changes:
- session auth now resolves through `backend-hormonia/app/api/v2/auth_session_shared.py`
- `resolve_session_id()` was extended with `query_session_id` as a lowest-priority fallback after Authorization / `X-Session-ID` / cookie sources
- websocket session auth first checks canonical embedded `user_id` session payloads and only opens a DB session when the embedded contract is incomplete
- successful session auth now emits an explicit `authenticated` websocket payload with `success`, `user_id`, and `user_role`
- invalid or expired session handshakes now emit stable websocket `error` payloads with `AUTH_WEBSOCKET_SESSION_INVALID` and `details.connection_id`
- transient lookup failures emit `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` so later debugging can distinguish bad sessions from backend lookup trouble
- real manager metadata is updated on session auth so post-connect room joins still work instead of leaving the connection logically unauthenticated

On the frontend, I refactored `frontend-hormonia/src/lib/websocket.ts` so websocket bootstrap is session-based:
- removed the `token=<firebase_jwt>` handshake behavior from the browser happy path
- added cookie-first/session-first URL construction with optional `session_id` fallback only for non-JWT session markers
- removed JWT-expiry gating from the happy path
- preserved reconnect and room subscription replay (`roomSubscriptions.forEach`, `joinPatientRoom`, `subscribeToQuizEvents`, `subscribeToFlowEvents`)
- added stable session-auth error inspection so `AUTH_WEBSOCKET_SESSION_INVALID` can stop blind reconnect loops and log `connection_id`

I also aligned the hooks/types layer:
- `frontend-hormonia/src/hooks/useWebSocket.ts` now connects from authenticated session state instead of `refreshToken()` / Firebase-token bootstrap and treats websocket auth failures as explicit error-state transitions
- `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` now uses session auth/bootstrap instead of `getFirebaseToken()` and reconnects through the same session-aware flow
- `frontend-hormonia/src/types/websocket.ts` now documents websocket auth error codes/diagnostics and renames the manager-facing connect semantics around session IDs rather than tokens

## Verification

Task-level verification passed:
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
  - canonical `user_id` session payload authenticates websocket without `firebase_uid`
  - invalid sessions emit explicit `AUTH_WEBSOCKET_SESSION_INVALID` diagnostics with `connection_id`
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/auth/session-first-cutover.test.tsx`
  - websocket source no longer appends `token=<firebase_jwt>`
  - reconnect + room replay contract remains present
  - stable invalid-session frontend diagnostics are pinned in source
  - session-first auth suite remained green after realtime changes

Slice-level verification run during this task:
- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - `session-first-cutover.test.tsx` passed
  - `session-websocket-cutover.test.ts` passed
  - `recovery-and-physician-routes-cutover.test.tsx` still fails as expected for T04
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
  - passed
- `cd frontend-hormonia && npm run build`
  - passed

## Diagnostics

Future agents can inspect this task by:
- running `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
- running `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts`
- inspecting backend websocket handshake payloads for:
  - `type: authenticated`
  - `type: error` with `error: AUTH_WEBSOCKET_SESSION_INVALID` or `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED`
  - `details.connection_id`
- checking frontend websocket logs/handlers for reconnect suppression tied to `AUTH_WEBSOCKET_SESSION_INVALID`
- reviewing `frontend-hormonia/src/lib/websocket.ts` for the cookie-first/session-first bootstrap path and room replay logic

## Deviations

None.

## Known Issues

- `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx` remains red because routed recovery pages and `/medico/login` email-first compatibility belong to T04.

## Files Created/Modified

- `backend-hormonia/app/api/websockets.py` — rewired handshake auth to canonical session resolution, emitted stable websocket auth diagnostics, and marked real connections authenticated for room access.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — added `query_session_id` resolution fallback and exposed canonical session-user extraction for websocket reuse.
- `frontend-hormonia/src/lib/websocket.ts` — removed Firebase token query bootstrap, kept reconnect/resubscribe behavior, and added stable session-auth diagnostics handling.
- `frontend-hormonia/src/hooks/useWebSocket.ts` — aligned the general realtime hook to session auth/bootstrap and explicit websocket auth error handling.
- `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` — aligned metrics realtime bootstrap to session auth and session-aware reconnect behavior.
- `frontend-hormonia/src/types/websocket.ts` — added websocket auth diagnostic typings and session-oriented manager contracts.
- `.gsd/DECISIONS.md` — recorded the websocket session-resolution and frontend auth-diagnostics decisions for downstream tasks.
- `.gsd/milestones/M002/slices/S03/S03-PLAN.md` — marked T03 complete.
