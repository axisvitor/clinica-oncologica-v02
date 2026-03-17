---
id: T01
parent: S01
milestone: M010
provides:
  - "GET /api/v2/physicians/patients endpoint with enriched flow data per patient"
  - "PhysicianPatientItem schema: id, name, flow_phase, flow_current_day, flow_status, last_interaction, unacknowledged_alerts_count, treatment_type"
  - "PhysicianPatientListResponse schema: paginated items[] + total + page + size"
  - "Query: Patient LEFT JOIN latest PatientFlowState (row_number partition) + FlowTemplateVersion + FlowKind + alert counts"
  - "Filters: search (ILIKE name), flow_phase (kind_key), flow_status, doctor_id (auto from session)"
requires: []
affects: [S02]
key_files:
  - backend-hormonia/app/api/v2/routers/physicians/patients.py
  - backend-hormonia/app/schemas/v2/physician_patients.py
  - backend-hormonia/app/api/v2/routers/physicians/__init__.py
key_decisions:
  - "Route path: /api/v2/physicians/patients (plural, matching existing physicians/ prefix)"
  - "Latest flow state via row_number() window function partitioned by patient_id, ordered by started_at DESC"
  - "current_day extracted from step_data JSONB (current_flow_day key), fallback to current_step column"
  - "Ordering: unacknowledged alerts DESC then name ASC — patients needing attention surface first"
patterns_established:
  - "Enriched list endpoint pattern: main table + subquery JOINs for related aggregate data"
drill_down_paths:
  - .gsd/milestones/M010/slices/S01/tasks/T01-PLAN.md
duration: 12min
verification_result: pass
completed_at: 2026-03-17
---

# T01: Endpoint backend GET /api/v2/physicians/patients

**Async FastAPI endpoint returning paginated patient list with JOINed flow phase, current day, last interaction, and unacknowledged alert count per patient**

## What Happened

Created `app/api/v2/routers/physicians/patients.py` with a single GET endpoint that builds a query against Patient, left-joining the latest PatientFlowState per patient (via row_number window function over started_at DESC), then joining through FlowTemplateVersion → FlowKind to get the flow phase (kind_key), and a separate subquery counting unacknowledged alerts. The current flow day is extracted from step_data JSONB's `current_flow_day` key with fallback to `current_step`.

Filters: `search` (ILIKE on name), `flow_phase` (exact match on kind_key), `flow_status` (exact match on PatientFlowState.status). Doctor filtering is automatic from session — doctors see their own patients, admins see all.

Results are ordered by unacknowledged alert count DESC then name ASC, so patients needing attention surface first.

Created `app/schemas/v2/physician_patients.py` with `PhysicianPatientItem` (8 fields) and `PhysicianPatientListResponse` (paginated wrapper). Registered the router in `physicians/__init__.py`.

## Deviations
- Route path is `/api/v2/physicians/patients` (plural) not `/api/v2/physician/patients` (singular) as in the context doc — matching the existing `physicians/` prefix in the router hierarchy.
- Dropped `phone` field from response — phone is LGPD-encrypted in the database and not useful in the dashboard list view.

## Files Created/Modified
- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — NEW: endpoint with query + filters + pagination
- `backend-hormonia/app/schemas/v2/physician_patients.py` — NEW: Pydantic schemas
- `backend-hormonia/app/api/v2/routers/physicians/__init__.py` — Added patients_router include
