---
id: T03
parent: S03
milestone: M003
provides:
  - Extracted the remaining quiz/clinical api-client namespaces into dedicated modules and turned `src/lib/api-client/types.ts` into a stable barrel over focused transport type owners.
key_files:
  - frontend-hormonia/src/lib/api-client/index.ts
  - frontend-hormonia/src/lib/api-client/ai.ts
  - frontend-hormonia/src/lib/api-client/quiz.ts
  - frontend-hormonia/src/lib/api-client/quizzes.ts
  - frontend-hormonia/src/lib/api-client/physician.ts
  - frontend-hormonia/src/lib/api-client/types.ts
  - frontend-hormonia/src/lib/api-client/types/physician.ts
  - frontend-hormonia/src/hooks/usePatients.ts
key_decisions:
  - `RiskAssessmentRequest` now has one canonical transport owner in `src/lib/api-client/types/physician.ts`, while `@/lib/api-client/types` stays the stable import surface via barrel re-export.
patterns_established:
  - Keep `src/lib/api-client/index.ts` composition-first by delegating each namespace through `createXApi(client)` modules and keep transport DTO ownership in `src/lib/api-client/types/*` domain files behind the barrel.
observability_surfaces:
  - Focused structural Vitest contracts, the split-module Python seam check, `npm run typecheck`, and `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`
duration: 14m
verification_result: partial
completed_at: 2026-03-13T00:11:06-03:00
blocker_discovered: false
---

# T03: Extract the quiz/clinical namespaces and turn `types.ts` into a domain barrel

**Extracted the remaining AI/quiz/physician client namespaces, collapsed `types.ts` into barrel glue, and moved the live `usePatients` caller onto a canonical type source.**

## What Happened

I finished the remaining `src/lib/api-client/index.ts` ownership split by creating dedicated `createXApi(client)` modules for `ai`, `quiz`, `quizzes`, and `physician`, then rewired the constructor to compose them directly. That removed the last inline namespace factories from `index.ts` and reduced the file to 223 lines.

I also split the transport DTO hotspot into domain files under `frontend-hormonia/src/lib/api-client/types/` (`common`, `messages`, `flows`, `alerts`, `reports`, `admin`, `ai`, `quiz`, `tasks`, `notifications`, `physician`, `flow-engine`) and rewrote `frontend-hormonia/src/lib/api-client/types.ts` as the stable barrel over those owners. `RiskAssessmentRequest` is now declared only in `src/lib/api-client/types/physician.ts` and explicitly re-exported from the barrel so callers still use `@/lib/api-client/types`.

To finish the live type-seam cleanup for this task, I moved `frontend-hormonia/src/hooks/usePatients.ts` off the `src/lib/types/api.ts` compatibility barrel and onto `@/types/api`, and updated the barrel contract test to assert the canonical owner in the new physician domain file rather than the old inline declaration model.

## Verification

Passed:
- `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
- `cd frontend-hormonia && python3 - <<'PY' ...` (slice seam check)
  - confirmed required split modules exist
  - `src/lib/api-client/index.ts` = 223 lines
  - `src/lib/api-client/types.ts` = 26 lines
  - `RiskAssessmentRequest` remains visible from the barrel
  - `usePatients.ts` no longer imports `lib/types/api`

Failed / still red:
- `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
  - structural suites and `tests/lib/api-client/core.test.ts` passed
  - `tests/integration/api-client.test.ts` still has 23 failing assertions around pre-existing endpoint/CSRF/baseURL expectations on auth/patients/messages/flows surfaces that this task did not modify
- `cd frontend-hormonia && npm run typecheck`
  - still fails on pre-existing TS4111 index-signature access in `src/hooks/useWebSocket.ts` and `src/lib/websocket.ts`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`
  - still fails because `S01-RESEARCH.md` anchors were not updated for the new hotspot sizes / duplicate-owner counts in this task

## Diagnostics

- Structural seam drift is now surfaced by:
  - `tests/lib/api-client/index-split.contract.test.ts`
  - `tests/unit/types/api-client-types-barrel.contract.test.ts`
  - `tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
