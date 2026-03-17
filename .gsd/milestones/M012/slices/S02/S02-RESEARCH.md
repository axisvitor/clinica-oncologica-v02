# S02: Injeção no pipeline de envio — Research

**Date:** 2026-03-17
**Depth:** Targeted
**Requirements:** R106 (primary owner), R107 (primary owner)

## Summary

The injection of per-patient overrides into the daily send pipeline requires modifying **two separate code paths**, not one. The roadmap identifies `_get_day_config` in `sequential_message_handler_pkg/state.py` as the single injection point, but the primary batch cron job (`process_daily_flows`) uses a completely different path through `_process_single_patient_flow` in `flow_helpers.py` → `TemplateLoaderService` — it never touches `_get_day_config`.

Both paths must respect overrides for R106 and R107 to be delivered. The `_get_day_config` path covers `send_flow_day_for_patient` (on-demand) and `handle_response_and_continue` (response flow). The `_process_single_patient_flow` path covers the daily cron. Skip logic is naturally handled: `_get_day_config` returning `None` already causes `load_flow_context` to emit `status: "skip"`, and in `flow_helpers.py` the absence of a template already returns `status: "skipped"`.

S01 already provides: `PatientFlowOverride` model, `patient_flow_overrides` table, cache invalidation on PUT via `cache.delete_pattern(f"flow_override:{flow_state.id}:*")`, and the GET/PUT API endpoints.

## Recommendation

Inject override lookup in both pipeline paths:

1. **`_get_day_config` (state.py)** — Add optional `patient_flow_state_id` parameter. When provided, check Redis cache `flow_override:{patient_flow_state_id}:day:{day}` first, then query `patient_flow_overrides` table. If override has `skip=true`, return `None`. If override exists, return a day_config dict built from override fields. Fall through to existing global template logic if no override. Cache the override (or a "miss" sentinel) with same TTL pattern.

2. **`_process_single_patient_flow` (flow_helpers.py)** — After loading `flow_state` but before calling `_get_message_template_for_day`, query `patient_flow_overrides` for `(flow_state.id, current_day)`. If override with `skip=true`, return `status: "skipped", reason: "Day skipped by patient override"`. If override exists, construct a synthetic `MessageTemplate`-like object from override content, bypassing TemplateLoaderService for that day.

3. **Update callers** of `_get_day_config` — In `load_flow_context` (`_flow_message_flow.py`), reorder to load `flow_state` **before** calling `_get_day_config` so we can pass `flow_state.id`. In `_flow_response_flow.py`, the `flow_state` is already loaded before the call.

## Implementation Landscape

### Key Files

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — **Primary injection.** `_get_day_config(flow_kind, day)` gets an optional `patient_flow_state_id` param. Override query + Redis cache added before the existing global template logic. Currently uses `get_sync_redis_client()` for cache.
- `backend-hormonia/app/services/flow/_flow_message_flow.py` — **Caller update.** `load_flow_context()` currently calls `_get_day_config` at line ~55 before loading `flow_state` at line ~75. Must reorder: load flow_state first, then call `_get_day_config(flow_kind, day_number, patient_flow_state_id=flow_state.id)`.
- `backend-hormonia/app/services/flow/_flow_response_flow.py` — **Caller update.** Calls `handler._get_day_config(flow_kind, current_day)`. The `flow_state` is already loaded via `_load_flow_state` before this call. Just add `patient_flow_state_id=flow_state.id` kwarg.
- `backend-hormonia/app/tasks/helpers/flow_helpers.py` — **Second pipeline path.** `_process_single_patient_flow()` uses `_get_message_template_for_day(db, flow_type_enum, current_day)` via `TemplateLoaderService`. Must add override check after flow_state is available (~line 290). The flow_state is already in scope.
- `backend-hormonia/app/models/flow.py` — S01 already added `PatientFlowOverride` model (on `milestone/M012` branch). Import it in state.py and flow_helpers.py for override queries.
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py` — S01's PUT endpoint already invalidates cache with `cache.delete_pattern(f"flow_override:{flow_state.id}:*")`. The new override cache keys in `_get_day_config` must match this pattern.

### Two Pipeline Paths (Critical Architecture Finding)

**Path A — Batch cron (primary daily path):**
```
process_daily_flows (cron 8AM BRT)
  → _process_single_patient_flow_by_id (flow_helpers.py)
    → _process_single_patient_flow
      → _get_message_template_for_day(db, flow_type_enum, current_day)
        → TemplateLoaderService.get_template_for_day()
      → flow_engine.generate_flow_message() (AI personalization)
      → Message(...) + send_scheduled_message.kiq()
