# S01: Guardrails do corte canônico de runtime — UAT

**Milestone:** M004
**Written:** 2026-03-14

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 ships a boundary contract and diagnostics, not a live runtime feature. The right proof is that the verifier reports the approved residue map, stays green on the current boundary, and fails clearly on synthetic drift.

## Preconditions

- Run from the repository root: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1`.
- Python dependencies for `backend-hormonia` are installed and `pytest` is available.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` and `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` exist in the working tree.
- No local edits are hiding deleted/moved hotspot files that would make the allowlist stale.

## Smoke Test

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`.
2. Confirm the output contains both `[backend]` and `[frontend]` sections.
3. **Expected:** The output lists category/file/count rows for approved residue and ends with `RESULT: --report all OK`.

## Test Cases

### 1. Green boundary replay

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`.
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`.
3. **Expected:** Both commands succeed. `--report all` prints the approved residue map; `--check all` ends with `RESULT: --check all OK` and does not emit `unexpected_file=` or `moved_hotspot=`.

### 2. Full regression harness stays green

1. Run `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py`.
2. Wait for pytest to finish.
3. **Expected:** The suite passes and exercises the real shell verifier through subprocesses without any failing tests.

### 3. Unexpected residue failure path is still inspectable

1. Run `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue`.
2. Wait for the targeted subset to finish.
3. **Expected:** The subset passes, proving the guard still rejects newly introduced residue and reports the offending category/file in a stable way.

### 4. Moved approved hotspot diagnostics still name the anchor

1. Run `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name`.
2. Wait for the targeted subset to finish.
3. **Expected:** The subset passes, proving a moved approved hotspot still fails with `moved_hotspot=` and `anchor=` diagnostics instead of a generic drift error.

## Edge Cases

### Backend/frontend scope isolation

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`.
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`.
3. **Expected:** The backend report shows only `backend-hormonia/...` files; the frontend report shows only `frontend-hormonia/...` files; both end with `OK`.

### Out-of-scope strings stay out of the failure surface

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`.
2. Inspect the reported file paths.
3. **Expected:** The report contains only official runtime files plus slice-local proof artifacts. It should not surface schema/history/test/doc paths such as Alembic migrations, historical docs, or unrelated vendor/public session strings.

## Failure Signals

- `verify-runtime-residue.sh --check all` exits nonzero or prints `unexpected_file=`.
- `verify-runtime-residue.sh --check all` exits nonzero or prints `moved_hotspot=` / `anchor=` for an approved hotspot that drifted.
- `--report backend` includes frontend files or `--report frontend` includes backend files.
- The targeted pytest subsets fail, which means the failure-path diagnostics are no longer trustworthy.
- The report output loses category/file/count detail and degrades into generic grep-style noise.

## Requirements Proved By This UAT

- R047 — The official-runtime Firebase residue boundary is executable and inspectable instead of implicit.
- R048 — Legacy auth/session surfaces inside the official runtime are now measurable by one scoped contract.
- R049 — Remaining `firebase_uid` hotspots in the official runtime are enumerated and guarded against silent drift.
- R050 — Frontend Firebase/session residue, including narrative hotspots and legacy transport fallbacks, is visible and guarded.

## Not Proven By This UAT

- This UAT does not prove that the runtime has already converged to the no-Firebase canonical path; that work belongs to S02–S06.
- This UAT does not prove live login, restore, logout, `/dashboard`, `/admin`, or `/whatsapp` behavior on a mounted stack.
- This UAT does not remove schema/migration residue; M005 still owns the physical schema cleanup.

## Notes for Tester

- A green result here means the boundary is honest, not that the residue is gone.
- The existing `pytest_asyncio` loop-scope deprecation warning may still appear during the backend pytest runs. Treat it as known noise unless it changes the pass/fail result.
- If a later slice intentionally removes or moves residue, the fix is not just code cleanup: update the allowlist and the slice handoff artifacts in the same change, then rerun this UAT.
