---
id: T01
parent: S02
milestone: M012
provides:
  - Per-patient override lookup in _get_day_config with Redis cache and skip logic
  - Callers in both on-demand pipeline paths pass patient_flow_state_id
key_files:
  - backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py
  - backend-hormonia/app/services/flow/_flow_message_flow.py
  - backend-hormonia/app/services/flow/_flow_response_flow.py
key_decisions:
  - Override lookup uses same 3600s TTL as global template cache
  - Empty dict {} cached as miss sentinel to avoid repeated DB queries for patients without overrides
  - Override day_config uses send_mode "single" since overrides are single-message by design
patterns_established:
  - Override cache key pattern flow_override:{state_id}:days matches S01 invalidation glob flow_override:{state_id}:*
  - Redis errors in override path logged as warnings with transparent fallback to DB — never fail the pipeline
observability_surfaces:
  - logger.debug("Override cache hit for flow_state %s") on Redis cache hit
  - logger.debug("Override cache miss for flow_state %s, querying DB") on Redis cache miss
  - logger.info("Day %s skipped by patient override for flow_state %s") when skip=True
  - logger.warning("Redis override cache error (falling back to DB)") on Redis failure
  - logger.warning("Failed to query patient overrides (falling back to global)") on DB failure
duration: 12m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T01: Inject override lookup in `_get_day_config` and update on-demand callers

**Added per-patient override lookup to `_get_day_config` with Redis cache, skip logic, and miss sentinel; reordered `load_flow_context` to load flow_state first; both on-demand callers now pass `patient_flow_state_id`.**

## What Happened

Modified three files to inject patient-level override support into the on-demand pipeline:

1. **state.py** — Extended `_get_day_config` with optional `patient_flow_state_id` parameter. When provided, checks Redis cache `flow_override:{state_id}:days` first. On cache miss, queries all `PatientFlowOverride` rows for the state and caches as a dict keyed by day number string. Empty dict `{}` is cached as a miss sentinel. Override with `skip=True` returns `None` (triggering existing skip handling). Found override returns a properly shaped day_config `{day, send_mode: "single", messages: [{content, message_type, expects_response}]}`. No override for the specific day falls through to the existing global template logic. Redis errors are logged as warnings with transparent fallback.

2. **_flow_message_flow.py** — Reordered `load_flow_context` to call `_get_or_create_flow_state` BEFORE `_get_day_config` (was after). This lets us pass `patient_flow_state_id=flow_state.id` to the config lookup. Removed the duplicate flow_state loading block that previously appeared after day_config validation.

3. **_flow_response_flow.py** — Added `patient_flow_state_id=getattr(flow_state, "id", None)` kwarg to the existing `_get_day_config` call. `flow_state` was already loaded before this call, so no reordering needed.

## Verification

- `ast.parse` PASS on all 3 modified files
- `patient_flow_state_id` appears 8 times in state.py (≥3 required)
- `patient_flow_state_id=flow_state.id` present in `_flow_message_flow.py`
- `patient_flow_state_id=getattr(flow_state, "id", None)` present in `_flow_response_flow.py`
- Cache key pattern `flow_override:{patient_flow_state_id}:days` present in state.py
- `send_mode` in override return shape confirmed in state.py
- Failure-path logging: 6 warning/fallback references in state.py

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -c "import ast; ast.parse(open('...state.py').read())"` | 0 | ✅ pass | 0.9s |
| 2 | `python3 -c "import ast; ast.parse(open('..._flow_message_flow.py').read())"` | 0 | ✅ pass | 0.9s |
| 3 | `python3 -c "import ast; ast.parse(open('..._flow_response_flow.py').read())"` | 0 | ✅ pass | 0.9s |
| 4 | `grep -c "patient_flow_state_id" ...state.py` → 8 | 0 | ✅ pass | <0.1s |
| 5 | `grep "patient_flow_state_id=flow_state.id" ..._flow_message_flow.py` | 0 | ✅ pass | <0.1s |
| 6 | `grep "patient_flow_state_id=" ..._flow_response_flow.py` | 0 | ✅ pass | <0.1s |
| 7 | `grep "flow_override:" ...state.py` | 0 | ✅ pass | <0.1s |
| 8 | `grep "send_mode" ...state.py` | 0 | ✅ pass | <0.1s |
| 9 | `grep -c "warning\|Warning\|fallback" ...state.py` → 6 | 0 | ✅ pass | <0.1s |
| S-V1 | ast state.py | 0 | ✅ pass | — |
| S-V2 | ast _flow_message_flow.py | 0 | ✅ pass | — |
| S-V3 | ast _flow_response_flow.py | 0 | ✅ pass | — |
| S-V4 | ast flow_helpers.py | 0 | ✅ pass (pre-existing, T02 not applied) | — |
| S-V5 | patient_flow_state_id count ≥3 | 0 | ✅ pass (8) | — |
| S-V6 | flow_override: in state.py | 0 | ✅ pass | — |
| S-V7 | kwarg in message_flow | 0 | ✅ pass | — |
| S-V8 | kwarg in response_flow | 0 | ✅ pass | — |
| S-V9 | skip in flow_helpers | — | ⏳ T02 | — |
| S-V10 | helper in flow_helpers | — | ⏳ T02 | — |
| S-V11 | failure-path logging ≥1 | 0 | ✅ pass (6) | — |

## Diagnostics

- **Redis cache**: `redis-cli GET flow_override:{state_id}:days` — shows JSON dict of overrides keyed by day number, or `{}` for no overrides (miss sentinel)
- **Override skip**: `logger.info("Day %s skipped by patient override for flow_state %s")` logged when skip=True
- **Cache errors**: Logged as `logger.warning("Redis override cache error (falling back to DB)")` — never fails the pipeline
- **DB query errors**: Logged as `logger.warning("Failed to query patient overrides (falling back to global)")` — falls through to global template

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — Added override lookup block to `_get_day_config` with Redis cache, DB fallback, skip logic, and miss sentinel
- `backend-hormonia/app/services/flow/_flow_message_flow.py` — Reordered `load_flow_context` to load flow_state before `_get_day_config`; passes `patient_flow_state_id=flow_state.id`
- `backend-hormonia/app/services/flow/_flow_response_flow.py` — Passes `patient_flow_state_id=getattr(flow_state, "id", None)` to `_get_day_config`
