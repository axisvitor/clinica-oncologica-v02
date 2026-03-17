# S03 — Research

**Date:** 2026-03-17

## Summary

S03 is a straightforward frontend slice: add a "Personalizar Fluxo" button to `PatientDetailPage`, create a `PatientFlowOverrideEditor` dialog component, and wire it to the S01 GET/PUT `/api/v2/patients/{patient_id}/flow-overrides` endpoints via a React Query hook. All visual patterns (Dialog editor, Badge, day card layout) already exist in `DayConfigEditor.tsx` (243 lines). The API contract from S01 returns each day annotated with `source: "global" | "override"` and `editable: bool`, so the frontend just renders what the backend provides — no client-side merge logic needed.

The primary adaptation from `DayConfigEditor` is: (1) show a source badge per day (global vs. custom), (2) respect `editable` flag to make past days read-only, (3) add a skip toggle per day, and (4) use React Query (`useQuery`/`useMutation`) instead of the imperative `useTemplates` hook pattern.

## Recommendation

Build in three sequential tasks: (T01) TypeScript types + React Query hook, (T02) `PatientFlowOverrideEditor` dialog component, (T03) integrate into `PatientDetailPage` + verify `tsc --noEmit` + `vite build`. T01 is a pure data layer with no UI dependencies. T02 is the bulk of the work but follows the `DayConfigEditor` pattern closely. T03 is wiring + green build proof.

## Implementation Landscape

### Key Files

- `frontend-hormonia/src/pages/PatientDetailPage.tsx` (~190 lines) — Entry point. Add "Personalizar Fluxo" button in the right sidebar area (near `FlowStatus` and `QuickActions`). Button opens the override editor dialog. Needs `useState` for dialog open state and the patient ID is already available via `useParams`.
- `frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx` (~243 lines) — Reference implementation. Copy the day-card layout pattern (border rounded-lg, Textarea, Select for message_type, Checkbox for expects_response). Adapt for: source badge, editable gating, skip toggle. Do NOT modify this file.
- `frontend-hormonia/src/features/patients/hooks/index.ts` — Re-exports patient hooks. Add `usePatientFlowOverrides` export here.
- `frontend-hormonia/src/hooks/useFlowEngine.ts` — Shows the established React Query pattern: `useQuery` with `queryKey`, `staleTime`, `enabled`. Follow same convention for the override hook.
- `frontend-hormonia/src/lib/api-client/core.ts` — `apiClient.get<T>(endpoint)` and `apiClient.put<T>(endpoint, body)` are the primitives for API calls.
- `frontend-hormonia/src/components/ui/badge.tsx` — Existing Badge component with variants: default, secondary, destructive, outline. Use for global/override source annotation.
- `frontend-hormonia/src/components/ui/switch.tsx` — Existing Switch component. Use for the skip toggle on each day.

### New Files to Create

- `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` — React Query hook wrapping GET/PUT. Types for `MergedDayItem` and `MergedDayListResponse` defined here (matching backend Pydantic schemas from `patient_overrides.py`).
- `frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx` — Dialog component. Props: `open`, `onOpenChange`, `patientId`. Internally fetches via the hook, renders day list with source badges and editability, saves via PUT mutation.

### Build Order

1. **T01: Types + Hook** — Define TS interfaces matching `MergedDayItem` and `MergedDayListResponse` from the backend. Create `usePatientFlowOverrides(patientId)` returning `{ data, isLoading, saveOverrides }` using `useQuery` for GET and `useMutation` for PUT. Export from `features/patients/hooks/index.ts`. This unblocks T02 immediately.

2. **T02: PatientFlowOverrideEditor component** — Dialog component consuming the hook. Day card layout adapted from DayConfigEditor: source badge (Badge component — "Global" secondary variant, "Personalizado" default/colored variant), content Textarea (disabled when `!editable`), message_type Select (disabled when `!editable`), expects_response Checkbox (disabled when `!editable`), skip Switch (disabled when `!editable`). "Adicionar Dia" button for extra days (new days are always source=override, editable=true). Save sends only modified/added days (those with `source === "override"` or user-changed) via PUT. This is the bulk of the slice.

3. **T03: Integration + Build proof** — Import editor into PatientDetailPage. Add "Personalizar Fluxo" button in the right sidebar (same area as FlowStatus/QuickActions). Wire `useState` for dialog open/close. Run `tsc --noEmit` and `vite build` — both must pass green.

### Verification Approach

- `cd frontend-hormonia && npx tsc --noEmit` — zero type errors
- `cd frontend-hormonia && npx vite build` — clean build with no errors
- Manual verification: new files parse correctly, imports resolve, no circular dependencies
- Badge visual: global days show `secondary` variant, override days show `default` (colored) variant, skipped days have visual distinction (strikethrough or muted + skip badge)
- Past days (editable=false) have all inputs disabled — Textarea, Select, Checkbox, Switch all receive `disabled` prop

## Constraints

- `tsconfig.json` has `strict: true`, `noImplicitAny: true`, `noUncheckedIndexedAccess: true` — all types must be explicit, no `any` escapes
- API calls must use `apiClient.get<T>()` / `apiClient.put<T>()` from `@/lib/api-client` — this is the established pattern throughout the codebase
- The PUT endpoint only accepts future-day overrides (day_number > current_flow_day). Backend returns 400 for past days, but the frontend should prevent this by disabling editing on non-editable days (defense in depth)
- React Query `queryKey` must include `patientId` for proper cache isolation: `['patient-flow-overrides', patientId]`
- The override editor must NOT modify `DayConfigEditor.tsx` — it's a separate component for a different purpose (template-level vs. patient-level editing)

## Common Pitfalls

- **PUT payload shape mismatch** — The PUT endpoint expects `{ days: OverrideDayInput[] }` where each day has `day_number`, `content`, `message_type`, `expects_response`, `skip`. The GET response has additional fields (`source`, `editable`) that must NOT be sent back in the PUT body. Filter to only send override/modified days with the correct subset of fields.
- **Adding extra days** — When the physician adds a day that doesn't exist in the global template, the day_number must not collide with existing days. Use a simple numeric input or auto-increment from the max existing day_number + 1.
- **Query invalidation on save** — After a successful PUT, invalidate `['patient-flow-overrides', patientId]` so the GET refetches the merged view. Also invalidate `['flow-state', patientId]` since the flow behavior changes.
