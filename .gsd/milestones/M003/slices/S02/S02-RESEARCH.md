# M003 / S02 — Research

**Date:** 2026-03-12

## Summary

This slice owns **R034** directly and materially supports **R036, R037, R038, and R039**. The backend auth/session hotspot is not one monolithic concern; it is a bundle of at least four already-distinct contracts currently trapped in `backend-hormonia/app/dependencies/auth_dependencies.py` (1579 lines): **session source resolution**, **session/cache → user hydration**, **mapping-dict → `User` adaptation**, and **legacy Firebase bearer/websocket compatibility**. The main operational seam is still `get_current_user_from_session()` (202 dependency uses in S01’s verifier), not `get_current_user()`. That means S02 should reduce risk by splitting around the session-first happy path first, then isolating compatibility residue behind stable re-exports.

The repo already contains reusable primitives that S02 should standardize on instead of re-inventing: `app.api.v2.auth_session_shared.resolve_session_id()`, `extract_canonical_user_from_session()`, `get_user_data_from_session()`, and `app.api.v2.user_cache_shared.get_or_cache_user_data()`. Several newer modules (`app/api/websockets.py`, `app/api/v2/templates_shared.py`, `app/api/v2/messages/helpers.py`, `app/api/v2/routers/tasks/dependencies.py`) already use those helpers, while the hotspot still inlines similar logic. The cleanest refactor is therefore **consolidation + delegation**, not a fresh auth framework.

There is one important surprise: the shared resolver and the hotspot do **not** currently express the same precedence contract. `get_current_user_from_session()` is cookie-first when `ENABLE_COOKIE_PRIORITY=True`, but `auth_session_shared.resolve_session_id()` is Authorization-first. S02 should either unify that intentionally or keep the difference explicit and fenced, because silent convergence/divergence here would create contract drift across HTTP routes, websocket bootstrap, tasks, templates, and other simplified dependencies.

## Recommendation

Take a **preserve-surface / split-internals** approach.

1. **Keep callable identity stable** for all exported auth dependencies during S02.
   - Preserve `app.dependencies.auth_dependencies` as the public import surface.
   - Preserve `app.dependencies.__init__` re-exports.
   - Re-export from new modules instead of changing import paths in callers.
   - Reason: FastAPI overrides are keyed by the original callable object, and the repo currently has **49 explicit override sites** for `get_current_user_from_session`, `get_current_user_object_from_session`, and `get_admin_user`.

2. **Split `auth_dependencies.py` by responsibility, not by arbitrary size.**
   Recommended internal module seams:
   - `session_contract.py` — session ID resolution, request.state side effects, session payload validation, permissions enrichment.
   - `session_cache.py` — canonical embedded-user extraction, cache lookup/hydration, PostgreSQL fallback, Redis rehydration helpers.
   - `user_adapter.py` — `user_to_cache_dict()`, dict→`User` conversion, role normalization.
   - `legacy_firebase.py` (or similarly named) — `verify_firebase_token()`, bearer-token `get_current_user()`, websocket Firebase fallback.
   - `role_dependencies.py` — `get_admin_user()`, `get_doctor_user()`, `get_current_active_admin()` once their import compatibility is preserved.

3. **Standardize on the existing shared session primitives where they already match the shipped contract.**
   - Reuse `auth_session_shared.py` / `user_cache_shared.py` instead of copying logic into yet another auth helper.
   - But do **not** blindly replace `get_current_user_from_session()` with `resolve_session_id()` until precedence behavior is made explicit; today they differ.

4. **Do not broaden S02 into deletion.**
   - `auth_session.py`, `roles/dependencies.py`, and Firebase compatibility branches remain S04-style cleanup decisions unless deadness is proven.
   - In S02, the right win is smaller modules with stable exports and stable contracts.

## Don’t Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Session source resolution across header/cookie/query paths | `backend-hormonia/app/api/v2/auth_session_shared.py::resolve_session_id()` | Already used by websocket, templates, messages, and tasks helpers; consolidates one important contract surface. |
| Canonical embedded-user extraction from session payloads | `backend-hormonia/app/api/v2/auth_session_shared.py::extract_canonical_user_from_session()` | Matches the user-id-centric local-session contract already proved by tests. |
| Cache-or-DB user hydration with Redis repopulation | `backend-hormonia/app/api/v2/user_cache_shared.py::get_or_cache_user_data()` | Avoids duplicating cache lookup / DB fallback / recache flow again inside the hotspot. |
| Override-tolerant dependency invocation for admin wrappers | `backend-hormonia/app/api/v2/routers/admin/dependencies.py::_invoke_dependency()` | The repo already has tests with narrower override signatures; this helper exists to absorb that fragility. |
| Compatibility wrappers that preserve patch targets | `backend-hormonia/app/api/v2/routers/health/compat.py`, `_get_current_user_from_session_dep()` in `reports.py` / `enhanced_reports.py` | These modules show the local pattern for preserving monkeypatch and dependency-override behavior without rewriting callers. |
| Redis adapter that bridges old cache interfaces to canonical methods | `backend-hormonia/app/dependencies/auth_dependencies.py::RedisAuthCacheAdapter` | Keeps legacy patch points alive while delegating to the newer Redis manager methods. |

