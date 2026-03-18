# S03: Editor de override no PatientDetailPage — UAT

**Milestone:** M012
**Written:** 2026-03-17

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S03 is a frontend-only slice delivering static type safety and build proof. No backend runtime is needed — the component structure, wiring, badge rendering, and editability gating are all verifiable through code inspection and build checks. Runtime integration is deferred to S04.

## Preconditions

- Working directory: `.gsd/worktrees/M012`
- Node.js available with `npx` in PATH
- `frontend-hormonia/node_modules` installed (`npm install` completed previously)
- No backend server required (artifact-driven verification)

## Smoke Test

Run `cd frontend-hormonia && npx tsc --noEmit && npx vite build` — both must exit 0 with zero errors.

## Test Cases

### 1. TypeScript types match backend schema

1. Open `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts`
2. Verify `MergedDayItem` has fields: `day_number: number`, `content: string`, `message_type: string`, `expects_response: boolean`, `skip: boolean`, `source: 'global' | 'override'`, `editable: boolean`
3. Verify `OverrideDayInput` has fields: `day_number`, `content`, `message_type`, `expects_response`, `skip` — and does NOT have `source` or `editable`
4. Verify `MergedDayListResponse` has: `patient_id: string`, `flow_state_id: string`, `current_flow_day: number`, `days: MergedDayItem[]`
5. **Expected:** All fields present with correct types; `OverrideDayInput` excludes read-only fields

### 2. React Query hook structure

1. Open `usePatientFlowOverrides.ts`
2. Verify `useQuery` with `queryKey: ['patient-flow-overrides', patientId]`, `enabled: !!patientId`, `staleTime: 60_000`
3. Verify `useMutation` calls `apiClient.put` to `/api/v2/patients/${patientId}/flow-overrides`
4. Verify `onSuccess` invalidates `['patient-flow-overrides', patientId]`
5. **Expected:** Hook follows React Query conventions with proper cache invalidation

### 3. Barrel re-export

1. Open `frontend-hormonia/src/features/patients/hooks/index.ts`
2. Verify `usePatientFlowOverrides` is exported (value export)
3. Verify `MergedDayItem`, `MergedDayListResponse`, `OverrideDayInput` are type-exported
4. **Expected:** All four exports present — consumers can import from `@/features/patients/hooks`

### 4. PatientFlowOverrideEditor source badges

1. Open `PatientFlowOverrideEditor.tsx`
2. Find the Badge rendering per day card
3. Verify: `source === 'global'` renders `<Badge variant="secondary">Global</Badge>`
4. Verify: `source === 'override'` renders `<Badge variant="default">Personalizado</Badge>`
5. Verify: `day.skip === true` renders `<Badge variant="destructive">Pulado</Badge>`
6. **Expected:** Three distinct badge variants for three day states

### 5. Editability gating on past days

1. In `PatientFlowOverrideEditor.tsx`, find the day card rendering
2. Verify: `!day.editable` triggers `opacity-60` class on the card container
3. Verify: `Textarea`, `Select`, `Checkbox`, `Switch` all have `disabled={!day.editable}`
4. **Expected:** All 4 input types are disabled when `editable` is false; visual opacity signals read-only state

### 6. Skip toggle

1. In `PatientFlowOverrideEditor.tsx`, find the Switch component
2. Verify: `checked={day.skip}`, `onCheckedChange` calls `updateDay(index, 'skip', checked)`
3. Verify: Skip toggle is disabled when `!day.editable`
4. **Expected:** Toggle reflects skip state, updates local state, respects editability

### 7. Add day functionality

1. Find the `addDay` callback
2. Verify: New day has `day_number = max(existing) + 1`, `source: 'override'`, `editable: true`, `skip: false`
3. Verify: "Adicionar Dia" button is in DialogFooter with Plus icon
4. **Expected:** New days auto-increment, are editable, and marked as override source

### 8. Save handler filters payload correctly

1. Find the `handleSave` function
2. Verify: Only days with `source === 'override'` are included in PUT payload
3. Verify: Each day is destructured to `{ day_number, content, message_type, expects_response, skip }` — no `source`/`editable`
4. **Expected:** PUT payload contains only modified/override days with correct field subset

### 9. Source promotion on edit

1. Find the `updateDay` callback
2. Verify: When a day with `source === 'global'` is modified, `source` is promoted to `'override'`
3. **Expected:** Editing a global day causes it to be included in the PUT payload

### 10. PatientDetailPage integration

1. Open `PatientDetailPage.tsx`
2. Verify: `Settings2` imported from lucide-react
3. Verify: `PatientFlowOverrideEditor` imported from `@/features/patients/components/PatientFlowOverrideEditor`
4. Verify: `showOverrideEditor` state initialized as `useState(false)`
5. Verify: Button with text "Personalizar Fluxo" and Settings2 icon calls `setShowOverrideEditor(true)`
6. Verify: `<PatientFlowOverrideEditor open={showOverrideEditor} onOpenChange={setShowOverrideEditor} patientId={id!} />` rendered
7. **Expected:** Dialog opens on button click, closes on dismiss, passes patientId to editor

### 11. Build verification

1. Run `cd frontend-hormonia && npx tsc --noEmit`
2. **Expected:** Exit code 0, zero type errors
3. Run `cd frontend-hormonia && npx vite build`
4. **Expected:** Exit code 0, all modules transformed, chunks emitted

## Edge Cases

### Empty day list

1. In `PatientFlowOverrideEditor.tsx`, verify the empty state rendering
2. When `days.length === 0 && !isLoading`, a message "Nenhum dia configurado. Clique em 'Adicionar Dia' para começar." is shown
3. **Expected:** Graceful empty state instead of blank dialog

### Loading state

1. Verify: When `isLoading` is true, a `Loader2` spinner is shown centered in the dialog
2. **Expected:** Spinner visible during data fetch, no flickering content

### Save with no overrides

1. If all days remain `source === 'global'` (no edits), the save handler sends `{ days: [] }`
2. **Expected:** No error — PUT accepts empty override list (clears overrides)

### Toast on save failure

1. In `handleSave`, the catch block calls `toast` with `variant: 'destructive'` and message "Erro ao salvar"
2. **Expected:** User sees red toast notification when PUT fails

## Failure Signals

- `tsc --noEmit` exits non-zero — type mismatch between hook interfaces and component usage
- `vite build` fails — broken imports, missing components, or syntax errors
- `PatientFlowOverrideEditor` not found in `PatientDetailPage.tsx` imports — wiring missing
- No Badge imports in editor — source badges not rendered
- No `disabled` props in editor — past day gating broken
- `source` or `editable` fields present in save payload destructuring — leaking read-only fields to PUT

## Requirements Proved By This UAT

- R108 — PatientDetailPage has "Personalizar Fluxo" button, editor dialog with merged day list, Global/Personalizado/Pulado badges, and future-only editing (contract proof via tsc + vite build green)

## Not Proven By This UAT

- Runtime API integration (GET returns real data, PUT persists to DB) — deferred to S04
- Cache invalidation behavior at runtime — deferred to S04
- Visual rendering in a browser — deferred to S04 or manual inspection
- Backend override persistence and pipeline injection — proved by S01 and S02

## Notes for Tester

- This UAT is artifact-driven: all test cases are verifiable by reading source code and running build commands. No running server is needed.
- The `editable` field is computed server-side based on `current_flow_day`. The frontend trusts this field unconditionally — there is no client-side day comparison logic.
- The editor uses local `useState` for day mutations. Changes are not persisted until "Salvar" is clicked. Closing the dialog discards unsaved changes (re-synced from query data on next open via the `useEffect`).
