---
estimated_steps: 5
estimated_files: 6
---

# T02: Prune dead backend auth dependency exports and legacy helper residue

**Slice:** S04 — Dead-Code And Obsolete-Compatibility Cleanup
**Milestone:** M003

## Description

Narrow the backend auth dependency surface to the session-first contract that is still live. This task removes dead wrappers from the public dependency/export seam, prunes their now-unused legacy helper implementations, and updates the directly-affected tests so stale Firebase-era expectations stop masquerading as current runtime truth.

## Steps

1. Remove `verify_firebase_token`, `get_doctor_user`, and `get_current_user_websocket` from `backend-hormonia/app/dependencies/auth_dependencies.py` and `backend-hormonia/app/dependencies/__init__.py`, leaving the remaining stable auth/session/admin/user imports intact.
2. Prune the matching dead implementations from `backend-hormonia/app/dependencies/auth_legacy_firebase.py` if the façade cleanup leaves them without internal callers.
3. Update `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` so it asserts the narrowed public surface rather than pinning the removed exports.
4. Update or explicitly skip the Firebase-auto-fallback residue in `backend-hormonia/tests/services/websocket/test_connection_manager.py` if it directly blocks symbol removal, making the obsolete status explicit instead of leaving a silent import/mock failure in the repo.
5. Run the focused backend auth/websocket/rbac/hard-cut suites that represent the current session-first contract.

## Must-Haves

- [ ] The backend public auth dependency surface no longer exports the three proven-dead wrappers, and any matching dead helper implementations are removed from the legacy module.
- [ ] The focused backend proof pack still passes, and any stale Firebase-era websocket test residue is either updated or made explicitly non-authoritative instead of failing implicitly.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py`
- Confirm the auth dependency surface seen by the contract test no longer includes `verify_firebase_token`, `get_doctor_user`, or `get_current_user_websocket`.

## Observability Impact

- Signals added/changed: the narrowed auth dependency contract becomes explicit in split-contract coverage, while stale Firebase-only websocket expectations stop failing as ambiguous symbol errors.
- How a future agent inspects this: rerun the focused Pytest command and inspect `auth_dependencies.py`, `__init__.py`, and the updated contract test when an export-surface regression appears.
- Failure state exposed: export-surface drift, stale compat-test residue, and session-first auth/websocket/rbac regressions are localized to named suites.

## Inputs

- `.gsd/milestones/M003/slices/S04/S04-RESEARCH.md` — identifies the three backend wrappers as dead on the runtime app graph and calls out the stale websocket-manager test residue.
- Outputs from S02 — the split auth/session modules (`auth_dependencies.py`, `auth_legacy_firebase.py`, role/session seams) provide the stable surface that must remain after pruning.

## Expected Output

- `backend-hormonia/app/dependencies/auth_dependencies.py` and `backend-hormonia/app/dependencies/__init__.py` — narrowed to the live backend auth dependency surface.
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — stripped of helper implementations that no longer have callers.
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` and `backend-hormonia/tests/services/websocket/test_connection_manager.py` — aligned with the post-cleanup session-first contract.
