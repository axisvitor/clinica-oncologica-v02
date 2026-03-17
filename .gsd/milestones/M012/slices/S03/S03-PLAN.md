# S03: Editor de override no PatientDetailPage

**Goal:** Physician can open a "Personalizar Fluxo" dialog from PatientDetailPage to view, edit, skip, and add flow days per patient — with visual badges distinguishing global vs. custom days and read-only gating on past days.
**Demo:** PatientDetailPage shows "Personalizar Fluxo" button in the right sidebar. Clicking opens a dialog with the full merged day list from GET `/api/v2/patients/{id}/flow-overrides`. Each day shows a "Global"/"Personalizado" badge. Past days (editable=false) have all inputs disabled. Future days can be edited (content, message_type, expects_response, skip). New days can be added. Save sends overrides via PUT. `tsc --noEmit` and `vite build` pass green.

## Must-Haves

- `usePatientFlowOverrides(patientId)` React Query hook wrapping GET/PUT with proper types matching backend schemas
- `PatientFlowOverrideEditor` dialog component with source badges (global/custom), editable gating, skip toggle, add day
- "Personalizar Fluxo" button in PatientDetailPage right sidebar (same area as FlowStatus/QuickActions)
- PUT payload filters to only override/modified days with correct field subset (no `source`/`editable` in request)
- Query invalidation on save: `['patient-flow-overrides', patientId]`
- `tsc --noEmit` zero errors
- `vite build` clean build

## Proof Level

- This slice proves: contract (static type safety + build green)
- Real runtime required: no (S04 handles runtime integration)
- Human/UAT required: no

## Verification

- `cd frontend-hormonia && npx tsc --noEmit` — zero errors
- `cd frontend-hormonia && npx vite build` — clean build, no errors
- New files parse: `usePatientFlowOverrides.ts`, `PatientFlowOverrideEditor.tsx` exist and are imported
- `PatientDetailPage.tsx` imports and renders the editor dialog

## Observability / Diagnostics

- **React Query DevTools**: Query key `['patient-flow-overrides', patientId]` visible in DevTools panel — inspect cache state, stale/fresh status, and fetch timing.
- **Network tab**: GET `/api/v2/patients/{id}/flow-overrides` and PUT same endpoint visible in browser Network tab with request/response payloads for debugging contract mismatches.
- **Mutation error surface**: `useMutation` surfaces `error` on the returned object; the editor component should display save failures to the user via toast or inline error.
- **Console logging**: `apiClient` already logs request/response at debug level; override requests will appear alongside existing API traffic.
- **Build-time signals**: `tsc --noEmit` and `vite build` catch type regressions immediately — any interface drift from backend schema changes surfaces as compile errors.
- **Redaction**: No PHI in query keys (only `patientId` UUID). Day content may contain clinical text — ensure it is not logged to console in production.

## Integration Closure

- Upstream surfaces consumed: GET/PUT `/api/v2/patients/{patient_id}/flow-overrides` from S01, `apiClient.get<T>()`/`apiClient.put<T>()` from `@/lib/api-client`, `MergedDayItem`/`MergedDayListResponse` schema shape from `patient_overrides.py`
- New wiring introduced in this slice: "Personalizar Fluxo" button in PatientDetailPage opens editor dialog; hook re-exported from `features/patients/hooks/index.ts`
- What remains before the milestone is truly usable end-to-end: S04 (integrated verification)

## Tasks

- [x] **T01: TypeScript types and React Query hook for patient flow overrides** `est:25m`
  - Why: Data layer must exist before the editor component can consume it. Defines TS interfaces matching the backend Pydantic schemas and wraps GET/PUT in React Query hooks.
  - Files: `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts`, `frontend-hormonia/src/features/patients/hooks/index.ts`
  - Do: Define `MergedDayItem`, `MergedDayListResponse`, `OverrideDayInput`, `OverrideDayUpdateRequest` interfaces matching backend schemas. Create `usePatientFlowOverrides(patientId)` with `useQuery` for GET and `useMutation` for PUT. Query key `['patient-flow-overrides', patientId]`. Invalidate on mutation success. Re-export from hooks barrel.
  - Verify: `cd frontend-hormonia && npx tsc --noEmit` passes with the new file
  - Done when: Hook file exists with full types, compiles without errors, exported from barrel

- [ ] **T02: PatientFlowOverrideEditor component + PatientDetailPage integration + build proof** `est:45m`
  - Why: This is the user-facing deliverable — the editor dialog and its wiring into the page. Covers R108 completely: button, badge, future-only editing, skip toggle, add day.
  - Files: `frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx`, `frontend-hormonia/src/pages/PatientDetailPage.tsx`
  - Do: Build editor dialog following `DayConfigEditor.tsx` pattern. Source badges via Badge component (secondary="Global", default="Personalizado"). Editable gating on all inputs via `disabled={!day.editable}`. Skip toggle via Switch. Add day button. Save filters to OverrideDayInput fields only. Wire into PatientDetailPage with useState for dialog open. Run `tsc --noEmit` + `vite build`.
  - Verify: `cd frontend-hormonia && npx tsc --noEmit && npx vite build` both green
  - Done when: Editor renders in PatientDetailPage, badges visible, past days disabled, both build checks green

## Files Likely Touched

- `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` (new)
- `frontend-hormonia/src/features/patients/hooks/index.ts` (modified — add export)
- `frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx` (new)
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` (modified — add button + dialog)
