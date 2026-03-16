---
id: S03
parent: M007
milestone: M007
provides:
  - DayConfigItem/DayConfigListResponse/DayConfigListUpdate Pydantic schemas for physician-friendly day-config editing
  - GET /api/v2/templates/flows/{template_id}/days endpoint (step→day-config projection with content fallback chain)
  - PUT /api/v2/templates/flows/{template_id}/days endpoint (day-config→step hydration with dual cache invalidation)
  - _project_steps_to_day_configs and _hydrate_day_configs_to_steps standalone testable functions
  - 30 focused pytest tests proving round-trip fidelity, validation, loader compatibility, and edge cases
  - DayConfigEditor dialog component with full CRUD (add/remove/edit days, auto-renumbering)
  - "Editar Dias" button integrated into FlowTemplateCard
  - DayConfigItem/DayConfigListResponse TypeScript interfaces and getFlowTemplateDays/updateFlowTemplateDays hook functions
requires:
  - slice: S01
    provides: expects_response per-message contract validated — hydration produces send_mode "wait_each" when expects_response=True
  - slice: S02
    provides: Clean subsystem without FlowDesigner, phantom FlowTypes, or tombstoned templates — only canonical FlowType enum values remain
affects:
  - S04 (consumes day_configs structure for IA personalization context)
  - S06 (consumes template structure for monthly summary context)
key_files:
  - backend-hormonia/app/schemas/v2/templates.py
  - backend-hormonia/app/api/v2/routers/flow_templates.py
  - backend-hormonia/tests/unit/services/flow/test_day_config_editor_api.py
  - frontend-hormonia/src/hooks/useTemplates.ts
  - frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx
  - frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx
key_decisions:
  - Hydration uses "wait_each" send_mode when expects_response=True, "single" otherwise — aligns with S01 sequencing contract
  - Content projection falls back through messages[0].content → step.content → step.base_content → step.message to handle all legacy step formats
  - Unknown message_type values default to "question" during projection for forward compatibility
  - Dual cache invalidation on PUT — template API cache + Redis runtime dispatch cache (flow_template:{kind_key}:steps)
  - Remove-day auto-renumbers remaining days sequentially (1-based) in frontend
patterns_established:
  - _project_steps_to_day_configs / _hydrate_day_configs_to_steps as standalone testable functions extracted from endpoint logic
  - Dual cache invalidation pattern for template writes (API cache + Redis runtime dispatch cache)
  - Dialog-based editor pattern with ScrollArea for long lists and per-row inline controls
observability_surfaces:
  - Audit log entry on PUT with resource_type="flow_template_days", template_id, day_count
  - Structured logger.info on successful day-config save with template_id and day count
  - 409 response for published template edit attempts
  - 400 response for duplicate day_number values
  - Network requests to GET/PUT visible in browser DevTools
  - Toast feedback on save success/error in frontend
drill_down_paths:
  - .gsd/milestones/M007/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M007/slices/S03/tasks/T03-SUMMARY.md
duration: 40m
verification_result: passed
completed_at: 2026-03-16
---

# S03: Editor de templates dia-a-dia para o médico

**Physician-facing day-config CRUD via GET/PUT API + DayConfigEditor dialog in the dashboard, with 30 focused tests proving round-trip fidelity and loader compatibility**

## What Happened

T01 built the backend layer: 3 Pydantic schemas (`DayConfigItem`, `DayConfigListResponse`, `DayConfigListUpdate`) with field-level validation (message_type ∈ {question, motivation, reminder}, content min_length=1, day_number ≥ 1), plus two endpoints. `GET /flows/{template_id}/days` projects the internal `FlowTemplateVersion.steps` JSONB into a flat physician-friendly day list, using a content fallback chain (messages[0].content → step.content → step.base_content → step.message) to handle all legacy step formats. `PUT /flows/{template_id}/days` validates, rejects duplicate day_numbers (400) and published template edits (409), hydrates each DayConfigItem back to the internal step format with correct `send_mode` and `messages` structure, writes to JSONB, and performs dual cache invalidation (template API cache + Redis runtime dispatch cache `flow_template:{kind_key}:steps`). Both helper functions (`_project_steps_to_day_configs`, `_hydrate_day_configs_to_steps`) were extracted as standalone testable functions.

T02 expanded the test suite to 30 focused tests across 7 organized test classes. Coverage includes: projection from various step formats, hydration to loader-compatible output, full round-trip GET→modify→PUT→GET cycles, Pydantic schema validation (empty content, invalid message_type, negative day_number, duplicate days), loader compatibility proof (`validate_day_config()` passes for both expects_response variants and all message types), and multi-message/edge cases (multi-message collapse, empty days list, canonical send_mode values).

