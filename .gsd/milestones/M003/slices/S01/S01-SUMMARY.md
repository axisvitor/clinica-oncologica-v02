---
id: S01
parent: M003
milestone: M003
provides:
  - A green evidence-map verifier plus a fixed backend/frontend handoff for cleanup order, contract guardrails, and proof-before-deletion work.
requires: []
affects:
  - S02
  - S03
  - S04
  - S05
key_files:
  - .gsd/milestones/M003/slices/S01/verify-evidence-map.sh
  - .gsd/milestones/M003/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M003/slices/S01/S01-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/S01-UAT.md
key_decisions:
  - S02 preserves backend mapping-style session dicts, User adapters, and request.state side effects before any auth cleanup.
  - S03 keeps `@/lib/api-client` and `@/types/api` stable while moving ownership inside `src/lib/api-client/index.ts` and `src/lib/api-client/types.ts`.
patterns_established:
  - Run `verify-evidence-map.sh --report <scope>` before trusting slice prose.
  - Treat alias cleanup as exact-import grep plus targeted tests plus type/build proof, not count-only suspicion.
observability_surfaces:
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report <backend|frontend|all>
drill_down_paths:
  - .gsd/milestones/M003/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T03-SUMMARY.md
duration: 3 tasks on 2026-03-12
verification_result: passed
completed_at: 2026-03-12
---

# S01: Evidence Map And Cleanup Guardrails

**Shipped a green evidence verifier and a fixed backend/frontend cleanup handoff that ranks hotspots, preserves visible contracts, and queues deletion proof instead of guesswork.**

## What Happened

T01 turned the slice into an executable contract: `verify-evidence-map.sh` re-derives hotspot counts, caller/import blast radius, candidate-reference counts, and handoff completeness from the live repo. T02 locked the backend side around the real auth/session seams: mapping-style session dict callers, `User` adapters, request-state side effects, wrapper drift, and compatibility residues that still have to survive S02.

T03 closed the frontend side and the handoff pack. The research now separates the stable public façades from the modules that actually own implementation and transport types: `@/lib/api-client` is the hot public client seam, `src/lib/api-client/index.ts` and `src/lib/api-client/types.ts` are the internal ownership modules, `@/types/api` is the app-facing/UI façade, and `src/lib/types/api.ts` plus `src/lib/api.ts` are legacy aliases that stay blocked on proof. The candidate ledger now names exact grep/test/typecheck/build commands for frontend aliases and duplicate transport declarations, and the slice summary/UAT now carry the ranked attack order plus the exact command pack S02–S05 inherit.

## Verification

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` — passed after the frontend handoff sections were completed and the open scaffold items were removed.
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` — passed and reported the expected backend/frontend hotspot metrics plus `handoff.summary.open_scaffold_items=0` and `handoff.uat.open_scaffold_items=0`.
- Repo scans used to finalize the frontend contract confirmed the live blast radius and residue state: `@/lib/api-client` has 104 internal imports, `@/lib/api-client/types` has 34, `@/types/api` has 50, `@/lib/types/api` still has one app caller (`src/hooks/usePatients.ts`), `src/lib/api.ts` has no exact repo-local imports, `src/hooks/use-quiz-session.ts` has no repo-local callers beyond itself, and `RiskAssessmentRequest` is duplicated twice inside `src/lib/api-client/types.ts`.
- This slice intentionally proves contract and handoff state, not runtime behavior. The downstream pytest/vitest/Playwright suites listed below were preserved as the execution pack for S02–S05 rather than re-run inside this artifact-only closeout task.

## Requirements Advanced

- R035 — hotspot ranking, non-candidates, and deletion candidates are now enforced by a rerunnable verifier and backed by exact grep/test/typecheck/build proof commands.
- R039 — the slice now hands downstream work one fixed attack order and one fixed command pack instead of requiring fresh repo-wide discovery.

## Requirements Validated

