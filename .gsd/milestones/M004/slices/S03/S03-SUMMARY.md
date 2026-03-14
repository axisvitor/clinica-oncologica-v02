---
id: S03
parent: M004
milestone: M004
provides:
  - Official frontend `/login`, `/dashboard`, and the shipped `/admin/*` route tree now consume only the canonical cookie-backed session-first contract, with zero approved frontend auth/session/Firebase residue in the runtime verifier.
requires:
  - slice: S02
    provides: Canonical backend login, verify-session, restore, and logout semantics centered on `user_id`.
affects:
  - S04
  - S05
  - S06
key_files:
  - frontend-hormonia/src/app/providers/AuthContext.tsx
  - frontend-hormonia/src/lib/api-client/core.ts
  - frontend-hormonia/src/lib/api-client/auth.ts
  - frontend-hormonia/src/lib/api-client/enhanced-analytics.ts
  - frontend-hormonia/src/lib/websocket.ts
  - frontend-hormonia/src/hooks/useWebSocket.ts
  - frontend-hormonia/src/hooks/useMetricsWebSocket.ts
  - frontend-hormonia/src/types/admin.ts
  - frontend-hormonia/shared-types/src/admin.ts
  - frontend-hormonia/src/lib/api-client/normalizers.ts
  - frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx
  - frontend-hormonia/tests/integration/admin-auth-flow.test.tsx
  - frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
key_decisions:
  - Prove admin auth through the shipped `/admin/*` route tree plus canonical `/login`, not through a standalone `AdminApp` mount.
  - Keep compatibility auth token state in memory only; official frontend HTTP/auth/analytics requests stay cookie-backed with CSRF and never emit `Authorization` or `X-Session-ID`.
  - Allow session/auth state to gate realtime connect/reconnect behavior, but never serialize `session_id` into official websocket URLs or hook builders.
  - Keep S01 `frontend` residue scopes with `approved: []` so the verifier remains a hard reintroduction gate after S03.
patterns_established:
  - Frontend cutover proof is seam-level and absence-driven: tests pin the lack of `localStorage.session_id`, `Authorization`, `X-Session-ID`, Firebase-shaped canonical fields, and websocket `?session_id=` fallback.
  - Slice closeout is only valid when focused tests, build, routed admin proof, websocket diagnostics, and residue guard all describe the same live boundary.
observability_surfaces:
  - `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts src/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts`
  - `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`
  - `cd frontend-hormonia && npm run build`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
drill_down_paths:
  - .gsd/milestones/M004/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T03-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T04-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T05-SUMMARY.md
duration: ~10h35m
verification_result: passed
completed_at: 2026-03-14T12:51:10-03:00
---

# S03: Frontend oficial convergido para contrato session-first canônico

**The official frontend now runs on the canonical session-first contract end to end: `/login`, `/dashboard`, and routed `/admin/*` stay cookie-backed, emit no legacy session transport, carry no Firebase-shaped canonical frontend contract, and the runtime residue guard reports zero approved frontend residue.**

## What Happened

This slice started by freezing the frontend boundary in executable form. The focused Vitest pack now names the real seams that mattered for the cut: shared HTTP header emission, `AuthProvider` storage/rehydration behavior, routed admin access through the shipped router, websocket bootstrap, and the remaining narrative/type residue. That removed the old blind spot where frontend auth could still look green while legacy transport survived in shared helpers or while admin auth drift hid behind a standalone admin harness.

From there the auth/session cut happened at the shared seams, not page by page. `AuthContext`, the auth client, the shared request core, and the enhanced analytics client were converged to cookie-backed session semantics with CSRF preserved. The official happy path no longer persists or rehydrates `localStorage.session_id`, no longer calls `setAuthToken(session_id)` as part of login/restore, and no longer emits `Authorization: Bearer <session_id>` or `X-Session-ID` from shared frontend request paths.

Realtime was then brought onto the same contract. The shared websocket manager, the generic hook, and the metrics hook still use authenticated state to decide whether they should connect, but they no longer serialize `session_id` into the websocket handshake. The stable auth failure surface stayed intact: the dedicated diagnostic proof still anchors on `AUTH_WEBSOCKET_SESSION_INVALID` without reviving query-string fallback.

The remaining frontend residue was in narrative and types. Official auth/admin comments, readiness messaging, and admin-session wording were rewritten around backend-owned cookies plus `verify-session`/restore semantics. Canonical frontend/shared admin-user types and normalizers dropped `firebase_uid` and other Firebase-shaped baggage instead of carrying dead fields as optional noise. The routed admin proof was tightened to exercise the shipped `/admin/*` tree and finished with one small test-only fix: the mocked admin dashboard shell now renders an `<Outlet />`, so nested admin children prove the real route tree instead of stopping at the shell.

Finally, S01 and S03 were republished to describe the same post-cut boundary. The frontend scopes remain present in the runtime-residue allowlist with `approved: []`, so any reintroduction of `firebase_uid`, `Authorization`, `X-Session-ID`, websocket `?session_id=`, or Firebase-era narrative on the official frontend becomes explicit verifier drift instead of quiet regression. After S03, the only approved auth/session legacy left in the M004 residue map is backend-owned.

## Verification

Full slice closeout was replayed after the task work and passed:

