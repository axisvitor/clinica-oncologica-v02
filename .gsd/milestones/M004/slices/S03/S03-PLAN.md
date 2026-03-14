# S03: Frontend oficial convergido para contrato session-first canônico

**Goal:** Converge the official frontend loop on the canonical session-first contract so `/login`, `/dashboard`, and the shipped `/admin/*` route tree stop depending on legacy session transports, Firebase-era semantics, or Firebase-shaped canonical types in the happy path.
**Demo:** Focused frontend proof passes while `AuthProvider`, the shared API clients, and the websocket builders use only cookie-backed session restore/verify semantics for the official app; the real routed `/admin/*` path is proven through the shipped router and canonical `/login` entrypoint; and the official auth/admin surfaces no longer treat Firebase as a live runtime contract.

## Requirement Coverage

- Owned by this slice: **R050** — O frontend oficial usa apenas o contrato canônico sem resíduo funcional de Firebase.
- Supported by this slice: **R047** — Firebase sai de vez do runtime oficial.
- Supported by this slice: **R048** — Auth/sessão converge para um contrato canônico único.
- Not claimed here: retiring backend acceptance of root `/session/*`, `X-Session-ID`, session-as-Bearer, and websocket query fallback stays for S04; adjacent/runtime-wide Firebase residue beyond the official frontend loop stays for S05; assembled no-Firebase stack proof stays for S06.
- Not planned here: reopening `/admin/login` as a public routed entrypoint. The canonical unauthenticated entrypoint remains `/login`, and S03 proof should exercise the shipped protected `/admin/*` tree instead of a standalone `AdminApp` mount.

## Must-Haves

- `/login`, `/dashboard`, and the shipped `/admin/*` route tree use the shared session-first contract through `AuthProvider` and the official router, with proof anchored on canonical `/login` rather than Firebase-era or standalone admin auth behavior.  
  _Advances: R050, supports R048_
- The official frontend stops emitting legacy session transports on the happy path: no `session_id` browser persistence for staff auth, no `Authorization: Bearer <session_id>`, no `X-Session-ID`, and no websocket `?session_id=` fallback from the shared frontend seams that power `/dashboard` and `/admin`.  
  _Advances: R050, supports R047, R048_
- Official auth/admin runtime narrative and canonical user/admin type surfaces stop treating Firebase or `firebase_uid` as part of the live frontend contract.  
  _Advances: R050, supports R047_
- The slice closes with focused frontend proof, a green build, and a shrunk S01 frontend residue boundary so later slices inherit an honest map of what auth/session legacy remains on purpose.  
  _Advances: R050, supports R047, R048_

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx`
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts`
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`
- `cd frontend-hormonia && npm run build`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`

## Observability / Diagnostics

- Runtime signals: session restore/login/logout still surface user-safe auth errors from the shared auth client/provider, websocket auth keeps stable diagnostics such as `AUTH_WEBSOCKET_SESSION_INVALID`, and init/session readiness messaging remains inspectable through the existing frontend validation surfaces.
- Inspection surfaces: the focused Vitest files above, `npm run build` for canonical type drift, and `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend` for the live frontend residue map.
- Failure visibility: the proof must distinguish HTTP header/session-storage leakage, websocket query-fallback leakage, routed admin-entry drift, and stale narrative/type residue instead of collapsing them into a generic auth failure.
- Redaction constraints: never log or assert on raw cookies, session tokens, passwords, or secret-bearing storage values; keep diagnostics to presence/absence, stable error codes, route outcomes, and user-safe metadata.

## Integration Closure

