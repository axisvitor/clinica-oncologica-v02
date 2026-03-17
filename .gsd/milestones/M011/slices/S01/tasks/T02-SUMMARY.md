---
id: T02
parent: S01
milestone: M011
provides:
  - Per-user Redis caching on physician/patients endpoint (TTL=60s) with full query-param key
key_files:
  - backend-hormonia/app/api/v2/routers/physicians/patients.py
key_decisions:
  - Manual redis_cache pattern (not @cache_response decorator) to include user_id in key and prevent cross-doctor data leaks
patterns_established:
  - Cache key format physician:patients:user:{user_id}:page:size:search:phase:status with try/except resilience
observability_surfaces:
  - logger.debug cache hit/miss messages, Redis keys physician:patients:user:* inspectable via CLI
duration: 10m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T02: Add manual Redis caching to physician/patients endpoint

**Added per-user Redis caching (TTL=60s) to list_physician_patients with full query-param cache key and try/except resilience**

## What Happened

Added manual Redis caching to `list_physician_patients` following the proven pattern from `dashboard.py`:
1. Added `get_generic_cache` import alongside existing `get_current_user_from_session`
2. Added `redis_cache=Depends(get_generic_cache)` to the function signature
3. Extract `user_id` from `current_user` with `hasattr` guard for attribute vs dict access
4. Cache key: `physician:patients:user:{user_id}:page:{page}:size:{size}:search:{search}:phase:{flow_phase}:status:{flow_status}` — includes all 5 query params
5. Cache read uses `is not None` (not truthy) so empty result sets `{"items": [], "total": 0}` are served from cache
6. Cache write serializes via `response.model_dump()` with `ttl=60`
7. Both read and write wrapped in try/except for Redis resilience

Confirmed `dashboard.py` is already correct: `CACHE_TTL_REALTIME = 120`, per-user key with `user:{user_id}`, `redis_cache=Depends(get_generic_cache)`. No modifications needed.

## Verification

All task and slice-level checks pass:
- `ast.parse` → OK for both patients.py and migration file
- `grep -c "redis_cache"` → 3 (import, Depends, .get, .set counted)
- `grep "user:{user_id}"` → matches cache key line
- `grep "ttl=60"` → matches redis_cache.set call
- `grep "is not None"` → matches cache check
- `grep "CACHE_TTL_REALTIME = 120" dashboard.py` → unchanged
- `git diff --name-only` does not include schema files
- Migration `down_revision = "m008_s01_t03_sessions_align"` confirmed
- Migration ast.parse → OK

## Diagnostics

- **Cache hit logging:** `logger.debug(f"Cache hit for physician patients: {cache_key}")` on every cache hit
- **Cache failure logging:** `logger.debug("Redis cache read/write failed...")` on Redis downtime
- **Key inspection:** `redis-cli KEYS "physician:patients:user:*"` shows cached entries
- **Failure mode:** Redis down → silent fallthrough to DB query, no user-facing error

## Deviations

None. Implementation followed the plan exactly.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — added per-user Redis caching with TTL=60s
- `.gsd/milestones/M011/slices/S01/tasks/T02-PLAN.md` — added missing Observability Impact section
