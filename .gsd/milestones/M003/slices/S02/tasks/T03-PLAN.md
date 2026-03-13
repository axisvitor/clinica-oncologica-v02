---
estimated_steps: 4
estimated_files: 7
---

# T03: Extract user adaptation and role wrapper seams

**Slice:** S02 — Backend Auth/Session Hotspot Refactor
**Milestone:** M003

## Description

Separate dict→`User` adaptation and role-gated wrappers from the session loader. These are distinct contracts with different callers, patch targets, and compatibility pressure, so they need their own focused modules and regression checks.

## Steps

1. Create `backend-hormonia/app/dependencies/auth_user_adapter.py` and move dict→`User` conversion, timestamp coercion, role normalization, and allowed-field filtering there.
2. Create `backend-hormonia/app/dependencies/auth_role_dependencies.py` and move admin/doctor/current-active-admin checks there while preserving the current return types and error semantics.
3. Update `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/__init__.py`, `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, and `backend-hormonia/app/api/v2/routers/roles/dependencies.py` to use the new modules without changing caller import paths; prefer canonical `id`/`user_id` when present, with `firebase_uid` kept as an explicit compatibility fallback.
4. Run the conversion, session-role, and new override-contract tests until the wrapper-sensitive seams are green again.

## Must-Haves

- [ ] Public imports remain stable: callers still import from `app.dependencies.auth_dependencies` or `app.dependencies` and FastAPI dependency overrides still target the same public names.
- [ ] Admin and role wrappers preserve their existing override tolerance and compatibility behavior while reducing their dependence on `firebase_uid` where canonical user IDs already exist.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/auth/test_user_conversion.py tests/auth/test_session_role_enforcement.py tests/api/v2/test_auth_dependency_override_contract.py`
- Check that the new override-contract tests and the legacy conversion tests both stay green; neither wrapper compatibility nor dict→`User` conversion is allowed to regress.

## Observability Impact

- Signals added/changed: Conversion and role-enforcement failures become attributable to dedicated modules rather than the monolith.
- How a future agent inspects this: Re-run the focused pytest command and inspect whether the failing seam is adapter normalization, admin override invocation, or role-wrapper lookup.
- Failure state exposed: Invalid role normalization, stray non-model fields, and wrapper override signature drift surface as dedicated test failures.

## Inputs

- `backend-hormonia/tests/auth/test_user_conversion.py` and `backend-hormonia/tests/auth/test_session_role_enforcement.py` — current conversion and role-enforcement expectations that must survive the split.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` and `backend-hormonia/app/api/v2/routers/roles/dependencies.py` — wrapper modules with patch/override sensitivity and compatibility constraints.

## Expected Output

- `backend-hormonia/app/dependencies/auth_user_adapter.py` and `backend-hormonia/app/dependencies/auth_role_dependencies.py` — focused modules for object adaptation and role gating.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` and `backend-hormonia/app/api/v2/routers/roles/dependencies.py` — wrappers still using the stable public dependencies while tolerating current override patterns.
