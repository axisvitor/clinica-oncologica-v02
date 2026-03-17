---
id: S01
parent: M012
milestone: M012
provides:
  - Alembic migration m012_s01_patient_flow_overrides (table + FK + UNIQUE + index)
  - PatientFlowOverride SQLAlchemy model in app/models/flow.py
  - Pydantic request/response schemas in app/schemas/v2/patient_overrides.py
  - GET /api/v2/patients/{patient_id}/flow-overrides returning merged day list with source/editable
  - PUT /api/v2/patients/{patient_id}/flow-overrides with future-only validation + Redis cache invalidation
requires:
  - slice: none
    provides: first slice — no dependencies
affects:
  - S02 (consumes PatientFlowOverride model + table for pipeline injection)
  - S03 (consumes GET/PUT API endpoints for frontend editor)
  - S04 (consumes all of the above for integrated verification)
key_files:
  - backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py
  - backend-hormonia/app/models/flow.py
  - backend-hormonia/app/schemas/v2/patient_overrides.py
  - backend-hormonia/app/api/v2/routers/patients/flow_overrides.py
  - backend-hormonia/app/api/v2/routers/patients/__init__.py
key_decisions:
  - D021: Dedicated patient_flow_overrides table (FK to patient_flow_states) instead of JSONB inside step_data
  - D022: Overrides are fixed — global template changes do not overwrite existing per-patient overrides
  - Merge logic extracted into _build_merged_days helper reused by both GET and PUT response building
  - DELETE+INSERT transaction pattern for atomic override replacement (not individual upserts)
  - Cache invalidation wrapped in try/except — Redis failure does not fail the PUT request
patterns_established:
  - Override model follows BaseModel pattern (inherits id/created_at/updated_at) with backref relationship to PatientFlowState
  - Merge algorithm: iterate global days → overlay overrides by day_number → append extra override-only days → sort by day_number
  - Source annotation per day: "global" (template-inherited) or "override" (patient-specific)
  - Editability gating: day_number > current_flow_day determines whether physician can modify
  - flow_overrides_router registered before crud_router to avoid /{patient_id} catch-all shadowing
observability_surfaces:
  - Structured log on PUT: "Flow overrides saved" with patient_id, flow_state_id, override_count
  - 404 "No active flow state found for this patient" — missing or inactive flow state
  - 400 "Cannot override day N: already sent (current day is M)" — past-day edit attempt
  - 422 on Pydantic schema validation failure
  - patient_flow_overrides table queryable by patient_flow_state_id
  - PatientFlowState.overrides backref for REPL/debug inspection
  - UNIQUE constraint uq_pfo_state_day surfaces as IntegrityError on duplicate day override
drill_down_paths:
  - .gsd/milestones/M012/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M012/slices/S01/tasks/T02-SUMMARY.md
duration: 22m
verification_result: passed
completed_at: 2026-03-17
---

# S01: Tabela de overrides + API de merge

**Persisted per-patient flow day overrides in dedicated table with GET/PUT endpoints that merge global template days with patient-specific overrides, annotating each day with source and editability**

## What Happened

Built the complete data layer and API for per-patient flow day overrides in two tasks:

**T01 (data layer):** Created Alembic migration `m012_s01_patient_flow_overrides` chained from `m011_s01_patient_flow_states_index`. The table has UUID PK, FK to `patient_flow_states` with ON DELETE CASCADE, UNIQUE constraint `uq_pfo_state_day` on (patient_flow_state_id, day_number), and index on patient_flow_state_id. Added `PatientFlowOverride` model to `flow.py` using `BaseModel` (inherits id/created_at/updated_at) with columns: patient_flow_state_id, day_number, content, message_type, expects_response, skip, created_by. Backref `overrides` on PatientFlowState. Pydantic schemas in `patient_overrides.py`: `OverrideDayInput` (request), `OverrideDayUpdateRequest` (bulk), `MergedDayItem` (response with `source: Literal["global", "override"]` and `editable: bool`), `MergedDayListResponse`.

