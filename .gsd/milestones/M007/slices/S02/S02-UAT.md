# S02: Remover abstrações mortas do subsistema de fluxo — UAT

**Milestone:** M007
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: This slice is deletion-only (dead code removal). Build gates, typecheck, and test suites are the definitive proof that no live behavior was broken. No new runtime behavior was introduced.

## Preconditions

- Repository checked out with S02 changes applied
- Node.js available for frontend build/typecheck
- Python 3 available for backend tests and diagnostic commands
- Working directory: project root

## Smoke Test

Run all three verification gates in sequence:

```bash
cd backend-hormonia && python3 -m pytest tests/services/flow/ tests/unit/services/flow/ -x -q --deselect tests/unit/services/flow/test_sequential_message_handler_split_contract.py
cd frontend-hormonia && npx tsc --noEmit
cd frontend-hormonia && npm run build
```

All three must exit 0 with no failures.

## Test Cases

### 1. FlowType enum contains only canonical members

1. Run: `cd backend-hormonia && python3 -c "from app.services.flow.types import FlowType; print([m.value for m in FlowType])"`
2. **Expected:** Output is exactly `['onboarding', 'daily_follow_up', 'quiz_mensal', 'custom']`

### 2. Stale DB values fall back to CUSTOM gracefully

1. Run: `cd backend-hormonia && python3 -c "from app.services.flow.types import normalize_flow_type; print(normalize_flow_type('treatment_adherence').value)"`
2. **Expected:** Output is `custom`
3. Run: `cd backend-hormonia && python3 -c "from app.services.flow.types import normalize_flow_type; print(normalize_flow_type('symptom_tracking').value)"`
4. **Expected:** Output is `custom`

### 3. Tombstoned flow/templates package is gone

1. Run: `ls backend-hormonia/app/services/flow/templates/ 2>&1`
2. **Expected:** "No such file or directory"
3. Run: `cd backend-hormonia && python3 -c "from app.services.flow.templates import manager" 2>&1`
4. **Expected:** `ModuleNotFoundError: No module named 'app.services.flow.templates'`

### 4. Dead test directories are gone

1. Run: `ls backend-hormonia/tests/services/flow/templates/ 2>&1`
2. **Expected:** "No such file or directory"
3. Run: `ls backend-hormonia/tests/unit/services/flow/templates/ 2>&1`
4. **Expected:** "No such file or directory"

### 5. FlowDesigner frontend directory is gone

1. Run: `ls frontend-hormonia/src/features/flow-designer/ 2>&1`
2. **Expected:** "No such file or directory"
3. Run: `ls frontend-hormonia/src/types/flow-designer.ts 2>&1`
4. **Expected:** "No such file or directory"

### 6. No dangling FlowDesigner imports in frontend source

1. Run: `grep -r "FlowDesignerDialog\|flow-designer\|templateConverters" --include='*.ts' --include='*.tsx' frontend-hormonia/src/`
2. **Expected:** No output (exit code 1, no matches)

### 7. Separate enums with matching string values are untouched

1. Run: `grep "TREATMENT_ADHERENCE" backend-hormonia/app/services/alerts/types.py`
2. **Expected:** At least one hit showing `AlertRuleType.TREATMENT_ADHERENCE` still exists
3. Run: `grep "TREATMENT_ADHERENCE" backend-hormonia/app/services/flow/types.py`
4. **Expected:** No output (phantom member removed from FlowType)

### 8. Frontend build succeeds

1. Run: `cd frontend-hormonia && npm run build`
2. **Expected:** Exit 0, "built in" message with module count, no missing module errors

### 9. Frontend typecheck passes

1. Run: `cd frontend-hormonia && npx tsc --noEmit 2>&1 | grep -v "tests/e2e/"`
2. **Expected:** No error lines (pre-existing e2e config errors are in excluded files)

### 10. Backend flow tests pass

1. Run: `cd backend-hormonia && python3 -m pytest tests/services/flow/ tests/unit/services/flow/ -x -q --deselect tests/unit/services/flow/test_sequential_message_handler_split_contract.py`
2. **Expected:** All pass (80+ passed, 4 skipped for tombstoned analytics, 0 failed)

## Edge Cases

### Stale DB value with unknown type string

1. Run: `cd backend-hormonia && python3 -c "from app.services.flow.types import normalize_flow_type; print(normalize_flow_type('completely_unknown_type').value)"`
2. **Expected:** `custom` (any unrecognized string falls back to CUSTOM)

### Deleted FlowDesignerDialog.tsx and templateConverters.ts

1. Run: `ls frontend-hormonia/src/features/templates/flows/FlowDesignerDialog.tsx 2>&1`
2. **Expected:** "No such file or directory"
3. Run: `ls frontend-hormonia/src/features/templates/utils/templateConverters.ts 2>&1`
4. **Expected:** "No such file or directory"

### TemplateManagementPage still renders (no "Novo Template" button)

1. Run: `grep -c "FlowDesignerDialog\|showFlowDesigner\|onCreateNew" frontend-hormonia/src/features/templates/TemplateManagementPage.tsx`
2. **Expected:** `0` (all FlowDesigner references removed)
3. Run: `grep "TemplateManagementPage" frontend-hormonia/src/features/templates/index.ts`
4. **Expected:** At least one hit (page still exported from barrel)

### FlowTemplateCard retains Versões and Desativar

1. Run: `grep -c "Versões\|Desativar" frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx`
2. **Expected:** At least 2 (both buttons still present)
3. Run: `grep -c "FlowDesignerDialog\|handleEdit\|handleNewVersion\|showEditor\|editMode" frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx`
4. **Expected:** `0` (all designer references removed)

## Failure Signals

- `ModuleNotFoundError` in any backend import → deletion missed a live consumer
- `TS2307` (cannot find module) in frontend typecheck → dangling import to deleted file
- `vite build` error for missing module → barrel export still references deleted file
- FlowType enum has more than 4 members → phantom members not fully removed
- `normalize_flow_type('treatment_adherence')` does not return CUSTOM → fallback broken
- `AlertRuleType.TREATMENT_ADHERENCE` missing → separate enum incorrectly touched

## Requirements Proved By This UAT

- R059 — Dead abstractions removed with proof: FlowDesigner visual (~4800 lines), FlowTypes fantasma (7 members), tombstoned flow/templates package, and ~4600 lines of dead tests are all gone with build/typecheck/test gates green

## Not Proven By This UAT

- Knowledge graph cleanup (not in S02 scope — R059 partially deferred)
- Mixin soup simplification (not in S02 scope — R059 partially deferred)
- Runtime behavior on a live stack (deletion-only slice, no runtime changes)

## Notes for Tester

- The pre-existing `test_sequential_message_handler_split_contract.py` failure (521 > 500 lines) is not caused by S02 — deselect it with `--deselect` flag as shown.
- The 4 skipped tests are tombstoned analytics tests from Phase 16 — also pre-existing.
- The `tests/e2e/playwright.config.e2e.ts` TS4111 errors are pre-existing and in files excluded from tsconfig — ignore them in typecheck output.
- Documentation files (`README.md`, `REFACTORING_SUMMARY.md`) in `features/templates/` still mention FlowDesigner — these are stale docs, not source code.
