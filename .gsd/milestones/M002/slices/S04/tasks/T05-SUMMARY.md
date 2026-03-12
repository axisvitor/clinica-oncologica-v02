---
id: T05
parent: S04
milestone: M002
provides:
  - Legacy Firebase-auth staff-login guidance is tombstoned toward the session-first proof surface.
  - The rerunnable hard-cut proof bundle is captured in `S04-PROOF.md` with real no-Firebase stack assumptions and diagnostics.
  - The final S04 verification gate was replayed far enough to prove static/doc cleanup, focused frontend/backend suites, and Playwright discovery, while exposing one remaining real browser-acceptance blocker.
key_files:
  - frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts
  - frontend-hormonia/tests/e2e/playwright.config.e2e.ts
  - frontend-hormonia/tests/e2e/README.md
  - frontend-hormonia/tests/e2e/SETUP_INSTRUCTIONS.md
  - docs/frontend/guides/api/API_GUIDE.md
  - docs/frontend/guides/configuration/ENVIRONMENT_GUIDE.md
  - docs/frontend/guides/deployment/DEPLOYMENT_GUIDE.md
  - backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py
  - .gsd/milestones/M002/slices/S04/S04-PROOF.md
key_decisions:
  - Playwright E2E config now uses `testDir: '.'` because the config file itself lives under `tests/e2e/`; the previous nested `./tests/e2e` value caused zero-test discovery for the new hard-cut spec.
  - T05 records the real assembled state honestly: static residue cleanup and focused proof gates are green, but the final browser acceptance remains blocked in the frontend/browser path even though direct backend login works on the same local stack.
patterns_established:
  - Final handoff proof for a hard cut should separate green static/runtime gates from red assembled-browser gates instead of hiding a remaining acceptance failure behind documentation cleanup.
  - Repository-facing docs should point operators to the rerunnable proof artifact instead of duplicating auth setup instructions that can drift.
observability_surfaces:
  - .gsd/milestones/M002/slices/S04/S04-PROOF.md
  - bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh
  - frontend-hormonia/test-results/
  - frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts
  - frontend-hormonia/tests/e2e/playwright.config.e2e.ts
  - backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py
verification_result: partial
completed_at: 2026-03-12T15:40:00-03:00
blocker_discovered: true
---

# T05: Tombstone legacy Firebase guidance and run local-stack final acceptance

**Closed the documentation/proof handoff for S04 and reran the slice gate far enough to prove the no-Firebase hard cut everywhere except the final real-browser login transition.**

## What Happened

I replaced the placeholder with a real T05 handoff and finished the repository-facing cleanup that T04 had left behind.

### Docs and operator guidance cleanup

I rewrote the remaining staff-auth-facing guides so they no longer teach Firebase Auth setup for staff login:

- `frontend-hormonia/tests/e2e/README.md`
- `frontend-hormonia/tests/e2e/SETUP_INSTRUCTIONS.md`
- `docs/frontend/guides/api/API_GUIDE.md`
- `docs/frontend/guides/configuration/ENVIRONMENT_GUIDE.md`
- `docs/frontend/guides/deployment/DEPLOYMENT_GUIDE.md`

Those files now point to the session-first contract and to `.gsd/milestones/M002/slices/S04/S04-PROOF.md` as the rerunnable source of truth.

### Playwright hard-cut harness follow-up

I completed the new acceptance harness shape:

- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`
  - asserts public config does not contain Firebase staff-auth guidance
  - exercises login → restore → reset-request → reset-confirm → in-app password change → logout → logout-all
  - watches for unexpected `/auth/firebase/verify` or Firebase network traffic
- `frontend-hormonia/tests/e2e/playwright.config.e2e.ts`
  - changed `testDir` to `'.'` so the spec is actually discoverable under the existing config location

### Proof artifact

I wrote `.gsd/milestones/M002/slices/S04/S04-PROOF.md` with:

- backend/frontend startup assumptions for a no-Firebase-auth local stack
- rerunnable verification commands
- green results for the residue guard, vitest suites, build, backend pytest, readiness/config truth checks, and Playwright discovery
- the remaining browser-acceptance failure state and where to inspect it

### Backend integration proof alignment

I also updated `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` so the integrated backend proof matches the shipped session-first behavior after password change revokes the active session. `logout-all` is now exercised only after a fresh re-login.

## Verification

I reran the T05 gate components and recorded the actual results.

### Static residue guard
- Command: `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
- Result: **PASS**

Observed output:
- `verify-no-firebase-auth.sh: session-first staff-auth hotspots are free of Firebase-auth residue.`

