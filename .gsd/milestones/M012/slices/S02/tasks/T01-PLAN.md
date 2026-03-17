---
estimated_steps: 5
estimated_files: 3
---

# T01: Inject override lookup in `_get_day_config` and update on-demand callers

**Slice:** S02 — Injeção no pipeline de envio
**Milestone:** M012

## Description

Modify `_get_day_config` in `state.py` to check per-patient overrides (stored in `patient_flow_overrides` table, created by S01) before falling back to the global template. Update both callers (`load_flow_context` in `_flow_message_flow.py` and `load_response_context` in `_flow_response_flow.py`) to pass `patient_flow_state_id` so overrides can be looked up.

This covers R106 (override consulted before global template with cache) and R107 (skip=true returns None, triggering existing skip handling) for the on-demand pipeline path (Path B: `send_flow_day_for_patient` and `handle_response_and_continue`).

**Critical constraints:**
- `patient_flow_state_id` MUST default to `None` for backward compatibility — existing test mocks use `AsyncMock(return_value=day_config)` or `AsyncMock(side_effect=lambda kind, day: ...)`.
- Override day_config MUST have `{day: N, send_mode: "single", messages: [{content, message_type, expects_response}]}` shape to pass `validate_day_config()`.
- `_get_day_config` uses `get_sync_redis_client()` for Redis (same as existing code).
- Cache key MUST be `flow_override:{patient_flow_state_id}:days` — matches S01 invalidation pattern `flow_override:{state_id}:*`.
- Store a miss sentinel (empty dict `{}`) to avoid DB queries for patients without overrides.
- In `_flow_message_flow.py`, `load_flow_context` currently calls `_get_day_config` at ~line 61 BEFORE `_get_or_create_flow_state` at ~line 102. MUST reorder: load flow_state first, then call `_get_day_config`.

## Steps

1. **Modify `_get_day_config` signature in state.py** — Add `patient_flow_state_id: Optional[UUID] = None` parameter. Add imports: `from app.models.flow import PatientFlowOverride` (same module as existing `PatientFlowState` import). At the top of the method, before the existing global template cache logic, add override lookup block:
   - If `patient_flow_state_id` is not None:
     - Build cache key: `f"flow_override:{patient_flow_state_id}:days"`
     - Try Redis GET for this key
     - On cache hit: parse JSON into dict. If empty dict → no overrides, fall through to global.
     - On cache miss: query `PatientFlowOverride` rows for this `patient_flow_state_id` using async `self.db.execute(select(PatientFlowOverride).filter(...))`. Build dict keyed by `str(day_number)` with value `{content, message_type, expects_response, skip}`. Cache as JSON with same TTL (3600s). Cache empty dict as sentinel if no rows found.
     - Look up `str(day)` in the override dict:
       - If found with `skip=True` → `logger.info("Day %s skipped by patient override for flow_state %s", day, patient_flow_state_id)` → return `None`
       - If found → build day_config: `{"day": day, "send_mode": "single", "messages": [{"content": override["content"], "message_type": override.get("message_type", "question"), "expects_response": override.get("expects_response", False)}]}` → return it
       - If not found → fall through to existing global template logic

2. **Reorder `load_flow_context` in `_flow_message_flow.py`** — Currently the function:
   - Validates state (line ~44)
   - Gets patient (line ~54)
   - Calls `_get_day_config(flow_kind, day_number)` (line ~61)
   - Validates day_config (line ~73)
   - Loads flow_state via `_get_or_create_flow_state` (line ~102)
   
   Must change to:
   - Validates state
   - Gets patient
   - Loads flow_state via `_get_or_create_flow_state` — MOVE this BEFORE `_get_day_config`
   - If not flow_state → return error
   - Calls `_get_day_config(flow_kind, day_number, patient_flow_state_id=flow_state.id)`
   - Validates day_config
   - Rest of the function continues using the already-loaded flow_state (remove the old loading block)
   
   **Important:** After moving flow_state loading earlier, the existing code block that loads flow_state (~line 102-111) and processes step_data (~line 112+) must be adapted. The flow_state is now already loaded; remove the duplicate load. Keep the step_data processing as-is.

