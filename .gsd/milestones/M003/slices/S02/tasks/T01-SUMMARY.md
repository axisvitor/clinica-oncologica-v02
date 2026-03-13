---
id: T01
parent: S02
milestone: M003
provides:
  - Proof-first split-contract suites for the backend auth/session refactor, plus websocket session diagnostic coverage.
key_files:
  - backend-hormonia/tests/unit/test_auth_dependency_module_split.py
  - backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py
  - backend-hormonia/tests/api/test_websocket_session_auth_contract.py
key_decisions:
  - Freeze the refactor around explicit split modules (`auth_session_contract`, `auth_session_cache`, `auth_user_adapter`, `auth_role_dependencies`) instead of relying on prose-only intent.
  - Treat canonical `id` / `user_id` session data as the happy path and pin `firebase_uid` as compatibility-only residue for later extraction.
patterns_established:
  - Add focused red contract suites before moving production auth code so missing seams fail at one boundary each instead of through broad end-to-end breakage.
  - Keep websocket session auth diagnostics explicit with stable `AUTH_WEBSOCKET_SESSION_INVALID` and `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` proofs.
observability_surfaces:
  - cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_dependency_override_contract.py
  - cd backend-hormonia && pytest -q tests/api/test_websocket_session_auth_contract.py
duration: ~25m across interrupted sessions
verification_result: passed
completed_at: 2026-03-13T00:46:47Z
blocker_discovered: false
---

# T01: Add failing split-contract tests for auth seams

**Shipped the red split-contract suites that pin the future auth/session module boundaries, admin override behavior, and websocket session diagnostics.**

## What Happened

Two prior auto-mode runs already wrote and auto-committed the planned test files, but both sessions stopped before writing the task summary, checking the slice plan box, or advancing `.gsd/STATE.md`. This closeout pass recovered the missing artifacts so the GSD state matches what is already in the branch.

`backend-hormonia/tests/unit/test_auth_dependency_module_split.py` now freezes the planned split around `auth_session_contract`, `auth_session_cache`, and `auth_user_adapter`. The suite pins explicit session-ID precedence under `ENABLE_COOKIE_PRIORITY`, canonical embedded-user extraction without a `firebase_uid` happy-path requirement, cache hydration for canonical and compatibility identity keys, safe dict→`User` adaptation, and delegation from `auth_dependencies.get_current_user_from_session()` / `get_current_user_object_from_session()` into the future split modules.

`backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` freezes the wrapper-sensitive seams the refactor must preserve: narrower dependency overrides in the admin router still work, the roles admin dependency must accept canonical user IDs without requiring `firebase_uid`, and `get_current_active_admin()` is expected to delegate into a future `auth_role_dependencies` module.

`backend-hormonia/tests/api/test_websocket_session_auth_contract.py` was tightened only where needed so the slice gate keeps websocket session diagnostics explicit. It now proves user-id-centric session auth, stable invalid-session diagnostics, and stable lookup-failure diagnostics.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_dependency_override_contract.py` → expected red. The failures are the intended proof surface: missing `app.dependencies.auth_session_contract`, `auth_session_cache`, `auth_user_adapter`, and `auth_role_dependencies` modules plus one live wrapper incompatibility in `app/api/v2/routers/roles/dependencies.py`, which still rejects canonical admin session data without `firebase_uid`.
- `cd backend-hormonia && pytest -q tests/api/test_websocket_session_auth_contract.py` → pass (`... [100%]`).
- No broader slice pack was rerun in this closeout pass because T01 is an intermediate proof-first task; the meaningful gate here is that the new contract suites exist and fail for the planned reasons rather than fixture or environment noise.

## Diagnostics

Re-run `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_dependency_override_contract.py` to inspect exactly which split seam is still missing or which wrapper contract still drifts. Re-run `cd backend-hormonia && pytest -q tests/api/test_websocket_session_auth_contract.py` to confirm websocket session auth still emits the stable success / invalid-session / lookup-failure signals the slice plan depends on.

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — red split-contract coverage for session precedence, canonical session payload shaping, cache hydration, adapter conversion, and façade delegation.
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` — red override/wrapper compatibility coverage for admin dependency overrides, canonical ID-based admin lookup, and future role-module delegation.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — websocket proof for canonical session auth plus stable invalid-session and lookup-failure diagnostics.
- `.gsd/milestones/M003/slices/S02/tasks/T01-SUMMARY.md` — durable closeout summary for the already-shipped T01 outputs.
- `.gsd/milestones/M003/slices/S02/S02-PLAN.md` — marked T01 complete.
- `.gsd/STATE.md` — advanced next action to T02.
- `.gsd/runtime/units/execute-task-M003-S02-T01.json` — aligned the persisted runtime unit with the recovered task closeout.
