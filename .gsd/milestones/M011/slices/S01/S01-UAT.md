# S01: Backend caching + index composto — UAT

**Milestone:** M011
**Written:** 2026-03-17

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: This slice adds a database index and Redis caching layer — both are backend infrastructure changes with no UI impact. Verification is fully achievable by inspecting the artifacts (migration file, endpoint code) and running static checks (ast.parse, grep for expected patterns). No live runtime or human experience testing is needed at this stage; S03 will do integrated verification.

## Preconditions

- Working directory contains `backend-hormonia/` with the modified files
- Python 3.x available for `ast.parse` checks
- `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` exists
- `backend-hormonia/app/api/v2/routers/physicians/patients.py` exists with caching changes
- `backend-hormonia/app/api/v2/routers/dashboard.py` exists and is unmodified

## Smoke Test

Run `python3 -c "import ast; ast.parse(open('backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py').read()); ast.parse(open('backend-hormonia/app/api/v2/routers/physicians/patients.py').read()); print('SMOKE OK')"` — must print `SMOKE OK` without errors.

## Test Cases

### 1. Migration file is valid and correctly chained

1. Run: `python3 -c "import ast; ast.parse(open('backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py').read()); print('OK')"`
2. Run: `grep 'down_revision' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
3. Run: `grep 'revision = ' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
4. **Expected:** ast.parse exits 0, `down_revision = "m008_s01_t03_sessions_align"`, `revision = "m011_s01_patient_flow_states_index"`

### 2. Migration creates the correct composite index

1. Run: `grep 'idx_pfs_patient_started' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
2. Run: `grep 'started_at DESC' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
3. Run: `grep 'patient_flow_states' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
4. Run: `grep 'if_not_exists' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
5. **Expected:** Index name `idx_pfs_patient_started` present in both upgrade and downgrade. `started_at DESC` in `sa.text()`. Table `patient_flow_states`. `if_not_exists=True` present.

### 3. Migration downgrade drops the index

1. Run: `grep 'drop_index' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
2. **Expected:** `op.drop_index("idx_pfs_patient_started", table_name="patient_flow_states")` present in downgrade function.

### 4. Physician/patients endpoint has Redis caching with correct TTL

1. Run: `python3 -c "import ast; ast.parse(open('backend-hormonia/app/api/v2/routers/physicians/patients.py').read()); print('OK')"`
2. Run: `grep -c 'redis_cache' backend-hormonia/app/api/v2/routers/physicians/patients.py`
3. Run: `grep 'ttl=60' backend-hormonia/app/api/v2/routers/physicians/patients.py`
4. **Expected:** ast.parse exits 0. `redis_cache` appears ≥ 3 times (import, Depends, get/set). `ttl=60` present in `redis_cache.set()` call.

### 5. Cache key includes user_id and all query params

1. Run: `grep 'user:{user_id}' backend-hormonia/app/api/v2/routers/physicians/patients.py`
2. Run: `grep 'page:{page}' backend-hormonia/app/api/v2/routers/physicians/patients.py`
3. Run: `grep 'search:{search}' backend-hormonia/app/api/v2/routers/physicians/patients.py`
4. Run: `grep 'phase:{flow_phase}' backend-hormonia/app/api/v2/routers/physicians/patients.py`
5. Run: `grep 'status:{flow_status}' backend-hormonia/app/api/v2/routers/physicians/patients.py`
6. **Expected:** All 5 query params plus user_id present in the cache key format string.

### 6. Cache read uses `is not None` to cache empty results

1. Run: `grep 'is not None' backend-hormonia/app/api/v2/routers/physicians/patients.py`
2. **Expected:** `if cached_data is not None:` present — ensures empty result sets `{"items": [], "total": 0}` are served from cache rather than hitting the DB again.

### 7. Dashboard caching is unchanged

1. Run: `grep 'CACHE_TTL_REALTIME = 120' backend-hormonia/app/api/v2/routers/dashboard.py`
2. **Expected:** Dashboard TTL remains at 120 seconds — no modifications to dashboard.py.

### 8. Response schema files are not modified

1. Run: `git diff --name-only HEAD -- 'backend-hormonia/app/api/v2/routers/physicians/schemas*' 'backend-hormonia/app/schemas*'`
2. **Expected:** Empty output — no schema files were changed, response shape is identical.

## Edge Cases

### Redis failure resilience

1. Inspect `backend-hormonia/app/api/v2/routers/physicians/patients.py` for try/except around `redis_cache.get()` and `redis_cache.set()`.
2. **Expected:** Both cache read and write are wrapped in try/except, with `logger.debug` logging the failure. The endpoint falls through to the DB query silently — no user-facing error.

### Cache key uniqueness across doctors

1. Verify cache key contains `user:{user_id}` — two doctors requesting the same page/size/search/phase/status get different cache keys.
2. **Expected:** Doctor A sees only their patients; Doctor B sees only theirs. No cross-contamination possible because user_id is part of the key.

### User_id extraction robustness

1. Inspect `patients.py` for `hasattr(current_user, 'id')` guard.
2. **Expected:** Works whether `current_user` is an object with `.id` attribute or a dict with `["id"]` key.

## Failure Signals

- `ast.parse` raises `SyntaxError` — file has broken Python syntax
- `redis_cache` count < 3 — caching not fully wired (missing import, Depends, or get/set)
- `user_id` absent from cache key — cross-doctor data leak risk
- `ttl=60` absent — cache lives forever or uses wrong TTL
- `CACHE_TTL_REALTIME` changed from 120 — dashboard caching was accidentally modified
- Schema files appear in git diff — response shape was inadvertently changed
- `down_revision` doesn't match `m008_s01_t03_sessions_align` — migration chain broken

## Requirements Proved By This UAT

- R100 — physician/patients and dashboard/main use Redis caching with per-user keys and appropriate TTLs (60s and 120s respectively)
- R101 — composite index on patient_flow_states(patient_id, started_at DESC) exists in a valid Alembic migration

## Not Proven By This UAT

- Actual runtime cache hit performance improvement (requires live stack with load)
- Index scan vs seq scan improvement on real data (requires `EXPLAIN ANALYZE` on populated DB)
- Cache invalidation correctness when patient data mutates (TTL-based only, no active invalidation tested)
- End-to-end response shape fidelity under caching (S03 scope)

## Notes for Tester

- This is a backend-only slice — no UI changes to verify.
- The migration has NOT been applied to any running database yet. It will be applied when `alembic upgrade head` runs against the live or dev database.
- The caching is manual (get/set) not decorator-based (@cache_response) — this is intentional per D019 to support user_id-scoped keys.
- Dashboard.py was intentionally not modified — it already had correct caching.
