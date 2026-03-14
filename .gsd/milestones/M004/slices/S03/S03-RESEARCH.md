# M004/S03 — Research

**Date:** 2026-03-14

## Summary

S03 directly owns **R050** and supports **R047** and **R048**. The frontend official runtime is already session-first in one important sense: `AuthProvider` talks to `/api/v2/auth/login`, `/api/v2/auth/verify-session`, and `/api/v2/auth/logout`, and the current focused proof no longer depends on Firebase listeners for the happy path. But the official app still emits legacy transports because the same provider persists `session_id` to localStorage, calls `apiClient.setAuthToken(session_id)` on login/restore, and the shared HTTP/WebSocket helpers still translate that into `Authorization: Bearer <session_id>`, `X-Session-ID`, and websocket `?session_id=` fallback. The guarded frontend residue map confirms the remaining live boundary is concentrated in a small set of shared files, not spread randomly through screens.

The cleanest slice is to cut those transports at the shared seams, not screen by screen. `AuthContext`, `ApiClientCore`, `createAuthApi.fetchSession()`, and the websocket URL builders own the real behavior. There is one route-tree surprise: the shipped router wraps `/admin/*` in `ProtectedRoute` before `AdminApp` runs, so the inner `/admin/login` route is not a public entrypoint in the real app. Current admin integration proof mounts `AdminApp` directly and therefore does not prove the shipped `/admin/*` route tree. That means S03 verification should anchor on the canonical `/login` entrypoint plus `/dashboard` → `/admin`, unless we intentionally re-open `/admin/login` as a public route.

## Recommendation

Take a three-pass frontend cut targeted at **R050**, while advancing **R047** and **R048**:

1. **Transport cut at shared seams**
   - Stop storing/restoring `session_id` in browser localStorage for staff auth.
   - Stop calling `apiClient.setAuthToken(session_id)` from `AuthProvider` and `createAuthApi.login()` / restore flows.
   - Remove header injection from `ApiClientCore.request()`, `ApiClientCore.getSessionHeaders()`, and `createAuthApi.fetchSession()`.
   - Remove websocket `session_id` query fallback from `src/lib/websocket.ts`, `src/hooks/useWebSocket.ts`, and `src/hooks/useMetricsWebSocket.ts`.
   - Keep `credentials: 'include'` and the CSRF flow unchanged.

2. **Narrative cleanup on official auth/admin surfaces**
   - Rewrite Firebase-era comments/logs in `AdminApp.tsx`, `AdminSessionManager.tsx`, `useSessionManagement.ts`, and `init-validator.ts`.
   - Make the session/restore copy describe backend cookies + verify-session, not Firebase auto-refresh.

3. **Type-contract cleanup for official user/admin surfaces**
   - Remove `firebase_uid` / Firebase-auth fields from canonical frontend user/admin types where runtime components do not read them (`src/lib/api-client/normalizers.ts`, `src/lib/api-client/admin.ts`, `src/types/admin.ts`, `shared-types/src/admin.ts`).
   - Treat `src/app/routes/AdminRoutes.lazy.tsx` as non-canonical residue: it contains Firebase-shaped mock admin data but is not the routed ownership path.

Why this order: the auth provider and shared helpers already centralize the official behavior, so one transport cut can collapse most of the live frontend residue without rewriting each page. The route-tree caveat means proof has to exercise the shipped router, not a standalone admin subtree.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Remove legacy auth headers across the official app | `frontend-hormonia/src/lib/api-client/core.ts` + `frontend-hormonia/src/lib/api-client/auth.ts` | These two files own the default fetch path and verify-session fetch; changing them collapses most `Authorization` / `X-Session-ID` emission in one place. |
| Keep login/restore/logout behavior consistent | `frontend-hormonia/src/app/providers/AuthContext.tsx` | `/login`, `/dashboard`, and admin routes already depend on this provider; it is the correct seam for session bootstrap and cleanup. |
| Remove websocket query fallback without losing diagnostics | `frontend-hormonia/src/lib/websocket.ts` + `frontend-hormonia/src/hooks/useWebSocket.ts` + `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` | These files already centralize URL assembly and stable auth error codes like `AUTH_WEBSOCKET_SESSION_INVALID`. |
| Keep admin auth unified | `frontend-hormonia/src/app/routes/AdminRoutes.tsx` + `frontend-hormonia/src/features/admin/AdminProtectedRoute.tsx` | Admin already reuses the shared auth provider. A separate admin auth layer would reintroduce drift. |

## Existing Code and Patterns

