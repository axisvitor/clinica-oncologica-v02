# S05: Integrated Proof And Structural Closeout

**Goal:** Prove the post-S04 structure still holds on the real assembled staff-auth, dashboard, admin, and WhatsApp surfaces, then close M003 with replayable evidence.
**Demo:** On a local no-Firebase stack, the structural gate stays green, current routed staff flows work on `/admin`, `/dashboard`, and `/whatsapp`, retained compatibility islands still behave as documented, and the slice closeout artifacts map that proof back to the requirements this slice owns.

## Must-Haves

- Re-run the S04 structural proof pack and the S01 evidence-map verifier on the current branch so the closeout starts from a green cleanup boundary.
- Prove current routed session-first behavior on a real local stack: `/admin` redirects through shared `/login`, successful login returns to the intended route, `/dashboard` and `/admin` render, and `/whatsapp` reaches its mocked WuzAPI status path.
- Re-prove the retained compatibility islands in scope: invalid `/session/validate` stays `200` with `valid:false`, `/session/logout` revokes a live legacy session, and bearer `Authorization: Bearer <session_id>` still works or is explicitly bounded with evidence.
- Publish slice-close artifacts that connect the structural win to concrete proof and move R037, R038, and R039 out of active status only if the proof is actually green.

## Active Requirement Coverage

- **R037 — Visible contracts remain stable during the cleanup:** prove current auth/dashboard/admin/WhatsApp entrypoints plus the retained `/session/*` and bearer compatibility behavior on the assembled runtime.
- **R038 — The codebase becomes safer to change in practice:** leave a closeout pack that ties the new seams to explicit replay commands, retained-island rationale, and current failure signals.
- **R039 — Structural cleanup leaves strong proof, not just nicer files:** combine the green structural verifier with focused suites and real local-stack smoke instead of ending on static diffs.

## Proof Level

