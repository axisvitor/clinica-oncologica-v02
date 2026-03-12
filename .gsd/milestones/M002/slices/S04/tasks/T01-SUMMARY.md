---
id: T01
parent: S04
milestone: M002
provides:
  - Failing hard-cut proof suites and a static Firebase-residue guard that pin the S04 stop condition before cleanup
key_files:
  - frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx
  - backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py
  - backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py
  - backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py
  - frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts
  - .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh
key_decisions:
  - T01 stays proof-first: tests are allowed to fail red against real hard-cut gaps, but not because the files or assertions are missing
patterns_established:
  - Session-first proof files should assert named contracts, stable diagnostics, and no-Firebase staff-auth assumptions directly in focused suites
observability_surfaces:
  - Focused vitest/pytest suites, stable auth error assertions, system readiness/config assertions, and verify-no-firebase-auth.sh
duration: 2h+
verification_result: partial
completed_at: 2026-03-12T13:25:00-03:00
blocker_discovered: false
---

# T01: Add failing hard-cut proof suites and Firebase-residue guard

**Added the S04 proof artifacts and residue guard that freeze the hard-cut target, with the new suites failing against real remaining Firebase/session cleanup gaps.**

## What Happened

I created all six T01 deliverables:

- `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx`
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`
- `.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`

The new proofs explicitly pin the S04 contracts:

- frontend public auth API must not expose a Firebase session bridge
- AuthProvider must not keep Firebase-token-named public helpers
- settings password change must send `current_password` + `new_password` to the first-party endpoint
- backend `/api/v2/auth/password` must stop requiring Firebase UID semantics and must revoke sessions by canonical `user_id`
- `/api/v2/auth/firebase/verify` and Firebase debug-token seams must be removed or tombstoned
- readiness, system health, validation, initialization, and public config must stop treating Firebase auth config as required staff-auth state
- integrated login → verify-session → protected access → reset → password rotation → logout must work through the assembled first-party contract
- browser acceptance must assume Firebase staff-auth env vars are absent and follow the real login/reset/logout path
- static residue scanning must stay scoped to the S04 staff-auth hotspots while ignoring historical `firebase_uid` compatibility data outside those hotspots

This addresses the T01 must-haves at the artifact level:

- proof files now exist and name the exact S04 contracts
- at least one proof checks inspectable diagnostics on failure paths (`error`, `request_id`, readiness/config warnings)
- the browser artifact is scoped to login/reset/password-change/logout on a no-Firebase stack
- the static guard is hotspot-scoped and currently passes from the repo root

## Verification

I ran the focused T01 checks that matter for this proof-first task.

### Frontend proof
- Command: `cd frontend-hormonia && npx vitest run tests/integration/auth/hard-cut-cleanup-proof.test.tsx`
- Result: **fails red on real cleanup gaps**, specifically:
  - `createSession` still exists on the public auth API
  - `getFirebaseToken` is still part of the AuthProvider contract
  - settings password change still submits only `new_password` instead of the first-party `{ current_password, new_password }` contract

### Backend proofs
- Command: `cd backend-hormonia && pytest tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_auth_hard_cut_end_to_end.py -q`
- Result: **fails red on real cleanup gaps**, specifically:
  - `/api/v2/auth/firebase/verify` is still live and returns Firebase-token behavior instead of being removed/tombstoned
  - `app/api/v2/routers/debug/auth.py` still imports/uses Firebase token verification
  - `/api/v2/auth/password` still rejects local/session-first users with `Firebase UID not found`
  - `/api/v2/auth/logout-all` still reports zero Redis invalidations when `firebase_uid` is absent
  - `/health/ready` still treats Firebase config as required readiness state
  - `/api/v2/system/health` still includes Firebase as a component and also hits a datetime JSON serialization issue
  - `/api/v2/system/validate` still warns/recommends Firebase auth setup
  - `/api/v2/system/initialize` still includes `firebase` in initialization components
  - integrated reset → password rotation fails because password change is still Firebase-based

### Static residue guard
- Command: `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
- Result: **passes** after fixing the script root resolution

### Playwright list check
- Command attempted: `cd frontend-hormonia && npx playwright test --list tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts`
- Result: **still reports “No tests found”** under the current Playwright path/config invocation. The spec file exists, but the list command still needs harness alignment.

## Diagnostics

Future agents can inspect this task with:

- `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx`
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`
- `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`

The most actionable current failure signals are:

- `createSession` / `getFirebaseToken` still present on frontend auth surfaces
- `Firebase UID not found` from `/api/v2/auth/password`
- live `/api/v2/auth/firebase/verify`
- Firebase token inspection still present in debug auth router
- readiness/system surfaces still reporting Firebase as required

## Deviations

- I broadened `frontend-hormonia/tests/e2e/playwright.config.e2e.ts` test matching to include `*.spec.ts` so the new acceptance file is in scope for the existing E2E harness, but the requested `--list` invocation still does not enumerate the file yet.

## Known Issues

- The Playwright `--list tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts` invocation still returns “No tests found”; this needs harness/path alignment.
- `backend-hormonia/app/api/v2/routers/system/health.py` currently serializes component payloads in a way that can trip datetime JSON serialization during the proof run.
- The new proof suites are intentionally red until T02–T05 remove the remaining Firebase staff-auth runtime residue.

## Files Created/Modified

- `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx` — frontend hard-cut proof for API/auth-context naming and settings password-change wiring.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` — backend cleanup proof for tombstoned Firebase seams, password change, and canonical logout-all revocation.
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py` — operational proof for no-Firebase readiness, health, validation, initialization, and config.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — integrated login/verify/reset/password-rotate/logout proof.
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` — browser acceptance artifact for the real no-Firebase login/reset/logout path.
- `.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh` — static residue guard scoped to S04 hotspots.
- `frontend-hormonia/tests/e2e/playwright.config.e2e.ts` — updated test matching so the new spec is under the existing E2E harness scope.