- `frontend-hormonia/src/app/providers/AuthContext.tsx` — canonical frontend auth owner. Already session-first on endpoints, but still persists `session_id` to localStorage and rehydrates `apiClient` with a transport token on login/restore.
- `frontend-hormonia/src/lib/api-client/auth.ts` — auth API contract owner. `login()` and `fetchSession()` are the cleanest place to stop setting/sending session headers manually.
- `frontend-hormonia/src/lib/api-client/core.ts` — shared request path. Currently emits both `Authorization: Bearer <session_id>` and `X-Session-ID` whenever `authToken` exists, so one change here affects most official fetch traffic.
- `frontend-hormonia/src/lib/websocket.ts` — official websocket manager. Still appends `?session_id=` when it finds a non-JWT session fallback; stable auth diagnostics are already in place and should be preserved.
- `frontend-hormonia/src/hooks/useWebSocket.ts` — second websocket URL builder. Must be updated with `src/lib/websocket.ts`; otherwise one websocket path can silently keep the fallback alive.
- `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` — metrics websocket path repeats the same session query fallback and will drift if S03 only edits the main websocket hook.
- `frontend-hormonia/src/app/routes/routeDefinitions.tsx` — real router ownership. `/admin/*` is wrapped in `ProtectedRoute` before `AdminApp`, so unauthenticated `/admin/login` never reaches the inner admin route tree.
- `frontend-hormonia/src/app/routes/AdminRoutes.tsx` — admin UI already uses shared `useAuth()` and `login()`. Good pattern to keep.
- `frontend-hormonia/src/features/admin/AdminSessionManager.tsx` — behavior is mostly local state, but copy/comments still describe Firebase token refresh. Low-risk narrative cleanup.
- `frontend-hormonia/src/hooks/auth/useSessionManagement.ts` — pure narrative residue now; it explicitly says restore is delegated to backend cookies + Firebase SDK even though the official provider no longer uses Firebase.
- `frontend-hormonia/src/types/admin.ts`, `frontend-hormonia/shared-types/src/admin.ts`, `frontend-hormonia/src/lib/api-client/admin.ts`, `frontend-hormonia/src/lib/api-client/normalizers.ts` — Firebase fields survive mostly as type/interface baggage. Component-level runtime reads are minimal, so these are likely removable with manageable test/factory churn.
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` — existing assembled-stack proof for `/login` → `/dashboard` on a no-Firebase stack. Good base to extend later, but it does not prove `/admin`.
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` — useful component proof for admin session handling, but it mounts `AdminApp` directly and therefore does not prove the real routed `/admin/*` entrypoint.

## Constraints

- S03 directly owns **R050** and supports **R047** and **R048**. The research should optimize for the official frontend loop, not repo-wide cleanup.
- Backend S02 already canonicalized identity and still accepts `X-Session-ID`, Bearer session IDs, and websocket query fallback. Frontend can stop emitting them without requiring a backend transport cut first.
- The canonical unauthenticated entrypoint in the shipped router is `/login`, not `/admin/login`. If admin-specific public login is desired, that is a route-tree change, not just auth cleanup.
- `ApiClientCore.getSessionHeaders()` is reused outside auth pages (WhatsApp, reports, metrics, initialization surfaces). Any helper change will affect more than `/dashboard` and `/admin`.
- Browser WebSockets cannot send arbitrary auth headers. Cookie-first websocket auth only works if the WS URL lands on an origin that receives the session cookie. The default `window.location.host` path is safest; custom `VITE_WS_BASE_URL` / `VITE_WS_URL` setups need explicit verification.
- `enhanced-analytics.ts` is a separate custom fetch client that reads `localStorage` directly. If it stays untouched, frontend residue counts will stay partially alive even after the main auth provider is cleaned up.

## Common Pitfalls

- **Cleaning only `AuthContext`** — If `createAuthApi.fetchSession()`, `ApiClientCore`, or `enhanced-analytics.ts` keep header injection, the frontend still emits legacy transports even after login/restore look cleaner.
- **Cleaning only the main websocket manager** — `useWebSocket.ts` and `useMetricsWebSocket.ts` both assemble URLs. Leaving one path unchanged preserves `session_id` fallback in runtime.
- **Trusting the current admin integration test as routed proof** — `tests/integration/admin-auth-flow.test.tsx` mounts `AdminApp` directly, so it does not catch the `/admin/*` outer `ProtectedRoute` shadowing.
- **Treating type cleanup as cosmetic** — Firebase fields are mostly type baggage, but they are copied through normalizers and fixtures. Removing them is low runtime risk, not zero churn.
- **Broadening into all e2e helpers immediately** — Many e2e/test helpers still hardcode `X-Session-ID`. That is real cleanup work, but S03 should prioritize runtime seams and focused proof first.

