---
id: T02
parent: S04
milestone: M007
provides:
  - PatientFlowResponse model and migration for structured patient response storage
  - Dual-write path in process_patient_response() persisting to patient_flow_responses table
key_files:
  - backend-hormonia/alembic/versions/m007_s04_t02_patient_flow_responses.py
  - backend-hormonia/app/models/patient_flow_response.py
  - backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py
key_decisions:
  - Dual-write block placed outside if flow_state block so responses are persisted even without active flow state
  - flow_state_id column nullable with ON DELETE SET NULL to preserve response history when flow states are cleaned up
patterns_established:
  - Dual-write pattern: new structured table + existing step_data JSONB in same transaction
observability_surfaces:
  - SQL: SELECT * FROM patient_flow_responses WHERE patient_id = ? ORDER BY responded_at DESC
  - Failure: if dual-write fails, entire transaction rolls back (step_data + flow_response)
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Create patient_flow_responses table, model, and wire dual-write

**Created Alembic migration, PatientFlowResponse SQLAlchemy model, and wired dual-write into process_patient_response() so every patient response is persisted to the new structured table in the same DB transaction**

## What Happened

1. Created Alembic migration `m007_s04_t02_patient_flow_responses` depending on `m006_s02_t03_drop_users_firebase_residue`. Table has UUID PK, nullable FK to `patient_flow_states`, not-null FK to `patients`, day/message context columns, response text, timestamps, and prompt/response message IDs. Four indexes including composite `(patient_id, responded_at)` for period queries.

2. Created `PatientFlowResponse` model extending `BaseModel` with relationships to `PatientFlowState` and `Patient`. Registered in models `__init__.py` barrel export.

3. Wired dual-write in `response_processing.py`: the new `PatientFlowResponse` row is created OUTSIDE the `if flow_state:` block (so it fires even when `flow_state is None`), and BEFORE the `await self.db.commit()`. Sets `commit_needed = True` unconditionally after `self.db.add()`.

## Verification

- `python -c "from app.models.patient_flow_response import PatientFlowResponse; print('OK')"` → **OK**
- `PatientFlowResponse(flow_state_id=None, ...)` instantiation → **NULL flow_state_id OK**
- `pytest tests/unit/services/flow/ -v --tb=short` → **140 passed, 1 pre-existing failure (unrelated line-count contract on sequencing.py), 4 skipped, 0 regressions**
- `pytest tests/unit/services/flow/test_personalization_grounding.py -v -k "hallucin or empty or ai_skip"` → **7 passed**

### Slice-level verification status (T02 of 3):
- ✅ Diagnostic/failure-path: grounding rejects hallucinated content (7 passed)
- ✅ Diagnostic/failure-path: NULL flow_state_id instantiation OK
- ✅ T01: Grounding calibration tests (25 passed, via full suite)
- ✅ T02: Model imports cleanly
- ⬜ T03: Response API and integration tests (not yet created)
- ✅ Slice-level: all flow tests green (140 passed, 0 regressions)

## Diagnostics

- **Inspect responses**: `SELECT * FROM patient_flow_responses WHERE patient_id = ? ORDER BY responded_at DESC`
- **Period query**: `SELECT * FROM patient_flow_responses WHERE patient_id = ? AND responded_at BETWEEN ? AND ?` (uses `ix_pfr_patient_responded` composite index)
- **Failure state**: if the DB write fails, SQLAlchemy exception propagates through the existing error handler in `process_patient_response()`, rolling back both `step_data` and `patient_flow_responses` writes

## Deviations

None

## Known Issues

- Pre-existing: `test_split_files_under_500_lines` fails because `sequencing.py` has 521 lines — not introduced by this task

## Files Created/Modified

- `backend-hormonia/alembic/versions/m007_s04_t02_patient_flow_responses.py` — New Alembic migration creating patient_flow_responses table with 4 indexes
- `backend-hormonia/app/models/patient_flow_response.py` — New SQLAlchemy model with relationships to PatientFlowState and Patient
- `backend-hormonia/app/models/__init__.py` — Added PatientFlowResponse to barrel exports
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py` — Added dual-write block and PatientFlowResponse import
- `.gsd/milestones/M007/slices/S04/S04-PLAN.md` — Added diagnostic failure-path verification check
