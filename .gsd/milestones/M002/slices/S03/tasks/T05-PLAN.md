---
estimated_steps: 4
estimated_files: 6
---

# T05: Update operational auth surfaces and record the S04 Firebase removal map

**Slice:** S03 — Frontend And Realtime Cutover
**Milestone:** M002

## Description

Reduce the remaining frontend runtime coupling now that the browser path is cut over, and leave S04 an explicit cleanup/removal checklist instead of a repo-wide archaeology pass.

## Steps

1. Update `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx` and `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx` so startup checks describe first-party session auth and websocket readiness rather than treating Firebase Auth config as a required service.
2. Adjust `frontend-hormonia/src/lib/runtime-config.ts`, `frontend-hormonia/.env.example`, and `frontend-hormonia/vite.config.ts` so build/runtime guidance no longer advertises Firebase Auth env vars or chunking as mandatory for staff auth.
3. Write `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md` naming the remaining Firebase auth modules, env knobs, and Firebase-named test suites that S04 should delete or tombstone after this slice’s proof is green.
4. Run the focused frontend cutover suites plus a production build to confirm operational surfaces no longer regress to Firebase-required startup assumptions.

## Must-Haves

- [ ] Initialization and service-monitoring UI no longer flags missing Firebase Auth config as a blocker for staff login.
- [ ] Frontend env/build guidance reflects first-party session auth as the canonical runtime path.
- [ ] The removal map explicitly lists remaining Firebase auth modules/tests/env knobs, grouped by what S04 can delete immediately versus what still needs a tombstone or follow-up.
- [ ] Operational/auth diagnostics still avoid logging secrets while making startup/session-auth state easy to inspect.

## Verification

- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd frontend-hormonia && npm run build`

## Observability Impact

- Signals added/changed: Startup health and service-check UX now report session-auth / websocket readiness rather than a stale Firebase dependency state.
- How a future agent inspects this: Use the initialization wizard screens, the focused frontend proof suites, the build output, and the removal-map doc.
- Failure state exposed: Missing session-auth wiring or stale Firebase-required startup copy is visible in the initialization surfaces and final build proof.

## Inputs

- `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx` / `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx` — operational UI surfaces still describing Firebase auth as required.
- `frontend-hormonia/vite.config.ts` / `frontend-hormonia/.env.example` — build/env artifacts that still imply Firebase Auth runtime dependence.

## Expected Output

- `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx` and `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx` — session-auth-aware operational surfaces.
- `frontend-hormonia/src/lib/runtime-config.ts`, `frontend-hormonia/.env.example`, and `frontend-hormonia/vite.config.ts` — runtime/build guidance aligned to first-party auth.
- `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md` — concrete S04 cleanup map for remaining Firebase auth residue.