- Upstream surfaces consumed: `frontend-hormonia/src/app/providers/AuthContext.tsx`, `frontend-hormonia/src/lib/api-client/core.ts`, `frontend-hormonia/src/lib/api-client/auth.ts`, `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts`, `frontend-hormonia/src/lib/websocket.ts`, `frontend-hormonia/src/hooks/useWebSocket.ts`, `frontend-hormonia/src/hooks/useMetricsWebSocket.ts`, `frontend-hormonia/src/app/routes/routeDefinitions.tsx`, `frontend-hormonia/src/app/routes/AdminRoutes.tsx`, `frontend-hormonia/src/AdminApp.tsx`, `frontend-hormonia/src/features/admin/AdminSessionManager.tsx`, `frontend-hormonia/src/hooks/auth/useSessionManagement.ts`, `frontend-hormonia/src/utils/init-validator.ts`, `frontend-hormonia/src/types/admin.ts`, `frontend-hormonia/shared-types/src/admin.ts`, `frontend-hormonia/src/lib/api-client/admin.ts`, `frontend-hormonia/src/lib/api-client/normalizers.ts`, and the focused frontend test suites listed above.
- New wiring introduced in this slice: the official frontend auth/admin/realtime path composes entirely through cookie-backed login/verify-session/restore semantics plus the shipped protected router, with no browser-carried legacy transport fallback on the official happy path.
- What remains before the milestone is truly usable end-to-end: S04 must retire or tombstone backend legacy transport acceptance and root `/session/*`, S05 must remove adjacent Firebase runtime residue outside the official frontend loop, and S06 must replay the assembled no-Firebase stack across the critical routes.

## Tasks

- [x] **T01: Freeze routed frontend proof for the canonical session-first contract** `est:1h`
  - Why: The current frontend packs are close, but they still miss the shipped `/admin/*` route tree and tolerate legacy transport behavior; the slice should start by pinning the real boundary in executable form before code moves.
  - Files: `frontend-hormonia/tests/unit/api-client/auth-headers.test.ts`, `frontend-hormonia/tests/lib/api-client/core.test.ts`, `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx`, `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx`, `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts`
  - Do: Update the focused frontend proof so it asserts cookie-first login/restore/logout without `localStorage.session_id`, no `Authorization` or `X-Session-ID` emission on official fetch paths, no websocket `?session_id=` fallback, and routed `/admin/*` access through the shipped protected router and canonical `/login`; run the pack red-first so failures point at the current transport/query/localStorage blind spots rather than setup noise.
  - Verify: `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - Done when: the focused tests express the intended canonical frontend contract and fail for the current legacy transport/admin-route behavior instead of unrelated fixture instability.
- [x] **T02: Remove HTTP and browser-storage legacy session transports from shared auth seams** `est:2h`
  - Why: The official frontend still leaks the old contract through `AuthProvider` and shared fetch helpers, so the HTTP/localStorage cut has to happen at the central seams rather than page by page.
  - Files: `frontend-hormonia/src/app/providers/AuthContext.tsx`, `frontend-hormonia/src/lib/api-client/auth.ts`, `frontend-hormonia/src/lib/api-client/core.ts`, `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts`, `frontend-hormonia/tests/unit/api-client/auth-headers.test.ts`, `frontend-hormonia/tests/lib/api-client/core.test.ts`, `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx`
  - Do: Stop persisting/restoring `session_id` in browser storage for staff auth, stop calling `apiClient.setAuthToken(session_id)` on login/restore, remove `Authorization` and `X-Session-ID` header injection from the shared request path plus the direct analytics client that still reads storage, and keep `credentials: 'include'`, CSRF handling, and user-safe auth diagnostics intact.
  - Verify: `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx`
  - Done when: the official HTTP auth/session path is cookie-backed and session-first without browser-stored `session_id` or legacy session headers, and the focused auth/client proof is green.
- [x] **T03: Remove websocket `session_id` fallback across the official realtime seams** `est:1h`
  - Why: Cleaning only the HTTP path would leave the realtime path silently preserving the legacy contract, and the manager plus both hooks have to converge together to avoid drift.
  - Files: `frontend-hormonia/src/lib/websocket.ts`, `frontend-hormonia/src/hooks/useWebSocket.ts`, `frontend-hormonia/src/hooks/useMetricsWebSocket.ts`, `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts`, `frontend-hormonia/tests/unit/hooks/useWebSocket.test.ts`, `frontend-hormonia/tests/unit/hooks/useWebSocket.comprehensive.test.ts`
  - Do: Remove websocket URL assembly that appends `session_id` query fallback, keep cookie-first bootstrap and stable auth diagnostics intact, and align the generic and metrics hooks with the shared websocket manager so no alternate official path can reintroduce the legacy query transport.
  - Verify: `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts`
  - Done when: no official websocket bootstrap path emits `?session_id=` and the focused realtime proof stays green with the existing auth/connection diagnostics.
- [x] **T04: Clean official auth/admin narrative and canonical type surfaces** `est:2h`
  - Why: R050 is not just a transport cut — the shipped frontend also has to stop describing Firebase as live behavior and stop carrying Firebase-shaped canonical admin/user contracts.
  - Files: `frontend-hormonia/src/AdminApp.tsx`, `frontend-hormonia/src/features/admin/AdminSessionManager.tsx`, `frontend-hormonia/src/hooks/auth/useSessionManagement.ts`, `frontend-hormonia/src/utils/init-validator.ts`, `frontend-hormonia/src/types/admin.ts`, `frontend-hormonia/shared-types/src/admin.ts`, `frontend-hormonia/src/lib/api-client/admin.ts`, `frontend-hormonia/src/lib/api-client/normalizers.ts`
  - Do: Rewrite Firebase-era comments/copy/logs in the official auth/admin surfaces to describe backend cookies + verify-session/session readiness, remove `firebase_uid` and Firebase-auth baggage from canonical admin/user types and normalizers where the official runtime no longer reads them, update the coupled tests/build expectations, and leave `src/app/routes/AdminRoutes.lazy.tsx` alone unless the canonical runtime or build forces a minimal targeted cleanup.
  - Verify: `cd frontend-hormonia && npx vitest run tests/integration/admin-auth-flow.test.tsx tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts tests/unit/hooks/useSessionManagement.test.ts src/utils/__tests__/init-validator.test.ts && npm run build`
  - Done when: official auth/admin runtime copy and canonical types no longer treat Firebase as a live frontend contract, and the focused admin/type/build proof is green.
- [x] **T05: Shrink the frontend residue boundary and publish the S03 handoff** `est:1h`
  - Why: S03 is only durable if the S01 frontend residue guard shrinks with the code and the slice leaves an explicit handoff for S04/S05/S06 about what legacy auth/session surface still remains on purpose.
  - Files: `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M004/slices/S01/S01-UAT.md`, `.gsd/milestones/M004/slices/S03/S03-SUMMARY.md`, `.gsd/milestones/M004/slices/S03/S03-UAT.md`
  - Do: Re-run the frontend residue report after the transport/narrative cleanup, update the S01 allowlist and handoff artifacts for removed or moved frontend hotspots, then write S03 summary/UAT artifacts that name the canonical frontend contract, the routed `/login` → `/dashboard` → `/admin` proof, and the exact backend-owned legacy surfaces still left for later slices.
  - Verify: `(cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts && npm run build) && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
  - Done when: the frontend residue boundary is reduced to intentional leftovers, S01 and S03 artifacts tell the same story, and the focused frontend proof, build, and residue guard are all green.

