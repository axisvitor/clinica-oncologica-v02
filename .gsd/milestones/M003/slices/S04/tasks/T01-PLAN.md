---
estimated_steps: 5
estimated_files: 6
---

# T01: Delete dead frontend compatibility files and pin the new boundary

**Slice:** S04 — Dead-Code And Obsolete-Compatibility Cleanup
**Milestone:** M003

## Description

Remove the strongest frontend dead-code candidates first because they already have the clearest evidence and the lowest runtime risk. This task closes the last test-only dependency on the legacy type barrel, deletes the cold alias/hook files outright, and leaves a focused contract test so the cleanup cannot quietly regress.

## Steps

1. Add `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` to assert that `src/lib/api.ts`, `src/lib/types/api.ts`, and `src/hooks/use-quiz-session.ts` are absent after S04 and that the focused type-validation proof does not import the legacy compat barrel anymore.
2. Update `frontend-hormonia/tests/unit/types-validation.test.ts` to import from the canonical S03-owned type surface instead of `@/lib/types/api`, preserving the same behavior/assertions where possible.
3. Delete `frontend-hormonia/src/lib/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, and `frontend-hormonia/src/hooks/use-quiz-session.ts` without replacing them with new aliases, tombstones, or renamed compatibility wrappers.
4. Run the focused frontend proof covering the cleanup contract, current auth/client flows, and monthly-quiz ownership so the deletions are backed by behavior-level evidence rather than grep-only evidence.
5. Run `npm run typecheck` and `npm run build` so the slice proves the cleanup at compile/build level too.

## Must-Haves

- [ ] `tests/unit/types-validation.test.ts` no longer depends on `src/lib/types/api.ts`, and the three proven-dead frontend files are fully deleted rather than re-aliased.
- [ ] Focused frontend auth/client/realtime/monthly-quiz proof plus typecheck/build remain green after the deletions.

## Verification

- `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`

## Observability Impact

- Signals added/changed: a dedicated cleanup contract test turns reintroduced compat files or legacy type imports into named failures instead of silent drift.
- How a future agent inspects this: rerun the focused Vitest command and inspect the deleted-file assertions plus the type-validation import path.
- Failure state exposed: dead-file resurrection, lingering compat imports, or auth/client/monthly-quiz regressions become explicit acceptance failures.

## Inputs

- `.gsd/milestones/M003/slices/S04/S04-RESEARCH.md` — identifies `src/lib/api.ts`, `src/lib/types/api.ts`, and `src/hooks/use-quiz-session.ts` as the strongest frontend delete candidates and points at the current proof pack.
- Outputs from S03 — `frontend-hormonia/src/lib/api-client/index.ts`, `frontend-hormonia/src/lib/api-client/types.ts`, and the refreshed auth/client test pack provide the canonical replacement surface.

## Expected Output

- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` — executable proof that the deleted compat files and the old test-only import path do not return.
- `frontend-hormonia/tests/unit/types-validation.test.ts` — migrated to canonical type imports.
- `frontend-hormonia/src/lib/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, and `frontend-hormonia/src/hooks/use-quiz-session.ts` — removed from the repo.
