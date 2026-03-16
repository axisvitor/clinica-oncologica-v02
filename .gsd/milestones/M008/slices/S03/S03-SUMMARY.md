---
id: S03
parent: M008
milestone: M008
provides:
  - flow_kinds with kind_key onboarding, daily_follow_up, quiz_mensal seeded and active in DB
  - flow_template_versions with JSONB steps containing real clinical content, send_mode, and expects_response
  - EnhancedTemplateLoader.get_message_for_day() returns content for all onboarding days (1,2,3,5,7,9,11,13,15) and daily_follow_up days (16,18,20,...,44,45)
  - Verification scripts for template loading and metadata validation
requires:
  - slice: S01
    provides: Postgres with schema at Alembic head including migration 9b4e2d1c7f66
affects:
  - S04
key_files:
  - backend-hormonia/alembic/versions/9b4e2d1c7f66_sync_canonical_flow_templates_from_snapshots.py
  - backend-hormonia/app/services/template_loader_pkg/loader.py
  - backend-hormonia/scripts/verify_templates.py
  - backend-hormonia/scripts/verify_template_metadata.py
key_decisions:
  - No migration or code fix needed — existing migration 9b4e2d1c7f66 already seeds all three flow kinds with correct canonical kind_keys and full clinical content from markdown snapshots
patterns_established:
  - Verification scripts in backend-hormonia/scripts/ for template seeding validation
observability_surfaces:
  - EnhancedTemplateLoader logs INFO on successful DB load (flow_type + version), WARNING on cache miss/expired, ERROR on load failure
  - loader.get_cache_stats() returns dict with cache_size, expired_entries, database_enabled
  - SQL: SELECT kind_key, display_name, is_active FROM flow_kinds ORDER BY kind_key
  - get_message_for_day() returns None gracefully for missing flows/days (no crash), logs WARNING
drill_down_paths:
  - .gsd/milestones/M008/slices/S03/tasks/T01-SUMMARY.md
duration: 15m
verification_result: passed
completed_at: 2026-03-16
---

# S03: Templates clínicos semeados

**All three canonical flow_kinds seeded with real clinical content — EnhancedTemplateLoader verified end-to-end for onboarding (9 days) and daily follow-up (16 days)**

## What Happened

Verified that migration `9b4e2d1c7f66` had already run correctly during S01's `alembic upgrade head`, seeding all three canonical flow_kinds (`onboarding`, `daily_follow_up`, `quiz_mensal`) from the markdown snapshot files. No migration fixes or code changes were needed.

Template step counts match the clinical protocol:
- **Onboarding v1**: 9 steps (days 1,2,3,5,7,9,11,13,15) — gap days are intentional per the clinical protocol
- **Daily Follow-Up v1**: 16 steps (days 16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,45)
- **Quiz Mensal v1**: 9 steps (days 1,4,8,11,15,18,22,26,30)

Ran `EnhancedTemplateLoader.get_message_for_day()` against every expected day — all return real clinical content with correct `send_mode` and `expects_response` metadata. Failure paths verified: nonexistent flow types and out-of-range days return `None` without crashing.

Created two verification scripts (`verify_templates.py`, `verify_template_metadata.py`) for re-running checks against the live database.

## Verification

**SQL checks (all pass):**
- `SELECT kind_key FROM flow_kinds ORDER BY kind_key` → `daily_follow_up, onboarding, quiz_mensal` ✅
- `SELECT template_name, jsonb_array_length(steps) FROM flow_template_versions WHERE is_active = true` → Daily Follow-Up v1 (16), Onboarding v1 (9), Quiz Mensal v1 (9) ✅

**Template loader checks (all pass):**
- `verify_templates.py`: all onboarding days (1-15) and daily_follow_up days (16-45) return content ✅
- `verify_template_metadata.py`: send_mode and expects_response match snapshot values ✅
- Spot checks: onboarding day 1 → sequential_auto, day 3 → wait_response; daily day 16 → single/False, day 18 → single/True ✅

**Failure path checks (pass):**
- `get_message_for_day("nonexistent_flow", 1)` → `None` with WARNING log, no crash ✅
- `get_message_for_day("onboarding", 99)` → `None`, no crash ✅

## Requirements Advanced

- R069 — Verified onboarding templates (9 days) exist in DB with real clinical content, correct send_mode and expects_response
- R074 — Verified daily_follow_up templates (16 days, 16-45) exist in DB with real clinical content, correct metadata

## Requirements Validated

- R069 — Templates de onboarding (15 dias) com conteúdo clínico real: proven by SQL query showing 9 onboarding steps seeded, and EnhancedTemplateLoader returning clinical content for all protocol days (1,2,3,5,7,9,11,13,15) with correct send_mode and expects_response
- R074 — Templates de daily follow-up (dia 16-45) com conteúdo: proven by SQL query showing 16 daily_follow_up steps seeded, and EnhancedTemplateLoader returning clinical content for all protocol days (16,18,20,...,44,45) with correct send_mode and expects_response

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

None — migration had already run correctly, no code changes needed.

## Known Limitations

- Not all calendar days have messages — onboarding has 9 steps across 15 calendar days, daily follow-up has 16 steps across 30 calendar days. Gap days are intentional per the clinical protocol, but `process_daily_flows` must handle "no template for today" gracefully (returns None → skip sending).
- Quiz mensal templates exist but are out of scope for end-to-end proof in M008 (R075 out-of-scope).

## Follow-ups

- none

## Files Created/Modified

- `backend-hormonia/scripts/verify_templates.py` — verification script for template loader end-to-end
- `backend-hormonia/scripts/verify_template_metadata.py` — verification script for send_mode and expects_response per day
- `.gsd/milestones/M008/slices/S03/S03-PLAN.md` — added observability/diagnostics section

## Forward Intelligence

### What the next slice should know
- Not every calendar day has a template step. Onboarding covers days 1,2,3,5,7,9,11,13,15. Daily follow-up covers days 16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,45. `get_message_for_day()` returns `None` for gap days — `process_daily_flows` must handle this as "nothing to send today" not as an error.
- `send_mode` values include `sequential_auto`, `wait_response`, and `single`. The sequencing engine in `SequentialMessageHandler` uses these to determine dispatch behavior — verify that `process_daily_flows` correctly interprets all three modes.

### What's fragile
- Template cache in EnhancedTemplateLoader uses in-memory caching with TTL — if the process restarts mid-flow, cache is cold and the next `get_message_for_day()` call hits the DB. Not a bug, but worth knowing for debugging timing issues.

### Authoritative diagnostics
- `backend-hormonia/scripts/verify_templates.py` — re-run against live DB to confirm template seeding state
- `backend-hormonia/scripts/verify_template_metadata.py` — re-run to inspect send_mode/expects_response per day
- SQL: `SELECT kind_key, display_name, is_active FROM flow_kinds ORDER BY kind_key` — fastest check for flow kinds

### What assumptions changed
- Original plan assumed migration might have failed or kind_keys might be wrong (`initial_15_days` vs `onboarding`) — actually, migration ran correctly with canonical kind_keys from the start. No fixes were needed.
