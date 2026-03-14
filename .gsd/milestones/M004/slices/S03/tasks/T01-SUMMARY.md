---
id: T01
parent: S03
milestone: M004
provides:
  - Focused red-first frontend proof for the canonical session-first contract across shared HTTP headers, AuthProvider storage/rehydration, routed admin entry, and websocket query fallback.
key_files:
  - frontend-hormonia/tests/unit/api-client/auth-headers.test.ts
  - frontend-hormonia/tests/lib/api-client/core.test.ts
  - frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx
  - frontend-hormonia/tests/integration/admin-auth-flow.test.tsx
  - frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts
  - .gsd/milestones/M004/slices/S03/S03-PLAN.md
key_decisions:
  - Freeze the official frontend contract as cookie-backed login/restore/verify semantics with explicit absence checks for Authorization, X-Session-ID, localStorage.session_id rehydration, and websocket ?session_id= fallback.
  - Route admin proof through the shipped admin route definition plus canonical /login instead of a standalone AdminApp mount, so later work has to fix real router drift.
patterns_established:
  - Focused cutover tests now name the legacy transport/storage/query seams directly and fail on presence/absence assertions rather than broad auth smoke outcomes.
  - Slice verification includes a single-test websocket diagnostic check so stable AUTH_WEBSOCKET_SESSION_INVALID proof can stay green while broader cutover work remains red.
observability_surfaces:
  - cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts
  - cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend
duration: ~55m
verification_result: passed
completed_at: 2026-03-14T10:35:37-03:00
blocker_discovered: false
---

# T01: Freeze routed frontend proof for the canonical session-first contract

**Rewrote the focused frontend proof pack so it now freezes cookie-first auth/header/storage/query expectations and exercises admin auth through the routed `/admin/*` tree plus canonical `/login` instead of a standalone `AdminApp` mount.**

## What Happened

The task started by fixing the slice artifact gap: `S03-PLAN.md` now includes an explicit diagnostic verification command for the stable websocket auth error surface, so the slice no longer closes on happy-path checks alone.

On the proof side, `frontend-hormonia/tests/unit/api-client/auth-headers.test.ts` and `frontend-hormonia/tests/lib/api-client/core.test.ts` were rewritten to assert the canonical HTTP contract directly: requests stay cookie-backed, preserve `credentials: 'include'` and CSRF behavior, and do **not** emit `Authorization` or `X-Session-ID` even if legacy token setters are exercised.

`frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` now proves the official `AuthProvider` loop instead of tolerating browser-carried session transport. The file still keeps the user-safe login diagnostic proof, but login/restore/logout assertions now explicitly reject `apiClient.setAuthToken(...)` as part of the happy path and reject `localStorage.session_id` rehydration/persistence during restore and login. Assertions were written against presence/absence, error codes, request ids, routes, and generic string checks rather than raw session or password values.

`frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` no longer mounts `AdminApp` as a self-contained subtree. It now targets the shipped `adminRoutes` definition and a canonical `/login` entrypoint, so routed admin failures show up against the real outer protected route instead of the old standalone proof. The rerun is red here, which is the point: it is now failing against routed admin behavior rather than a green-but-incomplete mount.

`frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` was tightened to reject legacy websocket `?session_id=` bootstrap while preserving the stable invalid-session diagnostic assertion (`AUTH_WEBSOCKET_SESSION_INVALID` / `connection_id`).

The focused rerun landed in the expected places for the transport cut: shared client headers still emit `Authorization` / `X-Session-ID`; `AuthProvider` still calls `setAuthToken(...)` and persists `localStorage.session_id`; websocket bootstrap still appends `session_id`; and routed admin proof is now red against the real `/admin/*` path rather than the old standalone admin harness.

## Verification

Ran the task verification command red-first:

