---
estimated_steps: 4
estimated_files: 6
---

# T02: Extract session resolution and cache hydration modules

**Slice:** S02 — Backend Auth/Session Hotspot Refactor
**Milestone:** M003

## Description

Split the biggest auth hotspot first: the session-first dict seam. This task moves session-ID resolution, request-state enrichment, canonical embedded-user handling, cache lookup, and Redis/DB fallback logic into focused modules while keeping `get_current_user_from_session()` as the stable public dependency callable.

## Steps

1. Create `backend-hormonia/app/dependencies/auth_session_contract.py` for session source resolution, request-state writes, and permission enrichment with explicit `ENABLE_COOKIE_PRIORITY` handling.
2. Create `backend-hormonia/app/dependencies/auth_session_cache.py` for canonical session payload extraction, Redis cache lookup, user-id/firebase fallback hydration, and Redis/DB fallback orchestration.
3. Rewire `backend-hormonia/app/dependencies/auth_dependencies.py` so `get_current_user_from_session()` delegates into the new modules while reusing `app.api.v2.auth_session_shared` / `app.api.v2.user_cache_shared` where their behavior already matches the shipped contract.
4. Run the split-contract and existing session-priority/session-identity suites, then trim or fix any remaining drift until the session dict seam is green again.

## Must-Haves

- [ ] `get_current_user_from_session()` keeps returning the same mapping-style payload with `permissions` plus `request.state.session_id` / `user_id` / `user_role` side effects.
- [ ] Cookie/header/authorization precedence remains deliberate and test-covered; shared helpers are reused only where they do not silently change the HTTP contract.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py`
- Re-run the focused command after each extraction until the session dict seam is green without reintroducing `firebase_uid` as a happy-path requirement.

## Observability Impact

- Signals added/changed: Session-resolution and fallback logging move into dedicated modules but keep the current source/fallback/inactive-user diagnostic surfaces.
- How a future agent inspects this: Use the focused pytest gate plus `request.state` assertions to localize whether the failure sits in session resolution, cache hydration, or fallback handling.
- Failure state exposed: Precedence drift, missing request-state writes, and user-id vs `firebase_uid` hydration regressions fail in dedicated unit/API tests instead of hiding in the monolith.

## Inputs

- `backend-hormonia/app/dependencies/auth_dependencies.py` — the current monolithic implementation being split.
- `backend-hormonia/app/api/v2/auth_session_shared.py` and `backend-hormonia/app/api/v2/user_cache_shared.py` — the shared helpers this task should standardize on where contracts align.

## Expected Output

- `backend-hormonia/app/dependencies/auth_session_contract.py` and `backend-hormonia/app/dependencies/auth_session_cache.py` — focused modules that own the session-first dict seam.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — slimmer façade keeping the public dependency callable stable while delegating the session work.