3. **Update caller in `_flow_response_flow.py`** — In `load_response_context`, the `flow_state` is already loaded via `handler.flow_state_repo.get_active_flow(patient_id)` at ~line 55 before `_get_day_config` is called at ~line 74. Simply change:
   ```python
   day_config = await handler._get_day_config(flow_kind, current_day)
   ```
   to:
   ```python
   day_config = await handler._get_day_config(flow_kind, current_day, patient_flow_state_id=getattr(flow_state, "id", None))
   ```

4. **Add override-related logging** — Ensure structured logging for cache hit/miss and override usage:
   - `logger.debug("Override cache hit for flow_state %s", patient_flow_state_id)` on Redis cache hit
   - `logger.debug("Override cache miss for flow_state %s, querying DB", patient_flow_state_id)` on Redis cache miss
   - `logger.info("Day %s skipped by patient override for flow_state %s", day, patient_flow_state_id)` on skip

5. **Verify** — Run `ast.parse` on all 3 modified files. Grep-verify key patterns.

## Must-Haves

- [ ] `_get_day_config` signature is `(self, flow_kind: str, day: int, patient_flow_state_id: Optional[UUID] = None)` — backward compatible
- [ ] Override check happens BEFORE global template lookup (early return if override found)
- [ ] Override with `skip=True` returns `None` from `_get_day_config`
- [ ] Override day_config has correct shape: `{day, send_mode, messages: [{content, message_type, expects_response}]}`
- [ ] Redis cache key is `flow_override:{patient_flow_state_id}:days` — matches S01 invalidation pattern
- [ ] Empty dict `{}` cached as miss sentinel for patients without overrides
- [ ] `load_flow_context` loads flow_state BEFORE calling `_get_day_config` and passes `patient_flow_state_id=flow_state.id`
- [ ] `load_response_context` passes `patient_flow_state_id=flow_state.id` to `_get_day_config`
- [ ] `ast.parse` PASS on all 3 files

## Verification

- `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py').read())"` — PASS
- `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/_flow_message_flow.py').read())"` — PASS
- `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/_flow_response_flow.py').read())"` — PASS
- `grep -c "patient_flow_state_id" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — at least 3
- `grep "patient_flow_state_id=flow_state.id" backend-hormonia/app/services/flow/_flow_message_flow.py` — present
- `grep "patient_flow_state_id=" backend-hormonia/app/services/flow/_flow_response_flow.py` — present
- `grep "flow_override:" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — cache key present
- `grep "send_mode" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — override returns proper shape

## Observability Impact

- Signals added: `logger.debug("Override cache hit/miss for flow_state %s")`, `logger.info("Day %s skipped by patient override for flow_state %s")`
- How a future agent inspects this: `redis-cli GET flow_override:{state_id}:days` shows cached overrides; empty `{}` means no overrides; populated dict shows day-keyed configs
- Failure state exposed: Redis errors logged as warnings with transparent fallback to DB query — override injection never fails the pipeline

## Inputs

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — Current `_get_day_config` that only queries global templates
- `backend-hormonia/app/services/flow/_flow_message_flow.py` — `load_flow_context` that calls `_get_day_config` before loading flow_state
- `backend-hormonia/app/services/flow/_flow_response_flow.py` — `load_response_context` that calls `_get_day_config` with `(flow_kind, current_day)` only
- `backend-hormonia/app/models/flow.py` — S01 already added `PatientFlowOverride` model (import it)
- S01 summary: cache invalidation pattern is `flow_override:{state_id}:*`, DELETE+INSERT on PUT

## Expected Output

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — `_get_day_config` checks patient overrides first (Redis cache → DB fallback), returns override day_config or None for skip, falls through to global template when no override
- `backend-hormonia/app/services/flow/_flow_message_flow.py` — `load_flow_context` loads flow_state before `_get_day_config`, passes `patient_flow_state_id`
- `backend-hormonia/app/services/flow/_flow_response_flow.py` — `load_response_context` passes `patient_flow_state_id` to `_get_day_config`