## Existing Code and Patterns

- `backend-hormonia/app/dependencies/auth_dependencies.py` — primary hotspot. The high-value extraction targets are:
  - `get_current_user_from_session()` — lines 738–1099 (~362 lines), the main session-first seam.
  - `get_current_user_object_from_session()` — lines 1100–1173 (~74 lines), pure adaptation seam.
  - `get_current_user()` — lines 1174–1457 (~284 lines), legacy bearer/Firebase path plus session-first preference.
  - `verify_firebase_token()` / `get_current_user_websocket()` / role deps — compatibility residue that should be isolated, not expanded.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — existing shared session primitives. This is the clearest reuse point for S02, but it currently has a precedence contract mismatch with `get_current_user_from_session()`.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — already centralizes serialize/cache/hydrate behavior; strong candidate to become the canonical cache helper underneath the hotspot.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical session **write/invalidate** path (`_create_canonical_session_cache_entry()`, `_invalidate_session_cache()`, `_invalidate_all_user_sessions_cache()`, `_get_session_id_from_request()`). S02 should align reads with this instead of letting `auth_dependencies.py` drift further.
- `backend-hormonia/app/routers/auth_session.py` — legacy full session router, still implementing its own Firebase/session flows. Not an early deletion candidate. It is a compatibility constraint.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — admin wrapper already preserves override behavior, test-environment fallback, and conversion from session dict to `User` object. Refactor should reuse/keep this behavior.
- `backend-hormonia/app/api/v2/routers/roles/dependencies.py` — thin admin-by-session wrapper, but still tied to `firebase_uid` DB lookup. That makes it a compatibility constraint for S02, not safe deletion.
- `backend-hormonia/app/api/websockets.py` — canonical websocket path already authenticates via session helpers, and its tests assert the user-id-centric session contract.
- `backend-hormonia/app/api/v2/templates_shared.py`, `backend-hormonia/app/api/v2/messages/helpers.py`, `backend-hormonia/app/api/v2/routers/tasks/dependencies.py` — proof that smaller session helpers are already an accepted pattern elsewhere in the repo.
- `backend-hormonia/app/dependencies/__init__.py` — public package re-export surface for `get_current_user`, `get_admin_user`, `get_doctor_user`, and `get_current_user_websocket`; re-export stability matters.

## Constraints

- **Stable callable identity is part of the contract.** FastAPI dependency overrides use the original dependency callable as the key. The repo currently has 49 explicit override sites touching these auth dependencies. Replacing imports instead of re-exporting will break tests and patch targets even if runtime behavior stays the same.
- **The mapping-style session dict contract must survive.** `get_current_user_from_session()` is the hottest seam in the backend and callers expect a dict-like payload with `permissions`, optional `firebase_uid`, and stable auth failure behavior.
- **`request.state` side effects are load-bearing.** `request.state.session_id`, `request.state.user_id`, and `request.state.user_role` are asserted in tests and consumed by middleware/helpers.
- **Canonical user-id sessions are already the happy path.** Multiple green suites assert that local/session-first auth must work without `firebase_uid` cache lookup on the happy path.
- **Compatibility branches still exist for real callers.** `verify_firebase_token`, `get_current_user_websocket`, `get_doctor_user`, `roles/dependencies.py`, and `auth_session.py` still have imports/tests or runtime residue. S02 should isolate them, not delete them on taste.
- **Session write/read drift already exists.** `auth.py` owns canonical session cache creation/invalidation, while `auth_dependencies.py` owns a broader read/rehydrate path. The split should reduce that asymmetry, not create a third contract.
- **Config-driven precedence and timeout behavior are real runtime constraints.** `ENABLE_COOKIE_PRIORITY`, `SESSION_COOKIE_NAME`, `FIREBASE_SESSION_TTL_SECONDS`, `DB_QUERY_TIMEOUT_READ`, and `REDIS_OPERATION_TIMEOUT` are wired into the hotspot today.

## Verification Baseline

Focused auth/session proof is strong enough to refactor against:

