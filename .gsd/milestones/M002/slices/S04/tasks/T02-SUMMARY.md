---
id: T02
parent: S04
milestone: M002
provides:
  - Frontend staff-auth runtime is session-first only, with Firebase browser modules, compat API naming, and frontend Firebase env/package residue removed
key_files:
  - frontend-hormonia/src/lib/api-client/auth.ts
  - frontend-hormonia/src/app/providers/AuthContext.tsx
  - frontend-hormonia/src/lib/runtime-config.ts
  - frontend-hormonia/src/lib/config-initializer.tsx
  - frontend-hormonia/src/features/initialization/ServiceMonitor.tsx
  - frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx
  - frontend-hormonia/vite.config.ts
  - frontend-hormonia/package.json
key_decisions:
  - Firebase browser/runtime modules were hard-deleted instead of left as tombstones because the shipped staff-auth path no longer imports them anywhere and proof now protects against reintroduction
  - IndexedDB cache support now depends directly on `idb` so removing Firebase does not leave the frontend build relying on a vanished transitive dependency
patterns_established:
  - Frontend auth/public config surfaces should expose only session-first naming (`login`, `restore`, `logout`, `logoutAll`, password change via current_password + new_password) and keep readiness diagnostics centered on session + websocket state
observability_surfaces:
  - Focused vitest suites, `npm run build`, frontend init/service monitor logs, and `.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
duration: 2h+
verification_result: partial
completed_at: 2026-03-12T13:40:00-03:00
blocker_discovered: false
---

# T02: Remove frontend Firebase runtime, compat naming, and package/env residue

**Removed the frontend Firebase auth runtime and compat seams so shipped staff auth is session-first only, while leaving the remaining backend/docs residue for T03–T05.**

## What Happened

I completed the T02 frontend hard-cut cleanup across runtime, provider/API naming, config, and package residue.

### Frontend auth/runtime cleanup

I removed the Firebase browser/runtime path from the shipped frontend staff-auth flow:

- deleted `frontend-hormonia/src/lib/firebase-client.ts`
- deleted `frontend-hormonia/src/lib/firebase-lazy.ts`
- deleted `frontend-hormonia/src/services/firebase-auth.ts`
- deleted the dead Firebase password-change hook at `frontend-hormonia/src/hooks/usePasswordChange.ts`
- deleted Firebase-only frontend test artifacts that existed only to keep those modules alive

### Session-first auth API/provider contract cleanup

I updated the canonical frontend auth surfaces so they no longer expose Firebase-era semantics:

- `frontend-hormonia/src/lib/api-client/auth.ts`
  - removed `createSession(firebaseToken, ...)`
  - replaced `PasswordChange.old_password` with `current_password`
  - implemented first-party `changePassword()` against `/api/v2/auth/password`
- `frontend-hormonia/src/app/providers/AuthContext.tsx`
  - removed `getFirebaseToken()` from the public provider contract
  - kept only session-first semantics for login/restore/logout/logoutAll/refresh

This satisfies the focused S04 proof that checks the public auth contract directly.

### Password/settings cleanup

I updated the frontend password-change wiring so it now sends the first-party contract:

- `frontend-hormonia/src/hooks/useSettings.ts`
  - now submits `{ current_password, new_password }`
  - removed Firebase re-auth guidance/comments
- `frontend-hormonia/src/features/settings/sections/SecuritySettings.tsx`
  - kept the same UI, now backed by the session-first request contract already expected by the proof

### Runtime/config/env/package cleanup

I removed frontend Firebase env/config/package residue:

- `frontend-hormonia/src/lib/runtime-config.ts`
  - removed all `VITE_FIREBASE_*` fields and logging
- `frontend-hormonia/src/lib/config-initializer.tsx`
  - removed legacy Firebase-config diagnostics from init logging
- `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx`
  - removed legacy Firebase-config checks from session readiness diagnostics
- `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx`
  - removed legacy Firebase-config checks/messages from environment readiness UI
- `frontend-hormonia/src/lib/env-validator.ts`
  - removed `VITE_FIREBASE_*` validation rules
- `frontend-hormonia/tests/setup.ts`
  - removed injected Firebase env vars
- `frontend-hormonia/vite.config.ts`
  - removed Firebase test aliases
- `frontend-hormonia/.env.example`
  - removed the frontend Firebase env block entirely
- `frontend-hormonia/package.json`
  - removed the `firebase` dependency

### Build follow-up found during verification

After removing `firebase`, the frontend build failed because `src/lib/react-query/persistentCache.ts` imports `idb` directly while the package had only been present transitively.

I fixed that by adding a direct frontend dependency on `idb`, which restores a real build contract instead of relying on Firebase-era transitive installation.

## Verification

I ran the T02 verification commands and recorded the real outcomes.

### Focused frontend proofs
- Command:
  - `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/hard-cut-cleanup-proof.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- Result: **passed**

This confirmed:
- no public `createSession` Firebase bridge remains
- `AuthProvider` no longer exposes `getFirebaseToken`
- password change submits `{ current_password, new_password }`
- session/websocket/init surfaces still report session-first diagnostics

