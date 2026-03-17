---
estimated_steps: 5
estimated_files: 1
---

# T01: Create and run verify-m011.sh integrated verification script

**Slice:** S03 — Verificação integrada
**Milestone:** M011

## Description

Create a replayable `verify-m011.sh` script at the project root that runs 7 integrated check groups covering all three M011 requirements (R100, R101, R102). The script consolidates checks from S01 and S02 into a single milestone-closing proof. No code changes — pure verification.

The 7 check groups:
1. **ast.parse** — Parse 3 backend Python files (migration, patients.py, dashboard.py)
2. **tsc --noEmit** — Frontend TypeScript compilation
3. **vite build** — Frontend production build
4. **Response shape** — Confirm zero changes to `backend-hormonia/app/schemas/` across M011
5. **Caching values** — Grep confirm TTL=60 in patients.py, TTL=120 in dashboard.py, user_id in cache key
6. **Timing values** — Grep confirm staleTime ≥ 60000 and refetchInterval ≥ 120000 outside monitoring exclusions (monitoring/system/whatsapp/hive-mind are intentionally exempt)
7. **Migration chain** — Confirm down_revision = `m008_s01_t03_sessions_align` and index name = `idx_pfs_patient_started`

## Steps

1. Create `verify-m011.sh` at project root with all 7 check groups. Each group prints a clear PASS/FAIL label. The script tracks failures and exits non-zero if any group fails.

2. For the **ast.parse** check (group 1), use:
   ```bash
   python3 -c "
   import ast
   for f in [
       'backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py',
       'backend-hormonia/app/api/v2/routers/physicians/patients.py',
       'backend-hormonia/app/api/v2/routers/dashboard.py',
   ]:
       ast.parse(open(f).read())
       print(f'  OK: {f}')
   "
   ```

3. For **tsc --noEmit** (group 2) and **vite build** (group 3), run from `frontend-hormonia/`:
   ```bash
   cd frontend-hormonia && npx tsc --noEmit
   cd frontend-hormonia && npx vite build
   ```

4. For **response shape** (group 4), check that no schema files were modified in M011 commits. Use `git diff` against the commit before M011 started (parent of first M011 commit) on `backend-hormonia/app/schemas/`. Also check that the response_model/return type annotations in patients.py and dashboard.py are unchanged by grepping for `response_model` in both files.

5. For **caching values** (group 5):
   - `grep -q "ttl=60" backend-hormonia/app/api/v2/routers/physicians/patients.py`
   - `grep -q "CACHE_TTL_REALTIME = 120" backend-hormonia/app/api/v2/routers/dashboard.py`
   - `grep -q 'user:{user_id}' backend-hormonia/app/api/v2/routers/physicians/patients.py` (or equivalent `user_id` in cache key)

6. For **timing values** (group 6), use the canonical audit from S02:
   ```bash
   rg "staleTime|refetchInterval" --type ts --type-add 'tsx:*.tsx' --type tsx frontend-hormonia/src/ \
     | grep -v features/system | grep -v features/monitoring \
     | grep -v hive-mind | grep -v ClinicalMonitoring \
     | grep -v AdminMonitoringTab | grep -v hooks/api/useSystemStats \
     | grep -v features/whatsapp
   ```
   Then verify no value < 60000 for staleTime or < 120000 for refetchInterval appears (excluding `queryPresets.realtime` which is an intentional monitoring preset).

7. For **migration chain** (group 7):
   - `grep -q 'm008_s01_t03_sessions_align' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
   - `grep -q 'idx_pfs_patient_started' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`

8. Run `bash verify-m011.sh` and confirm exit 0 with all 7 groups passing.

## Must-Haves

- [ ] `verify-m011.sh` exists at project root and is executable
- [ ] All 7 check groups pass (ast.parse, tsc, vite build, response shape, caching values, timing values, migration chain)
- [ ] Script exits 0 on success, non-zero on any failure
- [ ] Script output clearly labels each check group PASS/FAIL

## Verification

- `bash verify-m011.sh` exits 0
- Script output shows 7/7 groups passing
- No code files modified — only verify-m011.sh created

## Inputs

- S01 deliverables: `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` (Alembic migration with composite index), `backend-hormonia/app/api/v2/routers/physicians/patients.py` (manual redis_cache with TTL=60s and per-user key)
- S01 confirmed unchanged: `backend-hormonia/app/api/v2/routers/dashboard.py` (pre-existing TTL=120s caching)
- S02 deliverables: 21 frontend files with staleTime ≥ 60s and refetchInterval ≥ 120s, `tsc --noEmit` + `vite build` already proven green
- `node_modules` already exists from S02's `npm ci` — no reinstall needed

## Expected Output

- `verify-m011.sh` — Replayable milestone verification script at project root, 7 check groups, exits 0 on success

## Observability Impact

- **New signal:** `verify-m011.sh` produces structured PASS/FAIL output for 7 check groups, enabling milestone-closing proof
- **Inspection:** Re-run `bash verify-m011.sh` at any time to re-verify M011 deliverables; each group's failure output is inline
- **Failure state:** Non-zero exit code + FAIL labels make failed groups immediately identifiable; no hidden failures
