---
id: S03
parent: M003
milestone: M003
provides:
  - Split the frontend api-client/type hotspot behind stable façades, with `index.ts` reduced to a composition seam and `types.ts` reduced to a transport barrel over domain-owned DTO modules.
requires:
  - slice: S01
    provides: Frontend hotspot ranking, client/type guardrails, and proof-before-deletion constraints.
affects:
  - S04
  - S05
  - frontend-hormonia
key_files:
  - frontend-hormonia/src/lib/api-client.ts
  - frontend-hormonia/src/lib/api-client/index.ts
  - frontend-hormonia/src/lib/api-client/types.ts
  - frontend-hormonia/src/lib/api-client/types/physician.ts
  - frontend-hormonia/src/hooks/usePatients.ts
  - frontend-hormonia/tests/lib/api-client/index-split.contract.test.ts
  - frontend-hormonia/tests/unit/types/api-client-types-barrel.contract.test.ts
  - frontend-hormonia/tests/integration/api-client.test.ts
key_decisions:
  - Keep `@/lib/api-client`, `@/lib/api-client/types`, and `@/types/api` as stable façades while clarifying ownership underneath them.
  - Make `RiskAssessmentRequest` canonically owned by `src/lib/api-client/types/physician.ts` and keep it visible through the barrel instead of letting duplicate declarations drift.
  - Treat `src/lib/types/api.ts` as compat-only residue once its last live caller moved to canonical owners.
patterns_established:
  - Extract namespace-specific `createXApi(client)` modules and keep `index.ts` as pure composition rather than inline method ownership.
  - Move transport DTO ownership into domain files under `src/lib/api-client/types/*` and keep the public barrel stable while live callers migrate.
observability_surfaces:
  - cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts
  - cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts
  - cd frontend-hormonia && npm run typecheck && npm run build
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend
drill_down_paths:
  - .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S03/tasks/T03-SUMMARY.md
  - .gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md
duration: ~2h30m across 4 tasks
verification_result: passed
completed_at: 2026-03-13T03:54:01Z
---

# S03: Frontend Client/Type Surface Refactor

**S03 turned the frontend client/type hotspot into explicit composition and ownership seams while keeping the public façades stable and the focused frontend proof green.**

## What Happened

T01 started with red structural contract tests. Those tests pinned the public client façade, the planned extracted client modules, the transport-type barrel wiring, the canonical owner for `RiskAssessmentRequest`, and the migration of `usePatients.ts` off the compat type barrel.

T02 extracted the operational and admin namespaces out of `src/lib/api-client/index.ts` into dedicated `createXApi(client)` modules (`messages`, `flows`, `alerts`, `reports`, `notifications`, `admin-legacy`, `admin-users`) and reduced the main file to a composition seam.

T03 finished the remaining namespace split (`ai`, `quiz`, `quizzes`, `physician`) and replaced `src/lib/api-client/types.ts` with a stable barrel over domain-owned DTO modules. `RiskAssessmentRequest` became canonically owned by `src/lib/api-client/types/physician.ts`, and `usePatients.ts` moved to canonical type imports.

T04 closed the live compat seam and the stale proof drift. It aligned the remaining tests with the session-first runtime contract, fixed the lingering websocket typecheck failures, refreshed the S01 frontend verifier anchors, and closed the slice with green frontend structural/integration/type/build proof.

## Verification

Passed slice-close proof:
- `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd frontend-hormonia && npm run test -- src/hooks/__tests__/usePatients.test.ts tests/unit/types-validation.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- frontend structural seam check: `src/lib/api-client/index.ts` reduced to 223 lines, `src/lib/api-client/types.ts` reduced to 26 lines, and no live `lib/types/api` imports remained
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`

## Requirements Advanced

- R034 — materially reduced the targeted frontend hotspot.
- R037 — preserved session-first auth/client behavior and admin/dashboard consumption while internals moved.
- R038 — left explicit client/type ownership maps that future work can change locally.
- R039 — tied the structural refactor to green focused integration, typecheck, build, and verifier proof.

## Requirements Validated

- none — milestone-level visible-contract and integrated-proof acceptance still depended on S04/S05.

## Files Created/Modified

- `frontend-hormonia/src/lib/api-client/index.ts` — reduced to client composition only.
- `frontend-hormonia/src/lib/api-client/messages.ts`, `flows.ts`, `alerts.ts`, `reports.ts`, `notifications.ts`, `admin-legacy.ts`, `admin-users.ts`, `ai.ts`, `quiz.ts`, `quizzes.ts`, `physician.ts` — extracted namespace owners.
- `frontend-hormonia/src/lib/api-client/types.ts` — reduced to the stable transport barrel.
- `frontend-hormonia/src/lib/api-client/types/*.ts` — established domain-owned transport DTO modules.
- `frontend-hormonia/src/hooks/usePatients.ts` — moved off the compat type barrel.
- `frontend-hormonia/tests/lib/api-client/index-split.contract.test.ts` — pinned the client composition seam.
- `frontend-hormonia/tests/unit/types/api-client-types-barrel.contract.test.ts` — pinned barrel wiring and canonical DTO ownership.

## Forward Intelligence

### What the next slice should know
- The stable seam is the façade layer: `@/lib/api-client`, `@/lib/api-client/types`, and `@/types/api`. Future cleanup should keep using those boundaries unless caller churn is intentional.
- By the end of S03, `src/lib/types/api.ts` was compat-only residue rather than a live owner; S04 could delete it with proof instead of further migration work.

### What's fragile
- `frontend-hormonia/src/types/api.ts` — still a large app-facing façade; it is safer to narrow ownership gradually than to collapse UI and transport types together in one pass.

### Authoritative diagnostics
- `tests/lib/api-client/index-split.contract.test.ts` — fastest detector for composition drift in the public client seam.
- `tests/unit/types/api-client-types-barrel.contract.test.ts` — fastest detector for type-owner/barrel drift.

### What assumptions changed
- "The public seam is `src/lib/api-client/index.ts`" — false; the safe public seam was the façade file `src/lib/api-client.ts`, which is what made the internal split low-churn.
