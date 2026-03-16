# S04: Personalização IA e armazenamento de respostas

**Goal:** The AI personalization pipeline has proven grounding calibration, and patient free-text responses are persisted in a dedicated structured table with full flow context (day, message, timestamp) and queryable via API.

**Demo:** Unit tests prove grounding thresholds catch hallucinated content and pass anchored reformulations. A patient response processed through `process_patient_response()` appears both in the existing `step_data` and in the new `patient_flow_responses` table. `GET /api/v2/patients/{patient_id}/flow-responses?start_date=...&end_date=...` returns the structured responses.

## Must-Haves

- Focused unit tests proving `_personalization_is_grounded()` correctly accepts anchored content and rejects hallucinated content at the threshold boundaries (similarity ≥ 0.6, overlap ≥ 0.2, no-keyword similarity ≥ 0.35)
- Tests proving `_select_template_variation()` is deterministic and `_lightly_rephrase_question()` adds wrapper only to questions
- Test proving `_personalize_message_ai` skips AI for `expects_response=False` messages
- Alembic migration creating `patient_flow_responses` table with `flow_state_id`, `day_number`, `message_index`, `response_text`, `responded_at`, plus FK to `patient_flow_states`
- `PatientFlowResponse` SQLAlchemy model importable and usable
- `process_patient_response()` dual-writes to the new table alongside existing `step_data` writes, in the same transaction
- `GET /api/v2/patients/{patient_id}/flow-responses` endpoint with date-range filtering
- All existing flow tests (36+) remain green with 0 regressions

## Proof Level

- This slice proves: contract + integration
- Real runtime required: no (all verification via pytest with mock DB)
- Human/UAT required: no

## Verification

```bash
# T01: Grounding calibration tests
cd backend-hormonia && python -m pytest tests/unit/services/flow/test_personalization_grounding.py -v

# T02: Model imports cleanly
cd backend-hormonia && python -c "from app.models.patient_flow_response import PatientFlowResponse; print('OK')"

# T03: Response API and integration tests
cd backend-hormonia && python -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v

# Slice-level: all flow tests green
cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short
```

- `tests/unit/services/flow/test_personalization_grounding.py` — all green (10+ tests)
- `tests/unit/services/flow/test_patient_flow_responses.py` — all green (5+ tests)
- All existing flow tests (36+) — 0 regressions

## Observability / Diagnostics

- Runtime signals: `process_patient_response` writes to `patient_flow_responses` alongside existing `step_data` — dual-write is in the same DB transaction
- Inspection surfaces: `SELECT * FROM patient_flow_responses WHERE flow_state_id = ? ORDER BY responded_at`, `GET /api/v2/patients/{id}/flow-responses`
- Failure visibility: if the new table write fails, the existing `step_data` write also fails (same transaction); standard SQLAlchemy error propagation
- Redaction constraints: `response_text` contains patient free-text — PII, follow existing data handling patterns

## Integration Closure

- Upstream surfaces consumed: `pending_response_context` in `step_data` from S01 (provides `flow_day`, `message_index` linking); `process_patient_response()` in `response_processing.py` (write path target)
- New wiring introduced in this slice: `PatientFlowResponse` model + migration; dual-write in `process_patient_response`; new API endpoint on patient router
- What remains before the milestone is truly usable end-to-end: S05 (quiz alerts → notifications) and S06 (monthly IA summary consuming `patient_flow_responses`)

## Tasks

- [ ] **T01: Prove grounding calibration with focused unit tests** `est:45m`
  - Why: R060 requires proving the existing IA personalization pipeline produces anchored reformulations. The grounding logic exists but has no dedicated tests. This task proves the thresholds work correctly without changing any production code.
  - Files: `backend-hormonia/tests/unit/services/flow/test_personalization_grounding.py` (new)
  - Do: Write focused unit tests for `_personalization_is_grounded()` (boundary cases at thresholds), `_select_template_variation()` (determinism, empty variations), `_lightly_rephrase_question()` (question vs non-question, existing prefix skip), and `_personalize_message_ai` (skips AI when `expects_response=False`). Use realistic Portuguese oncology content. Follow the existing shim pattern from `test_sequential_message_handler.py` for module isolation.
  - Verify: `cd backend-hormonia && python -m pytest tests/unit/services/flow/test_personalization_grounding.py -v` — 10+ tests green
  - Done when: All grounding threshold boundary cases tested, variation determinism proven, AI skip for non-response messages proven, 0 regressions in existing tests.

- [ ] **T02: Create patient_flow_responses table, model, and wire dual-write** `est:1h`
  - Why: R061 requires structured response storage. Currently responses live in `step_data` JSONB blobs — not queryable by day/period. This creates the dedicated table, model, and wires the write path into the existing `process_patient_response()` transaction.
  - Files: `backend-hormonia/alembic/versions/m007_s04_t02_patient_flow_responses.py` (new migration), `backend-hormonia/app/models/patient_flow_response.py` (new model), `backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py` (modify)
  - Do: (1) Create Alembic migration depending on `m006_s02_t03_drop_users_firebase_residue` for `patient_flow_responses` table with columns: `id` (UUID PK), `flow_state_id` (UUID FK nullable to `patient_flow_states.id`), `patient_id` (UUID FK not-null to `patients.id`), `day_number` (int nullable), `message_index` (int nullable), `response_text` (text not-null), `responded_at` (datetime with tz not-null), `prompt_message_id` (string nullable), `response_message_id` (string nullable), `created_at`, `updated_at`. (2) Create `PatientFlowResponse` SQLAlchemy model. (3) In `process_patient_response()`, add the new table write before the existing `await self.db.commit()`, using the same `flow_state`, `context`, and `response_text` data already available. Handle `flow_state is None` by writing with `flow_state_id=NULL`.
  - Verify: `cd backend-hormonia && python -c "from app.models.patient_flow_response import PatientFlowResponse; print('OK')"` succeeds; existing flow tests still pass
  - Done when: Migration file created, model importable, `process_patient_response` writes to new table in same transaction, existing tests green.

- [ ] **T03: Response query API endpoint and integration tests** `est:45m`
  - Why: R061 requires responses to be "consultáveis via API". This builds the query endpoint and proves the full write-through path with integration-level tests.
  - Files: `backend-hormonia/app/api/v2/routers/patients/flow_responses.py` (new router), `backend-hormonia/app/api/v2/routers/patients/__init__.py` (modify to include new router), `backend-hormonia/tests/unit/services/flow/test_patient_flow_responses.py` (new test file)
  - Do: (1) Create `GET /api/v2/patients/{patient_id}/flow-responses` with query params `start_date`, `end_date` (optional date filters), returning list of `{id, flow_state_id, day_number, message_index, response_text, responded_at, prompt_message_id}`. Require doctor_or_admin auth. (2) Write integration-level tests proving: write-through from `process_patient_response` populates the new table, API returns correct data filtered by date, empty results when no data, correct patient scoping.
  - Verify: `cd backend-hormonia && python -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v` — 5+ tests green; `cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short` — all green
  - Done when: API endpoint returns structured responses filtered by date, integration tests prove write-through and query paths, all existing tests green.

## Files Likely Touched

- `backend-hormonia/tests/unit/services/flow/test_personalization_grounding.py` (new)
- `backend-hormonia/alembic/versions/m007_s04_t02_patient_flow_responses.py` (new)
- `backend-hormonia/app/models/patient_flow_response.py` (new)
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py` (modify)
- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py` (new)
- `backend-hormonia/app/api/v2/routers/patients/__init__.py` (modify)
- `backend-hormonia/tests/unit/services/flow/test_patient_flow_responses.py` (new)
