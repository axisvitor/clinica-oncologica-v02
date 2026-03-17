---
id: S01
parent: M010
milestone: M010
provides:
  - "GET /api/v2/physicians/patients — paginated, enriched with flow_phase, flow_current_day, flow_status, last_interaction, unacknowledged_alerts_count"
  - "Pydantic schemas: PhysicianPatientItem (8 fields), PhysicianPatientListResponse (paginated)"
  - "Frontend apiClient.physician.patients() + types"
  - "usePhysicianPatients() hook with debounced search, server-side filtering, pagination"
  - "PhysicianPatientTable component: 7 columns with patient flow context, alert badges, 1-click AI summary"
  - "PhysicianDashboard.tsx rewritten as patient-centric view (~300 lines, down from 727)"
requires: []
affects:
  - S02
  - S04
key_files:
  - backend-hormonia/app/api/v2/routers/physicians/patients.py
  - backend-hormonia/app/schemas/v2/physician_patients.py
  - backend-hormonia/app/api/v2/routers/physicians/__init__.py
  - frontend-hormonia/src/lib/api-client/physician.ts
  - frontend-hormonia/src/hooks/api/usePhysicianPatients.ts
  - frontend-hormonia/src/pages/PhysicianDashboard.tsx
  - frontend-hormonia/src/features/dashboard/components/physician/PhysicianPatientTable.tsx
key_decisions:
  - "D018: Dedicated /api/v2/physicians/patients endpoint (not enriching risk-assessments)"
  - "AI Insights/Analytics tabs removed from dashboard — moved to patient detail (S02)"
  - "PhysicianMetricsCards removed — patient list with alerts replaces aggregate risk cards"
  - "Latest flow state per patient via row_number() window function (handles multiple flow states)"
  - "Table ordered by unacknowledged alerts DESC then name ASC"
patterns_established:
  - "Backend: enriched list endpoint with subquery JOINs for related aggregate data"
  - "Frontend: usePhysicianPatients hook pattern with debounce + server-side filters"
  - "PhysicianPatientTable: shadcn Table with clinical context per row"
observability_surfaces:
  - "Endpoint logs on error"
  - "Frontend loading/error/empty states with explicit messaging"
drill_down_paths:
  - .gsd/milestones/M010/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M010/slices/S01/tasks/T02-SUMMARY.md
duration: ~27min (T01: 12min, T02: 15min)
verification_result: passed
completed_at: 2026-03-17
---

# S01: API enriquecida + Dashboard patient-centric

**Backend endpoint GET /api/v2/physicians/patients with JOINed flow data + PhysicianDashboard rewritten as patient-centric table with flow phase, day, alerts, and 1-click AI summary per patient**

## What Happened

**T01** created the backend endpoint at `app/api/v2/routers/physicians/patients.py` — an async FastAPI route that queries Patient LEFT JOIN latest PatientFlowState (via row_number window function partitioned by patient_id, ordered by started_at DESC) LEFT JOIN FlowTemplateVersion → FlowKind (for flow phase) + subquery counting unacknowledged alerts. Filters: search (ILIKE name), flow_phase (kind_key), flow_status, doctor_id (auto from session, admin sees all). Pagination via page/size. Results ordered by alert count DESC then name ASC — patients needing attention surface first. Pydantic schemas in `physician_patients.py` with PhysicianPatientItem (8 fields) and PhysicianPatientListResponse.

**T02** extended `physician.ts` in apiClient with `patients()` method and types, created `usePhysicianPatients` hook with `useDebounce` (300ms) + server-side filtering + pagination, built `PhysicianPatientTable` component (shadcn Table, 7 columns: patient, phase, day, last contact, alerts, status, actions), and rewrote `PhysicianDashboard.tsx` from 727 lines of analytics-heavy content (risk cards + risk table + AI Insights/Analytics tabs) to ~300 lines of focused patient-centric view with search, phase filter, status filter, patient table, and preserved chat/export dialogs.

## Verification

- `ast.parse` clean on all 3 backend files ✓
- Schema imports and field inspection clean ✓
- `tsc --noEmit` — only pre-existing e2e config errors (no new errors) ✓
- `vite build` — built successfully in 1m 9s ✓
- DashboardPage.tsx (admin) unchanged — git diff empty ✓
- Route path: `/api/v2/physicians/patients` via prefix chain ✓

## Requirements Advanced

- R089 — PhysicianDashboard now shows patient-centric list with flow_phase, flow_current_day, last_interaction, unacknowledged_alerts_count per patient. Ready for validation after runtime proof.
- R091 — Backend endpoint delivers enriched patient list with flow data in single query. Ready for validation after runtime proof.
- R092 — Brain icon in actions column navigates to `?tab=ai-summary` in 1 click. Partially advanced — full validation needs S02 to make AI summary visible without tab navigation.
- R095 — DashboardPage.tsx (admin) confirmed unchanged.

## Deviations

- Route path is `/api/v2/physicians/patients` (plural) not `/api/v2/physician/patients` as in context doc — matching existing `physicians/` router prefix.
- Dropped `phone` field from response — LGPD encrypted, not useful in list view.
- AI Insights/Analytics tabs removed from dashboard — belong in patient detail (S02), not overview.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — NEW: endpoint
- `backend-hormonia/app/schemas/v2/physician_patients.py` — NEW: schemas
- `backend-hormonia/app/api/v2/routers/physicians/__init__.py` — Added patients router
- `frontend-hormonia/src/lib/api-client/physician.ts` — Extended with patients() + types
- `frontend-hormonia/src/hooks/api/usePhysicianPatients.ts` — NEW: hook
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — REWRITTEN
- `frontend-hormonia/src/features/dashboard/components/physician/PhysicianPatientTable.tsx` — NEW

## Forward Intelligence

### What the next slice should know
- The dashboard navigates to `/physician/patients/:id` on row click and to `/physician/patients/:id?tab=ai-summary` on Brain icon click.
- S02 should make the AI summary visible by default on the patient detail page (not hidden behind a tab), so the Brain icon 1-click actually shows the summary without further navigation.
- The `usePhysicianPatients` hook and `PhysicianPatientTable` are designed for desktop-first — S04 should add mobile responsive breakpoints.

### What's fragile
- The backend query uses row_number() window function for latest flow state — if a patient has many flow states, the window function runs on all of them. Not a problem with typical volumes but could slow down at scale.
- `formatRelativeTime()` in PhysicianPatientTable is a simple implementation — doesn't handle timezones.
