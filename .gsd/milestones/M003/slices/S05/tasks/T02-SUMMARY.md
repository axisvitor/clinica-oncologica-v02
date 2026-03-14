---
id: T02
parent: S05
milestone: M003
provides:
  - Started the no-Firebase local stack, refreshed a replay-safe local admin proof user, re-proved bearer/validate compat behavior on the assembled backend, and isolated the live `/session/logout` red signal before browser smoke resumed.
key_files:
  - .gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/S05-UAT.md
  - .gsd/milestones/M003/slices/S05/S05-PLAN.md
  - .gsd/STATE.md
key_decisions:
  - Reused login-created live sessions for compat proof and kept seeded credentials/reset token only in masked `/tmp` replay artifacts instead of persisting them in repo files.
patterns_established:
  - When local helper scripts must touch backend models, run them under `backend-hormonia/.venv` with the same WuzAPI mock env as the assembled server to avoid interpreter/settings drift.
observability_surfaces:
  - bg_shell labels `s05-backend-no-firebase` and `s05-frontend-no-firebase`
  - http://localhost:8000/health/ready
  - http://localhost:8000/api/v2/system/config
  - /tmp/gsd-s05-runtime-proof.json
  - /tmp/gsd-s05-t02-proof.env
  - /tmp/gsd-s05-browser-bootstrap
duration: 25m
verification_result: partial
completed_at: 2026-03-13T14:03:37-03:00
blocker_discovered: false
---

# T02: Prove assembled runtime continuity on the local stack

**Started the no-Firebase local stack, seeded a replay-safe admin proof user, re-proved live bearer/validate behavior, and isolated a `/session/logout` blocker before the browser smoke completed.**

## What Happened

I started the backend and frontend with the M002 no-Firebase recipe, keeping mocked WuzAPI enabled and the frontend on Vite dev server port `5173`. Both processes came up cleanly enough to continue: the backend readiness surface reported `database`, `redis`, and `session_auth` without any `firebase` dependency, and `/api/v2/system/config` stayed free of Firebase config keys.

I reran the T02 backend verification command on this branch and it stayed green. After that I prepared the seeded proof-user contract locally instead of asking for manual setup: I used the backend virtualenv under the same runtime env contract as the server, refreshed a local **admin** proof user, generated a fresh reset token, and wrote only masked replay material to `/tmp/gsd-s05-t02-proof.env`.

From that seeded contract I exercised the retained compatibility islands directly against the assembled backend. Canonical login succeeded, cookie-backed `verify-session` succeeded, bearer `Authorization: Bearer <session_id>` was accepted on both `/api/v2/auth/verify-session` and `/api/v2/users/me`, and invalid `/session/validate` still returned `200` with `valid:false`.

The red signal in this unit was live legacy logout. A login-created session sent through `DELETE /session/logout` came back `422` with `Input validation failed`. A follow-up `/session/validate` against that same session returned `200` with `valid:false`, so the retained island is not cleanly proven yet and needs one focused follow-up pass to determine whether this is transport-shape drift or an actual response-contract bug.

Recovery interrupted the unit after that compat proof, before I could finish the seeded-user Chromium Playwright run and the browser-tool smoke for `/admin`, `/dashboard`, and `/whatsapp`. I froze the current evidence into `S05-UAT.md` instead of widening into ad-hoc debugging without durable output.

Must-have status at the end of this unit:
- **Retained compatibility islands:** partially addressed — bearer fallback and invalid `/session/validate` are green; live `/session/logout` is red/actionable.
- **Current session-first routes on the assembled local stack:** not yet fully addressed in-browser — browser/Playwright proof is still pending.

## Verification

Passed in this unit:

- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py tests/integration/test_auth_hard_cut_end_to_end.py`
  - Result: **PASS**
  - Note: existing `pytest_asyncio` deprecation warning remained unchanged.
- `http://localhost:8000/health/ready`
  - Observed: `status=ready`; dependencies included `database`, `redis`, `session_auth`; no `firebase` dependency present.
- `http://localhost:8000/api/v2/system/config`
  - Observed: returned current public config keys without Firebase config residue.
- Assembled backend compat probes captured in `/tmp/gsd-s05-runtime-proof.json`
  - `POST /api/v2/auth/login` → `200`
  - cookie-backed `GET /api/v2/auth/verify-session` → `200`
  - bearer `GET /api/v2/auth/verify-session` → `200`
  - bearer `GET /api/v2/users/me` → `200`
  - invalid `GET /session/validate` → `200` with `valid:false`

Red / not yet complete:

- live `DELETE /session/logout` against a login-created session → `422` (`Input validation failed`)
- seeded-user Chromium Playwright acceptance was **not run in this unit’s durable snapshot**
- browser-tool assertions for `/admin`, `/dashboard`, and `/whatsapp` were **not run in this unit’s durable snapshot**

## Diagnostics

Use these surfaces to resume without reopening discovery:

- Background processes:
  - `s05-backend-no-firebase`
  - `s05-frontend-no-firebase`
- Runtime truth:
  - `http://localhost:8000/health/ready`
  - `http://localhost:8000/api/v2/system/config`
- Masked replay artifacts (local only, not repo state):
  - `/tmp/gsd-s05-t02-proof.env` — seeded-user env contract for replay
  - `/tmp/gsd-s05-runtime-proof.json` — sanitized compat HTTP results
  - `/tmp/gsd-s05-browser-bootstrap` — helper to resume browser auth bootstrap without printing credentials
- Slice artifact:
  - `.gsd/milestones/M003/slices/S05/S05-UAT.md`

Most useful next diagnostic step: reproduce the live `DELETE /session/logout` `422` and capture the exact response body/validation details before changing code or running the remaining browser smoke.

## Deviations

Did not reach the planned Playwright/browser-tool phases in this unit because recovery was triggered after the direct compat pass surfaced the `/session/logout` red signal.

## Known Issues

- Live legacy `/session/logout` is not cleanly proven on the assembled backend: current direct replay returns `422` with `Input validation failed` instead of a clean logout response.
- The follow-up `/session/validate` on that same session returned `200` with `valid:false`, so state transition and response contract are currently out of sync or at least not yet explained.
- `/admin`, `/dashboard`, and `/whatsapp` browser/runtime smoke is still pending.

## Files Created/Modified

- `.gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md` — recorded the partial T02 runtime proof, the masked replay surfaces, and the live `/session/logout` blocker.
- `.gsd/milestones/M003/slices/S05/S05-UAT.md` — captured the assembled-stack verification snapshot, passed compat evidence, pending browser smoke, and resume notes.
- `.gsd/milestones/M003/slices/S05/S05-PLAN.md` — marked T02 complete for this unit’s durable handoff.
- `.gsd/STATE.md` — moved the state forward from the stale timed-out next action and exposed the remaining T02 blocker explicitly.
