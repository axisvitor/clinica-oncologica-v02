---
id: T02
parent: S02
milestone: M012
provides:
  - Sync override lookup helper _check_patient_override_for_day for batch cron path
  - Override skip and content-direct injection in _process_single_patient_flow
  - Both pipeline paths (on-demand and batch cron) now respect patient overrides with shared Redis cache
key_files:
  - backend-hormonia/app/tasks/helpers/flow_helpers.py
key_decisions:
  - Override content bypasses AI personalization entirely — physician-authored content is used as-is
  - Message metadata marks override messages with personalized:False and override:True for audit
patterns_established:
  - Sync override helper uses same cache key flow_override:{state_id}:days as T01 async path — both share cache
  - Redis errors in batch path logged as warnings with transparent fallback to DB — never fail the pipeline
observability_surfaces:
  - logger.info("Day %s skipped by patient override for patient %s") when skip=True in batch path
  - logger.info("Using patient override content for day %s patient %s") when override content used
  - logger.warning("Redis override cache error in batch path (falling back to DB)") on Redis failure
  - logger.warning("Failed to query patient overrides in batch path (falling back to global)") on DB failure
  - message_metadata.flow_context.override=True and personalized=False on override messages
duration: 7m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T02: Inject override check in batch cron path and verify all changes

**Added sync override lookup helper and wired skip/content-direct logic into batch cron's `_process_single_patient_flow`, completing override injection in both pipeline paths.**

## What Happened

Modified `flow_helpers.py` with two changes:

1. **`_check_patient_override_for_day` helper** — Sync function that checks Redis cache `flow_override:{flow_state_id}:days` first, falls back to `db.query(PatientFlowOverride).filter(...)` on cache miss, and caches the result with 3600s TTL. Returns the override dict for the requested day or None. Same cache key and format as T01's async path so both pipeline paths share cached data. Redis errors are logged as warnings with transparent fallback to DB.

2. **Override injection in `_process_single_patient_flow`** — After the "already sent today" check and before `_get_message_template_for_day`, normalizes the day via `_normalize_template_day` then calls the override helper. Three outcomes:
   - **skip=True**: Updates scheduling, commits, returns `{status: "skipped", reason: "Day skipped by patient override"}`
   - **Override exists**: Uses override content directly (bypasses `flow_engine.generate_flow_message()` and template lookup), creates Message with `override: True` and `personalized: False` metadata, schedules via `send_scheduled_message.kiq`, returns success with `override: True`
   - **No override**: Falls through to existing template + AI personalization path unchanged

3. **Imports** — Added `import json` and `PatientFlowOverride` to existing `app.models.flow` import line.

## Verification

- `ast.parse` PASS on all 4 modified files (flow_helpers.py, state.py, _flow_message_flow.py, _flow_response_flow.py)
- All grep checks pass for cache keys, skip reasons, helper presence, kwarg passing, metadata markers
- All 11 slice-level verification checks pass (S-V1 through S-V11)

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -c "import ast; ast.parse(open('...flow_helpers.py').read())"` | 0 | ✅ pass | 0.7s |
| 2 | `python3 -c "import ast; ast.parse(open('...state.py').read())"` | 0 | ✅ pass | 0.7s |
| 3 | `python3 -c "import ast; ast.parse(open('..._flow_message_flow.py').read())"` | 0 | ✅ pass | 0.7s |
| 4 | `python3 -c "import ast; ast.parse(open('..._flow_response_flow.py').read())"` | 0 | ✅ pass | 0.7s |
| 5 | `grep "Day skipped by patient override" flow_helpers.py` | 0 | ✅ pass | <0.1s |
| 6 | `grep "_check_patient_override_for_day" flow_helpers.py` | 0 | ✅ pass | <0.1s |
| 7 | `grep "flow_override:" flow_helpers.py` | 0 | ✅ pass | <0.1s |
| 8 | `grep '"override": True' flow_helpers.py` | 0 | ✅ pass | <0.1s |
| 9 | `grep '"personalized": False' flow_helpers.py` | 0 | ✅ pass | <0.1s |
| 10 | `grep "db.query(PatientFlowOverride)" flow_helpers.py` | 0 | ✅ pass | <0.1s |
| S-V1 | ast state.py | 0 | ✅ pass | — |
| S-V2 | ast _flow_message_flow.py | 0 | ✅ pass | — |
| S-V3 | ast _flow_response_flow.py | 0 | ✅ pass | — |
| S-V4 | ast flow_helpers.py | 0 | ✅ pass | — |
| S-V5 | patient_flow_state_id count ≥3 in state.py | 0 | ✅ pass (8) | — |
| S-V6 | flow_override: in state.py | 0 | ✅ pass | — |
| S-V7 | kwarg in _flow_message_flow.py | 0 | ✅ pass | — |
| S-V8 | kwarg in _flow_response_flow.py | 0 | ✅ pass | — |
| S-V9 | Day skipped in flow_helpers.py | 0 | ✅ pass | — |
| S-V10 | _check_patient_override_for_day in flow_helpers.py | 0 | ✅ pass | — |
| S-V11 | warning/fallback count ≥1 in state.py | 0 | ✅ pass (6) | — |

## Diagnostics

- **Override messages**: Query `message_metadata->'flow_context'->>'override' = 'true'` on Messages table to find override-originated messages
- **Skip logs**: `logger.info("Day %s skipped by patient override for patient %s")` in batch cron logs
- **Cache inspection**: `redis-cli GET flow_override:{state_id}:days` — shared between on-demand (T01) and batch (T02) paths
- **Redis failures**: Logged as `logger.warning("Redis override cache error in batch path")` — never fails pipeline

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/tasks/helpers/flow_helpers.py` — Added `import json`, `PatientFlowOverride` import, `_check_patient_override_for_day` sync helper, and override skip/content-direct logic in `_process_single_patient_flow`
