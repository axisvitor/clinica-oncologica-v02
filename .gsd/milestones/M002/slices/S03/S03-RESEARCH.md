# M002/S03 (Frontend And Realtime Cutover) — Research

**Date:** 2026-03-12

## Requirement Focus

**Primary owner**
- **R010** — Frontend and realtime auth no longer depend on Firebase tokens.

**Supporting requirements for this slice**
- **R005** — Frontend login must consume the first-party backend login path.
- **R006** — Browser session restore / remember-me must keep the Redis + HttpOnly session model working.
- **R008** — Admin-managed account flows must remain coherent on the frontend after the auth cutover.
- **R011** — This slice must materially reduce Firebase runtime dependence and leave a concrete hard-cut removal map for S04.
- **R012** — Frontend auth failures should remain inspectable rather than becoming opaque during the cutover.

**Consumed outputs that matter here**
- From **S01**: `POST /api/v2/auth/login`, `GET /api/v2/auth/verify-session`, `DELETE /api/v2/auth/logout`, and canonical authenticated-user access under `/api/v2/users/*` with temporary `/api/v2/auth/*` aliasing.
- From **S02**: `POST /api/v2/auth/password/reset-request` and `POST /api/v2/auth/password/reset-confirm` for real forgot-password / first-access UX.

## Summary

The frontend is already in a **hybrid auth state**, but not the one M002 wants to ship. HTTP auth is mostly **session/cookie-first** today: `AuthContext` restores from `verify-session`, `apiClient.auth.me()` relies on cookies, and logout already hits the backend session endpoints. But the **happy-path login/bootstrap flow is still Firebase-first**: `AuthContext` calls `firebase-auth.ts`, that service signs in through Firebase, obtains a Firebase ID token, then POSTs it to `/api/v2/auth/firebase/verify` to create the backend session. `AuthContext` also keeps Firebase auth-state listeners, Firebase token refresh logic, and a Firebase-derived `websocketToken` in state.

Realtime is the second large remaining dependency. The browser `wsManager` only authenticates with a `token=` query param and is written around JWT expiry/refresh behavior. The backend websocket endpoint does accept `session_id`, but its session-auth branch still dereferences `firebase_uid` out of the session payload and user cache, which conflicts with S01’s canonical `user_id` session identity contract. So the frontend cannot fully cut over realtime by itself; S03 likely needs a narrow backend alignment on websocket session auth as part of the same slice.

There is also important surface drift around doctor login and recovery UX. The routed app uses the generic auth/provider flow with `/physician/*`, while a separate `MedicoLogin` / `MedicoRoutes` stack still expects numeric CRM input and comments about Firebase mapping that does not exist. Meanwhile `LoginPage` still renders a support-email placeholder for “Esqueci minha senha” instead of consuming S02’s reset-request / reset-confirm API. S03 should treat these as cutover work, not polish: if the browser path still points users to Firebase-era or manual-recovery behavior, the milestone is not actually integrated.

## Recommendation

Take a **session-first cutover** and make `AuthContext` the canonical seam.

1. **Replace the Firebase login bridge with direct first-party auth calls.**
   - Implement `apiClient.auth.login()` against `POST /api/v2/auth/login`.
   - Pass **email + password + `remember_me`** from the UI.
   - Keep using `verify-session`, `me`, `logout`, and `logout-all` from the backend session contract.
   - Preserve the shim at `src/contexts/AuthContext.tsx` so existing imports do not explode while implementation moves.

2. **Simplify `AuthContext` to backend session semantics only.**
   - Keep the good parts already present: CSRF bootstrap, auth lock, cookie-first restore, dashboard prefetch, and structured cleanup.
   - Remove Firebase auth listeners, Firebase token refresh, `getFirebaseToken`, and Firebase persistence as control points for normal auth.
   - Re-define remember-me in terms of backend session TTL / cookie policy, not Firebase local-vs-session persistence.

3. **Collapse realtime bootstrap onto session semantics.**
   - Reuse the existing websocket manager and subscription protocol instead of adding another client.
   - Change auth bootstrap from `token=<firebase_jwt>` to a first-party session-compatible mechanism.
   - The fastest path appears to be reusing the backend’s existing `session_id` support, but that is only safe if the backend session-auth branch is updated off `firebase_uid` and the team explicitly accepts any remaining JS-readable session-id tradeoff.
   - If the product wants a stricter hard cut, prefer teaching the websocket endpoint to authenticate from the existing session cookie during handshake and treat `session_id` as temporary compatibility only.

4. **Choose one canonical doctor login surface.**
   - M002 standardizes login on **email only**.
   - The routed application already centers `/login` and `/physician/*`; keep that as canonical unless product requirements prove `/medico/*` is still live.
   - Do not preserve CRM-based doctor login behavior as part of this cutover.

5. **Wire recovery UX now, not later in cleanup.**
   - Replace the support-email placeholder in `LoginPage` with a real reset-request flow and a reset-confirm page/route using S02 APIs.
   - That keeps the integrated browser path aligned with the milestone promise that existing users recover access through reset / first-access flows.

