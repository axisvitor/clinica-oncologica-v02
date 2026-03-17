---
id: S02
parent: M012
milestone: M012
provides:
  - Override lookup in _get_day_config (on-demand path) with Redis cache, DB fallback, skip logic, and miss sentinel
  - Override check in _process_single_patient_flow (batch cron path) with shared Redis cache
  - Both pipeline paths (on-demand + batch cron) consult patient overrides before global templates
  - Skip logic in both paths for days with skip=true
  - Override content bypasses AI personalization (physician-authored content used as-is)
requires:
  - slice: S01
    provides: PatientFlowOverride model, patient_flow_overrides table, PUT endpoint cache invalidation pattern flow_override:{state_id}:*
affects:
  - S04
key_files:
  - backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py
  - backend-hormonia/app/services/flow/_flow_message_flow.py
  - backend-hormonia/app/services/flow/_flow_response_flow.py
  - backend-hormonia/app/tasks/helpers/flow_helpers.py
key_decisions:
  - Override content bypasses AI personalization — physician-authored content used as-is with metadata override:True, personalized:False (D025)
  - Empty dict {} cached as miss sentinel with 3600s TTL to prevent repeated DB queries for patients without overrides (D026)
  - Override day_config uses send_mode "single" since overrides are single-message by design
  - Redis errors in override path logged as warnings with transparent fallback to DB — never fail the pipeline
patterns_established:
  - Override cache key flow_override:{state_id}:days shared between async (on-demand) and sync (batch cron) paths
  - S01 invalidation glob flow_override:{state_id}:* clears cache on PUT — both paths pick up changes within TTL window
  - Sync helper _check_patient_override_for_day mirrors async logic in _get_day_config for batch cron compatibility
observability_surfaces:
  - logger.debug("Override cache hit/miss for flow_state %s") in on-demand path
  - logger.info("Day %s skipped by patient override") in both paths
  - logger.info("Using patient override content for day %s patient %s") in batch path
  - logger.warning("Redis override cache error") with transparent fallback in both paths
  - message_metadata.flow_context.override=True and personalized=False on override messages
  - Redis key flow_override:{state_id}:days inspectable via redis-cli GET
drill_down_paths:
  - .gsd/milestones/M012/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M012/slices/S02/tasks/T02-SUMMARY.md
duration: 19m
verification_result: passed
completed_at: 2026-03-17
---

# S02: Injeção no pipeline de envio

**Both pipeline paths (on-demand via `_get_day_config` and batch cron via `_process_single_patient_flow`) now consult per-patient overrides before global templates, with shared Redis cache, skip logic, and miss sentinel — override content bypasses AI personalization.**

## What Happened

Two tasks injected patient-level override support into the two independent pipeline paths that send messages to patients.

**T01** extended `_get_day_config` in `state.py` with an optional `patient_flow_state_id` parameter. When provided, it checks Redis cache `flow_override:{state_id}:days` first, falls back to DB query on cache miss, and caches the result (including empty dict `{}` as miss sentinel). Override with `skip=True` returns `None` (triggering existing skip handling). Found override returns a properly shaped day_config. No override falls through to global template. Redis/DB errors are logged as warnings and fall through transparently. Both on-demand callers were updated: `load_flow_context` was reordered to load flow_state before `_get_day_config` (so it can pass the ID), and `load_response_context` adds the kwarg to its existing call.

**T02** added a sync helper `_check_patient_override_for_day` in `flow_helpers.py` for the batch cron path, sharing the same cache key and format. In `_process_single_patient_flow`, after the "already sent today" check, the override helper is called. Three outcomes: skip → update scheduling + return skipped status, override → use content directly (bypass AI personalization) + schedule via `send_scheduled_message.kiq`, no override → fall through to existing template + AI path. Override messages carry metadata `override: True` and `personalized: False` for audit.

## Verification

All 11 slice-level verification checks pass:

