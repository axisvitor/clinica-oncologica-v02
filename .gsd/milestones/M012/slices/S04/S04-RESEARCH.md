# S04 — Research

**Date:** 2026-03-17
**Status:** Light research — terminal verification slice using established bash verify patterns

## Summary

S04 is the terminal verification slice for M012. It produces a single replayable `verify-m012.sh` bash script that proves all 11 Definition of Done items from the milestone roadmap. All deliverables already exist and passed individual slice-level verification (S01 ast.parse, S02 grep checks, S03 tsc+vite build). S04 consolidates these into a single replayable proof artifact.

The pattern is well-established: M003 has `M003-VERIFY.json` referencing `verify-evidence-map.sh`, M006 has `M006-VERIFY.json` with 10 phases. The verify script structure (set -euo pipefail, check functions, pass/fail counters, summary) is identical across milestones. No new technology, no ambiguity.

## Recommendation

Single task: write `verify-m012.sh` that runs all checks in order and produces a JSON result file. The script should be executable from the repo root and verify each DoD item with the cheapest reliable check available (ast.parse for backend syntax, grep for structural presence, tsc/vite for frontend build).

## Implementation Landscape

### Key Files

- `backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py` — migration file, verify: exists + ast.parse + down_revision correct + table name present
- `backend-hormonia/app/models/flow.py` — model, verify: `PatientFlowOverride` class + `uq_pfo_state_day` constraint
- `backend-hormonia/app/schemas/v2/patient_overrides.py` — schemas, verify: `source: Literal["global", "override"]` + `editable: bool`
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py` — API, verify: GET/PUT endpoints + `delete_pattern` cache invalidation + `current_flow_day` editability check
- `backend-hormonia/app/api/v2/routers/patients/__init__.py` — routing, verify: `flow_overrides_router` registered before `crud_router`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — pipeline on-demand path, verify: `patient_flow_state_id` param in `_get_day_config` + cache key `flow_override:` + skip logic
- `backend-hormonia/app/services/flow/_flow_message_flow.py` — on-demand caller, verify: passes `patient_flow_state_id=flow_state.id`
- `backend-hormonia/app/services/flow/_flow_response_flow.py` — on-demand caller, verify: passes `patient_flow_state_id`
- `backend-hormonia/app/tasks/helpers/flow_helpers.py` — batch cron path, verify: `_check_patient_override_for_day` + skip + `override: True` / `personalized: False` metadata
- `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` — hook, verify: exists
- `frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx` — editor, verify: Badge imports + Global/Personalizado/Pulado + disabled gating
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` — entry point, verify: `PatientFlowOverrideEditor` import + `Personalizar Fluxo` button + `showOverrideEditor` state

### DoD → Verification Check Map

| # | DoD Item | Verification |
|---|----------|-------------|
| 1 | `patient_flow_overrides` table via Alembic | migration file exists + `patient_flow_overrides` in content + `down_revision = "m011_s01"` |
| 2 | GET returns merge with source indicator | `source: Literal["global", "override"]` in schema + `_build_merged_days` in router |
| 3 | PUT saves + invalidates Redis cache | `delete_pattern(f"flow_override:` in router |
| 4 | `_get_day_config` prioritizes override | `patient_flow_state_id` param in signature + `flow_override:` cache key in state.py |
| 5 | Skip logic for `skip=true` | `skip` in state.py override block + `skipped` status in flow_helpers.py |
| 6 | Override is fixed (not overwritten by global) | Separate table (D021) + merge at read-time (grep `_build_merged_days`) |
| 7 | PatientDetailPage has override editor | `PatientFlowOverrideEditor` import + `Personalizar Fluxo` text |
| 8 | Future-day restriction | `current_flow_day` check in router + `editable` field + `disabled={!day.editable}` in editor |
| 9 | `tsc --noEmit` + `vite build` green | Run both commands |
| 10 | `ast.parse` green on all backend files | Python ast.parse on all 9 modified files |
| 11 | No regression for patients without overrides | Miss sentinel `{}` cached in state.py + fallthrough to global template |

### Build Order

Single task — write `verify-m012.sh` + `M012-VERIFY.json`.

The script structure:
1. Header (set -euo pipefail, ROOT_DIR, counters)
2. Helper functions (pass/fail recording)
3. Phase 1: ast.parse on all 9 backend files
4. Phase 2: Structural grep checks for each DoD item
5. Phase 3: `tsc --noEmit` in frontend-hormonia
6. Phase 4: `vite build` in frontend-hormonia
7. Summary with pass/fail counts and exit code
8. Write `M012-VERIFY.json` result file

### Verification Approach

The verify script IS the verification. Run `bash verify-m012.sh` from the repo root — it exits 0 on success, non-zero on failure. The JSON result file records each phase status for audit trail.

## Constraints

- Script must run from repo root (same as all prior verify scripts)
- `tsc --noEmit` requires `node_modules` present — script should check and `npm ci` if needed (or fail with clear message)
- `ast.parse` requires Python 3 — always available in this project
- No live database or Redis needed — all checks are static (file existence, content grep, syntax parse, build)
