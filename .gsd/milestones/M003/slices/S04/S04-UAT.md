# S04: Dead-Code And Obsolete-Compatibility Cleanup — UAT

**Milestone:** M003
**Written:** 2026-03-13

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S04 ships no new user-facing runtime entrypoint; the acceptance boundary is whether proven-dead residue stays removed, retained compatibility islands stay explicit, and focused frontend/backend proof remains green.

## Preconditions

- The repo contains the S04 handoff artifacts:
  - `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`
  - `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md`
  - `.gsd/milestones/M003/slices/S04/S04-UAT.md`
- Frontend and backend dependencies are installed.
- Tester understands that `backend-hormonia/app/routers/auth_session.py`, `firebase_uid`, and bearer-token fallback behavior are intentionally retained compatibility islands for now.

## Smoke Test

1. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`.
2. Confirm the command ends with `RESULT: --report all OK`.
3. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`.
4. Confirm the command ends with `RESULT: --check all OK`.
5. Open `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`.
6. **Expected:** the manifest clearly separates deleted residue from retained compatibility islands.

## Test Cases

### 1. Deleted frontend residue stays deleted

1. Run `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`.
2. Confirm the suite passes.
3. **Expected:** `frontend-hormonia/src/lib/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, and `frontend-hormonia/src/hooks/use-quiz-session.ts` remain absent, and the focused type-validation proof stays off the deleted compat type barrel.

### 2. Session-first frontend behavior survives the cleanup

1. Run `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`.
2. Confirm the suite passes.
3. **Expected:** session-first auth restore/login/logout, admin auth flow, and realtime websocket cutover remain green on the canonical client/auth surface.

### 3. Frontend compile/build proof still closes

1. Run `cd frontend-hormonia && npm run typecheck && npm run build`.
2. **Expected:** typecheck and production build pass without needing any of the deleted compat files.

### 4. Backend auth dependency surface stays pruned

1. Run `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py`.
2. **Expected:** the suite passes, `verify_firebase_token`, `get_doctor_user`, and `get_current_user_websocket` remain absent from the public auth dependency surface, and websocket auth accepts `jwt` / `session` while rejecting `firebase` / `auto`.

### 5. Manifest coverage and living-gate bookkeeping stay aligned

1. Run the manifest coverage script from the slice plan.
2. **Expected:** it prints `manifest covers removed residue and retained compatibility islands`.

## Edge Cases

### Evidence-map bookkeeping drift after intentional deletions

1. Re-run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` after deleting or restoring any tracked compat file.
2. **Expected:** intentional deletions resolve as zero-line tracked surfaces, while unexpected resurrection or bookkeeping drift causes the verifier to fail clearly instead of silently passing.

## Failure Signals

- `RESULT: --report all OK` or `RESULT: --check all OK` is missing from the evidence-map verifier
- the dead-compat frontend unit pack fails
- the session-first frontend integration pack fails
- `npm run typecheck` or `npm run build` fails
- the focused backend auth/websocket pytest pack fails
- the manifest coverage script reports missing cleanup entries

## Requirements Proved By This UAT

- R035 — dead-code removal stays tied to explicit evidence, focused proof, and the living verifier gate
- R036 — proven-dead compatibility residue is removed while still-live compatibility islands are explicitly isolated and documented

## Not Proven By This UAT

- Final assembled backend/frontend/dashboard/admin smoke across all affected runtime surfaces; that belongs to S05
- Safe deletion of `backend-hormonia/app/routers/auth_session.py`, `firebase_uid`, or bearer-token fallback behavior
- Broader cleanup outside the S04 manifest boundary

## Notes for Tester

- Start with `S04-CLEANUP-MANIFEST.md`; it is the authoritative slice boundary.
- Existing Node `--localstorage-file` warnings in frontend integration tests and the `pytest_asyncio` loop-scope deprecation warning are known non-blocking diagnostics from the final proof rerun.
- If a future slice wants to remove one of the retained compatibility islands, it must replace this artifact-driven proof with new evidence rather than assume the island is already dead.