6. **After the provider cutover, remove or tombstone Firebase build/runtime/test residue.**
   - Update service checks, tests, env docs, and Vite chunking so the repo stops assuming Firebase is a required frontend runtime.
   - That removal map is a direct S03 output needed by S04.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Session restore after refresh | `apiClient.auth.checkAuth()` / `verify-session` flow already used by `AuthContext` | Reuses the shipped S01 contract instead of inventing a second browser-side restore mechanism. |
| Auth lifecycle concurrency | `createAuthLock()` in `AuthContext` | Prevents login/restore races that the current provider already guards against. |
| Backend session continuity | Existing Redis + HttpOnly session endpoints from S01 (`login`, `verify-session`, `logout`) | The milestone explicitly preserves this architecture; do not invent JWT-only browser auth. |
| WebSocket room/reconnect behavior | `src/lib/websocket.ts` manager and room subscription protocol | The auth bootstrap needs to change, but the reconnect/subscription machinery is already there. |
| Password recovery / first access | S02 backend routes: `reset-request` and `reset-confirm` | These are the canonical migration path; do not keep the support-email placeholder or Firebase reset helpers. |
| Auth import stability in tests/app code | `src/contexts/AuthContext.tsx` shim over `src/app/providers/AuthContext.tsx` | Lets implementation change without breaking import paths across the app/tests. |

## Existing Code and Patterns

- `frontend-hormonia/src/app/providers/AuthContext.tsx` — **main cutover seam**. Reuse its auth lock, CSRF bootstrap, cookie-first restore, cleanup, and dashboard prefetch. Remove its Firebase listeners, Firebase token state, and Firebase-driven login/bootstrap behavior.
- `frontend-hormonia/src/contexts/AuthContext.tsx` — compatibility shim. Keep this stable while refactoring the provider implementation.
- `frontend-hormonia/src/lib/api-client/auth.ts` — already centralizes `verify-session`, `logout`, `logout-all`, `me`, and auth-header/session helpers. Extend this module for local auth; stop routing login through `/api/v2/auth/firebase/verify`.
- `frontend-hormonia/src/services/firebase-auth.ts` — useful as a map of current side effects (session storage, cleanup, token refresh), but it is fundamentally the old happy path and should not survive as the canonical auth service.
- `frontend-hormonia/src/lib/websocket.ts` — keep room subscription and reconnect logic; swap its auth bootstrap away from Firebase JWTs.
- `backend-hormonia/app/api/websockets.py` — already has a session-auth branch, but it still reads `firebase_uid` out of `session_data`; that must align with the S01 user-id-centric contract.
- `frontend-hormonia/src/pages/LoginPage.tsx` — good baseline UX for login form, remember-me checkbox, errors, and accessibility. The forgot-password action is still a placeholder and must be replaced.
- `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx` — currently just delegates to generic `login()`. Fine as a thin wrapper only if it stays email-based and role-aware.
- `frontend-hormonia/src/pages/medico/MedicoLogin.tsx` — drifted surface that still validates numeric CRM and comments about Firebase mapping. Avoid building new behavior on top of this assumption.
- `frontend-hormonia/src/app/routes/routeDefinitions.tsx` — shows the canonical routed physician surface is `/physician/*`, not the standalone `/medico/*` stack.
- `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx` — still treats Firebase auth as a required service and dynamically imports Firebase validation. This will produce misleading failures after the cutover unless updated.
- `frontend-hormonia/src/hooks/usePasswordChange.ts` — still uses Firebase re-authentication. This is a Firebase-era path to retire in favor of backend-owned password/change-reset flows.
- `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` — still requests a Firebase token and connects to a Firebase-tokenized websocket URL. Likely stale, but it is still a reintroduction risk.
- `frontend-hormonia/package.json`, `frontend-hormonia/.env.example`, `frontend-hormonia/vite.config.ts` — Firebase package/env/build-chunk residue that must be removed or explicitly tombstoned after the browser path is cut over.
- `frontend-hormonia/tests/auth/firebase-auth-comprehensive.test.tsx`, `frontend-hormonia/tests/components/auth/AuthContext.test.tsx`, `frontend-hormonia/tests/integration/auth-flow-comprehensive.test.tsx` — expected verification fallout zone. Several suites are explicitly Firebase-named or still assert `/auth/firebase/verify`.

## Constraints

- **Email-only login is the milestone contract.** Do not preserve CRM-only or dual email+CRM login as part of M002.
- **Preserve the Redis + HttpOnly session architecture.** S03 must consume the existing session contract, not replace it with pure JWT auth.
- **Remember-me must align to backend session semantics.** The backend already has `remember_me` support; the frontend should stop treating Firebase persistence as the source of truth.
- **No long-lived hybrid mode.** Temporary compatibility may exist during execution, but the shipped browser/realtime path cannot still require Firebase SDK state.
- **Profile/authenticated-user access should target the S01 canonical contract.** `/api/v2/users/*` is canonical; `/api/v2/auth/*` aliases are temporary compatibility only.
- **Realtime auth must work without Firebase tokens in the browser path.** If that requires a small websocket-backend change, it belongs in this slice’s implementation plan.
- **Frontend recovery UX must consume S02 APIs.** A manual support-email workaround does not satisfy the integrated milestone promise.

