---
id: S05
parent: M003
milestone: M003
provides:
  - Published a replayable red closeout that proves the structural gate stayed green, canonical session-first auth still works on the assembled stack, and legacy `/session/logout` is the remaining blocker preventing M003 closure.
requires:
  - slice: S04
    provides: Green structural closeout proof, the cleanup manifest, and the retained-compatibility-island boundary that S05 had to replay on the assembled runtime.
affects:
  - M003
  - frontend-hormonia
  - backend-hormonia
key_files:
  - .gsd/milestones/M003/slices/S05/S05-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/S05-UAT.md
  - .gsd/milestones/M003/slices/S05/tasks/T03-SUMMARY.md
  - .gsd/DECISIONS.md
  - .gsd/STATE.md
key_decisions:
  - Mark S05 complete once the closeout artifacts are published, but do not validate R037, R038, or R039 while the retained legacy `/session/logout` route still returns `422` and the `/admin` / `/dashboard` / `/whatsapp` browser smoke remains unproven.
  - Treat the current `/session/logout` failure as transport-shape drift on the retained compatibility island until a fix or a deeper contradiction is proven; the captured live response shows FastAPI is requiring `query.token`, not honoring the intended `X-CSRF-Token` header contract.
patterns_established:
  - Close the final slice on the first actionable retained-compatibility red signal and publish the exact response body before widening into later browser smoke.
  - Keep milestone and requirement validation red when runtime proof is partial, but still mark the slice complete once the closeout artifacts publish the blocker truthfully.
observability_surfaces:
  - .gsd/milestones/M003/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/S05-UAT.md
  - /tmp/gsd-s05-runtime-proof.json
  - /tmp/gsd-s05-t02-proof.env
  - bg_shell labels `s05-backend-no-firebase` and `s05-frontend-no-firebase`
  - http://localhost:8000/health/ready
  - http://localhost:8000/api/v2/system/config
drill_down_paths:
  - .gsd/milestones/M003/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T03-SUMMARY.md
duration: 45m across 3 tasks
verification_result: partial
completed_at: 2026-03-13T14:15:57-03:00
---

# S05: Integrated Proof And Structural Closeout

**S05 closed the planned cleanup slice honestly instead of ceremonially: the structural gate stayed green, canonical session-first auth and Bearer compatibility still work on the assembled local stack, and the remaining blocker is the retained legacy `/session/logout` route plus the browser smoke that was intentionally not claimed green afterward.**

## What Happened

T01 re-ran the S04 proof pack and the S01 evidence-map verifier on the current branch. The focused frontend suites, focused backend auth/session pack, typecheck/build, and both evidence-map modes all stayed green. That gave S05 a clean structural baseline before any runtime claims.

T02 started the assembled no-Firebase local stack, refreshed a replay-safe local admin proof user, and re-proved the retained compatibility islands directly against the live backend. Canonical `POST /api/v2/auth/login` succeeded, cookie-backed `GET /api/v2/auth/verify-session` succeeded, `Authorization: Bearer <session_id>` stayed accepted on `GET /api/v2/auth/verify-session` and `GET /api/v2/users/me`, and invalid `GET /session/validate` still returned `200` with `valid:false`.

The slice turned red at legacy logout. A live session created by canonical login was sent through `DELETE /session/logout` and returned `422` with `Input validation failed`. T03 replayed that request carefully and captured the exact validation body: FastAPI reported a missing `query.token` field even when the request carried the CSRF cookie, `X-CSRF-Token`, and `X-Session-ID`. A follow-up `GET /session/validate` on the same live session still returned `200` with `valid:false`, so the retained `/session/logout` island currently has response-contract drift and side-effect ambiguity on the assembled stack.

Because that retained compatibility island is explicitly in scope for R037 and R039, S05 did not force the rest of the closeout green. The seeded-user Playwright run and the browser-tool smoke for `/admin`, `/dashboard`, and `/whatsapp` were left unclaimed after the blocker was isolated. T03 turned that state into durable closeout artifacts, appended the acceptance strategy to `.gsd/DECISIONS.md`, and updated project/state tracking. Manual merge recovery then marked `S05` complete in `.gsd/milestones/M003/M003-ROADMAP.md` while intentionally keeping `R037` / `R038` / `R039` active in `.gsd/REQUIREMENTS.md` and leaving M003 itself open.

## Verification

Green proof recorded across the slice:
- `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `http://localhost:8000/health/ready`
- `http://localhost:8000/api/v2/system/config`
- assembled compat probes captured in `/tmp/gsd-s05-runtime-proof.json`:
  - `POST /api/v2/auth/login` → `200`
  - cookie-backed `GET /api/v2/auth/verify-session` → `200`
  - `Authorization: Bearer <session_id>` on `GET /api/v2/auth/verify-session` → `200`
  - `Authorization: Bearer <session_id>` on `GET /api/v2/users/me` → `200`
  - invalid `GET /session/validate` → `200` with `valid:false`