- This slice proves: final-assembly
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx`
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
- `cd frontend-hormonia && npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts --project=chromium` when the seeded-user contract from the M002 proof recipe is available; otherwise record the explicit skip reason in `S05-UAT.md`.
- Browser/runtime proof recorded in `S05-UAT.md`: `/admin` redirects to `/login` and returns to the intended route after login, `/dashboard` completes a successful `/api/v2/dashboard/main` fetch without fatal render error state, `/admin` root renders for the authenticated staff user, `/whatsapp` completes a successful `/api/v2/monitoring/wuzapi/session/status` fetch on mocked WuzAPI, invalid `/session/validate` returns `200` with `valid:false`, `/session/logout` revokes a live legacy session, and bearer `Authorization: Bearer <session_id>` is accepted on the canonical auth/session path.

## Observability / Diagnostics

- Runtime signals: evidence-map verifier output, focused suite output, backend/frontend dev-server readiness logs, browser network requests to `/api/v2/dashboard/main` and `/api/v2/monitoring/wuzapi/session/status`, and direct `/session/*` HTTP responses.
- Inspection surfaces: `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`, `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh`, Playwright output, browser console/network logs, and the S05 task/slice summaries.
- Failure visibility: redirect destination drift, failing request URL/status/body, compat-response status/body mismatches, auth fixture availability for the conditional Playwright run, and any local-stack boot failure isolated to backend/frontend/mock infrastructure.
- Redaction constraints: do not persist session IDs, seeded-user credentials, reset tokens, or mock WuzAPI secrets in logs or slice artifacts.

## Integration Closure

- Upstream surfaces consumed: `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`, `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh`, `.gsd/milestones/M002/slices/S04/S04-PROOF.md`, `frontend-hormonia/src/app/routes/routeDefinitions.tsx`, `frontend-hormonia/src/pages/LoginPage.tsx`, `frontend-hormonia/src/pages/DashboardPage.tsx`, `frontend-hormonia/src/pages/WhatsAppPage.tsx`, `backend-hormonia/app/api/v2/routers/auth.py`, and `backend-hormonia/app/core/router_registry.py`.
- New wiring introduced in this slice: none; S05 assembles and replays the already-refactored backend/frontend/runtime surfaces on the current local stack.
- What remains before the milestone is truly usable end-to-end: nothing if the structural gate, local-stack smoke, and compatibility proofs all pass; otherwise only the blockers recorded by this slice.

## Tasks

- [x] **T01: Re-run the structural closeout gate** `est:45m`
  - Why: The final smoke only means something if the post-S04 cleanup boundary is still green on the current branch.
  - Files: `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`, `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh`, `.gsd/milestones/M003/slices/S05/tasks/T01-SUMMARY.md`
  - Do: Re-run the focused frontend/backend proof commands recorded by S04, then rerun `verify-evidence-map.sh --report all` and `--check all` before any browser work. If any command regresses, isolate whether the drift is cleanup-boundary, focused-contract, or environment noise, and record the exact outcome in the task summary instead of continuing with ambiguous runtime smoke.
  - Verify: `cd frontend-hormonia && npm run test -- tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts tests/unit/types-validation.test.ts tests/monthly-quiz/useMonthlyQuiz.spec.tsx && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts && npm run typecheck && npm run build`; `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py tests/integration/test_auth_hard_cut_end_to_end.py`; `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all && bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
  - Done when: the structural proof pack is green on the current branch and `T01-SUMMARY.md` captures the exact passing commands, anchored counts, and any non-blocking diagnostics.
- [x] **T02: Prove assembled runtime continuity on the local stack** `est:1h30m`
  - Why: R037 and R039 are only closed when the shipped routes and retained compatibility islands still behave correctly on the assembled runtime, not just in focused suites.
  - Files: `.gsd/milestones/M002/slices/S04/S04-PROOF.md`, `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`, `backend-hormonia/tests/auth/test_session_validation.py`, `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`, `.gsd/milestones/M003/slices/S05/S05-UAT.md`, `.gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md`
  - Do: Start the backend and frontend with the M002 no-Firebase recipe, keep the frontend on `npm run dev` at 5173, and enable mocked WuzAPI so `/whatsapp` exercises a meaningful status path. Re-prove the retained `/session/*` behavior and bearer fallback directly, run the canonical Playwright auth acceptance only when the seeded-user contract is available, and use browser-tool assertions plus network logs to smoke `/admin`, `/dashboard`, and `/whatsapp` on the current routed surfaces.
  - Verify: `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py tests/integration/test_auth_hard_cut_end_to_end.py`; `cd frontend-hormonia && npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts --project=chromium` when fixtures are available; browser assertions and network checks recorded in `S05-UAT.md` for `/admin`, `/dashboard`, `/whatsapp`, `/session/validate`, `/session/logout`, and bearer fallback.
  - Done when: `S05-UAT.md` and `T02-SUMMARY.md` record a passing current-route smoke plus retained-compat proof, or a real blocker is isolated with enough logs and request evidence that the failure is actionable.
- [x] **T03: Publish the slice closeout and milestone state** `est:45m`
  - Why: R038 depends on the closeout being replayable by the next maintainer, and the milestone state only moves if the proof is tied back to requirements and current artifacts.
  - Files: `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md`, `.gsd/milestones/M003/slices/S05/S05-UAT.md`, `.gsd/milestones/M003/M003-ROADMAP.md`, `.gsd/REQUIREMENTS.md`, `.gsd/DECISIONS.md`, `.gsd/STATE.md`
  - Do: Compress the T01/T02 evidence into the slice summary and UAT, mark the roadmap and requirements only when the proof is actually green, and update decisions/state so the retained compatibility islands, acceptance route truth, and any remaining fragility are explicit. If the proof stays red, record the blocker honestly instead of forcing milestone closure.
  - Verify: `rg -n 'R037|R038|R039|/admin|/dashboard|/whatsapp|session/validate|Bearer' .gsd/milestones/M003/slices/S05/S05-SUMMARY.md .gsd/milestones/M003/slices/S05/S05-UAT.md .gsd/REQUIREMENTS.md`; `rg -n 'S05: Integrated Proof And Structural Closeout' .gsd/milestones/M003/M003-ROADMAP.md && rg -n 'Active Slice|Phase|Next Action' .gsd/STATE.md`
  - Done when: the slice artifacts and state files make it obvious whether M003 closed green, what exactly proved it, and which blocker prevented closure if it did not.

## Files Likely Touched

- `.gsd/milestones/M003/slices/S05/S05-PLAN.md`
- `.gsd/milestones/M003/slices/S05/tasks/T01-PLAN.md`
- `.gsd/milestones/M003/slices/S05/tasks/T02-PLAN.md`
- `.gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md`
- `.gsd/DECISIONS.md`
- `.gsd/STATE.md`
