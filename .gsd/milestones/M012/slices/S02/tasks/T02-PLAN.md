---
estimated_steps: 4
estimated_files: 1
---

# T02: Inject override check in batch cron path and verify all changes

**Slice:** S02 — Injeção no pipeline de envio
**Milestone:** M012

## Description

The daily batch cron `process_daily_flows` (8AM BRT) uses a completely different code path through `_process_single_patient_flow` → `_get_message_template_for_day` in `flow_helpers.py`. This path never touches `_get_day_config`. Without this task, overrides only work for on-demand sends — the most important pipeline (daily cron) would ignore them entirely, violating R106 and R107.

This task adds a sync override check helper and wires it into `_process_single_patient_flow` before the template lookup. When an override exists, its content is used directly, bypassing AI personalization (the physician already wrote the exact content they want). When skip=true, the day is skipped.

**Critical constraints:**
- `flow_helpers.py` uses **sync** `Session` (not `AsyncSession`). Override queries MUST use `db.query(PatientFlowOverride).filter(...)`, not `await db.execute(select(...))`.
- Redis access uses `get_sync_redis_client()` (same as `_get_day_config` in state.py).
- Cache key MUST be `flow_override:{flow_state.id}:days` — same key as T01 so both paths share cache.
- Override content bypasses `flow_engine.generate_flow_message()` — physician-authored content is used as-is.
- Day normalization via `_normalize_template_day` must happen BEFORE checking overrides (recurring monthly flows need cycle-adjusted day numbers).

## Steps

1. **Add `_check_patient_override_for_day` helper in flow_helpers.py** — Add import: `from app.models.flow import PatientFlowOverride` (already imports `PatientFlowState` from same module). Add helper function:
   ```python
   def _check_patient_override_for_day(
       flow_state_id: UUID, day: int, db: Session
   ) -> Optional[dict]:
       """Check for per-patient override, using Redis cache with DB fallback.
       
       Returns override dict {content, message_type, expects_response, skip}
       for the given day, or None if no override exists.
       Cache key: flow_override:{flow_state_id}:days — matches S01 invalidation.
       """
   ```
   Implementation:
   - Build cache key: `f"flow_override:{flow_state_id}:days"`
   - Try `get_sync_redis_client()` → `redis_client.get(cache_key)`
   - On cache hit: `json.loads()` → look up `str(day)` in dict → return override or None
   - On cache miss: `db.query(PatientFlowOverride).filter(PatientFlowOverride.patient_flow_state_id == flow_state_id).all()` → build dict keyed by `str(day_number)` with `{content, message_type, expects_response, skip}` per row → cache as JSON with TTL 3600 → look up `str(day)` → return override or None
   - On Redis error: warn and fall through to DB query directly
   - Log cache hit/miss at debug level
   - **Same cache format as T01** so both paths share the same cached data

2. **Wire override check into `_process_single_patient_flow`** — In the main function, after `flow_type_enum = normalize_flow_type(flow_state.flow_type)` and the "already sent today" check, before `_get_message_template_for_day`:
   
   a. Normalize the day: `template_day = _normalize_template_day(flow_type_enum, current_day)`
   
   b. Call: `override = _check_patient_override_for_day(flow_state.id, template_day, db)`
   
   c. **If override with skip=True:**
   ```python
   if override and override.get("skip"):
       logger.info(
           "Day %s skipped by patient override for patient %s",
           template_day, patient_id,
           extra={"flow_state_id": str(flow_state.id), "current_day": current_day}
       )
       _update_scheduling(flow_state, flow_type_enum, tz, db)
       db.commit()
       return {
           "status": "skipped",
           "patient_id": str(patient_id),
           "current_day": current_day,
           "reason": "Day skipped by patient override",
       }
   ```
   
   d. **If override exists (not skip):** Use override content directly, bypassing template lookup AND AI personalization:
   ```python
   if override:
       logger.info(
           "Using patient override content for day %s patient %s",
           template_day, patient_id,
           extra={"flow_state_id": str(flow_state.id)}
       )
       personalized_content = override["content"]
       # Build message metadata with override indicator
       message_metadata = {
           "generated_at": now_sao_paulo().isoformat(),
           "template_intent": "patient_override",
           "flow_context": {
               "flow_day": current_day,
               "flow_type": flow_type_enum.value,
               "flow_kind": step_data.get("flow_kind", flow_type_enum.value),
               "template_id": f"override_{flow_type_enum.value}_day_{template_day}",
               "personalized": False,
               "override": True,
           },
       }
       # Create message and schedule (same as existing non-override path)
       message = Message(
           patient_id=patient_id,
           direction=MessageDirection.OUTBOUND,
           type=MessageType.TEXT,
           content=personalized_content,
           status=MessageStatus.PENDING,
           scheduled_for=now_sao_paulo(),
           message_metadata=message_metadata,
       )
       db.add(message)
       db.flush()
       
       now_iso = now_sao_paulo().isoformat()
       flow_state.step_data = flow_state.step_data or {}
       flow_state.step_data["last_message_sent"] = now_iso
       _update_scheduling(flow_state, flow_type_enum, tz, db)
       db.commit()
       
       from app.tasks.messaging_taskiq import send_scheduled_message
       send_task_result = send_scheduled_message.kiq(str(message.id))
       task_id = str(getattr(send_task_result, "task_id", "unknown"))
       flow_state.step_data["last_task_id"] = task_id
       db.commit()
       
       return {
           "status": "success",
           "patient_id": str(patient_id),
           "current_day": current_day,
           "flow_type": flow_type_enum.value,
           "message_scheduled": True,
           "task_id": task_id,
           "override": True,
       }
   ```
   
   e. If no override → fall through to existing `_get_message_template_for_day` + AI personalization (no changes to existing code).

