---
id: T02
parent: S01
milestone: M010
provides:
  - "apiClient.physician.patients() method calling GET /api/v2/physicians/patients"
  - "PhysicianPatient + PhysicianPatientListResponse types in physician.ts"
  - "usePhysicianPatients() hook with debounced search, server-side filter, pagination"
  - "PhysicianPatientTable component: 7 columns (name, phase, day, last contact, alerts, status, actions)"
  - "PhysicianDashboard.tsx rewritten as patient-centric view (was 727 lines analytics-heavy, now ~300 lines patient-focused)"
  - "Brain icon in actions column navigates to ?tab=ai-summary in 1 click"
requires:
  - task: T01
    provides: GET /api/v2/physicians/patients backend endpoint
affects: [S02, S04]
key_files:
  - frontend-hormonia/src/lib/api-client/physician.ts
  - frontend-hormonia/src/hooks/api/usePhysicianPatients.ts
  - frontend-hormonia/src/pages/PhysicianDashboard.tsx
  - frontend-hormonia/src/features/dashboard/components/physician/PhysicianPatientTable.tsx
key_decisions:
  - "Removed AI Insights/Analytics tabs from dashboard — will move to patient detail in S02"
  - "Removed PhysicianMetricsCards risk count cards — patient list with alerts replaces them"
  - "Kept PhysicianChatDialog and PhysicianExportDialog — useful features"
  - "formatRelativeTime() in table — Portuguese relative time for last interaction"
  - "Table ordered by alerts DESC, name ASC (matching backend default)"
patterns_established:
  - "usePhysicianPatients hook pattern: useQuery + useDebounce + filter params"
  - "PhysicianPatientTable: shadcn Table with Badge for phase/status, Tooltip for alerts"
drill_down_paths:
  - .gsd/milestones/M010/slices/S01/tasks/T02-PLAN.md
duration: 15min
verification_result: pass
completed_at: 2026-03-17
---

# T02: Frontend hook + apiClient + PhysicianDashboard rewrite

**Patient-centric PhysicianDashboard with flow phase, day, alerts per patient row — replacing analytics-heavy risk assessment view**

## What Happened

Extended `physician.ts` in apiClient with `patients()` method and types (`PhysicianPatient`, `PhysicianPatientListResponse`, `PhysicianPatientListParams`). Created `usePhysicianPatients` hook wrapping `useQuery` with `useDebounce` for search (300ms), server-side flow_phase and flow_status filtering, and pagination.

Built `PhysicianPatientTable` component using shadcn Table with 7 columns: patient name (+ treatment type), flow phase (Badge), current day (mono font), last interaction (relative time in Portuguese), unacknowledged alerts (destructive Badge with count), flow status (colored Badge), and actions (Brain icon for 1-click AI summary). Row click navigates to `/physician/patients/:id`. Pagination controls at bottom.

Rewrote `PhysicianDashboard.tsx` from 727 lines (risk assessment cards + risk table + AI Insights tab + AI Analytics tab) down to ~300 lines of focused patient-centric view: header with title + actions (Atualizar, Chat IA, Exportar), filter bar (search input + phase select + status select), PhysicianPatientTable, and loading/error/empty states. Preserved PhysicianChatDialog and PhysicianExportDialog.

## Deviations
- Removed AI Insights and Analytics tabs from dashboard — these per-patient features belong in the patient detail page (S02 scope), not the overview.
- Removed PhysicianMetricsCards (risk count summary cards) — the patient list with alert counts replaces the need for aggregate risk cards.
- PhysicianRiskTable is no longer imported — replaced by PhysicianPatientTable.

## Files Created/Modified
- `frontend-hormonia/src/lib/api-client/physician.ts` — Added types + patients() method
- `frontend-hormonia/src/hooks/api/usePhysicianPatients.ts` — NEW: hook with debounce + filters
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — REWRITTEN: patient-centric view
- `frontend-hormonia/src/features/dashboard/components/physician/PhysicianPatientTable.tsx` — NEW: table component
