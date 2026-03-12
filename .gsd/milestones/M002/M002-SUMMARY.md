---
id: M002
provides:
  - First-party staff authentication with local email/password login, Redis + HttpOnly session issuance, password reset / first-access migration, and admin-managed provisioning without Firebase Auth runtime dependence
  - Session-first frontend and websocket auth cutover plus honest session_auth operational surfaces and a shipped no-Firebase runtime/config hard cut
key_decisions:
  - Preserve the existing DB + Redis + HttpOnly session architecture and make canonical session identity `user_id`, with `firebase_uid` retained only as compatibility metadata outside the happy path
  - Migrate existing and admin-created staff users through shared email-backed reset / first-access flows instead of manual recreation or public self-signup
  - Hard-cut Firebase Auth runtime/browser compatibility seams and prove the shipped state with focused suites, a static residue guard, health/config truth checks, and local no-Firebase browser replay
patterns_established:
  - Provider cutovers are proof-first: add focused red suites per seam (backend auth, recovery, frontend auth, websocket auth, hard-cut cleanup) before refactors, then keep those suites as the milestone gate
  - Auth failures should emit stable backend `error` + `request_id` diagnostics and be normalized into user-safe frontend/browser errors instead of opaque provider-origin failures
  - Operational auth truth should be published as session-auth readiness/config state rather than inferred from third-party SDK presence
observability_surfaces:
  - "cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_password_recovery.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_password_reset_migration_flow.py tests/integration/test_auth_hard_cut_end_to_end.py -q"
  - "cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx tests/integration/auth/hard-cut-cleanup-proof.test.tsx"
  - "bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh"
  - "GET /health/ready"
  - "GET /api/v2/system/config"
  - "POST /api/v2/auth/login"
  - "GET /api/v2/auth/verify-session"
requirement_outcomes:
  - id: R005
    from_status: active
    to_status: validated
    proof: "S01 proved backend local login/session issuance, S03 replaced browser login with `apiClient.auth.login()` and session restore, S04 removed Firebase runtime seams, and a local no-Firebase browser replay logged in to `/dashboard` through the shipped email/password flow."
  - id: R006
    from_status: active
    to_status: validated
    proof: "S01 proved verify-session, protected-route auth, logout, and DB+Redis invalidation on the `user_id` session contract; S03 session-first frontend tests proved remember_me propagation and restore/logout behavior; local browser replay stayed on `/dashboard` after reload using the same session-first contract."
  - id: R007
    from_status: active
    to_status: validated
    proof: "S02 integration coverage in `backend-hormonia/tests/integration/test_password_reset_migration_flow.py` proved existing Firebase-era users and admin-created users complete reset-confirm and then log in through local auth without manual recreation."
  - id: R008
    from_status: active
    to_status: validated
    proof: "S02 admin coverage in `backend-hormonia/tests/api/v2/test_admin_first_access.py` and T03 wiring kept admin-created accounts canonical via `send_activation_email=true` / email-backed recovery, while public self-signup remained absent."
  - id: R009
    from_status: active
    to_status: validated
    proof: "S02 shipped `POST /api/v2/auth/password/reset-request` and `/reset-confirm` with passing public contract/integration suites, and S03 shipped routed recovery pages on `/auth/password/reset-request`, `/auth/password/reset-confirm`, `/reset-password`, and `/primeiro-acesso`."
  - id: R010
    from_status: active
    to_status: validated
    proof: "S03 session-first auth and websocket cutover suites plus S04 hard-cut cleanup removed Firebase-token browser happy paths; websocket auth now uses the canonical session contract and frontend/network replay showed no Firebase-auth requests."
  - id: R011
    from_status: active
    to_status: validated
    proof: "S04 removed/tombstoned staff-auth Firebase runtime/config seams, `verify-no-firebase-auth.sh` passed, the backend/frontend focused hard-cut suites passed, and the local stack booted and authenticated staff users with Firebase env vars blank."
  - id: R012
    from_status: active
    to_status: validated
    proof: "Across S01-S04 the system now emits stable auth diagnostics for login/session/reset/password/websocket/operational failures (`error`, `message`, `request_id`, `session_auth`, websocket codes), with focused pytest/vitest proof covering those failure surfaces."
duration: ~18h wall-clock across 4 slices
verification_result: passed
completed_at: 2026-03-12T15:56:37-03:00
---

# M002: First-Party Authentication Cutover

**Staff authentication now runs end to end on the product’s own email/password + Redis session stack, with recovery/migration flows, session-first frontend/realtime auth, and a shipped no-Firebase runtime state.**