### Frontend focused hard-cut suites
- Command:
  - `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx tests/integration/auth/hard-cut-cleanup-proof.test.tsx`
- Result: **PASS** (`5 files, 18 tests`)

### Frontend production build
- Command:
  - `cd frontend-hormonia && npm run build`
- Result: **PASS**

### Backend focused hard-cut suites
- Command:
  - `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_password_reset_migration_flow.py tests/integration/test_auth_hard_cut_end_to_end.py -q`
- Result: **PASS**

### Local-stack operational truth checks
- Probe: `GET /health/ready`
  - Result: **PASS**
  - Observed `status=ready` with `database`, `redis`, and `session_auth`
- Probe: `GET /api/v2/system/config`
  - Result: **PASS**
  - Observed no Firebase public-config fields in the payload

### Playwright discovery
- Command:
  - `cd frontend-hormonia && npx playwright test --list --config tests/e2e/playwright.config.e2e.ts`
- Result: **PASS**
- The new spec is discoverable as:
  - `auth/session-first-hard-cut.spec.ts`

### Playwright browser acceptance
- Command:
  - `cd frontend-hormonia && npx playwright test auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts --project=chromium`
- Result: **FAIL**

Current failure signal:
- login form submits
- page remains on `/login`
- `expect(page).toHaveURL(/\/dashboard/)` times out

Important contrast check captured in `S04-PROOF.md`:
- a direct backend login probe against `POST /api/v2/auth/login` succeeds with `200 OK` on the same local stack
- this leaves the remaining blocker in the browser/frontend acceptance path rather than in the backend auth contract itself

## Diagnostics

The most useful places to inspect the remaining blocker are:

- `.gsd/milestones/M002/slices/S04/S04-PROOF.md`
- `frontend-hormonia/test-results/auth-session-first-hard-cu-45145--all-on-a-no-Firebase-stack-chromium/`
  - `test-failed-1.png`
  - `video.webm`
  - `error-context.md`
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`
- `frontend-hormonia/src/app/providers/AuthContext.tsx`
- `frontend-hormonia/src/features/auth/ProtectedRoute.tsx`
- `frontend-hormonia/src/lib/api-client/auth.ts`
- `frontend-hormonia/src/lib/api-client/core.ts`

Most actionable browser symptom from the failed run:
- the login button enters loading state (`Entrando...`) and the page remains at `http://localhost:5173/login` with no visible user-safe error surfaced before the URL assertion times out

## Deviations

- I did **not** mark the whole slice complete in this task summary because the final assembled Playwright acceptance is still red. The task now honestly records a partial closeout/handoff instead of leaving the placeholder file empty.
- I broadened the T05 proof notes beyond docs-only cleanup so the durable artifact includes the exact green/red split of the real gate, which is more useful to the next agent than a falsely “complete” summary.

## Known Issues

- The final Playwright hard-cut acceptance still fails during the first browser login transition: the frontend stays on `/login` instead of navigating to `/dashboard`.
- Because of that remaining red signal, T05’s verification is **partial**, even though the residue guard, focused frontend/backend suites, build, doc cleanup, and Playwright discovery are green.
- The current blocker appears to be in the frontend/browser acceptance path, not in the backend login endpoint itself.

## Files Created/Modified

- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` — finalized session-first browser proof assertions for config truth, reset, password rotation, logout, logout-all, and no-Firebase network residue.
- `frontend-hormonia/tests/e2e/playwright.config.e2e.ts` — fixed spec discovery by using `testDir: '.'`.
- `frontend-hormonia/tests/e2e/README.md` — rewrote E2E auth guidance toward the session-first hard-cut proof.
- `frontend-hormonia/tests/e2e/SETUP_INSTRUCTIONS.md` — replaced legacy setup guidance with the session-first local-stack replay steps.
- `docs/frontend/guides/api/API_GUIDE.md` — removed staff-auth Firebase guidance and documented the current session-first auth API contract.
- `docs/frontend/guides/configuration/ENVIRONMENT_GUIDE.md` — removed frontend Firebase-auth env guidance for staff auth.
- `docs/frontend/guides/deployment/DEPLOYMENT_GUIDE.md` — removed Firebase-auth deployment guidance and aligned deploy validation to session-first auth.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — aligned integrated backend proof sequencing with immediate session revocation after password change.
- `.gsd/milestones/M002/slices/S04/S04-PROOF.md` — durable proof artifact with commands, assumptions, green checks, failure state, and diagnostics.
- `.gsd/milestones/M002/slices/S04/tasks/T05-SUMMARY.md` — replaced blocker placeholder with this real execution summary.
