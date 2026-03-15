---
id: T01
parent: S01
milestone: M006
provides:
  - Session-only staff auth chokepoints with the lazy bearer/Firebase fallback removed from `get_current_user()` and the admin wrapper failing closed on legacy auth attempts.
key_files:
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/api/v2/routers/admin/dependencies.py
  - backend-hormonia/tests/unit/test_auth_dependencies.py
  - backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py
  - backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py
key_decisions:
  - Keep `get_current_user()` signature compatible for existing dependency call sites, but route every request through `get_current_user_from_session()` so bearer-only inputs are classified as legacy transport and rejected by the canonical session contract.
  - Preserve `_admin_bearer` as a compatibility export for router imports, while forwarding observed `X-Session-ID` / `Authorization` values into the session dependency only for rejection/detection, not acceptance.
patterns_established:
  - Staff-auth chokepoints should resolve identity only through `auth_session_contract`; legacy headers may be observed only to produce stable closed-failure diagnostics.
  - Admin test bypasses are allowed only when there is no auth attempt at all; legacy header/bearer attempts must flow into the session dependency and fail closed.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/api/v2/test_auth_hard_cut_cleanup.py -k "rejects_legacy_header_transport_without_cookie or stable_diagnostics"`
  - `python3 - <<'PY' ... auth_dependencies.py static seam check ... PY`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` (still red for T02 publication work)
duration: 55m
verification_result: passed
completed_at: 2026-03-15T14:59:05-03:00
blocker_discovered: false
---

# T01: Cortar o fallback bearer/Firebase dos chokepoints de staff auth

**Removed the live bearer/Firebase staff-auth seam, made the admin wrapper fail closed on legacy transport attempts, and pinned the contract with unit/API/integration proofs plus a static source guard.**

## What Happened

`backend-hormonia/app/dependencies/auth_dependencies.py` now treats `get_current_user()` as a strict session-first chokepoint. The lazy Firebase/bearer import path is gone, along with the dead import scaffolding and legacy-only helper functions that only existed to support that path. The function still preserves `request.state.user_id` / `request.state.user_role` for downstream callers, but it now always delegates to `get_current_user_from_session()`.

To keep direct dependency calls honest, `get_current_user()` synthesizes the `Authorization` header from the resolved `HTTPAuthorizationCredentials` when the raw header is absent, so bearer-only calls still register as a legacy transport attempt and are rejected by the session contract instead of silently behaving like “no auth attempt”. Cookie-backed requests and cookie+legacy mixed requests continue to resolve via the canonical cookie session path.

`backend-hormonia/app/api/v2/routers/admin/dependencies.py` was tightened so the test-only admin fallback remains available only when there is no auth attempt at all. When `X-Session-ID` or `Authorization: Bearer ...` are present without the session cookie, the wrapper now forwards those observed inputs into the session dependency instead of dropping them. That keeps the failure path honest in test mode and prevents the admin seam from masking regressions behind its local fallback.

The focused proofs were extended in three places:

- `backend-hormonia/tests/unit/test_auth_dependencies.py` now guards the removed seam statically and proves `get_current_user()` uses the session contract for mixed cookie+bearer inputs and bearer-only rejection.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` now proves bearer-only HTTP rejection remains stable and that the admin wrapper still fails closed in test mode when legacy transport is attempted without a cookie.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` now proves `/api/v2/auth/verify-session` rejects both `X-Session-ID` and session-as-Bearer transports after a real login.

I also fixed the slice plan pre-flight issue by adding an explicit failure-path verification command for the stable diagnostics in `test_auth_hard_cut_cleanup.py`.

## Verification

Passed task-level verification:

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependencies.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `python3 - <<'PY'
from pathlib import Path
text = Path('backend-hormonia/app/dependencies/auth_dependencies.py').read_text(encoding='utf-8')
for needle in ('authenticate_legacy_bearer_user', '_get_auth_legacy_firebase', '_get_firebase_service'):
    assert needle not in text, needle
print('legacy auth seam retired')
PY`

Passed slice-pack pytest verification:

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependencies.py tests/unit/test_runtime_residue_guard.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_validation.py tests/integration/test_auth_hard_cut_end_to_end.py`

Passed explicit failure-path/diagnostic verification added to the slice plan:

- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_hard_cut_cleanup.py -k "rejects_legacy_header_transport_without_cookie or stable_diagnostics"`

Slice-level verification still failing, as expected for the next task:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` → **failed** with the remaining residue-publication findings owned by T02 (`users.py` still flagged under `firebase_uid`, plus moved-hotspot drift in admin/residue metadata).

## Diagnostics

Future inspection surfaces for this task:

- `backend-hormonia/tests/unit/test_auth_dependencies.py::test_auth_dependencies_source_retires_legacy_bearer_firebase_seam`
- `backend-hormonia/tests/unit/test_auth_dependencies.py::test_get_current_user_rejects_bearer_only_via_session_contract`
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py::test_password_change_rejects_legacy_bearer_transport_without_cookie`
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py::test_admin_dependency_rejects_legacy_transport_without_cookie_even_in_test_mode`
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py::test_login_verify_reset_password_rotate_and_logout_without_firebase_staff_auth`
- Static seam check in `backend-hormonia/app/dependencies/auth_dependencies.py`

The stable failure surface remains the canonical 401 payload with `detail`, `message`, `error`, and `request_id` where applicable. The residue guard remains the broader slice signal for what still has to move out of approved runtime residue in T02.

## Deviations

- Kept `_admin_bearer` exported from `app.api.v2.routers.admin.dependencies` as a compatibility symbol because `app.api.v2.routers.admin.__init__` still imports it. The symbol remains inert for this task; the behavioral change is in how legacy transports are forwarded into the session dependency for rejection.

## Known Issues

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` still fails. That is not a T01 regression; it is the expected unfinished publication work for T02.

## Files Created/Modified

- `.gsd/milestones/M006/slices/S01/S01-PLAN.md` — added an explicit failure-path verification step for stable diagnostic coverage.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — removed the live lazy bearer/Firebase seam and legacy-only helpers; `get_current_user()` now always routes through the session contract.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — forwards observed legacy transport inputs into the session dependency, keeps test fallback limited to the true “no auth attempt” case, and uses the canonical session cookie name.
- `backend-hormonia/tests/unit/test_auth_dependencies.py` — added source-level seam retirement guard and direct `get_current_user()` contract tests.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` — added bearer-only rejection proof and admin-wrapper fail-closed regression tests.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — added integrated session-as-Bearer rejection proof for `/api/v2/auth/verify-session`.
- `.gsd/milestones/M006/slices/S01/tasks/T01-SUMMARY.md` — recorded execution, verification, diagnostics, and partial slice-level status for recovery.
