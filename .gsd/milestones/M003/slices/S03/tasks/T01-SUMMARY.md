---
id: T01
parent: S03
milestone: M003
provides:
  - Added failing structural contract tests that pin the frontend client/type seam before the S03 extraction work starts.
key_files:
  - frontend-hormonia/tests/lib/api-client/index-split.contract.test.ts
  - frontend-hormonia/tests/unit/types/api-client-types-barrel.contract.test.ts
  - frontend-hormonia/tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts
  - .gsd/milestones/M003/slices/S03/S03-PLAN.md
  - .gsd/STATE.md
  - .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md
key_decisions:
  - The structural contracts are source-aware and intentionally fail only on the documented seam gaps: missing delegated client modules, missing type-barrel wiring, duplicate `RiskAssessmentRequest` ownership, and the lingering `usePatients.ts` compat import.
patterns_established:
  - Keep one passing façade guard per seam and pair it with explicit red assertions whose failure text names the exact missing split module, duplicate type owner, or compat import drift.
observability_surfaces:
  - cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report frontend
duration: 2026-03-12
verification_result: passed
completed_at: 2026-03-12
blocker_discovered: false
---

# T01: Add failing structural contract tests for the client/type seam

**Added the initial red structural contract tests for the frontend API-client/type split and verified that they fail for the planned seam gaps instead of Vitest setup noise.**

## What Happened

I added `frontend-hormonia/tests/lib/api-client/index-split.contract.test.ts` to pin two sides of the client seam: a passing façade smoke check that `@/lib/api-client` still exposes the expected `apiClient`/`ApiClient` surface and runtime namespaces, plus explicit red assertions that `src/lib/api-client/index.ts` must import the remaining namespaces from dedicated modules, stop defining those namespace factories inline, and compose them via `createXApi(this)`.

I added `frontend-hormonia/tests/unit/types/api-client-types-barrel.contract.test.ts` to pin the transport-type seam. The file keeps a passing guard that `RiskAssessmentRequest` is still present in `src/lib/api-client/types.ts`, then fails on the two planned cleanup gaps: the missing `./types/quiz` and `./types/physician` barrel wiring, and the duplicate `RiskAssessmentRequest` declarations that still leave ownership ambiguous.

I added `frontend-hormonia/tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts` to isolate the last live app caller on the compatibility barrel. Both assertions currently fail on the documented condition: `src/hooks/usePatients.ts` still imports `Patient` from `../lib/types/api` instead of one of the allowed canonical paths.

After adding the tests, I ran the focused T01 proof command and confirmed the failures are named structural seam failures rather than unrelated Vitest/bootstrap issues. I then ran the broader S03 verification pack to record the current intermediate-task baseline before T02 starts.

## Verification

### T01 focused proof
- `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
  - **Expected red; confirmed.**
  - `tests/lib/api-client/index-split.contract.test.ts`: passing façade surface guard; failing missing delegated module imports, failing inline-factory removal, failing delegated constructor wiring.
  - `tests/unit/types/api-client-types-barrel.contract.test.ts`: passing `RiskAssessmentRequest` visibility guard; failing missing `./types/quiz` and `./types/physician` barrel re-exports; failing duplicate `RiskAssessmentRequest` ownership (`2` declarations found).
  - `tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`: failing lingering `../lib/types/api` import and failing canonical-source assertion.

### Remaining slice verification pack
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
  - **Failed, but unrelated to T01.** Current failure is the existing `@/config` mock missing `API_BASE_URL` for `tests/integration/api-client.test.ts`.
- `cd frontend-hormonia && npm run test -- tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx tests/components/dashboard/QuickStats.test.tsx`
  - **Passed.**
- `cd frontend-hormonia && npm run test -- src/hooks/__tests__/usePatients.test.ts tests/unit/types-validation.test.ts`
  - **Passed.**
- `cd frontend-hormonia && npm run typecheck && npm run build`
  - **Failed, but unrelated to T01.** Current blockers are existing `TS4111` index-signature accesses for `connection_id` in `src/hooks/useWebSocket.ts` and `src/lib/websocket.ts`.
- `cd frontend-hormonia && python3 - <<'PY' ... PY`
  - **Failed as expected for pre-split structure.** Missing extracted client/type modules are reported immediately.
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`
  - **Passed.**
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report frontend`
  - **Passed.** Report still shows `src/lib/api-client/index.ts` at 1304 lines, `src/lib/api-client/types.ts` at 1159 lines, and `RiskAssessmentRequest` with `2` direct declarations.

## Diagnostics

- Re-run `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts` to inspect the named structural failures this task introduced.
- Use `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report frontend` to confirm the hotspot sizes and duplicate-type counts before and after the later extraction tasks.
- The most important current red signals are:
  - missing delegated module imports for `messages`, `flows`, `alerts`, `reports`, `admin-legacy`, `admin-users`, `ai`, `quiz`, `quizzes`, `notifications`, and `physician`
  - missing `./types/quiz` and `./types/physician` barrel wiring
  - duplicate `RiskAssessmentRequest` ownership in `src/lib/api-client/types.ts`
  - lingering `src/hooks/usePatients.ts` import from `src/lib/types/api`

## Deviations

None.

## Known Issues

- `tests/integration/api-client.test.ts` is currently red for a pre-existing mock-shape problem (`@/config` mock omits `API_BASE_URL`), so it is not a clean signal for this task.
- `npm run typecheck` currently fails on pre-existing `TS4111` bracket-access issues around `connection_id` in websocket code.
- The structural Python check remains red until later S03 tasks actually extract the listed modules and migrate `usePatients.ts` off the compatibility barrel.

## Files Created/Modified

- `frontend-hormonia/tests/lib/api-client/index-split.contract.test.ts` — added façade-preservation and delegated-composition contract tests for `src/lib/api-client/index.ts`.
- `frontend-hormonia/tests/unit/types/api-client-types-barrel.contract.test.ts` — added barrel/duplicate-ownership contract tests for `src/lib/api-client/types.ts`.
- `frontend-hormonia/tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts` — added canonical-import contract tests for the remaining live compat caller.
- `.gsd/milestones/M003/slices/S03/S03-PLAN.md` — marked T01 complete.
- `.gsd/STATE.md` — advanced the next action to T02.
- `.gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md` — recorded this task closeout and verification baseline.
