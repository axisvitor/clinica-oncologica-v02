# S01: Guardrails do corte canônico de runtime — UAT

**Milestone:** M004
**Written:** 2026-03-14

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 ships a boundary contract and diagnostics, not a user-facing runtime feature. After S05, the right proof is that the verifier reports the reduced live residue inventory honestly, the focused S05 proof packs stay green for the surfaces that left the verifier, and root `/session/*` retirement remains explicit under focused pytest.

## Preconditions

- Run from the repository root: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1`.
- Python dependencies for `backend-hormonia` are installed and `pytest` is available.
- Node dependencies for `frontend-hormonia` are installed.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` and `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` exist in the working tree.
- No local edits are hiding deleted/moved hotspot files that would make the allowlist stale.

## Smoke Test

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`.
2. **Expected:** The output lists only approved backend residue rows for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`, prints `frontend` as `no approved residue`, and ends with `RESULT: --check all OK`.

## Test Cases

### 1. Post-S05 full residue boundary replay

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`.
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`.
3. **Expected:** Both commands succeed. The backend output lists only approved category/file/count rows for:
   - `firebase_uid` in:
     - `backend-hormonia/app/api/v2/routers/admin/utils.py`
     - `backend-hormonia/app/api/v2/routers/auth.py`
     - `backend-hormonia/app/api/v2/user_cache_shared.py`
     - `backend-hormonia/app/dependencies/auth_dependencies.py`
     - `backend-hormonia/app/dependencies/auth_legacy_firebase.py`
     - `backend-hormonia/app/dependencies/auth_role_dependencies.py`
     - `backend-hormonia/app/dependencies/auth_session_cache.py`
     - `backend-hormonia/app/dependencies/auth_session_contract.py`
   - `x_session_id` in:
     - `backend-hormonia/app/api/v2/routers/admin/dependencies.py`
     - `backend-hormonia/app/api/websockets.py`
     - `backend-hormonia/app/dependencies/auth_dependencies.py`
   - `session_bearer_fallback` in:
     - `backend-hormonia/app/api/v2/routers/admin/dependencies.py`
     - `backend-hormonia/app/dependencies/auth_session_contract.py`
   - `websocket_session_id_query` in:
     - `backend-hormonia/app/api/websockets.py`
4. **Expected:** The report/check must not mention approved `firebase_uid` residue in `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/core/redis_manager/session_cache.py`, or `backend-hormonia/app/dependencies/auth_user_adapter.py`.

### 2. Focused post-S05 proof-pack replay

1. Run `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`.
2. Run `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`.
3. Run `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`.
4. Run `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`.
5. Run `cd frontend-hormonia && npm run build`.
6. **Expected:** All commands pass. If the verifier starts listing a cleaned hotspot again, one of these proof packs should localize whether drift re-entered the auth/session seam, login/websocket payload writing, audit/admin/docs serialization, or adjacent frontend types.

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
3. **Expected:** The backend report shows only `backend-hormonia/...` files. The frontend report shows `no approved residue` and no backend files.

### Frontend reintroduction guard

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` after any future frontend auth/session cleanup or refactor.
2. **Expected:** The command stays green. Any new frontend hit in `firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, or `firebase_narrative` should fail immediately instead of being treated as approved debt.

### `/session/*` verifier split

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`.
2. Run `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`.
3. **Expected:** The verifier remains green even though `/session/*` strings still exist in the tombstone router and router registry. That surface is intentionally guarded by focused pytest now, not by approved verifier debt.

### M005 exclusion boundary

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`.
2. Inspect the emitted file list.
3. **Expected:** The report does not list `backend-hormonia/app/models/**` or `backend-hormonia/app/schemas/**`; schema/model Firebase residue remains explicitly excluded for M005.

## Failure Signals

- `verify-runtime-residue.sh --check all` exits nonzero or prints `unexpected_file=`.
- `verify-runtime-residue.sh --check all` exits nonzero or prints `moved_hotspot=` / `anchor=` for an approved hotspot that drifted.
- `--report all` starts listing approved `firebase_uid` residue in `auth_session_shared.py`, `session_cache.py`, or `auth_user_adapter.py` again.
- One of the focused S05 proof packs fails, which means the verifier and the cleaned runtime-adjacent surfaces no longer agree.
- `tests/auth/test_session_validation.py` returns 404 or old `/session/*` behavior instead of the explicit 410 tombstone.
- The targeted `test_runtime_residue_guard.py` subsets fail, which means the failure-path diagnostics are no longer trustworthy.
- The report output loses category/file/count detail and degrades into generic grep-style noise.

## Requirements Proved By This UAT

- R047 — The official-runtime Firebase residue boundary is executable and inspectable instead of implicit.
- R048 — Legacy auth/session surfaces inside the official runtime are measurable by one scoped contract plus focused proof for the adjacent surfaces that left the verifier.
- R049 — Remaining `firebase_uid` hotspots in the official runtime are enumerated and guarded against silent drift.
- R050 — The official frontend residue boundary is still proven clean inside the scoped runtime guard.

## Not Proven By This UAT

- This UAT does not prove the full runtime has already converged end to end to the no-Firebase canonical path; S06 still owns the assembled-stack proof.
- This UAT does not remove schema/migration residue; M005 still owns the physical schema/model cleanup.
- This UAT does not prove live `/login`, `/dashboard`, `/admin`, or `/whatsapp` behavior on a mounted stack.

## Notes for Tester

- A green result here means the boundary is honest, not that the milestone is done.
- `frontend` showing `no approved residue` is intentional. Do not repopulate the allowlist just to quiet a regression.
- Root `/session/*` is no longer approved verifier debt. If it regresses, fix the route or its focused proof instead of stuffing it back into `runtime-residue-allowlist.json`.
- Remaining `firebase_uid` report hits are post-S05 passive compatibility/sanitization/admin-helper residue, not proof that the canonical session/runtime path is still Firebase-shaped.
- The existing `pytest_asyncio` loop-scope deprecation warning may still appear during backend pytest runs. Treat it as known noise unless it changes the pass/fail result.
- If a later slice intentionally removes or moves residue, the fix is not just code cleanup: update the allowlist and the slice handoff artifacts in the same change, then rerun this UAT.
