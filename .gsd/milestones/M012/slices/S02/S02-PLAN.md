# S02: Injeção no pipeline de envio

**Goal:** Both pipeline paths (on-demand via `_get_day_config` and batch cron via `_process_single_patient_flow`) consult patient overrides before global templates, with Redis caching and skip logic.
**Demo:** When a `PatientFlowOverride` exists for a day, both pipeline paths use the override content instead of the global template. Days with `skip=true` are skipped by both paths. Patients without overrides work exactly as before. `ast.parse` green on all modified files.

## Must-Haves

- `_get_day_config` accepts optional `patient_flow_state_id`, checks override before global template
- Override with `skip=true` causes `_get_day_config` to return `None` (triggers existing skip handling)
- `_process_single_patient_flow` checks override before `_get_message_template_for_day`
- Override content used directly in batch path (no AI personalization for overrides)
- Redis cache key `flow_override:{patient_flow_state_id}:days` storing all overrides per patient as dict
- Cache key pattern matches S01 invalidation: `flow_override:{state_id}:*`
- Cache miss sentinel (empty dict `{}`) prevents DB query on every call for patients without overrides
- `_get_day_config` signature backward-compatible (`patient_flow_state_id` defaults to `None`)
- `ast.parse` green on all 4 modified files
- Patients without overrides work exactly as before (no behavior change)

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

- `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py').read())"` — PASS
- `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/_flow_message_flow.py').read())"` — PASS
- `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/_flow_response_flow.py').read())"` — PASS
- `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/helpers/flow_helpers.py').read())"` — PASS
- `grep -c "patient_flow_state_id" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` ≥ 3 (param + cache + query)
- `grep "flow_override:" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — cache key pattern present
- `grep "patient_flow_state_id=flow_state.id" backend-hormonia/app/services/flow/_flow_message_flow.py` — kwarg passed
- `grep "patient_flow_state_id=flow_state.id" backend-hormonia/app/services/flow/_flow_response_flow.py` — kwarg passed
- `grep "Day skipped by patient override" backend-hormonia/app/tasks/helpers/flow_helpers.py` — skip reason in batch path
- `grep "_check_patient_override_for_day" backend-hormonia/app/tasks/helpers/flow_helpers.py` — helper exists
- `grep -c "warning\|Warning\|fallback" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` ≥ 1 — failure-path logging present (Redis error fallback to DB)

## Observability / Diagnostics

- Runtime signals: `logger.debug("Override cache hit/miss for flow_state %s day %s")` in `_get_day_config`, `logger.info("Day skipped by patient override")` in both paths, `logger.info("Using patient override content")` in batch path
- Inspection surfaces: Redis key `flow_override:{state_id}:days` inspectable via `redis-cli GET`, `patient_flow_overrides` table queryable by `patient_flow_state_id`
- Failure visibility: Override cache errors logged as warnings with transparent fallback to DB query. Redis failure does not fail the pipeline.
- Redaction constraints: none

## Integration Closure

- Upstream surfaces consumed: `PatientFlowOverride` model from S01 (`app/models/flow.py`), `patient_flow_overrides` table, S01 cache invalidation pattern `flow_override:{state_id}:*` in PUT endpoint
- New wiring introduced: Override lookup in `_get_day_config` (Path B: on-demand + response), override check in `_process_single_patient_flow` (Path A: batch cron), Redis cache read/write for `flow_override:{state_id}:days`
- What remains: S03 (frontend editor), S04 (integrated verification)

## Tasks

- [x] **T01: Inject override lookup in `_get_day_config` and update on-demand callers** `est:45m`
  - Why: R106 and R107 require override injection in the on-demand pipeline path (Path B). `_get_day_config` is the single point where day configuration is resolved for `load_flow_context` (message send) and `load_response_context` (response continuation). Both callers must pass the patient's flow state ID so the override lookup can happen.
  - Files: `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py`, `backend-hormonia/app/services/flow/_flow_message_flow.py`, `backend-hormonia/app/services/flow/_flow_response_flow.py`
  - Do: (1) In `state.py`, add `patient_flow_state_id: Optional[UUID] = None` param to `_get_day_config`. When provided: check Redis cache `flow_override:{state_id}:days` for all overrides, on miss query all `PatientFlowOverride` rows for that state and cache as dict keyed by day string (empty dict = no overrides sentinel). Look up current day in dict: skip=True → return None, override exists → return day_config dict with `{day, send_mode: "single", messages: [{content, message_type, expects_response}]}`, no override → fall through to existing global template logic. (2) In `_flow_message_flow.py`, reorder `load_flow_context` to call `_get_or_create_flow_state` BEFORE `_get_day_config`, pass `patient_flow_state_id=flow_state.id`. Remove the old flow_state loading block that comes after day_config. (3) In `_flow_response_flow.py`, add `patient_flow_state_id=flow_state.id` kwarg to the existing `_get_day_config` call (flow_state is already loaded before it).
  - Verify: `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py').read())"` + same for the other 2 files. Grep for `patient_flow_state_id` in all 3 files.
  - Done when: `_get_day_config` checks override before global template when `patient_flow_state_id` is provided. Skip returns None. Override returns properly shaped day_config. Cache populated with miss sentinel. All 3 callers pass the kwarg. Signature backward-compatible. `ast.parse` green on all 3 files.

- [x] **T02: Inject override check in batch cron path and verify all changes** `est:40m`
  - Why: The batch cron (`process_daily_flows`) uses a completely different code path through `_process_single_patient_flow` → `_get_message_template_for_day` that never touches `_get_day_config`. Without this task, overrides only work for on-demand sends, not the daily 8AM cron — violating R106 and R107.
  - Files: `backend-hormonia/app/tasks/helpers/flow_helpers.py`
  - Do: (1) Add `_check_patient_override_for_day(flow_state_id, day, db)` helper: checks Redis cache `flow_override:{state_id}:days`, on miss queries all `PatientFlowOverride` rows (sync `db.query`), caches as dict (same format as T01), returns override config for the specific day or None. (2) In `_process_single_patient_flow`, after `flow_type_enum` is resolved and before `_get_message_template_for_day`: normalize day via `_normalize_template_day(flow_type_enum, current_day)`, call `_check_patient_override_for_day(flow_state.id, template_day, db)`. If skip=True → `_update_scheduling` + return `{status: "skipped", reason: "Day skipped by patient override"}`. If override exists → use override content directly (bypass AI personalization), create Message with override content and metadata indicating override, schedule via `send_scheduled_message.kiq`, return success with `override: True`. If no override → fall through to existing template + AI path. (3) Run comprehensive `ast.parse` verification on ALL 4 modified files (state.py, _flow_message_flow.py, _flow_response_flow.py, flow_helpers.py). Grep-verify cache key patterns, skip reasons, and kwarg presence.
  - Verify: `ast.parse` PASS on all 4 files. `grep "Day skipped by patient override" flow_helpers.py`. `grep "_check_patient_override_for_day" flow_helpers.py`. Verify cache key `flow_override:` pattern in flow_helpers.py. Verify no import cycles.
  - Done when: Both pipeline paths respect patient overrides. Skip logic works in batch path. Override content bypasses AI personalization. Cache read/write consistent with T01 and S01 invalidation pattern. `ast.parse` green on all 4 modified files.

## Files Likely Touched

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py`
- `backend-hormonia/app/services/flow/_flow_message_flow.py`
- `backend-hormonia/app/services/flow/_flow_response_flow.py`
- `backend-hormonia/app/tasks/helpers/flow_helpers.py`
