---
id: T02
parent: S03
milestone: M002
provides:
  - Session-first frontend auth login/restore/logout semantics wired to first-party backend endpoints, with normalized user-safe auth diagnostics.
key_files:
  - frontend-hormonia/src/lib/api-client/auth.ts
  - frontend-hormonia/src/app/providers/AuthContext.tsx
  - frontend-hormonia/src/hooks/useAuth.ts
  - frontend-hormonia/src/app/providers/MedicoAuthContext.tsx
key_decisions:
  - AuthContext now uses `apiClient.auth.login()`, `checkAuth()`, `logout()`, and `invalidateAllSessions()` as the browser happy path instead of Firebase listeners/persistence.
  - Backend auth failures are normalized through `toUserSafeAuthError` so UI callers can inspect `message`, `error`, `request_id`, and `status` without exposing secrets.
patterns_established:
  - Keep import stability by preserving the existing AuthContext/useAuth surface while swapping the runtime implementation to cookie-first session restore plus explicit auth-phase logging.
observability_surfaces:
  - AuthContext structured phase logs (`login`, `restore`, `logout`, `logout-all`, `refresh-session`)
  - User-safe auth error objects carrying backend `error` / `request_id` via `toUserSafeAuthError`
  - `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx`
duration: 1h20m
verification_result: passed
completed_at: 2026-03-12T11:06:00-03:00
blocker_discovered: false
---

# T02: Replace AuthContext with first-party session login, restore, and logout semantics

**Replaced the frontend happy path with first-party session auth while keeping the existing AuthContext/useAuth imports stable.**

## What Happened

I implemented direct first-party auth client methods in `frontend-hormonia/src/lib/api-client/auth.ts` for:
- `POST /api/v2/auth/login` with `remember_me`
- `POST /api/v2/auth/password/reset-request`
- `POST /api/v2/auth/password/reset-confirm`

The auth client now normalizes backend failures into safe `ApiError` payloads and exposes a shared `toUserSafeAuthError()` helper so UI layers can surface stable `message`, `error`, `request_id`, and `status` details without leaking passwords, tokens, or raw session secrets.

I refactored `frontend-hormonia/src/app/providers/AuthContext.tsx` so the normal browser path is now session-first:
- bootstrap still fetches CSRF
- restore uses `apiClient.auth.checkAuth()` / `verify-session`
- login uses `apiClient.auth.login()` directly
- logout uses `apiClient.auth.logout()`
- logout-all uses `apiClient.auth.invalidateAllSessions()`
- auth lock behavior and dashboard prefetch were preserved
- session persistence remains limited to `session_id` local cleanup/restore support already used by the app
- Firebase listeners, Firebase persistence setup, and Firebase bridge services were removed from the normal login / restore / logout control path

I also updated the compatibility consumers:
- `frontend-hormonia/src/hooks/useAuth.ts` now derives session-first tokens/state from the provider and routes reset-password requests to the first-party API
- `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx` now remains a thin wrapper over the session-based provider semantics

`frontend-hormonia/src/contexts/AuthContext.tsx` was intentionally left unchanged as the stable shim.

## Verification

Passed task-level verification:
- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx`
  - login hits `/api/v2/auth/login`
  - `remember_me` payload is preserved
  - session restore uses `verify-session`
  - logout clears local cleanup surfaces and does not call Firebase bridge services
  - backend auth failures remain inspectable

Additional slice-level spot checks run during this task:
- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - `session-first-cutover.test.tsx` passed
  - recovery/physician route cutover remains red as expected for T04
  - realtime websocket cutover remains red as expected for T03
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
  - still red as expected for T03 backend websocket work
- `cd frontend-hormonia && npm run build`
  - passed

## Diagnostics

Future agents can inspect this task by:
- running `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx`
- checking AuthContext logs for phase markers: `login`, `restore`, `logout`, `logout-all`, `refresh-session`
- inspecting thrown auth errors from the provider/hook for normalized `message`, `error`, `request_id`, `status`, and `data`

## Deviations

None.

## Known Issues

- `frontend-hormonia/tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx` is still failing because the routed reset UX and `/medico/login` email-first compatibility work belong to T04.
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` is still failing because the browser websocket handshake still appends `token=` and does not yet expose the expected invalid-session diagnostic contract; that is T03 scope.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` is still failing because backend websocket auth has not yet been cut over to the canonical session contract; that is T03 scope.

## Files Created/Modified

- `frontend-hormonia/src/lib/api-client/auth.ts` — added first-party login/reset client methods plus normalized safe auth diagnostics.
- `frontend-hormonia/src/app/providers/AuthContext.tsx` — replaced Firebase-first browser happy path with session-first login/restore/logout/logout-all while preserving auth lock and prefetch behavior.
- `frontend-hormonia/src/hooks/useAuth.ts` — aligned the derived auth hook to session-based provider state and first-party reset-password behavior.
- `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx` — kept physician auth as a thin wrapper over the refactored session seam.
- `.gsd/DECISIONS.md` — recorded the session-first AuthContext and normalized auth-error decision for downstream tasks.