3. **Add `import json` at top of flow_helpers.py** if not already present. Add `UUID` import from `uuid` module if not present (flow_helpers.py already imports `UUID` from uuid module — verify). Add `from typing import Optional` if not already present.

4. **Run comprehensive verification on ALL 4 modified files:**
   - `ast.parse` on state.py, _flow_message_flow.py, _flow_response_flow.py, flow_helpers.py
   - Grep for key patterns: `flow_override:` cache key, `patient_flow_state_id` kwarg, `Day skipped by patient override`, `_check_patient_override_for_day`
   - Verify no import cycles: state.py and flow_helpers.py both import `PatientFlowOverride` from `app.models.flow` (same as existing `PatientFlowState` import — no cycle)
   - Verify cache key consistency: both T01 (`_get_day_config`) and T02 (`_check_patient_override_for_day`) use `flow_override:{state_id}:days` — matches S01 invalidation pattern `flow_override:{state_id}:*`

## Must-Haves

- [ ] `_check_patient_override_for_day` helper uses sync `db.query()` (not async)
- [ ] Override with `skip=True` returns `{status: "skipped", reason: "Day skipped by patient override"}` in batch path
- [ ] Override content used directly — bypasses `flow_engine.generate_flow_message()` and `_get_message_template_for_day`
- [ ] `_normalize_template_day` applied before override check (recurring monthly flows need adjusted day)
- [ ] Redis cache key `flow_override:{flow_state_id}:days` — same key as T01, matches S01 invalidation
- [ ] Message metadata includes `"override": True` and `"personalized": False` when using override
- [ ] `ast.parse` PASS on all 4 modified files (state.py, _flow_message_flow.py, _flow_response_flow.py, flow_helpers.py)

## Verification

- `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/helpers/flow_helpers.py').read())"` — PASS
- `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py').read())"` — PASS (no regression from T01)
- `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/_flow_message_flow.py').read())"` — PASS (no regression from T01)
- `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/_flow_response_flow.py').read())"` — PASS (no regression from T01)
- `grep "Day skipped by patient override" backend-hormonia/app/tasks/helpers/flow_helpers.py` — present
- `grep "_check_patient_override_for_day" backend-hormonia/app/tasks/helpers/flow_helpers.py` — present
- `grep "flow_override:" backend-hormonia/app/tasks/helpers/flow_helpers.py` — cache key present
- `grep '"override": True' backend-hormonia/app/tasks/helpers/flow_helpers.py` — present in metadata
- `grep "patient_flow_state_id" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — at least 3 occurrences
- `grep "patient_flow_state_id=flow_state.id" backend-hormonia/app/services/flow/_flow_message_flow.py` — present

## Observability Impact

- Signals added: `logger.info("Day %s skipped by patient override for patient %s")`, `logger.info("Using patient override content for day %s patient %s")` with flow_state_id extra
- How a future agent inspects this: Check `message_metadata.flow_context.override` field on Message rows to see which messages came from overrides vs templates. Redis key `flow_override:{state_id}:days` shows cached override state.
- Failure state exposed: Redis cache errors logged as warnings; DB query fallback keeps pipeline running. Message metadata records `personalized: False, override: True` for audit trail.

## Inputs

- `backend-hormonia/app/tasks/helpers/flow_helpers.py` — Current `_process_single_patient_flow` using only `_get_message_template_for_day`
- `backend-hormonia/app/models/flow.py` — `PatientFlowOverride` model from S01
- T01 output: `_get_day_config` in state.py with override injection (verify ast.parse still passes)
- T01 output: `_flow_message_flow.py` and `_flow_response_flow.py` with `patient_flow_state_id` kwarg
- S01 summary: Cache invalidation pattern is `flow_override:{state_id}:*`, override model has columns: patient_flow_state_id, day_number, content, message_type, expects_response, skip

## Expected Output

- `backend-hormonia/app/tasks/helpers/flow_helpers.py` — `_check_patient_override_for_day` helper + override/skip logic wired into `_process_single_patient_flow` before template lookup
- All 4 modified files pass `ast.parse`
- Both pipeline paths (on-demand via T01, batch cron via T02) now respect patient overrides with consistent caching
