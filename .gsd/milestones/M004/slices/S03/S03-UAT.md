# S03: Frontend oficial convergido para contrato session-first canônico — UAT

**Milestone:** M004
**Written:** 2026-03-14T12:51:10-03:00

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S03 proves a frontend contract cut, not a live deployed behavior change. The slice definition, plan, and verification all anchor on focused Vitest/build/verifier replay rather than human interaction or an assembled runtime.

## Preconditions

- The repo is at the S03 tip on branch `gsd/M004/S03`.
- Frontend dependencies are installed in `frontend-hormonia/`.
- No local backend/frontend servers are required for this slice replay.
- The tester can run commands from the repo root.

## Smoke Test

Run:

`bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`

Expected: output shows `[frontend] - no approved residue` and ends with `RESULT: --check frontend OK`.

## Test Cases

### 1. Official HTTP/session auth path stays cookie-first

1. Run:
   - `cd frontend-hormonia`
   - `npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx`
2. Inspect the output.
3. **Expected:** 3 files pass / 21 tests pass. The output may include compatibility-only logs such as `Compatibility auth token cached`, but there must be no failing assertion about `Authorization`, `X-Session-ID`, `localStorage.session_id`, or `setAuthToken(session_id)` on the official login/restore/logout path.

### 2. Canonical `/login` still gates the shipped `/admin/*` route tree

1. Run:
   - `cd frontend-hormonia`
   - `npx vitest run tests/integration/admin-auth-flow.test.tsx`
2. Inspect the output.
3. **Expected:** all 3 tests pass. The proof should cover redirect/gating through canonical `/login` plus successful routed navigation to nested admin children under `/admin/*` rather than a standalone admin harness.

### 3. Realtime bootstrap is cookie-first and keeps stable auth diagnostics

1. Run:
   - `cd frontend-hormonia`
   - `npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts`
2. Then run:
   - `npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`
3. Inspect the output from both commands.
4. **Expected:** the broader realtime pack passes with no `?session_id=` regression, and the targeted diagnostic run passes with 1 passing test / 4 skipped while still anchoring on `AUTH_WEBSOCKET_SESSION_INVALID`.

### 4. Narrative, canonical types, build, and residue guard all agree on the post-cut frontend state

1. Run:
   - `cd frontend-hormonia`
   - `npx vitest run tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts src/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts`
2. Still in `frontend-hormonia`, run:
   - `npm run build`
3. Return to the repo root and run:
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
4. **Expected:** the type/narrative pack passes; `npm run build` succeeds; frontend report/check both say `no approved residue`; all-scope report/check stay green and list only backend-owned approved residue.

## Edge Cases

### Compatibility token setters stay isolated from the official HTTP path

1. Run the Case 1 command pack.
2. **Expected:** logs may mention compatibility auth token caching/clearing, but the tests still pass and prove that shared requests remain cookie-backed with no `Authorization` or `X-Session-ID` emission.

### Invalid websocket sessions still produce stable frontend diagnostics

1. Run the targeted diagnostic command from Case 3.
2. **Expected:** the test passes and continues to anchor on the stable websocket auth code (`AUTH_WEBSOCKET_SESSION_INVALID`) rather than falling back to transport-specific behavior.

### The residue guard fails on any frontend reintroduction

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` after any experimental change touching auth/session/frontend runtime seams.
2. **Expected:** the command remains green only while the frontend scope stays empty. Any reported frontend category/file hit is a slice regression, not acceptable drift.

## Failure Signals

- Any failure in `tests/unit/api-client/auth-headers.test.ts`, `tests/lib/api-client/core.test.ts`, or `tests/integration/auth/session-first-cutover.test.tsx` mentioning `Authorization`, `X-Session-ID`, `session_id`, or storage rehydration.
- `tests/integration/admin-auth-flow.test.tsx` failing to reach/render nested admin child routes.
- `tests/integration/realtime/session-websocket-cutover.test.ts` or the websocket hook packs failing on `?session_id=` or missing auth-code diagnostics.
- `npm run build` failing on admin/user type drift or route/build regressions.
- `verify-runtime-residue.sh --report frontend` or `--check frontend` reporting any frontend residue instead of `no approved residue`.

## Requirements Proved By This UAT

- R050 — Confirms the official frontend auth/admin/realtime path now uses only the canonical session-first contract, without functional Firebase residue, legacy browser-carried session transport, or Firebase-shaped canonical frontend types.
- R047 — Supports the broader no-Firebase runtime goal by proving the official frontend no longer treats Firebase as a live contract.
- R048 — Supports the canonical auth/session convergence by proving the frontend side of the contract is singular and cookie-backed.

## Not Proven By This UAT

- Backend retirement/tombstoning of root `/session/*`, `X-Session-ID`, session-as-Bearer fallback, or backend websocket query fallback; that belongs to S04.
- Backend/adjacent `firebase_uid` and Firebase narrative/cache residue outside the official frontend loop; that belongs to S05.
- Assembled local stack proof with Firebase Auth envs blank across `/dashboard`, `/admin`, and `/whatsapp`; that belongs to S06.

## Notes for Tester

- Some passing logs still mention compatibility auth token caching. In S03 that is acceptable because the value is isolated in memory only and no longer leaves the browser as an official transport.
- `--report all` and `--check all` are expected to list backend-owned approved residue. That is not a failure for S03; only frontend residue would be.
- If the routed admin test fails while URL assertions pass but nested content disappears, inspect the mocked dashboard shell in `tests/integration/admin-auth-flow.test.tsx` first; the proof depends on that mock exposing an `<Outlet />`.
