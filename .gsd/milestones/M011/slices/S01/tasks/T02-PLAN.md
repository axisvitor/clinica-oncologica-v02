---
estimated_steps: 6
estimated_files: 2
---

# T02: Add manual Redis caching to physician/patients endpoint

**Slice:** S01 — Backend caching + index composto
**Milestone:** M011

## Description

Add per-user Redis caching to the `list_physician_patients` endpoint in `backend-hormonia/app/api/v2/routers/physicians/patients.py` with TTL=60s. Follow the **exact manual caching pattern** already proven in `backend-hormonia/app/api/v2/routers/dashboard.py` — do NOT use the `@cache_response` decorator because it does not include `user_id` in the cache key when a Request object is present, causing cross-doctor data leaks.

The cache key must include `user_id` and all query parameters to prevent cache collisions between different doctors or different filter combinations.

Also verify that `dashboard.py`'s existing caching (TTL=120s, per-user key) is already correct and needs no modification — this is a confirmation step, not a code change.

**Critical: Do NOT modify the response schema `PhysicianPatientListResponse`** — field names, types, and structure must stay identical.

## Steps

1. Add imports to `backend-hormonia/app/api/v2/routers/physicians/patients.py`:
   - `from app.dependencies.auth_dependencies import get_generic_cache` (add to existing import line that already imports `get_current_user_from_session`)
2. Add `redis_cache=Depends(get_generic_cache)` as a new parameter to the `list_physician_patients` function signature
3. After the function docstring and before the subquery block, extract user_id: `user_id = current_user.id if hasattr(current_user, "id") else current_user.get("id")` (the function uses both `.id` attribute access and dict-style in different places — handle both)
4. Build the cache key: `cache_key = f"physician:patients:user:{user_id}:page:{page}:size:{size}:search:{search}:phase:{flow_phase}:status:{flow_status}"`
5. Add cache-check block before the subquery:
   ```python
   # Try cache first
   try:
       cached_data = await redis_cache.get(cache_key)
       if cached_data is not None:
           logger.debug(f"Cache hit for physician patients: {cache_key}")
           return cached_data
   except Exception:
       logger.debug("Redis cache read failed, falling through to DB")
   ```
   Use `is not None` (not `if cached_data:`) so empty-but-valid responses like `{"items": [], "total": 0, ...}` are served from cache.
6. After building the final response (the `return PhysicianPatientListResponse(...)` at the end), restructure to:
   - Build the response object: `response = PhysicianPatientListResponse(items=items, total=total, page=page, size=size)`
   - Cache the serialized response: wrap in try/except so cache failures don't break the endpoint
   ```python
   try:
       await redis_cache.set(cache_key, response.model_dump(), ttl=60)
   except Exception:
       logger.debug("Redis cache write failed, continuing without cache")
   ```
   - Return the response: `return response`

**Important implementation notes:**
- The `get_generic_cache` dependency comes from `app.dependencies.auth_dependencies` (same module already imported for `get_current_user_from_session`)
- The `GenericRedisCache` returned by `get_generic_cache` has `.get(key)` → returns deserialized data or None, and `.set(key, value, ttl=N)` — same interface used in dashboard.py
- Look at dashboard.py lines 93-167 for the reference pattern (already confirmed working)
- `current_user` in this endpoint is the return of `get_current_user_from_session` — check if it returns a dict or object. The endpoint currently accesses `current_user.id` and `current_user.role` as attributes, so use attribute access
- Wrap cache operations in try/except to be resilient to Redis downtime

**Dashboard.py verification (no changes):**
- Confirm `CACHE_TTL_REALTIME = 120` exists at module level
- Confirm cache key includes `user:{user_id}` 
- Confirm `redis_cache=Depends(get_generic_cache)` is in the function signature
- Report these confirmations — do not modify dashboard.py

## Must-Haves

- [ ] `redis_cache=Depends(get_generic_cache)` in `list_physician_patients` signature
- [ ] Cache key includes `user_id` and all 5 query params (page, size, search, flow_phase, flow_status)
- [ ] TTL = 60 seconds
- [ ] `is not None` check (not truthy check) to cache empty results
- [ ] Cache read/write wrapped in try/except for Redis resilience
- [ ] Response schema `PhysicianPatientListResponse` NOT modified
- [ ] File passes `ast.parse`
- [ ] dashboard.py confirmed unchanged (TTL=120s, user_id in key)

## Verification

- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/api/v2/routers/physicians/patients.py').read()); print('OK')"` → prints OK
- `grep -c "redis_cache" backend-hormonia/app/api/v2/routers/physicians/patients.py` → ≥ 3
- `grep "user:{user_id}" backend-hormonia/app/api/v2/routers/physicians/patients.py` → match confirming user_id in key
- `grep "ttl=60" backend-hormonia/app/api/v2/routers/physicians/patients.py` → match
- `grep "is not None" backend-hormonia/app/api/v2/routers/physicians/patients.py` → match for cache check
- `grep "CACHE_TTL_REALTIME = 120" backend-hormonia/app/api/v2/routers/dashboard.py` → match (unchanged)
- Schema file not modified: `git diff --name-only` does NOT include any schema files under `schemas/v2/physician_patients.py`

## Inputs

- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — current endpoint (131 lines, no caching, no Request param)
- `backend-hormonia/app/api/v2/routers/dashboard.py` — reference caching pattern (lines 93-167 show get_generic_cache usage with per-user key)
- `backend-hormonia/app/dependencies/auth_dependencies.py` — `get_generic_cache()` at line 298 returns `GenericRedisCache`
- T01 completed: Alembic migration for composite index exists

## Expected Output

- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — modified with Redis caching (per-user key, TTL=60s, try/except resilience)
- `backend-hormonia/app/api/v2/routers/dashboard.py` — confirmed unchanged (no modifications)
