---
id: T02
parent: S06
milestone: M004
provides:
  - Closed the mounted auth acceptance on the live no-Firebase stack and made the published preflight health/config probe truthful by preserving the stack briefly for immediate follow-up curls.
key_files:
  - .gsd/milestones/M004/slices/S06/run-mounted-proof.sh
  - .gsd/milestones/M004/slices/S06/S06-PLAN.md
  - .gsd/DECISIONS.md
  - .gsd/STATE.md
key_decisions:
  - Treat a successful mounted `--preflight` as a short-lived inspectable state: keep the local stack alive just long enough for the published follow-up curls, then auto-clean it.
patterns_established:
  - Validate the assembled auth runtime in layers: residue guard and backend auth pack first, mounted Chromium auth acceptance second, then repair only runner/bootstrap truth surfaces if the live replay is already green.
observability_surfaces:
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all
  - cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py
  - bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth
  - bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config
  - /tmp/gsd-s06-mounted-proof/status.json
  - /tmp/gsd-s06-mounted-proof/backend.log
  - /tmp/gsd-s06-mounted-proof/frontend.log
  - /tmp/gsd-s06-proof.env
  - /tmp/gsd-s06-browser-bootstrap
duration: 0h40m
verification_result: passed
completed_at: 2026-03-14T19:41:00-03:00
blocker_discovered: false
---

# T02: Fechar a aceitação auth/session-first no stack montado

**The live no-Firebase auth acceptance is green on the mounted stack, and the runner now keeps `--preflight` alive briefly so the published post-preflight health/config curls tell the truth instead of hitting a torn-down backend.**

## What Happened

I started with the contract checks the task plan called for under blank Firebase envs. The residue guard stayed green, and the backend auth/runtime pack (`test_system_auth_hard_cut_operational.py`, `test_local_auth_core_flow.py`, `test_auth_hard_cut_end_to_end.py`) also stayed green, so there was no evidence that S04/S05 drifted before the browser replay.

From there I ran the mounted proof against the real local stack with the seeded admin user and the existing Chromium acceptance. `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth` passed on the live backend/frontend contract without any auth/session code changes in `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `frontend-hormonia/src/features/auth/ProtectedRoute.tsx`, or `frontend-hormonia/src/lib/config-initializer.tsx`. That means the real `/login` → `/dashboard` lifecycle, reload/restore, reset request, reset confirm, password rotation, logout, and logout-all already agree with the mounted runtime.

The only regression exposed in this unit was operational: the slice’s written verification command `bash .../run-mounted-proof.sh --preflight && curl ...` was false because the runner cleaned up the backend/frontend before the follow-up curls ran. I fixed that in `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` by preserving the mounted stack for a short configurable window (`MOUNTED_PROOF_PREFLIGHT_HOLD_SECONDS`, default `10`) after a successful `--preflight`, then auto-cleaning the listeners. After that fix, the published command successfully hit the live `/health/ready` and `/api/v2/system/config` surfaces on the same mounted no-Firebase runtime.

This closes the T02 must-haves in runtime terms: the auth acceptance runs against the real stack and seeded local admin, Firebase envs stay blank with cookie-only transport and no Firebase browser traffic during the mounted auth replay, and the canonical readiness/config endpoints stay green without operational drift.

## Verification

Passed in this unit:

- `export FIREBASE_ADMIN_PROJECT_ID='' FIREBASE_ADMIN_CLIENT_EMAIL='' FIREBASE_ADMIN_PRIVATE_KEY='' FIREBASE_PROJECT_ID='' VITE_FIREBASE_API_KEY='' VITE_FIREBASE_PROJECT_ID='' VITE_FIREBASE_APP_ID='' VITE_FIREBASE_AUTH_DOMAIN=''; bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
  - Result: **PASS**
  - Observed: backend approved residue stayed on the published post-S05 boundary; frontend still reported no approved residue.

- `export FIREBASE_ADMIN_PROJECT_ID='' FIREBASE_ADMIN_CLIENT_EMAIL='' FIREBASE_ADMIN_PRIVATE_KEY='' FIREBASE_PROJECT_ID='' VITE_FIREBASE_API_KEY='' VITE_FIREBASE_PROJECT_ID='' VITE_FIREBASE_APP_ID='' VITE_FIREBASE_AUTH_DOMAIN=''; cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py`
  - Result: **PASS**
  - Observed: 7 tests passed; unchanged `pytest_asyncio` loop-scope deprecation warning only.

- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`
  - Result: **PASS**
  - Observed: the live Chromium acceptance passed on the mounted no-Firebase stack with the seeded admin user; login, reload/restore, reset, password rotation, logout, logout-all, and no-Firebase browser traffic all stayed green.

- `bash -n .gsd/milestones/M004/slices/S06/run-mounted-proof.sh`
  - Result: **PASS**

- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config`
  - Result: **PASS**
  - Observed: the runner preserved the mounted stack long enough for immediate follow-up probes; `/health/ready` reported `session_auth` and no Firebase dependency, and `/api/v2/system/config` stayed free of Firebase config keys.

Slice-level verification status at the end of T02:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — **PASS**
- `cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth` — **PASS**
- `cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium` — **not run in this unit**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all` — **not run in this unit**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config` — **PASS**

## Diagnostics

Use these surfaces to inspect what T02 closed without reconstructing the runtime:

- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth` — canonical live auth/session-first replay on the mounted stack.
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config` — truthful mounted readiness/config probe after the short preflight hold window.
- `/tmp/gsd-s06-mounted-proof/status.json` — last phase/status and artifact paths.
- `/tmp/gsd-s06-mounted-proof/backend.log` and `/tmp/gsd-s06-mounted-proof/frontend.log` — mounted stack logs.
- `/tmp/gsd-s06-proof.env` — masked replay contract only.
- `/tmp/gsd-s06-browser-bootstrap` — reseeds on demand before replay commands without persisting plaintext fixtures.

## Deviations

- No backend/frontend auth-flow code changes were needed in the expected seam files because the mounted Chromium proof was already green; the only real fix in this unit was to the runner’s preflight lifecycle so the published observability/verification command became true.

## Known Issues

- `cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium` and `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all` still belong to T03 and were not run in this unit.
- The existing backend startup noise from the seed helper (rate limiter/passlib warnings) is unchanged and non-blocking; it still does not print credentials or reset tokens.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — preserved a successful `--preflight` stack briefly for live follow-up curls, then auto-cleaned it so the published mounted verification path is truthful.
- `.gsd/DECISIONS.md` — recorded the short-lived mounted preflight preservation decision for post-preflight live probes.
- `.gsd/milestones/M004/slices/S06/S06-PLAN.md` — marked T02 complete.
- `.gsd/STATE.md` — advanced the next action to T03.