### Frontend build
- Command:
  - `cd frontend-hormonia && npm run build`
- Result: **passed**

Note: the first build attempt failed on missing direct dependency `idb`; I fixed that by adding `idb` explicitly, then reran the build successfully.

### Static residue guard
- Command:
  - `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`
- Result: **partial / still red at slice level**

The guard no longer reports the T02-owned frontend runtime/config/package hotspots. Remaining failures are in later-task scope:
- backend Firebase verify seam and password-change semantics (`T03`/`T04`)
- backend operational/config Firebase publication (`T03`)
- docs/E2E Firebase setup guidance (`T05`)

So T02’s frontend hard-cut is in place, but the slice-wide no-Firebase guard is not green yet because later tasks still own remaining residue.

## Diagnostics

Future agents can inspect the delivered T02 state with:

- `frontend-hormonia/src/lib/api-client/auth.ts`
- `frontend-hormonia/src/app/providers/AuthContext.tsx`
- `frontend-hormonia/src/hooks/useSettings.ts`
- `frontend-hormonia/src/lib/runtime-config.ts`
- `frontend-hormonia/src/lib/config-initializer.tsx`
- `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx`
- `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx`
- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/hard-cut-cleanup-proof.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `cd frontend-hormonia && npm run build`
- `bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`

Most important current inspection signal:
- if the guard still fails, the remaining failures should now all point at backend/docs surfaces rather than frontend runtime/package/env seams

## Deviations

- I added `idb` as a direct dependency even though it was not called out in the written task plan, because removing Firebase exposed that the build had been depending on `idb` transitively instead of declaring the package directly.

## Known Issues

- The slice-wide guard is still red because backend Firebase verify/password/config residue and Firebase setup guidance in docs/E2E assets remain; these are expected follow-on targets for `T03`, `T04`, and `T05`.
- Many non-gating historical frontend tests still use Firebase-era wording/mocks outside the focused T02 verification set. They were not rewritten here unless they directly blocked the T02 proof/build/runtime cleanup.

## Files Created/Modified

- `frontend-hormonia/src/lib/api-client/auth.ts` — removed the Firebase verify bridge and made password change first-party/session-first.
- `frontend-hormonia/src/app/providers/AuthContext.tsx` — removed Firebase-token-named provider API from the shipped auth contract.
- `frontend-hormonia/src/hooks/useSettings.ts` — changed settings password updates to send `{ current_password, new_password }` only.
- `frontend-hormonia/src/lib/runtime-config.ts` — removed frontend Firebase env declarations/logging from runtime config.
- `frontend-hormonia/src/lib/config-initializer.tsx` — removed legacy Firebase readiness/config diagnostics from initialization logging.
- `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx` — removed Firebase-based readiness/config checks from service monitoring.
- `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx` — removed Firebase-based env readiness checks and guidance from setup UI.
- `frontend-hormonia/src/lib/env-validator.ts` — removed `VITE_FIREBASE_*` validation rules.
- `frontend-hormonia/tests/setup.ts` — removed injected Firebase env scaffolding from frontend tests.
- `frontend-hormonia/vite.config.ts` — removed Firebase test aliases.
- `frontend-hormonia/.env.example` — removed the frontend Firebase env example block.
- `frontend-hormonia/package.json` — removed `firebase` and added direct `idb` dependency required by the real build.
- `frontend-hormonia/package-lock.json` — lockfile updated after dependency cleanup and direct `idb` install.
- `frontend-hormonia/src/types/vendor.d.ts` — removed Firebase module shims that only existed for the deleted frontend runtime.
- `frontend-hormonia/src/lib/firebase-client.ts` — deleted Firebase browser runtime module.
- `frontend-hormonia/src/lib/firebase-lazy.ts` — deleted Firebase lazy-loader runtime module.
- `frontend-hormonia/src/services/firebase-auth.ts` — deleted Firebase session bridge service.
- `frontend-hormonia/src/hooks/usePasswordChange.ts` — deleted dead Firebase password-change hook.
- `frontend-hormonia/src/lib/__tests__/firebase-client-initialization.test.ts` — deleted Firebase-only unit coverage.
- `frontend-hormonia/tests/unit/lib/test_firebase_client.ts` — deleted Firebase-only frontend client test.
- `frontend-hormonia/tests/unit/services/firebase-auth.comprehensive.test.ts` — deleted Firebase-only service suite.
- `frontend-hormonia/tests/unit/services/firebase-auth-session.test.ts` — deleted Firebase-only service session suite.
- `frontend-hormonia/tests/unit/services/token-refresh-validation.test.ts` — deleted Firebase-only token-refresh suite.
- `frontend-hormonia/tests/auth/firebase-auth-comprehensive.test.tsx` — deleted legacy Firebase-only auth proof suite.
- `frontend-hormonia/tests/e2e/integration.spec.ts` — deleted Firebase-focused E2E artifact.
- `frontend-hormonia/tests/integration/lazy-loading.test.tsx` — deleted Firebase lazy-loading integration suite.
