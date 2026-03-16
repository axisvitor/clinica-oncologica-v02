# S03: Templates clínicos semeados — UAT

**Milestone:** M008
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: Template seeding is a data contract — verified by SQL queries and Python scripts against live Postgres. No UI or real-time interaction required.

## Preconditions

- PostgreSQL running on port 5434 with `hormonia_dev` database
- Alembic head applied (including migration `9b4e2d1c7f66`)
- Backend virtualenv activated with app dependencies installed
- Working directory: `backend-hormonia/`

## Smoke Test

Run `python scripts/verify_templates.py` — should exit 0 with "ALL CHECKS PASSED ✅"

## Test Cases

### 1. Flow kinds exist with canonical kind_keys

1. Connect to PostgreSQL: `psql -h localhost -p 5434 -U hormonia -d hormonia_dev`
2. Run: `SELECT kind_key, display_name, is_active FROM flow_kinds ORDER BY kind_key;`
3. **Expected:** Three rows: `daily_follow_up`, `onboarding`, `quiz_mensal` — all with `is_active = true`

### 2. Template versions have correct step counts

1. Run: `SELECT ftv.template_name, fk.kind_key, jsonb_array_length(ftv.steps) as step_count FROM flow_template_versions ftv JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id WHERE ftv.is_active = true ORDER BY fk.kind_key;`
2. **Expected:**
   - Daily Follow-Up v1 (`daily_follow_up`): 16 steps
   - Onboarding v1 (`onboarding`): 9 steps
   - Quiz Mensal v1 (`quiz_mensal`): 9 steps

### 3. EnhancedTemplateLoader returns content for all onboarding days

1. Run: `cd backend-hormonia && python scripts/verify_templates.py`
2. **Expected:** All onboarding days (1,2,3,5,7,9,11,13,15) show "OK ✅" with clinical content snippet. Gap days (4,6,8,10,12,14) show "(no message, expected) ✅"

### 4. EnhancedTemplateLoader returns content for all daily follow-up days

1. (Same script as test 3)
2. **Expected:** All daily follow-up days (16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,45) show "OK ✅" with clinical content snippet

### 5. send_mode and expects_response match clinical protocol

1. Run: `cd backend-hormonia && python scripts/verify_template_metadata.py`
2. **Expected:**
   - Onboarding day 1: `send_mode=sequential_auto` ✅
   - Onboarding day 3: `send_mode=wait_response` ✅
   - Daily follow-up day 16: `send_mode=single`, `expects_response=False` ✅
   - Daily follow-up day 18: `send_mode=single`, `expects_response=True` ✅
   - Script exits 0 with "ALL CHECKS PASSED ✅"

### 6. Quiz mensal template loads

1. (verify_templates.py output includes Quiz Mensal section)
2. **Expected:** Quiz Mensal v1 loaded with days [1, 4, 8, 11, 15, 18, 22, 26, 30]

## Edge Cases

### Nonexistent flow type returns None

1. In Python: `loader.get_message_for_day("nonexistent_flow", 1)`
2. **Expected:** Returns `None`, logs WARNING with flow_type name, no exception raised

### Out-of-range day returns None

1. In Python: `loader.get_message_for_day("onboarding", 99)`
2. **Expected:** Returns `None`, no exception raised

### Gap day in onboarding returns None

1. In Python: `loader.get_message_for_day("onboarding", 4)`
2. **Expected:** Returns `None` — day 4 has no template step by design

## Failure Signals

- `verify_templates.py` exits with code 1 or shows "MISSING ❌" for any expected day
- `verify_template_metadata.py` shows "WRONG ❌" for any send_mode or expects_response value
- SQL query returns fewer than 3 flow_kinds or any with `is_active = false`
- `get_message_for_day()` raises an exception instead of returning None for missing data

## Requirements Proved By This UAT

- R069 — Templates de onboarding com conteúdo clínico real: tests 1-3, 5 prove content and metadata
- R074 — Templates de daily follow-up (dia 16-45) com conteúdo: tests 1-2, 4-5 prove content and metadata

## Not Proven By This UAT

- Runtime dispatch via `process_daily_flows` — that's S04's scope
- Template personalization by AI — that's S04's scope
- WhatsApp delivery of template content — that's S04's scope
- Quiz mensal end-to-end cycle — out of scope for M008 (R075)

## Notes for Tester

- The verification scripts are self-contained — run them from `backend-hormonia/` with the virtualenv active
- Gap days (no template step) are intentional per the clinical protocol, not bugs
- Template content is in Portuguese — expect clinical oncology language about hormonioterapia
