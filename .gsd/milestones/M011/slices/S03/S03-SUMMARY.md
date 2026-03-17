---
id: S03
parent: M011
milestone: M011
provides:
  - Replayable verify-m011.sh with 7 check groups proving M011 Definition of Done
  - R100, R101, R102 validated as a cohesive unit
requires:
  - slice: S01
    provides: Backend caching (per-user Redis TTL=60s physician, TTL=120s dashboard) and composite index migration
  - slice: S02
    provides: Frontend hooks with staleTime ≥ 60s and refetchInterval ≥ 120s, tsc + vite build green
affects: []
key_files:
  - verify-m011.sh
key_decisions: []
patterns_established:
  - Python eval for JS math expressions (5 * 60 * 1000) in timing audits — bash regex can't evaluate computed values
  - queryPresets.realtime exclusion by line-range in queryClient.ts — monitoring presets explicitly exempt from request-discipline thresholds
  - Commit-message grep for schema-unchanged proof avoids SIGPIPE with git log | head under set -o pipefail
observability_surfaces:
  - "bash verify-m011.sh — prints labeled PASS/FAIL for each of 7 groups with inline error detail on failure"
  - "Exit code: 0 = all 7 pass, non-zero = failure with FAIL labels identifying broken groups"
drill_down_paths:
  - .gsd/milestones/M011/slices/S03/tasks/T01-SUMMARY.md
duration: 15m
verification_result: passed
completed_at: 2026-03-17
---

# S03: Verificação integrada

**Replayable verify-m011.sh proves all M011 deliverables — backend caching, composite index, frontend request discipline — with 7/7 check groups passing and exit 0**

## What Happened

This terminal slice assembled and verified the outputs of S01 (backend caching + index) and S02 (frontend request discipline) into a single integrated proof.

**T01 — Created and ran verify-m011.sh** with 7 check groups covering every item in the M011 Definition of Done:

1. **ast.parse** — All 3 backend files parse cleanly (migration, patients.py, dashboard.py)
2. **tsc --noEmit** — Frontend TypeScript compilation exits 0, zero errors
3. **vite build** — Production build succeeds (4741 modules)
4. **Response shape** — No M011 commits modified `backend-hormonia/app/schemas/`; `response_model=` annotations confirmed in both routers
5. **Caching values** — `ttl=60` in patients.py, `CACHE_TTL_REALTIME = 120` in dashboard.py, `user:{user_id}` in cache key
6. **Timing values** — Python-based auditor evaluated 58 JS math expressions (e.g., `5 * 60 * 1000`), confirming all comply with staleTime ≥ 60000 and refetchInterval ≥ 120000. Monitoring exclusions applied for system/monitoring/hive-mind/whatsapp/queryPresets.realtime
7. **Migration chain** — `down_revision = "m008_s01_t03_sessions_align"` and index name `idx_pfs_patient_started` confirmed

All 7 groups passed. Script exits 0.

## Verification

```
bash verify-m011.sh  →  exit 0
Results: 7/7 passed, 0 failed
✅ M011 verification PASSED — all 7 check groups green
```

Milestone Definition of Done checklist:
- ✅ Redis caching on physician/patients (TTL=60s, per-user key) and dashboard/main (TTL=120s)
- ✅ Composite index `idx_pfs_patient_started` on `patient_flow_states(patient_id, started_at DESC)` via Alembic
- ✅ Frontend hooks normalized — staleTime ≥ 60s dashboard, ≥ 120s admin; refetchInterval ≥ 120s
- ✅ `tsc --noEmit` exit 0
- ✅ `vite build` exit 0
- ✅ Response shape unchanged — zero schema modifications

## Requirements Advanced

- None — all three requirements are validated by this slice (see below)

## Requirements Validated

- R100 — verify-m011.sh group 5 confirms TTL=60 in patients.py, TTL=120 in dashboard.py, user_id in cache key. S01 implemented per-user Redis caching on both hot-path endpoints.
- R101 — verify-m011.sh group 7 confirms composite index `idx_pfs_patient_started` exists in Alembic migration with correct down_revision chain. S01 created the migration with `if_not_exists=True`.
- R102 — verify-m011.sh group 6 confirms 58 timing values comply (staleTime ≥ 60000, refetchInterval ≥ 120000) with monitoring exclusions. S02 normalized 21 hooks across dashboard/admin.

## New Requirements Surfaced

- None

## Requirements Invalidated or Re-scoped

- None

## Deviations

- **Group 4 (response shape)** uses commit-message grep filtered to M011 task patterns instead of `git diff` against merge-base — avoids SIGPIPE issues with `git log | head` under `set -o pipefail`
- **Group 6 (timing values)** uses embedded Python instead of bash grep — necessary because JS timing values like `5 * 60 * 1000` can't be numerically evaluated by bash regex

## Known Limitations

- verify-m011.sh is a contract/static verification script — it does not test runtime Redis connectivity, actual cache hit behavior, or actual query plan changes from the index. This is by design per the M011 roadmap (Verification Classes: contract + integration only, no operational verification).

## Follow-ups

- None — M011 is complete. All three requirements (R100, R101, R102) validated.

## Files Created/Modified

- `verify-m011.sh` — Replayable M011 milestone verification script, 7 check groups, exits 0 when all pass

## Forward Intelligence

### What the next slice should know
- M011 is a terminal milestone — no downstream slices depend on it. The patterns established here (per-user cache key format, staleTime discipline thresholds, monitoring exclusions list) are stable for future work.
- The cache key format `physician:patients:user:{user_id}:page:...` is the canonical pattern for any future per-user endpoint caching.
- Frontend timing discipline: monitoring/real-time hooks are explicitly exempt from the ≥ 60s/120s thresholds. The exclusion list is in verify-m011.sh group 6.

### What's fragile
- The timing audit in group 6 uses Python `eval()` on extracted JS expressions — safe for numeric literals and `*` but would break on complex JS (ternary, function calls). Currently all 58 values are simple arithmetic.
- The monitoring exclusion list is hardcoded — if new monitoring hooks are added, they need to be added to the exclusion list in verify-m011.sh.

### Authoritative diagnostics
- `bash verify-m011.sh` — single command to re-verify all M011 deliverables at any time. No side effects, no mutations.
- Redis key inspection: `redis-cli KEYS "physician:patients:user:*"` shows active cached physician queries.
- Index verification: `SELECT indexname FROM pg_indexes WHERE indexname = 'idx_pfs_patient_started'` confirms the index exists in PostgreSQL.

### What assumptions changed
- Original plan assumed `@cache_response` decorator would be used on both endpoints — S01 used manual `redis_cache.get/set` instead for physician/patients to include user_id and all query params in the key. Dashboard already had correct caching. The verification script adapted to check the actual implementation values rather than decorator presence.
