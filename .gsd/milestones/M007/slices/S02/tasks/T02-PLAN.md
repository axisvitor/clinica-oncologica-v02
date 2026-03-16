---
estimated_steps: 10
estimated_files: 8
---

# T02: Delete FlowDesigner frontend and clean consumer imports

**Slice:** S02 — Remover abstrações mortas do subsistema de fluxo
**Milestone:** M007

## Description

Delete the entire FlowDesigner visual canvas feature from the frontend (~4800 lines including tests), its type definitions, the dialog wrapper, and the template format converters. Then carefully clean the consumer files that imported these — TemplateManagementPage and FlowTemplateCard must remain functional as listing/display components with designer-related triggers removed. Finally, clean barrel exports in `types/index.ts` and `templates/index.ts`.

## Steps

1. Delete the directory `frontend-hormonia/src/features/flow-designer/` entirely — 7 source files (2336 lines) + 8 test files (2441 lines). This is the visual canvas designer with no consumers outside the templates feature.
2. Delete `frontend-hormonia/src/types/flow-designer.ts` (233 lines) — type definitions for visual designer nodes, connections, state. NOTE: `ChartData` and `TreatmentType` defined here already have duplicate local definitions at lines ~123 and ~133 of `types/index.ts`, so nothing breaks.
3. Delete `frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx` (216 lines) — the modal that wraps FlowDesigner. Imported by TemplateManagementPage and FlowTemplateCard.
4. Delete `frontend-hormonia/src/features/templates/utils/templateConverters.ts` (120 lines) — API↔FlowDesigner format converters, only used by FlowDesignerDialog.
5. Edit `frontend-hormonia/src/types/index.ts`: find and remove the two lines around line 60-61 that read like `// Flow designer types` and `export * from './flow-designer'`. Leave everything else intact.
6. Edit `frontend-hormonia/src/features/templates/index.ts`: remove `export { FlowDesignerDialog }` (around line 14) and `export { convertTemplateToDesign, convertDesignToTemplate }` (around line 24). Keep all other exports.
7. Edit `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx`:
   - Remove the `FlowDesignerDialog` import (around line 25)
   - Remove the `showFlowDesigner` state variable (around line 35)
   - Remove the button onClick that sets `showFlowDesigner(true)` (around line 80)
   - Remove the `onCreateNew` handler (around line 137)
   - Remove the `<FlowDesignerDialog ... />` JSX block (around lines 156-158)
   - Keep the entire template list/search/filter/pagination UI intact
   - The page must still render and function as a template listing page
8. Edit `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx`:
   - Remove the `FlowDesignerDialog` import (around line 11)
   - Remove `showEditor` and `editMode` state variables
   - Remove `handleEdit` and `handleNewVersion` handlers
   - Remove the `<FlowDesignerDialog ... />` JSX block (around lines 101-112)
   - Remove the Edit and Nova Versão buttons that opened the FlowDesignerDialog
   - Keep the card structure, template info display, Versões button, and Desativar button
9. Run typecheck: `cd frontend-hormonia && npx tsc --noEmit` — must exit 0
10. Run build: `cd frontend-hormonia && npm run build` — must exit 0

## Must-Haves

- [ ] `frontend-hormonia/src/features/flow-designer/` directory deleted entirely
- [ ] `frontend-hormonia/src/types/flow-designer.ts` deleted
- [ ] `frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx` deleted
- [ ] `frontend-hormonia/src/features/templates/utils/templateConverters.ts` deleted
- [ ] `types/index.ts` no longer re-exports from `./flow-designer`
- [ ] `templates/index.ts` no longer exports FlowDesignerDialog or templateConverter functions
- [ ] TemplateManagementPage renders without FlowDesigner references — list/search/filter/pagination intact
- [ ] FlowTemplateCard renders without designer features — card display, Versões, Desativar intact
- [ ] `npx tsc --noEmit` exits 0
- [ ] `npm run build` exits 0
- [ ] `frontend-hormonia/src/lib/flow-engine/` is NOT touched (out of scope per research)

## Observability Impact

This task removes dead frontend code. No runtime signals change — the FlowDesigner was never rendered in production (no route pointed to it standalone). Diagnostic changes:

- **Build gate**: `npm run build` no longer bundles ~4800 lines of flow-designer code — bundle size decreases
- **Type gate**: `npx tsc --noEmit` no longer resolves flow-designer types
- **Dead import check**: `grep -r "FlowDesignerDialog\|flow-designer" --include='*.ts' --include='*.tsx' frontend-hormonia/src/` returns no hits after this task
- **Failure shape**: Any accidental re-import of deleted modules produces `TS2307: Cannot find module` at typecheck time

## Verification

- `cd frontend-hormonia && npx tsc --noEmit` exits 0
- `cd frontend-hormonia && npm run build` exits 0
- `ls frontend-hormonia/src/features/flow-designer/` returns "No such file or directory"
- `ls frontend-hormonia/src/types/flow-designer.ts` returns "No such file or directory"
- `grep -r "FlowDesignerDialog\|flow-designer" frontend-hormonia/src/features/templates/` returns no hits
- `grep "flow-designer" frontend-hormonia/src/types/index.ts` returns no hits

## Inputs

- T01 completed: backend tombstones and phantom enum members already removed, backend tests green
- `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx` — live template listing page routed via AdminRoutes.tsx. Must survive with designer triggers removed.
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — card component with template info, Versões, Desativar buttons that must stay.
- `frontend-hormonia/src/types/index.ts` — barrel file that re-exports `flow-designer.ts` but also has duplicate local `ChartData` and `TreatmentType` definitions at lines ~123 and ~133. After removing the re-export, the local definitions take over seamlessly.
- `frontend-hormonia/src/features/templates/index.ts` — barrel that exports FlowDesignerDialog and converter functions to be removed.
- Research confirmed no consumer imports `ChartData` or `TreatmentType` from `@/types/flow-designer` directly.
- The `frontend-hormonia/src/lib/flow-engine/` directory references a DIFFERENT `FlowType` enum in `lib/api-client/types/flows.ts` — this is NOT the flow-designer and is explicitly out of scope.

## Expected Output

- `frontend-hormonia/src/features/flow-designer/` — gone
- `frontend-hormonia/src/types/flow-designer.ts` — gone
- `frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx` — gone
- `frontend-hormonia/src/features/templates/utils/templateConverters.ts` — gone
- `frontend-hormonia/src/types/index.ts` — edited, no flow-designer re-export
- `frontend-hormonia/src/features/templates/index.ts` — edited, no designer exports
- `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx` — edited, functional without FlowDesigner
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — edited, functional without designer features
- Frontend typecheck and build both green
