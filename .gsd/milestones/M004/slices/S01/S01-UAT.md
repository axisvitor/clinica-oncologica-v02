# S01: Guardrails do corte canônico de runtime — UAT

**Milestone:** M004
**Written:** 2026-03-14

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 ships a boundary contract and diagnostics, not a user-facing runtime feature. After S03, the right proof is that the verifier reports a backend-only approved boundary, the frontend scope stays zero-approved, and drift still fails clearly.

## Preconditions

- Run from the repository root: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1`.
- Python dependencies for `backend-hormonia` are installed and `pytest` is available.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` and `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` exist in the working tree.
- No local edits are hiding deleted/moved hotspot files that would make the allowlist stale.

## Smoke Test

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`.
2. **Expected:** The output contains `[frontend]`, prints `- no approved residue`, and ends with `RESULT: --report frontend OK`.

## Test Cases

### 1. Frontend zero-residue replay

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`.
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`.
3. **Expected:** Both commands succeed. `--report frontend` and `--check frontend` print `no approved residue` and do not emit `unexpected_file=` or `moved_hotspot=`.

### 2. Full boundary replay

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`.
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`.
3. **Expected:** Both commands succeed. `--report all` lists approved backend category/file/count rows, shows `frontend` as `no approved residue`, and `--check all` ends with `RESULT: --check all OK`.

### 3. Full regression harness stays green

1. Run `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py`.
2. Wait for pytest to finish.
3. **Expected:** The suite passes and still exercises the real shell verifier through subprocesses without any failing tests.

### 4. Failure-path diagnostics are still inspectable

1. Run `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue`.
2. Run `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name`.
3. **Expected:** Both targeted subsets pass, proving the guard still rejects newly introduced residue and still names moved approved hotspots with stable diagnostics.

## Edge Cases

### Backend/frontend scope isolation

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`.
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`.
3. **Expected:** The backend report shows only `backend-hormonia/...` files; the frontend report shows no approved residue and no backend files.

### Frontend reintroduction guard

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` after any future frontend auth/session cleanup or refactor.
2. **Expected:** The command stays green. Any new frontend hit in `firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, or `firebase_narrative` should fail immediately instead of being treated as approved debt.

## Failure Signals

- `verify-runtime-residue.sh --check frontend` or `--check all` exits nonzero or prints `unexpected_file=`.
- `verify-runtime-residue.sh --check frontend` or `--check all` exits nonzero or prints `moved_hotspot=` / `anchor=` for an approved hotspot that drifted.
- `--report frontend` lists approved residue instead of `no approved residue`.
- The targeted pytest subsets fail, which means the failure-path diagnostics are no longer trustworthy.
- The report output loses category/file/count detail and degrades into generic grep-style noise.

## Requirements Proved By This UAT

- R047 — The official-runtime Firebase residue boundary is executable and inspectable instead of implicit.
- R048 — Legacy auth/session surfaces inside the official runtime are measurable by one scoped contract.
- R049 — Remaining `firebase_uid` hotspots in the official runtime are enumerated and guarded against silent drift.
- R050 — The official frontend residue boundary is now proven clean inside the scoped runtime guard.

## Not Proven By This UAT

- This UAT does not prove that the full runtime has already converged end-to-end to the no-Firebase canonical path; backend transport retirement, adjacent Firebase cleanup, and assembled-stack proof still belong to S04–S06.
- This UAT does not prove live login, restore, logout, `/dashboard`, `/admin`, or `/whatsapp` behavior on a mounted stack.
- This UAT does not remove schema/migration residue; M005 still owns the physical schema cleanup.

## Notes for Tester

- A green result here means the boundary is honest, not that the milestone is done. After S03, the remaining approved residue is backend-owned.
- `frontend` showing `no approved residue` is intentional. Do not repopulate the allowlist just to quiet a regression.
- The existing `pytest_asyncio` loop-scope deprecation warning may still appear during the backend pytest runs. Treat it as known noise unless it changes the pass/fail result.
- If a later slice intentionally removes or moves residue, the fix is not just code cleanup: update the allowlist and the slice handoff artifacts in the same change, then rerun this UAT.