| # | Check | Result |
|---|-------|--------|
| S-V1 | `ast.parse` state.py | ✅ PASS |
| S-V2 | `ast.parse` _flow_message_flow.py | ✅ PASS |
| S-V3 | `ast.parse` _flow_response_flow.py | ✅ PASS |
| S-V4 | `ast.parse` flow_helpers.py | ✅ PASS |
| S-V5 | `patient_flow_state_id` count ≥3 in state.py | ✅ PASS (8) |
| S-V6 | `flow_override:` in state.py | ✅ PASS |
| S-V7 | kwarg in _flow_message_flow.py | ✅ PASS |
| S-V8 | kwarg in _flow_response_flow.py | ✅ PASS |
| S-V9 | skip reason in flow_helpers.py | ✅ PASS |
| S-V10 | `_check_patient_override_for_day` in flow_helpers.py | ✅ PASS |
| S-V11 | failure-path logging ≥1 in state.py | ✅ PASS (6) |

## Requirements Advanced

- none (both requirements fully validated by this slice)

## Requirements Validated

- R106 — `_get_day_config` consults override before global template in both on-demand callers, with Redis cache and DB fallback. Proven by ast.parse green + grep confirming 8 `patient_flow_state_id` references and kwarg passing in both callers.
- R107 — Days with `skip=true` are skipped by both pipeline paths. On-demand returns `None` (existing skip handling). Batch returns `status: "skipped"` with scheduling update. Proven by ast.parse green + grep confirming skip paths in both state.py and flow_helpers.py.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

None. Both tasks executed as planned.

## Known Limitations

- Cache TTL (3600s) means an override created via PUT will be visible in the pipeline within 1 hour even if Redis cache is stale (S01 PUT invalidation should handle this immediately, but if invalidation fails, there's a 1-hour window).
- Sync helper in batch path duplicates logic from async path — not shared code, but shared cache key and format. Changes to one must be mirrored in the other.

## Follow-ups

- none — S03 (frontend editor) and S04 (integrated verification) are already planned in the roadmap.

## Files Created/Modified

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — Extended `_get_day_config` with override lookup, Redis cache, skip logic, miss sentinel, and failure-path logging
- `backend-hormonia/app/services/flow/_flow_message_flow.py` — Reordered `load_flow_context` to load flow_state before `_get_day_config`; passes `patient_flow_state_id=flow_state.id`
- `backend-hormonia/app/services/flow/_flow_response_flow.py` — Passes `patient_flow_state_id=getattr(flow_state, "id", None)` to `_get_day_config`
- `backend-hormonia/app/tasks/helpers/flow_helpers.py` — Added `_check_patient_override_for_day` sync helper and override skip/content-direct logic in `_process_single_patient_flow`

## Forward Intelligence

### What the next slice should know
- Both pipeline paths now share Redis cache key `flow_override:{state_id}:days`. S01's PUT endpoint invalidates via glob `flow_override:{state_id}:*`. The S03 frontend editor should use the existing PUT endpoint which already handles cache invalidation.
- Override messages in the batch path carry `override: True` and `personalized: False` in metadata — S04 verification can query this to prove overrides reached the messaging layer.
- The on-demand path reorder in `load_flow_context` now loads flow_state BEFORE day_config. If any future change depends on the old ordering, it will need adjustment.

### What's fragile
- **Sync/async duplication**: `_check_patient_override_for_day` (sync, flow_helpers.py) and override block in `_get_day_config` (async, state.py) implement the same logic independently. If the cache format changes, both must be updated.
- **Day normalization**: Batch path calls `_normalize_template_day` before override lookup. On-demand path receives the day already normalized. If normalization logic changes, verify both paths still resolve the same day key.

### Authoritative diagnostics
- `redis-cli GET flow_override:{state_id}:days` — shows cached override dict (or `{}` for no overrides). This is the single source of truth for what the pipeline sees.
- `SELECT * FROM patient_flow_overrides WHERE patient_flow_state_id = ?` — ground truth for what was configured by the physician.
- Messages table: `message_metadata->'flow_context'->>'override' = 'true'` — proves override content reached the messaging layer.

### What assumptions changed
- No assumptions changed. Both pipeline paths existed as documented in the slice plan, and the injection points were where expected.
