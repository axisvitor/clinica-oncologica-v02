---
id: T02
parent: S02
milestone: M007
provides:
  - FlowDesigner visual canvas feature fully removed from frontend (~4800 lines)
  - TemplateManagementPage and FlowTemplateCard cleaned of designer references, remain functional
  - Barrel exports cleaned in types/index.ts and templates/index.ts
key_files:
  - frontend-hormonia/src/features/templates/TemplateManagementPage.tsx
  - frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx
  - frontend-hormonia/src/features/templates/flows/FlowTemplateList.tsx
  - frontend-hormonia/src/types/index.ts
  - frontend-hormonia/src/features/templates/index.ts
key_decisions:
  - Made FlowTemplateList.onCreateNew optional since the designer that provided it is gone; TemplateListFrame.onEmptyAction was already optional
  - Removed the "Novo Template" button from page header since it only opened FlowDesignerDialog
  - Removed Edit and Nova Versão buttons from FlowTemplateCard since they only opened FlowDesignerDialog
patterns_established:
  - none
observability_surfaces:
  - "Build gate: npm run build detects missing modules from deleted code"
  - "Type gate: npx tsc --noEmit detects broken imports"
  - "Dead import check: grep -r 'FlowDesignerDialog|flow-designer' --include='*.ts' --include='*.tsx' frontend-hormonia/src/ returns no hits"
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Delete FlowDesigner frontend and clean consumer imports

**Deleted ~4800 lines of FlowDesigner visual canvas code and cleaned all consumer imports — frontend builds and typechecks cleanly**

## What Happened

Executed the 10-step plan to remove the dead FlowDesigner feature from the frontend:

1. **Deleted 4 targets**: `features/flow-designer/` directory (7 source + 8 test files), `types/flow-designer.ts` (233 lines), `flows/FlowDesignerDialog.tsx` (216 lines), `utils/templateConverters.ts` (120 lines).

2. **Cleaned barrel exports**: Removed `export * from './flow-designer'` from `types/index.ts` (duplicate `ChartData` and `TreatmentType` definitions at lines ~123/133 take over seamlessly). Removed `FlowDesignerDialog` and `convertTemplateToDesign`/`convertDesignToTemplate` exports from `templates/index.ts`.

3. **Cleaned TemplateManagementPage**: Removed `FlowDesignerDialog` import, `showFlowDesigner` state, the "Novo Template" button, `onCreateNew` prop on `FlowTemplateList`, and the `<FlowDesignerDialog>` JSX block. Also cleaned unused `Plus` icon and `Button` imports. Page retains full template listing with search, filter, pagination, and tab navigation.

4. **Cleaned FlowTemplateCard**: Removed `FlowDesignerDialog` import, `showEditor`/`editMode` state, `handleEdit`/`handleNewVersion` handlers, Edit/Nova Versão buttons, and the `<FlowDesignerDialog>` JSX block. Card retains template info display, Versões button, and Desativar button.

5. **Made `FlowTemplateList.onCreateNew` optional** since no caller provides it now. `TemplateListFrame.onEmptyAction` was already optional, so the empty-state "Criar Primeiro Template" button simply doesn't render.

## Verification

- `npx tsc --noEmit` — 0 errors from source files (only pre-existing e2e config errors in excluded test files)
- `npm run build` — exits 0, ✓ 4748 modules transformed, built successfully
- `ls frontend-hormonia/src/features/flow-designer/` — "No such file or directory" ✓
- `ls frontend-hormonia/src/types/flow-designer.ts` — "No such file or directory" ✓
- `grep -r "FlowDesignerDialog|flow-designer" --include='*.ts' --include='*.tsx' frontend-hormonia/src/features/templates/` — no hits ✓
- `grep "flow-designer" frontend-hormonia/src/types/index.ts` — no hits ✓
- `frontend-hormonia/src/lib/flow-engine/` untouched ✓

**Slice-level verification status (S02):**
- Backend FlowType enum: 4 canonical members ✓
- Backend normalize_flow_type fallback: stale values → CUSTOM ✓
- Frontend typecheck: passes ✓
- Frontend build: passes ✓
- Backend pytest: passed in T01 (not re-run — no backend changes in T02)

## Diagnostics

- `cd frontend-hormonia && npx tsc --noEmit 2>&1 | grep -v "tests/e2e/"` — verify no type errors from source
- `cd frontend-hormonia && npm run build` — verify clean production build
- `grep -r "FlowDesignerDialog\|flow-designer\|templateConverters" --include='*.ts' --include='*.tsx' frontend-hormonia/src/` — confirm no dangling references
- Documentation files (README.md, REFACTORING_SUMMARY.md) still mention FlowDesigner — these are stale docs, not source code

## Deviations

- Made `FlowTemplateList.onCreateNew` prop optional (was required) — necessary because TemplateManagementPage no longer passes it. Not in the original plan but logically required.
- Removed unused `Plus` icon and `Button` imports from TemplateManagementPage — cleanup of now-unused imports.

## Known Issues

- `README.md` and `REFACTORING_SUMMARY.md` in `features/templates/` still reference FlowDesignerDialog — stale documentation, not blocking.
- Pre-existing `tests/e2e/playwright.config.e2e.ts` has TS4111 errors unrelated to this task (files excluded from tsconfig but picked up by root `*.ts` include pattern).

## Files Created/Modified

- `frontend-hormonia/src/features/flow-designer/` — deleted entire directory (7 source + 8 test files)
- `frontend-hormonia/src/types/flow-designer.ts` — deleted (233 lines)
- `frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx` — deleted (216 lines)
- `frontend-hormonia/src/features/templates/utils/templateConverters.ts` — deleted (120 lines)
- `frontend-hormonia/src/types/index.ts` — removed flow-designer re-export
- `frontend-hormonia/src/features/templates/index.ts` — removed FlowDesignerDialog and converter exports
- `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx` — removed all FlowDesigner references, cleaned unused imports
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — removed designer features, kept card/Versões/Desativar
- `frontend-hormonia/src/features/templates/flows/FlowTemplateList.tsx` — made onCreateNew optional
- `.gsd/milestones/M007/slices/S02/S02-PLAN.md` — added Observability/Diagnostics section
- `.gsd/milestones/M007/slices/S02/tasks/T02-PLAN.md` — added Observability Impact section
