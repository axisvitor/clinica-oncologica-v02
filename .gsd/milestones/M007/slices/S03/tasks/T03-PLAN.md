---
estimated_steps: 6
estimated_files: 3
---

# T03: Frontend — DayConfigEditor component and FlowTemplateCard integration

**Slice:** S03 — Editor de templates dia-a-dia para o médico
**Milestone:** M007

## Description

Build the physician-facing day-config editing surface: a new `DayConfigEditor` dialog component, API hook functions, and the "Editar Dias" button in `FlowTemplateCard`. The doctor clicks the button, sees a list of days with content/type/response fields, edits, saves.

## Steps

1. **Add types and API functions to `useTemplates.ts`.**

   Add `DayConfigItem` interface near the existing `FlowTemplateStep` interface:
   ```typescript
   export interface DayConfigItem {
     day_number: number
     content: string
     message_type: 'question' | 'motivation' | 'reminder'
     expects_response: boolean
   }

   export interface DayConfigListResponse {
     template_id: string
     template_name: string
     is_draft: boolean
     days: DayConfigItem[]
     total_days: number
   }
   ```

   Add two new functions inside the `useTemplates` hook body, following the pattern of existing functions (use `apiClient`, `useCallback`, error handling with `logger.error`):

   ```typescript
   const getFlowTemplateDays = useCallback(
     async (templateId: string): Promise<DayConfigListResponse | null> => {
       try {
         const response = await apiClient.get<DayConfigListResponse>(
           `/api/v2/templates/flows/${templateId}/days`
         )
         return response
       } catch (error) {
         logger.error('Failed to get flow template days', error)
         return null
       }
     }, []
   )

   const updateFlowTemplateDays = useCallback(
     async (templateId: string, days: DayConfigItem[]): Promise<DayConfigListResponse | null> => {
       try {
         const response = await apiClient.put<DayConfigListResponse>(
           `/api/v2/templates/flows/${templateId}/days`,
           { days }
         )
         return response
       } catch (error) {
         logger.error('Failed to update flow template days', error)
         throw error  // re-throw so the UI can show error toast
       }
     }, []
   )
   ```

   Add both functions to the hook's return object (there's a return statement near the end of the hook that returns an object with all functions).

2. **Create `DayConfigEditor.tsx`** at `frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx`:

   ```typescript
   import React, { useState, useEffect } from 'react'
   import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
   import { Button } from '@/components/ui/button'
   import { Textarea } from '@/components/ui/textarea'
   import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
   import { Checkbox } from '@/components/ui/checkbox'
   import { Label } from '@/components/ui/label'
   import { ScrollArea } from '@/components/ui/scroll-area'
   import { useTemplates } from '@/hooks/useTemplates'
   import type { DayConfigItem } from '@/hooks/useTemplates'
   import { useToast } from '@/components/ui/use-toast'
   import { logger } from '@/lib/logger'
   import { Trash2, Plus } from 'lucide-react'
   ```

   Props: `{ open: boolean; onOpenChange: (open: boolean) => void; templateId: string; templateName: string }`

   State: `days: DayConfigItem[]`, `loading: boolean`, `saving: boolean`

   On open (useEffect watching `open` + `templateId`): call `getFlowTemplateDays(templateId)`, populate `days` state.

   Render: Dialog with ScrollArea containing the day list. Each day row:
   - Label showing `Dia {day.day_number}` (auto-numbered, not editable)
   - Textarea for `content` (3-4 rows)
   - Select for `message_type` with options: "Pergunta" (question), "Motivação" (motivation), "Lembrete" (reminder)
   - Checkbox with label "Espera resposta" for `expects_response`
   - Remove button (Trash2 icon) to delete the day

   Footer: "Adicionar Dia" button (Plus icon) that appends a new day with `day_number = max(existing) + 1`, empty content, type "question", expects_response false. "Salvar" button calls `updateFlowTemplateDays(templateId, days)`, shows toast on success/error, closes dialog on success.

   When removing a day, renumber remaining days sequentially (1, 2, 3, ...).

