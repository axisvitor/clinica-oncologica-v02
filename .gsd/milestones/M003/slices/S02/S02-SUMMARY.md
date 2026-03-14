---
id: S02
parent: M003
milestone: M003
provides:
  - Split the backend auth/session hotspot behind stable façade imports, preserving the mapping-style session seam, `User` adapter seam, wrapper behavior, and isolated legacy bearer/websocket compatibility.
requires:
  - slice: S01
    provides: Backend hotspot ranking, auth/session guardrails, and proof-before-deletion constraints.
affects:
  - S04
  - S05
  - backend-hormonia
key_files:
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/dependencies/auth_session_contract.py
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/dependencies/auth_user_adapter.py
  - backend-hormonia/app/dependencies/auth_role_dependencies.py
  - backend-hormonia/app/dependencies/auth_legacy_firebase.py
  - backend-hormonia/tests/unit/test_auth_dependency_module_split.py
  - backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py
key_decisions:
  - Keep `app.dependencies.auth_dependencies` and `app.dependencies` as the stable public auth import/override surface while moving implementation into focused internal modules.
  - Preserve `ENABLE_COOKIE_PRIORITY`, mapping-style session dicts, `User` adaptation, and `request.state.session_id` / `user_id` / `user_role` side effects as explicit contracts rather than incidental behavior.
  - Treat canonical `id` / `user_id` session identity as authoritative for wrapper lookups and leave `firebase_uid` as compatibility fallback only.
patterns_established:
  - Split backend auth/session by caller contract first: request-facing session resolution, cache/DB hydration, dict→`User` adaptation, role wrappers, then legacy bearer/websocket compatibility.
  - Keep override-sensitive FastAPI dependencies as thin façade callables so existing dependency overrides stay stable while behavior moves underneath.
observability_surfaces:
  - cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/auth/test_user_conversion.py
  - cd backend-hormonia && pytest -q tests/api/v2/test_auth_dependency_override_contract.py tests/auth/test_session_role_enforcement.py tests/api/test_websocket_session_auth_contract.py
  - cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_hard_cut_cleanup.py
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend
drill_down_paths:
  - .gsd/milestones/M003/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T04-SUMMARY.md
duration: ~3h across 4 tasks
verification_result: passed
completed_at: 2026-03-13T01:51:12Z
---

# S02: Backend Auth/Session Hotspot Refactor

**S02 split the backend auth/session hotspot into contract-specific modules, kept the public dependency surface stable, and closed on focused backend proof instead of structural churn alone.**

## What Happened

T01 started with red split-contract tests so the slice had an executable boundary before moving production code. Those tests pinned the session dict seam, the `User` adapter seam, wrapper override behavior, and websocket session diagnostics.

T02 extracted the session-first happy path into `auth_session_contract.py` and `auth_session_cache.py`, then moved dict→`User` conversion into `auth_user_adapter.py`. `auth_dependencies.get_current_user_from_session()` stayed the public façade, but the request-facing precedence, permission enrichment, request-state writes, cache hydration, and DB fallback logic were no longer trapped in the monolith.

T03 extracted the role/user wrapper seam into `auth_role_dependencies.py` and updated the admin/roles wrappers to prefer canonical `id` / `user_id` session identity instead of defaulting to `firebase_uid`. The public import and override targets stayed stable.

T04 isolated the remaining Firebase/bearer/websocket compatibility inside `auth_legacy_firebase.py`, reduced `auth_dependencies.py` to a 675-line façade, refreshed the S01 backend anchors, and closed the slice on green focused proof.

## Verification

Passed slice-close proof:
- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/auth/test_user_conversion.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_dependency_override_contract.py tests/auth/test_session_role_enforcement.py tests/api/test_websocket_session_auth_contract.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_hard_cut_cleanup.py`
- backend structural split check: `auth_dependencies.py` reduced to 675 lines behind `auth_session_contract.py`, `auth_session_cache.py`, `auth_user_adapter.py`, `auth_role_dependencies.py`, and `auth_legacy_firebase.py`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`

## Requirements Advanced

- R034 — materially reduced the highest-risk backend hotspot.
- R037 — preserved visible auth/session, wrapper, and websocket contracts while moving internals.
- R038 — left clearer backend ownership seams and a smaller façade for future maintenance.
- R039 — tied the refactor to focused backend contract and integration proof.

## Requirements Validated

- none — the milestone-level visible-contract and integrated-proof requirements still depended on S03–S05.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_dependencies.py` — reduced to the stable public façade.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — extracted request-facing session resolution and request-state side effects.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — extracted cache/DB hydration and canonical session payload handling.
- `backend-hormonia/app/dependencies/auth_user_adapter.py` — extracted mapping-style session payload → `User` adaptation.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` — extracted role gating and admin/session wrapper behavior.
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — isolated legacy bearer/websocket compatibility.
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — contract tests for the split façade and its delegated seams.
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` — wrapper override/compatibility proof.

## Forward Intelligence

### What the next slice should know
- The stable backend seam is still `app.dependencies.auth_dependencies`; future work should move underneath it unless import/override churn is intentional.
- `firebase_uid` is compatibility-only now, but it is not dead by assumption; S04 still needed proof before deleting anything around it.

### What's fragile
- `backend-hormonia/app/routers/auth_session.py` and `backend-hormonia/app/api/v2/routers/roles/dependencies.py` — they still express retained compatibility behavior and can drift if someone reasons only from the canonical happy path.

### Authoritative diagnostics
- `tests/unit/test_auth_dependency_module_split.py` — the sharpest detector for façade/seam regressions.
- `tests/api/v2/test_auth_dependency_override_contract.py` — the sharpest detector for wrapper/override drift.

### What assumptions changed
- "The backend auth hotspot is one file to shrink" — false; it was several caller contracts trapped in one file, and splitting by contract was what made the refactor safe.
