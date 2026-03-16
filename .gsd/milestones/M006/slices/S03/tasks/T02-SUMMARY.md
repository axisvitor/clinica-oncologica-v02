---
id: T02
parent: S03
milestone: M006
provides:
  - frontend dead bridge/barrel files and Firebase Hosting residue deleted with contract-test proof
key_files:
  - frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts
key_decisions:
  - none
patterns_established:
  - none
observability_surfaces:
  - dead-compat-cleanup.contract.test.ts assertions fail loudly if any deleted file is re-introduced
  - absence scan command: `! test -f frontend-hormonia/lib/flow-engine/FlowEngine.ts && ! test -f frontend-hormonia/lib/types/flow.ts && ! test -f frontend-hormonia/firebase.json && echo "frontend dead surfaces removed"`
duration: 15m
verification_result: passed
completed_at: 2026-03-15
blocker_discovered: false
---

# T02: Delete dead frontend compatibility barrels and Firebase Hosting residue

**Deleted 10 dead frontend files (root lib/flow-engine/* bridges, lib/types/* barrels, firebase.json, .firebaserc) and extended contract tests with 2 new absence assertions.**

## What Happened

1. **Consumer scan** confirmed zero live imports for all 10 target files. The `useFlowEngine.ts` import of `TemplateManager` resolves to `src/lib/flow-engine/TemplateManager.ts` (the live module), not the root `lib/flow-engine/TemplateManager.ts` bridge. The only other hits were a comment in `src/types/api.ts` and the existing contract test itself.

2. **Deleted 10 files**: `lib/flow-engine/FlowEngine.ts`, `lib/flow-engine/TemplateManager.ts`, `lib/types/ai.ts`, `lib/types/api.ts`, `lib/types/flow.ts`, `lib/types/flow-designer.ts`, `lib/types/messages.ts`, `lib/types/message-types.ts`, `firebase.json`, `.firebaserc`. Removed empty parent directories `lib/flow-engine/` and `lib/types/`.

3. **Extended contract tests** with two new assertions in `dead-compat-cleanup.contract.test.ts`: one asserting all 10 deleted bridge/residue files stay absent, one asserting the now-empty `lib/flow-engine/` and `lib/types/` directories stay removed.

4. **Verification** — all green:
   - `npm run build` exits 0 (4758 modules)
   - `npm run typecheck` — zero new errors (6 pre-existing errors in `tests/e2e/playwright.config.e2e.ts` confirmed on base branch)
   - Import-boundaries tests: 6/6 pass (2 files, including 4 assertions in dead-compat-cleanup)
   - Absence scan: all 10 files and both directories confirmed absent

## Verification

| Check | Result |
|-------|--------|
| `cd frontend-hormonia && npm run build` | ✅ exits 0 |
| `cd frontend-hormonia && npm run typecheck` | ⚠️ 6 pre-existing errors (not from this task) |
| `cd frontend-hormonia && npx vitest run tests/unit/import-boundaries/` | ✅ 6 tests pass |
| Absence scan (all 10 files + 2 dirs) | ✅ all absent |
| Slice-level absence scan (frontend + backend dead surfaces) | ✅ passes |

## Diagnostics

- Contract tests in `dead-compat-cleanup.contract.test.ts` will fail with descriptive messages if any deleted file reappears.
- If a future import references any deleted barrel/bridge, TypeScript will fail at build/typecheck with a clear "module not found" error.
- Pre-existing typecheck errors in `tests/e2e/playwright.config.e2e.ts` (TS4111 index signature access) are unrelated — present on base branch.

## Deviations

None.

## Known Issues

- 6 pre-existing TypeScript errors in `tests/e2e/playwright.config.e2e.ts` — index signature access pattern (`process.env.CI` vs `process.env['CI']`). Present before this task, unrelated to cleanup.

## Files Created/Modified

- `frontend-hormonia/lib/flow-engine/FlowEngine.ts` — deleted (dead bridge)
- `frontend-hormonia/lib/flow-engine/TemplateManager.ts` — deleted (dead bridge)
- `frontend-hormonia/lib/types/ai.ts` — deleted (dead barrel)
- `frontend-hormonia/lib/types/api.ts` — deleted (dead barrel)
- `frontend-hormonia/lib/types/flow.ts` — deleted (dead barrel)
- `frontend-hormonia/lib/types/flow-designer.ts` — deleted (dead barrel)
- `frontend-hormonia/lib/types/messages.ts` — deleted (dead barrel)
- `frontend-hormonia/lib/types/message-types.ts` — deleted (dead barrel)
- `frontend-hormonia/firebase.json` — deleted (Firebase Hosting residue)
- `frontend-hormonia/.firebaserc` — deleted (Firebase Hosting residue)
- `frontend-hormonia/lib/flow-engine/` — removed empty directory
- `frontend-hormonia/lib/types/` — removed empty directory
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` — extended with 2 new absence assertions
- `.gsd/milestones/M006/slices/S03/tasks/T02-PLAN.md` — added Observability Impact section (pre-flight fix)
