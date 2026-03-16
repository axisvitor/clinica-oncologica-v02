# S02 — Remover abstrações mortas do subsistema de fluxo — Research

**Date:** 2026-03-16
**Depth:** Light (well-scoped deletion of known dead code with clear verification)
**Requirement:** R059 — Abstrações mortas de fluxo são removidas com prova

## Summary

S02 is a surgical dead-code removal slice. Every target is already identified, tombstoned, or provably unused. The work divides into three independent tracks: (1) delete the FlowDesigner visual feature from frontend + clean its consumers, (2) strip phantom FlowType enum members from the backend, (3) delete the tombstoned `flow/templates` package and its ~4600 lines of dead tests. All tracks converge on a single verification gate: frontend build + typecheck green, backend tests green.

No new technology, no architectural decisions, no ambiguous scope. The only real pitfall is breaking the frontend templates feature (TemplateManagementPage, FlowTemplateCard) when removing the FlowDesignerDialog — those files need careful import cleanup, not deletion.

## Recommendation

Execute in three parallel tracks (frontend designer, backend enum, backend tombstones), then verify. The frontend track is largest and has the most import-chain risk so it should be done carefully. Backend changes are trivial deletions with no live callers.

## Implementation Landscape

### Key Files

**Track 1 — FlowDesigner deletion (frontend)**

Files to DELETE entirely:
- `frontend-hormonia/src/features/flow-designer/` — 7 source files (2336 lines) + 8 test files (2441 lines). The entire visual canvas designer. No consumers outside the templates feature.
- `frontend-hormonia/src/types/flow-designer.ts` (233 lines) — type definitions for visual designer nodes, connections, state, testing, import/export. Only consumed by flow-designer components and templateConverters.
- `frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx` (216 lines) — modal wrapping FlowDesigner. Imported by TemplateManagementPage and FlowTemplateCard.
- `frontend-hormonia/src/features/templates/utils/templateConverters.ts` (120 lines) — API↔FlowDesigner format converters. Only used by FlowDesignerDialog.

Files to EDIT:
- `frontend-hormonia/src/types/index.ts` — remove line 60-61 (`// Flow designer types...` + `export * from './flow-designer'`). The `ChartData` and `TreatmentType` interfaces also defined in flow-designer.ts already have duplicate local definitions at lines 123 and 133 of this same file, so removing the re-export won't break consumers.
- `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx` — remove `FlowDesignerDialog` import (line 25), `showFlowDesigner` state (line 35), button onClick setter (line 80), `onCreateNew` handler (line 137), and the `<FlowDesignerDialog>` JSX block (lines 156-158). The "Novo Template" button can stay as UI placeholder or be removed — S03 replaces it with the day-list editor.
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — remove `FlowDesignerDialog` import (line 11), `showEditor`/`editMode` state, `handleEdit`/`handleNewVersion` handlers, the `<FlowDesignerDialog>` JSX block (lines 101-112), and the Edit/Nova Versão buttons. Keep the card structure, Versões button, Desativar button.
- `frontend-hormonia/src/features/templates/index.ts` — remove line 14 (`export { FlowDesignerDialog }`) and line 24 (`export { convertTemplateToDesign, convertDesignToTemplate }`).

**Track 2 — Phantom FlowType members (backend)**

- `backend-hormonia/app/services/flow/types.py` — remove enum members: `TREATMENT_ADHERENCE`, `SYMPTOM_TRACKING`, `MEDICATION_REMINDER`, `APPOINTMENT_PREP`, `POST_APPOINTMENT`, `EMERGENCY_PROTOCOL`, `MONITORING`. Keep only: `ONBOARDING`, `DAILY_FOLLOW_UP`, `QUIZ_MENSAL`, `CUSTOM`. The `normalize_flow_type()` fallback to `CUSTOM` already handles unknown values safely.
  - **CRITICAL**: `TREATMENT_ADHERENCE` as a string also exists in `AlertRuleType` (`app/services/alerts/types.py`), `MetricType` (`app/monitoring/business_metrics.py`), `AnalyticsEventType` (`app/services/analytics/data_extraction/models.py`) — these are SEPARATE enums with matching string values and must NOT be touched. Only `FlowType` in `app/services/flow/types.py` is in scope.
  - `FlowType.APPOINTMENT_PREP` and `FlowType.EMERGENCY_PROTOCOL` are referenced only in tombstoned template tests (being deleted in Track 3), confirmed zero live callers via `rg "FlowType\.(APPOINTMENT_PREP|...)"`.

