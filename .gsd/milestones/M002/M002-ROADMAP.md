# M002: First-Party Authentication Cutover

**Vision:** Replace Firebase Auth for staff access with first-party email/password authentication, keep the proven Redis + HttpOnly session model, migrate existing users through reset/first-access flows, and ship the system in a hard-cut state with no Firebase Auth runtime dependency.

## Success Criteria

- Staff users can log in with email/password through the product’s own auth flow and reach protected dashboard/API surfaces without Firebase token exchange.
- Existing users regain access through reset/first-access email flows instead of manual account recreation.
- Session continuity features such as remember-me, verify-session, logout, and protected-route auth keep working after the provider switch.
- Frontend dashboard and realtime auth no longer depend on Firebase SDK state or Firebase tokens.
- Firebase Auth runtime/config dependencies are removed or tombstoned, and integrated verification proves the assembled auth system works end to end.

## Key Risks / Unknowns

- The current session and user-resolution path is keyed to `firebase_uid` in multiple places — a bad identity-contract migration will break protected routes and WebSocket auth.
- The frontend auth lifecycle still depends on Firebase SDK behavior for login, session restore, and realtime bootstrap.
- Existing users need a recoverable migration path during the hard cut, or staff access will be disrupted.
- Removing Firebase Auth only partially would leave hidden runtime/env coupling and defeat the point of the milestone.

## Proof Strategy

- `firebase_uid`-centric auth/session contract risk → retire in S01 by proving protected routes and session validation work against the new first-party session identity contract.
- Existing-user migration risk → retire in S02 by proving reset/first-access flows for seeded users and admin-created accounts.
- Frontend/realtime Firebase dependence risk → retire in S03 by proving dashboard and médico auth bootstrap work without Firebase SDK tokens.
- Partial-removal/hard-cut risk → retire in S04 by proving runtime boot, cleanup, and end-to-end auth verification pass without Firebase Auth dependency.

## Verification Classes

- Contract verification: focused pytest suites for auth services/dependencies/routes, frontend auth-context tests, and artifact checks for removed Firebase auth paths.
- Integration verification: real backend + Redis session behavior, password-reset token flow, protected API auth, and browser/frontend auth lifecycle.
- Operational verification: app/test bootstrap without Firebase Auth runtime config, plus session restore/logout behavior across normal lifecycle transitions.
- UAT / human verification: smoke-check the login UI, first-access/reset experience, and remember-me behavior in the browser after the code path is live.

## Milestone Definition of Done

This milestone is complete only when all are true:

- All slices are complete and their shipped contracts are verified.
- Backend login, session validation, password recovery, and admin provisioning are wired together under first-party auth.
- Frontend dashboard and médico auth flows use the shipped first-party path rather than Firebase Auth.
- Firebase Auth runtime/config dependencies for staff auth are removed or explicitly tombstoned in the shipped state.
- Success criteria are re-checked against integrated behavior, not just static artifacts.
- Final integrated acceptance scenarios pass.

## Requirement Coverage

- Covers: R005, R006, R007, R008, R009, R010, R011, R012
- Partially covers: none
- Leaves for later: R020, R021, R022, R023
- Orphan risks: none

## Slices

- [ ] **S01: Local Auth Core** `risk:high` `depends:[]`
  > After this: backend staff login, session issuance, verify-session, and protected-route auth work through first-party email/password in focused tests.
- [ ] **S02: Account Recovery And Migration** `risk:high` `depends:[S01]`
  > After this: existing users and newly admin-created users can activate/reset access through secure email-backed first-access flows proved by backend tests.
- [ ] **S03: Frontend And Realtime Cutover** `risk:medium` `depends:[S01,S02]`
  > After this: dashboard and médico login/logout/remember-me/realtime auth run on first-party session semantics without Firebase Auth in the browser path.
- [ ] **S04: Hard Cut Cleanup And Integrated Proof** `risk:medium` `depends:[S02,S03]`
  > After this: Firebase Auth runtime paths are removed or tombstoned, and integrated verification proves login → session restore → protected access → reset → logout end to end.

## Boundary Map

### S01 → S02

Produces:
- `POST /api/v2/auth/login` — first-party email/password login that sets the canonical HttpOnly session cookie and returns normalized user/session metadata.
- `GET /api/v2/auth/verify-session` / `DELETE /api/v2/auth/logout` — stable session validation and logout contract backed by first-party sessions.
- Auth/session identity invariant — Redis session payload and dependency resolvers no longer require Firebase token verification on the happy path.
- Protected-route dependency surface in `auth_dependencies.py` — current-user resolution works from the new session identity contract.

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- Stable auth API contract for frontend consumption: login, verify-session, logout, and normalized user payload shape.
- Session continuity invariant — remember-me and cookie/session restoration remain legal client behavior after login.

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- `POST /api/v2/auth/password/reset-request` — request reset/first-access email.
- `POST /api/v2/auth/password/reset-confirm` — confirm reset with signed token and new password.
- Admin provisioning + activation invariant — admin-created accounts land in a recoverable first-access state compatible with the new frontend auth path.
- Password state transitions — `force_change_password` / `last_password_change` / related migration markers are updated coherently.

Consumes from S01:
- First-party login/session contract.
- New protected-route identity resolution.

### S03 → S04

Produces:
- Frontend auth context contract — `AuthContext` and `MedicoAuthContext` log in, restore session, remember user intent, and log out without Firebase runtime helpers.
- Realtime/bootstrap contract — WebSocket auth uses first-party session-compatible semantics instead of Firebase token dependence.
- Firebase auth removal map — the concrete browser/runtime modules, env variables, and compatibility shims that can now be deleted or tombstoned safely.

Consumes from S01:
- First-party login/session endpoints.

Consumes from S02:
- Password reset / first-access contracts.

### S04 → Milestone Complete

Produces:
- End-to-end auth proof suite covering login, session restore, protected access, reset/first-access, and logout without Firebase Auth.
- Hard-cut shipped state where staff auth no longer depends on Firebase Auth runtime/config.
- Operator-facing diagnostics/tests that make auth failures inspectable during and after the cutover.

Consumes from S01:
- Core login/session contracts.

Consumes from S02:
- Recovery and migration flows.

Consumes from S03:
- Frontend and realtime cutover contracts.