## Open Risks

- Cross-origin websocket or API deployments may still depend on cookie scope/domain behavior that has only been implicitly masked by header/query fallbacks.
- If `enhanced-analytics.ts` stays on localStorage + legacy headers, the frontend residue story will remain partly ambiguous even after `/login`, `/dashboard`, and `/admin` are clean.
- The real routed admin entrypoint may need an explicit decision: shared `/login` remains canonical, or `/admin/login` becomes truly public. The codebase currently says one thing in route definitions and another in component-level admin tests.
- Direct fetch clients that currently rely on `getSessionHeaders()` may need CSRF-aware migration later if they perform state-changing requests outside `ApiClientCore.request()`.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Frontend auth/runtime research | built-in `frontend-design` | installed, but not directly relevant to this slice because the work is auth/session convergence, not UI design |
| React 19 | `vercel-labs/agent-skills@vercel-react-best-practices` | available (207.7K installs) — install with `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |
| Vite 6 | `antfu/skills@vite` | available (9.4K installs) — install with `npx skills add antfu/skills@vite` |
| TanStack Query 5 | `jezweb/claude-skills@tanstack-query` | available (2.5K installs) — install with `npx skills add jezweb/claude-skills@tanstack-query` |

## Sources

- The canonical browser auth flow is already first-party on endpoints, but still persists and reuses `session_id` as a transport token in `AuthProvider`. (source: [frontend-hormonia/src/app/providers/AuthContext.tsx](frontend-hormonia/src/app/providers/AuthContext.tsx))
- Shared HTTP auth emission still lives in the client core and the verify-session fetch path. (source: [frontend-hormonia/src/lib/api-client/core.ts](frontend-hormonia/src/lib/api-client/core.ts), [frontend-hormonia/src/lib/api-client/auth.ts](frontend-hormonia/src/lib/api-client/auth.ts))
- Websocket auth still has explicit `session_id` query fallback in both the manager and hook layers, and the metrics websocket repeats the pattern. (source: [frontend-hormonia/src/lib/websocket.ts](frontend-hormonia/src/lib/websocket.ts), [frontend-hormonia/src/hooks/useWebSocket.ts](frontend-hormonia/src/hooks/useWebSocket.ts), [frontend-hormonia/src/hooks/useMetricsWebSocket.ts](frontend-hormonia/src/hooks/useMetricsWebSocket.ts))
- Firebase narrative residue in official frontend sources is still concentrated in admin/session docs/comments: `AdminApp.tsx`, `AdminSessionManager.tsx`, `useSessionManagement.ts`, `types/admin.ts`, and `init-validator.ts`. (source: [frontend-hormonia/src/AdminApp.tsx](frontend-hormonia/src/AdminApp.tsx), [frontend-hormonia/src/features/admin/AdminSessionManager.tsx](frontend-hormonia/src/features/admin/AdminSessionManager.tsx), [frontend-hormonia/src/hooks/auth/useSessionManagement.ts](frontend-hormonia/src/hooks/auth/useSessionManagement.ts), [frontend-hormonia/src/types/admin.ts](frontend-hormonia/src/types/admin.ts), [frontend-hormonia/src/utils/init-validator.ts](frontend-hormonia/src/utils/init-validator.ts))
- The real routed admin tree protects `/admin/*` before `AdminApp` renders, which makes `/admin/login` a shadowed inner route today. (source: [frontend-hormonia/src/app/routes/routeDefinitions.tsx](frontend-hormonia/src/app/routes/routeDefinitions.tsx), [frontend-hormonia/src/app/routes/AdminRoutes.tsx](frontend-hormonia/src/app/routes/AdminRoutes.tsx))
- The current frontend residue boundary is still live and concentrated in header/query/type/narrative hotspots, but the guard is green on the approved boundary. (source: `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`, `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`)
- Focused frontend proof is green today, but one core unit pack still asserts dual headers and the admin integration pack bypasses the real routed entrypoint. (source: [frontend-hormonia/tests/unit/api-client/auth-headers.test.ts](frontend-hormonia/tests/unit/api-client/auth-headers.test.ts), [frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx](frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx), [frontend-hormonia/tests/integration/admin-auth-flow.test.tsx](frontend-hormonia/tests/integration/admin-auth-flow.test.tsx), [frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts](frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts), local run of `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`)
- Existing no-Firebase browser acceptance already proves `/login` → `/dashboard` on cookies/CSRF without Firebase envs, which is the right base to extend for S03/S06. (source: [frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts](frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts))
