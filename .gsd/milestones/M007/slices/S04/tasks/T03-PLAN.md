---
estimated_steps: 5
estimated_files: 3
---

# T03: Response query API endpoint and integration tests

**Slice:** S04 — Personalização IA e armazenamento de respostas
**Milestone:** M007

## Description

Build the `GET /api/v2/patients/{patient_id}/flow-responses` endpoint for querying structured patient responses by date range, and write integration-level tests proving the full write-through path from `process_patient_response()` to the new `patient_flow_responses` table and the query API.

## Steps

1. Create `backend-hormonia/app/api/v2/routers/patients/flow_responses.py`:
   - Define a new `APIRouter` with `prefix=""` (will be mounted under the patients prefix)
   - Pydantic response schema `FlowResponseItem`:
     - `id: UUID`
     - `flow_state_id: Optional[UUID]`
     - `day_number: Optional[int]`
     - `message_index: Optional[int]`
     - `response_text: str`
     - `responded_at: datetime`
     - `prompt_message_id: Optional[str]`
     - `response_message_id: Optional[str]`
   - Endpoint `GET /{patient_id}/flow-responses`:
     - Path param: `patient_id: UUID`
     - Query params: `start_date: Optional[date]`, `end_date: Optional[date]`
     - Auth: `require_doctor_or_admin` (same pattern as `crud.py`)
     - Query `patient_flow_responses` filtered by `patient_id`, optionally filtered by `responded_at` between `start_date` and `end_date`
     - Order by `responded_at ASC`
     - Return `List[FlowResponseItem]`

2. Register the new router in `backend-hormonia/app/api/v2/routers/patients/__init__.py`:
   - Check the current structure of `__init__.py`. If it uses `include_router` to compose sub-routers, add the flow_responses router the same way.
   - If `__init__.py` just re-exports, import and include the new router following the existing pattern.
   - The endpoint should be reachable at `GET /api/v2/patients/{patient_id}/flow-responses`.

3. Create `backend-hormonia/tests/unit/services/flow/test_patient_flow_responses.py`:
   - Use the same test infrastructure/shim pattern as existing flow tests.
   - Test the dual-write: mock the DB session, call `process_patient_response()`, verify `db.add()` was called with a `PatientFlowResponse` instance with correct attributes (`patient_id`, `day_number`, `message_index`, `response_text`, `responded_at`).
   - Test dual-write without flow state: set `flow_state=None` scenario, verify `PatientFlowResponse` is still created with `flow_state_id=None`.
   - Test the API endpoint schema: verify `FlowResponseItem` serializes correctly.
   - Test date filtering logic: verify the SQLAlchemy query applies `start_date` and `end_date` filters correctly.
   - Test empty results: verify API returns empty list when no responses exist.

4. Run all tests and verify 0 regressions:
   ```bash
   cd backend-hormonia && python -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v
   cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short
   ```

5. Final verification — ensure the entire flow test suite is green:
   ```bash
   cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short
   ```

## Must-Haves

- [ ] `GET /api/v2/patients/{patient_id}/flow-responses` endpoint with date-range filtering
- [ ] Endpoint requires `doctor_or_admin` authorization
- [ ] Response schema includes `id`, `flow_state_id`, `day_number`, `message_index`, `response_text`, `responded_at`
- [ ] Integration test proves dual-write from `process_patient_response()` creates `PatientFlowResponse` with correct attributes
- [ ] Test proves dual-write works when `flow_state is None`
- [ ] All existing flow tests remain green (0 regressions)

## Verification

- `cd backend-hormonia && python -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v` — 5+ tests green
- `cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short` — all green, 0 regressions

## Observability Impact

- Signals added/changed: new API endpoint `GET /api/v2/patients/{patient_id}/flow-responses` with standard FastAPI request logging
- How a future agent inspects this: `curl /api/v2/patients/{id}/flow-responses?start_date=2026-03-01&end_date=2026-03-31` returns structured JSON
- Failure state exposed: 404 if patient not found, 403 if not authorized, empty array if no responses

## Inputs

- `backend-hormonia/app/models/patient_flow_response.py` — The model created in T02. Import `PatientFlowResponse` for queries.
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py` — Modified in T02 to dual-write. Tests verify the `db.add(PatientFlowResponse(...))` call happens.
- `backend-hormonia/app/api/v2/routers/patients/crud.py` — Existing patient CRUD router. Follow its auth pattern (`require_doctor_or_admin`), import conventions, and router structure.
- `backend-hormonia/app/api/v2/routers/patients/__init__.py` — Router composition file. Add the new flow_responses router here.
- `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py` — Reference for test shim pattern and mock setup.

## Expected Output

- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py` — New router with `GET /{patient_id}/flow-responses` endpoint
- `backend-hormonia/app/api/v2/routers/patients/__init__.py` — Modified to include the new router
- `backend-hormonia/tests/unit/services/flow/test_patient_flow_responses.py` — New test file with 5+ integration-level tests proving dual-write and API query paths