- R035 — `verify-evidence-map.sh --check all` now passes against live repo counts, section headings, explicit non-candidates, and handoff completeness.
- R039 — `verify-evidence-map.sh --report all` plus the completed summary/UAT artifacts make the slice outputs inspectable and rerunnable by a later agent.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

- None.

## Deviations

None.

## Known Limitations

- S01 fixes the boundaries and proof pack, not the runtime cleanup itself. S02–S05 still have to execute the backend split, frontend ownership split, proof-driven deletions, and integrated smoke replay.
- `frontend-hormonia/src/lib/api-client/index.ts` and `frontend-hormonia/src/lib/api-client/types.ts` remain large mixed-responsibility files; the slice only fixed how they may be attacked safely.
- `frontend-hormonia/src/lib/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, `frontend-hormonia/src/hooks/use-quiz-session.ts`, backend Firebase residues, and duplicate transport declarations remain blocked candidates until their proof queues are run.

## Follow-ups

- S02: split backend auth/session in contract order — session dict seam first, `User` adapters second, wrapper cleanup last.
- S03: split frontend client/type ownership behind `@/lib/api-client`, `@/lib/api-client/types`, and `@/types/api`, starting with the hottest internal ownership modules.
- S04: run the deletion proof queue and remove or tombstone only candidates that clear grep plus targeted tests plus type/build proof.
- S05: rerun integrated Playwright smoke after S02–S04 land so cleanup proof includes visible flows, not just focused suites.

## Files Created/Modified

- `./.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — executable verifier for backend/frontend hotspot anchors, candidate counts, and handoff completeness.
- `./.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — finalized hotspot ranking, contract guardrails, explicit non-candidates, and deletion proof ledger.
- `./.gsd/milestones/M003/slices/S01/S01-SUMMARY.md` — completed slice handoff with attack order, contracts, proof queue, and command pack.
- `./.gsd/milestones/M003/slices/S01/S01-UAT.md` — reviewer-oriented artifact/UAT checklist for re-running the slice evidence contract.
- `./.gsd/milestones/M003/slices/S01/tasks/T03-SUMMARY.md` — final task closeout for the frontend/handoff unit.

## Forward Intelligence

### What the next slice should know
- The safe frontend seam is `@/lib/api-client`, not `src/lib/api-client/index.ts` directly. Treat `index.ts` and `types.ts` as the internal ownership modules you are free to split, and treat `@/types/api` as the UI-facing façade that can narrow ownership gradually.
- Backend cleanup order is fixed by caller shape, not file size: mapping-style session dicts, then `User` adapters, then wrapper drift and compatibility residue.
- `src/lib/types/api.ts` still has one app caller plus test coverage, `src/lib/api.ts` is colder but still needs export/build proof, and `src/hooks/use-quiz-session.ts` looks dead only by static repo-local evidence so far.

### What's fragile
- `backend-hormonia/app/routers/auth_session.py` and `backend-hormonia/app/api/v2/routers/roles/dependencies.py` — they still carry `firebase_uid` and thinner compatibility behavior, so early deletion will create hidden auth drift.
- `frontend-hormonia/src/lib/api-client.ts` and `frontend-hormonia/src/types/api.ts` — they are hot façades; import-path churn here multiplies work across the repo instead of reducing it.

### Authoritative diagnostics
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` — first source of truth for hotspot sizes, caller/import blast radius, candidate counts, and whether the handoff artifacts drifted.
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — authoritative contract and deletion-proof ledger once the verifier says the markdown still matches the repo.

### What assumptions changed
- "`src/lib/api-client/index.ts` is the frontend public seam" — false; the real public seam is `src/lib/api-client.ts`, and that distinction is what lets S03 split internals without repo-wide import churn.
- "The ugly frontend aliases are probably just dead" — only partly true; `src/lib/api.ts` is colder than expected, but `src/lib/types/api.ts` still has a live app caller and `use-quiz-session.ts` still needs route/e2e proof before deletion.