**Track 3 — Tombstoned templates package + dead tests (backend)**

Files to DELETE entirely:
- `backend-hormonia/app/services/flow/templates/` — entire directory (4 files, 33 lines total). All four files (`__init__.py`, `manager.py`, `repository.py`, `validator.py`) are tombstones that raise `ImportError`.
- `backend-hormonia/tests/services/flow/templates/` — 6 files (~2900 lines): `test_manager.py` (1022), `test_repository.py` (1011), `test_validator_transitions.py` (777), `_template_test_utils.py` (70), `test_validator_graph.py` (12), `__init__.py` (8). All import from tombstoned modules.
- `backend-hormonia/tests/unit/services/flow/templates/` — 2 files (~1700 lines): `test_template_validator.py` (1015), `test_template_repository.py` (683). Same — import from tombstoned modules.

### Build Order

1. **Track 3 first** (backend tombstones) — safest, zero risk. Delete tombstoned package + dead tests. Run backend tests to confirm no regressions.
2. **Track 2** (backend enum) — remove phantom FlowType members. Run backend tests again.
3. **Track 1** (frontend) — delete flow-designer directory and types, then edit consumers. Run frontend typecheck + build + tests.
4. **Final gate** — all three verification commands green.

### Verification Approach

```bash
# Backend: run all flow-related tests (deleted test dirs are gone, so no --ignore needed)
cd backend-hormonia && python -m pytest tests/ -x -q

# Frontend typecheck
cd frontend-hormonia && npx tsc --noEmit

# Frontend build
cd frontend-hormonia && npm run build

# Frontend tests
cd frontend-hormonia && npx vitest run
```

Observable outcomes:
- Backend pytest passes with 0 failures (deleted test files no longer collected)
- `tsc --noEmit` exits 0 (no broken imports from deleted files)
- `vite build` succeeds (no missing modules)
- vitest passes (deleted test files no longer collected, remaining tests green)

## Constraints

- **TemplateManagementPage must remain functional** — it's the live template listing page routed via `AdminRoutes.tsx`. Only the FlowDesignerDialog trigger needs removal; the list/search/filter/pagination UI stays intact.
- **FlowTemplateCard must keep non-designer functionality** — card displays template info, has Versões and Desativar buttons that remain live. Only Edit and Nova Versão (which open FlowDesignerDialog) are removed.
- **`normalize_flow_type()` handles unknown strings** — it falls back to `FlowType.CUSTOM`, so any stale DB rows with phantom flow_type values won't crash.
- **AlertRuleType.TREATMENT_ADHERENCE is a separate enum** — lives in `app/services/alerts/types.py`, used by 15 alert rules. Must NOT be touched.
- **Knowledge graph is out of scope** — `app/memory/knowledge_graph.py` (765 lines) is used via lazy import by `flow_coordinator/state_manager.py` and `quiz/session_coordinator.py`. It silently no-ops on ImportError. It's dead-ish but entangled with quiz/coordinator logic and not listed in the S02 scope. Leave for later.
- **Frontend `lib/flow-engine/` is out of scope** — `FlowEngine.ts`, `TemplateManager.ts`, `types.ts` (1103 lines total) reference `FlowType.INITIAL_15_DAYS` etc. These are the frontend API types enum, NOT the flow-designer types. The frontend `FlowType` enum in `lib/api-client/types/flows.ts` has its own phantom members (`INITIAL_15_DAYS`, `DAYS_16_45`, `MONTHLY_RECURRING`, etc.) but they're used in live `FlowStatus.tsx` switch statements and `FlowEngine.ts`. Cleaning these is a separate concern from the visual designer removal.

## Common Pitfalls

- **Duplicate type names across files** — `ChartData` and `TreatmentType` are defined in both `types/flow-designer.ts` AND `types/index.ts` directly. The re-export `export * from './flow-designer'` currently shadows the local definitions. After removing the re-export, the local definitions at lines 123 and 133 of `index.ts` take over. Verify no consumer expects the flow-designer-specific shape (checked: no consumer imports these from `@/types/flow-designer` directly).
- **Confusing TREATMENT_ADHERENCE across systems** — the string `"treatment_adherence"` exists in 3 separate enum types (FlowType, AlertRuleType, MetricType). Only FlowType is being cleaned. A grep-and-replace approach would be dangerous — edits must target the specific enum definition.
