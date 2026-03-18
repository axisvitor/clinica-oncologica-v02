---
estimated_steps: 6
estimated_files: 3
---

# T02: PatientFlowOverrideEditor component + PatientDetailPage integration + build proof

**Slice:** S03 — Editor de override no PatientDetailPage
**Milestone:** M012

**Relevant skill:** `frontend-design` — load this skill for UI component patterns and design guidance.

## Description

Build the `PatientFlowOverrideEditor` dialog component and wire it into `PatientDetailPage`. This is the user-facing deliverable for the entire slice (R108): a "Personalizar Fluxo" button in the right sidebar opens a dialog showing all flow days with source badges, editability gating, skip toggles, and an "Adicionar Dia" button. Follows the `DayConfigEditor.tsx` layout pattern closely but adapted for the override use case.

## Steps

1. **Create `PatientFlowOverrideEditor.tsx`** at `frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx`.

   Props interface:
   ```typescript
   interface PatientFlowOverrideEditorProps {
     open: boolean
     onOpenChange: (open: boolean) => void
     patientId: string
   }
   ```

   Imports needed:
   - `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter` from `@/components/ui/dialog`
   - `Button` from `@/components/ui/button`
   - `Textarea` from `@/components/ui/textarea`
   - `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue` from `@/components/ui/select`
   - `Checkbox` from `@/components/ui/checkbox`
   - `Label` from `@/components/ui/label`
   - `ScrollArea` from `@/components/ui/scroll-area`
   - `Badge` from `@/components/ui/badge`
   - `Switch` from `@/components/ui/switch`
   - `useToast` from `@/components/ui/use-toast`
   - `Loader2`, `Plus` from `lucide-react`
   - `usePatientFlowOverrides` and types `MergedDayItem`, `OverrideDayInput` from `@/features/patients/hooks`
   - `useState`, `useCallback`, `useEffect` from `react`

2. **Implement the component body:**

   - Call `usePatientFlowOverrides(patientId)` to get `{ data, isLoading, saveOverrides, isSaving }`
   - Local state: `days` as `MergedDayItem[]`, initialized from `data?.days` when data loads (use `useEffect` watching `data` and `open`)
   - Day mutation helpers (same pattern as `DayConfigEditor.tsx`):
     - `updateDay(index, field, value)` — updates local state
     - `addDay()` — appends new day with `day_number = max existing + 1`, `source: 'override'`, `editable: true`, `skip: false`, empty content, `message_type: 'question'`, `expects_response: false`
   - `MESSAGE_TYPE_LABELS` map: `{ question: 'Pergunta', motivation: 'Motivação', reminder: 'Lembrete' }`
   - Save handler:
     - Filter `days` to only those where `source === 'override'` (user-modified or new)
     - Map to `OverrideDayInput` shape (strip `source` and `editable` fields)
     - Call `saveOverrides({ days: filteredDays })`
     - On success: toast "Personalização salva" with count, close dialog
     - On error: toast error

3. **Day card layout** (inside ScrollArea, mirroring DayConfigEditor):

   For each day, render a `div.rounded-lg.border.p-4.space-y-3`:

   - **Header row:** "Dia {day_number}" label + source badge:
     - `source === 'global'`: `<Badge variant="secondary">Global</Badge>`
     - `source === 'override'`: `<Badge variant="default">Personalizado</Badge>`
     - If `day.skip`: additionally show `<Badge variant="destructive">Pulado</Badge>`
   - **Content:** `<Textarea>` with `value={day.content}`, `disabled={!day.editable}`, `rows={3}`, placeholder "Conteúdo da mensagem para este dia..."
   - **Controls row** (flex, gap-4, flex-wrap):
     - **Type select:** `<Select>` with `value={day.message_type}`, `disabled={!day.editable}`, options from MESSAGE_TYPE_LABELS
     - **Expects response:** `<Checkbox>` with `checked={day.expects_response}`, `disabled={!day.editable}`
     - **Skip toggle:** `<Switch>` with `checked={day.skip}`, `disabled={!day.editable}`, label "Pular dia"
   - Past/non-editable days: all inputs receive `disabled` prop. Add `opacity-60` class to the card container when `!day.editable` for visual distinction.

4. **Dialog footer:**
   - "Adicionar Dia" button (outline variant, Plus icon, disabled when loading/saving)
   - "Salvar" button (default variant, Loader2 spinner when saving, disabled when loading/saving)

