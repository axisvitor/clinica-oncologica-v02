---
estimated_steps: 5
estimated_files: 2
---

# T01: Write verify-m012.sh and M012-VERIFY.json

**Slice:** S04 — Verificação integrada
**Milestone:** M012

## Description

Write the replayable verification script that proves all 11 M012 Definition of Done items, run it, and produce the JSON audit artifact. This is the sole deliverable of S04 — the terminal verification slice for the milestone.

The script follows the established project pattern (verify-m011.sh): `set -euo pipefail`, pass/fail counters, grouped phases, summary with exit code. Four phases: (1) `ast.parse` on all 9 backend files modified by M012, (2) structural grep checks for each DoD item, (3) `tsc --noEmit`, (4) `vite build`. The M012-VERIFY.json records each phase with status/command/summary.

After the script runs green, update requirements R104, R105, R108, R109 from active → validated using the gsd_update_requirement tool.

## Steps

1. Create `verify-m012.sh` at repo root with this structure:
   - Header: `#!/usr/bin/env bash`, `set -euo pipefail`, `PASS_COUNT=0`, `FAIL_COUNT=0`, `TOTAL=11`, helper functions `pass()` and `fail()`
   - **Phase 1 — ast.parse** (`[1/11]`): Run `python3 -c "import ast; ..."` on all 9 backend files:
     - `backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py`
     - `backend-hormonia/app/models/flow.py`
     - `backend-hormonia/app/schemas/v2/patient_overrides.py`
     - `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`
     - `backend-hormonia/app/api/v2/routers/patients/__init__.py`
     - `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py`
     - `backend-hormonia/app/services/flow/_flow_message_flow.py`
     - `backend-hormonia/app/services/flow/_flow_response_flow.py`
     - `backend-hormonia/app/tasks/helpers/flow_helpers.py`
   - **Phase 2 — Migration structure** (`[2/11]`): Verify migration file exists, contains `patient_flow_overrides` table name, and has correct `down_revision = "m011_s01"`
   - **Phase 3 — GET merge with source indicator** (`[3/11]`): Grep for `source: Literal["global", "override"]` in `patient_overrides.py` AND `_build_merged_days` in `flow_overrides.py`
   - **Phase 4 — PUT + Redis cache invalidation** (`[4/11]`): Grep for `delete_pattern(f"flow_override:` in `flow_overrides.py`
   - **Phase 5 — _get_day_config prioritizes override** (`[5/11]`): Grep for `patient_flow_state_id` in `state.py` signature (count ≥ 3) AND `flow_override:` cache key
   - **Phase 6 — Skip logic** (`[6/11]`): Grep for `skip` in state.py override block AND `skipped` or `skip` status in `flow_helpers.py`
   - **Phase 7 — Override immutability** (`[7/11]`): Verify separate table (D021) + merge at read-time (`_build_merged_days`)
   - **Phase 8 — PatientDetailPage has override editor** (`[8/11]`): Grep for `PatientFlowOverrideEditor` import and `Personalizar Fluxo` text in `PatientDetailPage.tsx`
   - **Phase 9 — Future-day restriction** (`[9/11]`): Grep for `current_flow_day` in router AND `editable` in schema AND `disabled` or `editable` gating in editor component
   - **Phase 10 — tsc --noEmit** (`[10/11]`): Run `cd frontend-hormonia && npx tsc --noEmit`
   - **Phase 11 — vite build** (`[11/11]`): Run `cd frontend-hormonia && npx vite build`
   - **Summary**: Print pass/fail counts, exit with `[ $FAIL_COUNT -eq 0 ]`

2. Run `bash verify-m012.sh` and confirm all 11 checks pass (exit 0).