## Next Slice Execution Order

1. S02 — split backend auth/session internals while preserving the mapping-style session dict seam, the `User` adapter seam, request-state side effects, and the compatibility behavior still exercised by wrapper modules and `auth_session.py`.
2. S03 — split frontend ownership under the stable façades: keep `@/lib/api-client`, `@/lib/api-client/types`, and `@/types/api` stable while moving code and DTO ownership inside `src/lib/api-client/index.ts` and `src/lib/api-client/types.ts`.
3. S04 — run the deletion proof queue for backend residues, legacy frontend aliases, suspicious quiz-session code, and duplicate transport declarations; delete or tombstone only what clears proof.
4. S05 — replay integrated smoke for login, admin/dashboard, websocket, and WhatsApp-adjacent surfaces after the structural work lands.

## Backend Handoff

- Stable contracts that must survive S02:
  - `get_current_user_from_session()` keeps returning mapping-style session dicts with `permissions`, optional `firebase_uid`, and `request.state.session_id` / `user_id` / `user_role` side effects.
  - `get_current_user_object_from_session()` and `get_current_user()` keep the `User`-object contract and session-first preference.
  - Canonical session writer/reader alignment between `app/api/v2/routers/auth.py` and `app/dependencies/auth_dependencies.py` stays intact.
- Wrapper constraints that must be carried, not hand-waved:
  - `backend-hormonia/app/api/v2/routers/admin/dependencies.py`
  - `backend-hormonia/app/api/v2/routers/reports.py`
  - `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
  - `backend-hormonia/app/api/v2/routers/roles/dependencies.py`
- Explicit backend non-candidates for early deletion:
  - `backend_session_permissions_field`
  - `backend_firebase_uid_compatibility`
  - `backend-hormonia/app/routers/auth_session.py` compatibility behavior until S04 proof says otherwise.

## Frontend Handoff

- Stable public façades:
  - `@/lib/api-client` — 104 internal imports; the only public client entrypoint.
  - `@/lib/api-client/types` — 34 direct imports; transport/shared DTO façade.
  - `@/types/api` — 50 direct imports; app-facing/UI façade.
- Internal ownership modules for S03 to attack safely:
  - `frontend-hormonia/src/lib/api-client/index.ts`
  - `frontend-hormonia/src/lib/api-client/types.ts`
  - `frontend-hormonia/src/lib/ai-adapters.ts` as the model seam when transport and UI types differ.
- Legacy compatibility aliases and residues that stay blocked on proof:
  - `frontend-hormonia/src/lib/types/api.ts` — one remaining app caller in `src/hooks/usePatients.ts` plus validation-test coverage.
  - `frontend-hormonia/src/lib/api.ts` — no exact repo-local imports, but still blocked on type/build/export proof.
  - `frontend-hormonia/src/hooks/use-quiz-session.ts` — self-only repo-local refs so far; still needs route/e2e proof.
  - Duplicate `RiskAssessmentRequest` declarations inside `frontend-hormonia/src/lib/api-client/types.ts`.
- Explicit frontend non-candidates for early deletion:
  - `frontend_api_client_facade`
  - `frontend_types_api_facade`

## Deletion Proof Queue

### Backend candidates

- `verify_firebase_token`
  - `rg -n "verify_firebase_token" backend-hormonia/app backend-hormonia/tests backend-hormonia/docs`
  - `cd backend-hormonia && pytest tests/auth/test_session_validation.py tests/auth/test_user_conversion.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py`
- `get_doctor_user`
  - `rg -n "get_doctor_user" backend-hormonia/app backend-hormonia/tests`
  - `cd backend-hormonia && pytest tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py`
- `get_current_user_websocket`
  - `rg -n "get_current_user_websocket" backend-hormonia/app backend-hormonia/tests`
  - `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py`
  - `cd frontend-hormonia && npm run test -- tests/integration/realtime/session-websocket-cutover.test.ts`
- Legacy Firebase/session compatibility branches
  - `rg -n "firebase_uid|verify_token|get_cached_token|get_cached_user" backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/api/v2/routers/roles/dependencies.py backend-hormonia/app/routers/auth_session.py`
  - `rg -n "validate_session|logout_session|firebase_uid|permissions" backend-hormonia/app/routers/auth_session.py backend-hormonia/app/api/v2/routers/auth.py`

### Frontend candidates

- `frontend-hormonia/src/lib/api.ts`
  - `rg -n "['\"](@/lib/api|\.\./lib/api|\.\./\.\./lib/api|\.\./\.\./\.\./lib/api)['\"]" frontend-hormonia/src frontend-hormonia/tests`
  - `cd frontend-hormonia && npm run typecheck && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
  - `cd frontend-hormonia && npm run build`
