---
estimated_steps: 4
estimated_files: 3
---

# T01: Add failing structural contract tests for the client/type seam

**Slice:** S03 — Frontend Client/Type Surface Refactor
**Milestone:** M003

## Description

Create the executable boundary for the frontend refactor before moving production code. The tests in this task should fail first for meaningful reasons so later tasks prove they actually closed the client/type split instead of just rearranging files.

## Steps

1. Add `frontend-hormonia/tests/lib/api-client/index-split.contract.test.ts` to assert that `@/lib/api-client` keeps the same public surface while `src/lib/api-client/index.ts` is expected to delegate the remaining inline namespaces to dedicated modules.
2. Add `frontend-hormonia/tests/unit/types/api-client-types-barrel.contract.test.ts` to pin `src/lib/api-client/types.ts` as a barrel contract and to make duplicate `RiskAssessmentRequest` ownership fail explicitly until the split lands.
3. Add `frontend-hormonia/tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts` to assert that `src/hooks/usePatients.ts` must stop importing `src/lib/types/api.ts` once the slice is complete.
4. Run the new focused tests and confirm the failure modes are the intended structural gaps, not unrelated Vitest or environment breakage.

## Must-Haves

- [ ] The new tests assert real boundary outcomes: stable façade exports, extracted-module wiring, one canonical `RiskAssessmentRequest`, and the `usePatients.ts` canonical import path.
- [ ] The initial red state is informative and directly tied to missing module extraction / barrel cleanup / compatibility isolation.

## Verification

- `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
- Confirm the first failures point at the planned structural seam rather than unrelated runner setup issues.

## Observability Impact

- Signals added/changed: New structural contract tests expose missing module extraction, duplicate type ownership, and lingering compat imports as named failures.
- How a future agent inspects this: Re-run the focused Vitest command to see which part of the split contract regressed.
- Failure state exposed: public-surface drift, barrel drift, and canonical-import drift become explicit test failures instead of implicit code review judgment.

## Inputs

- `.gsd/milestones/M003/slices/S03/S03-RESEARCH.md` — defines the stable façades, the remaining inline namespaces, the duplicate `RiskAssessmentRequest`, and the live `usePatients.ts` compat caller.
- `.gsd/milestones/M003/slices/S01/S01-SUMMARY.md` — hands off the evidence contract that says S03 must preserve façade imports while isolating compat residue.

## Expected Output

- `frontend-hormonia/tests/lib/api-client/index-split.contract.test.ts` — failing structural contract coverage for the client composition seam.
- `frontend-hormonia/tests/unit/types/api-client-types-barrel.contract.test.ts` — failing barrel/duplicate-type coverage for the transport type seam.
- `frontend-hormonia/tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts` — failing compatibility-isolation coverage for the remaining live app caller.
