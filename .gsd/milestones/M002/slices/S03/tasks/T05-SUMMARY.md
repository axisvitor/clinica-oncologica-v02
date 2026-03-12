---
id: T05
parent: S03
milestone: M002
provides:
  - Session-first operational startup surfaces and an explicit S04 Firebase auth removal map.
key_files:
  - frontend-hormonia/src/features/initialization/ServiceMonitor.tsx
  - frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx
  - frontend-hormonia/src/lib/runtime-config.ts
  - frontend-hormonia/.env.example
  - frontend-hormonia/vite.config.ts
  - .gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md
  - frontend-hormonia/tests/integration/initialization/session-auth-operational-surfaces.test.tsx
key_decisions:
  - Initialization health now treats backend CSRF/session readiness plus websocket availability as the inspectable auth signal instead of Firebase config presence.
  - VITE_FIREBASE_* remains documented only as optional legacy compatibility until S04 removes the residual Firebase modules/tests/env declarations.
patterns_established:
  - When operational UI copy drifts behind a cutover, add a small focused integration proof for the startup surface instead of relying only on broader auth suites.
observability_surfaces:
  - EnvironmentSetup structured logs: auth_mode, session_auth_status, websocket_status, legacy_firebase_configured
  - ServiceMonitor structured logs: auth_mode, session_auth_status, websocket_status, legacy_firebase_configured
  - frontend-hormonia/tests/integration/initialization/session-auth-operational-surfaces.test.tsx
  - .gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md
duration: 1h15m
verification_result: passed
completed_at: 2026-03-12T12:26:52-03:00
blocker_discovered: false
---

# T05: Update operational auth surfaces and record the S04 Firebase removal map

**Shifted initialization/build surfaces to first-party session auth and documented the remaining Firebase auth residue for S04 cleanup.**

## What Happened

I replaced the stale Firebase-auth-required startup checks in the initialization feature with session-first health signals:

- `EnvironmentSetup.tsx` now checks API reachability, websocket configuration, backend CSRF/session readiness, and session policy configuration.
- `ServiceMonitor.tsx` now reports `Sessão do Backend` and `WebSocket de Sessão` instead of treating Firebase Auth as a required operational service.
- Both initialization surfaces emit structured diagnostics that expose `auth_mode`, session/websocket status, and whether legacy Firebase config is still present, without logging secrets.

I also aligned runtime/build guidance with the completed browser cutover:

- `runtime-config.ts` now marks `VITE_FIREBASE_*` as legacy compatibility knobs and logs session-first runtime diagnostics without exposing values.
- `config-initializer.tsx` now logs first-party session auth readiness instead of claiming Firebase-exclusive auth.
- `.env.example` no longer advertises Firebase browser config as mandatory for staff auth.
- `vite.config.ts` keeps Firebase-related aliases only as explicit legacy test compatibility and stops treating Firebase chunking/prebundling as a normal mandatory path.

Finally, I wrote `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md`, grouping the remaining Firebase residue into:

- delete-immediately runtime modules/tests,
- compat shims/tests to rewrite or tombstone,
- env knobs to delete after module removal,
- type/doc residue requiring follow-up.

To lock the operational cutover behavior, I added `frontend-hormonia/tests/integration/initialization/session-auth-operational-surfaces.test.tsx` covering the new EnvironmentSetup and ServiceMonitor semantics.

## Verification

Passed:

- `cd frontend-hormonia && npx vitest run tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx tests/integration/auth/recovery-and-physician-routes-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `cd backend-hormonia && pytest tests/api/test_websocket_session_auth_contract.py -q`
- `cd frontend-hormonia && npm run build`

Also rechecked:

- `cd frontend-hormonia && npx vitest run tests/integration/config-initialization.test.ts`

## Diagnostics

Future agents can inspect this task through:

- `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx`
  - structured log `Environment auth diagnostics`
  - fields: `auth_mode`, `session_auth_status`, `websocket_status`, `legacy_firebase_configured`
- `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx`
  - structured log `Service auth diagnostics`
  - fields: `auth_mode`, `session_auth_status`, `websocket_status`, `legacy_firebase_configured`
- `frontend-hormonia/tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md`

## Deviations

- Added a focused initialization-surface integration test (`tests/integration/initialization/session-auth-operational-surfaces.test.tsx`) so the operational auth copy/behavior is explicitly proved instead of relying only on the broader slice auth suites.

## Known Issues

- The initialization wizard is not currently exposed through a confirmed app route in the shipped router, so verification for these UI surfaces was performed through targeted integration tests plus final build proof rather than a browser-routed page flow.

## Files Created/Modified

- `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx` — replaced Firebase-auth-required monitoring with session-auth and websocket readiness checks.
- `frontend-hormonia/src/features/initialization/EnvironmentSetup.tsx` — replaced Firebase config checks with session-first environment readiness checks.
- `frontend-hormonia/src/lib/runtime-config.ts` — reclassified Firebase env fields as legacy compatibility and added session-first runtime diagnostics.
- `frontend-hormonia/src/lib/config-initializer.tsx` — updated startup logging to report first-party session auth readiness.
- `frontend-hormonia/.env.example` — removed Firebase-as-required guidance from frontend environment documentation.
- `frontend-hormonia/vite.config.ts` — demoted Firebase-specific aliasing/prebundling to explicit legacy compatibility only.
- `frontend-hormonia/tests/integration/initialization/session-auth-operational-surfaces.test.tsx` — added proof coverage for the updated initialization and service-monitoring surfaces.
- `.gsd/milestones/M002/slices/S03/S03-FIREBASE-AUTH-REMOVAL-MAP.md` — documented the concrete S04 Firebase auth cleanup/removal map.
- `.gsd/DECISIONS.md` — recorded the operational-auth observability and legacy-env guidance decisions.
- `.gsd/milestones/M002/slices/S03/S03-PLAN.md` — marked T05 complete.
