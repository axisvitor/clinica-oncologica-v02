---
estimated_steps: 5
estimated_files: 8
---

# T05: Tombstone legacy Firebase guidance and run local-stack final acceptance

**Slice:** S04 — Hard Cut Cleanup And Integrated Proof
**Milestone:** M002

## Description

Close the slice with operator-facing honesty and assembled proof. This task removes or tombstones Firebase-auth-only docs/tests, runs the full no-Firebase-auth proof gate on the local stack, and records the rerunnable evidence so future agents can inspect the shipped state without rediscovering the slice logic.

## Steps

1. Delete or convert Firebase-auth-only tests and docs into explicit tombstones that point to the session-first S03/S04 proof, focusing on the staff-auth setup guides and Firebase-comprehensive test artifacts that would otherwise mislead future work.
2. Finalize `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` and the local-stack execution notes so the browser acceptance path is reproducible against backend/frontend processes started without Firebase staff-auth env vars.
3. Start the local backend/frontend stack with Firebase staff-auth config intentionally absent, then run the full S04 gate: residue guard, focused vitest suites, frontend build, focused backend pytest suites, and the Playwright acceptance spec.
4. Capture the commands, environment assumptions, and pass/fail results in `.gsd/milestones/M002/slices/S04/S04-PROOF.md`, including where to look when auth or readiness fails.
5. Re-run the residue guard after any doc/test cleanup to ensure no Firebase-auth staff-login guidance or runtime residue has crept back in.

## Must-Haves

- [ ] Repository-facing docs/tests no longer instruct operators or future agents to configure Firebase Auth for staff login.
- [ ] The local browser acceptance path runs against a real no-Firebase-auth stack, not mocked-only infrastructure.
- [ ] Final proof evidence is recorded in a durable slice artifact with commands, assumptions, and diagnostics.
- [ ] Static residue checks still pass after doc/test cleanup.

## Verification

- `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh && cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx tests/integration/auth/hard-cut-cleanup-proof.test.tsx && npm run build`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_password_reset_migration_flow.py tests/integration/test_auth_hard_cut_end_to_end.py -q && cd ../frontend-hormonia && npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts`

## Observability Impact

- Signals added/changed: Final proof documentation consolidates the slice’s runtime, test, and static-inspection signals into one inspectable handoff artifact.
- How a future agent inspects this: Read `S04-PROOF.md`, run the residue guard, then replay the exact vitest/pytest/Playwright commands on the local stack.
- Failure state exposed: Stale Firebase guidance, runtime residue, or local-stack auth regressions are tied to concrete commands and inspection surfaces instead of tribal knowledge.

## Inputs

- All prior S04 tasks — provide the hard-cut implementation, proofs, and residue guard needed for final acceptance.
- Existing frontend/backend Playwright and test harness configuration — reused for the final local-stack no-Firebase-auth execution.

## Expected Output

- `.gsd/milestones/M002/slices/S04/S04-PROOF.md` — durable proof bundle with commands, assumptions, and diagnostics for the hard cut.
- Firebase-auth-only docs/tests are deleted or explicit tombstones that redirect to the session-first proof.
- The full S04 verification gate is runnable and green on a no-Firebase-auth local stack.