- `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - **Expected red, and it failed on the intended seams:**
    - `tests/unit/api-client/auth-headers.test.ts` / `tests/lib/api-client/core.test.ts` still see `Authorization` and `X-Session-ID` emission.
    - `tests/integration/auth/session-first-cutover.test.tsx` still sees `AuthProvider` call `setAuthToken(...)` and persist `localStorage.session_id` during restore/login.
    - `tests/integration/realtime/session-websocket-cutover.test.ts` still sees websocket `session_id` query fallback in `src/lib/websocket.ts`.
    - `tests/integration/admin-auth-flow.test.tsx` is now red on routed admin behavior under the shipped `/admin/*` path rather than the old standalone admin mount.

Ran slice-level checks:

- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`
  - **Passed** (1 passed, 3 skipped).
- `cd frontend-hormonia && npm run build`
  - **Passed**.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`
  - **Passed**.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
  - **Passed**.
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts`
  - **Red**: intended websocket query-fallback proof is still red, and unrelated/pre-existing failures also surfaced in `tests/unit/hooks/useWebSocket.test.ts`, `tests/unit/hooks/useWebSocket.comprehensive.test.ts`, and `src/utils/__tests__/init-validator.test.ts`.

## Diagnostics

To inspect this task later:

- Run the focused red pack to see which contract seam is still drifting:
  - shared HTTP client (`auth-headers.test.ts`, `core.test.ts`)
  - `AuthProvider` storage/rehydration (`session-first-cutover.test.tsx`)
  - routed admin entry (`admin-auth-flow.test.tsx`)
  - websocket bootstrap (`session-websocket-cutover.test.ts`)
- Run the single websocket diagnostic test to verify the stable auth error surface independently:
  - `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`
- Use the residue report/check commands to confirm the broader frontend legacy boundary stayed unchanged while the proof moved.

## Deviations

- Added an explicit failure-path verification command to `.gsd/milestones/M004/slices/S03/S03-PLAN.md` during pre-flight so the slice proves an inspectable websocket auth diagnostic, not only green-path reruns.
- The routed admin proof uses a minimal canonical `/login` harness in the test file rather than the lazy public login page component, so the red result reflects admin route behavior instead of Suspense noise.

## Known Issues

- The official frontend runtime still leaks the legacy contract on the happy path: `Authorization`, `X-Session-ID`, `localStorage.session_id`, and websocket `?session_id=` fallback all remain live until T02/T03 remove them.
- The routed admin proof is now red against the shipped `/admin/*` path. That is intentional for T01, but the exact runtime fix still belongs to later task work.
- The broader second slice verification pack still has unrelated/pre-existing failures in `tests/unit/hooks/useWebSocket.test.ts`, `tests/unit/hooks/useWebSocket.comprehensive.test.ts`, and `src/utils/__tests__/init-validator.test.ts`.

## Files Created/Modified

- `frontend-hormonia/tests/unit/api-client/auth-headers.test.ts` — rewrote shared-client header proof around cookie-first requests with no default `Authorization` / `X-Session-ID` emission.
- `frontend-hormonia/tests/lib/api-client/core.test.ts` — added focused core-request contract checks for empty session headers and CSRF-preserving, cookie-backed requests.
- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` — extended `AuthProvider` proof to reject `localStorage.session_id` persistence/rehydration and auth-token transport fallback while preserving user-safe diagnostics.
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` — reworked admin proof around the shipped routed `/admin/*` surface and canonical `/login` entrypoint.
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` — tightened realtime proof to reject websocket `session_id` query fallback while preserving stable auth diagnostics.
- `.gsd/milestones/M004/slices/S03/S03-PLAN.md` — added an explicit diagnostic verification command for the websocket auth failure surface.
- `.gsd/DECISIONS.md` — recorded that S03 routed admin proof now anchors on `adminRoutes` plus canonical `/login` instead of standalone `AdminApp` proof.
- `.gsd/milestones/M004/slices/S03/tasks/T01-SUMMARY.md` — recorded the red-first proof freeze, verification outcomes, and follow-on diagnostics for the next task.
