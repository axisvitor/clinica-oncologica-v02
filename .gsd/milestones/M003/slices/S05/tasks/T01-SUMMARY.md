---
id: T01
parent: S05
milestone: M003
provides:
  - Replayed the structural closeout proof pack on the S05 branch and re-established a known-green cleanup baseline before runtime smoke.
key_files:
  - .gsd/milestones/M003/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/S05-PLAN.md
  - .gsd/STATE.md
key_decisions:
  - Treat the S01 evidence-map metrics as the authoritative structural closeout anchors for S05 replay.
patterns_established:
  - Re-run the focused S04 proof pack before any assembled runtime smoke so runtime regressions are not conflated with cleanup-boundary drift.
observability_surfaces:
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all
  - frontend-hormonia vitest output for the focused unit and integration packs
  - backend-hormonia pytest output for the auth/session proof pack
duration: 5m
verification_result: passed
completed_at: 2026-03-13T13:48:38-03:00
blocker_discovered: false
---

# T01: Re-run the structural closeout gate

**Replayed the focused S04 cleanup proof pack and confirmed the S01 evidence-map verifier is still green on the current S05 branch.**

## What Happened

I used the S04 cleanup manifest and S04 summary as the replay contract, then reran the focused frontend unit pack, frontend integration pack, frontend typecheck/build, the current S05 backend auth/session proof command, and both S01 evidence-map verifier modes without widening beyond the task contract.

Everything passed on the first run. There was no cleanup-boundary regression, no focused-contract regression, and no environment-only noise that needed isolation before T02.

The evidence-map output matched the anchored S04 snapshot exactly:

```text
[backend]
  - backend.auth_dependencies.lines=675
  - backend.auth_router.lines=1245
  - backend.auth_session.lines=731
  - backend.admin_dependencies.lines=136
  - backend.reports.lines=787
  - backend.enhanced_reports.lines=764
  - backend.roles_dependencies.lines=23
  - backend.flows.lines=1281
  - backend.message_handler.lines=1126
  - backend.depends.get_current_user_from_session=202
  - backend.depends.get_current_user_object_from_session=7
  - backend.depends.get_current_user=60
  - backend.depends.get_admin_user=68
  - backend.hardcoded_session_id_alias=9
  - backend.candidate.verify_firebase_token.repo_refs=4
  - backend.candidate.get_doctor_user.repo_refs=1
  - backend.candidate.get_current_user_websocket.repo_refs=2

[frontend]
  - frontend.api_client_facade.lines=75
  - frontend.api_client_facade.imports=103
  - frontend.api_client_index.lines=223
  - frontend.api_client_types.lines=26
  - frontend.api_client_types.imports=34
  - frontend.types_api.lines=900
  - frontend.types_api.imports=50
  - frontend.legacy_types.lines=0
  - frontend.legacy_types.imports=0
  - frontend.legacy_api.lines=0
  - frontend.legacy_api.imports=0
  - frontend.use_quiz_session.lines=0
  - frontend.duplicate_exports.count=0
  - frontend.risk_assessment_request.direct_declarations=0
  - frontend.duplicate_exports.names=

[handoff]
  - handoff.summary.open_scaffold_items=0
  - handoff.uat.open_scaffold_items=0
```

The backend command defined by the current S05 verification contract includes `tests/integration/test_auth_hard_cut_end_to_end.py` in addition to the S04 manifest’s focused backend cleanup pack. It stayed green and remained auth/session-scoped, so T01 still starts T02 from a clean structural baseline.

No product code changed in this task. Only the slice artifacts/state were updated to record the green replay.

## Verification

Passed:

- `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
  - Passed: 3 files / 21 tests green.
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - Passed: 4 files / 43 tests green.
- `cd frontend-hormonia && npm run typecheck && npm run build`
  - Passed: TypeScript clean; Vite production build completed after transforming 4758 modules.
- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py tests/integration/test_auth_hard_cut_end_to_end.py`
  - Passed: suite completed green at 100%.
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
  - Passed: ended with `RESULT: --report all OK`.
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
  - Passed: ended with `RESULT: --check all OK`.

## Diagnostics

Replay the structural gate with:

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
- the focused frontend and backend commands listed above

Accepted non-blocking diagnostics that remained unchanged from S04:

- frontend integration tests still emit the existing Node warning: ``--localstorage-file was provided without a valid path``
- backend pytest still emits the existing `pytest_asyncio` deprecation warning about `asyncio_default_fixture_loop_scope`

## Deviations

None.

## Known Issues

- The existing frontend Node `--localstorage-file` warning is still present during the focused integration pack.
- The existing backend `pytest_asyncio` deprecation warning is still present during the focused pytest pack.

## Files Created/Modified

- `.gsd/milestones/M003/slices/S05/tasks/T01-SUMMARY.md` — recorded the structural closeout replay, command outcomes, anchored metrics, and accepted diagnostics.
- `.gsd/milestones/M003/slices/S05/S05-PLAN.md` — marked T01 complete.
- `.gsd/STATE.md` — advanced the next action to T02.
