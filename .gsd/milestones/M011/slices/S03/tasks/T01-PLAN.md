---
estimated_steps: 3
estimated_files: 2
---

# T01: Run integrated verification and validate R100/R101/R102

**Slice:** S03 — Verificação integrada
**Milestone:** M011

## Description

Terminal verification gate for M011. Create and run a single verification script that confirms all deliverables from S01 (backend caching + composite index) and S02 (frontend request discipline) are correct and integrated. This validates requirements R100 (Redis caching on hot paths), R101 (composite index on patient_flow_states), and R102 (frontend staleTime/refetchInterval discipline).

No code changes to the application — this is pure verification.

## Steps

1. **Create `verify-m011.sh`** at `.gsd/milestones/M011/slices/S03/verify-m011.sh` with 7 sequential checks, each printing PASS/FAIL and exiting non-zero on failure:

   **Check 1 — ast.parse backend files:**
   ```bash
   python3 -c "
   import ast, sys
   files = [
       'backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py',
       'backend-hormonia/app/api/v2/routers/physicians/patients.py',
       'backend-hormonia/app/api/v2/routers/dashboard.py',
   ]
   for f in files:
       ast.parse(open(f).read())
       print(f'  PASS: {f}')
   "
   ```

   **Check 2 — tsc --noEmit:**
   ```bash
   cd frontend-hormonia && npx tsc --noEmit
   ```

   **Check 3 — vite build:**
   ```bash
   cd frontend-hormonia && npx vite build
   ```

   **Check 4 — Response shape unchanged (zero schema file changes in M011):**
   ```bash
   # Check that no files in backend-hormonia/app/schemas/ were modified in the M011 worktree
   git diff origin/main --name-only -- backend-hormonia/app/schemas/ | wc -l
   # Must be 0
   ```
   If `origin/main` is not available, use `git log --oneline --all` to find the base branch and diff against it. Alternative: check that no response_model or return type annotations changed in the modified endpoint files by grepping for `response_model` and confirming they match the original.

   **Check 5 — Caching values (R100 validation):**
   ```bash
   grep -q "ttl=60" backend-hormonia/app/api/v2/routers/physicians/patients.py
   grep -q "user:{user_id}" backend-hormonia/app/api/v2/routers/physicians/patients.py  # or user_id in key
   grep -q "CACHE_TTL_REALTIME = 120" backend-hormonia/app/api/v2/routers/dashboard.py
   ```
   The patients.py key pattern is `physician:patients:user:{user_id}:...` — confirm user_id is part of the cache key to prevent cross-doctor data leaks. Note: S01 used manual `redis_cache.get/set`, not `@cache_response` decorator — grep for `redis_cache` presence, not `@cache_response`.

   **Check 6 — Timing values (R102 validation):**
   ```bash
   rg "staleTime|refetchInterval" --type ts --type-add 'tsx:*.tsx' --type tsx frontend-hormonia/src/ \
     | grep -v features/system | grep -v features/monitoring \
     | grep -v hive-mind | grep -v ClinicalMonitoring \
     | grep -v AdminMonitoringTab | grep -v hooks/api/useSystemStats \
     | grep -v features/whatsapp
   ```
   All remaining staleTime values must be ≥ 60000. All remaining refetchInterval values must be ≥ 120000. Known exceptions that are OK:
   - `queryPresets.realtime` in queryClient.ts (intentional monitoring preset)
   - Dead code files (`useOptimizedQuery.helpers.ts`, `ProductionProvider.tsx`) with zero imports

   **Check 7 — Migration chain (R101 validation):**
   ```bash
   grep -q 'down_revision = "m008_s01_t03_sessions_align"' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py
   grep -q "idx_pfs_patient_started" backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py
   grep -q "if_not_exists" backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py
   ```

2. **Run the script** and confirm all 7 checks pass.

3. **If any check fails**, diagnose and report. S03 is verification-only — if a check fails, it means S01 or S02 has a defect that was missed. Do NOT fix application code in this task; report the failure clearly.

## Must-Haves

- [ ] `verify-m011.sh` script created with all 7 checks
- [ ] ast.parse passes on all 3 backend files
- [ ] `tsc --noEmit` exits 0
- [ ] `vite build` exits 0
- [ ] Response shape unchanged (zero schema modifications)
- [ ] Caching: TTL=60 in patients.py, TTL=120 in dashboard.py, user_id in cache key, redis_cache present
- [ ] Timing: all non-monitoring staleTime ≥ 60000, refetchInterval ≥ 120000
- [ ] Migration: correct down_revision, index name, if_not_exists

## Verification

- `bash .gsd/milestones/M011/slices/S03/verify-m011.sh` exits 0
- All 7 checks print PASS

## Inputs

- S01 deliverables: `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` (composite index migration), `backend-hormonia/app/api/v2/routers/physicians/patients.py` (manual redis_cache with per-user key, TTL=60s)
- S01 confirmed unchanged: `backend-hormonia/app/api/v2/routers/dashboard.py` (TTL=120s, per-user key)
- S02 deliverables: 21 frontend files with staleTime ≥ 60s and refetchInterval ≥ 120s, `tsc --noEmit` + `vite build` already proven green
- `node_modules` already installed from S02's `npm ci`

## Expected Output

- `.gsd/milestones/M011/slices/S03/verify-m011.sh` — replayable verification script for M011
- All 7 checks passing — proves R100 (caching), R101 (index), R102 (frontend discipline) are validated
