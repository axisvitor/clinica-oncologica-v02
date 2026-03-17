# S03 — Verificação integrada — Research

**Date:** 2026-03-17
**Depth:** Light — pure verification slice, no new code, all deliverables already exist from S01+S02.

## Summary

S03 is the terminal verification gate for M011. S01 delivered backend caching (manual redis_cache on physician/patients with TTL=60s, dashboard unchanged at TTL=120s) plus the Alembic composite index migration. S02 normalized staleTime/refetchInterval across 21 frontend files and proved `tsc --noEmit` + `vite build` green. S03 runs the integrated proof that confirms all deliverables work together and the milestone Definition of Done is met.

There are no unknowns. Both dependency slices completed successfully with passing verification. The only work is re-running the checks in a single integrated pass and confirming response shape is unchanged (zero schema file modifications in M011).

## Recommendation

Single task executing all verification checks in sequence: ast.parse backend files → tsc --noEmit → vite build → response shape audit → caching/timing value grep audit. No code changes expected.

## Implementation Landscape

### Key Files

**Backend (S01 deliverables to verify):**
- `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` — Alembic migration: composite index `idx_pfs_patient_started` on `patient_flow_states(patient_id, started_at DESC)`, `down_revision = "m008_s01_t03_sessions_align"`, `if_not_exists=True`
- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — Manual redis_cache.get/set with per-user key (`physician:patients:user:{user_id}:...`), TTL=60s, try/except resilience
- `backend-hormonia/app/api/v2/routers/dashboard.py` — Pre-existing caching with `CACHE_TTL_REALTIME = 120`, confirmed unchanged by S01

**Frontend (S02 deliverables to verify):**
- `frontend-hormonia/src/lib/react-query/queryClient.ts` — Global default staleTime=60s
- 21 hook/component files — staleTime ≥ 60s (dashboard/patient) or ≥ 120s (admin), refetchInterval ≥ 120s everywhere except monitoring

### Build Order

Single verification pass — no dependencies between checks, but logical order is:

1. **ast.parse** on the 2 modified backend .py files (migration + patients.py)
2. **tsc --noEmit** (frontend type check)
3. **vite build** (frontend production build)
4. **Response shape audit** — confirm zero changes to `backend-hormonia/app/schemas/` and no response_model/return-type changes in the modified endpoint files
5. **Caching value audit** — grep confirm TTL=60 in patients.py, TTL=120 in dashboard.py, user_id in cache key
6. **Timing value audit** — grep confirm staleTime ≥ 60000 and refetchInterval ≥ 120000 outside monitoring exclusions
7. **Migration chain** — confirm down_revision points to `m008_s01_t03_sessions_align` and index name is `idx_pfs_patient_started`

### Verification Approach

```bash
# 1. ast.parse backend files
python3 -c "
import ast
for f in [
    'backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py',
    'backend-hormonia/app/api/v2/routers/physicians/patients.py',
    'backend-hormonia/app/api/v2/routers/dashboard.py',
]:
    ast.parse(open(f).read())
    print(f'OK: {f}')
"

# 2. tsc --noEmit
cd frontend-hormonia && npx tsc --noEmit

# 3. vite build
cd frontend-hormonia && npx vite build

# 4. Response shape — zero schema changes
git diff <S01_base_commit>..HEAD --name-only -- backend-hormonia/app/schemas/
# Must be empty

# 5. Caching values
grep "ttl=60" backend-hormonia/app/api/v2/routers/physicians/patients.py
grep "CACHE_TTL_REALTIME = 120" backend-hormonia/app/api/v2/routers/dashboard.py
grep "user:{user_id}" backend-hormonia/app/api/v2/routers/physicians/patients.py

# 6. Timing values (S02 canonical audit)
rg "staleTime|refetchInterval" --type ts --type-add 'tsx:*.tsx' --type tsx frontend-hormonia/src/ \
  | grep -v features/system | grep -v features/monitoring \
  | grep -v hive-mind | grep -v ClinicalMonitoring \
  | grep -v AdminMonitoringTab | grep -v hooks/api/useSystemStats \
  | grep -v features/whatsapp

# 7. Migration chain
grep "down_revision" backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py
grep "idx_pfs_patient_started" backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py
```

All checks must pass for milestone Definition of Done.

## Constraints

- `node_modules` already exists from S02's `npm ci` — no reinstall needed unless corrupted
- The Alembic migration cannot be applied without a running PostgreSQL — structural verification via ast.parse and grep is sufficient for this verification class (contract verification per roadmap)
- `queryPresets.realtime` (staleTime=10s) is an intentional monitoring exception — the timing audit must exclude it
