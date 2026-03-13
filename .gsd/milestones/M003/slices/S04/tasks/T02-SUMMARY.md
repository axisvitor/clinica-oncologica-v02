---
id: T02
parent: S04
milestone: M003
provides:
  - Pinned the already-pruned backend auth dependency surface with negative contract coverage and explicit websocket legacy-mode rejection proofs.
key_files:
  - backend-hormonia/tests/unit/test_auth_dependency_module_split.py
  - backend-hormonia/tests/services/websocket/test_connection_manager.py
  - backend-hormonia/tests/validation/test_vulnerability_scenarios.py
key_decisions:
  - Do not reintroduce removed auth wrappers for test compatibility; assert their absence on the public dependency surface instead.
  - Treat legacy websocket auth_type values (`firebase`, `auto`) as explicitly unsupported and test that rejection rather than preserving fallback mocks.
patterns_established:
  - When a dead auth/export seam is already pruned in runtime code, convert stale tests into negative contract checks and explicit legacy-mode rejection coverage instead of rebuilding compatibility shims.
observability_surfaces:
  - Named pytest suites for the auth split contract, websocket manager auth modes, session-first websocket contract, and hard-cut cleanup proofs.
duration: 1h
verification_result: passed
completed_at: 2026-03-13T12:03:17-03:00
blocker_discovered: false
---

# T02: Prune dead backend auth dependency exports and legacy helper residue

**Pinned the already-pruned backend auth surface with negative contract tests and explicit websocket legacy-mode rejection coverage.**

## What Happened

`backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/__init__.py`, and `backend-hormonia/app/dependencies/auth_legacy_firebase.py` were already in the desired post-prune state: `verify_firebase_token`, `get_doctor_user`, and `get_current_user_websocket` were absent from the public surface, and the legacy helper module no longer implemented the removed websocket/Firebase façade helpers.

The failing proof was therefore stale test residue, not missing runtime cleanup. I updated `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` to assert the narrowed public/package export surface directly and to confirm the legacy helper module still lacks the removed Firebase/websocket helpers. I also rewrote `backend-hormonia/tests/services/websocket/test_connection_manager.py` so it proves the current websocket contract (`jwt` and `session`) and explicitly rejects the retired `firebase` / `auto` auth modes instead of patching non-existent symbols. Finally, I updated `backend-hormonia/tests/validation/test_vulnerability_scenarios.py` to reflect the tombstoned Firebase verify route so a latent dead-symbol patch does not re-break later full-suite runs.

## Verification

- Passed: `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py tests/validation/test_vulnerability_scenarios.py::TestSessionFixationVulnerabilities::test_tombstoned_firebase_verify_route_does_not_issue_session`
- Passed: `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
- Passed: `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- Passed: `cd frontend-hormonia && npm run typecheck && npm run build`
- Failed (pre-existing slice follow-up, not a T02 runtime regression): `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` because the verifier still expects `frontend-hormonia/src/lib/types/api.ts`, which T01 intentionally deleted and T03 is expected to reconcile/document.

## Diagnostics

- Re-run `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` to inspect the narrowed auth dependency surface contract.
- Re-run `backend-hormonia/tests/services/websocket/test_connection_manager.py` to inspect explicit acceptance of `jwt` / `session` and rejection of `firebase` / `auto` auth modes.
- Re-run `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` and `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` to confirm the session-first websocket/auth hard-cut diagnostics remain authoritative.

## Deviations

Updated one additional latent security test outside the task’s focused verification pack (`backend-hormonia/tests/validation/test_vulnerability_scenarios.py`) so the repo no longer contains another stale patch against the removed `verify_firebase_token` export.

## Known Issues

- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` is still out of sync with the deleted frontend compat file from T01; that bookkeeping/doc alignment remains for T03.
- The pytest run still emits the existing `pytest_asyncio` deprecation warning about `asyncio_default_fixture_loop_scope` being unset.

## Files Created/Modified

- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — replaced stale delegation expectations with negative contract checks for removed auth exports/helpers.
- `backend-hormonia/tests/services/websocket/test_connection_manager.py` — converted Firebase/auto-fallback expectations into current-contract (`jwt`/`session`) coverage plus explicit legacy-mode rejection.
- `backend-hormonia/tests/validation/test_vulnerability_scenarios.py` — aligned the session-fixation proof with the tombstoned Firebase verify route instead of patching a removed export.
- `.gsd/milestones/M003/slices/S04/S04-PLAN.md` — marked T02 complete.
- `.gsd/STATE.md` — advanced the slice next action to T03.
