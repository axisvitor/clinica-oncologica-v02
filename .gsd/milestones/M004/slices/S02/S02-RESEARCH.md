# M004/S02 — Research

**Date:** 2026-03-14

## Summary

S02 owns **R048** (single canonical auth/session contract) and **R049** (`firebase_uid` leaves the canonical runtime path), and supports **R047** (Firebase leaves the official runtime). The good news is that the canonical `/api/v2/auth/*` flow is already closer to the target than the S01 residue report alone suggests. `backend-hormonia/app/api/v2/routers/auth.py` already issues sessions from first-party email/password login, stores `user_id` in the `sessions` table, verifies sessions through `get_current_user_from_session`, revokes by canonical `user_id`, and passes focused proof packs that explicitly assert the happy path works without `firebase_uid` in the Redis session payload.

The remaining problem is lower in the stack. The backend still has **two auth helper families**: the newer `auth_dependencies` / `auth_session_contract` / `auth_session_cache` path, and the older `auth_session_shared` / `user_cache_shared` path used by adjacent V2 helpers and websockets. Both are partly canonical, but both still preserve hidden `firebase_uid` and legacy transport fallback behavior. That means the route contract is mostly converged while the helper substrate still allows the old identity model to leak back in.

Recommendation: treat S02 as a **backend convergence slice**, not a transport-retirement slice. Keep the visible `/api/v2/auth/login` → `verify-session` → restore → logout contract and the existing admin override seams stable. Narrow the canonical backend identity path so official runtime auth/session does not *need* `firebase_uid` anywhere outside explicit legacy modules. Leave root `/session/*`, `X-Session-ID`, session-as-Bearer, and websocket query fallback retirement to S03/S04, because the frontend and adjacent runtime still depend on them today.

## Recommendation

1. **Use the existing canonical route contract as the acceptance baseline.**
   - `/api/v2/auth/login`, `/api/v2/auth/verify-session`, `/api/v2/auth/logout`, `/api/v2/auth/logout-all`, and `/api/v2/users/me` already have green proof packs.
   - Avoid unnecessary payload/cookie drift; S02 does not need a public contract redesign to satisfy R048/R049.

2. **Converge the helper layer on `user_id`-first resolution.**
   - The canonical session payload produced by login already contains enough data for restore/verify without `firebase_uid`.
   - The real S02 work is shrinking `firebase_uid` from `auth_session_cache.py`, `auth_session_contract.py`, `auth_session_shared.py`, and `user_cache_shared.py` so the happy path resolves identity via embedded canonical fields and `get_user_by_id` / DB-by-`user_id` first.

3. **Quarantine legacy behavior instead of deleting it early.**
   - `app/dependencies/auth_legacy_firebase.py` and `app/routers/auth_session.py` are the right places for compatibility-only Firebase or root `/session/*` behavior.
   - Do not spread new canonical behavior into those legacy seams, and do not let canonical V2 helpers keep defining auth semantics through Firebase-shaped fallbacks.

4. **Do not retire header/bearer/query transport fallbacks in S02.**
   - `frontend-hormonia/src/app/providers/AuthContext.tsx` still restores `session_id` from localStorage.
   - `frontend-hormonia/src/lib/api-client/auth.ts` and `src/lib/api-client/core.ts` still emit both `Authorization: Bearer <session_id>` and `X-Session-ID`.
   - If S02 removes those server-side paths now, the official app regresses before S03 can cut the frontend over.

5. **If precedence changes are necessary, unify them deliberately or leave them alone.**
   - Today there are multiple session-id resolvers with different precedence rules.
   - Silent one-file precedence changes will create auth behavior drift across routes, helpers, and websockets.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| First-party email/password authentication | `backend-hormonia/app/services/auth.py::AuthService.authenticate_local_credentials` | Already handles invalid credentials, account lockout, inactive accounts, `auth_provider` normalization, and login-attempt cleanup. |
| Canonical session dependency orchestration | `backend-hormonia/app/dependencies/auth_session_contract.py::resolve_authenticated_session_user` | Already centralizes session lookup, `request.state` side effects, role permission enrichment, and the canonical session dependency contract. |
| Session cache/DB hydration | `backend-hormonia/app/dependencies/auth_session_cache.py::resolve_session_user_data` | Already encapsulates Redis lookup, DB fallback, cache rehydration, and user activity extension; S02 should narrow this seam, not replace it. |
| DB-backed session issuance/revocation | `backend-hormonia/app/api/v2/routers/auth.py` + `backend-hormonia/app/models/session.py` | The shipped login/logout flow already writes `SessionModel` rows and revokes them correctly. |
| Global revocation by canonical identity | `backend-hormonia/app/api/v2/routers/auth.py::_invalidate_all_user_sessions_cache` + `backend-hormonia/app/core/redis_manager/session_cache.py::invalidate_all_user_sessions` | Already supports `user_id`-centric invalidation while tolerating compatibility adapters that still know `firebase_uid`. |
| Override-sensitive auth proof | `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` | Already pins the narrow-signature override behavior and mapping-style session payload contract that admin/router code depends on. |

