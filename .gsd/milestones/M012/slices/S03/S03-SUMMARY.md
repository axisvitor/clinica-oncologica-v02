---
id: S03
parent: M012
milestone: M012
provides:
  - PatientFlowOverrideEditor dialog component with source badges, editability gating, skip toggles, add-day
  - "Personalizar Fluxo" button wired into PatientDetailPage right sidebar
  - usePatientFlowOverrides React Query hook (GET query + PUT mutation) with full TypeScript types
  - Barrel re-export from features/patients/hooks/index.ts
requires:
  - slice: S01
    provides: GET/PUT /api/v2/patients/{patient_id}/flow-overrides endpoints, MergedDayItem schema with source and editable fields
affects:
  - S04
key_files:
  - frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts
  - frontend-hormonia/src/features/patients/hooks/index.ts
  - frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx
  - frontend-hormonia/src/pages/PatientDetailPage.tsx
key_decisions:
  - Global days promoted to override source when physician edits them — prevents unintended global mutations sent to PUT
patterns_established:
  - Override editor follows DayConfigEditor.tsx dialog pattern with Badge-based source annotation and disabled-prop gating
  - QUERY_KEY_PREFIX constant for React Query key consistency across query and mutation
patterns_reused:
  - apiClient.get<T>/put<T,TData> from core.ts
  - useQuery/useMutation/useQueryClient convention from useFlowEngine.ts
  - Dialog/DialogContent/DialogHeader/DialogFooter layout from DayConfigEditor.tsx
  - Badge variant mapping (secondary=Global, default=Personalizado, destructive=Pulado)
observability_surfaces:
  - React Query DevTools key ['patient-flow-overrides', patientId] for cache state, staleness, fetch timing
  - Network tab GET/PUT /api/v2/patients/{id}/flow-overrides for request/response inspection
  - Toast notifications on save success ("Personalização salva") and failure ("Erro ao salvar")
  - Mutation errors propagate ApiError with status, userFriendlyMessage, retryable
drill_down_paths:
  - .gsd/milestones/M012/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M012/slices/S03/tasks/T02-SUMMARY.md
duration: 20m
verification_result: passed
completed_at: 2026-03-17
---

# S03: Editor de override no PatientDetailPage

**PatientFlowOverrideEditor dialog with source badges, future-day gating, skip toggles, and add-day — wired into PatientDetailPage via "Personalizar Fluxo" button, with typed React Query hook for GET/PUT override endpoints**

## What Happened

T01 defined the TypeScript data layer: four interfaces (`MergedDayItem`, `MergedDayListResponse`, `OverrideDayInput`, `OverrideDayUpdateRequest`) mirroring the backend Pydantic schemas from S01, plus `usePatientFlowOverrides(patientId)` wrapping GET and PUT with React Query. The hook uses `enabled: !!patientId`, `staleTime: 60_000`, and cache invalidation on mutation success. Types and hook are re-exported from the patients hooks barrel.

T02 built the `PatientFlowOverrideEditor` dialog (~230 lines) following the existing `DayConfigEditor.tsx` pattern. Each day card displays a Badge indicating source (`Global` secondary, `Personalizado` default, `Pulado` destructive). Past days (`editable: false`) have all inputs disabled with `opacity-60` visual distinction. Future days support content editing via Textarea, message type via Select (question/motivation/reminder), expects_response via Checkbox, and skip via Switch. "Adicionar Dia" appends a new override day with auto-incremented day_number. The save handler filters to only `source === 'override'` days and strips `source`/`editable` before sending to PUT — preventing global days from being accidentally overwritten.

The editor was wired into `PatientDetailPage.tsx` with a `useState` for dialog visibility, a Settings2-icon button labeled "Personalizar Fluxo" in the right sidebar between FlowStatus and QuickActions, and conditional rendering of the editor dialog when `id` is present.

## Verification

| # | Check | Result | Duration |
|---|-------|--------|----------|
| 1 | `cd frontend-hormonia && npx tsc --noEmit` | ✅ zero errors | 35.3s |
| 2 | `cd frontend-hormonia && npx vite build` | ✅ 4744 modules, clean build | 80.1s |
| 3 | `usePatientFlowOverrides.ts` exists with 4 interfaces + hook | ✅ | — |
| 4 | `PatientFlowOverrideEditor.tsx` exists with badges, disabled gating, skip toggle | ✅ | — |
| 5 | `PatientDetailPage.tsx` imports editor + renders "Personalizar Fluxo" button | ✅ | — |
| 6 | Barrel `index.ts` re-exports hook + 3 type interfaces | ✅ | — |

## Requirements Advanced

- R108 — PatientDetailPage now has the "Personalizar Fluxo" button, the override editor dialog with full merged day list, badge visual (Global/Personalizado/Pulado), and future-only editing gating. All proof criteria met by `tsc --noEmit` + `vite build` green.

## Requirements Validated

- none (R108 advances to validated after S04 integrated verification confirms end-to-end behavior)

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

None. Implementation follows the slice plan exactly.

## Known Limitations

- The editor's `editable` gating relies on the `editable: boolean` field returned by the backend GET endpoint (which compares `day_number` to `current_flow_day`). If the backend field is missing or incorrect, the gating is wrong. This is an S01 contract dependency.
- The "Pulado" badge uses strikethrough styling only via the destructive Badge variant — no CSS `line-through` on the day content itself. Visual distinction is clear but could be enhanced.
- Toast notifications are the only error surface for save failures — no inline error display within the dialog.

## Follow-ups

- S04 must verify end-to-end: dialog opens → fetches merged data → edits persist via PUT → re-fetch shows updates. This is the integrated verification gap.

## Files Created/Modified

- `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` — new: 4 exported interfaces + React Query hook (GET query + PUT mutation)
- `frontend-hormonia/src/features/patients/hooks/index.ts` — modified: added barrel re-export for hook + 3 type interfaces
- `frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx` — new: ~230 line dialog component with source badges, editability gating, skip toggle, add-day
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` — modified: added Settings2 import, editor import, showOverrideEditor state, button in sidebar, dialog render (~15 lines added)

## Forward Intelligence

### What the next slice should know
- The frontend is fully wired to the S01 API endpoints. S04 can test the full loop: open dialog → see merged days → edit a future day → save → verify override persisted.
- The PUT payload only includes override-source days. S04 should verify that editing a global day promotes it to override in the request.

### What's fragile
- The `MergedDayItem` interface must stay in sync with the backend `MergedDayOverrideItemSchema` from `patient_overrides.py`. Any field rename or type change will break `tsc --noEmit`. This is the primary drift signal.
- The `editable` field computation is entirely server-side. If `current_flow_day` is wrong in the flow state, the wrong days become editable. S04 should verify this boundary.

### Authoritative diagnostics
- `tsc --noEmit` is the fastest signal for schema drift between backend and frontend. Run it first when debugging type mismatches.
- React Query DevTools key `['patient-flow-overrides', patientId]` shows whether the GET succeeded, the cache state, and whether invalidation fired after PUT.

### What assumptions changed
- No assumptions changed. The S01 API shape matched the plan exactly, and the DayConfigEditor pattern transferred cleanly to the override editor.
