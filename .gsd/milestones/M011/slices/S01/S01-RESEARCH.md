# S01 — Backend caching + index composto — Research

**Date:** 2026-03-17
**Depth:** Targeted

## Summary

This slice adds Redis caching to the two hottest physician endpoints and creates a composite index for the window function query. The implementation is straightforward but has one critical finding: the `@cache_response` decorator's key-building logic does NOT safely include `user_id` when a `Request` object is present — it only uses `[func_name, request.url.path, request.url.query]`, which would cause cache key collision between different doctors seeing each other's patients. The `dashboard.py` endpoint already has correct manual caching with `user_id` in the key and TTL=120s via `redis_cache.get/set`. The physician endpoint has no caching at all.

The recommendation is: (1) for `physician/patients`, do NOT use the bare `@cache_response` decorator — instead follow the proven manual caching pattern from `dashboard.py` which already includes `user_id` in the key, (2) for `dashboard/main`, the caching already works correctly — only adjust TTL if it differs from target, (3) create a standard Alembic migration for the composite index.

## Recommendation

**Physician/patients endpoint**: Add manual caching following the exact pattern in `dashboard.py` — build key as `f"physician:patients:user:{user_id}:page:{page}:size:{size}:search:{search}:phase:{flow_phase}:status:{flow_status}"`, use `redis_cache = Depends(get_generic_cache)` for get/set with TTL=60s. This avoids the `@cache_response` key collision issue while matching the codebase's existing working pattern.

**Dashboard/main endpoint**: Already has correct per-user caching via `redis_cache.get/set` with key `f"dashboard:main:user:{user_id}:range:{time_range.value}"` and TTL=120s (`CACHE_TTL_REALTIME = 120`). No changes needed — the caching is already in place and correct.

**Index**: Standard Alembic migration with `op.create_index` on `patient_flow_states(patient_id, started_at DESC)`. Down revision: `m008_s01_t03_sessions_align`.

## Implementation Landscape

### Key Files

- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — The physician patient list endpoint (131 lines). Async, uses `get_async_db` + `get_current_user_from_session`. Has NO `request: Request` parameter and NO caching. Filters by `Patient.doctor_id == current_user.id` for non-admin users. Window function `ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY started_at DESC)` in subquery. Needs: add `request: Request` param, add `redis_cache=Depends(get_generic_cache)` dependency, add cache get/set with user-specific key and TTL=60s.

- `backend-hormonia/app/api/v2/routers/dashboard.py` — Dashboard endpoints (561 lines). `get_main_dashboard` already has manual caching: key `f"dashboard:main:user:{user_id}:range:{time_range.value}"`, TTL=120s via `CACHE_TTL_REALTIME = 120`, using `redis_cache=Depends(get_generic_cache)`. **No changes needed** — already correctly cached per-user with correct TTL matching D019.

- `backend-hormonia/app/infrastructure/cache/cache_decorators.py` — Defines `@cache_response`. Key-building path when `request_obj is not None`: uses `[func_name, request.url.path, request.url.query]` — does NOT include user_id/role. When `request_obj is None`: hashes all args/kwargs including unstable `AsyncSession` objects (cache never hits). **Do not use `@cache_response` for user-specific endpoints without key_builder enhancement.**

- `backend-hormonia/app/dependencies/auth_dependencies.py` — `get_generic_cache()` at line 298 returns `GenericRedisCache`. `get_current_user_from_session()` at line 457 returns `Dict` with `id`, `role`, `email` etc.

- `backend-hormonia/app/models/flow.py` — `PatientFlowState` model. Existing indexes: `patient_id` (single column, `index=True`), `status` (single, `index=True`), `(id, version)` via explicit `Index("idx_patient_flow_states_version", "id", "version")`. No composite index on `(patient_id, started_at)`. The `started_at` column: `Column(DateTime(timezone=True), server_default=func.now())`.

- `backend-hormonia/alembic/versions/m008_s01_t03_sessions_align.py` — Latest Alembic head. `revision = "m008_s01_t03_sessions_align"`. New migration must set `down_revision` to this.

### Build Order

**Task 1: Alembic migration for composite index** — Write migration file `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`. Create index `idx_pfs_patient_started` on `patient_flow_states(patient_id, started_at DESC)`. Use `postgresql_using='btree'` and add `if_not_exists=True` guard for safety. This is independent and can be verified with `ast.parse` immediately.

**Task 2: Add caching to physician/patients endpoint** — Add `request: Request` param (needed for `@limiter` pattern and future consistency), add `redis_cache=Depends(get_generic_cache)` dependency, add `from app.dependencies.auth_dependencies import get_generic_cache` import. Build cache key incorporating `user_id` + all query params. Cache get before query execution, cache set after building response. TTL=60s. Verify with `ast.parse`.

**Task 3: Verify dashboard.py caching is correct** — Confirm `CACHE_TTL_REALTIME = 120` matches D019's 120s dashboard TTL. Confirm key includes `user_id`. No code changes expected — just verification.

### Verification Approach

1. `python3 -c "import ast; ast.parse(open('backend-hormonia/app/api/v2/routers/physicians/patients.py').read()); print('OK')"` — syntax check on modified endpoint
2. `python3 -c "import ast; ast.parse(open('backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py').read()); print('OK')"` — syntax check on migration
3. Verify response shape unchanged: the endpoint return type `PhysicianPatientListResponse` must remain identical (no new fields, no field removals)
4. Verify cache key includes `user_id` by reading the code (no runtime test needed)
5. Verify migration `down_revision` points to `m008_s01_t03_sessions_align`

## Constraints

- `@cache_response` decorator builds key from `[func_name, request.url.path, request.url.query]` when Request is present — does NOT include FastAPI dependency-injected params like `current_user`. This is a design limitation, not a bug — admin endpoints using it are safe because all admins see the same data.
- Alembic migration must use `down_revision = "m008_s01_t03_sessions_align"` — this is the current head.
- The `get_generic_cache` dependency returns `GenericRedisCache` with `.get(key)` and `.set(key, value, ttl=N)` interface — same as dashboard.py uses.
- `@limiter.limit("30/minute")` on the endpoint requires `request: Request` as a parameter — adding Request is consistent with this existing pattern on dashboard endpoints (though the physician endpoint doesn't have a limiter yet).

## Common Pitfalls

- **Cache key collision between doctors** — If using `@cache_response` on physician/patients, doctor A would see doctor B's patients from cache. The key must include `user_id`. Manual caching with `f"physician:patients:user:{user_id}:..."` prevents this.
- **Caching None/empty results** — If a doctor has zero patients, the result `{"items": [], "total": 0, ...}` is still valid and should be cached. The dashboard.py pattern caches truthy values (`if cached_data:`), which would skip caching empty-but-valid dict responses. Use `if cached_data is not None:` instead.
- **Import of get_generic_cache** — Must import from `app.dependencies.auth_dependencies`, not from a cache module. This is the existing pattern across dashboard.py, monitoring.py.
- **Dashboard.py already cached** — Don't add `@cache_response` on top of the existing manual caching — that would create double-caching with potentially different keys and TTLs.

## Open Risks

- The M011 context doc states "@cache_response gera cache key a partir de args/kwargs do endpoint — inclui current_user automaticamente" — this is **incorrect** based on code analysis. The `cache_response` decorator's key builder ignores non-Request kwargs when Request is present. The planner should not rely on this assumption and should use manual caching instead.