## Existing Code and Patterns

- `backend-hormonia/app/api/v2/routers/auth.py` — canonical login/verify/logout/logout-all routes. Login is already session-first and creates both the DB session row and Redis session payload.
- `backend-hormonia/app/services/auth.py` — canonical local credential authentication. Reuse this service layer; it already owns lockout, inactivity, and `auth_provider` cleanup.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — stable public dependency surface. `get_current_user_from_session()` is already documented as `user_id`-first with `firebase_uid` compatibility only when canonical data is missing.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — current canonical dependency entrypoint. It applies `request.state.session_id`, `request.state.user_id`, and `request.state.user_role`, which downstream overrides/tests rely on.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — the main hidden dual-identity seam. It already prefers embedded canonical session data and `user_id`, but still caches, rehydrates, and falls back through `firebase_uid` when present.
- `backend-hormonia/app/api/v2/auth_session_shared.py` + `backend-hormonia/app/api/v2/user_cache_shared.py` — alternate V2 helper family used by `messages/helpers.py`, `templates_shared.py`, `routers/tasks/dependencies.py`, `routers/localization.py`, and `api/websockets.py`. This family still preserves `firebase_uid` and legacy transport precedence.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` — already treats canonical `id` / `user_id` as authoritative and only falls back to `firebase_uid` when canonical IDs are absent.
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — correct place for Firebase bearer compatibility. Keep it isolated instead of letting Firebase logic bleed back into canonical helpers.
- `backend-hormonia/app/routers/auth_session.py` + `backend-hormonia/app/core/router_registry.py` — retained root `/session/*` compatibility island. Important constraint: this island is still mounted and still Firebase-shaped, but roadmap ownership says retirement is S04, not S02.
- `frontend-hormonia/src/app/providers/AuthContext.tsx` — frontend restore still loads `session_id` from localStorage and seeds the API client with it before calling `checkAuth()`.
- `frontend-hormonia/src/lib/api-client/auth.ts` + `frontend-hormonia/src/lib/api-client/core.ts` — the official client still emits `Authorization` and `X-Session-ID` together when a stored session id exists.

## Constraints

- This research targets **R048** and **R049** directly, and **R047** as a supporting constraint.
- The visible route contract is already proven green. S02 should converge backend identity/session internals without introducing avoidable response/cookie changes.
- Root `/session/*` retirement is explicitly a later slice concern. S02 should not broaden into deleting or tombstoning `backend-hormonia/app/routers/auth_session.py`.
- Frontend restore is not cookie-only yet. Backend acceptance of `X-Session-ID` and session-as-Bearer must remain stable until S03/S04 cut the official client over.
- Admin/router auth overrides depend on mapping-style session payloads and `request.state.user_id` / `request.state.user_role` side effects. Narrower override signatures are part of the proven contract.
- There are multiple session-id resolvers today:
  - `auth_session_contract.resolve_request_session_id()` — cookie priority by default via `ENABLE_COOKIE_PRIORITY`
  - `auth_session_shared.resolve_session_id()` — Authorization → `X-Session-ID` → cookie → query
  - `auth.py::_get_session_id_from_request()` — cookie → `X-Session-ID` → Authorization
  S02 should not create a fourth behavior by accident.
- `SessionModel` remains the canonical persistent session store. Redis is the fast-path cache, not the only source of truth.

## Common Pitfalls

- **Fixing only `auth.py`** — the top-level auth routes already look mostly canonical; the real hidden drift is in the shared helper families and adjacent V2 consumers.
- **Treating every `firebase_uid` occurrence as equally important** — some references are already legacy-only or schema-adjacent; S02 should remove *happy-path dependence*, not broaden into M005.
- **Removing `X-Session-ID` too early** — the current frontend restore/protected-request flow still emits it, and many helper dependencies still read it.
- **Assuming Authorization-only session fallback is uniformly supported** — it is not. `get_current_user_from_session()` accepts it, but `get_current_user()` only takes the session-first branch when a cookie or `X-Session-ID` is present.
- **Breaking override seams while “simplifying” dependencies** — admin dependencies intentionally tolerate narrower test override signatures and expect mapping-style user payloads.
- **Changing precedence in one helper only** — that will leave auth routes, tasks/templates/messages, and websockets disagreeing about which session source wins.

## Open Risks

- `backend-hormonia/app/dependencies/auth_dependencies.py::get_current_user()` currently routes to session-first auth only when a cookie or `X-Session-ID` is present. If the frontend drops the header before backend behavior is aligned, routes that depend on `get_current_user()` can fall through into legacy Firebase bearer auth.
- `backend-hormonia/app/api/v2/auth_session_shared.py` is still used by messages, templates, tasks, localization, and websockets. S02 can make `/api/v2/auth/*` green while leaving adjacent official-runtime helpers on a different auth/session contract unless this family is converged too.
- `auth_session_cache.py`, `user_cache_shared.py`, and Redis cache helpers still write/cache `firebase_uid` when available. Even if routes stop reading it on the happy path, hidden fallback dependence can survive in rehydration and cache-miss behavior.
- The root `/session/*` island and older Firebase-era tests still exist. Broad edits can create noisy failures that do not represent a regression in the official runtime path.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — `npx skills add wshobson/agents@fastapi-templates` |
| Redis | `mindrally/skills@redis-best-practices` | available — `npx skills add mindrally/skills@redis-best-practices` |
| SQLAlchemy | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | available — `npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm` |

## Sources

- The canonical route contract for login, verify-session, logout, logout-all, and password change lives in `backend-hormonia/app/api/v2/routers/auth.py` (source: [`backend-hormonia/app/api/v2/routers/auth.py`](backend-hormonia/app/api/v2/routers/auth.py))
- The current public auth dependency surface and request-state contract live in `backend-hormonia/app/dependencies/auth_dependencies.py` and `backend-hormonia/app/dependencies/auth_session_contract.py` (source: [`backend-hormonia/app/dependencies/auth_dependencies.py`](backend-hormonia/app/dependencies/auth_dependencies.py), [`backend-hormonia/app/dependencies/auth_session_contract.py`](backend-hormonia/app/dependencies/auth_session_contract.py))
- The hidden dual-identity cache/session fallback logic lives in `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, and `backend-hormonia/app/api/v2/user_cache_shared.py` (source: [`backend-hormonia/app/dependencies/auth_session_cache.py`](backend-hormonia/app/dependencies/auth_session_cache.py), [`backend-hormonia/app/api/v2/auth_session_shared.py`](backend-hormonia/app/api/v2/auth_session_shared.py), [`backend-hormonia/app/api/v2/user_cache_shared.py`](backend-hormonia/app/api/v2/user_cache_shared.py))
- The retained Firebase/root-session compatibility islands live in `backend-hormonia/app/dependencies/auth_legacy_firebase.py`, `backend-hormonia/app/routers/auth_session.py`, and `backend-hormonia/app/core/router_registry.py` (source: [`backend-hormonia/app/dependencies/auth_legacy_firebase.py`](backend-hormonia/app/dependencies/auth_legacy_firebase.py), [`backend-hormonia/app/routers/auth_session.py`](backend-hormonia/app/routers/auth_session.py), [`backend-hormonia/app/core/router_registry.py`](backend-hormonia/app/core/router_registry.py))
- The current frontend restore and header-emission contract lives in `frontend-hormonia/src/app/providers/AuthContext.tsx`, `frontend-hormonia/src/lib/api-client/auth.ts`, and `frontend-hormonia/src/lib/api-client/core.ts` (source: [`frontend-hormonia/src/app/providers/AuthContext.tsx`](frontend-hormonia/src/app/providers/AuthContext.tsx), [`frontend-hormonia/src/lib/api-client/auth.ts`](frontend-hormonia/src/lib/api-client/auth.ts), [`frontend-hormonia/src/lib/api-client/core.ts`](frontend-hormonia/src/lib/api-client/core.ts))
- The adjacent V2 helper consumers of `auth_session_shared` were mapped with repo search and include messages, templates, tasks, localization, and websockets (source: `rg -n "from app\.api\.v2\.auth_session_shared import|resolve_session_id\(|get_user_data_from_session\(" backend-hormonia/app/api/v2 -g '*.py'`)
- Focused backend auth proof is already green on the current codebase (source: `cd backend-hormonia && pytest -q tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_dependency_override_contract.py tests/api/v2/test_auth_session_priority.py`)
- The live backend residue boundary for this slice comes from the S01 verifier report (source: `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`)
- Skill discovery came from `npx skills find "FastAPI"`, `npx skills find "Redis"`, and `npx skills find "SQLAlchemy"`
