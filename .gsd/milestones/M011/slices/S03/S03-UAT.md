# S03: Verificação integrada — UAT

**Milestone:** M011
**Written:** 2026-03-17

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: M011 roadmap specifies contract + integration verification only (no operational verification, no UAT/human verification). The verification script is the canonical proof artifact.

## Preconditions

- Git repository checked out with M011 S01 and S02 changes applied
- Node.js and npm available (for tsc and vite build)
- Python 3.x available (for ast.parse and timing value evaluation)
- No runtime services needed (no PostgreSQL, no Redis, no backend server)

## Smoke Test

Run `bash verify-m011.sh` — should exit 0 with `7/7 passed, 0 failed` in the summary line.

## Test Cases

### 1. Full integrated verification (all 7 groups)

1. Run `bash verify-m011.sh`
2. **Expected:** Output shows `[1/7] ast.parse` through `[7/7] Migration chain`, each with `✅ PASS`
3. **Expected:** Summary line reads `Results: 7/7 passed, 0 failed`
4. **Expected:** Final line reads `✅ M011 verification PASSED — all 7 check groups green`
5. **Expected:** Exit code is 0 (`echo $?` → 0)

### 2. Backend Python syntax (ast.parse)

1. Run `python3 -c "import ast; ast.parse(open('backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py').read())"`
2. Run same for `backend-hormonia/app/api/v2/routers/physicians/patients.py`
3. Run same for `backend-hormonia/app/api/v2/routers/dashboard.py`
4. **Expected:** All three exit 0 with no output (valid Python)

### 3. TypeScript compilation

1. Run `cd frontend-hormonia && npx tsc --noEmit`
2. **Expected:** Exit 0, no errors

### 4. Production build

1. Run `cd frontend-hormonia && npx vite build`
2. **Expected:** Exit 0, dist/ directory produced with JS bundles

### 5. Response shape unchanged

1. Run `git log --oneline --all -- backend-hormonia/app/schemas/ | grep -E "M011|S01.*T0|S02.*T0"`
2. **Expected:** No output — no M011 commits touched schema files
3. Run `grep -c "response_model" backend-hormonia/app/api/v2/routers/physicians/patients.py`
4. **Expected:** At least 1 match
5. Run `grep -c "response_model" backend-hormonia/app/api/v2/routers/dashboard.py`
6. **Expected:** At least 1 match

### 6. Caching values

1. Run `grep "ttl=60" backend-hormonia/app/api/v2/routers/physicians/patients.py`
2. **Expected:** Match found — physician endpoint uses 60s TTL
3. Run `grep "CACHE_TTL_REALTIME = 120" backend-hormonia/app/api/v2/routers/dashboard.py`
4. **Expected:** Match found — dashboard uses 120s TTL
5. Run `grep "user:{user_id}" backend-hormonia/app/api/v2/routers/physicians/patients.py`
6. **Expected:** Match found — cache key includes user_id (no cross-doctor data leaks)

### 7. Timing values discipline

1. Run `rg "staleTime" frontend-hormonia/src/ --no-filename` and manually verify all non-monitoring values ≥ 60000
2. Run `rg "refetchInterval" frontend-hormonia/src/ --no-filename` and manually verify all non-monitoring values ≥ 120000
3. Monitoring exclusions (do NOT need to comply): files in `features/system`, `features/monitoring`, `hive-mind`, `ClinicalMonitoring`, `AdminMonitoringTab`, `useSystemStats`, `features/whatsapp`, `useOptimizedQuery`, `ProductionProvider`, `queryPresets.realtime` block in queryClient.ts
4. **Expected:** Zero violations outside monitoring exclusions

### 8. Migration chain

1. Run `grep "down_revision" backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
2. **Expected:** Contains `m008_s01_t03_sessions_align`
3. Run `grep "idx_pfs_patient_started" backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
4. **Expected:** Index name found in both upgrade and downgrade functions

## Edge Cases

### Re-run idempotency

1. Run `bash verify-m011.sh` twice consecutively
2. **Expected:** Both runs produce identical PASS results — script has no side effects, no mutations

### Missing node_modules

1. Remove `frontend-hormonia/node_modules` (or run in clean checkout)
2. Run `bash verify-m011.sh`
3. **Expected:** Script either runs `npm ci` as part of tsc/vite steps or fails clearly at group 2 or 3 with an actionable error message

## Failure Signals

- Any `❌ FAIL` label in verify-m011.sh output indicates a broken check group
- Exit code non-zero from verify-m011.sh
- `tsc --noEmit` producing errors → frontend type regressions
- `vite build` failing → frontend build regressions
- `ast.parse` failing → Python syntax errors in backend files
- Cache TTL values not matching expected (60/120) → caching misconfiguration
- staleTime < 60000 outside monitoring → request discipline violation

## Requirements Proved By This UAT

- R100 — Backend caching on physician/patients (TTL=60s) and dashboard/main (TTL=120s) with per-user cache keys
- R101 — Composite index `idx_pfs_patient_started` on `patient_flow_states(patient_id, started_at DESC)` via Alembic migration
- R102 — Frontend hooks with staleTime ≥ 60s and refetchInterval ≥ 120s (monitoring exempt)

## Not Proven By This UAT

- Actual Redis cache hit/miss behavior at runtime (no running Redis)
- Actual PostgreSQL query plan improvement from the composite index (no running database)
- Actual reduction in network requests from a browser (no running frontend)
- These are operational verification items explicitly excluded from M011's verification scope

## Notes for Tester

- The verification is contract-level by design — M011 roadmap explicitly states no operational or UAT verification is required.
- `verify-m011.sh` is the single source of truth for milestone closure. All 7 groups must pass.
- The monitoring exclusion list in group 6 is intentional — real-time monitoring hooks need faster refresh rates for operational awareness.
- If `npm ci` hasn't been run, groups 2 and 3 will fail — run `cd frontend-hormonia && npm ci` first.
