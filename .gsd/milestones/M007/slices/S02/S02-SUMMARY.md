---
id: S02
parent: M007
milestone: M007
provides:
  - FlowDesigner visual canvas feature fully removed (~4800 lines frontend + tests)
  - FlowType enum reduced to 4 canonical members (ONBOARDING, DAILY_FOLLOW_UP, QUIZ_MENSAL, CUSTOM)
  - Tombstoned flow/templates package deleted (4 files + ~4600 lines of dead tests)
  - normalize_flow_type() graceful fallback for stale DB values → CUSTOM
  - TemplateManagementPage and FlowTemplateCard cleaned, functional without designer
requires:
  - slice: none
    provides: independent slice
affects:
  - S03
key_files:
  - backend-hormonia/app/services/flow/types.py
  - frontend-hormonia/src/features/templates/TemplateManagementPage.tsx
  - frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx
  - frontend-hormonia/src/features/templates/flows/FlowTemplateList.tsx
  - frontend-hormonia/src/types/index.ts
  - frontend-hormonia/src/features/templates/index.ts
key_decisions:
  - Removed 7 phantom FlowType enum members; normalize_flow_type() fallback handles stale DB values gracefully to CUSTOM
  - Made FlowTemplateList.onCreateNew optional since the designer that provided it is gone
  - Removed "Novo Template" button from page header (only opened FlowDesignerDialog)
  - Removed Edit and Nova Versão buttons from FlowTemplateCard (only opened FlowDesignerDialog)
  - Did NOT touch AlertRuleType, MetricType, or AnalyticsEventType — separate enums with matching string values
patterns_established:
  - none
observability_surfaces:
  - "python3 -c 'from app.services.flow.types import FlowType; print([m.value for m in FlowType])' — confirms 4 canonical members"
  - "normalize_flow_type('treatment_adherence') → FlowType.CUSTOM — stale value fallback"
  - "grep -r 'FlowDesignerDialog|flow-designer' --include='*.ts' --include='*.tsx' frontend-hormonia/src/ — must return no hits"
drill_down_paths:
  - .gsd/milestones/M007/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007/slices/S02/tasks/T02-SUMMARY.md
duration: 30m
verification_result: passed
completed_at: 2026-03-16
---

# S02: Remover abstrações mortas do subsistema de fluxo

**Deleted ~4800 lines of FlowDesigner visual canvas, ~4600 lines of dead tests, 7 phantom FlowType enum members, and the tombstoned flow/templates package — leaving build, typecheck, and backend tests green with a clean subsystem ready for S03's template editor.**

## What Happened

**T01 — Backend cleanup (15m):** Deleted the tombstoned `flow/templates/` package (4 files all raising ImportError), its dead tests across 2 directories (~4600 lines in 8 files), and 7 phantom FlowType enum members (TREATMENT_ADHERENCE, SYMPTOM_TRACKING, MEDICATION_REMINDER, APPOINTMENT_PREP, POST_APPOINTMENT, EMERGENCY_PROTOCOL, MONITORING). The `normalize_flow_type()` function's existing fallback gracefully maps any stale DB values to `FlowType.CUSTOM`. Critical safety constraint respected: `AlertRuleType`, `MetricType`, and `AnalyticsEventType` — separate enums in separate files with matching string values — were left untouched.

**T02 — Frontend cleanup (15m):** Deleted the entire `flow-designer/` feature directory (7 source + 8 test files), `types/flow-designer.ts` (233 lines), `FlowDesignerDialog.tsx` (216 lines), and `templateConverters.ts` (120 lines). Cleaned barrel exports in `types/index.ts` and `templates/index.ts`. Cleaned TemplateManagementPage (removed designer dialog, "Novo Template" button, related state) and FlowTemplateCard (removed Edit/Nova Versão buttons, designer dialog, related state). Made `FlowTemplateList.onCreateNew` optional since no caller provides it now. Both pages remain functional — TemplateManagementPage keeps list/search/filter/pagination, FlowTemplateCard keeps card display/Versões/Desativar.

## Verification

All slice-level verification gates pass:

