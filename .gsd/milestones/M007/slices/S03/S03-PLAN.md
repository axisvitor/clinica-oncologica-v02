# S03: Editor de templates dia-a-dia para o médico

**Goal:** O médico edita o conteúdo de cada dia do fluxo via API e UI no dashboard, e o conteúdo atualizado é carregado pelo `EnhancedTemplateLoader` para envio real.

**Demo:** Médico abre a lista de templates → clica "Editar Dias" num template rascunho → vê a lista de dias com conteúdo, tipo, e flag de espera-resposta → edita conteúdo do dia 3 → adiciona dia 46 → salva → recarrega → conteúdo atualizado aparece. O `validate_day_config()` passa nos steps salvos.

## Must-Haves

- GET `/api/v2/templates/flows/{template_id}/days` retorna lista de `{day_number, content, message_type, expects_response}` projetada do JSONB `steps`
- PUT `/api/v2/templates/flows/{template_id}/days` aceita lista de day-configs, valida, e escreve de volta no JSONB `steps` no formato que `EnhancedTemplateLoader` e `StateMixin._get_day_config()` consomem
- PUT só edita templates draft; templates publicados retornam 409
- Cache invalidado: tanto `templates:v2:flow:*` quanto `flow_template:{kind_key}:steps` (Redis runtime cache, TTL 1h)
- Componente `DayConfigEditor` no frontend: dialog com lista de dias editável (textarea conteúdo, select tipo, checkbox espera-resposta)
- Botão "Editar Dias" no `FlowTemplateCard` abre o editor
- Frontend typecheck e build verdes

## Proof Level

- This slice proves: operational
- Real runtime required: no (API contract proven by focused tests + typecheck/build)
- Human/UAT required: no (manual exercise desirable but not blocking)

## Verification

- `cd backend-hormonia && python -m pytest tests/unit/services/flow/test_day_config_editor_api.py -v` — 6+ tests pass
- `cd frontend-hormonia && npx tsc --noEmit` — typecheck green
- `cd frontend-hormonia && npm run build` — build green
- Round-trip test: GET days → PUT modified → GET days → changes reflected
- Validation test: PUT with empty content → 400
- Loader compatibility test: steps produced by PUT pass `validate_day_config()`

## Observability / Diagnostics

- Runtime signals: Audit log entry on day-config save (`AuditAction.UPDATE`, resource_type `flow_template_days`); structured log with template_id, day_count
- Inspection surfaces: `GET /api/v2/templates/flows/{id}/days` to inspect current day configs; `SELECT steps FROM flow_template_versions WHERE id = '{id}'` for raw JSONB
- Failure visibility: 409 on published template edit attempt with clear message; 400 on invalid day-config with field-level errors; 404 on missing template
- Redaction constraints: none

## Integration Closure

- Upstream surfaces consumed: `FlowTemplateVersion.steps` JSONB (model), `_check_write_permission` + `_invalidate_template_cache` + `_extract_user_context` (templates_shared.py), `validate_day_config()` (config_validation.py), `get_current_user_from_session` (auth)
- New wiring introduced in this slice: 2 API endpoints (`GET/PUT .../days`), `DayConfigEditor` component, "Editar Dias" button in `FlowTemplateCard`
- What remains before the milestone is truly usable end-to-end: S04 (IA personalization + response storage), S05 (quiz alerts), S06 (monthly summary)

## Tasks

- [ ] **T01: Backend — Pydantic schemas and GET/PUT day-config endpoints** `est:35m`
  - Why: The core data layer — projects between internal `steps` JSONB and physician-friendly day-config list. Without this, the frontend has nothing to call.
  - Files: `backend-hormonia/app/schemas/v2/templates.py`, `backend-hormonia/app/api/v2/routers/flow_templates.py`, `backend-hormonia/app/api/v2/templates_shared.py`
  - Do: Add `DayConfigItem`, `DayConfigListResponse`, `DayConfigListUpdate` Pydantic schemas. Add `GET /flows/{template_id}/days` that reads `FlowTemplateVersion.steps` and projects each step to `{day_number, content, message_type, expects_response}`. Add `PUT /flows/{template_id}/days` that validates day-configs, hydrates each back to full step format (`{day, send_mode, messages: [{order:1, content, expects_response}], intent, message_type}`), writes to `steps` JSONB (draft only, 409 for published), and invalidates both template cache AND Redis `flow_template:{kind_key}:steps` key.
  - Verify: `cd backend-hormonia && python -c "from app.schemas.v2.templates import DayConfigItem, DayConfigListResponse, DayConfigListUpdate; print('OK')"` — schemas importable
  - Done when: Both endpoints are importable and the schemas validate correctly; the PUT hydration produces steps that pass `validate_day_config()` manually.

- [ ] **T02: Backend tests — Prove day-config API contract with focused pytest** `est:25m`
  - Why: The steps↔day-config projection is the riskiest part — if the hydration is wrong, the runtime will crash on dispatch. Tests prove the contract before the UI is built.
  - Files: `backend-hormonia/tests/unit/services/flow/test_day_config_editor_api.py`
  - Do: Write focused unit tests: (1) round-trip GET→PUT→GET with content changes, (2) validation rejects empty content, (3) validation rejects invalid message_type, (4) PUT on published template returns 409, (5) steps output passes `validate_day_config()`, (6) multi-message day collapses to single message on save, (7) empty days list is valid. Mock DB/Redis at the boundary.
  - Verify: `cd backend-hormonia && python -m pytest tests/unit/services/flow/test_day_config_editor_api.py -v` — all tests pass
  - Done when: 6+ tests pass covering round-trip, validation, draft-only, and loader compatibility.

- [ ] **T03: Frontend — DayConfigEditor component and FlowTemplateCard integration** `est:35m`
  - Why: The physician-facing surface — without this, the API exists but the doctor can't use it.
  - Files: `frontend-hormonia/src/hooks/useTemplates.ts`, `frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx`, `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx`
  - Do: Add `DayConfigItem` interface and `getFlowTemplateDays()` / `updateFlowTemplateDays()` functions to `useTemplates.ts`. Create `DayConfigEditor.tsx` as a Dialog with: scrollable list of day rows (auto-numbered), each with textarea (content), select (question/motivation/reminder), checkbox (expects_response); Add Day / Remove Day buttons; Save button calls PUT. Add "Editar Dias" button to `FlowTemplateCard.tsx` that opens the editor.
  - Verify: `cd frontend-hormonia && npx tsc --noEmit && npm run build` — typecheck + build green
  - Done when: `FlowTemplateCard` shows "Editar Dias" button, clicking opens `DayConfigEditor` dialog, component compiles and builds without errors.

## Files Likely Touched

- `backend-hormonia/app/schemas/v2/templates.py`
- `backend-hormonia/app/api/v2/routers/flow_templates.py`
- `backend-hormonia/tests/unit/services/flow/test_day_config_editor_api.py`
- `frontend-hormonia/src/hooks/useTemplates.ts`
- `frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx`
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx`
