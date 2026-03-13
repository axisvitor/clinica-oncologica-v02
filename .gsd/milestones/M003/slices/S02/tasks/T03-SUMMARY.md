---
id: T03
parent: S02
milestone: M003
provides:
  - Extracted auth user-adaptation and role-wrapper seams into focused modules behind the stable auth dependency façade.
  - Switched admin session lookups to prefer canonical `id` / `user_id`, with `firebase_uid` retained only as an explicit compatibility fallback.
key_files:
  - backend-hormonia/app/dependencies/auth_user_adapter.py
  - backend-hormonia/app/dependencies/auth_role_dependencies.py
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/api/v2/routers/admin/dependencies.py
  - backend-hormonia/app/api/v2/routers/roles/dependencies.py
  - backend-hormonia/tests/unit/test_auth_dependency_module_split.py
key_decisions:
  - Keep `app.dependencies.auth_dependencies` and `app.dependencies` as the public import/override surface; the new modules stay internal seams and the façade delegates to them.
  - Treat canonical session `id` / `user_id` as authoritative for admin wrapper DB lookups and use `firebase_uid` only when canonical IDs are absent.
patterns_established:
  - Keep override-sensitive FastAPI dependencies as thin façade callables so existing `dependency_overrides` targets remain stable while implementation moves underneath.
  - Isolate pure adaptation/role helpers in side-effect-free modules so auth splitting does not reintroduce router import cycles.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/auth/test_user_conversion.py tests/auth/test_session_role_enforcement.py tests/api/v2/test_auth_dependency_override_contract.py`
  - `cd backend-hormonia && pytest -q tests/auth/test_role_resolution.py`
  - `cd backend-hormonia && python3 - <<'PY' ...` structural split check (`auth_dependencies.py` now 1015 lines; `auth_legacy_firebase.py` still missing)
duration: 40m
verification_result: passed
completed_at: 2026-03-12T22:14:22-03:00
blocker_discovered: false
---

# T03: Extract user adaptation and role wrapper seams

**Split user adaptation and role gating into dedicated auth modules while keeping the public dependency/override surface stable.**

## What Happened

`backend-hormonia/app/dependencies/auth_user_adapter.py` now owns the user-adaptation helpers: `session_user_data_to_user()`, `resolve_user_role()`, and `user_to_cache_dict()`. `auth_dependencies.py` keeps the old public function names but delegates to the adapter so existing imports and tests keep working.

`backend-hormonia/app/dependencies/auth_role_dependencies.py` now owns the role-gated wrapper checks: active-user, admin-user, doctor-user, session-admin validation, and admin-user DB lookup from session identity. `auth_dependencies.py` delegates `get_current_active_user()`, `get_admin_user()`, `get_doctor_user()`, and `get_current_active_admin()` into that module.

The admin and roles router wrappers were updated without changing caller import paths. `app/api/v2/routers/admin/dependencies.py` still tolerates narrower override signatures, but its final admin gate now runs through the extracted role helper. `app/api/v2/routers/roles/dependencies.py` now prefers canonical `id` / `user_id` for the admin lookup and only falls back to `firebase_uid` when those canonical IDs are absent. That addresses both task must-haves: the public imports/override targets stayed stable, and the wrappers kept their compatibility behavior while reducing default dependence on `firebase_uid`.

`app/dependencies/__init__.py` now re-exports the session/admin auth façade names that this slice keeps stable, and the split-contract unit tests were extended to assert delegation into the new adapter/role modules.

## Verification

Passed task proof:

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/auth/test_user_conversion.py tests/auth/test_session_role_enforcement.py tests/api/v2/test_auth_dependency_override_contract.py`
- `cd backend-hormonia && pytest -q tests/auth/test_role_resolution.py`

Passed slice-level checks run during T03:

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/auth/test_user_conversion.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_dependency_override_contract.py tests/auth/test_session_role_enforcement.py tests/api/test_websocket_session_auth_contract.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_hard_cut_cleanup.py`

Still red outside T03 scope:

- Structural split check fails only because `backend-hormonia/app/dependencies/auth_legacy_firebase.py` does not exist yet. The size target itself now passes: `auth_dependencies.py` is down to 1015 lines.
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend` still fails because `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` has stale hotspot/candidate anchors for the new line counts and repo refs.

## Diagnostics

Future inspection points:

- Adapter seam regressions: `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/auth/test_user_conversion.py tests/auth/test_role_resolution.py`
- Wrapper seam regressions: `cd backend-hormonia && pytest -q tests/api/v2/test_auth_dependency_override_contract.py tests/auth/test_session_role_enforcement.py`
- Structural progress: rerun the slice structural check; `auth_dependencies.py` is already below the `<1100` budget and only the T04 module creation remains on that gate.

## Deviations

None.

## Known Issues

- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` is still missing, so the full structural slice gate cannot pass until T04.
- The backend evidence-map check is stale relative to the refactor and needs the research anchors updated in a later task.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_user_adapter.py` — expanded the adapter seam to own cache serialization and role normalization in addition to dict→`User` conversion.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` — added the focused role-gating and session-admin lookup module.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — reduced the façade to delegation for adapter and role-wrapper helpers while preserving public names.
- `backend-hormonia/app/dependencies/__init__.py` — re-exported the stable auth façade names through the package surface.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — preserved override-tolerant wrapper invocation while delegating the final admin check.
- `backend-hormonia/app/api/v2/routers/roles/dependencies.py` — switched admin lookup to canonical `id` / `user_id` first, with explicit `firebase_uid` fallback.
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — added delegation proofs for the extracted adapter and role modules.
- `.gsd/DECISIONS.md` — recorded the canonical-ID-first wrapper lookup decision for downstream tasks.
- `.gsd/milestones/M003/slices/S02/S02-PLAN.md` — marked T03 complete.
- `.gsd/STATE.md` — advanced the next action to T04.
