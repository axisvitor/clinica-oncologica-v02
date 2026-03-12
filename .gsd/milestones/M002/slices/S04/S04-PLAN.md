# S04: Hard Cut Cleanup And Integrated Proof

**Goal:** Remove the remaining Firebase Auth runtime and compatibility seams from staff authentication, then prove the assembled first-party auth system works end to end with inspectable failure signals.
**Demo:** On a local stack started without `VITE_FIREBASE_*` browser auth config and without `FIREBASE_ADMIN_*` staff-auth credentials, a seeded staff user can log in at `/login`, refresh to restore the session, reach protected dashboard/API and websocket surfaces, complete reset-request/reset-confirm and in-app password change, then logout/logout-all — while runtime health/config surfaces and proof artifacts show session-first auth as the only shipped staff-auth path.

## Requirement Coverage

- Owned by this slice: **R011** Firebase Auth dependency is hard-cut from runtime and compatibility paths; **R012** authentication failures become inspectable instead of opaque.
- Supported by this slice: **R005** first-party staff login, **R006** Redis + HttpOnly session continuity, **R007** existing-user recovery, **R009** password reset via email, **R010** frontend/realtime auth without Firebase tokens.

## Must-Haves

- Frontend shipped runtime no longer imports, configures, aliases, or depends on Firebase Auth for staff auth: the Firebase browser modules/dependency are removed, `createSession(firebaseToken, ...)` is gone, `getFirebaseToken()` is renamed or removed in favor of session-first nomenclature, and missing `VITE_FIREBASE_*` values do not appear as a staff-auth requirement.  
  _Covers: R011, R010_
- Backend boot/readiness/validation/system-config surfaces stop treating Firebase Admin/browser auth config as a required staff-auth dependency; public config no longer emits `VITE_FIREBASE_*`, and auth initialization logs describe Firebase as optional/out-of-scope for the staff-auth happy path instead of claiming auth is broken.  
  _Covers: R011, R012_
- Remaining staff-auth compatibility seams are removed or explicit tombstones: `/api/v2/auth/firebase/verify`, its middleware exemptions, Firebase-only debug token inspection, and websocket `auth_type="firebase"` / `auto` fallback do not remain part of the shipped staff-auth runtime.  
  _Covers: R011_
- `/api/v2/auth/password` and the settings security UI use first-party current-password verification, shared password-strength rules, local hash update, and session revocation keyed to canonical `user_id` rather than Firebase Admin SDK semantics.  
  _Covers: R005, R006, R011_
- Final proof covers login → session restore → protected access → reset-request/reset-confirm → password change → logout/logout-all, and it runs against a stack where Firebase staff-auth config is absent.  
  _Covers: R005, R006, R007, R009, R010, R011_
- Auth and operational failures remain inspectable through stable error codes/messages, `request_id`/phase diagnostics, readiness component status, and replayable proof artifacts without logging passwords, reset tokens, session cookies, or secret config values.  
  _Covers: R012_
- Legacy Firebase-auth-only docs/tests are deleted or explicit tombstones so the repository no longer instructs operators or future agents to configure Firebase Auth for staff login.  
  _Covers: R011, R012_

## Proof Level

- This slice proves: final-assembly
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx` — frontend hard-cut proof for session-first auth client/context naming, password-change wiring, and absence of Firebase-auth bridges.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` — backend auth cleanup proof for first-party password change, logout-all/user-id session revocation, and removed/tombstoned Firebase verify/debug seams.
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py` — backend operational proof that readiness, health, initialization, validation, and public config stay truthful with Firebase auth config absent.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — integrated backend proof for login → verify-session → protected access → reset-confirm/password rotation → logout without Firebase auth credentials.
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` — real browser acceptance against the local frontend/backend stack started without `VITE_FIREBASE_*` or `FIREBASE_ADMIN_*` auth config.
- `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh` — static artifact guard scoped to staff-auth runtime/docs/test hotspots; fails on leftover Firebase auth imports/routes/env guidance while ignoring out-of-scope historical `firebase_uid` data-model residue.
- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx tests/integration/auth/hard-cut-cleanup-proof.test.tsx`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_password_reset_migration_flow.py tests/integration/test_auth_hard_cut_end_to_end.py -q`
- `cd frontend-hormonia && npm run build`
- Start backend/frontend without Firebase staff-auth env vars, then run `cd frontend-hormonia && npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts`

## Observability / Diagnostics

- Runtime signals: auth endpoints and browser auth flows keep stable `error` / `request_id` / phase markers (`login`, `restore`, `reset-request`, `reset-confirm`, `password-change`, `logout-all`, `websocket-auth`) while system surfaces report session-auth readiness instead of Firebase-required status.
- Inspection surfaces: `/api/v2/auth/verify-session`, `/api/v2/health/ready`, `/api/v2/system/health`, `/api/v2/system/validate`, `/api/v2/system/config`, settings/security UI error states, websocket auth error payloads, Playwright traces, pytest/vitest output, and `verify-no-firebase-auth.sh`.
- Failure visibility: invalid current password, expired/invalid reset token, revoked session, missing optional Redis/session dependencies, and stale Firebase staff-auth artifacts become explicit with component names or stable codes instead of silent logout, ambiguous readiness failure, or ghost compatibility calls.
- Redaction constraints: never log or persist plaintext passwords, reset tokens, raw session cookies/IDs beyond existing safe diagnostics, or Firebase/private credential material.

