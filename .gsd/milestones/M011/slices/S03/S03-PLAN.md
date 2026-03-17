# S03: Verificação integrada

**Goal:** Prove all M011 deliverables work together — backend caching, composite index, frontend request discipline — and produce replayable milestone-closing proof.
**Demo:** `bash verify-m011.sh` exits 0 with all 7 check groups passing: ast.parse, tsc, vite build, response shape, caching values, timing values, migration chain.

## Must-Haves

- Replayable `verify-m011.sh` script at project root covering all 7 verification groups
- ast.parse green on the 3 backend files (migration, patients.py, dashboard.py)
- `tsc --noEmit` exit 0
- `vite build` exit 0
- Zero schema changes in `backend-hormonia/app/schemas/` across M011
- Caching values confirmed: TTL=60 in patients.py, TTL=120 in dashboard.py, user_id in cache key
- Timing values confirmed: staleTime ≥ 60000 and refetchInterval ≥ 120000 outside monitoring exclusions
- Migration chain confirmed: down_revision = `m008_s01_t03_sessions_align`, index name = `idx_pfs_patient_started`

## Proof Level

- This slice proves: final-assembly
- Real runtime required: no (contract verification per roadmap)
- Human/UAT required: no

## Observability / Diagnostics

- **Script output:** `verify-m011.sh` prints labeled PASS/FAIL for each of 7 check groups with a final summary line (e.g., `7/7 checks passed`)
- **Exit code:** Non-zero exit on any failure — CI-friendly and machine-parseable
- **Failure visibility:** Each failed group prints its error output inline before the FAIL label so the root cause is immediately visible without re-running individual checks
- **Replayability:** Script can be re-run at any time without side effects (no mutations, no installs, pure verification)

## Verification

- `bash verify-m011.sh` — exits 0 with all checks passing
- On failure: script exits non-zero and FAIL labels identify which check groups failed with inline error output

## Integration Closure

- Upstream surfaces consumed: S01 backend caching + index files, S02 frontend timing changes
- New wiring introduced in this slice: none
- What remains before the milestone is truly usable end-to-end: nothing — this is the terminal slice

## Tasks

- [x] **T01: Create and run verify-m011.sh integrated verification script** `est:20m`
  - Why: Terminal verification gate — proves all M011 deliverables (R100, R101, R102) work together and produces milestone-closing proof
  - Files: `verify-m011.sh`
  - Do: Create `verify-m011.sh` at project root with 7 check groups: (1) ast.parse 3 backend files, (2) tsc --noEmit, (3) vite build, (4) response shape audit via git diff on schemas/, (5) caching value grep (TTL=60, TTL=120, user_id in key), (6) timing value grep with monitoring exclusions, (7) migration chain grep (down_revision, index name). Run the script and confirm exit 0.
  - Verify: `bash verify-m011.sh` exits 0
  - Done when: All 7 check groups pass, script is committed, milestone Definition of Done is proven

## Files Likely Touched

- `verify-m011.sh`
