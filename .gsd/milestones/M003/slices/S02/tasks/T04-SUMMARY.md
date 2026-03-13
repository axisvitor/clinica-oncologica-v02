---
id: T04
parent: S02
milestone: M003
provides:
  - Routed Firebase verification, bearer-token auth, and websocket compatibility through the isolated `auth_legacy_firebase.py` seam while keeping `auth_dependencies.py` as the stable public façade.
  - Closed the backend proof gate with green slice-level auth/session/websocket/login checks, a 706-line structural split pass, and a refreshed backend evidence verifier.
key_files:
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/dependencies/__init__.py
  - backend-hormonia/tests/unit/test_auth_dependency_module_split.py
  - .gsd/milestones/M003/slices/S01/S01-RESEARCH.md
key_decisions:
  - Keep `app.dependencies.auth_dependencies` and `app.dependencies` as the public auth import/override surface; legacy Firebase/bearer/websocket behavior moves underneath that façade instead of changing caller patch targets.
  - Refresh the S01 backend evidence anchors to current hotspot/candidate counts so the verifier stays usable as the slice closes.
patterns_established:
  - Keep session-first auth logic in the façade, but delegate compatibility-only bearer/websocket work to one explicit module so legacy residue has a single implementation home.
  - Add split-contract delegation tests for the façade whenever a hotspot refactor moves behavior underneath stable FastAPI dependency names.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/auth/test_user_conversion.py`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_auth_dependency_override_contract.py tests/auth/test_session_role_enforcement.py tests/api/test_websocket_session_auth_contract.py`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_hard_cut_cleanup.py`
  - `cd backend-hormonia && python3 - <<'PY' ...` structural split check (`auth_dependencies.py` now 706 lines)
  - `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`
duration: 35m
verification_result: passed
completed_at: 2026-03-12T22:48:54-03:00
blocker_discovered: false
---

# T04: Isolate legacy bearer/websocket compatibility and close the backend proof gate

**Isolated the remaining Firebase/bearer/websocket compatibility behind the stable auth façade and closed the slice with green proof plus a refreshed backend evidence gate.**

## What Happened

`backend-hormonia/app/dependencies/auth_dependencies.py` stopped owning the legacy Firebase implementation details directly. `_firebase_service` initialization now comes from `auth_legacy_firebase.initialize_firebase_service(...)`, `verify_firebase_token()` delegates to the compatibility module, `get_current_user()` keeps the session-first happy path in place but hands the bearer-token branch to `auth_legacy_firebase.authenticate_legacy_bearer_user(...)`, and `get_current_user_websocket()` now delegates to the same module as a thin wrapper.

That leaves `auth_dependencies.py` as the public façade and override surface while making `backend-hormonia/app/dependencies/auth_legacy_firebase.py` the single implementation home for the compatibility-only Firebase/bearer/websocket path. The façade line count dropped to 706, well under the slice budget, without changing the public dependency names that existing callers patch or import.

`backend-hormonia/app/dependencies/__init__.py` was refreshed to keep exporting the auth façade names, including `verify_firebase_token`, through the package surface.

`backend-hormonia/tests/unit/test_auth_dependency_module_split.py` gained explicit delegation proofs for `verify_firebase_token()`, the bearer fallback inside `get_current_user()`, and `get_current_user_websocket()`. That turns the isolation into an enforced contract instead of a one-off refactor.

The only red gate after the code move was the backend evidence verifier. Its failure was not a runtime regression; `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` still had stale backend hotspot/candidate anchors from earlier in the slice. I refreshed the current backend anchor counts there so the verifier reflects the shipped state of S02 instead of the pre-refactor baseline.

## Verification

Passed slice-level backend proof:

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/auth/test_user_conversion.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_dependency_override_contract.py tests/auth/test_session_role_enforcement.py tests/api/test_websocket_session_auth_contract.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_hard_cut_cleanup.py`

Passed task-specific proof:

- `cd backend-hormonia && pytest -q tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_hard_cut_cleanup.py`

Passed structural split gate:

- `cd backend-hormonia && python3 - <<'PY' ...`
  - Result: `{'auth_dependencies_lines': 706, 'split_modules': ['app/dependencies/auth_session_contract.py', 'app/dependencies/auth_session_cache.py', 'app/dependencies/auth_user_adapter.py', 'app/dependencies/auth_role_dependencies.py', 'app/dependencies/auth_legacy_firebase.py']}`

Passed backend evidence verifier after refreshing anchors:

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`
  - Result: `RESULT: --check backend OK`

Additional safety check:

- `cd backend-hormonia && python3 -m py_compile app/dependencies/auth_dependencies.py app/dependencies/__init__.py tests/unit/test_auth_dependency_module_split.py`

## Diagnostics

Future inspection points:

- Façade/compat split regressions: `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/test_websocket_session_auth_contract.py`
- Full backend slice gate: rerun the three slice pytest commands above plus the structural split check and `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`
- Structural hotspot status: `backend-hormonia/app/dependencies/auth_dependencies.py` is now 706 lines; the isolated compatibility implementation lives in `backend-hormonia/app/dependencies/auth_legacy_firebase.py`

## Deviations

None.

## Known Issues

- `pytest` still emits the existing `pytest-asyncio` deprecation warning about `asyncio_default_fixture_loop_scope` being unset. It did not block or invalidate the slice proof.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_dependencies.py` — reduced the public auth surface to a session-first façade that delegates Firebase verification, bearer auth, and websocket compatibility into `auth_legacy_firebase.py`.
- `backend-hormonia/app/dependencies/__init__.py` — kept the package-level auth export surface aligned with the façade, including `verify_firebase_token`.
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — added delegation proofs for the legacy Firebase/bearer/websocket split seams.
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — refreshed backend hotspot/candidate anchors so the evidence verifier matches the shipped S02 state.
- `.gsd/DECISIONS.md` — recorded the stable-façade / isolated-compatibility decision for downstream slices.
- `.gsd/milestones/M003/slices/S02/S02-PLAN.md` — marked T04 complete.