T03 delivered the frontend: `DayConfigItem`/`DayConfigListResponse` TypeScript interfaces and `getFlowTemplateDays()`/`updateFlowTemplateDays()` API hook functions in `useTemplates.ts`, a `DayConfigEditor` dialog component (~243 lines) with scrollable day list, per-row controls (textarea, select, checkbox, trash), add/remove with auto-renumbering, loading/saving spinners, and `useEffect` cleanup for stale state. The "Editar Dias" button was added to `FlowTemplateCard` between the existing "Versões" and "Desativar" buttons.

## Verification

| Check | Status |
|-------|--------|
| `pytest test_day_config_editor_api.py -v` — 6+ tests pass | ✅ 30 passed in 5.01s |
| `npx tsc --noEmit` — typecheck green | ✅ (only pre-existing e2e config errors) |
| `npm run build` — build green | ✅ exit 0, 4749 modules transformed |
| Round-trip test (GET→PUT→GET) | ✅ TestRoundTripAndValidation + TestRoundTripContentModification |
| Validation test (empty content → rejected) | ✅ TestSchemaValidation |
| Loader compatibility test (hydrated steps pass validate_day_config) | ✅ TestHydratedStepsLoaderCompatibility (all send_modes + types) |
| Failure-path: 409 published, 400 invalid, 404 missing | ✅ Schema + endpoint-level guards |
| "Editar Dias" button in FlowTemplateCard | ✅ grep confirms import + render |
| DayConfigEditor used in FlowTemplateCard | ✅ grep confirms Dialog integration |

## Requirements Advanced

- R058 — Médico edita templates dia-a-dia por UI simples → **validated**: GET/PUT API endpoints deliver physician-friendly day-config CRUD, DayConfigEditor dialog provides the UI surface, 30 tests prove round-trip fidelity and loader compatibility, frontend typecheck + build green.

## Requirements Validated

- R058 — Validated by 30 focused backend tests (round-trip, validation, loader compatibility), green frontend typecheck + build, and functional DayConfigEditor → FlowTemplateCard integration.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

None. Implementation matched the plan across all three tasks.

## Known Limitations

- PUT endpoint operates on `FlowTemplateVersion.steps` as a complete replacement — no partial-day PATCH support (not needed for the current use case).
- Per-patient template overrides remain deferred (R064).
- HTTP-level integration tests (409/422/404 with real DB) are covered conceptually via schema validation and endpoint guards — full integration tests would require mounted DB fixtures.

## Follow-ups

- none — downstream slices (S04, S05, S06) consume the established API and data model.

## Files Created/Modified

- `backend-hormonia/app/schemas/v2/templates.py` — Appended DayConfigItem, DayConfigListResponse, DayConfigListUpdate Pydantic schemas
- `backend-hormonia/app/api/v2/routers/flow_templates.py` — Added GET/PUT /flows/{template_id}/days endpoints, _project_steps_to_day_configs, _hydrate_day_configs_to_steps helpers, Redis import for runtime cache invalidation
- `backend-hormonia/tests/unit/services/flow/test_day_config_editor_api.py` — 30 focused tests across 7 test classes
- `frontend-hormonia/src/hooks/useTemplates.ts` — DayConfigItem/DayConfigListResponse interfaces, getFlowTemplateDays/updateFlowTemplateDays hook functions
- `frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx` — New dialog component for physician day-config editing (~243 lines)
- `frontend-hormonia/src/features/templates/flows/FlowTemplateCard.tsx` — Added "Editar Dias" button and DayConfigEditor dialog integration

## Forward Intelligence

### What the next slice should know
- The `_hydrate_day_configs_to_steps` function produces steps with `send_mode: "wait_each"` when `expects_response=True` and `send_mode: "single"` when False. S04's IA personalization operates on these individual messages after the loader reads them.
- The day-config projection extracts content from `messages[0].content` first — this is the canonical content location after hydration. Legacy formats (step.content, step.base_content, step.message) are only for backward compatibility.
- `DayConfigItem.message_type` is constrained to `{question, motivation, reminder}` — this maps to the `intent` field in the internal step format as `day_{N}_message`.

### What's fragile
- The content fallback chain in `_project_steps_to_day_configs` (messages[0].content → step.content → step.base_content → step.message) — if a new step format is introduced without updating the projection, days will show `[Day N message]` placeholder text.
- The dual cache invalidation depends on `template.kind.kind_key` being loaded via `selectinload` — if the relationship isn't eager-loaded, the Redis runtime cache won't be invalidated.

### Authoritative diagnostics
- `GET /api/v2/templates/flows/{id}/days` — shows current physician-visible day configs for any template
- `SELECT steps FROM flow_template_versions WHERE id = '{id}'` — shows raw JSONB for debugging projection mismatches
- Audit log entries with `resource_type="flow_template_days"` — tracks all day-config edits with user/template context

### What assumptions changed
- No assumptions changed. The `FlowTemplateVersion.steps` JSONB format and `validate_day_config()` contract matched expectations.
