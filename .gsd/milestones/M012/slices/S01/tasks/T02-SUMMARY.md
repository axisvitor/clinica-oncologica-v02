---
id: T02
parent: S01
milestone: M012
provides:
  - GET /{patient_id}/flow-overrides endpoint with global+override merge logic
  - PUT /{patient_id}/flow-overrides endpoint with future-only validation and cache invalidation
  - _build_merged_days helper reused by both endpoints
  - _get_active_flow_state helper for flow state lookup
key_files:
  - backend-hormonia/app/api/v2/routers/patients/flow_overrides.py
  - backend-hormonia/app/api/v2/routers/patients/__init__.py
key_decisions:
  - Extracted merge logic into _build_merged_days helper so PUT reuses GET's response building
  - DELETE+INSERT transaction pattern (not individual upserts) for atomic override replacement
  - Cache invalidation wrapped in try/except to not fail the request if Redis is down
patterns_established:
  - flow_overrides router follows flow_responses.py structural pattern (auth decorators, limiter, dependencies)
  - Merge algorithm: iterate global days → overlay overrides → append extra override-only days → sort
observability_surfaces:
  - Structured log on PUT: patient_id, flow_state_id, override_count
  - 404 with "No active flow state found for this patient"
  - 400 with "Cannot override day {N}: already sent (current day is {M})"
duration: 12m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T02: Build GET/PUT flow-overrides endpoints with merge logic and register router

**Added GET/PUT flow-overrides endpoints with merge logic (global template overlay + override annotation), future-only validation, Redis cache invalidation, and registered router before crud_router**

## What Happened

Created `flow_overrides.py` router with two helpers and two endpoints:

- `_get_active_flow_state`: queries most recent active PatientFlowState for a patient, raises 404 if none
- `_build_merged_days`: loads template via `_project_steps_to_day_configs`, overlays overrides by day_number, appends extra override-only days, annotates each day with `source` ("global"/"override") and `editable` (day_number > current_flow_day), sorts by day_number
- GET endpoint: auth-gated, rate-limited 30/min, returns MergedDayListResponse
- PUT endpoint: auth-gated, rate-limited 10/min, validates all days are future-only, DELETE+INSERT transaction, invalidates Redis cache pattern `flow_override:{state_id}:*`, returns updated merged view

Registered `flow_overrides_router` in `patients/__init__.py` before `crud_router` to avoid `/{patient_id}` catch-all shadowing.

## Verification

- AST parse on all 5 slice files: **PASS** (migration, model, schemas, router, __init__)
- `grep "flow_overrides" __init__.py` → import and include_router visible ✅
- `grep "source" patient_overrides.py` → `Literal["global", "override"]` ✅
- `grep "delete_pattern\|flow_override" flow_overrides.py` → cache invalidation present ✅
- `grep "_project_steps_to_day_configs" flow_overrides.py` → global template loading reused ✅
- `grep "down_revision"` → `m011_s01_patient_flow_states_index` ✅
- `grep "UniqueConstraint"` → `uq_pfo_state_day` on (patient_flow_state_id, day_number) ✅
- Merge logic coverage: global-only days ✅, overridden days ✅, extra override days ✅, skip field ✅, editable gating ✅
- Router registration order: flow_overrides_router before crud_router ✅

All slice-level verification checks pass (this is the final task of S01).

## Diagnostics

- Query overrides: `SELECT * FROM patient_flow_overrides WHERE patient_flow_state_id = :id`
- GET endpoint: `GET /api/v2/patients/{id}/flow-overrides` returns full merged state
- PUT structured log: `"Flow overrides saved"` with extra fields `patient_id`, `flow_state_id`, `override_count`
- Error shapes: 404 (no active flow state), 400 (past-day edit with specific day+current_day in message), 422 (schema validation)

## Deviations

None — implementation followed the task plan exactly.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py` — new router with GET/PUT endpoints, merge logic, helpers
- `backend-hormonia/app/api/v2/routers/patients/__init__.py` — added flow_overrides_router import and registration before crud_router
