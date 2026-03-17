---
id: S01
parent: M011
milestone: M011
provides:
  - Alembic migration creating composite index idx_pfs_patient_started on patient_flow_states(patient_id, started_at DESC)
  - Per-user Redis caching on physician/patients endpoint (TTL=60s) with full query-param cache key
  - Dashboard caching confirmed unchanged (TTL=120s, per-user key)
requires: []
affects:
  - S03
key_files:
  - backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py
  - backend-hormonia/app/api/v2/routers/physicians/patients.py
key_decisions:
  - Manual redis_cache.get/set pattern (not @cache_response decorator) to include user_id in key and prevent cross-doctor data leaks (D019 covers strategy)
patterns_established:
  - Cache key format physician:patients:user:{user_id}:page:{page}:size:{size}:search:{search}:phase:{flow_phase}:status:{flow_status} with try/except resilience
  - Use if_not_exists=True on create_index for idempotent Alembic migrations
observability_surfaces:
  - logger.debug cache hit/miss/failure messages on physician/patients endpoint
  - Redis keys physician:patients:user:* inspectable via Dragonfly CLI
  - pg_indexes query for idx_pfs_patient_started after migration
  - alembic current shows m011_s01_patient_flow_states_index as head after upgrade
drill_down_paths:
  - .gsd/milestones/M011/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M011/slices/S01/tasks/T02-SUMMARY.md
duration: 15m
verification_result: passed
completed_at: 2026-03-17
---

# S01: Backend caching + index composto

**Alembic composite index on patient_flow_states for ROW_NUMBER() acceleration, plus per-user Redis caching (TTL=60s) on physician/patients endpoint with try/except resilience**

## What Happened

Two tasks delivered the backend optimization layer:

**T01 — Composite index migration.** Created Alembic migration `m011_s01_patient_flow_states_index` chaining from `m008_s01_t03_sessions_align`. The upgrade creates index `idx_pfs_patient_started` on `patient_flow_states(patient_id, sa.text("started_at DESC"))` with `if_not_exists=True` for idempotent re-runs. The downgrade drops the index. This index directly accelerates the `ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY started_at DESC)` window function used in the physician/patients endpoint — converting a sequential scan + in-memory sort to an index scan.

**T02 — Per-user Redis caching.** Added manual Redis caching to `list_physician_patients` following the proven pattern from `dashboard.py`. The implementation: (1) imports `get_generic_cache` and adds `redis_cache=Depends(get_generic_cache)` to the function signature, (2) extracts `user_id` from `current_user` with `hasattr` guard for attribute vs dict access, (3) builds a cache key including all 5 query params (`page`, `size`, `search`, `flow_phase`, `flow_status`) plus `user_id` — making key collision between doctors impossible, (4) uses `is not None` for cache check so empty result sets are served from cache, (5) wraps both read and write in try/except so Redis downtime falls through silently to the DB query. Confirmed `dashboard.py` already has correct caching (TTL=120s, per-user key) — no modifications needed.

## Verification

All 8 slice-level checks passed:

1. `ast.parse` migration file → OK
2. `ast.parse` patients.py → OK
3. `down_revision = "m008_s01_t03_sessions_align"` → match
4. `grep -c "redis_cache" patients.py` → 3 (import, Depends, get/set)
5. `grep "user:{user_id}" patients.py` → confirms user_id in cache key
6. `grep "ttl=60" patients.py` → confirms TTL
7. `grep "CACHE_TTL_REALTIME = 120" dashboard.py` → dashboard unchanged
8. `git diff --name-only` on schema/model files → empty (response shape unchanged)

Additional checks: `idx_pfs_patient_started` present in upgrade and downgrade, `if_not_exists=True` present, `is not None` cache check present, `Cache hit` and cache failure debug logging present.

## Requirements Advanced

- R100 — physician/patients endpoint now uses manual Redis caching with per-user key and TTL=60s. Dashboard caching confirmed unchanged at TTL=120s. Both endpoints serve cached data from Dragonfly, eliminating redundant DB queries.
- R101 — Composite index `idx_pfs_patient_started` on `patient_flow_states(patient_id, started_at DESC)` created via Alembic migration, enabling index scan for the ROW_NUMBER() window function.

## Requirements Validated

- None — R100 and R101 are advanced but not yet validated. Full validation requires S03's integrated verification (confirming response shape unchanged end-to-end, migration applies cleanly in the Alembic chain).

## New Requirements Surfaced

- None

## Requirements Invalidated or Re-scoped

- None

## Deviations

None. Both tasks followed the plan exactly.

## Known Limitations

- Cache invalidation is TTL-based only — no active invalidation when patient data changes. The 60s TTL is short enough that this is acceptable for clinical workflows.
- Redis failure is silent (try/except fallthrough) — no alerting mechanism if Dragonfly goes down. The endpoint continues working but without cache benefit.
- The composite index migration uses `if_not_exists=True` but does not use `CREATE INDEX CONCURRENTLY` — on very large tables, this could briefly lock writes during migration.

## Follow-ups

- S02 must align frontend staleTime with backend TTL (≥ 60s physician, ≥ 120s dashboard) to avoid fetching the same cached data repeatedly.
- S03 must verify the complete integration: backend caching + frontend discipline + response shape unchanged.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` — new Alembic migration creating composite index for ROW_NUMBER() optimization
- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — added per-user Redis caching with TTL=60s and try/except resilience

## Forward Intelligence

### What the next slice should know
- The physician/patients endpoint uses **manual** `redis_cache.get()`/`redis_cache.set()` — not the `@cache_response` decorator. This is intentional: the decorator doesn't support user_id-scoped keys needed to prevent cross-doctor data leaks.
- Dashboard caching was already correct and was intentionally left unchanged. Don't re-implement it.
- The Alembic migration chain head is now `m011_s01_patient_flow_states_index` (was `m008_s01_t03_sessions_align`).

### What's fragile
- Cache key format `physician:patients:user:{user_id}:page:{page}:size:{size}:search:{search}:phase:{flow_phase}:status:{flow_status}` — if new query params are added to the endpoint, the cache key must be updated or stale results will be served for the new param's different values.
- The `hasattr(current_user, 'id')` guard handles both attribute and dict access for `user_id` — if `current_user` shape changes, this guard needs review.

### Authoritative diagnostics
- `redis-cli KEYS "physician:patients:user:*"` — shows all cached entries; empty means cache is not being hit
- `logger.debug` messages at `Cache hit for physician patients:` and `Redis cache read/write failed` — check application logs for cache behavior
- `SELECT indexname FROM pg_indexes WHERE tablename = 'patient_flow_states'` — should show `idx_pfs_patient_started` after migration

### What assumptions changed
- The roadmap mentioned `@cache_response` decorator — the plan correctly refined this to manual redis_cache pattern because user_id-scoped keys are needed. This was planned, not a deviation.