**T02 (API endpoints):** Created `flow_overrides.py` router with two helpers and two endpoints. `_get_active_flow_state` queries the most recent active PatientFlowState, raising 404 if none. `_build_merged_days` loads the global template via `_project_steps_to_day_configs`, overlays overrides by day_number, appends extra override-only days, annotates each with source/editable, and sorts. GET endpoint is auth-gated (30/min rate limit). PUT validates future-only editability (day_number > current_flow_day), replaces overrides via DELETE+INSERT in a single transaction, invalidates Redis cache pattern `flow_override:{state_id}:*` (failure-tolerant), and returns the updated merged view. Router registered in `patients/__init__.py` before `crud_router` to prevent path shadowing.

## Verification

- `ast.parse` PASS on all 5 files (migration, model, schemas, router, __init__)
- `grep down_revision` → `m011_s01_patient_flow_states_index` ✓
- UniqueConstraint `uq_pfo_state_day` on (patient_flow_state_id, day_number) in both model and migration ✓
- `source: Literal["global", "override"]` and `editable: bool` in response schema ✓
- `_project_steps_to_day_configs` reused for global template loading ✓
- `delete_pattern(f"flow_override:{flow_state.id}:*")` for Redis cache invalidation ✓
- `flow_overrides_router` registered before `crud_router` in __init__.py ✓
- Structured logging on PUT with patient_id, flow_state_id, override_count ✓
- Error shapes: 404 (no active flow state), 400 (past-day edit with day/current_day), 422 (validation) ✓

## Requirements Advanced

- R104 — `patient_flow_overrides` table created with content, message_type, expects_response, skip, FK to patient_flow_states. Data layer complete.
- R105 — GET returns merged global+override day list with `source` indicator. PUT saves overrides. Full API contract delivered.
- R109 — Override immutability achieved by design: overrides live in separate table, merge happens at read-time. Global template changes don't touch overrides.
- R064 — Foundation laid: per-patient flow customization now has persistence and API. Awaits S02 (pipeline injection) and S03 (frontend editor) to be fully usable.

## Requirements Validated

- none — R104, R105, R109 need runtime integration (S02 pipeline + S04 verification) before moving to validated

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

None — implementation followed the slice plan exactly.

## Known Limitations

- No runtime proof yet — endpoints are syntactically correct and structurally sound but haven't been hit by a real request. S04 handles this.
- Cache invalidation pattern `flow_override:{state_id}:*` is defined but S02 must implement the cache read path.
- Override editability gate uses `current_flow_day` from step_data — if step_data is missing or malformed, current_flow_day defaults to 0 (all days editable).

## Follow-ups

- S02 must implement the cache read path in `_get_day_config` using the `flow_override:{state_id}:days` key pattern.
- S02 must handle the `skip=true` override flag in the daily processing pipeline.
- S03 consumes the GET/PUT endpoints directly — no further backend changes needed for the frontend editor.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py` — Alembic migration creating patient_flow_overrides table
- `backend-hormonia/app/models/flow.py` — added PatientFlowOverride model with FK, UNIQUE, backref
- `backend-hormonia/app/schemas/v2/patient_overrides.py` — Pydantic schemas for override request/response
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py` — GET/PUT endpoints with merge logic
- `backend-hormonia/app/api/v2/routers/patients/__init__.py` — registered flow_overrides_router before crud_router

## Forward Intelligence

### What the next slice should know
- The merge algorithm in `_build_merged_days` iterates global template days first, overlays matching overrides, then appends override-only days (days that don't exist in the template). S02 should follow the same priority: check override table first, fall back to global template.
- Cache key pattern is `flow_override:{patient_flow_state_id}:*` — S02's read path should use `flow_override:{state_id}:days` to store the per-patient override dict and check it before querying the DB.
- The PUT endpoint already invalidates the cache on save. S02 doesn't need to add invalidation — just the read/populate path.

### What's fragile
- `_project_steps_to_day_configs` is imported from `flow_templates.py` — it was designed for the template editor API and makes assumptions about the step structure. If that function changes shape, the merge logic breaks.
- `current_flow_day` read from `step_data.get("current_flow_day", 0)` — defaults to 0 if missing, making all days editable. This is safe but could surprise operators debugging a patient with missing step_data.

### Authoritative diagnostics
- `SELECT * FROM patient_flow_overrides WHERE patient_flow_state_id = :id ORDER BY day_number` — canonical query to see all overrides for a patient
- `GET /api/v2/patients/{id}/flow-overrides` — returns the full merged state; trustworthy because it uses the same merge algorithm that PUT validates against

### What assumptions changed
- No assumptions changed. The plan's boundary map (S01→S02, S01→S03) held exactly.