3. Create `.gsd/milestones/M012/M012-VERIFY.json` with structure:
   ```json
   {
     "milestone": "M012",
     "verified_at": "<ISO timestamp>",
     "phases": {
       "ast_parse_backend": { "status": "passed", "command": "python3 ast.parse on 9 files", "summary": "..." },
       "migration_structure": { "status": "passed", ... },
       "get_merge_source": { "status": "passed", ... },
       "put_cache_invalidation": { "status": "passed", ... },
       "get_day_config_override": { "status": "passed", ... },
       "skip_logic": { "status": "passed", ... },
       "override_immutability": { "status": "passed", ... },
       "frontend_editor": { "status": "passed", ... },
       "future_day_restriction": { "status": "passed", ... },
       "tsc_no_emit": { "status": "passed", ... },
       "vite_build": { "status": "passed", ... }
     }
   }
   ```

4. Update requirements to validated using `gsd_update_requirement`:
   - **R104**: validated — patient_flow_overrides table exists with correct structure, ast.parse green, down_revision correct
   - **R105**: validated — GET returns merge with source indicator, PUT saves + invalidates cache, proven by grep + ast.parse
   - **R108**: validated — PatientDetailPage has "Personalizar Fluxo" button, editor with badges and future-day gating, tsc + vite build green
   - **R109**: validated — Override in separate table (D021), merge at read-time via _build_merged_days, global changes don't touch overrides

5. Commit: `verify(M012): add integrated verification script`

## Must-Haves

- [ ] `verify-m012.sh` exists at repo root and is executable
- [ ] Script covers all 11 DoD items from M012 roadmap
- [ ] `bash verify-m012.sh` exits 0
- [ ] `M012-VERIFY.json` exists with all phases showing `"status": "passed"`
- [ ] R104, R105, R108, R109 updated to validated

## Verification

- `bash verify-m012.sh` exits 0 with 11/11 PASS
- `cat .gsd/milestones/M012/M012-VERIFY.json | python3 -m json.tool` shows valid JSON with all phases passed
- `grep -c '"passed"' .gsd/milestones/M012/M012-VERIFY.json` returns 11

## Inputs

- S01 summary: migration file at `backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py`, model in `flow.py`, schemas in `patient_overrides.py`, router in `flow_overrides.py`, registration in `__init__.py`. Key patterns: `_build_merged_days`, `source: Literal["global", "override"]`, `delete_pattern(f"flow_override:`, `uq_pfo_state_day`, `current_flow_day`
- S02 summary: `_get_day_config` in `state.py` with `patient_flow_state_id` param, `flow_override:` cache key, skip logic. `_check_patient_override_for_day` in `flow_helpers.py`. Both callers updated (`_flow_message_flow.py`, `_flow_response_flow.py`)
- S03 summary: `usePatientFlowOverrides.ts` hook, `PatientFlowOverrideEditor.tsx` component, `PatientDetailPage.tsx` with "Personalizar Fluxo" button and `showOverrideEditor` state
- Prior verify pattern: `verify-m011.sh` at repo root (same structure: set -euo pipefail, pass/fail, grouped checks, summary)

## Observability Impact

- **New signals**: `verify-m012.sh` stdout produces structured pass/fail output with group labels `[N/11]` and ✅/❌ markers. Exit code 0 = all green, 1 = any failure.
- **Inspection surfaces**: `M012-VERIFY.json` is the persistent audit artifact — `cat .gsd/milestones/M012/M012-VERIFY.json | python3 -m json.tool` shows per-phase status at any time.
- **Failure state**: On any phase failure, `FAIL_COUNT > 0` triggers non-zero exit. The JSON artifact records which specific phase failed with its command and summary. Re-run `bash verify-m012.sh` to reproduce.
- **Downstream**: R104/R105/R108/R109 status in REQUIREMENTS.md transitions from `active` to `validated`, visible via `grep -E 'R10[4589]' .gsd/REQUIREMENTS.md`.

## Expected Output

- `verify-m012.sh` — replayable bash script proving all 11 M012 DoD items
- `.gsd/milestones/M012/M012-VERIFY.json` — audit artifact with per-phase pass/fail
- R104, R105, R108, R109 moved from active to validated
