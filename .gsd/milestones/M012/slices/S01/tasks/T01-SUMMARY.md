---
id: T01
parent: S01
milestone: M012
provides:
  - patient_flow_overrides Alembic migration (table + FK + unique constraint + index)
  - PatientFlowOverride SQLAlchemy model in flow.py
  - Pydantic request/response schemas in patient_overrides.py
key_files:
  - backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py
  - backend-hormonia/app/models/flow.py
  - backend-hormonia/app/schemas/v2/patient_overrides.py
key_decisions: []
patterns_established:
  - Override model follows BaseModel pattern (inherits id/created_at/updated_at) with backref relationship to PatientFlowState
observability_surfaces:
  - patient_flow_overrides table queryable by patient_flow_state_id
  - PatientFlowState.overrides backref for REPL/debug inspection
  - UNIQUE constraint uq_pfo_state_day prevents duplicate day overrides at DB level
  - FK ON DELETE CASCADE auto-cleans orphan overrides
duration: 10m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T01: Create migration, model, and schemas for patient_flow_overrides

**Added patient_flow_overrides Alembic migration, SQLAlchemy model, and Pydantic request/response schemas for per-patient flow day overrides**

## What Happened

Created the complete data layer for per-patient flow day overrides:

1. **Alembic migration** (`m012_s01_patient_flow_overrides`) — creates `patient_flow_overrides` table with UUID PK, FK to `patient_flow_states` with ON DELETE CASCADE, UNIQUE constraint on (patient_flow_state_id, day_number), and index on patient_flow_state_id. Chains from `m011_s01_patient_flow_states_index`.

2. **SQLAlchemy model** (`PatientFlowOverride`) — added to `flow.py` after `PatientFlowState`. Uses `BaseModel` (inherits id/created_at/updated_at). Columns: patient_flow_state_id (FK), day_number, content, message_type, expects_response, skip, created_by. Relationship backref `overrides` on PatientFlowState.

3. **Pydantic schemas** (`patient_overrides.py`) — `OverrideDayInput` (request), `OverrideDayUpdateRequest` (bulk request), `MergedDayItem` (response with `source: Literal["global", "override"]` and `editable: bool`), `MergedDayListResponse` (full merged view).

## Verification

- `ast.parse` PASS on all 3 files (migration, model, schemas)
- `grep down_revision` → `m011_s01_patient_flow_states_index` ✓
- Model has FK to patient_flow_states with ON DELETE CASCADE ✓
- UniqueConstraint `uq_pfo_state_day` on (patient_flow_state_id, day_number) ✓
- Schema has `source: Literal["global", "override"]` and `editable: bool` ✓
- Slice verification: 3/5 PASS, 1 SKIP (T02 file not yet created), 1 already existed

## Diagnostics

- Query overrides: `SELECT * FROM patient_flow_overrides WHERE patient_flow_state_id = :id`
- ORM inspection: `flow_state.overrides` returns list of PatientFlowOverride for a given PatientFlowState
- Constraint violations surface as IntegrityError with constraint name `uq_pfo_state_day`

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py` — new Alembic migration creating patient_flow_overrides table
- `backend-hormonia/app/models/flow.py` — added PatientFlowOverride model after PatientFlowState
- `backend-hormonia/app/schemas/v2/patient_overrides.py` — new Pydantic schemas for override request/response
- `.gsd/milestones/M012/slices/S01/tasks/T01-PLAN.md` — added Observability Impact section (pre-flight fix)
