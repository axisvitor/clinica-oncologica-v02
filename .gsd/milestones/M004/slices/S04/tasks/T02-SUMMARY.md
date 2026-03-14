---
id: T02
parent: S04
milestone: M004
provides:
  - Cookie-only helper/auth wrapper consumption plus acceptance proof that no longer hides behind dual cookie+header session transport.
key_files:
  - backend-hormonia/app/api/v2/routers/localization.py
  - backend-hormonia/app/api/v2/templates_shared.py
  - backend-hormonia/app/api/v2/routers/tasks/dependencies.py
  - backend-hormonia/app/api/v2/routers/admin/dependencies.py
  - backend-hormonia/tests/api/v2/test_localization.py
  - backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py
  - backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py
key_decisions:
  - Remaining helper wrappers should resolve staff sessions from the canonical session cookie only; legacy header/bearer inputs may still be observed for diagnostics or test-bypass suppression, but they are no longer passed through as an accepted runtime transport.
patterns_established:
  - Helper tests and hard-cut acceptance proofs now send session cookie + CSRF only, and explicit legacy-header rejection probes clear ambient client cookies before making a header-only request.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_shared_canonical_identity.py`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
duration: 1h20m
verification_result: passed
completed_at: 2026-03-14T14:14:03-03:00
blocker_discovered: false
---

# T02: Converge remaining helper consumers and acceptance proof on the cookie-only contract

**Cut the remaining helper/session wrappers and the hard-cut acceptance proof over to cookie-only staff auth, including localization, while removing the dual-transport test crutch and adding explicit header rejection checks.**

## What Happened

I changed `backend-hormonia/app/api/v2/routers/localization.py` so the route-local auth shim no longer requires `X-Session-ID`. It now resolves the staff session from the canonical session cookie, returns the canonical `Session cookie required` / `Invalid or expired session` surfaces, and keeps the admin-role checks and localization cache behavior intact.

I changed the remaining in-scope helper wrappers that were still parsing or documenting legacy session transport locally: `backend-hormonia/app/api/v2/templates_shared.py`, `backend-hormonia/app/api/v2/routers/tasks/dependencies.py`, `backend-hormonia/app/api/v2/messages/helpers.py`, `backend-hormonia/app/api/v2/patients_shared_helpers.py`, `backend-hormonia/app/api/v2/patients_utils.py`, `backend-hormonia/app/api/v2/routers/patients/base.py`, `backend-hormonia/app/api/v2/routers/reports.py`, and `backend-hormonia/app/api/v2/routers/enhanced_reports.py`. Those helpers now consume the cookie-backed contract only instead of accepting `X-Session-ID` / bearer session IDs as an alternate path.

I also updated the quiz/report-adjacent shared shims that only needed narrative cleanup: `backend-hormonia/app/api/v2/_quiz_shared.py` and `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/_shared.py` no longer advertise cookie/header/bearer precedence in their helper docstrings.

For admin auth, `backend-hormonia/app/api/v2/routers/admin/dependencies.py` now treats the session cookie as the only canonical staff-session input. Legacy `X-Session-ID` / bearer presence is still noticed so the test-only local-admin bypass does not mask an attempted auth request, but those values are no longer forwarded into session resolution as an accepted transport.

On the proof side, I rewired `backend-hormonia/tests/api/v2/test_localization.py`, `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`, and `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` to authenticate with session cookie + CSRF only. The localization suite now has explicit assertions for header-only rejection and expired-cookie failure. The hard-cut cleanup pack now proves header-only password change rejection. The end-to-end proof no longer sends cookie + `X-Session-ID` together and includes an explicit header-only verify-session rejection after clearing the client cookie jar so the probe is honest.

I also updated `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` so the focused shared-helper proof matches the cookie-only contract and the revised helper signatures.

## Verification

Passed:
- `cd backend-hormonia && pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_shared_canonical_identity.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`
- `cd backend-hormonia && python3 -m py_compile app/api/v2/routers/localization.py app/api/v2/templates_shared.py app/api/v2/routers/tasks/dependencies.py app/api/v2/routers/admin/dependencies.py app/api/v2/messages/helpers.py app/api/v2/patients_utils.py app/api/v2/patients_shared_helpers.py app/api/v2/routers/patients/base.py app/api/v2/_quiz_shared.py app/api/v2/routers/monthly_quiz_operations/_shared.py app/api/v2/routers/reports.py app/api/v2/routers/enhanced_reports.py tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py tests/api/v2/test_auth_session_shared_canonical_identity.py`

Slice-level residue state:
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` → completed with 23 drift notes after removing more legacy helper anchors than the current allowlist expects.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` → failed with 23 issues. The failures are the expected stale-residue/allowlist fallout for S04 and remain T03 work.

## Diagnostics

Use these in order when this boundary regresses:
- Helper/consumer contract drift: `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_shared_canonical_identity.py`
- Localization/helper acceptance drift: `cd backend-hormonia && pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
- Original chokepoint contract drift: `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
- Residue inventory / stale allowlist fallout: `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` and `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

