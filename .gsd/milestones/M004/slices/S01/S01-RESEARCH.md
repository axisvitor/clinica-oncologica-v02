# M004/S01 — Research

**Date:** 2026-03-13

## Summary

S01 does not directly own or support an Active requirement in `.gsd/REQUIREMENTS.md`; it is an enabling slice for `R047`, `R048`, `R049`, and `R050`. The real job here is to make runtime residue visible and replayable before S02–S05 start cutting it. Current shipped residue is real, not hypothetical: root `/session/*` is still mounted, canonical `/api/v2/auth/*` still writes `firebase_uid` into session cache metadata and still accepts `X-Session-ID` / `Authorization: Bearer <session_id>`, the official frontend client still emits both header forms and restores `session_id` from localStorage, and websocket auth still accepts a `session_id` query fallback on both client and server.

A repo-wide “ban firebase” guard would be the wrong tool. There are legitimate out-of-scope Firebase/schema leftovers, third-party `/session/*` strings under WuzAPI, and multiple live auth helper families with conflicting source precedence. The slice should instead produce a scoped verifier that reports exactly which official runtime surfaces still carry: `firebase_uid`, root legacy `/session/*`, `X-Session-ID`, Bearer-as-session fallback, websocket `session_id` query fallback, and Firebase operational narrative/comments in shipped files.

Primary recommendation: create a new M004 guardrail script under `.gsd/milestones/M004/slices/S01/` with both `--report` and `--check` modes, reusing the shape of M002’s scoped residue scanner and M003’s machine-readable verifier. `--report` should print the current allowed residue map; `--check` should fail when new references appear outside the approved surface list or when existing hotspots move without the research boundary being updated. That gives S02–S05 a hard boundary for `R047`–`R050` without pretending those requirements are already satisfied.

## Recommendation

Take a two-layer verifier approach.

1. **Runtime residue inventory (`--report`)**
   - Emit one section each for:
     - `firebase_uid` runtime dependence
     - root legacy `/session/*`
     - `X-Session-ID` emission/acceptance
     - `Authorization: Bearer <session_id>` acceptance/emission
     - websocket `session_id` query fallback
     - Firebase operational narrative in shipped runtime files
   - For each section, list current live files and counts, not just pass/fail.
   - Keep scope to `backend-hormonia/app`, `frontend-hormonia/src`, and the slice-local verifier/artifacts. Do **not** scan repo-wide docs/tests/models by default.

2. **Guardrail enforcement (`--check`)**
   - Fail when:
     - a new runtime file starts emitting or accepting `X-Session-ID`
     - a new runtime file starts using session-as-Bearer fallback
     - a new runtime file reintroduces Firebase narrative/comments in official auth/session surfaces
     - `firebase_uid` appears in new runtime-auth/session/cache helpers outside the approved residual set
     - root `/session/*` grows or stays ambiguous instead of remaining an explicit compat island
   - Allow a small explicit allowlist for surfaces already known to be live in M004/S01.

3. **Use separate allowlists, not one giant grep**
   - `firebase_uid` allowlist: cache/session helpers, compat admin DTOs, legacy islands explicitly left for M004/S02–S05 or M005.
   - `/session/*` allowlist: root legacy auth router only; explicitly exclude WuzAPI `/session/*` and quiz session routes from auth cleanup failures.
   - header/bearer allowlist: current frontend auth client, current backend resolver families, websocket handshake.
   - narrative allowlist: ideally empty for shipped auth/session files; failures here are useful early wins.

4. **Treat resolver drift as a first-class problem**
   - There are multiple live session resolvers with different precedence rules. The verifier should track all of them explicitly, because cutting only one leaves ambiguity alive.
   - Current live resolver families:
     - `backend-hormonia/app/dependencies/auth_session_contract.py`
     - `backend-hormonia/app/api/v2/auth_session_shared.py`
     - `backend-hormonia/app/api/v2/routers/auth.py::_get_session_id_from_request()`

