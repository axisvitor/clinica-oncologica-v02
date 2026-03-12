---
estimated_steps: 5
estimated_files: 8
---

# T02: Remove frontend Firebase runtime, compat naming, and package/env residue

**Slice:** S04 — Hard Cut Cleanup And Integrated Proof
**Milestone:** M002

## Description

Delete the remaining Firebase browser/runtime dependency from the shipped staff-auth path so the frontend can build, initialize, and authenticate entirely through first-party session contracts without ghost compatibility helpers or Firebase setup guidance.

## Steps

1. Remove the Firebase browser/runtime modules and any remaining imports from staff-auth code paths (`src/lib/firebase-client.ts`, `src/lib/firebase-lazy.ts`, `src/services/firebase-auth.ts`, dead password-change hook residue, and related type shims), updating callers to use the already-shipped first-party auth/session client instead.
2. Update `frontend-hormonia/src/lib/api-client/auth.ts` and `frontend-hormonia/src/app/providers/AuthContext.tsx` so `createSession(firebaseToken, ...)` is deleted and Firebase-token-named provider APIs are replaced with session-first naming or removed from the public contract entirely.
3. Strip legacy Firebase-auth env/config/test scaffolding from `runtime-config`, `config-initializer`, `ServiceMonitor`, `EnvironmentSetup`, `tests/setup.ts`, `vite.config.ts`, and `.env.example` so missing `VITE_FIREBASE_*` values never appear as a blocker for staff auth.
4. Remove the `firebase` package from `frontend-hormonia/package.json` and adjust any build/test aliases or mocks that only existed to keep Firebase-era code compiling.
5. Run the focused frontend integration proof, build, and residue guard; fix any remaining Firebase-auth hotspots surfaced by the new tests or static script.

## Must-Haves

- [ ] No shipped staff-auth runtime import path reaches `firebase/*` or a local Firebase wrapper module.
- [ ] `AuthContext` and the frontend auth client expose only session-first semantics for login/restore/logout/password management.
- [ ] Build/test/runtime config no longer requires or advertises `VITE_FIREBASE_*` for staff auth.
- [ ] The frontend still exposes inspectable auth/session initialization state without logging secrets.

## Verification

- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/hard-cut-cleanup-proof.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `cd frontend-hormonia && npm run build && cd .. && bash .gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`

## Observability Impact

- Signals added/changed: Frontend runtime/init logs and operational UI now speak only in session-auth and websocket-readiness terms.
- How a future agent inspects this: Run the focused vitest suites, build the frontend, and use the residue guard to confirm no Firebase-auth runtime or guidance remains.
- Failure state exposed: Any accidental Firebase reintroduction appears as a compile/import failure, failing hard-cut proof assertion, or static-guard hit with a concrete file path.

## Inputs

- `frontend-hormonia/src/lib/api-client/auth.ts` and `frontend-hormonia/src/app/providers/AuthContext.tsx` — current session-first implementation still carrying Firebase-named compatibility seams.
- `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md` — prior slice’s delete/tombstone ordering for frontend residue.

## Expected Output

- Frontend source/build/test config no longer contains Firebase-auth runtime modules, aliases, or package dependencies for staff auth.
- `frontend-hormonia/src/lib/api-client/auth.ts`, `frontend-hormonia/src/app/providers/AuthContext.tsx`, and initialization/config surfaces express session-first semantics only.
- The focused frontend proof and residue guard stay green without `VITE_FIREBASE_*` inputs.