- `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - Passed: 5 files, 29 tests.
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts src/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts`
  - Passed: 7 files, 108 tests.
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`
  - Passed: 1 test, 4 skipped.
- `cd frontend-hormonia && npm run build`
  - Passed.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`
  - Passed with `no approved residue`.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
  - Passed with `no approved residue`.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
  - Passed; only backend-owned approved legacy remained.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
  - Passed; frontend remained clean.

## Requirements Advanced

- R047 — Shrunk the official runtime boundary further by removing Firebase-era frontend transport, narrative, and canonical-type behavior from the shipped auth/admin/realtime path.
- R048 — Converged the official frontend onto the same canonical cookie-backed session contract already established in the backend, leaving only backend-owned legacy acceptance for S04.

## Requirements Validated

- R050 — Validated by the focused frontend proof packs, green routed `/login` → `/admin/*` integration coverage, green websocket diagnostic proof, green build, and a green residue guard showing zero approved frontend auth/session/Firebase residue.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The planned closeout still needed one targeted test-only fix: `tests/integration/admin-auth-flow.test.tsx` had to render an `<Outlet />` in the mocked admin dashboard shell so the routed proof could exercise nested admin children through the shipped `/admin/*` tree. The production router contract itself did not need another structural change.

## Known Limitations

Backend-owned legacy auth/session surfaces are still intentionally alive and remain the next slice boundary: root `/session/*`, `X-Session-ID`, session-as-Bearer fallback, backend websocket session query fallback, and backend/adjacent `firebase_uid` plus Firebase narrative residue still appear in the S01 verifier map and move to S04/S05/S06.

## Follow-ups

- S04: retire, reject, or tombstone backend acceptance of root `/session/*`, `X-Session-ID`, session-as-Bearer, and websocket query fallback now that the official frontend no longer depends on them.
- S05: remove remaining backend/adjacent `firebase_uid` and Firebase-era narrative/runtime residue outside the official frontend loop.
- S06: replay the assembled no-Firebase stack across `/login`, `/dashboard`, `/admin`, and `/whatsapp` with the final runtime boundary in place.

## Files Created/Modified

- `frontend-hormonia/src/app/providers/AuthContext.tsx` — removed browser `session_id` rehydration/persistence and kept the official auth loop cookie-backed.
- `frontend-hormonia/src/lib/api-client/core.ts` — removed `Authorization` / `X-Session-ID` emission from the shared request path while preserving CSRF and credentials.
- `frontend-hormonia/src/lib/api-client/auth.ts` — aligned login/verify-session helpers to cookie-backed session semantics only.
- `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts` — cut localStorage/header fallback and reused the shared CSRF lifecycle.
- `frontend-hormonia/src/lib/websocket.ts` — removed official websocket `session_id` query fallback and cleaned naming residue that still matched the verifier.
- `frontend-hormonia/src/hooks/useWebSocket.ts` — kept connect/reconnect gating but removed websocket query transport fallback.
- `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` — aligned metrics websocket bootstrap to the same cookie-first rule.
- `frontend-hormonia/src/types/admin.ts` — removed Firebase-shaped admin-user baggage from the canonical frontend type surface.
- `frontend-hormonia/shared-types/src/admin.ts` — removed Firebase-shaped shared admin-user fields from the canonical contract.
- `frontend-hormonia/src/lib/api-client/normalizers.ts` — stopped normalizing Firebase-era fields into official frontend user shapes.
- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` — froze the session-first HTTP/storage contract in executable proof.
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` — proved admin access through the shipped routed `/admin/*` tree and canonical `/login`.
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` — froze the no-`?session_id=` websocket boundary while preserving stable auth diagnostics.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — republished frontend scopes with `approved: []`.
- `.gsd/milestones/M004/slices/S03/S03-UAT.md` — published artifact-driven slice replay for the canonical frontend contract.

## Forward Intelligence

### What the next slice should know
- The official frontend no longer needs any backend legacy session transport. If S04 keeps accepting `/session/*`, `X-Session-ID`, session-as-Bearer, or websocket query fallback, that is backend inertia only, not a frontend dependency.
- The residue guard now encodes “frontend clean” as existing scopes with `approved: []`. Preserve that convention unless the verifier gains a better zero-scope representation.
- The routed admin proof is trustworthy again because it exercises the shipped `/admin/*` tree via canonical `/login`, not a standalone admin harness.

### What's fragile
- `tests/integration/admin-auth-flow.test.tsx` mock shell wiring — if future test refactors remove the mocked dashboard `<Outlet />`, nested route proof will go red even if runtime routing is still fine.
- `verify-runtime-residue.sh` frontend category naming — source-only helper renames can matter if they accidentally match category patterns again.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` — the fastest trustworthy signal that the official frontend has not reintroduced legacy auth/session/Firebase residue.
- `cd frontend-hormonia && npx vitest run tests/integration/admin-auth-flow.test.tsx` — the most direct routed proof for canonical `/login` plus shipped `/admin/*` behavior.
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"` — the tightest check that websocket auth diagnostics remained stable through the transport cut.

### What assumptions changed
- “The frontend cut is mostly an HTTP/header cleanup” — false; realtime bootstrap, routed admin proof, narrative surfaces, and canonical type baggage all needed explicit convergence.
- “Once the focused tests are green, the verifier will already agree” — false; the residue boundary still needed explicit allowlist republication and naming cleanup to turn the new frontend state into a durable regression gate.
