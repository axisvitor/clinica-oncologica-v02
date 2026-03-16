---
estimated_steps: 6
estimated_files: 4
---

# T01: Delete backend tombstones and phantom FlowType members

**Slice:** S02 — Remover abstrações mortas do subsistema de fluxo
**Milestone:** M007

## Description

Remove the tombstoned `flow/templates/` package (4 files that all raise ImportError), its ~4600 lines of dead tests across 2 test directories, and 7 phantom FlowType enum members that have zero live callers. This clears all backend dead code, preparing a clean subsystem for S03's template editor.

## Steps

1. Delete the entire directory `backend-hormonia/app/services/flow/templates/` — contains 4 tombstone files (`__init__.py`, `manager.py`, `repository.py`, `validator.py`) totaling ~33 lines, all raising `ImportError`
2. Delete the entire directory `backend-hormonia/tests/services/flow/templates/` — contains 6 test files (~2900 lines): `test_manager.py`, `test_repository.py`, `test_validator_transitions.py`, `_template_test_utils.py`, `test_validator_graph.py`, `__init__.py`
3. Delete the entire directory `backend-hormonia/tests/unit/services/flow/templates/` — contains 2 test files (~1700 lines): `test_template_validator.py`, `test_template_repository.py`
4. Edit `backend-hormonia/app/services/flow/types.py`: remove these FlowType enum members: `TREATMENT_ADHERENCE`, `SYMPTOM_TRACKING`, `MEDICATION_REMINDER`, `APPOINTMENT_PREP`, `POST_APPOINTMENT`, `EMERGENCY_PROTOCOL`, `MONITORING`. Keep only: `ONBOARDING`, `DAILY_FOLLOW_UP`, `QUIZ_MENSAL`, `CUSTOM`.
5. **CRITICAL SAFETY CHECK**: Verify you are editing ONLY the `FlowType` enum in `app/services/flow/types.py`. Do NOT touch: `AlertRuleType` in `app/services/alerts/types.py`, `MetricType` in `app/monitoring/business_metrics.py`, or `AnalyticsEventType` in `app/services/analytics/data_extraction/models.py`. These are separate enums that happen to have string values like `"treatment_adherence"`.
6. Run backend tests: `cd backend-hormonia && python -m pytest tests/ -x -q`

## Must-Haves

- [ ] `backend-hormonia/app/services/flow/templates/` directory deleted entirely
- [ ] `backend-hormonia/tests/services/flow/templates/` directory deleted entirely
- [ ] `backend-hormonia/tests/unit/services/flow/templates/` directory deleted entirely
- [ ] FlowType enum in `app/services/flow/types.py` contains ONLY: ONBOARDING, DAILY_FOLLOW_UP, QUIZ_MENSAL, CUSTOM
- [ ] `AlertRuleType.TREATMENT_ADHERENCE` (in `app/services/alerts/types.py`) is untouched
- [ ] `MetricType` (in `app/monitoring/business_metrics.py`) is untouched
- [ ] `AnalyticsEventType` (in `app/services/analytics/data_extraction/models.py`) is untouched
- [ ] Backend tests pass: `cd backend-hormonia && python -m pytest tests/ -x -q` exits 0

## Verification

- `cd backend-hormonia && python -m pytest tests/ -x -q` exits 0 with no failures
- `ls backend-hormonia/app/services/flow/templates/` returns "No such file or directory"
- `ls backend-hormonia/tests/services/flow/templates/` returns "No such file or directory"
- `ls backend-hormonia/tests/unit/services/flow/templates/` returns "No such file or directory"
- `grep -c "TREATMENT_ADHERENCE\|SYMPTOM_TRACKING\|MEDICATION_REMINDER\|APPOINTMENT_PREP\|POST_APPOINTMENT\|EMERGENCY_PROTOCOL\|MONITORING" backend-hormonia/app/services/flow/types.py` returns 0

## Inputs

- `backend-hormonia/app/services/flow/types.py` — the FlowType enum to edit (remove 7 phantom members, keep 4 canonical)
- `backend-hormonia/app/services/flow/templates/` — tombstone directory to delete (4 files raising ImportError)
- `backend-hormonia/tests/services/flow/templates/` — dead test directory to delete (6 files, ~2900 lines)
- `backend-hormonia/tests/unit/services/flow/templates/` — dead test directory to delete (2 files, ~1700 lines)
- Research confirmed zero live callers for deleted enum members via `rg "FlowType\.(APPOINTMENT_PREP|...)"` — only references were in the tombstoned tests being deleted
- `normalize_flow_type()` in the same file already falls back to `FlowType.CUSTOM` for unknown values, so stale DB rows won't crash

## Expected Output

- `backend-hormonia/app/services/flow/templates/` — gone
- `backend-hormonia/tests/services/flow/templates/` — gone
- `backend-hormonia/tests/unit/services/flow/templates/` — gone
- `backend-hormonia/app/services/flow/types.py` — FlowType enum with only ONBOARDING, DAILY_FOLLOW_UP, QUIZ_MENSAL, CUSTOM
- Backend test suite passing green
