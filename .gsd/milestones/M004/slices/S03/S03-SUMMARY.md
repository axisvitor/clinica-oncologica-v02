---
id: S03
parent: M004
milestone: M004
provides:
  - The official frontend loop now uses the canonical session-first contract end to end, with routed `/login` → protected `/dashboard` / `/admin/*` proof, zero approved frontend residue in the S01 guard, and a precise handoff for the backend-owned legacy still left for S04–S06.
requires:
  - slice: S02
    provides: Backend auth/session helpers and the public dependency surface now converge on one canonical `user_id`-first contract, leaving transport and adjacent compatibility residue explicit for frontend cutover.
affects:
  - M004/S04
  - M004/S05
  - M004/S06
key_files:
  - frontend-hormonia/src/app/providers/AuthContext.tsx
  - frontend-hormonia/src/lib/api-client/core.ts
  - frontend-hormonia/src/lib/api-client/auth.ts
  - frontend-hormonia/src/lib/api-client/enhanced-analytics.ts
  - frontend-hormonia/src/lib/websocket.ts
  - frontend-hormonia/src/hooks/useWebSocket.ts
  - frontend-hormonia/src/app/routes/AdminRoutes.tsx
  - frontend-hormonia/tests/integration/admin-auth-flow.test.tsx
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S03/S03-UAT.md
key_decisions:
  - The official frontend contract is cookie-backed login/restore/verify-session semantics only; `session_id` compatibility values may exist in memory for gating, but not as browser storage, HTTP headers, or websocket query transport.
  - Canonical unauthenticated entry is `/login`; `/admin/login` remains a protected routed path that redirects into `/login`, and admin proof must re-enter the shipped `/admin/*` tree rather than a standalone shell.
  - Once the frontend residue count hit zero, the S01 frontend scopes stayed in place with empty approved sets so the verifier acts as a reintroduction guard instead of losing vocabulary.
patterns_established:
  - Red-first seam-level proof names legacy HTTP header, browser storage, websocket query, routed admin-entry, and narrative/type residue directly instead of relying on broad auth smoke outcomes.
  - Slice closeout requires the focused proof, build, residue report, residue check, and slice handoff artifacts to agree on the same reduced boundary.
observability_surfaces:
  - cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts
  - cd frontend-hormonia && npm run build
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all
  - cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"
drill_down_paths:
  - .gsd/milestones/M004/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T03-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T04-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T05-SUMMARY.md
duration: ~7h
verification_result: passed
completed_at: 2026-03-14T11:55:43-03:00
---

# S03: Frontend oficial convergido para contrato session-first canônico

**The official frontend loop now proves cookie-backed `/login` → `/dashboard` / `/admin/*` behavior without legacy session transports, Firebase-shaped canonical baggage, or any approved frontend residue in the S01 guard.**

## What Happened

T01 started by freezing the real failure surface in focused proof. Instead of broad auth smoke tests, the slice pinned exact seams: shared HTTP requests must stay free of `Authorization` and `X-Session-ID`, `AuthProvider` must not rehydrate `localStorage.session_id`, the routed admin flow must go through canonical `/login` and back into the shipped `/admin/*` tree, and websocket bootstrap must stop serializing `?session_id=` while keeping stable auth diagnostics like `AUTH_WEBSOCKET_SESSION_INVALID`.

T02 and T03 then cut the official transport seams themselves. `AuthProvider`, the shared API clients, and the analytics client stopped persisting or translating `session_id` into frontend-owned HTTP transport. The shared websocket manager and hook family stopped assembling websocket URLs with `session_id` query fallback; only in-memory session/auth gating remains for connect and reconnect decisions. Stable auth diagnostics stayed intact, so the failure surface is still observable without preserving the old transport.

T04 and T05 finished the canonical story and the handoff. Official auth/admin narrative and canonical admin/user type surfaces dropped Firebase-shaped baggage. The last routed proof gap turned out to be test-only: the mocked `AdminDashboard` shell in `admin-auth-flow.test.tsx` needed to render an `<Outlet />` so nested admin child routes could appear. Once that was fixed, the routed proof passed for all three cases the slice needed: `/admin/login` redirects to `/login`, successful login returns to `/admin/system/compensation`, and an already-authenticated admin restores directly into `/admin/templates`. The S01 boundary was then republished to show the honest post-S03 state: `frontend` now has `no approved residue`, while all remaining approved categories are backend-owned.

## Verification

Passed on slice closeout rerun:

- `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts`
- `cd frontend-hormonia && npm run build`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

Observability/diagnostic surfaces confirmed on rerun:

- Focused Vitest failures still distinguish HTTP/storage leakage, websocket query leakage, routed admin-entry drift, and narrative/type drift instead of collapsing into generic auth failure.
- `npm run build` stayed green after the canonical type cleanup.
- `--report frontend` / `--check frontend` now print `no approved residue`.
- `--report all` / `--check all` show the backend-only legacy map later slices still own.
- The websocket proof still preserves stable auth error-code visibility such as `AUTH_WEBSOCKET_SESSION_INVALID`.