Red / incomplete proof recorded in the closeout:
- live `DELETE /session/logout` → `422` with validation error on `query.token`
- follow-up `GET /session/validate` on that same live session → `200` with `valid:false`
- `cd frontend-hormonia && npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts --project=chromium` was not claimed green in the final closeout
- browser/runtime smoke for `/admin`, `/dashboard`, and `/whatsapp` was not claimed green in the final closeout

## Requirements Advanced

- R037 — S05 re-proved that the structural cleanup did not break canonical session-first login, canonical auth/session verification, invalid legacy `session/validate`, or Bearer session fallback, and isolated the remaining visible-contract drift to legacy `/session/logout` plus the uncompleted `/admin` / `/dashboard` / `/whatsapp` smoke.
- R038 — the milestone now has a replayable handoff that ties each passing and failing surface to concrete commands, local-stack entrypoints, retained compatibility islands, and an explicit next action instead of forcing a misleading “done” state.
- R039 — the slice ended on executable proof and an exact live `422` body rather than on structural diffs or assumed browser continuity.

## Requirements Validated

- none — `R037`, `R038`, and `R039` remain active because legacy `/session/logout` is still red and the routed `/admin`, `/dashboard`, and `/whatsapp` browser smoke was not rerun after that blocker.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The planned Playwright/browser phases were not completed after the retained compatibility proof turned red. Instead of widening into more smoke with an unresolved compat blocker in front of it, T03 captured the exact live `/session/logout` validation body and published the slice as partial/red.

## Known Limitations

- Legacy `DELETE /session/logout` is not cleanly proven on the assembled local stack. The current live response is `422` with missing `query.token`, even when the request carries CSRF cookie + `X-CSRF-Token` + `X-Session-ID`.
- Follow-up `GET /session/validate` on that same live session returns `200` with `valid:false`, so the legacy logout island currently has mismatched response/side-effect behavior.
- Browser/runtime smoke for `/admin`, `/dashboard`, and `/whatsapp` is still pending in the closeout artifact.
- The seeded-user Chromium Playwright acceptance is still pending in the closeout artifact.
- `.gsd/REQUIREMENTS.md` intentionally keeps `R037`, `R038`, and `R039` active, and M003 remains open, even though `.gsd/milestones/M003/M003-ROADMAP.md` now marks `S05` complete as a truthful red handoff.

## Follow-ups

- Rebind or fix the legacy `/session/logout` CSRF contract so the retained compatibility route accepts the intended request shape and returns a clean success response.
- Re-run the direct compat proof after that fix: canonical login, cookie verify, Bearer verify/users-me, invalid `session/validate`, and live `session/logout`.
- Only after the compat proof is green, run the pending Playwright spec and browser assertions for `/admin`, `/dashboard`, and `/whatsapp`.
- Move `R037`, `R038`, and `R039` to validated only after the full proof pack is green.

## Files Created/Modified

- `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md` — compressed the slice into a replayable closeout tied to the exact green proof and the remaining red blocker.
- `.gsd/milestones/M003/slices/S05/S05-UAT.md` — rewrote the UAT around the real assembled-stack entrypoints, direct compat checks, exact `/session/logout` response body, and the explicit browser/Playwright skip state.
- `.gsd/milestones/M003/slices/S05/tasks/T03-SUMMARY.md` — recorded the task-level closeout publication, state decisions, and verification.
- `.gsd/milestones/M003/M003-ROADMAP.md` — now marks `S05` complete while leaving milestone closure to the follow-up proof.
- `.gsd/PROJECT.md` — refreshed current state so the repo no longer points at “run S05 next”.
- `.gsd/DECISIONS.md` — appended the final S05 acceptance strategy, the current legacy logout diagnosis, and the slice-complete/milestone-open rule.
- `.gsd/STATE.md` — marked the slice as blocked on the retained legacy logout route and set the next action.
- `.gsd/milestones/M003/slices/S05/S05-PLAN.md` — marked T03 complete.

## Forward Intelligence

### What the next slice should know
- The current S05 blocker is narrower than it first looked: canonical `/api/v2/auth/*` login/verify plus Bearer fallback are green on the assembled stack; the remaining red is concentrated in legacy `/session/logout` and the browser smoke that should only resume after that route is explained or fixed.

### What's fragile
- The retained legacy auth/session island around `/session/validate` and `/session/logout` — it coexists beside the canonical `/api/v2/auth/*` path, so it is easy to assume logout is covered because session invalidation side effects still happen even while the response contract is wrong.

### Authoritative diagnostics
- `.gsd/milestones/M003/slices/S05/S05-UAT.md` plus the live probe shape recorded there — it contains the exact `/session/logout` `422` body, the follow-up `session/validate` result, and the exact local-stack commands used for replay.
- `backend-hormonia/app/routers/auth_session.py` and `backend-hormonia/app/middleware/csrf.py` — together they show why the route still declares `Depends(validate_csrf_token)` while the validation helper signature makes FastAPI look for `query.token` instead of the intended `X-CSRF-Token` request header.

### What assumptions changed
- We assumed the remaining S05 red signal was a generic legacy logout failure that still needed reproduction — the replay showed a more specific transport/dependency mismatch: the route returns `422` for missing `query.token` while the same session is already invalid by the next `session/validate` call.