5. **Define the official-runtime boundary up front**
   - **In scope for S01 guardrails**
     - `backend-hormonia/app/core/router_registry.py`
     - `backend-hormonia/app/routers/auth_session.py`
     - `backend-hormonia/app/dependencies/auth_*`
     - `backend-hormonia/app/api/v2/auth_session_shared.py`
     - `backend-hormonia/app/api/websockets.py`
     - `backend-hormonia/app/core/redis_manager/session_cache.py`
     - current frontend auth/api/websocket sources under `frontend-hormonia/src`
   - **Out of scope for this slice’s failure surface**
     - schema/model residue intended for M005
     - historical docs/test artifacts unless they are the official proof harness
     - vendor/session strings unrelated to staff auth (for example WuzAPI)

Why this approach: it matches what S01 promises in the roadmap — an executable map of live runtime residue — without pretending the runtime is already canonical. It also sets up S02–S05 to remove residue one category at a time while keeping reintroduction visible.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Scoped residue scanning for auth cleanup | `.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh` | Already proved the value of targeted `rg` checks with explicit hotspot allowlists instead of noisy repo-wide bans. |
| Machine-readable report/check verifier shape | `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` | Already implements the right ergonomics for `--report` vs `--check`, anchored metrics, and drift notes. |
| Canonical no-Firebase auth proof | `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` | Proves the first-party login/verify/reset/logout flows on canonical `user_id` sessions and shows where Firebase-based fallback is no longer needed on the happy path. |
| Legacy `/session/*` compatibility proof | `backend-hormonia/tests/auth/test_session_validation.py` | Pins the retained compat island semantics (`200 + valid:false`, header-based validation/logout) so S01 can distinguish intentional residue from accidental reintroduction. |
| Frontend hard-cut contract proof | `frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx` | Already guards the public auth API against `createSession`/`getFirebaseToken` reintroduction and proves password change uses the first-party endpoint. |

## Existing Code and Patterns

- `backend-hormonia/app/core/router_registry.py` — authoritative live-app truth: both the root legacy `/session` router and `/ws` websocket routes are still mounted.
- `backend-hormonia/app/routers/auth_session.py` — real compatibility island, not dead code. `validate` / `logout` use cookie + `X-Session-ID`; `logout-all` / `active` still use Firebase Bearer verification; top-level docstring still tells the Firebase-era story.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical `/api/v2/auth/*` contract; still writes `firebase_uid` into session cache metadata, still extracts session IDs from cookie / `X-Session-ID` / `Authorization: Bearer`.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — session-first façade with a live legacy bearer fallback when no cookie/header session is present.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — one live session resolver family; precedence is setting-driven and not identical to the shared V2 helper.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — second resolver family; hard-codes `Bearer -> X-Session-ID -> cookie -> query_session_id`, which matters for websocket and helper drift.
- `backend-hormonia/app/core/redis_manager/session_cache.py` — still stores `firebase_uid` in session payloads and matches global invalidation by either canonical `user_id` or compatibility `firebase_uid`.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — still reads/writes cached user data by both `id` and `firebase_uid`; this is one of the key runtime pivot points for `R049` risk.
- `backend-hormonia/app/api/websockets.py` — websocket handshake still accepts `session_id` from query string as a live fallback in addition to cookie/header sources.
- `backend-hormonia/app/api/v2/templates_shared.py` — representative V2 helper still accepts `Authorization`, `X-Session-ID`, and cookie session sources; useful model for how far header fallback has spread beyond auth routes.
- `backend-hormonia/app/api/v2/patients_shared_helpers.py` and `backend-hormonia/app/api/v2/patients_utils.py` — older helper family still resolves session -> `firebase_uid` -> user, so S01 cannot assume the canonical helpers are the only live dependency path.
- `frontend-hormonia/src/lib/api-client/core.ts` — official frontend runtime still emits both `Authorization: Bearer <session_id>` and `X-Session-ID` when an auth token is present.
- `frontend-hormonia/src/lib/api-client/auth.ts` — verify-session client still sends both header forms, and the public auth client still treats `session_id` as the core browser-held token.
- `frontend-hormonia/src/app/providers/AuthContext.tsx` — official app persists `session_id` in localStorage, restores it on startup, and configures the API client with that token before cookie-only verification runs.
- `frontend-hormonia/src/lib/websocket.ts` and `frontend-hormonia/src/hooks/useWebSocket.ts` — current frontend websocket path still appends `session_id` query fallback when a session-style token is present.
- `frontend-hormonia/src/hooks/auth/useSessionManagement.ts` — no live Firebase code, but still contains Firebase-auth operational comments that tell the wrong runtime story.
- `frontend-hormonia/src/features/admin/AdminSessionManager.tsx` — another shipped Firebase-narrative surface; describes session extension/refresh as Firebase-managed.
- `frontend-hormonia/src/AdminApp.tsx` — shipped comment block still says `AuthProvider (Firebase authentication)`.
- `frontend-hormonia/src/utils/init-validator.ts` — current init validator still hardcodes `authentication: true` with a Firebase-era comment.
- `frontend-hormonia/src/types/admin.ts` and `frontend-hormonia/shared-types/src/admin.ts` — official frontend/admin type surfaces still expose Firebase-specific fields and enums.

