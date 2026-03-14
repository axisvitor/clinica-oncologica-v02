# S01: Guardrails do corte canônico de runtime — UAT

**Milestone:** M004
**Written:** 2026-03-14

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 ships a boundary contract and diagnostics, not a user-facing runtime feature. After S04, the right proof is that the verifier reports the reduced live residue inventory honestly, the frontend scope stays zero-approved, and root `/session/*` retirement remains explicit under focused pytest.

## Preconditions

- Run from the repository root: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1`.
- Python dependencies for `backend-hormonia` are installed and `pytest` is available.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` and `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` exist in the working tree.
- No local edits are hiding deleted/moved hotspot files that would make the allowlist stale.

## Smoke Test

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`.
2. **Expected:** The output lists only approved backend residue rows for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`, then ends with `RESULT: --check backend OK`.

## Test Cases

### 1. Reduced backend residue boundary replay

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`.
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`.
3. **Expected:** Both commands succeed. The output lists only approved backend category/file/count rows for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`. It must not mention approved `root_legacy_session` or backend Firebase-narrative residue.

### 2. Frontend zero-residue replay

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`.
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`.
3. **Expected:** Both commands succeed. `frontend` prints `no approved residue` and does not emit `unexpected_file=` or `moved_hotspot=`.

### 3. Root `/session/*` retirement stays explicit

1. Run `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`.
2. Wait for pytest to finish.
3. **Expected:** The suite passes and proves representative `/session/*` routes return HTTP 410 with `AUTH_LEGACY_SESSION_ROUTE_RETIRED`, the retired path, and the canonical replacement prefix instead of 404 drift or legacy route behavior.

### 4. Failure-path diagnostics are still inspectable

1. Run `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue`.
2. Run `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name`.
3. **Expected:** Both targeted subsets pass, proving the guard still rejects newly introduced residue and still names moved approved hotspots with stable diagnostics.

## Edge Cases

### Backend/frontend scope isolation

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`.
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`.
3. **Expected:** The backend report shows only `backend-hormonia/...` files and no retired root-session category. The frontend report shows no approved residue and no backend files.

### Frontend reintroduction guard

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` after any future frontend auth/session cleanup or refactor.
2. **Expected:** The command stays green. Any new frontend hit in `firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, or `firebase_narrative` should fail immediately instead of being treated as approved debt.

### `/session/*` verifier split

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`.
2. Run `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`.
3. **Expected:** The verifier remains green even though `/session/*` strings still exist in the tombstone router and router registry. That surface is intentionally guarded by focused pytest now, not by approved verifier debt.

## Failure Signals

- `verify-runtime-residue.sh --check backend` or `--check frontend` exits nonzero or prints `unexpected_file=`.
- `verify-runtime-residue.sh --check backend` or `--check frontend` exits nonzero or prints `moved_hotspot=` / `anchor=` for an approved hotspot that drifted.
- `--report backend` starts listing approved `root_legacy_session` or backend Firebase-narrative residue again.
- `tests/auth/test_session_validation.py` returns 404 or old `/session/*` behavior instead of the explicit 410 tombstone.
- The targeted pytest subsets fail, which means the failure-path diagnostics are no longer trustworthy.
- The report output loses category/file/count detail and degrades into generic grep-style noise.

## Requirements Proved By This UAT

- R047 — The official-runtime Firebase residue boundary is executable and inspectable instead of implicit.
- R048 — Legacy auth/session surfaces inside the official runtime are measurable by one scoped contract plus the explicit root-route retirement proof.
- R049 — Remaining `firebase_uid` hotspots in the official runtime are enumerated and guarded against silent drift.
- R050 — The official frontend residue boundary is still proven clean inside the scoped runtime guard.

## Not Proven By This UAT

- This UAT does not prove the full runtime has already converged end to end to the no-Firebase canonical path; S05 and S06 still own the remaining cleanup and assembled-stack proof.
- This UAT does not prove live `/login`, `/dashboard`, `/admin`, or `/whatsapp` behavior on a mounted stack.
- This UAT does not remove schema/migration residue; M005 still owns the physical schema cleanup.

## Notes for Tester

- A green result here means the boundary is honest, not that the milestone is done.
- `frontend` showing `no approved residue` is intentional. Do not repopulate the allowlist just to quiet a regression.
- Root `/session/*` is no longer approved verifier debt. If it regresses, fix the route or its focused proof instead of stuffing it back into `runtime-residue-allowlist.json`.
- The existing `pytest_asyncio` loop-scope deprecation warning may still appear during the backend pytest runs. Treat it as known noise unless it changes the pass/fail result.
- If a later slice intentionally removes or moves residue, the fix is not just code cleanup: update the allowlist and the slice handoff artifacts in the same change, then rerun this UAT.