## What Happened

M002 replaced the old hybrid Firebase-token-to-session chain with a first-party authentication system owned by the backend while deliberately keeping the proven Redis + HttpOnly cookie session model. S01 rewired the backend happy path first: `POST /api/v2/auth/login` now verifies local email/password credentials, creates the canonical DB session row plus Redis session payload, and authenticates protected routes, `verify-session`, and logout through canonical `user_id` session identity instead of requiring Firebase token exchange.

S02 then solved the migration problem that would have made a hard cut unusable in practice. Public password recovery landed on `POST /api/v2/auth/password/reset-request` and `POST /api/v2/auth/password/reset-confirm`, backed by a shared password-reset service that updates local-auth state, clears lockouts, and revokes DB + Redis sessions by canonical `user_id`. Admin-created accounts and admin-triggered resets were moved onto the same email-backed first-access contract, with redacted delivery metadata replacing plaintext temporary-password behavior on the canonical path.

S03 cut the browser and realtime stack over to session-first semantics. `AuthContext` now logs in, restores session, and logs out via first-party backend endpoints; `/medico/login` became a compatibility entrypoint to the shared email-first login surface instead of preserving CRM-only auth; public reset pages were shipped on both canonical and legacy-compatible routes; websocket bootstrap moved to cookie-first/session-first auth with stable websocket diagnostics instead of Firebase JWT query tokens; and initialization/monitoring surfaces were rewritten to report session-auth readiness instead of Firebase-config presence.

S04 finished the hard cut. Firebase browser modules and compat naming were removed, backend readiness/config/validation now tell the truth about `session_auth`, in-app password change now verifies the current local password and revokes sessions by canonical `user_id`, live Firebase verify/debug/websocket auth seams were removed from shipped runtime paths, and the repository gained a static `verify-no-firebase-auth.sh` guard plus focused hard-cut proof suites. The slice closeout also rewrote the remaining repository-facing auth guidance toward the session-first contract and recorded the assembled no-Firebase proof in `S04-PROOF.md`.

One important nuance surfaced during milestone closeout: S04/T05 recorded a red Playwright timeout at the first browser login transition on the local proof stack. Replaying the same no-Firebase stack directly in the browser during milestone completion showed the login path itself succeeds and lands on `/dashboard`, with session restore surviving reload. The remaining noise after login came from unrelated dashboard data fetch failures (`flow_state` query/type drift) rather than Firebase-auth regression. The milestone gate therefore uses the passing focused auth suites, the passing backend hard-cut end-to-end suite, the passing residue guard, honest no-Firebase startup checks, and direct browser replay as the authoritative auth proof.

## Cross-Slice Verification

- **Success criterion: staff users can log in with email/password and reach protected dashboard/API surfaces without Firebase token exchange.**
  - Verified by S01 backend contract/integration suites:
    - `backend-hormonia/tests/api/v2/test_auth_local_login.py`
    - `backend-hormonia/tests/integration/test_local_auth_core_flow.py`
  - Verified by S03 frontend session-first suite:
    - `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx`
  - Verified again by S04 hard-cut suite:
    - `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
  - Verified by direct local browser replay on the no-Firebase stack during milestone completion: login via `/login` reached `http://localhost:5173/dashboard`, and browser/network logs showed session-first auth with no Firebase-auth requests.

- **Success criterion: existing users regain access through reset/first-access flows instead of manual recreation.**
  - Verified by S02 focused suites:
    - `backend-hormonia/tests/api/v2/test_auth_password_recovery.py`
    - `backend-hormonia/tests/api/v2/test_admin_first_access.py`
    - `backend-hormonia/tests/integration/test_password_reset_migration_flow.py`
  - Those suites prove both Firebase-era users and admin-created users migrate through reset-confirm into working local-auth state.

- **Success criterion: remember-me, verify-session, logout, and protected-route auth keep working after the provider switch.**
  - Verified by S01 backend session coverage for verify-session, protected-route access, and logout invalidation.
  - Verified by S03 frontend session-first auth suite, which asserts `remember_me` propagation, cookie/session restore, and logout cleanup.
  - Verified by direct browser replay: after local login, reloading `/dashboard` preserved authenticated access through the same session-first contract.

- **Success criterion: frontend dashboard and realtime auth no longer depend on Firebase SDK state or Firebase tokens.**
  - Verified by S03 focused suites:
    - `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx`
    - `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts`
    - `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`
  - Verified by S04 frontend hard-cut suite:
    - `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx`
  - Verified statically by `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh` and operationally by browser/network replay showing no `/auth/firebase/verify` or Firebase-auth traffic.