## Constraints

- S01 is an **enabling** slice for `R047`, `R048`, `R049`, and `R050`; it does not validate them by itself. Its job is to make their runtime residue visible and guardable.
- A repo-wide `firebase` or `/session/` ban will be wrong. The repo still contains legitimate schema/model residue, WuzAPI `/session/*` strings, and quiz/public session routes that are not the same as staff-auth runtime residue.
- There is **no single source of truth** for session ID precedence today. Multiple live resolver families disagree on cookie/header/Bearer/query ordering.
- The official frontend runtime still emits `X-Session-ID` and `Authorization: Bearer <session_id>`; S01 cannot treat these as test-only residue.
- Websocket query fallback is live on **both** client and server. Any future cut has to land on both sides together.
- Root legacy `/session/*` is mixed: `validate`/`logout` are session-based, while `logout-all`/`active` still depend on Firebase bearer verification.
- Many `firebase_uid` occurrences are not equal in importance. S01 should isolate **runtime-auth/session/cache** dependence from broader schema/audit leftovers intended for M005.

## Common Pitfalls

- **Using a single repo-wide grep as the guardrail** — this will drown in false positives from models, docs, tests, WuzAPI, and other out-of-scope session strings. Keep the verifier scoped to the official runtime boundary.
- **Treating `X-Session-ID` and Bearer-as-session as stale tests only** — the shipped frontend client still emits both, and backend helpers still accept them.
- **Guarding only `auth.py` and missing the spread helpers** — `templates_shared.py`, `tasks/dependencies.py`, `localization.py`, patient helpers, and websocket handshake code still participate in the live session contract.
- **Cutting websocket query fallback on only one side** — the browser still appends `session_id` query params, and the backend still accepts them.
- **Ignoring narrative residue because the code path works** — S01 explicitly promises guardrails for Firebase narrative/semantics too. Wrong comments/logs in shipped auth/session files are part of the runtime ambiguity.

## Open Risks