## Common Pitfalls

- **Keeping remember-me tied to Firebase persistence** — today the checkbox controls `firebaseAuthLazy.setPersistence()` instead of the first-party login payload. Pass `remember_me` to backend login and treat any JS-side session-id storage as a compatibility detail, not the definition of session continuity.
- **Refactoring the provider but forgetting realtime bootstrap** — HTTP may look green while websockets still require a Firebase JWT. Cut over `wsManager` and any alternate websocket hooks in the same slice.
- **Assuming `/medico/*` is the canonical doctor surface** — the routed app currently uses `/physician/*`. Verify whether `/medico/*` has real callers before investing in its CRM-based behavior.
- **Leaving recovery UX as a placeholder** — `LoginPage` still shows a support-email alert. That will strand migrated users even if S02 backend endpoints already work.
- **Updating runtime code but not test/build residue** — Firebase-named tests, ServiceMonitor checks, Vite chunks, env docs, and optional hooks can keep failing after the main cutover unless they are updated deliberately.
- **Using the backend websocket session path as-is** — it still depends on `firebase_uid`. If the frontend switches to `session_id` without backend alignment, realtime auth can fail silently.

## Open Risks

- **Backend websocket auth is not fully on the S01 identity contract yet.** The `session_id` branch in `app/api/websockets.py` still reads `firebase_uid` from session data and cache.
- **There may be hidden consumers of `/medico/*`.** Route definitions suggest the canonical surface is `/physician/*`, but standalone `MedicoRoutes` and related tests still exist.
- **The current frontend exposes `session_id` to JavaScript/localStorage for websocket compatibility.** Reusing that approach for S03 is likely the fastest cutover, but it is not as clean as cookie-only websocket auth and should be treated as an explicit tradeoff.
- **Password reset integration may require new pages/routes, not just a button change.** The current login page has no reset-request or reset-confirm UX.
- **Test fallout is guaranteed.** Several suites still encode Firebase assumptions or hardcode `/api/v2/auth/firebase/verify`.
- **Initialization/operational UX still reports Firebase as a required service.** If not updated, operators may see false degraded/unhealthy states after a successful cutover.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Frontend UI / route-level UX cleanup | `frontend-design` | available locally (installed), but tangential to the core auth/realtime cutover |
| React auth / secrets workflows | `incept5/eve-skillpacks@eve-auth-and-secrets` | not installed; promising if extra auth workflow guidance is wanted (`npx skills add incept5/eve-skillpacks@eve-auth-and-secrets`) |
| Firebase auth decommissioning context | `firebase/agent-skills@firebase-auth-basics` | not installed; promising for legacy Firebase-path cleanup (`npx skills add firebase/agent-skills@firebase-auth-basics`) |
| Vite build cleanup | `antfu/skills@vite` | not installed; promising for post-cutover bundler/env cleanup (`npx skills add antfu/skills@vite`) |

## Sources

- Hybrid browser auth is still Firebase-first on login/bootstrap but session-first on verify/me/logout (source: `frontend-hormonia/src/app/providers/AuthContext.tsx`, `frontend-hormonia/src/services/firebase-auth.ts`, `frontend-hormonia/src/lib/api-client/auth.ts`)
- WebSocket auth still expects `token=` in the browser and backend session auth still dereferences `firebase_uid` (source: `frontend-hormonia/src/lib/websocket.ts`, `backend-hormonia/app/api/websockets.py`)
- Login UI still ships a manual support-email placeholder instead of reset-request / reset-confirm UX (source: `frontend-hormonia/src/pages/LoginPage.tsx`)
- Doctor surface drift: routed physician pages are canonical while `MedicoLogin` still assumes CRM/Firebase behavior (source: `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx`, `frontend-hormonia/src/pages/medico/MedicoLogin.tsx`, `frontend-hormonia/src/app/routes/routeDefinitions.tsx`, `rg -n "MedicoRoutes|/medico/dashboard|ROUTES\.MEDICO|medico/login" frontend-hormonia/src`)
- Firebase runtime/build residue still exists in dependency list, env docs, bundle config, service monitor, and tests (source: `frontend-hormonia/package.json`, `frontend-hormonia/.env.example`, `frontend-hormonia/vite.config.ts`, `frontend-hormonia/src/features/initialization/ServiceMonitor.tsx`, `rg -n "AuthContext|firebase-auth|usePasswordChange|MedicoLogin|websocket|verify-session|requestPasswordReset|firebase/verify" frontend-hormonia/src frontend-hormonia/tests`)
- Backend already supports remember-me, while the current frontend still drives persistence through Firebase behavior instead of the first-party login contract (source: `rg -n "remember.?me|rememberMe|remember_me" backend-hormonia/app frontend-hormonia/src`)
- Skill discovery suggestions were gathered via `npx skills find "react authentication"`, `npx skills find "firebase auth"`, and `npx skills find "vite"`
