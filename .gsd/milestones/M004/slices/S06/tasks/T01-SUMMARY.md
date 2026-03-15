---
id: T01
parent: S06
milestone: M004
provides:
  - Added a replayable mounted-runtime entrypoint, ephemeral proof-user seeding with masked `/tmp` artifacts, and the thin routed smoke spec required to drive S06 on one no-Firebase stack.
key_files:
  - .gsd/milestones/M004/slices/S06/run-mounted-proof.sh
  - .gsd/milestones/M004/slices/S06/seed-proof-user.py
  - frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts
  - frontend-hormonia/playwright.config.ts
  - .gsd/milestones/M004/slices/S06/S06-PLAN.md
key_decisions:
  - Keep only masked proof artifacts in `/tmp` and generate real `E2E_SESSION_FIRST_*` exports on demand through a reseeding bootstrap helper instead of persisting plaintext credentials or reset tokens.
patterns_established:
  - Use one shell entrypoint to own blank-Firebase envs, WuzAPI mock wiring, runtime probes, seed refresh, and Playwright invocation so auth and smoke stay pointed at the same mounted contract.
observability_surfaces:
  - /tmp/gsd-s06-mounted-proof/status.json
  - /tmp/gsd-s06-mounted-proof/backend.log
  - /tmp/gsd-s06-mounted-proof/frontend.log
  - /tmp/gsd-s06-proof.env
  - /tmp/gsd-s06-browser-bootstrap
  - bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight
  - cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium --list
duration: 1h05m
verification_result: passed
completed_at: 2026-03-14T19:31:00-03:00
blocker_discovered: false
---

# T01: Codificar o replay montado da prova sem Firebase

**Shipped a replayable S06 mounted-proof runner, masked proof-user seeding/bootstrap, and a routed runtime smoke spec that discovers cleanly from the project root Playwright command.**

## What Happened

I fixed the slice plan’s observability gap first by adding an explicit verification step that queries `/health/ready` and `/api/v2/system/config` after the mounted preflight, so the slice no longer relies only on opaque green exits.

From there I built the S06 execution spine in `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh`. The runner owns the no-Firebase launch contract from M002/S04: it blanks `FIREBASE_ADMIN_*` and `VITE_FIREBASE_*`, injects `WHATSAPP_WUZAPI_USE_MOCK=true` with a dummy token, starts backend/frontend on ports `8000` and `5173`, probes `/health/ready`, `/api/v2/system/config`, and `/api/v2/monitoring/wuzapi/session/status`, refreshes the proof-user contract, and exposes phase-specific logs/status files under `/tmp/gsd-s06-mounted-proof`.

I added `.gsd/milestones/M004/slices/S06/seed-proof-user.py` as the proof-user helper. It runs under `backend-hormonia/.venv`, creates or updates a local **admin** proof user, generates a fresh reset token, writes only masked replay material to `/tmp/gsd-s06-proof.env`, and emits real `E2E_SESSION_FIRST_*` exports only in-memory for the runner. For manual replay, it also writes `/tmp/gsd-s06-browser-bootstrap`, which reseeds on demand and then execs the requested command without leaving plaintext credentials or reset tokens at rest.

On the frontend side I added `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts`. The smoke uses the official `/login` entrypoint, proves `/admin` redirects there when unauthenticated, logs in once, then asserts the live routed runtime on `/admin`, `/dashboard`, and `/whatsapp` using real backend fetches (`/api/v2/analytics/overview`, `/api/v2/dashboard/main`, `/api/v2/monitoring/wuzapi/session/status`) while also rejecting Firebase network drift and `/admin/login` fallback.

The slice/task verification command for the smoke omits `--config`, so I added `frontend-hormonia/playwright.config.ts` at the project root to re-export the existing E2E config and set a non-clashing `outputDir`. That keeps the written verification command truthful instead of depending on a hidden extra flag.

I also tightened runner cleanup after the first failed replay left Vite listening on `5173`. The runner now kills listeners on its own bound ports when it started those processes, so repeated runs don’t fail on their own residue.

## Verification

Passed in this unit:

- `chmod +x .gsd/milestones/M004/slices/S06/run-mounted-proof.sh .gsd/milestones/M004/slices/S06/seed-proof-user.py && bash -n .gsd/milestones/M004/slices/S06/run-mounted-proof.sh && python3 -m py_compile .gsd/milestones/M004/slices/S06/seed-proof-user.py`
  - Result: **PASS**
- `cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium --list`
  - Result: **PASS**
  - Observed: the new runtime smoke is discoverable from the project-root Playwright command the task/slice plan expects.
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight`
  - Result: **PASS**
  - Observed: backend/frontend booted on the mounted no-Firebase contract, `/health/ready` reported `session_auth` with no `firebase`, `/api/v2/system/config` stayed free of Firebase config keys, mocked WuzAPI status returned connected/logged-in, and the proof-user seed completed with masked `/tmp` artifacts.

Slice-level verification status at the end of T01:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — **not run in this unit**
- `cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py` — **not run in this unit**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth` — **not run in this unit**
- `cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium` — **not run in this unit**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all` — **not run in this unit**

Those remaining slice-level executions are still owned by T02/T03; this task closed the mounted entrypoint, seed contract, and smoke discovery/preflight prerequisites they depend on.

## Diagnostics

Use these surfaces to inspect or resume the mounted proof without reconstructing the setup:

- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight`
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke`
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`
- `/tmp/gsd-s06-mounted-proof/status.json` — last phase, status, and artifact paths without secrets
- `/tmp/gsd-s06-mounted-proof/backend.log`
- `/tmp/gsd-s06-mounted-proof/frontend.log`
- `/tmp/gsd-s06-proof.env` — masked replay contract only
- `/tmp/gsd-s06-browser-bootstrap` — reseeds on demand and then execs a replay command without storing plaintext credentials at rest

The most useful next replay for T02 is `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`, because it uses the exact same stack/seed contract that passed preflight here.

## Deviations

- Added `frontend-hormonia/playwright.config.ts` even though the task plan did not name it explicitly, because the written verification command for the new smoke omits `--config` and needed a truthful project-root Playwright entrypoint.
- Updated `.gsd/milestones/M004/slices/S06/S06-PLAN.md` to add an explicit diagnostic/status-surface verification step (`/health/ready` + `/api/v2/system/config`) before continuing with the unit, per the flagged pre-flight observability gap.

## Known Issues

- `run-mounted-proof.sh --preflight` is green, but the mounted auth acceptance (`--auth`) and full routed smoke execution (`--smoke` / `--all`) were not run in this unit; any real browser/auth regression still belongs to T02/T03.
- The seed helper emits backend startup/logging noise to stderr during replay because importing the backend settings stack initializes the same operational logging surfaces as the live app. It does not print credentials or reset tokens, but the output is noisier than the masked summary file.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — added the replayable mounted-runtime entrypoint with phased preflight/seed/auth/smoke execution, runtime probes, status file output, and cleanup.
- `.gsd/milestones/M004/slices/S06/seed-proof-user.py` — added the proof-user seed/reset helper with masked `/tmp` artifacts and on-demand bootstrap exports.
- `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts` — added the thin routed smoke for `/login`, `/admin`, `/dashboard`, and `/whatsapp` on the live no-Firebase stack.
- `frontend-hormonia/playwright.config.ts` — added a project-root Playwright config so the slice verification command works without an extra `--config` flag.
- `.gsd/milestones/M004/slices/S06/S06-PLAN.md` — added a diagnostic verification step and marked T01 complete.
- `.gsd/DECISIONS.md` — recorded the masked-artifacts + reseeding-bootstrap contract for S06 proof fixtures.
