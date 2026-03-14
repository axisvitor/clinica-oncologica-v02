# S01: Guardrails do corte canônico de runtime — UAT

**Milestone:** M004
**Written:** 2026-03-14

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 does not ship a new runtime feature. It ships an executable boundary contract, so acceptance is whether the report, gate, research map, summary handoff, and reviewer checklist all describe the same official-runtime residue surface.

## Preconditions

- The S01 handoff artifacts exist:
  - `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`
  - `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`
  - `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`
  - `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`
  - `.gsd/milestones/M004/slices/S01/S01-UAT.md`
- Backend test dependencies are installed.
- Tester understands that S01 freezes the residue boundary; it does **not** prove the runtime is already canonical.

## Smoke Test

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`.
2. Confirm the command ends with `RESULT: --report all OK`.
3. Open `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`.
4. Confirm the file lists the six category ids (`firebase_uid`, `root_legacy_session`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, `firebase_narrative`) using the `backend` / `frontend` scope names.
5. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`.
6. Confirm the command ends with `RESULT: --check all OK`.
7. **Expected:** the executable report/gate and the published slice artifacts describe the same approved boundary.

## Test Cases

### 1. Published map matches the executable boundary

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`.
2. Compare the approved files/counts in the output with `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`.
3. Open `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`.
4. Confirm the downstream ownership matches the handoff order:
   - S02 owns backend `firebase_uid` canonicalization
   - S03 owns frontend header/bearer/query emission removal
   - S04 owns root `/session/*` retirement plus backend acceptance removal
   - S05 owns adjacent `firebase_uid` and Firebase-narrative cleanup
5. **Expected:** no approved report row is missing from the research map, and the summary names the correct next-slice owner for each residue family.

### 2. Drift failures stay inspectable

1. Run `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue`.
2. Run `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name`.
3. **Expected:** both tests pass, proving the guard still emits structured failure surfaces for:
   - `category=... unexpected_file=...`
   - `category=... moved_hotspot=... anchor=...`

### 3. Out-of-scope strings stay out of the official failure surface

1. Open `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`.
2. Confirm the `out_of_scope_exclusions` list still contains exactly:
   - `schema_model_residue`
   - `historical_docs_tests`
   - `vendor_or_unrelated_session_strings`
3. Open `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` and confirm the exclusions table matches those ids, reasons, and path families.
4. Re-run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`.
5. **Expected:** the exclusions remain documented and the gate stays green without accidentally pulling schema/tests/WuzAPI/public-session strings into the official runtime failure surface.

## Edge Cases

### Intentional cleanup shrinks an approved hotspot set

1. After a later slice removes a currently approved hotspot, re-run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` before changing the allowlist.
2. **Expected:** the guard fails with `moved_hotspot=` or `approved residue no longer matches current scan`, making the bookkeeping drift visible.
3. Update the allowlist, `S01-RESEARCH.md`, `S01-SUMMARY.md`, and `S01-UAT.md` in the same change, then re-run the verifier.
4. **Expected:** the boundary shrinks deliberately and returns to green without leaving stale handoff docs behind.

## Failure Signals

- `RESULT: --report all OK` or `RESULT: --check all OK` is missing from the verifier output
- `S01-RESEARCH.md` uses category ids or scope names that differ from the allowlist/verifier
- an approved file/count in `--report all` is missing from the research map
- the focused pytest drift tests fail
- the exclusion ids or path families in `S01-RESEARCH.md` drift from `runtime-residue-allowlist.json`
- `--check all` reports `unexpected_file=` or `moved_hotspot=` and the handoff pack was not updated in the same change

## Requirements Proved By This UAT

- R047 — S01 leaves Firebase-era runtime residue explicitly measurable and reviewable instead of implicit.
- R048 — S01 freezes one executable auth/session boundary contract for later slices to shrink.
- R049 — S01 makes the live `firebase_uid` runtime pivots inspectable for the backend canonicalization work.
- R050 — S01 makes the official frontend fallback/narrative residue inspectable for the later frontend cleanup work.

## Not Proven By This UAT

- Actual removal of `firebase_uid` from the canonical backend identity path
- Actual removal of frontend `X-Session-ID`, Bearer-as-session, or websocket query fallback behavior
- Retirement of the root `/session/*` runtime island
- Final assembled no-Firebase runtime proof; that belongs to later M004 slices

## Notes for Tester

- Start with `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`; it is the authoritative readable map.
- Use `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` when you need the next-slice owner, not the full hotspot inventory.
- If a future slice changes `runtime-residue-allowlist.json` without updating the handoff docs, treat the work as incomplete even if the verifier is green.