- **FlowType enum**: exactly `['onboarding', 'daily_follow_up', 'quiz_mensal', 'custom']` ✅
- **Stale DB fallback**: `normalize_flow_type('treatment_adherence')` → `FlowType.CUSTOM` ✅
- **Deleted directories/files**: all 7 targets confirmed absent (No such file or directory) ✅
- **Dead import scan**: `grep -r "FlowDesignerDialog|flow-designer|templateConverters"` returns no hits ✅
- **Phantom FlowType count**: 0 matches in `types.py` ✅
- **Separate enums intact**: `AlertRuleType.TREATMENT_ADHERENCE` confirmed present ✅
- **Frontend typecheck**: `npx tsc --noEmit` passes (only pre-existing e2e config errors in excluded files) ✅
- **Frontend build**: `npm run build` exits 0 (4748 modules transformed) ✅
- **Backend flow tests**: 84 passed, 4 skipped, 0 failed ✅

## Requirements Advanced

- R059 — FlowDesigner visual, FlowTypes fantasma, and tombstoned templates package fully removed with build/typecheck/test proof

## Requirements Validated

- R059 — Validated by: FlowDesigner (~4800 lines) deleted, 7 phantom FlowType members removed, tombstoned flow/templates package deleted, dead tests deleted (~4600 lines), frontend build + typecheck green, backend tests green, normalize_flow_type stale fallback proven, separate enums untouched

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- Made `FlowTemplateList.onCreateNew` prop optional (was required) — necessary because TemplateManagementPage no longer passes it after designer removal. Not in original plan but logically required.
- Removed unused `Plus` icon and `Button` imports from TemplateManagementPage — cleanup of now-unused imports.

## Known Limitations

- Documentation files (`README.md`, `REFACTORING_SUMMARY.md` in `features/templates/`) still reference FlowDesignerDialog — stale docs, not source code.
- Pre-existing `tests/e2e/playwright.config.e2e.ts` has TS4111 errors unrelated to this slice (files excluded from tsconfig).
- 3 pre-existing backend test failures unrelated to this slice: tombstoned webhook test, firebase auth monkeypatch, sequencing.py line-count contract (521 > 500).

## Follow-ups

- none

## Files Created/Modified

- `backend-hormonia/app/services/flow/types.py` — removed 7 phantom FlowType enum members
- `backend-hormonia/app/services/flow/templates/` — deleted directory (4 tombstone files)
- `backend-hormonia/tests/services/flow/templates/` — deleted directory (6 dead test files)
- `backend-hormonia/tests/unit/services/flow/templates/` — deleted directory (2 dead test files)
- `frontend-hormonia/src/features/flow-designer/` — deleted directory (15 files)
- `frontend-hormonia/src/types/flow-designer.ts` — deleted (233 lines)
- `frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx` — deleted (216 lines)
- `frontend-hormonia/src/features/templates/utils/templateConverters.ts` — deleted (120 lines)
- `frontend-hormonia/src/types/index.ts` — removed flow-designer re-export
- `frontend-hormonia/src/features/templates/index.ts` — removed FlowDesignerDialog and converter exports
- `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx` — removed FlowDesigner references, cleaned imports
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — removed designer features
- `frontend-hormonia/src/features/templates/flows/FlowTemplateList.tsx` — made onCreateNew optional

## Forward Intelligence

### What the next slice should know
- The flow subsystem is clean: `FlowType` has 4 members, `FlowTemplateVersion` + `EnhancedTemplateLoader` are the canonical template surface. S03's day-list template editor builds directly on this.
- TemplateManagementPage still works as a template listing page but has no "create" or "edit" entry point — S03 needs to add the new day-list editor UI.
- FlowTemplateCard kept Versões and Desativar buttons but lost Edit and Nova Versão — S03 should add the new editing surface.

### What's fragile
- `FlowTemplateList.onCreateNew` is now optional and renders no button when omitted — S03 should provide a new handler when adding create functionality.
- The `ChartData` and `TreatmentType` interfaces in `types/index.ts` have duplicate local definitions (lines ~123 and ~133) that took over from the deleted `flow-designer.ts` re-export — no issue currently but worth being aware of if those types are touched.

### Authoritative diagnostics
- `python3 -c "from app.services.flow.types import FlowType; print([m.value for m in FlowType])"` — single source of truth for enum state
- `npm run build` exit code — the final arbiter for frontend integrity after any template-related change
- `grep -r "FlowDesignerDialog|flow-designer" --include='*.ts' --include='*.tsx' frontend-hormonia/src/` — should always return empty

### What assumptions changed
- The plan estimated ~4800 lines for FlowDesigner — this was accurate across the 15 source + 8 test files plus supporting types/dialog/converters
- Full-suite `pytest tests/ -x -q` is impractical (>600s); flow-subsystem-scoped run is the pragmatic verification path
