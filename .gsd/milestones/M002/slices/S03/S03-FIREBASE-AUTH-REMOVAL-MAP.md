# S03 → S04 Firebase Auth Removal Map

Purpose: make S04 a low-ambiguity cleanup pass now that S03 has cut the shipped browser and realtime happy path over to first-party backend sessions.

## Removal Gate

Before deleting each batch below, keep these proofs green:

- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
- `cd frontend-hormonia && npm run build`

If a deletion breaks one of those commands, stop and either restore the compat seam or tombstone it explicitly.

## A. Delete Immediately Once S03 Proof Stays Green

These files are Firebase-auth implementation residue, not part of the canonical staff-auth runtime.

### Runtime modules
- `frontend-hormonia/src/lib/firebase-client.ts`
- `frontend-hormonia/src/lib/firebase-lazy.ts`
- `frontend-hormonia/src/services/firebase-auth.ts`

### Firebase-auth-only tests
- `frontend-hormonia/src/lib/__tests__/firebase-client-initialization.test.ts`
- `frontend-hormonia/tests/auth/firebase-auth-comprehensive.test.tsx`
- `frontend-hormonia/tests/unit/lib/test_firebase_client.ts`
- `frontend-hormonia/tests/unit/services/firebase-auth.comprehensive.test.ts`
- `frontend-hormonia/tests/unit/services/firebase-auth-session.test.ts`
- `frontend-hormonia/tests/e2e/integration.spec.ts`
- `frontend-hormonia/tests/integration/lazy-loading.test.tsx` if no non-Firebase lazy-loading behavior still matters after removal

### Build/test compatibility seams that should disappear with the modules above
- `frontend-hormonia/vite.config.ts` test-only aliases for `firebase/app` and `firebase/auth`

## B. Tombstone Or Rename After Callers Are Migrated

These surfaces still carry Firebase-era names or compatibility bridges but are no longer canonical behavior.

### Shims / compat API surfaces
- `frontend-hormonia/src/app/providers/AuthContext.tsx` — `getFirebaseToken()` is now a session-id/session token shim; rename/remove after websocket callers stop using the Firebase-era name.
- `frontend-hormonia/src/contexts/AuthContext.tsx` — remove/rename Firebase-named exports if still mirrored here.
- `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx` — remove any remaining Firebase-named compat fields once physician flows consume only session-first names.
- `frontend-hormonia/src/lib/api-client/auth.ts` — delete `createSession(firebaseToken, ...)` and `/api/v2/auth/firebase/verify` bridge once no callers remain.

### Firebase-shaped tests that should be rewritten, not blindly deleted
- `frontend-hormonia/tests/auth/user-state-management.test.tsx`
- `frontend-hormonia/tests/components/auth/AuthContext.test.tsx`
- `frontend-hormonia/tests/unit/contexts/AuthContext.comprehensive.test.tsx`
- `frontend-hormonia/tests/unit/hooks/useWebSocket.comprehensive.test.ts`
- `frontend-hormonia/tests/integration/auth/auth-flow.comprehensive.test.tsx`
- `frontend-hormonia/tests/integration/auth-flow-comprehensive.test.tsx`
- `frontend-hormonia/tests/integration/api-connections.test.ts`
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx`
- `frontend-hormonia/tests/integration/auth/race-condition.test.tsx`

Expected S04 action: rewrite them around session auth semantics or tombstone them if superseded by the S03 proof suites.

## C. Env Knobs To Remove From Public Guidance First, Then Delete From Code

S03 already makes these optional in operational/build guidance. S04 should remove the knobs themselves once the legacy Firebase modules are gone.

### Knob names
- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_FIREBASE_MESSAGING_SENDER_ID`
- `VITE_FIREBASE_APP_ID`
- `VITE_FIREBASE_MEASUREMENT_ID`

### Code paths still declaring or validating them
- `frontend-hormonia/src/lib/runtime-config.ts`
- `frontend-hormonia/src/lib/env-validator.ts`
- `frontend-hormonia/tests/setup.ts`
- `frontend-hormonia/.env.example`

Expected S04 action: delete the fields from `RuntimeConfig`, remove validator entries, drop test env injection, and remove the legacy comment block from `.env.example` entirely.

## D. Firebase-Named Data/Test Residue Requiring Follow-Up

These are not necessarily auth-runtime blockers, but they keep Firebase-era vocabulary alive.

### Type/data residue
- `frontend-hormonia/src/types/api.ts` — `firebase_uid?`
- `frontend-hormonia/src/types/admin.ts` — `firebase_*` profile/sync fields
- `frontend-hormonia/src/lib/api-client/normalizers.ts` — `firebase_uid` mapping
- `frontend-hormonia/src/lib/api-client/admin.ts` — `firebase_uid?`

### Docs / setup residue
- `frontend-hormonia/src/features/initialization/README.md`
- `frontend-hormonia/tests/e2e/README.md`
- `frontend-hormonia/tests/e2e/SETUP_INSTRUCTIONS.md`
- `frontend-hormonia/tests/TEST_SUITE_SUMMARY.md`
- Any remaining `Firebase` wording in test titles or diagnostics after the above rewrites

Expected S04 action: either remove these fields/docs if the backend no longer exposes them, or tombstone them with an explicit “legacy compatibility only” note until a later data-contract cleanup.

## Suggested S04 Deletion Order

1. Remove Firebase-only tests and modules from **Section A**.
2. Delete Vite test aliases and all `VITE_FIREBASE_*` declarations from code/tests in **Section C**.
3. Rewrite or tombstone Firebase-named compat tests and shims from **Section B**.
4. Clean type/docs residue from **Section D**.
5. Re-run the S03 proof gate after every batch, not just at the end.
