# S03 — Editor de templates dia-a-dia para o médico — Research

**Date:** 2026-03-16

## Summary

S03 is a targeted integration slice: connect an existing backend CRUD API to a new physician-facing day-config editing surface. The backend already has `FlowTemplateVersion.steps` as JSONB with full CRUD at `/api/v2/templates/flows`, and the sequencing code (`StateMixin._get_day_config`) reads from that same JSONB via the active template. The gap is twofold: (1) the existing API exposes raw `steps` (complex nested structure with `messages`, `send_mode`, `order`, etc.) rather than a physician-friendly flat list of day configs, and (2) the frontend has no edit entry point after S02 removed the FlowDesigner buttons.

The approach is: add a thin backend endpoint pair (`GET/PUT .../days`) that translates between the internal `steps` JSONB and a physician-friendly `[{day_number, content, message_type, expects_response}]` list, then build a simple frontend day-list editor component that FlowTemplateCard can open. No new DB columns or migrations needed — the `steps` JSONB is already the canonical store, and the `EnhancedTemplateLoader._parse_db_template_version()` already consumes it.

## Recommendation

Build backend-first (thin day-config API endpoints + Pydantic schemas), then frontend (day editor component + card integration). The backend layer is a pure read/write projection over the existing `steps` JSONB — no model changes. The frontend is a new component that calls the new endpoints. Verify by round-tripping: create template → edit days via new API → confirm `EnhancedTemplateLoader` loads updated content.

## Implementation Landscape

### Key Files

