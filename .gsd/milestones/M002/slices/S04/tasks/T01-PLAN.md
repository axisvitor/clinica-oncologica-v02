---
estimated_steps: 5
estimated_files: 6
---

# T01: Add failing hard-cut proof suites and Firebase-residue guard

**Slice:** S04 — Hard Cut Cleanup And Integrated Proof
**Milestone:** M002

## Description

Freeze the S04 stopping condition before cleanup work starts. This task adds the proof artifacts that must fail until Firebase-auth runtime residue is actually removed, first-party password change is wired, backend operational surfaces become truthful, and the local stack works without Firebase staff-auth configuration.

## Steps

1. Add `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx` asserting that the frontend auth client/context exposes only session-first staff-auth behavior: no Firebase session bridge, no Firebase-token-named helper on the public provider contract, and settings password change uses the first-party endpoint contract.
2. Add `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` covering removed/tombstoned Firebase verify/debug seams, first-party `/api/v2/auth/password` behavior, and logout-all/session-revocation keyed to canonical `user_id` rather than Firebase-only identity.
3. Add `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py` plus `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` proving readiness/config/initialization remain truthful with Firebase auth env absent and that login → verify-session → protected access → reset/password rotation → logout works through the assembled first-party contract.
4. Add `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` as the real browser acceptance script against a local no-Firebase-auth stack, reusing the existing Playwright harness and seeded-auth fixtures instead of creating a new runner.
5. Add `.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh` to fail on leftover Firebase-auth imports/routes/env guidance in the S04 hotspots while explicitly excluding out-of-scope historical `firebase_uid` compatibility data.

## Must-Haves

- [ ] New proof files name the exact S04 contracts and fail for real hard-cut gaps rather than harness/setup issues.
- [ ] The static guard checks staff-auth runtime, config, docs, and Firebase-only tests without broad false positives from unrelated compatibility data.
- [ ] Browser acceptance is scoped to the actual login/reset/logout demo path and assumes Firebase staff-auth env vars are absent.
- [ ] At least one proof checks inspectable diagnostics on failure paths, not just happy-path success.

## Verification

- `cd frontend-hormonia && npx vitest run tests/integration/auth/hard-cut-cleanup-proof.test.tsx && cd ../backend-hormonia && pytest tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_auth_hard_cut_end_to_end.py -q`
- `cd frontend-hormonia && npx playwright test --list tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts && cd .. && bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`

## Observability Impact

- Signals added/changed: Proof now pins stable auth error codes/messages, request correlation/phase diagnostics, and honest system readiness/config output as slice requirements.
- How a future agent inspects this: Run the focused vitest/pytest suites, inspect Playwright trace output from the e2e spec, and execute `verify-no-firebase-auth.sh` for residue checks.
- Failure state exposed: Residual Firebase runtime calls, dishonest readiness/config signals, password-change gaps, or opaque auth failures become concrete failing assertions with named files and routes.

## Inputs

- `.gsd/milestones/M002/slices/S04/S04-PLAN.md` — defines the S04 final-assembly proof gate and scoped hotspots.
- Existing cutover suites from S01–S03 — provide the canonical session-first auth contracts to extend rather than replacing the test harness.

## Expected Output

- `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx` and `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` — new frontend proof artifacts for hard-cut behavior.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`, `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`, and `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — backend/API/integration proof artifacts for the hard cut.
- `.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh` — repeatable static residue guard for staff-auth Firebase cleanup.