## Requirements Advanced

- R047 — The official frontend no longer treats Firebase narrative, Firebase-shaped canonical types, or legacy session transport as live runtime behavior.
- R048 — The frontend side of auth/session now converges on one canonical session-first contract and hands the remaining legacy transport work off explicitly to backend-owned slices.

## Requirements Validated

- R050 — The official frontend now uses only the canonical contract on the happy path, and the residue guard confirms there is no approved frontend runtime residue left in scope.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- T05 needed one targeted test-only fix that was not called out in the written plan: the mocked `AdminDashboard` shell in `tests/integration/admin-auth-flow.test.tsx` had to render `<Outlet />` so the routed admin proof could exercise nested child routes. The shipped runtime route tree was already correct; only the mock shell was masking it.

## Known Limitations

- Backend legacy transport acceptance is still live by design. `root_legacy_session`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query` still appear in backend scope and remain S04 work.
- Backend `firebase_uid` compatibility residue is still live in helper/cache/admin-adjacent paths and remains S05 work.
- S03 proves the official frontend path and the residue boundary, not the fully assembled stack with every deferred backend/runtime surface removed.

## Follow-ups

- S04 should retire the backend-owned legacy transport surfaces explicitly: `root_legacy_session`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, and the backend `firebase_narrative` concentrated in `auth_session.py`.
- S05 should remove the remaining backend/adjacent `firebase_uid` residue that survives after transport retirement and clean any adjacent runtime Firebase baggage outside the official frontend loop.
- S06 should replay the assembled no-Firebase stack across the critical routes once the backend compatibility surfaces are gone.
- Any later slice that changes the approved residue boundary must update the S01 allowlist, S01 handoff artifacts, and the current slice handoff in the same change.

## Files Created/Modified

- `frontend-hormonia/src/app/providers/AuthContext.tsx` — removed browser `session_id` rehydration/persistence from the official auth path while keeping user-safe auth-phase diagnostics.
- `frontend-hormonia/src/lib/api-client/auth.ts` — stopped emitting `X-Session-ID` and `Authorization: Bearer <session_id>` on official requests.
- `frontend-hormonia/src/lib/api-client/core.ts` — kept compatibility-only in-memory auth token handling without translating it into legacy shared-request headers.
- `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts` — reused the shared cookie+CSRF client path instead of localStorage/header fallback.
- `frontend-hormonia/src/lib/websocket.ts` — removed official websocket query fallback and kept cookie-first auth diagnostics visible.
- `frontend-hormonia/src/hooks/useWebSocket.ts` — aligned hook-level websocket bootstrap with the shared cookie-first manager and kept stable auth error handling.
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` — proved the canonical routed `/login` → `/admin/*` flow and fixed the mock shell to expose nested route content.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — republished the S01 boundary so frontend scopes remain present but carry zero approved hotspots.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M004/slices/S01/S01-UAT.md` — updated the shared residue handoff to match the post-S03 live report.
- `.gsd/milestones/M004/slices/S03/S03-SUMMARY.md` and `.gsd/milestones/M004/slices/S03/S03-UAT.md` — published the slice closeout, replay checklist, and backend-owned legacy handoff.

## Forward Intelligence

### What the next slice should know
- The official frontend boundary is now clean enough that any new frontend auth/session residue should be treated as a regression before anything else.
- The remaining approved legacy categories are backend-owned and already named precisely by the S01 verifier; use those ids and scopes verbatim in later handoffs.
- The routed admin proof is worth keeping focused: it now proves the real `/admin/*` tree through canonical `/login` without relying on a standalone `AdminApp` mount.

### What's fragile
- `backend-hormonia/app/routers/auth_session.py` — it still concentrates root-route legacy transport handling, Firebase narrative, and `firebase_uid` residue, so S04 changes here will move multiple anchors at once.
- `backend-hormonia/app/api/websockets.py` and `app/api/v2/**` transport helpers — once S04 starts removing acceptance paths, residue counts and anchors will move together quickly.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend` — fastest way to confirm the official frontend still has zero approved residue.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` — live map of the backend-only approved residue still left for S04/S05.
- `cd frontend-hormonia && npx vitest run tests/integration/admin-auth-flow.test.tsx` — trusted routed proof for canonical `/login` entry and re-entry into the shipped `/admin/*` tree.
- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"` — trusted proof that the websocket auth failure surface stayed stable after the transport cut.

### What assumptions changed
- "The residue report would still show some approved frontend hotspots after the transport cut" — not true; the correct post-S03 state is zero approved frontend residue.
- "The remaining routed admin failure meant the shipped route tree was still wrong" — not true; the runtime was correct and the last failing seam was a test-only mock shell missing `<Outlet />`.
