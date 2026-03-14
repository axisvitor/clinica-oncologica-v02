# M004/S05 — Research

**Date:** 2026-03-14

## Summary

S05 owns **R047** directly and materially supports **R049**. After S03/S04, the official frontend is already clean in the S01 residue guard, and the public auth transport has already been cut over to the cookie-backed contract. The remaining live Firebase problem is deeper: backend internals still persist, cache, and sometimes resolve authenticated identity through `firebase_uid` alongside canonical `id` / `user_id`. That means Firebase is no longer the public contract, but it is still part of the runtime’s internal identity model.

The main blocker is not docs or old tests. It is the cache/session/helper seam spanning `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/core/redis_manager/session_cache.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, and `backend-hormonia/app/api/v2/user_cache_shared.py`. Those files still serialize `firebase_uid`, cache user payloads by UID, rehydrate sessions with UID metadata, and fallback to DB/cache lookup by UID when canonical identity is incomplete. Websocket auth inherits the same behavior through the shared helper path.

The second surprise is operational: the current branch has **committed merge-conflict markers in live auth files**, not just tests. `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py` fails immediately. So execution cannot start from “small Firebase cleanup” alone; it first needs auth-dependency hygiene restored, then the `firebase_uid` runtime pivot removed, then adjacent audit/docs/types aligned, while leaving model/migration drops to M005.

## Recommendation

Take S05 in three ordered passes.

**Pass 1 — restore a trustworthy auth baseline.** Resolve the committed merge markers in `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/dependencies/auth_dependencies.py`, and `backend-hormonia/app/dependencies/__init__.py` before making semantic changes. Until that is done, any runtime proof is suspect and backend verification cannot honestly pass.

**Pass 2 — remove `firebase_uid` from the live session/cache identity path.** Start at `backend-hormonia/app/dependencies/auth_session_cache.py` and `backend-hormonia/app/core/redis_manager/session_cache.py`, then align the adjacent shared helper path in `backend-hormonia/app/api/v2/auth_session_shared.py` and `backend-hormonia/app/api/v2/user_cache_shared.py`. The goal is: canonical payloads/session rows/cache entries are keyed and rehydrated by `id` / `user_id` only; any remaining `firebase_uid` becomes passive passthrough at most, or disappears from runtime payloads entirely. Only after that should the auth login serializer in `backend-hormonia/app/api/v2/routers/auth.py` and the shared adapter in `backend-hormonia/app/dependencies/auth_user_adapter.py` stop writing `firebase_uid` into session/cache payloads.

**Pass 3 — clean the adjacent story without crossing into M005.** Audit and admin audit surfaces still expose `firebase_uid`, but repo evidence suggests canonical request state no longer sets `request.state.firebase_uid`, so this looks like response/storage residue rather than a live auth dependency. Update the runtime-adjacent audit/admin serializers/schemas/docs/types (`backend-hormonia/app/middleware/hipaa_audit_middleware.py`, `backend-hormonia/app/services/audit/audit_service.py`, `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py`, `backend-hormonia/app/schemas/v2/admin_extensions.py`, `backend-hormonia/app/api/v2/routers/docs/data_providers.py`, `frontend-hormonia/src/types/api.ts`, `frontend-hormonia/src/types/rbac.ts`, `frontend-hormonia/src/types/medico.ts`) so the official system stops describing Firebase as live. Leave physical schema/model/migration cleanup (`app/models/**`, `app/schemas/**`, Alembic) for M005.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Canonical session identity cleanup | `backend-hormonia/app/dependencies/auth_session_cache.py` + `backend-hormonia/app/dependencies/auth_session_contract.py` + `backend-hormonia/app/core/redis_manager/session_cache.py` | These are already the shared seams for HTTP session restore and cache rehydration; removing `firebase_uid` here fixes the official runtime once instead of chasing route-by-route symptoms. |
| Adjacent runtime consumers still inheriting UID fallback | `backend-hormonia/app/api/v2/auth_session_shared.py` + `backend-hormonia/app/api/v2/user_cache_shared.py` | Websocket and helper-driven consumers already use this pair. Reuse the shared helper boundary instead of forking a second canonicalization path. |
| Audit/admin residue cleanup | `backend-hormonia/app/services/audit/audit_service.py` + `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` + `backend-hormonia/app/schemas/v2/admin_extensions.py` | These are the central serializer/schema seams for runtime audit output. Clean them there and the admin surface follows without touching schema yet. |
| Regression guard | `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` and the existing S01 allowlist vocabulary | S01 already encodes the milestone’s approved boundary. Extend proof with focused checks where S01 intentionally excludes docs/models/tests instead of inventing a second residue vocabulary. |

## Existing Code and Patterns

- `backend-hormonia/app/dependencies/auth_session_cache.py` — canonical auth/session helper, but still serializes `firebase_uid`, caches by UID, rehydrates Redis sessions with UID metadata, and falls back to DB/cache lookup by UID. Also currently contains committed merge markers and is not syntactically safe.
- `backend-hormonia/app/core/redis_manager/session_cache.py` — the live session payload contract still stores optional `firebase_uid` and matches global logout/session listing by `user_id OR firebase_uid`; this is the deepest runtime blocker for R049.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — adjacent shared session helper still treats `firebase_uid` as a valid fallback identity and is used by live consumers like websocket auth.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — companion cache helper still serializes `firebase_uid`, reads by UID when canonical ID is absent, and writes cache entries under both keys.
- `backend-hormonia/app/api/v2/routers/auth.py` — official local login still adds `user_payload["firebase_uid"] = user.firebase_uid` before creating the Redis session cache entry.
- `backend-hormonia/app/dependencies/auth_user_adapter.py` — shared user/session adapter still emits `firebase_uid`, `firebase_last_sign_in`, and `firebase_photo_url` into cache/session-style payloads.
- `backend-hormonia/app/middleware/hipaa_audit_middleware.py` — audit extraction still reads `request.state.firebase_uid`, but the canonical session contract only sets `user_id` and `user_role`; this suggests audit UID is now mostly inert runtime residue.
- `backend-hormonia/app/services/audit/audit_service.py` — central runtime audit service still models and persists `firebase_uid` in `AuditEventContext` and `AuditLog` writes.
- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` — live admin audit serializer still returns `firebase_uid` in audit payloads.
- `backend-hormonia/app/schemas/v2/admin_extensions.py` — admin audit response schema and examples still advertise `firebase_uid` as a first-class field.
- `backend-hormonia/app/api/v2/routers/docs/data_providers.py` — live docs provider still tells operators to authenticate with Firebase and use `X-Session-ID`; this is not archive content, it is routed docs content.
- `frontend-hormonia/src/types/api.ts` — the generic frontend `User` interface still exposes `firebase_uid`, even though the runtime normalizers already dropped it.
- `frontend-hormonia/src/types/rbac.ts` — still exports `AuthProvider.FIREBASE`; repo search found no live runtime usage outside type barrels, so this is likely low-risk narrative/type cleanup.
- `frontend-hormonia/src/types/medico.ts` — still explains role validation in Firebase-claims terms; likely adjacent documentation/type residue, not a runtime blocker.
- `backend-hormonia/app/utils/user_cache.py` — strong Firebase-shaped cache helper, but repo search found no live app imports outside tests; treat as probable dead/isolated residue, not the first S05 target.
- `backend-hormonia/app/models/user.py`, `backend-hormonia/app/models/audit_log.py`, `backend-hormonia/app/models/user_sync_log.py` — Firebase columns/enums remain, but this is structural debt already assigned to M005.

## Constraints

- The current branch is not auth-runtime-clean: committed merge markers exist in live backend auth files (`auth_session_contract.py`, `auth_session_cache.py`, `auth_dependencies.py`, `dependencies/__init__.py`). `python3 -m py_compile ...` fails before semantic verification can even start.
- S05 must not drift into M005. Dropping `firebase_uid` columns, `AuthProvider.FIREBASE`, audit-log indexes, or Alembic history is schema/migration work, not this slice.
- The S01 verifier intentionally excludes `backend-hormonia/app/models/**`, `backend-hormonia/app/schemas/**`, backend docs routes, tests, and other historical surfaces. S05 therefore needs both the residue guard **and** focused proof for audit/docs/type cleanup.
- `backend-hormonia/app/api/websockets.py` consumes the shared session helper path, so session/cache cleanup cannot be HTTP-only.
- `frontend-hormonia/src/app/providers/AuthContext.tsx` still uses `@/types/api` `User`, so cleaning `frontend-hormonia/src/types/api.ts` must preserve the current runtime shape expected by the provider and normalizers.
- `backend-hormonia/app/middleware/hipaa_audit_middleware.py` currently extracts session context from `Authorization` and `X-Session-ID`; S04 already retired those as accepted staff transports, so audit cleanup must not accidentally revive them as semantically valid.

## Common Pitfalls

- **Confusing runtime blockers with schema debt** — fix the live session/cache/helper path first; leave model columns, indexes, and migrations to M005.
- **Relying on S01 alone to prove S05** — S01 does not cover docs, models, schemas, or many adjacent runtime files. Pair it with focused proof around audit/admin/docs/type seams.
- **Starting with dead-looking helpers** — `backend-hormonia/app/utils/user_cache.py` looks bad but has no live app imports; don’t burn the slice there before fixing the real session/cache path.
- **Cleaning audit storage before audit runtime semantics** — first prove whether canonical auth still feeds `firebase_uid` into request state; otherwise you risk churning schema-facing code without reducing runtime Firebase dependence.
- **Ignoring the merge-marker blocker** — any planned verification after a semantic edit is meaningless until the backend auth files are syntactically valid again.

## Open Risks

- Resolving the committed merge markers may reveal a semantic divergence between S04’s intended cookie-only contract and the currently checked-in files; the first execution pass may need to re-establish S04 truth before S05-specific cleanup.
- Removing UID fallback from session/cache helpers can ripple into `RedisAuthCacheAdapter`, `FirebaseRedisCache`, `RedisManager` compatibility helpers, websocket auth, and null/test doubles that still mirror dual-key behavior.
- Audit/admin cleanup may require a compatibility decision: hide `firebase_uid` from response schemas now while leaving DB columns intact, or keep a deprecated field until M005. The safer S05 bias is to stop treating it as official runtime output.
- `backend-hormonia/app/api/v2/routers/docs/data_providers.py` is live routed docs content, not archive markdown. Updating it changes operator-facing guidance immediately and should be verified explicitly.
- The frontend generic type cleanup is probably low risk, but `AuthProvider.FIREBASE` and `firebase_uid` removal can still surface stale imports in type-only code outside the S01 runtime guard.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — install with `npx skills add wshobson/agents@fastapi-templates` |
| Redis | `mindrally/skills@redis-best-practices` | available — install with `npx skills add mindrally/skills@redis-best-practices` |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available — install with `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |

## Sources

- The live backend residue map after S04 is concentrated in `firebase_uid`, `x_session_id`, session-as-Bearer rejection plumbing, and websocket session fallback; frontend approved residue is already zero. (source: `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`)
- The canonical session/cache helper still serializes `firebase_uid`, caches by UID, and falls back to DB/cache lookup by UID; it currently contains committed merge markers. (source: `backend-hormonia/app/dependencies/auth_session_cache.py`)
- The request-state contract only persists `session_id`, `user_id`, and `user_role`, which makes audit `request.state.firebase_uid` look mostly inert under the canonical path. (source: `backend-hormonia/app/dependencies/auth_session_contract.py`)
- The underlying Redis session contract still stores optional `firebase_uid` and matches global logout/session listing by `user_id OR firebase_uid`. (source: `backend-hormonia/app/core/redis_manager/session_cache.py`)
- Adjacent helper consumers still inherit UID fallback semantics through shared V2 session/cache helpers. (source: `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`, `backend-hormonia/app/api/websockets.py`)
- Official local login still injects `firebase_uid` into the session cache payload. (source: `backend-hormonia/app/api/v2/routers/auth.py`)
- Audit/admin runtime surfaces still model and emit `firebase_uid`, even though the canonical auth request state is already `user_id`-first. (source: `backend-hormonia/app/middleware/hipaa_audit_middleware.py`, `backend-hormonia/app/services/audit/audit_service.py`, `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py`, `backend-hormonia/app/schemas/v2/admin_extensions.py`)
- Live routed docs still instruct Firebase login and `X-Session-ID` usage, so operational guidance has not caught up to S04. (source: `backend-hormonia/app/api/v2/routers/docs/data_providers.py`)
- The generic frontend runtime type surface still exposes `firebase_uid`, while RBAC and medico types still describe Firebase-era auth semantics. (source: `frontend-hormonia/src/types/api.ts`, `frontend-hormonia/src/types/rbac.ts`, `frontend-hormonia/src/types/medico.ts`)
- `backend-hormonia/app/utils/user_cache.py` and `backend-hormonia/app/services/audit_log.py` do not appear to have live app imports, so they should not drive S05 before the session/cache seam is fixed. (source: repo search with `rg` over `backend-hormonia/app` and `backend-hormonia/tests`)
- Current branch health is not trustworthy for auth work until the merge markers are resolved: `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py` fails. (source: local verification command)
- External skill discovery found plausible optional skills for FastAPI, Redis, and React, but none are installed project skills today. (source: `npx skills find "FastAPI"`, `npx skills find "Redis"`, `npx skills find "React"`)
