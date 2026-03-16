---
id: T01
parent: S03
milestone: M007
provides:
  - DayConfigItem/DayConfigListResponse/DayConfigListUpdate Pydantic schemas
  - GET /flows/{template_id}/days endpoint (step→day-config projection)
  - PUT /flows/{template_id}/days endpoint (day-config→step hydration with dual cache invalidation)
  - _project_steps_to_day_configs and _hydrate_day_configs_to_steps helper functions
key_files:
  - backend-hormonia/app/schemas/v2/templates.py
  - backend-hormonia/app/api/v2/routers/flow_templates.py
  - backend-hormonia/tests/unit/services/flow/test_day_config_editor_api.py
key_decisions:
  - Hydration uses "wait_each" send_mode when expects_response=True, "single" otherwise
  - Projection falls back through messages[0].content → step.content → step.base_content → step.message for content extraction
  - Unknown message_type values default to "question" during projection
patterns_established:
  - _project_steps_to_day_configs / _hydrate_day_configs_to_steps as standalone testable functions extracted from endpoint logic
  - Dual cache invalidation pattern: template API cache + Redis runtime dispatch cache
observability_surfaces:
  - Audit log entry on PUT with resource_type="flow_template_days", template_id, day_count
  - Structured logger.info on successful day-config save
  - 409 response for published template edit attempts
  - 400 response for duplicate day_number values
duration: 20m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Backend — Pydantic schemas and GET/PUT day-config endpoints

**Added GET/PUT /flows/{template_id}/days endpoints with Pydantic schemas for physician-friendly day-config editing**

## What Happened

1. Appended 3 Pydantic models to `templates.py`: `DayConfigItem` (with `message_type` validator against `{question, motivation, reminder}`), `DayConfigListResponse`, `DayConfigListUpdate`.

2. Added `GET /flows/{template_id}/days` endpoint that loads `FlowTemplateVersion.steps` and projects each step to a flat `DayConfigItem` using content fallback chain (messages[0].content → step.content → step.base_content → step.message). Returns sorted by day_number.

3. Added `PUT /flows/{template_id}/days` endpoint that:
   - Enforces draft-only editing (409 for published templates)
   - Rejects duplicate day_number values (400)
   - Hydrates each DayConfigItem to internal step format with `messages` list, `send_mode`, `intent`
   - Performs dual cache invalidation: template API cache + Redis `flow_template:{kind_key}:steps` runtime dispatch cache
   - Logs audit entry with `resource_type="flow_template_days"`

4. Extracted `_project_steps_to_day_configs` and `_hydrate_day_configs_to_steps` as standalone functions for direct testability.

5. Created initial test file with 19 tests covering projection, hydration, round-trip, loader compatibility, and schema validation.

## Verification

- `python -c "from app.schemas.v2.templates import DayConfigItem, DayConfigListResponse, DayConfigListUpdate; print('OK')"` → **PASS**
- Route registration check: both GET and PUT on `/flows/{template_id}/days` registered → **PASS**
- Hydration → `validate_day_config()` → **PASS** (step format matches config_validation expectations)
- Round-trip: DayConfigItem → hydrate → project → identical values → **PASS**
- `pytest tests/unit/services/flow/test_day_config_editor_api.py -v` → **19/19 passed**

### Slice-level verification status (partial — T01 of 3):
- [x] `pytest tests/unit/services/flow/test_day_config_editor_api.py -v` — 19 passed
- [ ] `cd frontend-hormonia && npx tsc --noEmit` — not yet (T03)
- [ ] `cd frontend-hormonia && npm run build` — not yet (T03)
- [x] Round-trip test: hydrate → project → identical — passed
- [x] Validation test: empty content → schema rejection — passed
- [x] Loader compatibility test: hydrated steps pass `validate_day_config()` — passed
- [x] Failure-path: invalid message_type rejected; duplicate day_number detection works

## Diagnostics

- **Inspect current state:** `GET /api/v2/templates/flows/{id}/days`
- **Audit trail:** Audit log entries with `resource_type="flow_template_days"` for change history
- **Error shapes:** 409 `{"detail": "Cannot edit days of a published template. Create a new draft version first."}`, 400 `{"detail": "Duplicate day_number values are not allowed"}`, 404 `{"detail": "Template not found"}`
- **Runtime cache key:** `flow_template:{kind_key}:steps` in Redis (invalidated on PUT)

## Deviations

None

## Known Issues

None

## Files Created/Modified

- `backend-hormonia/app/schemas/v2/templates.py` — Appended DayConfigItem, DayConfigListResponse, DayConfigListUpdate schemas
- `backend-hormonia/app/api/v2/routers/flow_templates.py` — Added GET/PUT /flows/{template_id}/days endpoints, Redis import, helper functions
- `backend-hormonia/tests/unit/services/flow/test_day_config_editor_api.py` — Created with 19 unit tests for projection, hydration, round-trip, and validation
- `.gsd/milestones/M007/slices/S03/S03-PLAN.md` — Added failure-path verification step; marked T01 done
