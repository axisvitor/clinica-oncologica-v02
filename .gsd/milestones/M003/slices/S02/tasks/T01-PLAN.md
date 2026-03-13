---
estimated_steps: 4
estimated_files: 3
---

# T01: Add failing split-contract tests for auth seams

**Slice:** S02 — Backend Auth/Session Hotspot Refactor
**Milestone:** M003

## Description

Create the executable contract for the refactor before moving production code. The new tests should fail at first because the split modules and delegation seams do not exist yet; that failure is the proof that later tasks are closing a real boundary instead of only renaming code.

## Steps

1. Add `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` to pin the planned split seams for session resolution/cache hydration and dict→`User` adaptation.
2. Add `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` to pin override-sensitive admin and role-wrapper behavior against narrower dependency signatures and canonical session data.
3. Tighten `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` only where needed so websocket auth diagnostics remain part of the slice gate.
4. Run the new focused tests and confirm they fail for the expected pre-split reasons (missing modules, missing delegation seams, or unchanged wrapper behavior).

## Must-Haves

- [ ] The new tests reference the planned split modules (`auth_session_contract.py`, `auth_session_cache.py`, `auth_user_adapter.py`, `auth_role_dependencies.py`) and assert real contract behavior, not only import existence.
- [ ] The initial failure mode is meaningful: it proves the current hotspot shape does not yet satisfy the split contract and gives later tasks a real pass/fail target.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_dependency_override_contract.py`
- Confirm the failures point to the missing split modules/delegation hooks rather than unrelated fixture or environment breakage.

## Observability Impact

- Signals added/changed: New regression tests pin stable auth failure diagnostics and override-sensitive wrapper behavior.
- How a future agent inspects this: Re-run the focused pytest command to see exactly which auth seam or wrapper contract regressed.
- Failure state exposed: Missing-module drift, precedence drift, wrapper override drift, and websocket diagnostic drift become explicit test failures.

## Inputs

- `backend-hormonia/tests/unit/test_auth_session_identity_contract.py` — current session-first contract assertions to extend rather than replace.
- `backend-hormonia/tests/api/v2/test_auth_session_priority.py` and `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — the existing precedence and override-sensitive behavior this task is freezing in place.

## Expected Output

- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — failing split-contract coverage for session/cache/adapter seams.
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` — failing override/wrapper compatibility coverage ready for the implementation tasks to satisfy.