The explicit header-only rejection probe in `tests/integration/test_auth_hard_cut_end_to_end.py` clears `client.cookies` before the request. If that assertion starts passing unexpectedly, check whether ambient client cookies were reintroduced before assuming the runtime contract regressed.

## Deviations

- Expanded the helper sweep beyond the task’s minimum expected-output list to include patients, reports, and quiz-adjacent shared wrappers once the residue scan showed they were still advertising the retired transport contract.
- Updated `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` even though it was not in the task’s explicit output list, because it directly exercised the helper signatures and would otherwise remain a stale local proof.

## Known Issues

- The S01 residue allowlist is now further out of date. `verify-runtime-residue.sh --check backend` still fails until T03 republishes the backend residue boundary and handles the remaining `/session/*` retirement work.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` still contains legacy header/bearer detection strings for attempted-auth gating, which the current residue guard still counts as outstanding `x_session_id` / `session_bearer_fallback` anchors.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/localization.py` — moved localization auth off direct `X-Session-ID` dependency and onto canonical cookie-backed session validation.
- `backend-hormonia/app/api/v2/templates_shared.py` — removed local header/bearer session parsing from the template helper wrapper.
- `backend-hormonia/app/api/v2/routers/tasks/dependencies.py` — reduced the task helper dependency to canonical session-cookie auth only.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — stopped forwarding header/bearer transport into admin session resolution while preserving test-bypass suppression for attempted auth.
- `backend-hormonia/app/api/v2/messages/helpers.py` — aligned the message helper wrapper to cookie-only canonical session lookup.
- `backend-hormonia/app/api/v2/patients_shared_helpers.py` — replaced the firebase_uid-only patient helper path with canonical session-cookie lookup.
- `backend-hormonia/app/api/v2/patients_utils.py` — updated the sync patient helper wrapper to use the shared cookie-only contract.
- `backend-hormonia/app/api/v2/routers/patients/base.py` — updated the async patient helper wrapper to use the shared cookie-only contract.
- `backend-hormonia/app/api/v2/routers/reports.py` — removed local header/bearer forwarding from the reports session dependency shim.
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py` — removed local header/bearer forwarding from the enhanced reports session dependency shim.
- `backend-hormonia/app/api/v2/_quiz_shared.py` — updated quiz helper docs to describe the cookie-only contract.
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/_shared.py` — updated monthly quiz helper docs to describe the cookie-only contract.
- `backend-hormonia/tests/api/v2/test_localization.py` — switched auth fixtures to cookie + CSRF and added explicit legacy-header rejection / expired-cookie assertions.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` — switched helper auth fixtures to cookie + CSRF and added explicit header-only rejection proof.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — removed the dual-transport fixture crutch and added explicit header-only rejection in the integrated auth flow.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — aligned the focused helper proof with the cookie-only helper contract.
- `.gsd/milestones/M004/slices/S04/S04-PLAN.md` — marked T02 complete.
- `.gsd/STATE.md` — advanced the slice next action to T03.