## Integration Closure

- Upstream surfaces consumed: S01 local login/session/logout contracts and canonical user-id session identity; S02 reset-request/reset-confirm/password-migration flow; S03 AuthContext/session-first browser flow, websocket session auth, and initialization/service-monitoring cutover surfaces.
- New wiring introduced in this slice: settings security UI → first-party password-change endpoint; backend readiness/validation/config routes → session-auth-only diagnostics; static guard script + local-stack Playwright acceptance → repeatable no-Firebase hard-cut proof.
- What remains before the milestone is truly usable end-to-end: nothing for the M002 staff-auth cutover once this slice ships; broader historical `firebase_uid` model cleanup and out-of-scope patient/quiz auth work remain deferred.

## Tasks

- [x] **T01: Add failing hard-cut proof suites and Firebase-residue guard** `est:1h10m`
  - Why: Lock the slice stopping condition before cleanup so S04 cannot claim success while Firebase staff-auth seams, dishonest readiness signals, or untested password-change gaps still exist.
  - Files: `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx`, `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`, `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`, `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`, `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`, `.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
  - Do: Create focused failing proofs for session-first-only frontend auth APIs/context naming, first-party password change and logout-all session revocation, truthful system readiness/config without Firebase auth creds, backend integrated login→restore→protected→reset→logout flow, and local browser acceptance on a no-Firebase-auth stack; add a static guard script that scans only staff-auth runtime/docs/test hotspots so it catches stale Firebase imports/routes/env guidance without flagging out-of-scope historical compatibility fields.
  - Verify: `cd frontend-hormonia && npx vitest run tests/integration/auth/hard-cut-cleanup-proof.test.tsx && cd ../backend-hormonia && pytest tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_auth_hard_cut_end_to_end.py -q && cd ../frontend-hormonia && npx playwright test --list tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts && cd .. && bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
  - Done when: the new proof artifacts exist, express the slice must-haves directly, and fail only on real cleanup gaps rather than missing harness/setup.
- [x] **T02: Remove frontend Firebase runtime, compat naming, and package/env residue** `est:1h20m`
  - Why: The shipped browser path is still dishonest until Firebase SDK imports, compatibility helpers, dependency entries, and legacy env/test knobs are gone from the staff-auth runtime.
  - Files: `frontend-hormonia/src/lib/api-client/auth.ts`, `frontend-hormonia/src/app/providers/AuthContext.tsx`, `frontend-hormonia/src/lib/runtime-config.ts`, `frontend-hormonia/src/lib/config-initializer.tsx`, `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx`, `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx`, `frontend-hormonia/vite.config.ts`, `frontend-hormonia/package.json`
  - Do: Delete the Firebase browser modules/services/unused hooks and update imports so no staff-auth code reaches `firebase/*`; remove `createSession(firebaseToken, ...)`, replace `getFirebaseToken()` with session-first naming or drop it entirely, strip `VITE_FIREBASE_*` handling from runtime config/test setup/env guidance/Vite aliases, remove the `firebase` dependency, and keep initialization/service-monitoring/config logs focused on session/websocket readiness instead of legacy Firebase state.
  - Verify: `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/hard-cut-cleanup-proof.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx && npm run build && cd .. && bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
  - Done when: frontend auth/runtime/build surfaces no longer require or advertise Firebase Auth, the `firebase` package can be removed cleanly, and the focused proof remains green.
- [x] **T03: Make backend readiness, health, and public config honest without Firebase Auth** `est:1h20m`
  - Why: The hard cut is not credible if backend startup, system health, or public config still report Firebase Admin/browser auth config as a required component for staff authentication.
  - Files: `backend-hormonia/app/routers/health.py`, `backend-hormonia/app/api/v2/routers/system/health.py`, `backend-hormonia/app/api/v2/routers/system/helpers/health_checker.py`, `backend-hormonia/app/api/v2/routers/system/validation.py`, `backend-hormonia/app/api/v2/routers/system/initialization.py`, `backend-hormonia/app/api/v2/routers/system/config.py`, `backend-hormonia/app/api/v2/routers/system/helpers/config_builder.py`, `backend-hormonia/app/dependencies/auth_dependencies.py`
  - Do: Reframe readiness/startup/system-health/validation/init around database, Redis, CSRF/session, and websocket/session-auth concerns; make Firebase auth clearly optional or out-of-scope for the staff-auth happy path; stop publishing `VITE_FIREBASE_*` from the public config surface and align dependency-initialization logging so missing Firebase creds no longer claim that authentication “will not work.”
  - Verify: `cd backend-hormonia && pytest tests/api/v2/test_system_auth_hard_cut_operational.py tests/api/v2/test_health.py tests/api/v2/test_auth_local_login.py -q`
  - Done when: backend operational endpoints stay truthful and inspectable without Firebase auth config, and no public config payload exposes Firebase-auth runtime knobs.
- [x] **T04: Replace remaining Firebase-only auth seams with first-party password and session behavior** `est:1h30m`
  - Why: Login/reset proof is incomplete while in-app password management, logout-all cache invalidation, websocket auth modes, and compatibility routes still depend on Firebase semantics.
  - Files: `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/services/auth.py`, `backend-hormonia/app/middleware/csrf.py`, `backend-hormonia/app/middleware/config.py`, `backend-hormonia/app/api/v2/routers/debug/auth.py`, `backend-hormonia/app/services/websocket/connection_manager.py`, `frontend-hormonia/src/hooks/useSettings.ts`, `frontend-hormonia/src/features/settings/sections/SecuritySettings.tsx`
  - Do: Replace `/api/v2/auth/password` with first-party current-password validation, shared password-strength enforcement, local hash update, metadata stamping, and session revocation keyed to canonical `user_id`; make logout-all use the canonical session identity contract instead of `firebase_uid`; remove/tombstone `/api/v2/auth/firebase/verify`, its middleware exemptions, and Firebase debug inspection; tighten websocket auth modes to the S03 session-first contract; and wire the settings security UI to the new backend behavior with stable user-safe diagnostics.
  - Verify: `cd backend-hormonia && pytest tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_password_recovery.py -q && cd ../frontend-hormonia && npx vitest run tests/integration/auth/hard-cut-cleanup-proof.test.tsx tests/unit/hooks/useSettings.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
  - Done when: no shipped staff-auth route or settings flow requires Firebase Auth/Admin SDK semantics, and password/session failures remain inspectable through stable backend/frontend diagnostics.
