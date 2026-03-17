# S01: Backend caching + index composto

**Goal:** physician/patients and dashboard/main endpoints return cached data from Dragonfly. Composite index on patient_flow_states(patient_id, started_at DESC) exists via Alembic migration. All modified backend files pass ast.parse.

**Demo:** physician/patients endpoint uses manual Redis caching with per-user key (TTL 60s). dashboard/main already has correct per-user caching (TTL 120s) — verified unchanged. Alembic migration creates composite index for the ROW_NUMBER() window function.

## Must-Haves

- Alembic migration `m011_s01_patient_flow_states_index` creates index `idx_pfs_patient_started` on `patient_flow_states(patient_id, started_at DESC)` with `down_revision = "m008_s01_t03_sessions_align"`
- `list_physician_patients` endpoint uses `redis_cache = Depends(get_generic_cache)` with cache key including `user_id` and all query params (page, size, search, flow_phase, flow_status), TTL=60s
- Cache key collision impossible — key format: `physician:patients:user:{user_id}:page:{page}:size:{size}:search:{search}:phase:{flow_phase}:status:{flow_status}`
- `dashboard.py` `get_main_dashboard` caching remains unchanged (already correct: per-user key, TTL=120s)
- Response shape (`PhysicianPatientListResponse`) unchanged — same fields, same types
- All modified files pass `python3 -c "import ast; ast.parse(...)"`

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

- `python3 -c "import ast; ast.parse(open('backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py').read()); print('OK')"`
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/api/v2/routers/physicians/patients.py').read()); print('OK')"`
- Migration `down_revision` equals `"m008_s01_t03_sessions_align"`
- `grep -c "redis_cache" backend-hormonia/app/api/v2/routers/physicians/patients.py` returns ≥ 3 (import/depend/get/set)
- `grep "user:{user_id}" backend-hormonia/app/api/v2/routers/physicians/patients.py` confirms user_id in cache key
- `grep "ttl=60" backend-hormonia/app/api/v2/routers/physicians/patients.py` confirms TTL
- `grep "CACHE_TTL_REALTIME = 120" backend-hormonia/app/api/v2/routers/dashboard.py` confirms dashboard TTL unchanged
- Response model `PhysicianPatientListResponse` not modified (no changes to schema file)
- Failure-path: `python3 -c "import ast; ast.parse(open('backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py').read())"` exits 0 (migration not corrupted); `alembic -c backend-hormonia/alembic.ini history` shows linear chain without branch splits (no fork from parallel migrations)

## Observability / Diagnostics

- Runtime signals: `logger.debug(f"Cache hit for physician patients: {cache_key}")` on cache hit (matches dashboard.py pattern)
- Inspection surfaces: Redis keys matching `physician:patients:user:*` visible in Dragonfly CLI
- Failure visibility: cache miss falls through to DB query silently — no error, just slower
- Redaction constraints: none (cache key contains user UUID, not PII)

## Integration Closure

- Upstream surfaces consumed: `get_generic_cache` from `app.dependencies.auth_dependencies`, `GenericRedisCache.get/set` interface, Alembic migration chain head `m008_s01_t03_sessions_align`
- New wiring introduced in this slice: `redis_cache` dependency injection in physician/patients endpoint
- What remains before the milestone is truly usable end-to-end: S02 (frontend request discipline), S03 (integrated verification)

## Tasks

- [x] **T01: Create Alembic migration for patient_flow_states composite index** `est:20m`
  - Why: The ROW_NUMBER() window function in physician/patients does `PARTITION BY patient_id ORDER BY started_at DESC` — without a composite index this is a sequential scan per patient. Covers R101.
  - Files: `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
  - Do: Write Alembic migration with `revision = "m011_s01_patient_flow_states_index"`, `down_revision = "m008_s01_t03_sessions_align"`. Create index `idx_pfs_patient_started` on table `patient_flow_states` columns `(patient_id, sa.text("started_at DESC"))`. Use `if_not_exists=True` for safety. Downgrade drops the index.
  - Verify: `python3 -c "import ast; ast.parse(open('backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py').read()); print('OK')"` and grep confirms `down_revision = "m008_s01_t03_sessions_align"`.
  - Done when: Migration file exists, parses clean, has correct down_revision and creates the composite index.

- [x] **T02: Add manual Redis caching to physician/patients endpoint** `est:30m`
  - Why: The physician patient list endpoint hits the DB on every request with a heavy window function query. Adding per-user Redis caching with TTL=60s eliminates redundant queries. Covers R100. Also verifies dashboard.py needs no changes (already correctly cached per D019).
  - Files: `backend-hormonia/app/api/v2/routers/physicians/patients.py`
  - Do: (1) Add imports: `get_generic_cache` from `app.dependencies.auth_dependencies`, `json` stdlib. (2) Add `redis_cache=Depends(get_generic_cache)` parameter to `list_physician_patients`. (3) Extract `user_id` from `current_user` (use `current_user.id` or `current_user.get("id")`). (4) Build cache key: `f"physician:patients:user:{user_id}:page:{page}:size:{size}:search:{search}:phase:{flow_phase}:status:{flow_status}"`. (5) Before the DB query block, try `cached_data = await redis_cache.get(cache_key)` — if `cached_data is not None`, return it (use `is not None` to cache empty results). (6) After building the response dict, `await redis_cache.set(cache_key, response_data, ttl=60)`. (7) Add `logger.debug(f"Cache hit for physician patients: {cache_key}")` on hit. (8) **Do NOT modify dashboard.py** — verify it already has correct caching (TTL=120s, user_id in key). (9) **Do NOT modify the response schema** — `PhysicianPatientListResponse` fields stay identical.
  - Verify: `python3 -c "import ast; ast.parse(open('backend-hormonia/app/api/v2/routers/physicians/patients.py').read()); print('OK')"` plus grep checks for `redis_cache`, `user_id` in key, `ttl=60`.
  - Done when: Endpoint has per-user caching with TTL=60s, cache key includes user_id + all query params, ast.parse passes, response shape unchanged, dashboard.py confirmed unchanged.

## Files Likely Touched

- `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` (new)
- `backend-hormonia/app/api/v2/routers/physicians/patients.py` (modified)
