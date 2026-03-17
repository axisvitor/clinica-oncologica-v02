---
estimated_steps: 5
estimated_files: 2
---

# T01: TypeScript types and React Query hook for patient flow overrides

**Slice:** S03 — Editor de override no PatientDetailPage
**Milestone:** M012

## Description

Create the data layer for the patient flow override editor. Define TypeScript interfaces that mirror the backend Pydantic schemas (`MergedDayItem`, `MergedDayListResponse`, `OverrideDayInput`, `OverrideDayUpdateRequest`) and wrap the GET/PUT endpoints in a React Query hook. This unblocks T02 (the editor component) by providing typed data access.

The project uses `strict: true`, `noImplicitAny: true`, `noUncheckedIndexedAccess: true` in tsconfig — all types must be explicit with no `any` escapes.

## Steps

1. **Create `usePatientFlowOverrides.ts`** at `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts`. Define these interfaces matching the backend schemas in `backend-hormonia/app/schemas/v2/patient_overrides.py`:

   ```typescript
   // Response types (from GET)
   interface MergedDayItem {
     day_number: number
     content: string
     message_type: string
     expects_response: boolean
     skip: boolean
     source: 'global' | 'override'
     editable: boolean
   }

   interface MergedDayListResponse {
     patient_id: string
     flow_state_id: string
     current_flow_day: number
     days: MergedDayItem[]
   }

   // Request types (for PUT)
   interface OverrideDayInput {
     day_number: number
     content: string
     message_type: string
     expects_response: boolean
     skip: boolean
   }

   interface OverrideDayUpdateRequest {
     days: OverrideDayInput[]
   }
   ```

   Export all four interfaces.

2. **Create the hook** `usePatientFlowOverrides(patientId: string)` in the same file:

   - Import `useQuery`, `useMutation`, `useQueryClient` from `@tanstack/react-query`
   - Import `apiClient` from `@/lib/api-client`
   - GET: `useQuery` with `queryKey: ['patient-flow-overrides', patientId]`, `queryFn` calls `apiClient.get<MergedDayListResponse>(\`/api/v2/patients/${patientId}/flow-overrides\`)`, `enabled: !!patientId`, `staleTime: 60_000`
   - PUT mutation: `useMutation` calling `apiClient.put<MergedDayListResponse, OverrideDayUpdateRequest>(\`/api/v2/patients/${patientId}/flow-overrides\`, payload)`. On success, invalidate `['patient-flow-overrides', patientId]`.
   - Return `{ data, isLoading, error, saveOverrides: mutation.mutateAsync, isSaving: mutation.isPending }`

3. **Add export** to `frontend-hormonia/src/features/patients/hooks/index.ts`:
   ```typescript
   export { usePatientFlowOverrides } from './usePatientFlowOverrides'
   ```
   Also re-export the type interfaces: `export type { MergedDayItem, MergedDayListResponse, OverrideDayInput } from './usePatientFlowOverrides'`

4. **Verify types compile**: Run `cd frontend-hormonia && npx tsc --noEmit` — must pass with zero errors on the new file.

## Must-Haves

- [ ] `MergedDayItem` interface with `source: 'global' | 'override'` and `editable: boolean`
- [ ] `OverrideDayInput` interface WITHOUT `source` and `editable` (request-only fields)
- [ ] `usePatientFlowOverrides` hook using `useQuery` for GET and `useMutation` for PUT
- [ ] Query key includes patientId: `['patient-flow-overrides', patientId]`
- [ ] Hook exported from `features/patients/hooks/index.ts` barrel
- [ ] `tsc --noEmit` passes with zero errors

## Verification

- `cd frontend-hormonia && npx tsc --noEmit` — zero errors
- `grep -n "usePatientFlowOverrides" frontend-hormonia/src/features/patients/hooks/index.ts` — export exists
- `grep -n "MergedDayItem" frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` — type exists

## Observability Impact

- **New query key**: `['patient-flow-overrides', patientId]` appears in React Query DevTools when the hook mounts. Agents can inspect cache freshness, refetch count, and error state.
- **New network traffic**: GET and PUT to `/api/v2/patients/{id}/flow-overrides` — visible in browser Network tab. Failed requests surface as `error` on the hook return value.
- **Failure visibility**: If the API returns 4xx/5xx, `query.error` and `mutation.error` are set. Downstream components should render these; the hook does not swallow errors.
- **Inspection command**: `grep -rn "patient-flow-overrides" frontend-hormonia/src/` confirms all consumers of this query key.
- **No new logging added**: The hook relies on `apiClient`'s existing debug-level request logging. No additional console output.

## Inputs

- Backend schema reference: `backend-hormonia/app/schemas/v2/patient_overrides.py` — defines `MergedDayItem`, `MergedDayListResponse`, `OverrideDayInput`, `OverrideDayUpdateRequest`
- API client pattern: `frontend-hormonia/src/lib/api-client/core.ts` — `apiClient.get<T>(endpoint)` and `apiClient.put<T, TData>(endpoint, body)`
- React Query pattern: `frontend-hormonia/src/hooks/useFlowEngine.ts` — shows `useQuery`/`useMutation`/`useQueryClient` conventions
- Existing barrel: `frontend-hormonia/src/features/patients/hooks/index.ts` — currently exports `usePatientActions` and `usePatientTable`
- Import for apiClient: `import { apiClient } from '@/lib/api-client'`

## Expected Output

- `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` — new file with 4 interfaces + hook
- `frontend-hormonia/src/features/patients/hooks/index.ts` — modified to re-export hook and types
