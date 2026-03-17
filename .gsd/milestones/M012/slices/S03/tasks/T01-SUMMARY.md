---
id: T01
parent: S03
milestone: M012
provides:
  - TypeScript interfaces mirroring backend patient override schemas
  - React Query hook for GET/PUT patient flow overrides
key_files:
  - frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts
  - frontend-hormonia/src/features/patients/hooks/index.ts
key_decisions:
  - Kept query key as flat string prefix plus patientId for easy invalidation
patterns_established:
  - React Query hook with useQuery+useMutation in a single file, query key constant extracted for reuse
observability_surfaces:
  - React Query DevTools: query key ['patient-flow-overrides', patientId]
  - Network tab: GET/PUT /api/v2/patients/{id}/flow-overrides
  - Hook exposes error and isSaving for downstream UI error rendering
duration: 10m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T01: TypeScript types and React Query hook for patient flow overrides

**Added usePatientFlowOverrides hook with MergedDayItem/OverrideDayInput types and React Query GET/PUT wiring**

## What Happened

Created the data layer for the patient flow override editor. Defined four TypeScript interfaces (`MergedDayItem`, `MergedDayListResponse`, `OverrideDayInput`, `OverrideDayUpdateRequest`) that mirror the backend Pydantic schemas in `patient_overrides.py`. The hook wraps GET with `useQuery` (staleTime 60s, enabled guard) and PUT with `useMutation` (invalidates cache on success). All types are exported from the patients hooks barrel. `tsc --noEmit` passes with zero errors.

## Verification

- `npx tsc --noEmit` — zero errors, confirming all types are correct under strict mode
- `grep` confirmed barrel exports for hook and type re-exports
- File existence verified on disk

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npx tsc --noEmit` | 0 | ✅ pass | 38.8s |
| 2 | `ls usePatientFlowOverrides.ts` | 0 | ✅ pass | <1s |
| 3 | `grep usePatientFlowOverrides index.ts` | 0 | ✅ pass | <1s |
| 4 | `grep MergedDayItem usePatientFlowOverrides.ts` | 0 | ✅ pass | <1s |

### Slice-Level Checks (partial — T01 is intermediate)

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | `tsc --noEmit` | ✅ pass | Zero errors |
| 2 | `vite build` | ⏳ deferred | Will run after T02 adds component |
| 3 | `usePatientFlowOverrides.ts` exists | ✅ pass | — |
| 4 | `PatientFlowOverrideEditor.tsx` exists | ⏳ T02 | — |
| 5 | `PatientDetailPage` imports editor | ⏳ T02 | — |

## Diagnostics

- **React Query DevTools**: Look for `['patient-flow-overrides', <uuid>]` query key when the editor mounts (T02).
- **Network tab**: GET/PUT to `/api/v2/patients/{id}/flow-overrides` — inspect payloads for contract alignment.
- **Error surface**: `error` property on hook return exposes fetch/save failures; `isSaving` tracks mutation state.
- **Grep for consumers**: `grep -rn "patient-flow-overrides" frontend-hormonia/src/` lists all query key references.

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` — new: 4 interfaces + usePatientFlowOverrides hook
- `frontend-hormonia/src/features/patients/hooks/index.ts` — modified: added hook and type re-exports
- `.gsd/milestones/M012/slices/S03/S03-PLAN.md` — modified: added Observability section, marked T01 done
- `.gsd/milestones/M012/slices/S03/tasks/T01-PLAN.md` — modified: added Observability Impact section
