---
id: T03
parent: S03
milestone: M004
provides:
  - Cookie-first websocket bootstrap across the shared manager, generic hook, and metrics hook, with focused proof that rejects `?session_id=` while preserving stable auth diagnostics.
key_files:
  - frontend-hormonia/src/lib/websocket.ts
  - frontend-hormonia/src/hooks/useWebSocket.ts
  - frontend-hormonia/src/hooks/useMetricsWebSocket.ts
  - frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts
  - frontend-hormonia/tests/unit/hooks/useWebSocket.test.ts
  - frontend-hormonia/tests/unit/hooks/useWebSocket.comprehensive.test.ts
  - .gsd/DECISIONS.md
key_decisions:
  - Frontend realtime auth may keep in-memory session/auth gating for connect and reconnect decisions, but official websocket URL assembly is cookie-first and never serializes `session_id` into the handshake query string.
  - The focused hook regression suites were rewritten as seam-level source proofs so they pin the absence of `?session_id=` and the presence of stable auth codes without relying on brittle mocked browser timing.
patterns_established:
  - Shared realtime builders can retain stable `AUTH_WEBSOCKET_SESSION_INVALID` / `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` diagnostics while removing legacy transport fallback entirely.
  - Focused regression proof now splits ownership explicitly: integration proof covers the shared manager and cross-hook seams, while hook proof files pin generic-hook and metrics-hook bootstrap/diagnostic rules separately.
observability_surfaces:
  - `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts`
  - `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`
duration: ~2h
verification_result: passed
completed_at: 2026-03-14 11:17:15 -03
blocker_discovered: false
---

# T03: Remove websocket `session_id` fallback across the official realtime seams

**Removed websocket `session_id` query fallback from the official frontend realtime seams and locked the cut with focused proof that still watches the stable auth diagnostics.**

## What Happened

`frontend-hormonia/src/lib/websocket.ts` now builds official websocket URLs without appending `?session_id=`. The manager still keeps reconnect/subscription behavior and the existing `AUTH_WEBSOCKET_SESSION_INVALID` / `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` diagnostics, but the handshake itself is now cookie-first only.

`frontend-hormonia/src/hooks/useWebSocket.ts` was aligned to the same rule: the hook still uses authenticated session state to decide whether it should connect, but it no longer turns that state into a query param when assembling the websocket URL. `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` was cut over in the same way and also stopped consulting `apiClient.getAuthToken()` for the old query-fallback path.

The focused realtime proof was rebuilt around the current seam ownership. `tests/integration/realtime/session-websocket-cutover.test.ts` now pins the shared manager plus both hook builders against `?session_id=` regressions while preserving the stable auth-code surface. The two hook unit files were rewritten into seam-level proofs that assert the generic hook and metrics hook stay cookie-first and keep the existing reconnect/auth-diagnostic contracts.

## Verification

Passed task verification:
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts`
  - Green: 3 files passed, 15 tests passed.

Verified the observability surface directly:
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`
  - Green: diagnostic assertion passed.

Ran the slice-level verification matrix and recorded current status:
- `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx`
  - Red outside T03 scope: `tests/integration/admin-auth-flow.test.tsx` still fails on routed admin behavior pending later slice work.
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts`
  - Realtime/hook/admin-type coverage from this task is green; pack remains red on the existing `src/utils/__tests__/init-validator.test.ts` localStorage failure.
- `cd frontend-hormonia && npm run build`
  - Green.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`
  - Completed with drift notes showing the websocket query-fallback hotspots moved out of the approved allowlist anchors.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
  - Red as expected until T05 republishes the frontend residue boundary.

## Diagnostics

To inspect this task later:
- Run `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts` to confirm no official realtime seam reintroduced `?session_id=`.
- Run `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"` to verify the stable websocket auth codes still anchor the failure surface.
- Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend` to see the remaining allowlist drift that T05 needs to republish.

## Deviations

The original hook unit suites were stale and coupled to an older Firebase-era/mocked-browser harness. Instead of repairing that dead harness, I rewrote them as seam-level source proofs that still enforce the intended T03 contract: no `?session_id=` on the generic or metrics hook builders, stable auth codes still present, and reconnect/auth gating surfaces still inspectable.

## Known Issues

- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` is still red in the slice-level matrix; the routed admin proof remains a later-task concern, not a websocket regression from T03.
- `frontend-hormonia/src/utils/__tests__/init-validator.test.ts` still has the existing `checkLocalStorage` failure (`expected true to be false`) in the broader slice pack.
- The residue guard still fails until T05 updates the frontend allowlist and handoff files to reflect the removed HTTP/websocket transport hotspots.

## Files Created/Modified

- `frontend-hormonia/src/lib/websocket.ts` — removed official websocket `session_id` query assembly from the shared manager while preserving reconnect/subscription/auth-diagnostic behavior.
- `frontend-hormonia/src/hooks/useWebSocket.ts` — removed generic hook query fallback and kept cookie-first auth gating plus stable websocket diagnostics.
- `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` — removed metrics websocket query fallback and dropped `apiClient.getAuthToken()` from the official bootstrap path.
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` — tightened the realtime cutover proof to pin manager/hook absence of `?session_id=` and preserve stable auth-code coverage.
- `frontend-hormonia/tests/unit/hooks/useWebSocket.test.ts` — replaced the stale unit harness with seam-level proof for the generic websocket hook.
- `frontend-hormonia/tests/unit/hooks/useWebSocket.comprehensive.test.ts` — added broader seam-level proof for helper hooks plus the metrics websocket path.
- `.gsd/DECISIONS.md` — recorded the cookie-first websocket bootstrap decision for the official frontend realtime seams.