- `frontend-hormonia/src/lib/types/api.ts`
  - `rg -n "@/lib/types/api|\.\./lib/types/api|\.\./\.\./src/lib/types/api" frontend-hormonia/src frontend-hormonia/tests`
  - `cd frontend-hormonia && npm run test -- src/hooks/__tests__/usePatients.test.ts tests/hooks/usePatientImport.test.ts`
  - `cd frontend-hormonia && npm run typecheck && npm run build`
- `frontend-hormonia/src/hooks/use-quiz-session.ts`
  - `rg -n "use-quiz-session|useQuizSession" frontend-hormonia/src frontend-hormonia/tests`
  - `cd frontend-hormonia && npm run test -- tests/monthly-quiz/useMonthlyQuiz.spec.tsx tests/unit/pages/QuestionariosPage.test.tsx`
  - `cd frontend-hormonia && npx playwright test tests/e2e/quiz-submission-flow.spec.ts tests/e2e/quiz-complete-flow.spec.ts`
- Duplicate `RiskAssessmentRequest` declarations
  - `rg -n "export (interface|type) RiskAssessmentRequest\\b" frontend-hormonia/src/lib/api-client/types.ts frontend-hormonia/src/types/api.ts`
  - `cd frontend-hormonia && npm run test -- tests/hooks/api/usePhysicianRiskAssessments.test.tsx tests/integration/api-client.test.ts`
  - `cd frontend-hormonia && npm run typecheck`

## Exact Verification Commands

### Backend

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`
- `cd backend-hormonia && pytest tests/auth/test_session_validation.py tests/auth/test_user_conversion.py tests/api/v2/test_auth_session_priority.py`
- `cd backend-hormonia && pytest tests/auth/test_user_conversion.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py`
- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py`
- `cd backend-hormonia && pytest tests/api/v2/test_admin.py tests/api/v2/test_dashboard.py tests/api/test_admin_contracts.py`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py`

### Frontend

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report frontend`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`
- `cd frontend-hormonia && npm run typecheck && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
- `cd frontend-hormonia && npm run test -- tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `cd frontend-hormonia && npm run test -- tests/integration/admin-auth-flow.test.tsx tests/components/dashboard/QuickStats.test.tsx`

### Slice Close

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
- `cd frontend-hormonia && npx playwright test tests/e2e/auth/login.spec.ts tests/e2e/admin-dashboard-complete.spec.ts tests/e2e/websocket.spec.ts tests/e2e/test_whatsapp_integration_e2e.spec.ts`

## Reviewer Focus

1. Confirm the attack order still reads backend contract split first, frontend ownership split second, deletion proof third, integrated smoke last.
2. Confirm the protected surfaces are still explicit: backend mapping/User/request.state contracts and frontend public façades vs internal ownership modules vs legacy aliases.
3. Confirm no candidate is described as dead without an exact grep command plus the targeted tests and type/build proof it still needs.
4. Confirm the command pack in this summary still matches `S01-RESEARCH.md`, `S01-UAT.md`, and `verify-evidence-map.sh`.
