---
id: T03
parent: S03
milestone: M007
provides:
  - DayConfigItem/DayConfigListResponse TypeScript interfaces in useTemplates.ts
  - getFlowTemplateDays() / updateFlowTemplateDays() API hook functions
  - DayConfigEditor dialog component with full CRUD for day configs
  - "Editar Dias" button integrated into FlowTemplateCard
key_files:
  - frontend-hormonia/src/hooks/useTemplates.ts
  - frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx
  - frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx
key_decisions:
  - DayConfigEditor uses useEffect cleanup (cancelled flag) to avoid stale state on rapid open/close
  - Remove-day auto-renumbers remaining days sequentially (1-based)
  - updateFlowTemplateDays re-throws after toast so UI callers can handle save failures
patterns_established:
  - Dialog-based editor pattern with ScrollArea for long lists, per-row inline controls
observability_surfaces:
  - Network requests to GET/PUT /api/v2/templates/flows/{id}/days visible in browser DevTools
  - Toast feedback on save success/error
  - Backend audit log entry on successful PUT (resource_type flow_template_days)
duration: 12m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T03: Frontend — DayConfigEditor component and FlowTemplateCard integration

**Built physician-facing DayConfigEditor dialog with day list CRUD, type select, expects-response checkbox, and integrated "Editar Dias" button in FlowTemplateCard**

## What Happened

Added `DayConfigItem` and `DayConfigListResponse` TypeScript interfaces to `useTemplates.ts`, along with `getFlowTemplateDays()` and `updateFlowTemplateDays()` hook functions following the existing `apiClient` + `useCallback` + error-toast pattern.

Created `DayConfigEditor.tsx` (~190 lines) — a Dialog component that loads days on open, displays them as bordered rows with: auto-numbered label, content Textarea, message-type Select (Pergunta/Motivação/Lembrete), expects-response Checkbox, and Trash2 remove button. Footer has "Adicionar Dia" (appends new day) and "Salvar" (calls PUT endpoint). Remove auto-renumbers remaining days. Loading spinner during fetch, saving spinner on submit.

Added "Editar Dias" button to `FlowTemplateCard.tsx` between Versões and Desativar buttons, with `showDayEditor` state and `DayConfigEditor` dialog render.

## Verification

- `npx tsc --noEmit` — only pre-existing e2e config errors (not in our files) ✅
- `npm run build` — exits 0, 4749 modules transformed ✅
- `grep -r "DayConfigEditor"` — found in definition (DayConfigEditor.tsx) and import (FlowTemplateCard.tsx) ✅
- `grep -r "getFlowTemplateDays\|updateFlowTemplateDays"` — found in useTemplates.ts (definition + return) and DayConfigEditor.tsx (usage) ✅
- `grep "Editar Dias" FlowTemplateCard.tsx` — button text present ✅
- Backend tests: 30/30 passed (slice verification) ✅

### Slice-Level Verification Status (T03 is final task)

| Check | Status |
|-------|--------|
| `pytest test_day_config_editor_api.py -v` — 6+ tests pass | ✅ 30 passed |
| `npx tsc --noEmit` — typecheck green | ✅ (pre-existing e2e errors only) |
| `npm run build` — build green | ✅ exit 0 |
| Round-trip test (GET→PUT→GET) | ✅ covered by TestRoundTripAndValidation |
| Validation test (empty content → 400) | ✅ covered by TestSchemaValidation |
| Loader compatibility test | ✅ covered by TestHydratedStepsLoaderCompatibility |
| Failure-path tests (409/422/404) | ✅ covered by unit tests |

All slice verification checks pass.

## Diagnostics

- Inspect day configs: `GET /api/v2/templates/flows/{id}/days` returns current projection
- Save changes: `PUT /api/v2/templates/flows/{id}/days` with `{ days: [...] }`
- Error shapes: 409 for published templates, 400 for invalid data, 404 for missing template
- Frontend: browser DevTools Network tab shows GET/PUT requests; toast notifications confirm success/failure
- Audit trail: backend audit log entries with `resource_type="flow_template_days"`

## Deviations

- API functions use full error-toast pattern (matching existing hook style) instead of the minimal `logger.error` pattern in the plan — consistent with the codebase convention.

## Known Issues

None.

## Files Created/Modified

- `frontend-hormonia/src/hooks/useTemplates.ts` — Added DayConfigItem/DayConfigListResponse interfaces and getFlowTemplateDays/updateFlowTemplateDays hook functions
- `frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx` — New dialog component for physician day-config editing
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — Added "Editar Dias" button and DayConfigEditor dialog integration
