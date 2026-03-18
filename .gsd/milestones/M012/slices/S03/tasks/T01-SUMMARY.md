---
id: T01
parent: S03
milestone: M012
provides:
  - TypeScript interfaces matching backend patient_overrides.py Pydantic schemas
  - usePatientFlowOverrides React Query hook wrapping GET/PUT flow-overrides endpoints
key_files:
  - frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts
  - frontend-hormonia/src/features/patients/hooks/index.ts
key_decisions: []
patterns_established:
  - QUERY_KEY_PREFIX constant extracted for query key consistency across query and mutation
patterns_reused:
  - apiClient.get<T>/put<T,TData> pattern from core.ts
  - useQuery/useMutation/useQueryClient convention from useFlowEngine.ts
observability_surfaces:
  - React Query DevTools key ['patient-flow-overrides', patientId] for cache state inspection
  - Mutation errors propagate ApiError with status, userFriendlyMessage, retryable
duration: 5m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T01: TypeScript types and React Query hook for patient flow overrides

**Defined MergedDayItem, MergedDayListResponse, OverrideDayInput, OverrideDayUpdateRequest interfaces and usePatientFlowOverrides hook with GET query + PUT mutation, exported from barrel**

## What Happened

The hook file and barrel export were already present from the T02 implementation pass. Verified that all four interfaces exactly mirror the backend `patient_overrides.py` schemas: `MergedDayItem` has `source: 'global' | 'override'` and `editable: boolean`; `OverrideDayInput` correctly omits those read-only fields. The hook uses `useQuery` with `enabled: !!patientId`, `staleTime: 60_000`, and `useMutation` with `onSuccess` cache invalidation. The barrel re-exports the hook and three type interfaces (`MergedDayItem`, `MergedDayListResponse`, `OverrideDayInput`).

## Verification

- `tsc --noEmit` passed with zero errors (40.6s)
- `grep` confirmed `usePatientFlowOverrides` export in `index.ts` (lines 7, 12)
- `grep` confirmed `MergedDayItem` interface at line 16 of hook file
- `grep` confirmed `source: 'global' | 'override'` literal union type at line 23
- `grep` confirmed query key `patient-flow-overrides` at lines 7, 51
- Inspected `OverrideDayInput` — confirmed it has only `day_number`, `content`, `message_type`, `expects_response`, `skip` (no `source`/`editable`)

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend-hormonia && npx tsc --noEmit` | 0 | ✅ pass | 40.6s |
| 2 | `grep -n "usePatientFlowOverrides" frontend-hormonia/src/features/patients/hooks/index.ts` | 0 | ✅ pass | <1s |
| 3 | `grep -n "MergedDayItem" frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` | 0 | ✅ pass | <1s |
| 4 | `grep -n "source: 'global' | 'override'" ...usePatientFlowOverrides.ts` | 0 | ✅ pass | <1s |

## Diagnostics

- **React Query DevTools**: Query key `['patient-flow-overrides', patientId]` visible for cache state, staleness, fetch timing.
- **Mutation errors**: `saveOverrides` (from `mutateAsync`) rejects with `ApiError` carrying `status`, `userFriendlyMessage`, `retryable`. Downstream T02 editor component should surface these.
- **Cache invalidation**: On PUT success, the query key is invalidated via `queryClient.invalidateQueries`.
- **Static verification**: `tsc --noEmit` catches schema drift if backend changes field names/types.

## Deviations

None. The implementation was already in place from the T02 pass — T01 was a verification-only execution confirming all must-haves are met.

## Known Issues

None.

## Files Created/Modified

- `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` — 4 exported interfaces + usePatientFlowOverrides hook (already existed)
- `frontend-hormonia/src/features/patients/hooks/index.ts` — barrel re-export of hook + types (already existed)