```
Does NOT use `_get_day_config`. Uses sync DB (`Session`), not `AsyncSession`.

**Path B — On-demand per-patient:**
```
send_flow_day_for_patient (on-demand task)
  → SequentialMessageHandler.send_day_messages()
    → run_flow_message()
      → load_flow_context()
        → handler._get_day_config(flow_kind, day_number)
      → dispatch_send_mode() → _send_all_sequential / _send_wait_each / etc.
```
Also used by response flow: `handle_response_and_continue` → `_flow_response_flow.py` → `_get_day_config`.

### Build Order

1. **`_get_day_config` override injection (state.py)** — This is the core change. Add override lookup before global template, using `patient_flow_state_id`. Override with `skip=true` → return `None`. Override without skip → return override as day_config dict (same shape: `{day, content, messages: [{content, expects_response, message_type}], send_mode}`). Cache at `flow_override:{patient_flow_state_id}:day:{day}`.

2. **Caller updates (_flow_message_flow.py, _flow_response_flow.py)** — Pass `patient_flow_state_id` to `_get_day_config`. In `load_flow_context`, reorder flow_state loading before `_get_day_config` call.

3. **Batch path injection (flow_helpers.py)** — In `_process_single_patient_flow`, after flow_state is available, query override. Skip or substitute content. Uses sync DB, so override query must be sync (`db.query(PatientFlowOverride)...`).

4. **Verification** — `ast.parse` on all modified files. Verify skip logic returns `None`/skip. Verify override content is used instead of global. Verify cache key matches S01's invalidation pattern.

### Verification Approach

- `python -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py').read())"` — repeat for all modified files
- Verify `_get_day_config` signature is backward-compatible (`patient_flow_state_id` defaults to `None`)
- Verify cache key pattern: `flow_override:{patient_flow_state_id}:day:{day}` — matches S01's invalidation `flow_override:{flow_state.id}:*`
- Verify skip returns `None` from `_get_day_config` (triggers existing "skip" handling in load_flow_context)
- Verify `_process_single_patient_flow` returns `status: "skipped"` when override has skip=true
- Verify no import cycle: state.py importing `PatientFlowOverride` from `app.models.flow` (same import as existing `PatientFlowState`)

## Constraints

- `_get_day_config` signature must remain backward-compatible — `patient_flow_state_id` must default to `None` so existing callers don't break (even if we update all known callers, tests mock `_get_day_config` with `(flow_kind, day)` signature).
- `_process_single_patient_flow` in flow_helpers.py uses **sync** `Session` (not `AsyncSession`). Override query here must use `db.query(PatientFlowOverride).filter(...)` (sync ORM), not `await db.execute(select(...))`.
- `_get_day_config` uses `get_sync_redis_client()` for cache. The S01 PUT endpoint uses `GenericRedisCache` (wraps sync redis via `get_generic_cache`). Both ultimately hit the same Redis instance via `RedisManager`, so cache keys will match.
- Override day_config must match the shape expected by `validate_day_config()` in `config_validation.py` — needs at minimum `{messages: [{content, ...}]}` structure, not just flat `{content, ...}`.
- Tests that mock `_get_day_config` (at least 4 test files) use `AsyncMock(return_value=day_config)` or `AsyncMock(side_effect=lambda kind, day: ...)` — the new optional kwarg won't break these because `**kwargs` passes through.

## Common Pitfalls

- **Forgetting Path A** — Only injecting in `_get_day_config` misses the batch `process_daily_flows` cron path entirely. Both paths must be covered.
- **Reorder dependency in load_flow_context** — `_get_day_config` is currently called BEFORE `_get_or_create_flow_state`. Moving flow_state loading earlier changes the order of DB calls. If `_get_day_config` returns None (skip), the flow_state was loaded unnecessarily but harmlessly. If `_get_or_create_flow_state` creates a new state, that creation must not affect the skip decision.
- **Override day_config shape** — The override stores flat fields (`content`, `message_type`, `expects_response`). But `_get_day_config` callers expect a day_config dict with nested `messages` array. The override must be transformed: `{day: N, send_mode: "single", messages: [{content: ..., message_type: ..., expects_response: ...}]}`.
- **Cache miss sentinel** — Without a "no override" sentinel, every patient without overrides triggers a DB query on every `_get_day_config` call. Use a sentinel value like `json.dumps({"_no_override": true})` in Redis with same TTL.