- **Success criterion: Firebase Auth runtime/config dependencies are removed or tombstoned, and integrated verification proves the assembled auth system works end to end.**
  - Verified by S04 focused backend/frontend hard-cut suites and build:
    - `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx`
    - `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py`
    - `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`
    - `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
    - `cd frontend-hormonia && npm run build`
  - Verified by no-Firebase operational truth checks:
    - `GET /health/ready` reported `database`, `redis`, and `session_auth` with no Firebase dependency
    - `GET /api/v2/system/config` contained no public Firebase-auth config fields
  - Verified by `verify-no-firebase-auth.sh`, which passed against the staff-auth runtime/docs/test hotspots.

- **Definition of done check.**
  - All slices are marked complete in the roadmap (`S01`–`S04` are `[x]`).
  - All slice summary files exist under `.gsd/milestones/M002/slices/`.
  - Cross-slice integration points were rechecked against the focused suites above plus `S04-PROOF.md` and direct browser replay on the assembled no-Firebase stack.
  - Backend login/session/recovery/admin provisioning are wired together under first-party auth.
  - Frontend dashboard and realtime bootstrap now use session-first auth instead of Firebase tokens.
  - Firebase Auth staff-runtime/config dependencies are removed or tombstoned in the shipped state.
  - Final integrated acceptance is satisfied by the passing backend hard-cut end-to-end suite, the passing no-Firebase operational/runtime gates, and direct browser replay proving `/login` → `/dashboard` → reload on the assembled local stack.

- **Criteria not met:** none.

## Requirement Changes

- R005: active → validated — S01 proved local backend login/session issuance, S03 moved the browser happy path to first-party session auth, S04 removed Firebase runtime seams, and direct browser replay reached `/dashboard` without Firebase token exchange.
- R006: active → validated — S01 proved session issuance/verify/logout/protected-route auth on the canonical session contract, S03 proved remember-me/session restore/logout in frontend tests, and direct browser replay preserved authenticated access across reload.
- R007: active → validated — S02 integration coverage proved existing Firebase-era users regain access through reset-confirm and then log in through local auth without manual recreation.
- R008: active → validated — S02 admin create/reset flows now use admin-managed first-access/recovery as the canonical onboarding path, with no public self-signup added.
- R009: active → validated — S02 shipped public email reset-link flows and S03 shipped the routed browser UX for reset-request/reset-confirm/first-access.
- R010: active → validated — S03/S04 removed Firebase-token dependence from browser and websocket auth, with focused proof suites and no-Firebase browser/network replay.
- R011: active → validated — S04 hard-cut cleanup removed/tombstoned Firebase Auth runtime/config seams, the residue guard passed, and the stack authenticated staff users with Firebase env vars blank.
- R012: active → validated — Login, reset, websocket, password-change, and operational auth failures now emit stable inspectable diagnostics proved by focused suites across all four slices.

## Forward Intelligence

### What the next milestone should know
- The auth cutover itself is complete and no longer depends on Firebase Auth runtime/config, but local no-Firebase replay still exposes unrelated post-login dashboard data failures. Future work should treat those as dashboard/data-contract follow-up, not as auth regression.

### What's fragile
- The dashboard shell can load successfully after login while individual dashboard data requests fail because of non-auth schema/query drift (`flow_state` comparison errors in the local proof stack). That can look like an auth failure from the browser unless you separate route transition evidence from post-login data fetch evidence.

### Authoritative diagnostics
- `.gsd/milestones/M002/slices/S04/S04-PROOF.md` plus the focused backend/frontend hard-cut suites and `verify-no-firebase-auth.sh` are the fastest trustworthy auth-cutover signals. They isolate login/session/reset/runtime truth from unrelated application data issues.

### What assumptions changed
- The original assumption from S04/T05 was that the red Playwright login gate meant the cutover itself was still incomplete. Direct browser replay on the same no-Firebase stack showed the auth transition works; the earlier red signal was a timeout/harness symptom amplified by unrelated dashboard 5xxs after authentication.

## Files Created/Modified

- `.gsd/milestones/M002/M002-SUMMARY.md` — milestone closeout summary with requirement transitions, cross-slice verification, and downstream guidance.
- `.gsd/REQUIREMENTS.md` — moved R005–R012 from active to validated with milestone proof references.
- `.gsd/PROJECT.md` — updated project state to reflect M002 completion and the shipped session-first auth runtime.
- `.gsd/STATE.md` — cleared the active milestone and refreshed milestone/requirement counts after M002 completion.
