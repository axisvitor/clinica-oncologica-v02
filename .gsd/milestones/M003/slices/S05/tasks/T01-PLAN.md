---
estimated_steps: 4
estimated_files: 3
---

# T01: Re-run the structural closeout gate

**Slice:** S05 — Integrated Proof And Structural Closeout
**Milestone:** M003

## Description

Re-establish the post-S04 cleanup boundary before any assembled runtime smoke. This task replays the focused proof pack that already defines the structural closeout contract, then reruns the living evidence-map verifier so later browser/runtime work starts from a known-green baseline instead of mixing boundary drift with runtime noise.

## Steps

1. Re-run the focused frontend unit, frontend integration, frontend typecheck/build, and backend auth/session proof commands documented by the S04 cleanup manifest.
2. Re-run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` and `--check all` on the same branch state.
3. If anything fails, isolate whether the regression is a real cleanup-boundary break, a focused contract break, or environment noise before moving on.
4. Write `T01-SUMMARY.md` with the exact commands, pass/fail status, anchored metrics, and any non-blocking diagnostics that remain acceptable for S05.

## Must-Haves

- [ ] The S04 focused proof pack is replayed on the current branch without widening scope.
- [ ] The S01 evidence-map verifier is green, or any failure is isolated clearly enough to block T02 on evidence instead of guesswork.

## Verification

- `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`

## Inputs

- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` — authoritative focused proof pack and retained-compatibility boundary from the previous slice.
- `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md` — forward-intelligence handoff on what S05 should trust and what remains fragile.
- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — living structural gate for hotspot sizes, deleted residue, and retained cleanup bookkeeping.

## Expected Output

- `.gsd/milestones/M003/slices/S05/tasks/T01-SUMMARY.md` — replay log for the structural closeout gate, including exact commands, current green/red status, and any accepted diagnostics.
