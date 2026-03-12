---
estimated_steps: 4
estimated_files: 5
---

# T02: Replace AuthContext with first-party session login, restore, and logout semantics

**Slice:** S03 — Frontend And Realtime Cutover
**Milestone:** M002

## Description

Move the browser happy path onto the S01 session contract by making the auth API client and `AuthContext` speak directly to the backend login / verify-session / logout endpoints, while preserving existing import stability and the auth-lock/session-restore safeguards the app already depends on.

## Steps

1. Implement first-party `login`, `requestPasswordReset`, and `confirmPasswordReset` methods in `frontend-hormonia/src/lib/api-client/auth.ts`, including `remember_me` payload support and user-safe extraction of backend auth diagnostics.
2. Refactor `frontend-hormonia/src/app/providers/AuthContext.tsx` to keep CSRF bootstrap, auth locking, cookie-first restore, cleanup, and dashboard prefetch, but remove Firebase listeners, Firebase persistence, and Firebase session-bridge logic from the normal login / restore / logout path.
3. Keep `frontend-hormonia/src/contexts/AuthContext.tsx` stable as the compatibility shim, and adapt `frontend-hormonia/src/hooks/useAuth.ts` plus `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx` to session-based state/methods so current callers do not break while the implementation moves.
4. Run the focused frontend auth suite until login, remember-me, session restore, logout, and inspectable error propagation all pass without Firebase happy-path dependencies.

## Must-Haves

- [ ] Login calls the backend-owned email/password route with `remember_me` instead of delegating to Firebase sign-in or `/auth/firebase/verify`.
- [ ] Session restore after refresh relies on `verify-session` / cookie-backed auth, not Firebase auth-state listeners or Firebase persistence.
- [ ] Logout and logout-all clear frontend session state and backend auth tokens without leaving Firebase as a required control path.
- [ ] Backend auth failures stay inspectable in a user-safe way (`error`, `request_id`, or equivalent normalized detail), with no password or session-secret leakage.

## Verification

- `cd frontend-hormonia && npx vitest run tests/integration/auth/session-first-cutover.test.tsx`
- Re-check that the suite does not observe Firebase bridge calls, localStorage-based auth persistence, or token-exchange login on the happy path.

## Observability Impact

- Signals added/changed: Browser auth logs and UI errors become aligned to backend session phases instead of opaque Firebase state transitions.
- How a future agent inspects this: Run the focused auth suite or inspect the login / verify-session network calls and normalized error state in the provider/UI.
- Failure state exposed: Invalid credentials, failed session restore, and logout cleanup regressions surface on explicit login/restore/logout assertions instead of hidden listener timing.

## Inputs

- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` — failing proof that defines the public browser auth contract for this slice.
- `frontend-hormonia/src/app/providers/AuthContext.tsx` / `frontend-hormonia/src/lib/api-client/auth.ts` — the current Firebase-first happy path to replace while preserving import stability.

## Expected Output

- `frontend-hormonia/src/lib/api-client/auth.ts` — first-party auth client methods for login and recovery endpoints.
- `frontend-hormonia/src/app/providers/AuthContext.tsx` — session-first login, restore, and logout provider implementation.
- `frontend-hormonia/src/contexts/AuthContext.tsx` — stable compatibility shim over the refactored provider.
- `frontend-hormonia/src/hooks/useAuth.ts` — derived auth hook aligned to session-based semantics.
- `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx` — thin physician wrapper over the cutover session auth seam.
