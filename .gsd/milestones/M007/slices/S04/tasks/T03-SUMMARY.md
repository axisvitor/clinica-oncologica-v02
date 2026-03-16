---
id: T03
parent: S04
milestone: M007
provides:
  - GET /api/v2/patients/{patient_id}/flow-responses endpoint with date-range filtering
  - FlowResponseItem Pydantic schema for structured response serialization
  - 14 integration-level tests proving dual-write, schema, filtering, and ordering
key_files:
  - backend-hormonia/app/api/v2/routers/patients/flow_responses.py
  - backend-hormonia/app/api/v2/routers/patients/__init__.py
  - backend-hormonia/tests/unit/services/flow/test_patient_flow_responses.py
key_decisions:
  - Mounted flow_responses_router before crud_router in __init__.py to avoid /{patient_id} path shadowing
  - Used datetime.combine with time.min/time.max for inclusive date-range filtering
patterns_established:
  - FlowResponseItem Pydantic schema with from_attributes=True for ORM-to-API serialization
observability_surfaces:
  - GET /api/v2/patients/{id}/flow-responses?start_date=...&end_date=... returns structured JSON
  - 404 if patient not found, 403 if not authorized, empty array if no responses
duration: 12m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T03: Response query API endpoint and integration tests

**Built GET /api/v2/patients/{patient_id}/flow-responses endpoint with date-range filtering and 14 integration tests proving dual-write, schema serialization, date filtering, and ordering**

## What Happened

1. Created `flow_responses.py` router with:
   - `FlowResponseItem` Pydantic response schema (id, flow_state_id, day_number, message_index, response_text, responded_at, prompt/response_message_id)
   - `GET /{patient_id}/flow-responses` endpoint with `start_date`/`end_date` optional query params
   - `@require_doctor_or_admin()` auth decorator matching existing patient endpoints
   - Patient existence check (404 if not found)
   - SQLAlchemy async query with conditional date filtering and ASC ordering

2. Registered `flow_responses_router` in `__init__.py` — placed before `crud_router` to prevent the `/{patient_id}` catch-all from shadowing `/{patient_id}/flow-responses`.

3. Created `test_patient_flow_responses.py` with 14 tests across 5 test classes:
   - **TestFlowResponseItemSchema** (3 tests): full serialization, nullable fields, JSON round-trip
   - **TestDualWrite** (4 tests): PatientFlowResponse creation with/without flow_state, db.add() verification for both paths
   - **TestDateFiltering** (4 tests): no filter, start_date, end_date, combined range
   - **TestEmptyResults** (2 tests): empty set, filter-excludes-all
   - **TestResponseOrdering** (1 test): ascending responded_at sort

## Verification

- `python -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v` — **14 passed**
- `python -m pytest tests/unit/services/flow/ -v --tb=short` — **154 passed, 4 skipped, 1 pre-existing failure** (test_split_files_under_500_lines for sequencing.py at 521 lines — not introduced by T03)
- Slice diagnostic checks all pass:
  - Grounding rejects hallucinated content: 7 passed
  - NULL flow_state_id instantiation: OK
  - Model import: OK

## Diagnostics

- **Query responses**: `curl /api/v2/patients/{id}/flow-responses?start_date=2026-03-01&end_date=2026-03-31`
- **Failure states**: 404 if patient not found, 403 if not doctor/admin, empty `[]` if no responses in range
- **Date filtering**: uses `datetime.combine(date, time.min)` / `datetime.combine(date, time.max)` for inclusive day boundaries

## Deviations

None.

## Known Issues

- Pre-existing `test_split_files_under_500_lines` failure (sequencing.py 521 > 500 lines) — not introduced by this task.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py` — New router with GET endpoint and FlowResponseItem schema
- `backend-hormonia/app/api/v2/routers/patients/__init__.py` — Added flow_responses_router inclusion
- `backend-hormonia/tests/unit/services/flow/test_patient_flow_responses.py` — 14 integration-level tests
- `.gsd/milestones/M007/slices/S04/S04-PLAN.md` — Marked T03 as [x], added diagnostic failure-path check