## Files Likely Touched

- `frontend-hormonia/src/app/providers/AuthContext.tsx`
- `frontend-hormonia/src/lib/api-client/auth.ts`
- `frontend-hormonia/src/lib/api-client/core.ts`
- `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts`
- `frontend-hormonia/src/lib/websocket.ts`
- `frontend-hormonia/src/hooks/useWebSocket.ts`
- `frontend-hormonia/src/hooks/useMetricsWebSocket.ts`
- `frontend-hormonia/src/AdminApp.tsx`
- `frontend-hormonia/src/features/admin/AdminSessionManager.tsx`
- `frontend-hormonia/src/hooks/auth/useSessionManagement.ts`
- `frontend-hormonia/src/utils/init-validator.ts`
- `frontend-hormonia/src/types/admin.ts`
- `frontend-hormonia/shared-types/src/admin.ts`
- `frontend-hormonia/src/lib/api-client/admin.ts`
- `frontend-hormonia/src/lib/api-client/normalizers.ts`
- `frontend-hormonia/tests/unit/api-client/auth-headers.test.ts`
- `frontend-hormonia/tests/lib/api-client/core.test.ts`
- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx`
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx`
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts`
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`
- `.gsd/milestones/M004/slices/S03/S03-SUMMARY.md`
- `.gsd/milestones/M004/slices/S03/S03-UAT.md`
