---
id: T02
parent: S03
milestone: M004
provides:
  - Cookie-backed official frontend auth/client seams: AuthProvider, auth API, shared core requests, and enhanced analytics no longer persist browser `session_id` transport or emit legacy HTTP session headers.
key_files:
  - frontend-hormonia/src/app/providers/AuthContext.tsx
  - frontend-hormonia/src/lib/api-client/auth.ts
  - frontend-hormonia/src/lib/api-client/core.ts
  - frontend-hormonia/src/lib/api-client/enhanced-analytics.ts
  - .gsd/DECISIONS.md
  - .gsd/milestones/M004/slices/S03/S03-PLAN.md
  - .gsd/STATE.md
key_decisions:
  - `authToken` remains a compatibility-only in-memory value; official frontend HTTP/auth/analytics requests now rely on cookies + CSRF and do not translate it into `Authorization` or `X-Session-ID`.
  - `enhanced-analytics.ts` now reuses the shared `apiClient` CSRF lifecycle instead of reading `localStorage` for auth headers, with a single retry on CSRF-shaped 403 responses.
patterns_established:
  - The existing T01 proof can be turned green by cutting the shared auth/client seams directly; no page-level transport compatibility path was preserved on the official frontend happy path.
  - The frontend residue guard reports this cut as `moved_hotspot` drift until T05 republishes the allowlist, which is the expected signal when approved transport residue disappears.
observability_surfaces:
  - cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx
  - cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"
  - cd frontend-hormonia && npm run build
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend
duration: ~1h10m
verification_result: passed
completed_at: 2026-03-14T10:52:08-03:00
blocker_discovered: false
---

# T02: Remove HTTP and browser-storage legacy session transports from shared auth seams

**Cut the official frontend HTTP/storage auth seams over to cookie-backed session semantics: `AuthProvider` stopped rehydrating/persisting `session_id`, shared requests stopped emitting `Authorization` / `X-Session-ID`, and the direct analytics client now uses cookies + CSRF instead of localStorage token fallback.**

## What Happened

`frontend-hormonia/src/app/providers/AuthContext.tsx` was cut over so the official restore/login/logout path no longer reads `localStorage.session_id`, no longer persists `session_id` back into browser storage during restore/login, and no longer calls `apiClient.setAuthToken(...)` as part of the staff happy path. Session state still keeps the backend-returned `session_id` in memory for the remaining realtime compatibility work, but the browser-storage transport path is gone.

`frontend-hormonia/src/lib/api-client/auth.ts` now fetches `/api/v2/auth/verify-session` with cookies only, and the login helper no longer rehydrates the shared client with `session_id` or fabricates `access_token` from that value. User-safe auth diagnostics stayed intact through the same `toUserSafeAuthError` path frozen in T01.

`frontend-hormonia/src/lib/api-client/core.ts` was narrowed so `request()` and `getSessionHeaders()` no longer translate `authToken` into `Authorization` or `X-Session-ID`. The value remains available only as a compatibility-side in-memory token for later websocket cleanup, while shared HTTP requests stay cookie-backed and keep the existing CSRF fetch/retry behavior.

`frontend-hormonia/src/lib/api-client/enhanced-analytics.ts` no longer reads `localStorage.session_id` / `auth_token` and no longer injects auth/session headers. It now relies on `credentials: 'include'` plus the shared `apiClient` CSRF token lifecycle for POST requests, including one refresh-and-retry when a response looks like a CSRF rejection.

No focused proof file needed further edits in this task: the T01 tests already named the intended boundary, and they turned green once the shared seams were cut.

## Verification

Task verification passed:

- `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx`
  - **Passed** (21 tests).
  - Confirms: no `Authorization` / `X-Session-ID` emission from the shared client, no `localStorage.session_id` rehydration/persistence during official restore/login, preserved `credentials: 'include'`, preserved CSRF on state-changing requests, and preserved user-safe login diagnostics.

Direct seam check after the cut:

- `rg -n "Authorization|X-Session-ID|localStorage\.getItem\('session_id'\)|localStorage\.setItem\('session_id'\)" frontend-hormonia/src/app/providers/AuthContext.tsx frontend-hormonia/src/lib/api-client/auth.ts frontend-hormonia/src/lib/api-client/core.ts frontend-hormonia/src/lib/api-client/enhanced-analytics.ts`
  - Confirms the owned runtime files no longer emit legacy HTTP headers or read/write `localStorage.session_id`; remaining hits are compatibility setter/clearer APIs only.

Slice-level verification snapshot after the task:

- `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx`
  - **Red** only on `tests/integration/admin-auth-flow.test.tsx` (routed admin path still pending later slice work).
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts`
  - **Red** on the expected websocket `session_id` query fallback plus current failures in `tests/unit/hooks/useWebSocket.test.ts`, `tests/unit/hooks/useWebSocket.comprehensive.test.ts`, and `src/utils/__tests__/init-validator.test.ts`.
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`
  - **Passed** (1 passed, 3 skipped).
- `cd frontend-hormonia && npm run build`
  - **Passed**.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`
  - **Completed with drift notes** showing the approved `x_session_id` and `session_bearer_fallback` hotspots in `auth.ts`, `core.ts`, and `enhanced-analytics.ts` no longer exist.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
  - **Red** only because the allowlist still expects those removed hotspots; this is T05 bookkeeping, not surviving transport residue.

## Diagnostics

To inspect this task later:

- Rerun the focused auth/client pack to confirm the official HTTP/storage cut remains green:
  - `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx`
- Use the residue commands to confirm the removed transport seams now show up as allowlist drift rather than live residue:
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
- Use the single websocket diagnostic test to separate stable auth-error observability from the still-pending query-fallback cleanup:
  - `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`

## Deviations

None.

## Known Issues

- `tests/integration/admin-auth-flow.test.tsx` is still red on the routed `/admin/*` path. That remained outside T02 and still belongs to later slice work.
- `src/lib/websocket.ts` and the hook builders still preserve websocket `session_id` query fallback; the focused realtime proof stays red until T03 removes it.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` is now red because the allowlist still approves transport hotspots that T02 removed. T05 must republish the residue boundary.
- The broader slice verification pack still surfaces current failures in `tests/unit/hooks/useWebSocket.test.ts`, `tests/unit/hooks/useWebSocket.comprehensive.test.ts`, and `src/utils/__tests__/init-validator.test.ts`.

## Files Created/Modified

- `frontend-hormonia/src/app/providers/AuthContext.tsx` — removed official restore/login browser-storage rehydration/persistence and dropped `setAuthToken(...)` from the official auth happy path.
- `frontend-hormonia/src/lib/api-client/auth.ts` — removed legacy verify-session/login header/token injection and stopped synthesizing `access_token` from `session_id`.
- `frontend-hormonia/src/lib/api-client/core.ts` — made shared request headers cookie-only while preserving CSRF behavior and leaving `authToken` as compatibility-only state.
- `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts` — removed localStorage/header auth fallback and aligned analytics POST requests to cookies + shared CSRF handling.
- `.gsd/DECISIONS.md` — recorded the cookie-only HTTP seam decision and the fact that websocket fallback cleanup remains a separate T03 concern.
- `.gsd/milestones/M004/slices/S03/S03-PLAN.md` — marked T02 complete.
- `.gsd/STATE.md` — advanced the next action to T03 after T02 closeout.
- `.gsd/milestones/M004/slices/S03/tasks/T02-SUMMARY.md` — recorded the shipped seam cut, verification results, and the remaining slice red surfaces.
