# S03: Editor de templates dia-a-dia para o médico — UAT

**Milestone:** M007
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: The slice delivers a CRUD API + frontend dialog. The API contract is proven by 30 focused backend tests (projection, hydration, round-trip, validation, loader compatibility). The frontend is proven by green typecheck + build. Live runtime exercise is desirable but not blocking — the data transformation layer is the riskiest part and it's covered.

## Preconditions

- Backend running: `cd backend-hormonia && uvicorn app.main:app --port 8000`
- Frontend running: `cd frontend-hormonia && npm run dev`
- Authenticated session (logged in as admin or doctor)
- At least one flow template exists in **draft** status (if none exists, create one via the dashboard)

## Smoke Test

1. Open the dashboard at `/templates` or the flow templates section
2. Find any template card → verify "Editar Dias" button is visible between "Versões" and "Desativar"
3. Click "Editar Dias" → verify dialog opens with template name in the header

## Test Cases

### 1. Load existing day configs

1. Navigate to the flow templates section in the dashboard
2. Find a draft template with existing steps (configured days)
3. Click "Editar Dias"
4. **Expected:** Dialog opens showing a scrollable list of days. Each row shows: day number label, content textarea (pre-filled), message type select (Pergunta/Motivação/Lembrete), "Espera resposta" checkbox. Days are sorted by day_number.

### 2. Edit day content and save

1. Open "Editar Dias" on a draft template
2. Change the content of day 3 to "Como você está se sentindo hoje? Conte-me sobre qualquer mudança."
3. Change message type of day 3 to "Motivação"
4. Check "Espera resposta" for day 3
5. Click "Salvar"
6. **Expected:** Toast "Dias salvos" appears. Dialog closes. Re-open "Editar Dias" — day 3 shows the updated content, type "Motivação", and checkbox checked.

### 3. Add a new day

1. Open "Editar Dias" on a draft template that has e.g. 5 days
2. Click "Adicionar Dia"
3. **Expected:** A new day row appears at the bottom with day number 6, empty content textarea, default type "Pergunta", unchecked "Espera resposta"
4. Fill in content: "Nova mensagem de acompanhamento"
5. Click "Salvar"
6. **Expected:** Toast confirms save. Re-open — 6 days visible, day 6 has the new content.

### 4. Remove a day and verify renumbering

1. Open "Editar Dias" on a template with at least 4 days
2. Click the trash icon on day 2
3. **Expected:** Day 2 disappears. Former day 3 becomes day 2, former day 4 becomes day 3 (auto-renumbered sequentially).
4. Click "Salvar"
5. **Expected:** Toast confirms save. Re-open — days are renumbered correctly.

### 5. Verify draft-only guard (via API)

1. Using curl or browser DevTools, send `PUT /api/v2/templates/flows/{published_template_id}/days` with valid body
2. **Expected:** Response `409` with body `{"detail": "Cannot edit days of a published template. Create a new draft version first."}`

### 6. Round-trip via API

1. `GET /api/v2/templates/flows/{draft_template_id}/days` → note the response
2. Modify one day's content in the response
3. `PUT /api/v2/templates/flows/{draft_template_id}/days` with the modified `days` array
4. `GET /api/v2/templates/flows/{draft_template_id}/days` again
5. **Expected:** The modified content appears in the second GET response. All other fields match.

## Edge Cases

### Empty template (no days)

1. Create or find a draft template with no steps
2. Open "Editar Dias"
3. **Expected:** Dialog shows "Nenhum dia configurado. Clique em 'Adicionar Dia' para começar."
4. Add a day, fill content, save
5. **Expected:** Save succeeds, re-open shows 1 day.

### Validation — empty content

1. Open "Editar Dias", add a new day
2. Leave content textarea empty
3. Click "Salvar"
4. **Expected:** PUT request returns 422 (validation error from Pydantic). Toast shows error.

### Validation — duplicate day numbers (via API)

1. Send `PUT /api/v2/templates/flows/{id}/days` with two days both having `day_number: 1`
2. **Expected:** Response `400` with `{"detail": "Duplicate day_number values are not allowed"}`
3. Note: The UI prevents this through auto-renumbering, so this can only happen via direct API call.

### Missing template

1. Send `GET /api/v2/templates/flows/00000000-0000-0000-0000-000000000000/days`
2. **Expected:** Response `404` with `{"detail": "Template not found"}`

## Failure Signals

- "Editar Dias" button missing from FlowTemplateCard → check DayConfigEditor import
- Dialog opens but shows no days on a template with known steps → check `_project_steps_to_day_configs` content fallback chain
- Save succeeds but re-open shows old data → check dual cache invalidation (both template API cache and Redis `flow_template:{kind_key}:steps`)
- 500 error on GET → check `FlowTemplateVersion.steps` JSONB format compatibility
- Frontend build fails → check TypeScript interfaces match the backend schema

## Requirements Proved By This UAT

- R058 — Médico edita templates dia-a-dia por UI simples: the test cases prove CRUD via API and UI, draft-only guard, validation, round-trip fidelity, and the physician workflow (load → edit → save → verify).

## Not Proven By This UAT

- Runtime dispatch behavior: whether `EnhancedTemplateLoader` picks up the saved steps for actual WhatsApp message delivery (proven by loader compatibility unit tests, but not by end-to-end flow execution)
- Per-patient override (R064 — deferred)
- IA personalization of edited content (S04 scope)
- Concurrent editing by multiple physicians (no locking mechanism — last-write-wins)

## Notes for Tester

- The "Editar Dias" button appears for all templates (draft and published). Published templates will show the days but the save will fail with 409 — this is correct behavior.
- The auto-renumbering on remove is immediate in the UI but only persisted on save.
- Pre-existing e2e typecheck errors in `tests/e2e/playwright.config.e2e.ts` are unrelated — they existed before this slice.
- Backend test `test_split_files_under_500_lines` fails because `sequencing.py` has 521 lines — this is a pre-existing issue from S01, unrelated to this slice.