- **Resolver drift may survive unnoticed** — because multiple resolver families exist, one path can become canonical while another quietly keeps accepting header/query/bearer residue.
- **Frontend contract cleanup may lag behind runtime cleanup** — even if the auth happy path works, admin/shared types and runtime comments can keep the official contract narratively tied to Firebase.
- **`firebase_uid` is still a real runtime pivot in cache/session helpers** — cutting the obvious router code without addressing cache hydration and invalidation paths will leave `R049` half-open.
- **Legacy `/session/*` has deeper live behavior than expected** — `logout-all` and `active` are still Firebase-bearer-based, so S04 will be more than a simple header rejection pass.
- **Secondary clients may be overlooked** — `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts` still emits both `Authorization` and `X-Session-ID`, so guardrails that only inspect the main auth client will miss reintroduction paths.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — `npx skills add wshobson/agents@fastapi-templates` |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available — `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |
| Playwright | `currents-dev/playwright-best-practices-skill@playwright-best-practices` | available — `npx skills add currents-dev/playwright-best-practices-skill@playwright-best-practices` |

## Sources

- Live router mount truth: root legacy `/session` and `/ws` are still part of the shipped app (source: [`backend-hormonia/app/core/router_registry.py`](backend-hormonia/app/core/router_registry.py))
- Root legacy router is still a real compat island and still carries Firebase narrative plus mixed auth behavior (`validate/logout` vs `logout-all/active`) (source: [`backend-hormonia/app/routers/auth_session.py`](backend-hormonia/app/routers/auth_session.py))
- Canonical auth still writes `firebase_uid` into session cache metadata and still accepts cookie / `X-Session-ID` / Bearer extraction (source: [`backend-hormonia/app/api/v2/routers/auth.py`](backend-hormonia/app/api/v2/routers/auth.py))
- Session-first façade still keeps a legacy bearer fallback, and session resolution is split across multiple helper families (source: [`backend-hormonia/app/dependencies/auth_dependencies.py`](backend-hormonia/app/dependencies/auth_dependencies.py), [`backend-hormonia/app/dependencies/auth_session_contract.py`](backend-hormonia/app/dependencies/auth_session_contract.py), [`backend-hormonia/app/api/v2/auth_session_shared.py`](backend-hormonia/app/api/v2/auth_session_shared.py))
- Cache/session helpers still use `firebase_uid` as a live compatibility key for hydration, caching, and invalidation (source: [`backend-hormonia/app/core/redis_manager/session_cache.py`](backend-hormonia/app/core/redis_manager/session_cache.py), [`backend-hormonia/app/api/v2/user_cache_shared.py`](backend-hormonia/app/api/v2/user_cache_shared.py))
- Older V2 helpers still resolve authenticated users through `firebase_uid`, so canonical auth helpers are not the only live path (source: [`backend-hormonia/app/api/v2/patients_shared_helpers.py`](backend-hormonia/app/api/v2/patients_shared_helpers.py), [`backend-hormonia/app/api/v2/patients_utils.py`](backend-hormonia/app/api/v2/patients_utils.py), [`backend-hormonia/app/api/v2/templates_shared.py`](backend-hormonia/app/api/v2/templates_shared.py))
- Websocket auth still accepts query-string session fallback on the backend and still emits it on the frontend (source: [`backend-hormonia/app/api/websockets.py`](backend-hormonia/app/api/websockets.py), [`frontend-hormonia/src/lib/websocket.ts`](frontend-hormonia/src/lib/websocket.ts), [`frontend-hormonia/src/hooks/useWebSocket.ts`](frontend-hormonia/src/hooks/useWebSocket.ts))
- Official frontend auth runtime still stores `session_id`, restores it on boot, and emits both `Authorization` and `X-Session-ID` (source: [`frontend-hormonia/src/app/providers/AuthContext.tsx`](frontend-hormonia/src/app/providers/AuthContext.tsx), [`frontend-hormonia/src/lib/api-client/core.ts`](frontend-hormonia/src/lib/api-client/core.ts), [`frontend-hormonia/src/lib/api-client/auth.ts`](frontend-hormonia/src/lib/api-client/auth.ts), [`frontend-hormonia/src/lib/api-client/enhanced-analytics.ts`](frontend-hormonia/src/lib/api-client/enhanced-analytics.ts))
- Shipped frontend narrative/type surfaces still carry Firebase semantics even where runtime logic no longer depends on it (source: [`frontend-hormonia/src/AdminApp.tsx`](frontend-hormonia/src/AdminApp.tsx), [`frontend-hormonia/src/hooks/auth/useSessionManagement.ts`](frontend-hormonia/src/hooks/auth/useSessionManagement.ts), [`frontend-hormonia/src/features/admin/AdminSessionManager.tsx`](frontend-hormonia/src/features/admin/AdminSessionManager.tsx), [`frontend-hormonia/src/utils/init-validator.ts`](frontend-hormonia/src/utils/init-validator.ts), [`frontend-hormonia/src/types/admin.ts`](frontend-hormonia/src/types/admin.ts), [`frontend-hormonia/shared-types/src/admin.ts`](frontend-hormonia/shared-types/src/admin.ts))
- Reusable verifier and proof patterns already exist and should be adapted rather than reinvented (source: [`.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh`](.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh), [`.gsd/milestones/M003/slices/S01/verify-evidence-map.sh`](.gsd/milestones/M003/slices/S01/verify-evidence-map.sh), [`backend-hormonia/tests/auth/test_session_validation.py`](backend-hormonia/tests/auth/test_session_validation.py), [`backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`](backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py), [`frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx`](frontend-hormonia/tests/integration/auth/hard-cut-cleanup-proof.test.tsx))
- External skill suggestions for the core stack were discovered with `npx skills find` for FastAPI, React, and Playwright (source: local skill discovery commands run during S01 research)
