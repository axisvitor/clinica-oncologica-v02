---
estimated_steps: 4
estimated_files: 8
---

# T02: Delete dead frontend compatibility barrels and Firebase Hosting residue

**Slice:** S03 — Purga final de bridges, tombstones, serviços mortos e narrativa operacional errada
**Milestone:** M006

## Description

Root `frontend-hormonia/lib/flow-engine/*` bridges and `frontend-hormonia/lib/types/*` barrels have zero repo consumers and are not included in the frontend build/typecheck config. `firebase.json` and `.firebaserc` are Firebase Hosting residue files with no in-repo operational references. Delete them all and extend the existing `dead-compat-cleanup.contract.test.ts` to assert the newly deleted files stay absent.

## Steps

1. **Final consumer scan** — for each target file, run `rg` for its import path patterns to confirm zero live consumers beyond self-references and documentation. Pay special attention to `@/lib/*` vs root `lib/*` resolution — `@/` maps to `src/`, not the root `lib/`.
2. **Delete the dead files:**
   - `frontend-hormonia/lib/flow-engine/FlowEngine.ts`
   - `frontend-hormonia/lib/flow-engine/TemplateManager.ts`
   - `frontend-hormonia/lib/types/ai.ts`
   - `frontend-hormonia/lib/types/api.ts`
   - `frontend-hormonia/lib/types/flow.ts`
   - `frontend-hormonia/lib/types/flow-designer.ts`
   - `frontend-hormonia/lib/types/messages.ts`
   - `frontend-hormonia/lib/types/message-types.ts`
   - `frontend-hormonia/firebase.json`
   - `frontend-hormonia/.firebaserc`
   - Delete parent directories if empty after removal (`lib/flow-engine/`, `lib/types/`).
3. **Extend contract tests** — add assertions to `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` for each newly deleted file, following the existing pattern of "deleted compat files stay deleted" assertions.
4. **Verify** — run `npm run build`, `npm run typecheck`, and the import-boundaries test suite.

## Must-Haves

- [ ] All listed bridge/barrel files deleted.
- [ ] `firebase.json` and `.firebaserc` deleted from `frontend-hormonia/`.
- [ ] `dead-compat-cleanup.contract.test.ts` extended with assertions for all newly deleted files.
- [ ] `npm run build` and `npm run typecheck` green.
- [ ] Import-boundaries test suite green.

## Verification

- `cd frontend-hormonia && npm run build` exits 0.
- `cd frontend-hormonia && npm run typecheck` exits 0.
- `cd frontend-hormonia && npx vitest run tests/unit/import-boundaries/` all green.
- `! test -f frontend-hormonia/lib/flow-engine/FlowEngine.ts && ! test -f frontend-hormonia/lib/types/flow.ts && ! test -f frontend-hormonia/firebase.json && echo "frontend dead surfaces removed"` succeeds.

## Inputs

- S03 research: confirmed zero repo consumers for all target files, resolution analysis showing `useFlowEngine.ts` uses `src/lib/flow-engine/*` not root bridges, `lib/types/flow.ts` targets non-existent modules.
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` — existing contract test pattern to extend.
- `frontend-hormonia/tsconfig.json` and `tsconfig.build.json` — confirms root `lib/**` is excluded from build.

## Expected Output

- 10 dead files deleted from `frontend-hormonia/`.
- Extended `dead-compat-cleanup.contract.test.ts` with ~8 new "stays deleted" assertions.
- Green build, typecheck, and contract tests.