5. **Wire into PatientDetailPage** — edit `frontend-hormonia/src/pages/PatientDetailPage.tsx`:

   - Add import: `import { PatientFlowOverrideEditor } from '@/features/patients/components/PatientFlowOverrideEditor'`
   - Add import: `import { Settings2 } from 'lucide-react'` (or `Sliders` — use `Settings2` for the customize icon)
   - Add state: `const [showOverrideEditor, setShowOverrideEditor] = useState(false)`
   - In the right sidebar area (inside `<div className="space-y-6">` that contains `<FlowStatus>` and `<QuickActions>`), add between FlowStatus and QuickActions:
     ```tsx
     <Button
       variant="outline"
       className="w-full"
       onClick={() => setShowOverrideEditor(true)}
     >
       <Settings2 className="mr-2 h-4 w-4" />
       Personalizar Fluxo
     </Button>
     ```
   - After the `<SendQuizLinkModal>` block (before closing `</div>`), add:
     ```tsx
     {id && (
       <PatientFlowOverrideEditor
         open={showOverrideEditor}
         onOpenChange={setShowOverrideEditor}
         patientId={id}
       />
     )}
     ```

6. **Build proof:**
   - Run `cd frontend-hormonia && npx tsc --noEmit` — must pass with zero errors
   - Run `cd frontend-hormonia && npx vite build` — must produce clean build with no errors

## Must-Haves

- [ ] `PatientFlowOverrideEditor` dialog component with Badge source annotation per day
- [ ] Global days show `<Badge variant="secondary">Global</Badge>`, override days show `<Badge variant="default">Personalizado</Badge>`
- [ ] All inputs disabled when `!day.editable` (Textarea, Select, Checkbox, Switch)
- [ ] Non-editable days have `opacity-60` visual distinction
- [ ] Skip toggle via Switch component with "Pular dia" label
- [ ] "Adicionar Dia" appends new override day with auto-incremented day_number
- [ ] Save filters to only `source === 'override'` days, strips `source`/`editable` from PUT payload
- [ ] "Personalizar Fluxo" button in PatientDetailPage right sidebar between FlowStatus and QuickActions
- [ ] `tsc --noEmit` passes with zero errors
- [ ] `vite build` produces clean build

## Verification

- `cd frontend-hormonia && npx tsc --noEmit` — zero type errors
- `cd frontend-hormonia && npx vite build` — clean build, no errors
- `grep -n "PatientFlowOverrideEditor" frontend-hormonia/src/pages/PatientDetailPage.tsx` — import + render exist
- `grep -n "Personalizar Fluxo" frontend-hormonia/src/pages/PatientDetailPage.tsx` — button text exists
- `grep -n "Badge" frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx` — badge used for source annotation
- `grep -n "disabled" frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx` — editability gating present

## Inputs

- T01 output: `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` — provides `usePatientFlowOverrides` hook and types `MergedDayItem`, `OverrideDayInput`
- Reference pattern: `frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx` — day card layout, dialog structure, save pattern. **Do NOT modify this file.**
- Integration target: `frontend-hormonia/src/pages/PatientDetailPage.tsx` — right sidebar section with `<FlowStatus>` and `<QuickActions>` components
- UI components: `@/components/ui/dialog`, `@/components/ui/badge`, `@/components/ui/switch`, `@/components/ui/textarea`, `@/components/ui/select`, `@/components/ui/checkbox`, `@/components/ui/scroll-area`, `@/components/ui/label`
- Toast: `@/components/ui/use-toast`

## Expected Output

- `frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx` — new ~250-line dialog component
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` — modified with button + dialog wiring (~15 lines added)
- `tsc --noEmit` and `vite build` both passing green

## Observability Impact

- **React Query DevTools**: Query key `['patient-flow-overrides', patientId]` appears when the dialog opens. Inspect cache state, stale/fresh status, and fetch timing.
- **Network tab**: GET `/api/v2/patients/{id}/flow-overrides` fires on dialog open; PUT on save. Check request/response payloads for contract alignment.
- **Toast notifications**: Save success shows "Personalização salva" with count; save failures show "Erro ao salvar" with destructive variant.
- **Mutation error state**: `isSaving` and `error` from the hook surface save progress/failures in the component.
- **Build-time signals**: `tsc --noEmit` and `vite build` catch type regressions from interface drift immediately.