- **Green during research**
  - `cd backend-hormonia && pytest -q tests/auth/test_user_conversion.py tests/unit/test_auth_session_identity_contract.py tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_hard_cut_cleanup.py`
  - `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend`

- **Red outside the slice’s core gate, but worth recording**
  - `cd backend-hormonia && pytest -q tests/api/v2/test_auth_timeout.py tests/security/test_firebase_uid_validation.py tests/unit/test_auth_dependencies.py`
    - current failure surface: `tests/security/test_firebase_uid_validation.py` assumes the older `firebase_uid` cache path and does not configure `get_user_by_id` on `AsyncMock(spec=FirebaseRedisCache)`. The runtime is already more `user_id`-centric than those mocks.
  - `cd backend-hormonia && pytest -q tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/api/v2/test_admin.py -k 'get_admin_user or admin'`
    - current failure surfaced in `tests/api/v2/test_admin.py::TestActivityStatistics::test_get_activity_statistics`, apparently unrelated to the auth/session hotspot (`AuditLog.severity` query issue).

**Implication for S02:** use the green focused auth/session suites as the slice gate; record the broader red suites as pre-existing/out-of-scope noise unless the refactor directly touches them.

## Common Pitfalls

- **Breaking dependency overrides by moving the callable instead of re-exporting it** — keep `auth_dependencies.py` as the stable import/override surface and delegate internally.
- **Accidentally reintroducing `firebase_uid` as a required happy-path field** — several green suites explicitly assert canonical session behavior without `firebase_uid` lookup.
- **Unifying session source precedence without noticing the current mismatch** — `get_current_user_from_session()` can be cookie-first; `resolve_session_id()` is currently Authorization-first. Pick one contract deliberately, with tests.
- **Deleting wrapper logic from admin/reports/health because it looks repetitive** — those wrappers exist to preserve test patch targets and narrower override signatures.
- **Treating `auth_session.py` as a dead alias** — it is still a full compatibility router with its own behavior; S02 should not assume it is removable.
- **Expanding S02 into Firebase retirement cleanup** — the slice win is a cleaner backend auth/session seam, not broad compatibility deletion.

## Open Risks

- The current red `tests/security/test_firebase_uid_validation.py` suite can become a distraction during S02. It is evidence of test-fixture drift toward older cache assumptions, not necessarily of a runtime auth regression.
- `app/routers/auth_session.py` duplicates older session behavior deeply enough that S02 may only partially reduce backend auth complexity unless shared helpers are extracted and reused there later.
- `roles/dependencies.py` still queries by `firebase_uid`, so a too-aggressive simplification in S02 could create admin-only drift that won’t show up in the smaller local-session suites.
- If S02 changes precedence behavior without an explicit test update, websocket/tasks/template helpers could diverge from HTTP route behavior in subtle ways.

## Skills Discovered

Relevant installed skills from the current environment: **none**.

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — `npx skills add wshobson/agents@fastapi-templates` |
| Redis | `mindrally/skills@redis-best-practices` | available — `npx skills add mindrally/skills@redis-best-practices` |
| SQLAlchemy | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | available — `npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm` |

## Sources

- Hotspot size, dependency counts, candidate counts, and baseline seam blast radius (source: `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend`)
- Stable backend auth/session handoff, non-candidates, and deletion-proof queue (source: `.gsd/milestones/M003/slices/S01/S01-SUMMARY.md`)
- Main hotspot structure and split candidates (source: `backend-hormonia/app/dependencies/auth_dependencies.py`)
- Canonical session shared helpers already used outside the hotspot (source: `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`)
- Canonical session write/invalidate path (source: `backend-hormonia/app/api/v2/routers/auth.py`)
- Compatibility constraints and wrapper patterns (source: `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `backend-hormonia/app/api/v2/routers/roles/dependencies.py`, `backend-hormonia/app/api/v2/routers/reports.py`, `backend-hormonia/app/api/v2/routers/enhanced_reports.py`, `backend-hormonia/app/api/v2/routers/health/compat.py`, `backend-hormonia/app/routers/auth_session.py`)
- Existing session-helper reuse in adjacent modules (source: `backend-hormonia/app/api/websockets.py`, `backend-hormonia/app/api/v2/templates_shared.py`, `backend-hormonia/app/api/v2/messages/helpers.py`, `backend-hormonia/app/api/v2/routers/tasks/dependencies.py`)
- FastAPI override contract: `app.dependency_overrides` uses the original dependency callable as the dictionary key (source: FastAPI docs, `advanced/testing-dependencies.md`: https://github.com/fastapi/fastapi/blob/master/docs/en/docs/advanced/testing-dependencies.md)
