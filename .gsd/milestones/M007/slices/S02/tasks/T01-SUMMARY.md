---
id: T01
parent: S02
milestone: M007
provides:
  - Clean FlowType enum with only 4 canonical members
  - Tombstoned flow/templates package fully removed
  - ~4600 lines of dead test code deleted
key_files:
  - backend-hormonia/app/services/flow/types.py
key_decisions:
  - Removed 7 phantom FlowType enum members; normalize_flow_type() fallback handles stale DB values gracefully
patterns_established:
  - none
observability_surfaces:
  - "python3 -c 'from app.services.flow.types import FlowType; print([m.value for m in FlowType])' — confirms 4 canonical members"
  - "normalize_flow_type('treatment_adherence') → FlowType.CUSTOM — stale value fallback"
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Delete backend tombstones and phantom FlowType members

**Removed tombstoned flow/templates package (4 files), ~4600 lines of dead tests (8 files across 2 directories), and 7 phantom FlowType enum members — leaving only the 4 canonical members.**

## What Happened

1. Deleted `backend-hormonia/app/services/flow/templates/` — 4 tombstone files (`__init__.py`, `manager.py`, `repository.py`, `validator.py`) all raising ImportError.
2. Deleted `backend-hormonia/tests/services/flow/templates/` — 6 test files (~2900 lines).
3. Deleted `backend-hormonia/tests/unit/services/flow/templates/` — 2 test files (~1700 lines).
4. Edited `backend-hormonia/app/services/flow/types.py` — removed 7 phantom FlowType enum members (TREATMENT_ADHERENCE, SYMPTOM_TRACKING, MEDICATION_REMINDER, APPOINTMENT_PREP, POST_APPOINTMENT, EMERGENCY_PROTOCOL, MONITORING). Kept ONBOARDING, DAILY_FOLLOW_UP, QUIZ_MENSAL, CUSTOM.
5. Safety check confirmed: `AlertRuleType` in `alerts/types.py`, `MetricType` in `business_metrics.py`, and `AnalyticsEventType` in `data_extraction/models.py` are all untouched.

## Verification

- `ls` on all 3 deleted directories returns "No such file or directory" ✅
- `grep -c` for phantom members in `types.py` returns 0 ✅
- `FlowType` enum contains exactly `['onboarding', 'daily_follow_up', 'quiz_mensal', 'custom']` ✅
- `normalize_flow_type('treatment_adherence')` returns `FlowType.CUSTOM` (fallback works) ✅
- Flow subsystem tests pass: 84 passed, 4 skipped (pre-existing tombstoned analytics), 0 failed ✅
- Test collection across full suite succeeds — no import errors from deletions ✅
- Separate enums (`AlertRuleType.TREATMENT_ADHERENCE`, `MetricType`, `AnalyticsEventType`) confirmed untouched ✅

**Pre-existing failures (not caused by this task):**
- `tests/services/webhook/test_message_extractor.py` — imports a tombstoned module (Phase 37)
- `tests/api/critical/test_firebase_auth.py` — monkeypatches non-existent `_firebase_service` attribute
- `tests/unit/services/flow/test_sequential_message_handler_split_contract.py` — line-count contract (521 > 500)

**Slice-level verification (partial — T01 is intermediate):**
- Backend pytest (flow subsystem): ✅ passes
- Frontend typecheck: not yet (T02 scope)
- Frontend build: not yet (T02 scope)

## Diagnostics

- `cd backend-hormonia && python3 -c "from app.services.flow.types import FlowType; print([m.value for m in FlowType])"` — shows exactly 4 members
- `cd backend-hormonia && python3 -c "from app.services.flow.types import normalize_flow_type; print(normalize_flow_type('treatment_adherence'))"` — confirms fallback to CUSTOM
- Any future `from app.services.flow.templates import ...` raises `ModuleNotFoundError`

## Deviations

None.

## Known Issues

- 3 pre-existing test failures unrelated to this task (tombstoned webhook test, firebase auth monkeypatch, line-count contract). These exist on the baseline and are not regressions.
- Full-suite pytest run exceeds 600s, making `pytest tests/ -x -q` impractical as a single command. Flow-subsystem-scoped run confirms no regressions.

## Files Created/Modified

- `backend-hormonia/app/services/flow/types.py` — removed 7 phantom FlowType enum members
- `backend-hormonia/app/services/flow/templates/` — deleted directory (4 tombstone files)
- `backend-hormonia/tests/services/flow/templates/` — deleted directory (6 dead test files)
- `backend-hormonia/tests/unit/services/flow/templates/` — deleted directory (2 dead test files)
- `.gsd/milestones/M007/slices/S02/S02-PLAN.md` — added Observability/Diagnostics section and failure-path verification
- `.gsd/milestones/M007/slices/S02/tasks/T01-PLAN.md` — added Observability Impact section
