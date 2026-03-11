# M002: First-Party Authentication Cutover — Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

## Project Description

Replace Firebase Auth for staff login with first-party authentication owned by the backend, while preserving the existing Redis + HttpOnly session architecture that already protects the rest of the API. The target users are admins and doctors using the internal dashboard and related protected surfaces.

## Why This Milestone

The current authentication path is hybrid and fragile: the frontend signs in through Firebase, the backend validates a Firebase token, and only then creates a Redis session. That chain has become a repeated source of authentication pain. The codebase already has local-password primitives (`hashed_password`, password hashing helpers, reset-token helpers, admin reset flows, session infrastructure), so the project is paying Firebase complexity without needing Firebase as the long-term staff identity provider.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Log into the dashboard with email and password using the product’s own authentication flow.
- Recover access through a first-access / reset-email flow without depending on Firebase.
- Stay signed in with remember-me behavior and continue using protected pages after the hard cut.

### Entry point / environment

- Entry point: `/login`, `/medico/login`, protected API routes under `/api/v2/auth/*`, and authenticated WebSocket bootstrap.
- Environment: browser + backend API + Redis + PostgreSQL + SMTP/email in local-dev and production-like environments.
- Live dependencies involved: database, Redis session store, email delivery, WebSocket auth, frontend dashboard.

## Completion Class

- Contract complete means: auth endpoints, session payload contracts, reset-token flows, and frontend auth contracts are covered by tests and artifact checks.
- Integration complete means: browser login, session validation, protected API access, password reset, and logout work together without Firebase Auth in the loop.
- Operational complete means: the app can boot and execute staff auth flows without Firebase Auth credentials/config, and remember-me/session restore behavior survives normal lifecycle events.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- A staff user can log in with email/password, land on protected UI/API surfaces, and keep using the system via first-party session auth.
- An existing seeded user can complete the reset/first-access flow by email token and then log in successfully.
- The runtime no longer requires Firebase Auth client/admin credentials or SDK code paths for staff authentication.

## Risks and Unknowns

- Current auth/session state is keyed heavily by `firebase_uid` across session resolution, cache lookups, and websocket auth — if this identity contract is not migrated cleanly, protected routes will break.
- The frontend auth lifecycle still depends on Firebase SDK state and token refresh behavior — removing backend Firebase alone is not sufficient.
- Hard cut means compatibility shims and env assumptions must be retired without stranding real users or breaking bootstrap.
- Password reset email flow must be secure, rate limited, and operationally observable, or the migration path will become the next source of support pain.

## Existing Codebase / Prior Art

- `backend-hormonia/app/api/v2/routers/auth.py` — current Firebase verification, verify-session, logout, and password-change routes.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — canonical auth dependency surface with session auth primary and Firebase fallback.
- `backend-hormonia/app/routers/auth_session.py` — legacy session routes and header/cookie compatibility behavior.
- `backend-hormonia/app/models/user.py` — local password fields and auth-provider fields already exist.
- `backend-hormonia/app/core/security.py` — signed password reset token helpers.
- `frontend-hormonia/src/app/providers/AuthContext.tsx` — current dashboard auth lifecycle, remember-me behavior, and WebSocket bootstrap.
- `frontend-hormonia/src/services/firebase-auth.ts` — current Firebase login bridge that still owns the happy path.
- `frontend-hormonia/src/lib/api-client/auth.ts` — current auth client where local auth methods are still unsupported.
- `docs/compatibility/backward-compatibility-inventory.md` — auth/session shims and sunset targets that M002 will likely reduce or remove.

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R005 — replaces Firebase Auth with first-party staff login.
- R006 — preserves Redis/cookie session continuity instead of redesigning auth transport.
- R007 — provides existing-user migration via reset/first-access instead of manual recreation.
- R008 — keeps account creation admin-driven.
- R009 — adds/finishes self-service reset-by-email.
- R010 — removes Firebase token dependence from frontend and realtime auth.
- R011 — enforces a hard cut, not a prolonged hybrid mode.
- R012 — makes auth failures and migration outcomes inspectable.

## Scope

### In Scope

- Backend-owned email/password login for staff.
- Redis + HttpOnly session issuance/validation using first-party auth.
- Existing-user reset / first-access migration flow.
- Admin-created account lifecycle tied to first-party auth.
- Frontend dashboard and médico login cutover away from Firebase auth runtime.
- Auth-related compatibility cleanup, verification, and observability needed to support the cutover.

### Out of Scope / Non-Goals

- Public self-signup.
- CRM-only or dual email+CRM login.
- MFA or enterprise SSO/OIDC.
- Patient/quiz auth redesign beyond incidental compatibility considerations.
- Long-lived Firebase/local auth coexistence after the shipped milestone.

## Technical Constraints

- Preserve the current Redis + HttpOnly session architecture; do not switch M002 to a pure JWT-only auth model.
- API routes stay on AsyncSession; worker flows stay on sync Session.
- Maintain existing security posture: CSRF, rate limiting, password hashing, and audit-friendly behavior should not regress.
- The shipped state must not require Firebase Auth runtime credentials for staff authentication.
- Login identifier is email only.

## Integration Points

- PostgreSQL `users` table — local password/auth-provider state and migration markers live here.
- Redis session cache — existing session storage and verification path must keep working under the new auth subject contract.
- Frontend dashboard auth context — login, logout, remember-me, and session restore must cut over cleanly.
- WebSocket auth bootstrap — currently mixes session ID and Firebase token behavior; M002 must align it with first-party auth.
- SMTP / email services — required for reset/first-access delivery.
- Admin user management routes/services — account creation and reset flows must remain coherent after the cutover.

## Open Questions

- Should the canonical session principal become `user_id` or a generalized `auth_subject` instead of `firebase_uid`? — Planning must resolve this early because many cache and auth helpers assume `firebase_uid` today.
- Which header-based session compatibility shims (`X-Session-ID`, `Authorization`) remain after the cutover? — Current thinking: keep only what is still necessary for real clients like WebSocket/bootstrap, then retire the rest in the final hard-cut slice.
