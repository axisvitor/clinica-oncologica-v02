---
estimated_steps: 5
estimated_files: 8
---

# T01: Stabilize proof surfaces and delete dead backend auth/session cluster

**Slice:** S03 — Purga final de bridges, tombstones, serviços mortos e narrativa operacional errada
**Milestone:** M006

## Description

Merge-marker files in active pytest/vitest collection paths poison broad verification. The dead `SessionService` class and broken `auth_legacy_firebase.py` module are confirmed non-runtime by `ServiceProvider` wiring (which uses `SimpleSessionService`) and the S01 hard cut. This task resolves or deletes merge-marker files, then removes the dead backend auth/session cluster and its test consumers, updating the S01 residue verifier if any proof-only anchors pointed at now-deleted files.

## Steps

1. **Scan for merge markers** in `backend-hormonia/tests/`, `frontend-hormonia/tests/`, and `frontend-hormonia/src/` — list every file with `<<<<<<<`, `=======`, or `>>>>>>>` markers.
2. **Triage each merge-marker file:**
   - `auth_legacy_firebase.py` — delete entirely (broken dead code confirmed by S01).
   - `test_auth_dependency_module_split.py` — delete (tests for the deleted `auth_legacy_firebase` module).
   - `test_auth_dependency_override_contract.py` — inspect: if it contains useful auth contract tests beyond the merge markers, fix the conflicts; if it's primarily dead `auth_legacy_firebase` consumers, delete it.
   - Frontend test files with merge markers (`types-validation.test.ts`, `admin-auth-flow.test.tsx`, `usePatients.test.ts`) — inspect each: fix useful ones by resolving conflicts, delete if content is dead or duplicated by existing canonical tests.
3. **Delete the dead `SessionService` cluster:**
   - Delete `backend-hormonia/app/services/session_service.py`.
   - In `backend-hormonia/tests/unit/services/test_auth_session_services_async.py`, remove or delete `SessionService` import and tests (keep any `SimpleSessionService` tests if present).
   - Check `backend-hormonia/tests/integration/test_phase23_service_async_missinggreenlet.py` for the `SessionService` import — remove the import and dead tests while preserving any live `SimpleSessionService` or greenlet testing.
4. **Update S01 residue verifier proof-only anchors** in `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — if `auth_legacy_firebase.py` or `session_service.py` were listed as proof-only anchors, remove them. Run `verify-runtime-residue.sh --check backend` to confirm no anchor-drift failures.
5. **Verify** clean backend imports, zero merge markers in test paths, and S01 guard still green.

## Must-Haves

- [ ] No unresolved merge markers remain in files inside active pytest/vitest collection paths.
- [ ] `backend-hormonia/app/services/session_service.py` deleted.
- [ ] `backend-hormonia/app/dependencies/auth_legacy_firebase.py` deleted.
- [ ] `test_auth_dependency_module_split.py` deleted.
- [ ] Backend import chain (`from app.service_provider import ServiceProvider`) succeeds.
- [ ] S01 residue guard (`verify-runtime-residue.sh --check backend`) passes.

## Verification

- `rg -l '^<<<<<<<|^=======$|^>>>>>>>' backend-hormonia/tests frontend-hormonia/tests frontend-hormonia/src --glob '!**/node_modules/**' | wc -l` returns 0.
- `cd backend-hormonia && python3 -c "from app.service_provider import ServiceProvider; print('ok')"` succeeds.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` passes.
- `! test -f backend-hormonia/app/services/session_service.py && ! test -f backend-hormonia/app/dependencies/auth_legacy_firebase.py && echo "dead cluster removed"` succeeds.

## Observability Impact

- **Merge-marker cleanup** restores trustworthy broad `pytest`/`vitest` collection — previously, conflict text caused parse failures that masked real test results.
- **Dead cluster removal** eliminates `ImportError` traps from `session_service.py` and `auth_legacy_firebase.py` that could surface in import-time diagnostics.
- **Inspection surface:** `verify-runtime-residue.sh --report backend` shows updated proof-only anchor state. Absence scans confirm deleted files stay deleted.
- **Failure visibility:** If a future agent re-introduces a dependency on deleted modules, the `ServiceProvider` import check and S01 residue guard will fail explicitly.

## Inputs

- S01 summary: honest live-vs-retired auth/session boundary established; `auth_legacy_firebase.py` is retired/broken, `SessionService` is not on canonical runtime path.
- S03 research: exact file list of merge-marker locations, `SessionService` import sites, and `auth_legacy_firebase` ref sites.
- `backend-hormonia/app/service_provider.py` — confirms `session_service` returns `SimpleSessionService`.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — proof-only anchors that may reference deleted files.

## Expected Output

- Dead backend service files deleted: `session_service.py`, `auth_legacy_firebase.py`, `test_auth_dependency_module_split.py`, and any other dead-only test files.
- Merge-marker files resolved or deleted across both backend and frontend test paths.
- Updated `runtime-residue-allowlist.json` with removed anchors for deleted files.
- Clean backend imports and green S01 guard.