- The split-module/size proof is inspectable with the Python check embedded in the slice plan.
- Evidence-map drift is inspectable with `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`.
- Remaining non-T03 red signals are localized to:
  - `tests/integration/api-client.test.ts`
  - `src/hooks/useWebSocket.ts`
  - `src/lib/websocket.ts`
  - `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md`

## Deviations

- I split `src/lib/api-client/types.ts` into a broader set of domain owner files than the minimum `quiz`/`physician` pair so the hotspot actually became barrel glue and dropped under the slice size budget.
- I updated `tests/unit/types/api-client-types-barrel.contract.test.ts` so it now verifies canonical ownership in `src/lib/api-client/types/physician.ts` instead of expecting an inline declaration to remain inside `types.ts`, which matches the authoritative T03 plan.

## Known Issues

- `tests/integration/api-client.test.ts` remains red with endpoint-shape/baseURL/CSRF expectation drift outside the files changed in T03.
- `npm run typecheck` remains red because of existing TS4111 bracket-notation issues in websocket files unrelated to this extraction.
- `verify-evidence-map.sh --check frontend` remains red until `S01-RESEARCH.md` is refreshed with the new hotspot metrics and duplicate-owner anchor values.

## Files Created/Modified

- `frontend-hormonia/src/lib/api-client/ai.ts` — extracted the AI namespace into a dedicated `createAiApi(client)` module.
- `frontend-hormonia/src/lib/api-client/quiz.ts` — extracted the quiz session namespace into a dedicated `createQuizApi(client)` module.
- `frontend-hormonia/src/lib/api-client/quizzes.ts` — extracted quiz-template CRUD/analytics into a dedicated `createQuizTemplatesApi(client)` module.
- `frontend-hormonia/src/lib/api-client/physician.ts` — extracted physician risk-assessment access into a dedicated `createPhysicianApi(client)` module.
- `frontend-hormonia/src/lib/api-client/index.ts` — rewired the API client to pure delegated composition for the remaining namespaces.
- `frontend-hormonia/src/lib/api-client/types.ts` — replaced the monolith with a stable domain barrel.
- `frontend-hormonia/src/lib/api-client/types/common.ts` — moved shared transport response/filter primitives into a domain owner file.
- `frontend-hormonia/src/lib/api-client/types/messages.ts` — moved message DTO ownership behind the barrel.
- `frontend-hormonia/src/lib/api-client/types/flows.ts` — moved flow DTO ownership behind the barrel.
- `frontend-hormonia/src/lib/api-client/types/alerts.ts` — moved alert DTO ownership behind the barrel.
- `frontend-hormonia/src/lib/api-client/types/reports.ts` — moved report DTO ownership behind the barrel.
- `frontend-hormonia/src/lib/api-client/types/admin.ts` — moved admin transport DTO ownership/re-exports behind the barrel.
- `frontend-hormonia/src/lib/api-client/types/ai.ts` — moved AI transport DTO ownership behind the barrel.
- `frontend-hormonia/src/lib/api-client/types/quiz.ts` — moved quiz transport DTO ownership behind the barrel.
- `frontend-hormonia/src/lib/api-client/types/tasks.ts` — moved task DTO ownership behind the barrel.
- `frontend-hormonia/src/lib/api-client/types/notifications.ts` — moved notification DTO ownership behind the barrel.
- `frontend-hormonia/src/lib/api-client/types/physician.ts` — established the canonical owner for `RiskAssessmentRequest` and physician risk DTOs.
- `frontend-hormonia/src/lib/api-client/types/flow-engine.ts` — moved flow-engine support DTO ownership behind the barrel.
- `frontend-hormonia/src/hooks/usePatients.ts` — migrated `Patient` imports off the compatibility barrel.
- `frontend-hormonia/tests/unit/types/api-client-types-barrel.contract.test.ts` — aligned the structural contract with the new canonical owner/barrel architecture.
