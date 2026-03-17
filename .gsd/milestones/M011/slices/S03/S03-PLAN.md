# S03: Verificação integrada

**Goal:** Prove that S01 (backend caching + index) and S02 (frontend request discipline) work together with zero regressions — validating R100, R101, R102 and closing milestone M011.
**Demo:** All 7 verification checks pass in a single integrated run: ast.parse backend, tsc --noEmit, vite build, response shape unchanged, caching values correct, timing values correct, migration chain valid.

## Must-Haves

- `ast.parse` green on all 3 backend files (migration, patients.py, dashboard.py)
- `tsc --noEmit` exit 0
- `vite build` exit 0
- Zero changes to `backend-hormonia/app/schemas/` (response shape unchanged)
- TTL=60 in patients.py, TTL=120 in dashboard.py, user_id in cache key
- All staleTime ≥ 60000 and refetchInterval ≥ 120000 outside monitoring exclusions
- Migration down_revision = `m008_s01_t03_sessions_align` and index name = `idx_pfs_patient_started`

## Proof Level

- This slice proves: final-assembly
- Real runtime required: no
- Human/UAT required: no

## Verification

- `bash .gsd/milestones/M011/slices/S03/verify-m011.sh` — single script running all 7 checks, exits non-zero on any failure

## Integration Closure

- Upstream surfaces consumed: S01 backend files (migration + patients.py + dashboard.py), S02 frontend hooks (21 files with normalized timing)
- New wiring introduced in this slice: none
- What remains before the milestone is truly usable end-to-end: nothing — this slice closes M011

## Tasks

- [x] **T01: Run integrated verification and validate R100/R101/R102** `est:15m`
  - Why: Terminal verification gate — confirms all M011 deliverables work together and validates all three requirements
  - Files: `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`, `backend-hormonia/app/api/v2/routers/physicians/patients.py`, `backend-hormonia/app/api/v2/routers/dashboard.py`, `frontend-hormonia/src/lib/react-query/queryClient.ts`
  - Do: Create `verify-m011.sh` script running all 7 checks in sequence (ast.parse, tsc, vite build, schema diff, caching grep, timing grep, migration chain). Execute it. All checks must pass.
  - Verify: `bash .gsd/milestones/M011/slices/S03/verify-m011.sh` exits 0
  - Done when: All 7 checks pass, R100/R101/R102 validated

## Files Likely Touched

- `.gsd/milestones/M011/slices/S03/verify-m011.sh` (created — verification script)
