# S04: Verificação integrada

**Goal:** Replayable bash script proves all 11 M012 Definition of Done items, consolidating S01–S03 deliverables into a single verifiable artifact.
**Demo:** `bash verify-m012.sh` exits 0 with all checks PASS. `M012-VERIFY.json` records each phase status.

## Must-Haves

- `verify-m012.sh` covers all 11 DoD items from the M012 roadmap
- Script exits 0 when all pass, non-zero on any failure
- `M012-VERIFY.json` records phase-level pass/fail for audit trail
- `ast.parse` green on all backend files modified by M012
- Structural grep checks for each DoD item (migration, model, schemas, API, pipeline, cache, skip, frontend)
- `tsc --noEmit` green
- `vite build` green

## Proof Level

- This slice proves: final-assembly
- Real runtime required: no (static checks + build only)
- Human/UAT required: no

## Verification

- `bash verify-m012.sh` exits 0 with all phases PASS
- `cat M012-VERIFY.json` shows all phases with `"status": "passed"`
- R104, R105, R108, R109 validation evidence present in script output

## Integration Closure

- Upstream surfaces consumed: all S01 files (migration, model, schemas, router, __init__), all S02 files (state.py, _flow_message_flow.py, _flow_response_flow.py, flow_helpers.py), all S03 files (usePatientFlowOverrides.ts, PatientFlowOverrideEditor.tsx, PatientDetailPage.tsx)
- New wiring introduced in this slice: none — verification only
- What remains before the milestone is truly usable end-to-end: nothing — S04 is terminal

## Tasks

- [x] **T01: Write verify-m012.sh and M012-VERIFY.json** `est:25m`
  - Why: Single task produces the replayable verification script that proves all 11 M012 DoD items and the JSON result artifact. This is the only deliverable of S04.
  - Files: `verify-m012.sh`, `.gsd/milestones/M012/M012-VERIFY.json`
  - Do: Write bash script with set -euo pipefail, pass/fail counters, 4 phases (ast.parse on 9 backend files, structural grep for each DoD item, tsc --noEmit, vite build). Run script to confirm all pass. Write M012-VERIFY.json recording each phase status. Update requirements R104/R105/R108/R109 to validated.
  - Verify: `bash verify-m012.sh` exits 0, `M012-VERIFY.json` has all phases passed
  - Done when: Script exits 0, JSON artifact exists, all 4 active requirements validated

## Observability / Diagnostics

- **Verification script output**: `bash verify-m012.sh` prints pass/fail per check group with ✅/❌ prefixes and a summary line. Non-zero exit on any failure.
- **JSON audit artifact**: `.gsd/milestones/M012/M012-VERIFY.json` records each phase with status/command/summary. Inspectable via `python3 -m json.tool`.
- **Requirement status**: R104, R105, R108, R109 updated to `validated` in REQUIREMENTS.md when all checks pass.
- **Failure visibility**: Script uses `set -euo pipefail`. Each phase independently reports pass/fail, so partial failures are visible without re-running. JSON artifact preserves the last run's results.
- **Redaction**: No secrets or PII involved — all checks are static analysis and build verification.

## Files Likely Touched

- `verify-m012.sh`
- `.gsd/milestones/M012/M012-VERIFY.json`
