# S02: Remover abstrações mortas do subsistema de fluxo

**Goal:** Remove ~4800 lines of dead code from the flow subsystem — FlowDesigner visual (frontend), phantom FlowType enum members (backend), and tombstoned templates package (backend) — leaving build, typecheck, and tests green.

**Demo:** After this slice, `frontend-hormonia/src/features/flow-designer/` no longer exists, `FlowType` enum contains only the 4 canonical members (ONBOARDING, DAILY_FOLLOW_UP, QUIZ_MENSAL, CUSTOM), the tombstoned `flow/templates/` package and its ~4600 lines of dead tests are gone, and all verification gates pass.

## Must-Haves

- Tombstoned `backend-hormonia/app/services/flow/templates/` directory deleted entirely
- Dead test directories for tombstoned templates deleted (`tests/services/flow/templates/`, `tests/unit/services/flow/templates/`)
- Phantom `FlowType` members removed: TREATMENT_ADHERENCE, SYMPTOM_TRACKING, MEDICATION_REMINDER, APPOINTMENT_PREP, POST_APPOINTMENT, EMERGENCY_PROTOCOL, MONITORING
- Only canonical FlowType members remain: ONBOARDING, DAILY_FOLLOW_UP, QUIZ_MENSAL, CUSTOM
- `frontend-hormonia/src/features/flow-designer/` directory deleted entirely
- `frontend-hormonia/src/types/flow-designer.ts` deleted
- `FlowDesignerDialog` and `templateConverters` deleted
- Consumer files (TemplateManagementPage, FlowTemplateCard, types/index.ts, templates/index.ts) cleaned of dead imports/references
- TemplateManagementPage remains functional as a template listing page
- FlowTemplateCard retains non-designer functionality (Versões, Desativar)
- `AlertRuleType.TREATMENT_ADHERENCE` and other separate enums with matching string values are NOT touched
- Backend tests pass (`pytest tests/ -x -q`)
- Frontend typecheck passes (`npx tsc --noEmit`)
- Frontend build passes (`npm run build`)

## Proof Level

- This slice proves: operational
- Real runtime required: no (build + typecheck + test gates are sufficient)
- Human/UAT required: no

## Verification

```bash
# Backend: all tests pass (deleted test files no longer collected)
cd backend-hormonia && python -m pytest tests/ -x -q

# Frontend typecheck
cd frontend-hormonia && npx tsc --noEmit

# Frontend build
cd frontend-hormonia && npm run build
```

- Backend pytest exits 0 with no failures
- `tsc --noEmit` exits 0 with no broken imports from deleted files
- `vite build` succeeds with no missing modules
- Diagnostic: `cd backend-hormonia && python -c "from app.services.flow.types import FlowType; members = [m.value for m in FlowType]; assert members == ['onboarding','daily_follow_up','quiz_mensal','custom'], f'Unexpected: {members}'"` exits 0
- Failure-path: `cd backend-hormonia && python -c "from app.services.flow.types import normalize_flow_type; r = normalize_flow_type('treatment_adherence'); assert r.value == 'custom', f'Fallback broken: {r}'"` exits 0 (stale DB values handled)

## Integration Closure

- Upstream surfaces consumed: none (independent slice)
- New wiring introduced in this slice: none (deletion only)
- What remains before the milestone is truly usable end-to-end: S03 builds the day-list template editor on top of the cleaned subsystem; S04–S06 add personalization, alerts, and summary

## Tasks

- [x] **T01: Delete backend tombstones and phantom FlowType members** `est:30m`
  - Why: Remove the tombstoned `flow/templates/` package (4 files raising ImportError), its ~4600 lines of dead tests across 2 directories, and 7 phantom FlowType enum members that have zero live callers — clearing backend dead code for S03.
  - Files: `backend-hormonia/app/services/flow/templates/` (delete dir), `backend-hormonia/tests/services/flow/templates/` (delete dir), `backend-hormonia/tests/unit/services/flow/templates/` (delete dir), `backend-hormonia/app/services/flow/types.py` (edit enum)
  - Do:
    1. Delete the entire `backend-hormonia/app/services/flow/templates/` directory (4 tombstone files)
    2. Delete the entire `backend-hormonia/tests/services/flow/templates/` directory (6 test files, ~2900 lines)
    3. Delete the entire `backend-hormonia/tests/unit/services/flow/templates/` directory (2 test files, ~1700 lines)
    4. Edit `backend-hormonia/app/services/flow/types.py`: remove FlowType enum members TREATMENT_ADHERENCE, SYMPTOM_TRACKING, MEDICATION_REMINDER, APPOINTMENT_PREP, POST_APPOINTMENT, EMERGENCY_PROTOCOL, MONITORING. Keep only ONBOARDING, DAILY_FOLLOW_UP, QUIZ_MENSAL, CUSTOM.
    5. CRITICAL: Do NOT touch `AlertRuleType` in `app/services/alerts/types.py`, `MetricType` in `app/monitoring/business_metrics.py`, or `AnalyticsEventType` in `app/services/analytics/data_extraction/models.py` — these are separate enums with matching string values.
    6. Run `cd backend-hormonia && python -m pytest tests/ -x -q` to verify
  - Verify: `cd backend-hormonia && python -m pytest tests/ -x -q` exits 0
  - Done when: Backend tests pass with tombstoned package deleted and FlowType containing only 4 canonical members