**Backend — existing (read, don't rewrite):**
- `backend-hormonia/app/models/flow.py` — `FlowTemplateVersion` model with `steps` (JSONB column, aliased as `messages` via property). The column name is `steps` in the DB schema. No schema change needed.
- `backend-hormonia/app/api/v2/routers/flow_templates.py` — Full CRUD router already mounted at `/api/v2/templates/flows` (prefix `/templates` in `router.py` line 147). Has `GET /flows/{template_id}`, `PUT /flows/{template_id}`, etc. The new day-config endpoints should be added here.
- `backend-hormonia/app/api/v2/templates_shared.py` — Shared helpers: `_serialize_flow_template`, `_extract_user_context`, `_check_write_permission`, cache helpers. Reuse these.
- `backend-hormonia/app/services/template_loader_pkg/loader.py` — `EnhancedTemplateLoader._parse_db_template_version()` reads `steps` as a list of step dicts. Each step: `{"day": int, "messages": [...], "send_mode": str, ...}`. Each message: `{"content": str, "expects_response": bool, "order": int}`. The loader must continue to work unchanged.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — `StateMixin._get_day_config()` reads `steps` from DB directly via SQL (`SELECT ftv.steps FROM flow_template_versions`) and returns the step matching a given day number. This is the runtime reader — must continue to work.
- `backend-hormonia/app/services/flow/config_validation.py` — `validate_day_config()` validates each step before dispatch. Expects: `{day, send_mode, messages: [{content, expects_response, ...}]}`. The new write endpoint must produce data that passes this validation.
- `backend-hormonia/app/schemas/v2/templates.py` — Existing Pydantic schemas for templates. Add new `DayConfigItem` and `DayConfigList` schemas here.

**Backend — new (create):**
- New endpoints in `flow_templates.py`: `GET /flows/{template_id}/days` and `PUT /flows/{template_id}/days`
- New Pydantic schemas in `templates.py`: `DayConfigItem`, `DayConfigListResponse`, `DayConfigListUpdate`

**Frontend — existing (modify):**
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — Currently has Versões and Desativar buttons (Edit was removed in S02). Needs new "Editar Dias" button that opens the day editor.
- `frontend-hormonia/src/hooks/useTemplates.ts` (~657 lines) — CRUD hook calling `/api/v2/templates/flows`. Needs two new functions: `getFlowTemplateDays()` and `updateFlowTemplateDays()`.
- `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx` — List page, no changes needed.

**Frontend — new (create):**
- `frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx` — New dialog/panel component: list of days, each with content textarea, message_type select, expects_response checkbox. Add/remove day buttons.

### Data Shape Contract

The `steps` JSONB stores a list where each element represents one day:
```json
[
  {
    "day": 1,
    "send_mode": "wait_each",
    "messages": [
      {"order": 1, "content": "Hello!", "expects_response": true}
    ],
    "intent": "day_1_message"
  }
]
```

The physician-facing day-config API simplifies this to:
```json
[
  {
    "day_number": 1,
    "content": "Hello!",
    "message_type": "question",
    "expects_response": true
  }
]
```

The GET endpoint projects: `step.messages[0].content` → `content`, infers `message_type` from content/metadata, reads `step.messages[0].expects_response`.

The PUT endpoint hydrates: wraps each day-config into the full step structure with `messages: [{order: 1, content, expects_response}]`, `send_mode` derived from `expects_response` (single if no response expected, wait_each if response expected), `intent` auto-generated as `day_{N}_message`.

### Build Order

1. **Backend schemas** — Add `DayConfigItem`, `DayConfigListResponse`, `DayConfigListUpdate` to `schemas/v2/templates.py`. These are pure Pydantic — no dependencies, instant to verify.

2. **Backend endpoints** — Add `GET /flows/{template_id}/days` and `PUT /flows/{template_id}/days` to `flow_templates.py`. The GET reads `FlowTemplateVersion.steps` and projects to day-config list. The PUT takes day-config list, validates, and writes back to `steps` JSONB. Reuse existing auth (`get_current_user_from_session`), permission (`_check_write_permission`), and cache (`_invalidate_template_cache`) helpers from `templates_shared.py`.

3. **Backend tests** — Focused pytest for the new endpoints: round-trip GET/PUT, validation (missing content, invalid message_type), empty days list, and verify the output is consumable by `validate_day_config()`.

4. **Frontend hook** — Add `getFlowTemplateDays()` and `updateFlowTemplateDays()` to `useTemplates.ts`. Simple API calls to the new endpoints.

5. **Frontend DayConfigEditor** — New component: Dialog with a scrollable list of day rows. Each row: day number (auto), content (textarea), message_type (select: question/motivation/reminder), expects_response (checkbox). Add Day / Remove Day buttons. Save button calls PUT.

6. **Frontend integration** — Add "Editar Dias" button to `FlowTemplateCard.tsx` that opens `DayConfigEditor`. Wire up loading and saving.

### Verification Approach

**Backend:**
- `cd backend-hormonia && python -m pytest tests/unit/services/flow/test_day_config_editor_api.py -v` — new test file for the day-config endpoints
- Round-trip test: create template via existing POST → GET days → modify → PUT days → GET days → confirm changes persisted
- Validation test: PUT with invalid data (empty content, invalid message_type) → 400
- Loader compatibility test: after PUT, confirm `validate_day_config()` passes on the stored step data

**Frontend:**
- `cd frontend-hormonia && npx tsc --noEmit` — typecheck
- `cd frontend-hormonia && npm run build` — build passes

**Integration:**
- Manual: open `/admin/templates` → click a flow template's "Editar Dias" → see days loaded → edit content → save → verify updated content is stored

## Constraints

- `FlowTemplateVersion.steps` JSONB must remain compatible with `EnhancedTemplateLoader._parse_db_template_version()` and `StateMixin._get_day_config()` — both read directly from this column. The write endpoint must produce data in the exact shape they expect.
- The existing `validate_day_config()` in `config_validation.py` validates each step at dispatch time. Steps written by the new editor must pass this validation (requires `messages` list with `content` string per message, valid `send_mode`).
- `_CANONICAL_SEND_MODES` = `{single, sequential_auto, wait_response, wait_each}`. The editor must produce valid send_mode values.
- The API is mounted at prefix `/templates` (line 147 of `router.py`), so the full path for the new endpoints will be `/api/v2/templates/flows/{template_id}/days`.
- Auth uses `get_current_user_from_session` — existing pattern, no new auth work.
- Permission check uses `_check_write_permission` from `templates_shared.py` for write operations.

## Common Pitfalls

- **Steps JSONB shape mismatch** — The `steps` column can hold either a dict or a list (schema allows both). The runtime (`_get_day_config`, `_parse_db_template_version`) only works with list format. The PUT endpoint must always write a list, never a dict.
- **message_type mapping** — The physician sees "question/motivation/reminder" but the internal `MessageType` enum is `TEXT/INTERACTIVE/QUIZ_TRIGGER/MEDIA`. These are different domains. The physician's `message_type` is a semantic label that lives alongside `content` in the step metadata — it is NOT the same as `MessageType`. Store it as a string field in the step dict (e.g., `step.message_type` or `step.messages[0].type`), and keep the loader's `MessageType.TEXT` as the transport type.
- **Draft vs published editing** — The existing PUT endpoint creates a new version when editing a non-draft template. The day-config PUT should follow the same pattern: if the template is a draft, edit in-place; if published, the endpoint should either error or create a new draft version.
- **Cache invalidation** — After writing day configs, must call `_invalidate_template_cache("flow", template_id)` AND the Redis cache used by `StateMixin._get_day_config()` (key: `flow_template:{flow_kind}:steps`, TTL 1h). Without Redis invalidation, the runtime will serve stale day configs for up to an hour.

## Open Risks

- Multi-message days in existing templates: If a physician opens the editor for a template that already has multi-message days (from the `reimport_flow_templates.py` import), the simple one-message-per-day editor must decide how to handle them. Safest: show only the first message's content but preserve the full structure on read, and only overwrite when the physician explicitly saves.
