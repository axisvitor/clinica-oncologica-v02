---
estimated_steps: 5
estimated_files: 3
---

# T02: Create patient_flow_responses table, model, and wire dual-write

**Slice:** S04 — Personalização IA e armazenamento de respostas
**Milestone:** M007

## Description

Create the `patient_flow_responses` table via Alembic migration, the `PatientFlowResponse` SQLAlchemy model, and wire the write path into `process_patient_response()` in `response_processing.py` so every patient response is persisted to the new table in the same DB transaction as the existing `step_data` writes.

## Steps

1. Create the Alembic migration file `backend-hormonia/alembic/versions/m007_s04_t02_patient_flow_responses.py`:
   - Revision ID: `m007_s04_t02_patient_flow_responses`
   - Depends on: `m006_s02_t03_drop_users_firebase_residue`
   - Table name: `patient_flow_responses`
   - Columns:
     - `id` — UUID primary key with `gen_random_uuid()` server default
     - `flow_state_id` — UUID, FK to `patient_flow_states.id` ON DELETE SET NULL, **nullable** (responses can exist without active flow state)
     - `patient_id` — UUID, FK to `patients.id` ON DELETE CASCADE, **not null**
     - `day_number` — Integer, nullable
     - `message_index` — Integer, nullable
     - `response_text` — Text, not null
     - `responded_at` — DateTime with timezone, not null
     - `prompt_message_id` — String(255), nullable
     - `response_message_id` — String(255), nullable
     - `created_at` — DateTime with timezone, server default `now()`
     - `updated_at` — DateTime with timezone, server default `now()`, onupdate `now()`
   - Indexes:
     - `ix_pfr_patient_id` on `patient_id`
     - `ix_pfr_flow_state_id` on `flow_state_id`
     - `ix_pfr_responded_at` on `responded_at`
     - `ix_pfr_patient_responded` composite on `(patient_id, responded_at)` for period queries
   - Downgrade: drop table `patient_flow_responses`

2. Create the SQLAlchemy model `backend-hormonia/app/models/patient_flow_response.py`:
   - Class `PatientFlowResponse(BaseModel)` with `__tablename__ = "patient_flow_responses"`
   - Mirror the migration columns with SQLAlchemy Column types
   - Relationships: `flow_state = relationship("PatientFlowState")`, `patient = relationship("Patient")`
   - Import `BaseModel` from `app.models.base`
   - Use `UUID(as_uuid=True)` for UUID columns, `JSONB` is not needed here

3. Register the model in the models package so it's discoverable:
   - Check if `backend-hormonia/app/models/__init__.py` has a barrel export pattern. If so, add the import there. If not, the model file is sufficient on its own.

4. Wire the dual-write into `backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py`:
   - Import `PatientFlowResponse` and `now_sao_paulo` at the top of the file
   - Locate the section after `state_data["last_response"] = {...}` and before `reminder_result = None` (around line 225-230)
   - Add a new block that creates a `PatientFlowResponse` instance:
     ```python
     # Persist structured response to dedicated table
     flow_response = PatientFlowResponse(
         flow_state_id=flow_state.id if flow_state else None,
         patient_id=patient_id,
         day_number=flow_day,
         message_index=message_index,
         response_text=response_text,
         responded_at=now_sao_paulo(),
         prompt_message_id=context.get("prompt_message_id"),
         response_message_id=context.get("response_message_id"),
     )
     self.db.add(flow_response)
     ```
   - This must be placed BEFORE the `await self.db.commit()` that happens at the end of the method. The existing code already has `commit_needed = True` when `flow_state` exists, but we also need to set `commit_needed = True` unconditionally after the new write (since we always want to write the response even without a flow state).
   - **Critical**: the dual-write block must be placed OUTSIDE the `if flow_state:` block, so it runs even when `flow_state is None`. The `flow_state_id` column is nullable for exactly this reason.
   - Also ensure `commit_needed = True` is set after `self.db.add(flow_response)`.

5. Verify:
   ```bash
   cd backend-hormonia && python -c "from app.models.patient_flow_response import PatientFlowResponse; print('OK')"
   cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short
   ```

## Must-Haves

- [ ] Migration file with correct `down_revision = "m006_s02_t03_drop_users_firebase_residue"` and all specified columns/indexes
- [ ] `PatientFlowResponse` model importable with correct column definitions
- [ ] `process_patient_response()` writes to new table in the same transaction as `step_data` writes
- [ ] Dual-write works even when `flow_state is None` (with `flow_state_id=NULL`)
- [ ] All existing flow tests remain green (0 regressions)

## Verification

- `cd backend-hormonia && python -c "from app.models.patient_flow_response import PatientFlowResponse; print('OK')"` — prints OK
- `cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short` — all existing tests green

## Observability Impact

- Signals added/changed: every `process_patient_response` call now also creates a `patient_flow_responses` row — observable via SQL query
- How a future agent inspects this: `SELECT * FROM patient_flow_responses WHERE patient_id = ? ORDER BY responded_at DESC`
- Failure state exposed: if the DB write fails, the entire transaction (including `step_data` writes) rolls back — SQLAlchemy exception propagates through the existing error handler

## Inputs

- `backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py` — The file to modify. Key section: `process_patient_response()` method. The dual-write goes after the `state_data["last_response"]` block (~line 225) and before `reminder_result = None` (~line 230). The `await self.db.commit()` is near line 280 — the new write must happen before it.
- `backend-hormonia/app/models/flow.py` — Contains `PatientFlowState` model for reference. The new `PatientFlowResponse` follows the same `BaseModel` pattern.
- `backend-hormonia/app/models/base.py` — Contains `BaseModel` base class for the new model.
- Alembic head is `m006_s02_t03_drop_users_firebase_residue`

## Expected Output

- `backend-hormonia/alembic/versions/m007_s04_t02_patient_flow_responses.py` — New migration creating the `patient_flow_responses` table
- `backend-hormonia/app/models/patient_flow_response.py` — New SQLAlchemy model `PatientFlowResponse`
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py` — Modified to dual-write responses to the new table