3. **Add "Editar Dias" button to `FlowTemplateCard.tsx`.**

   Import `DayConfigEditor`:
   ```typescript
   import { DayConfigEditor } from './DayConfigEditor'
   ```

   Add state: `const [showDayEditor, setShowDayEditor] = useState(false)`

   Add button in the actions area (between Versões and Desativar):
   ```tsx
   <Button variant="outline" size="sm" onClick={() => setShowDayEditor(true)}>
     Editar Dias
   </Button>
   ```

   Add the dialog render after the existing `FlowTemplateVersionsDialog`:
   ```tsx
   <DayConfigEditor
     open={showDayEditor}
     onOpenChange={setShowDayEditor}
     templateId={template.id}
     templateName={template.template_name}
   />
   ```

4. **Verify the Select component** exists at `frontend-hormonia/src/components/ui/select.tsx` and exports `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue`. If it doesn't export all of these, check what's available and adapt the import. Similarly verify `ScrollArea` is exported from `scroll-area.tsx`, `Checkbox` from `checkbox.tsx`, `Textarea` from `textarea.tsx`.

5. **Run typecheck and build:**
   ```bash
   cd frontend-hormonia && npx tsc --noEmit
   cd frontend-hormonia && npm run build
   ```
   Fix any type errors or missing imports.

6. **Verify the component renders correctly** by checking that `FlowTemplateCard` references `DayConfigEditor` and the dialog opens/closes.

## Must-Haves

- [ ] `DayConfigItem` interface and API functions added to `useTemplates.ts`
- [ ] `DayConfigEditor.tsx` component with day list, content textarea, type select, expects_response checkbox
- [ ] Add Day / Remove Day functionality with auto-renumbering
- [ ] "Editar Dias" button in `FlowTemplateCard.tsx` opens the editor
- [ ] Save calls PUT endpoint and shows toast feedback
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run build` exits 0

## Verification

- `cd frontend-hormonia && npx tsc --noEmit` — typecheck green (ignore pre-existing e2e config errors in excluded files)
- `cd frontend-hormonia && npm run build` — build exits 0
- `grep -r "DayConfigEditor" frontend-hormonia/src/ --include='*.tsx' --include='*.ts'` — shows import in FlowTemplateCard and definition in DayConfigEditor
- `grep -r "getFlowTemplateDays\|updateFlowTemplateDays" frontend-hormonia/src/ --include='*.ts'` — shows functions in useTemplates.ts
- `grep "Editar Dias" frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — button text found

## Inputs

- `frontend-hormonia/src/hooks/useTemplates.ts` — Existing hook (657 lines). Has `apiClient` import from `@/lib/api-client`, `logger` from `@/lib/logger`, uses `useCallback` pattern. Return object near end lists all exported functions. `FlowTemplate` interface at line 77 has `id: string`. API calls use pattern `apiClient.get<T>(url)` / `apiClient.put<T>(url, data)`.
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — 91 lines. Has Versões and Desativar buttons. Uses `useState` for `showVersions`. Template prop has `id`, `template_name`, `is_draft`, `is_active`, `steps`, etc.
- UI components available: `dialog.tsx` (Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter), `button.tsx`, `textarea.tsx`, `select.tsx` (Select, SelectContent, SelectItem, SelectTrigger, SelectValue), `checkbox.tsx`, `label.tsx`, `scroll-area.tsx` (ScrollArea), `badge.tsx`. Icons from `lucide-react` (already used in the codebase).
- API contract from T01: `GET /api/v2/templates/flows/{id}/days` returns `{template_id, template_name, is_draft, days: [{day_number, content, message_type, expects_response}], total_days}`; `PUT` same path accepts `{days: [...]}` and returns same response shape.

## Expected Output

- `frontend-hormonia/src/hooks/useTemplates.ts` — `DayConfigItem` interface, `DayConfigListResponse` interface, `getFlowTemplateDays()`, `updateFlowTemplateDays()` functions added
- `frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx` — New component (~120-160 lines)
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — "Editar Dias" button and DayConfigEditor dialog added