- [x] **T05: Tombstone legacy Firebase guidance and run local-stack final acceptance** `est:1h20m`
  - Why: S04 is only complete when the repository stops teaching Firebase Auth for staff login and the assembled no-Firebase-auth stack is proven through the real browser entrypoint.
  - Files: `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`, `frontend-hormonia/tests/e2e/README.md`, `frontend-hormonia/tests/e2e/SETUP_INSTRUCTIONS.md`, `frontend-hormonia/tests/auth/firebase-auth-comprehensive.test.tsx`, `docs/frontend/guides/api/API_GUIDE.md`, `docs/frontend/guides/configuration/ENVIRONMENT_GUIDE.md`, `docs/frontend/guides/deployment/DEPLOYMENT_GUIDE.md`, `.gsd/milestones/M002/slices/S04/S04-PROOF.md`
  - Do: Delete or explicit-tombstone Firebase-auth-only docs/tests so they point to the session-first proof instead of ghost Firebase setup, finish the new Playwright/local-stack acceptance harness, run the full S04 gate plus the static residue guard against backend/frontend started without Firebase staff-auth env vars, and record the rerunnable proof bundle/results in `S04-PROOF.md` for future agents.
  - Verify: `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh && cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx tests/integration/auth/hard-cut-cleanup-proof.test.tsx && npm run build && cd ../backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_password_reset_migration_flow.py tests/integration/test_auth_hard_cut_end_to_end.py -q && cd ../frontend-hormonia && npx playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts`
  - Done when: the repo no longer advertises Firebase Auth as a staff-auth requirement, the full no-Firebase-auth proof gate passes, and rerun instructions/results are captured in slice artifacts.

## Files Likely Touched

- `frontend-hormonia/src/lib/api-client/auth.ts`
- `frontend-hormonia/src/app/providers/AuthContext.tsx`
- `frontend-hormonia/src/lib/runtime-config.ts`
- `frontend-hormonia/src/lib/config-initializer.tsx`
- `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx`
- `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx`
- `frontend-hormonia/src/hooks/useSettings.ts`
- `frontend-hormonia/src/features/settings/sections/SecuritySettings.tsx`
- `frontend-hormonia/vite.config.ts`
- `frontend-hormonia/package.json`
- `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx`
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`
- `frontend-hormonia/tests/auth/firebase-auth-comprehensive.test.tsx`
- `backend-hormonia/app/routers/health.py`
- `backend-hormonia/app/api/v2/routers/system/health.py`
- `backend-hormonia/app/api/v2/routers/system/helpers/health_checker.py`
- `backend-hormonia/app/api/v2/routers/system/validation.py`
- `backend-hormonia/app/api/v2/routers/system/initialization.py`
- `backend-hormonia/app/api/v2/routers/system/config.py`
- `backend-hormonia/app/api/v2/routers/system/helpers/config_builder.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/services/auth.py`
- `backend-hormonia/app/services/websocket/connection_manager.py`
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
- `.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
- `.gsd/milestones/M002/slices/S04/S04-PROOF.md`