- [ ] **T02: Delete FlowDesigner frontend and clean consumer imports** `est:1h`
  - Why: Remove the entire visual flow designer feature (~4800 lines including tests) from the frontend, clean imports in consumer files (TemplateManagementPage, FlowTemplateCard), and verify the frontend still builds and typechecks cleanly.
  - Files: `frontend-hormonia/src/features/flow-designer/` (delete dir), `frontend-hormonia/src/types/flow-designer.ts` (delete), `frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx` (delete), `frontend-hormonia/src/features/templates/utils/templateConverters.ts` (delete), `frontend-hormonia/src/types/index.ts` (edit), `frontend-hormonia/src/features/templates/index.ts` (edit), `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx` (edit), `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` (edit)
  - Do:
    1. Delete `frontend-hormonia/src/features/flow-designer/` directory entirely (7 source + 8 test files)
    2. Delete `frontend-hormonia/src/types/flow-designer.ts` (233 lines)
    3. Delete `frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx` (216 lines)
    4. Delete `frontend-hormonia/src/features/templates/utils/templateConverters.ts` (120 lines)
    5. Edit `frontend-hormonia/src/types/index.ts`: remove the `export * from './flow-designer'` line (and its comment). The `ChartData` and `TreatmentType` interfaces already have duplicate local definitions at lines ~123 and ~133 of this file.
    6. Edit `frontend-hormonia/src/features/templates/index.ts`: remove `export { FlowDesignerDialog }` (line 14) and `export { convertTemplateToDesign, convertDesignToTemplate }` (line 24)
    7. Edit `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx`: remove `FlowDesignerDialog` import, `showFlowDesigner` state, button onClick that sets it, `onCreateNew` handler, and the `<FlowDesignerDialog>` JSX block. Keep the rest of the page (list/search/filter/pagination) intact.
    8. Edit `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx`: remove `FlowDesignerDialog` import, `showEditor`/`editMode` state, `handleEdit`/`handleNewVersion` handlers, the `<FlowDesignerDialog>` JSX block, and the Edit/Nova Versão buttons. Keep the card structure, Versões button, Desativar button.
    9. Run typecheck: `cd frontend-hormonia && npx tsc --noEmit`
    10. Run build: `cd frontend-hormonia && npm run build`
  - Verify: `cd frontend-hormonia && npx tsc --noEmit && npm run build` both exit 0
  - Done when: Frontend builds and typechecks with zero FlowDesigner references, TemplateManagementPage and FlowTemplateCard remain functional without designer features

## Files Likely Touched

- `backend-hormonia/app/services/flow/templates/` (delete dir)
- `backend-hormonia/tests/services/flow/templates/` (delete dir)
- `backend-hormonia/tests/unit/services/flow/templates/` (delete dir)
- `backend-hormonia/app/services/flow/types.py`
- `frontend-hormonia/src/features/flow-designer/` (delete dir)
- `frontend-hormonia/src/types/flow-designer.ts` (delete)
- `frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx` (delete)
- `frontend-hormonia/src/features/templates/utils/templateConverters.ts` (delete)
- `frontend-hormonia/src/types/index.ts`
- `frontend-hormonia/src/features/templates/index.ts`
- `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx`
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx`
.py`
- `frontend-hormonia/src/features/flow-designer/` (delete dir)
- `frontend-hormonia/src/types/flow-designer.ts` (delete)
- `frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx` (delete)
- `frontend-hormonia/src/features/templates/utils/templateConverters.ts` (delete)
- `frontend-hormonia/src/types/index.ts`
- `frontend-hormonia/src/features/templates/index.ts`
- `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx`
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx`
