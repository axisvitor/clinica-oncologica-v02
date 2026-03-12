# M002/S04 — Hard Cut Cleanup And Integrated Proof — Research

**Date:** 2026-03-12

## Summary

S04 owns **R011** (hard-cut Firebase Auth from staff-auth runtime/compat paths) and **R012** (inspectable auth failures with integrated proof). It also materially supports **R005**, **R006**, **R007**, **R009**, and **R010** because the final slice is where the shipped system must prove first-party login, session continuity, recovery, realtime/session bootstrap, and runtime boot all work together without Firebase Auth in the loop.

The good news is that the proof baseline is already stronger than the placeholder slice summaries suggest. During this research session, the focused frontend cutover suites passed, the backend websocket/local-login/password-reset suites passed, the backend integration flows for local auth and reset migration passed, and `frontend-hormonia && npm run build` passed. That means S04 is not blocked on unknown auth core behavior; it is primarily a **cleanup + operational decoupling + proof assembly** slice.

The real remaining work is removing Firebase-auth residue that still makes the shipped state dishonest: frontend runtime modules/tests/env knobs still exist, backend operational health/config/startup surfaces still model Firebase as required, and one live password-change path still depends on Firebase Admin SDK semantics. The safest S04 approach is to delete/tombstone in batches, keep the existing focused proof suites green after every batch, and only then claim the hard cut.

## In-Scope Requirement Targeting

### Slice-owned active requirements
- **R011 — Firebase Auth dependency is hard-cut from runtime and compatibility paths**
- **R012 — Authentication failures become inspectable instead of opaque**

### Slice-supported active requirements
- **R005 — First-party staff login replaces Firebase Auth**
- **R006 — Existing Redis session continuity survives the auth cutover**
- **R007 — Existing users regain access without manual recreation**
- **R009 — Users can recover passwords via email reset link**
- **R010 — Frontend and realtime auth no longer depend on Firebase tokens**

### Not a primary S04 target
- **R008** stays primarily owned by S02/S03; S04 only needs to avoid regressing the shipped admin-created-account flow.

## Current Proof Baseline

These commands were run during research and are already green:

- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_password_recovery.py tests/integration/test_password_reset_migration_flow.py -q`
- `cd backend-hormonia && pytest tests/integration/test_local_auth_core_flow.py tests/integration/test_password_reset_migration_flow.py -q`
- `cd frontend-hormonia && npm run build`

This means S04 should reuse these as the deletion/proof gate rather than inventing a brand-new mega-suite first.

## Recommendation

Take a **three-batch hard-cut** approach:

1. **Frontend residue removal first**
   - Delete the Firebase browser modules, Vite test aliases, legacy env declarations, and Firebase-only tests identified by the S03 removal map.
   - Remove the `firebase` dependency from `frontend-hormonia/package.json` only after the source/test imports are gone.
   - Rewrite or tombstone Firebase-named tests instead of trying to keep them semantically identical.

2. **Backend operational decoupling second**
   - Rewrite health/config/validation/initialization surfaces so missing Firebase admin credentials does **not** make staff-auth runtime look unhealthy or not-ready.
   - Remove public config emission of `VITE_FIREBASE_*` values and stop presenting Firebase as a required component for startup.
   - Fix misleading auth dependency initialization logging that still claims auth “will not work” when Firebase is absent.

3. **Backend compatibility seam cleanup + integrated proof last**
   - Tombstone or remove `/api/v2/auth/firebase/verify`, the Firebase-only password-change path, and websocket-manager Firebase fallback paths that are no longer part of the shipped browser happy path.
   - Keep only session-first contracts for login, verify-session, logout, logout-all, reset-request, reset-confirm, and websocket session auth.
   - Finish with an integrated proof bundle covering: login → session restore → protected access → reset/first-access → logout, plus boot/readiness without Firebase browser/admin config.

Primary recommendation: **do not hand-roll a new auth framework for S04**. Reuse the existing S01/S02/S03 session-first contracts and delete the old Firebase seams around them.

## Don’t Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Session-first browser auth proof | `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` | Already pins login/restore/logout semantics against the real first-party client contract. |
| Recovery / migration proof | `backend-hormonia/app/services/password_reset_service.py` + `tests/api/v2/test_auth_password_recovery.py` + `tests/integration/test_password_reset_migration_flow.py` | Reuses the shipped reset/first-access orchestration instead of creating another migration path. |
| Websocket session identity | `backend-hormonia/app/api/v2/auth_session_shared.py` + `tests/api/test_websocket_session_auth_contract.py` | Canonical cookie/header/query-fallback resolution already exists and is proven. |
| Deletion order for frontend cleanup | `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md` | It already groups delete-now vs rewrite/tombstone work and is the lowest-risk S04 execution map. |

## Existing Code and Patterns

- `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md` — authoritative S04 deletion order for frontend runtime modules, tests, env knobs, and doc residue.
- `frontend-hormonia/src/app/providers/AuthContext.tsx` — canonical session-first browser auth provider; the runtime is already cookie/session-first and the remaining `getFirebaseToken()` name is compatibility residue.
- `frontend-hormonia/src/lib/api-client/auth.ts` — first-party login/reset/verify/logout client is already shipped; `createSession(firebaseToken, ...)` is the legacy escape hatch S04 should delete.
- `frontend-hormonia/src/lib/websocket.ts` — shipped websocket bootstrap is already session-first; keep this contract and remove older Firebase-era helpers/tests around it.
- `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx` and `ServiceMonitor.tsx` — S03 already moved the operational UI to session-auth readiness; backend system surfaces should now match that story.
- `backend-hormonia/app/services/auth.py` — canonical local credential validation and account-lock handling for S01 login.
- `backend-hormonia/app/services/password_reset_service.py` — canonical reset/first-access/migration orchestration with session revocation keyed to `user_id`.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — shared session resolver and embedded canonical-user extraction for realtime/session consumers.
- `backend-hormonia/app/api/v2/routers/auth.py` — local login/reset contracts are real, but the same router still contains `/firebase/verify` and a Firebase-only `/password` change route.
- `backend-hormonia/app/routers/health.py` and `backend-hormonia/app/api/v2/routers/system/*` — still the highest-value operational cleanup zone because they continue to model Firebase as a required/inspectable component.

## Constraints

- Preserve the **Redis + HttpOnly cookie** session architecture; S04 is a hard cut of the identity provider, not a JWT redesign.
- The shipped state must boot and pass staff-auth flows **without requiring** `VITE_FIREBASE_*` browser config or `FIREBASE_ADMIN_*` backend credentials for staff auth.
- Keep the existing focused gate green after each cleanup batch instead of saving all deletions for one final rerun.
- `firebase_uid` may still exist as compatibility data in user/session payloads, but it must not remain a required happy-path key for staff auth.
- Recovery links must continue to land on the routed public UX already shipped in S03: `/auth/password/reset-request`, `/auth/password/reset-confirm`, `/reset-password`, and `/primeiro-acesso`.
- S02/S03 top-level slice summaries are placeholders; task summaries and actual code/tests are the trustworthy source of prior-slice behavior.

## What S04 Must Clean Up

### 1. Frontend runtime and package residue

These are still present and should be treated as primary hard-cut targets:

- `frontend-hormonia/src/lib/firebase-client.ts`
- `frontend-hormonia/src/lib/firebase-lazy.ts`
- `frontend-hormonia/src/services/firebase-auth.ts`
- `frontend-hormonia/src/types/vendor.d.ts`
- `frontend-hormonia/vite.config.ts` test aliases for `firebase/app` and `firebase/auth`
- `frontend-hormonia/src/lib/runtime-config.ts` Firebase env fields
- `frontend-hormonia/src/lib/env-validator.ts` Firebase validation rules
- `frontend-hormonia/tests/setup.ts` injected `VITE_FIREBASE_*`
- `frontend-hormonia/.env.example` legacy Firebase block
- `frontend-hormonia/package.json` still declares `firebase`
- `frontend-hormonia/src/lib/api-client/auth.ts` still exposes `createSession(firebaseToken, ...)`

### 2. Frontend compat naming/tests/docs residue

These are not all runtime blockers, but they will make the hard cut incomplete if left untouched:

- `frontend-hormonia/src/app/providers/AuthContext.tsx` still exposes `getFirebaseToken()` as a compat name
- Firebase-shaped tests remain in:
  - `tests/auth/firebase-auth-comprehensive.test.tsx`
  - `tests/auth/user-state-management.test.tsx`
  - `tests/components/auth/AuthContext.test.tsx`
  - `tests/unit/contexts/AuthContext.comprehensive.test.tsx`
  - `tests/unit/hooks/useWebSocket.comprehensive.test.ts`
  - `tests/integration/auth/auth-flow.comprehensive.test.tsx`
  - `tests/integration/auth/race-condition.test.tsx`
  - `tests/integration/api-connections.test.ts`
  - `tests/integration/admin-auth-flow.test.tsx`
  - `tests/integration/lazy-loading.test.tsx`
  - `tests/e2e/integration.spec.ts`
- Docs and setup guides still instruct Firebase config or assert Firebase behavior:
  - `frontend-hormonia/src/features/initialization/README.md`
  - `frontend-hormonia/tests/e2e/README.md`
  - `frontend-hormonia/tests/e2e/SETUP_INSTRUCTIONS.md`
  - `frontend-hormonia/tests/TEST_SUITE_SUMMARY.md`
  - `docs/frontend/guides/api/API_GUIDE.md`
  - `docs/frontend/guides/configuration/ENVIRONMENT_GUIDE.md`
  - `docs/frontend/guides/deployment/DEPLOYMENT_GUIDE.md`

### 3. Backend operational/runtime coupling that still breaks the hard-cut story

These are likely the highest-risk backend blockers for R011/R012:

- `backend-hormonia/app/routers/health.py` — readiness/startup validation still treats Firebase config as required and can mark the app not ready when Firebase creds are absent.
- `backend-hormonia/app/api/v2/routers/system/validation.py` — still recommends configuring Firebase Admin SDK.
- `backend-hormonia/app/api/v2/routers/system/health.py` + `helpers/health_checker.py` — still includes `firebase` as a first-class component.
- `backend-hormonia/app/api/v2/routers/system/initialization.py` — still initializes/skips a `firebase` component.
- `backend-hormonia/app/api/v2/routers/system/config.py` + `helpers/config_builder.py` + `app/schemas/v2/system.py` — still publish/shape public `VITE_FIREBASE_*` config.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — module init still logs that auth “will not work” if Firebase creds are absent; this becomes misleading after the cutover.

### 4. Backend auth compatibility seams still carrying Firebase behavior

- `backend-hormonia/app/api/v2/routers/auth.py`:
  - `POST /api/v2/auth/firebase/verify`
  - Firebase-based `/api/v2/auth/password`
  - logout-all cache invalidation still keyed to `firebase_uid`
- `backend-hormonia/app/middleware/csrf.py` and `app/middleware/config.py` still exempt `/api/v2/auth/firebase/verify`
- `backend-hormonia/app/api/v2/routers/debug/auth.py` still uses `verify_firebase_token()` for debug token inspection
- `backend-hormonia/app/services/websocket/connection_manager.py` still imports Firebase auth and supports `auth_type="firebase"` / `auto`
- `backend-hormonia/app/services/firebase_auth_service.py`, `firebase_auth_shared.py`, `firebase_user_sync_service.py`, and `firebase_auth_circuit_breaker.py` remain live compat/service files; whether they are deleted or tombstoned depends on confirmed non-staff callers, but they should not remain required for staff-auth boot or proof

### 5. One live password-management blocker

A real runtime blocker remains outside the login/reset happy path:

- `frontend-hormonia/src/hooks/useSettings.ts` still sends password changes to `/api/v2/auth/password`
- `frontend-hormonia/src/features/settings/sections/SecuritySettings.tsx` uses that hook
- `backend-hormonia/app/api/v2/routers/auth.py` implements `/api/v2/auth/password` by requiring `firebase_uid` and updating Firebase Admin SDK state

This means staff password change is still Firebase-dependent even after login/reset cutover. S04 should either:

- migrate `/api/v2/auth/password` to first-party current-password verification + local hash update + session revocation, reusing the same password policy direction as S02, **or**
- explicitly disable/tombstone this UI/route and record that it is not part of the shipped auth surface.

For an honest hard cut, the first option is better.

## Common Pitfalls

- **Deleting frontend Firebase files without removing Vite aliases/test env injection** — tests will keep compiling against ghost `firebase/*` imports and mask incomplete cleanup.
- **Claiming the hard cut while backend readiness still fails without Firebase creds** — `app/routers/health.py` and system routes are currently the clearest operational contradiction.
- **Leaving `/api/v2/auth/password` untouched** — login/reset may be clean, but staff password management would still require Firebase Admin SDK.
- **Keeping `createSession(firebaseToken)` and `getFirebaseToken()` “for now”** — those names become a reintroduction path and keep tests/docs anchored to the old model.
- **Trying to rewrite every legacy auth test into equivalent session-first coverage** — many should be deleted or tombstoned once the focused proof suites already cover the canonical behavior.
- **Blindly removing backend Firebase packages before checking out-of-scope callers** — staff-auth surfaces should stop requiring Firebase immediately, but package deletion should follow confirmed caller analysis rather than guesswork.

## Open Risks

- `frontend-hormonia/package.json` still depends on `firebase`, so accidental reintroduction remains easy until the dependency is removed.
- `backend-hormonia/app/services/websocket/connection_manager.py` still ships Firebase/JWT auth modes; hidden legacy callers or tests may fail when S04 tightens this.
- The workspace still contains a Firebase admin service-account JSON artifact in the repository root; S04 should ensure the app no longer depends on file-based Firebase credentials and should treat this as ops-cleanup risk.
- There is a large volume of Firebase-era docs/tests. Without a strict tombstone/delete policy, S04 can sprawl into documentation archaeology instead of shipped proof.
- Backend `firebase_uid` fields remain widespread in models/types/tests. S04 should not expand into a full data-model rename unless directly needed for the hard-cut proof.

## Suggested S04 Proof Gate

Keep this gate green after every deletion batch:

### Frontend
- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `cd frontend-hormonia && npm run build`

### Backend
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_password_recovery.py tests/integration/test_local_auth_core_flow.py tests/integration/test_password_reset_migration_flow.py -q`

### Final integrated acceptance to add/assemble in S04
- Boot backend/frontend with Firebase browser/admin auth config absent on the staff-auth path
- Browser/UAT proof for:
  - `/login` login success
  - session restore on reload
  - protected dashboard/API access
  - reset-request + reset-confirm
  - logout / logout-all
- Explicit artifact checks proving no staff-auth runtime imports/routes/env guidance still point at Firebase Auth

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | suggested via `npx skills find` (6.1K installs) |
| FastAPI | `mindrally/skills@fastapi-python` | suggested via `npx skills find` (2K installs) |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | suggested via `npx skills find` (200.2K installs) |
| Playwright | `currents-dev/playwright-best-practices-skill@playwright-best-practices` | suggested via `npx skills find` (8.2K installs) |

## Sources

- S03 deletion ordering, compat seams, and env/doc cleanup targets (source: `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md`)
- Session-first browser auth implementation and remaining compat naming (`getFirebaseToken`) (source: `frontend-hormonia/src/app/providers/AuthContext.tsx`)
- Session-first auth client with lingering `createSession(firebaseToken, ...)` bridge (source: `frontend-hormonia/src/lib/api-client/auth.ts`)
- Frontend Firebase runtime residue and env/test alias coupling (source: `frontend-hormonia/src/lib/firebase-client.ts`, `frontend-hormonia/src/lib/firebase-lazy.ts`, `frontend-hormonia/src/services/firebase-auth.ts`, `frontend-hormonia/src/lib/runtime-config.ts`, `frontend-hormonia/src/lib/env-validator.ts`, `frontend-hormonia/vite.config.ts`, `frontend-hormonia/package.json`)
- Password reset / first-access canonical service and user-id session revocation (source: `backend-hormonia/app/services/password_reset_service.py`)
- Canonical local credential auth (source: `backend-hormonia/app/services/auth.py`)
- Canonical websocket/session resolver utilities (source: `backend-hormonia/app/api/v2/auth_session_shared.py`)
- Backend operational Firebase coupling still present in health/config/validation/init/public-config surfaces (source: `backend-hormonia/app/routers/health.py`, `backend-hormonia/app/api/v2/routers/system/config.py`, `backend-hormonia/app/api/v2/routers/system/validation.py`, `backend-hormonia/app/api/v2/routers/system/health.py`, `backend-hormonia/app/api/v2/routers/system/initialization.py`, `backend-hormonia/app/api/v2/routers/system/helpers/config_builder.py`, `backend-hormonia/app/api/v2/routers/system/helpers/health_checker.py`, `backend-hormonia/app/schemas/v2/system.py`)
- Backend auth router still carrying Firebase verify and Firebase-only password change (source: `backend-hormonia/app/api/v2/routers/auth.py`)
- Remaining Firebase fallback in websocket manager (source: `backend-hormonia/app/services/websocket/connection_manager.py`)
- Current green proof baseline for S04 cleanup work (source: command results from this research session for frontend vitest auth/realtime/initialization suites, backend pytest auth/recovery/websocket/integration suites, and `frontend-hormonia && npm run build`)
