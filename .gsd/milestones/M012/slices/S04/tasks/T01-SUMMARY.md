---
id: T01
parent: S04
milestone: M012
provides:
  - Replayable verification script proving all 11 M012 DoD items
  - JSON audit artifact with per-phase pass/fail
  - R104/R105/R108/R109 validated
key_files:
  - verify-m012.sh
  - .gsd/milestones/M012/M012-VERIFY.json
key_decisions: []
patterns_established:
  - verify-m012.sh follows same pattern as verify-m011.sh (set -euo pipefail, pass/fail counters, grouped phases, summary exit code)
observability_surfaces:
  - verify-m012.sh stdout with ✅/❌ per phase and summary line
  - M012-VERIFY.json audit artifact for persistent inspection
duration: 8m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T01: Write verify-m012.sh and M012-VERIFY.json

**Added replayable verification script proving all 11 M012 DoD items — ast.parse on 9 backend files, structural grep for each feature, tsc --noEmit, vite build — plus JSON audit artifact and R104/R105/R108/R109 validated**

## What Happened

Created `verify-m012.sh` at repo root following the established M011 pattern. The script has 11 check phases:

1. **ast.parse** — validates all 9 backend Python files modified by M012
2. **Migration structure** — confirms patient_flow_overrides table and correct down_revision chain
3. **GET merge with source indicator** — verifies `source: Literal["global", "override"]` in schema and `_build_merged_days` in router
4. **PUT + Redis cache invalidation** — confirms `delete_pattern(f"flow_override:...)` in router
5. **_get_day_config prioritizes override** — checks `patient_flow_state_id` parameter (8 occurrences) and `flow_override:` cache key in state.py
6. **Skip logic** — confirms skip handling in state.py and `skipped` status in flow_helpers.py
7. **Override immutability** — verifies separate table + merge-at-read via `_build_merged_days`
8. **Frontend editor** — confirms PatientFlowOverrideEditor import and "Personalizar Fluxo" text in PatientDetailPage
9. **Future-day restriction** — validates `current_flow_day` in router, `editable` field in schema, `disabled={!day.editable}` in editor
10. **tsc --noEmit** — TypeScript compilation clean
11. **vite build** — production build succeeds (4744 modules, ~1m10s)

Script ran with 11/11 PASS, exit code 0. Created M012-VERIFY.json with all 11 phases showing `"status": "passed"`. Updated R104, R105, R108, R109 from active → validated.

Note: the plan specified `down_revision = "m011_s01"` but the actual migration uses the full revision ID `"m011_s01_patient_flow_states_index"` — script uses the real value.

## Verification

- `bash verify-m012.sh` → exit 0, 11/11 PASS
- `python3 -m json.tool < .gsd/milestones/M012/M012-VERIFY.json` → valid JSON
- `grep -c '"passed"' .gsd/milestones/M012/M012-VERIFY.json` → 11

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash verify-m012.sh` | 0 | ✅ pass | 113s |
| 2 | `python3 -m json.tool < M012-VERIFY.json` | 0 | ✅ pass | <1s |
| 3 | `grep -c '"passed"' M012-VERIFY.json` → 11 | 0 | ✅ pass | <1s |

## Diagnostics

- Run `bash verify-m012.sh` to re-verify all 11 DoD items at any time
- Inspect `cat .gsd/milestones/M012/M012-VERIFY.json | python3 -m json.tool` for per-phase audit trail
- Check requirement status: `grep -E 'R10[4589]' .gsd/REQUIREMENTS.md`

## Deviations

- Plan specified `down_revision = "m011_s01"` but actual migration uses `"m011_s01_patient_flow_states_index"` — script uses the real value (not a bug, just a shorthand in the plan)
- Plan said editor at `PatientFlowOverrideEditor.tsx` in `src/components/` but actual path is `src/features/patients/components/` — script uses the real path

## Known Issues

None

## Files Created/Modified

- `verify-m012.sh` — replayable verification script with 11 check phases covering all M012 DoD items
- `.gsd/milestones/M012/M012-VERIFY.json` — JSON audit artifact with per-phase pass/fail status
- `.gsd/milestones/M012/slices/S04/S04-PLAN.md` — T01 marked done, observability section added
- `.gsd/milestones/M012/slices/S04/tasks/T01-PLAN.md` — observability impact section added
- `.gsd/STATE.md` — updated to M012 done, R104/R105/R108/R109 validated
