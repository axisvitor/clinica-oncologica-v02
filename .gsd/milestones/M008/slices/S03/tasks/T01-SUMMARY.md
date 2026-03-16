---
id: T01
parent: S03
milestone: M008
provides:
  - Verified flow_kinds (onboarding, daily_follow_up, quiz_mensal) seeded correctly in DB
  - Verified all template steps have send_mode and expects_response from snapshots
  - Verified EnhancedTemplateLoader loads all days end-to-end
key_files:
  - backend-hormonia/alembic/versions/9b4e2d1c7f66_sync_canonical_flow_templates_from_snapshots.py
  - backend-hormonia/app/services/template_loader_pkg/loader.py
  - backend-hormonia/scripts/verify_templates.py
  - backend-hormonia/scripts/verify_template_metadata.py
key_decisions:
  - No migration or code fix needed — existing migration 9b4e2d1c7f66 already seeds all three flow kinds with correct canonical kind_keys and full clinical content
patterns_established:
  - Verification scripts in backend-hormonia/scripts/ for template seeding validation
observability_surfaces:
  - EnhancedTemplateLoader logs INFO on successful DB load, WARNING on cache miss, ERROR on load failure
  - loader.get_cache_stats() for runtime cache inspection
  - SQL: SELECT kind_key FROM flow_kinds WHERE is_active for available flow kinds
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Verificar e corrigir seeding de templates

**Verified seeded templates — all three flow kinds exist with correct kind_keys and full clinical content loadable via EnhancedTemplateLoader**

## What Happened

Inspected the database to confirm migration `9b4e2d1c7f66` ran successfully. Found all three canonical flow_kinds (`onboarding`, `daily_follow_up`, `quiz_mensal`) present and active. Template versions contain the correct step counts matching snapshot files:

- **Onboarding v1**: 9 steps (days 1,2,3,5,7,9,11,13,15) — not every day has a message, gaps are intentional per the clinical protocol
- **Daily Follow-Up v1**: 16 steps (days 16,18,20,...,44,45)
- **Quiz Mensal v1**: 9 steps (days 1,4,8,11,15,18,22,26,30)

Ran `EnhancedTemplateLoader.get_message_for_day()` against all onboarding and daily_follow_up days — every step returns clinical content with correct `send_mode` and `expects_response` values. No migration fixes or code changes were needed.

Added observability/diagnostics section and failure-path verification to the slice plan per pre-flight requirements.

## Verification

**SQL checks (all pass):**
- `SELECT kind_key FROM flow_kinds ORDER BY kind_key` → `daily_follow_up, onboarding, quiz_mensal` ✅
- `SELECT template_name, jsonb_array_length(steps) FROM flow_template_versions WHERE is_active = true` → Daily Follow-Up v1 (16), Onboarding v1 (9), Quiz Mensal v1 (9) ✅

**Template loader checks (all pass):**
- `scripts/verify_templates.py`: all onboarding days (1-15) and daily_follow_up days (16-45) return content ✅
- `scripts/verify_template_metadata.py`: send_mode and expects_response match snapshot values ✅
- Spot checks: onboarding day 1 → sequential_auto, day 3 → wait_response; daily day 16 → single/False, day 18 → single/True ✅

**Failure path checks (pass):**
- `get_message_for_day("nonexistent_flow", 1)` → `None` with WARNING log, no crash ✅
- `get_message_for_day("onboarding", 99)` → `None`, no crash ✅

**Slice-level verification status (1 task slice — all checks run):**
- ✅ SQL: flow_kinds returns canonical keys
- ✅ SQL: template_versions show step counts
- ✅ Python: EnhancedTemplateLoader returns content for all required days
- ✅ Failure path: nonexistent flows return None gracefully

## Diagnostics

- Run `backend-hormonia/scripts/verify_templates.py` to re-verify template loading end-to-end
- Run `backend-hormonia/scripts/verify_template_metadata.py` to inspect send_mode/expects_response per day
- SQL: `SELECT kind_key, display_name, is_active FROM flow_kinds ORDER BY kind_key`
- SQL: `SELECT template_name, version_number, is_active, jsonb_array_length(steps) FROM flow_template_versions`

## Deviations

None — no fixes were needed, migration had already run correctly.

## Known Issues

None

## Files Created/Modified

- `backend-hormonia/scripts/verify_templates.py` — verification script for template loader end-to-end
- `backend-hormonia/scripts/verify_template_metadata.py` — verification script for send_mode and expects_response
- `.gsd/milestones/M008/slices/S03/S03-PLAN.md` — added observability/diagnostics section and failure-path verification
