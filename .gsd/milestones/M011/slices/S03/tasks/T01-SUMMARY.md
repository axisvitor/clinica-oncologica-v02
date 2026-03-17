---
id: T01
parent: S03
milestone: M011
provides:
  - Replayable verify-m011.sh script with 7 check groups covering R100, R101, R102
key_files:
  - verify-m011.sh
key_decisions: []
patterns_established:
  - Python eval for JS math expressions (5 * 60 * 1000) in timing audits — bash regex can't evaluate these
  - queryPresets.realtime exclusion by line-range in queryClient.ts rather than substring match
observability_surfaces:
  - "bash verify-m011.sh — prints PASS/FAIL for each of 7 groups with inline error detail on failure"
  - "Exit code: 0 = all pass, non-zero = failure with FAIL labels identifying broken groups"
duration: 15m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T01: Create and run verify-m011.sh integrated verification script

**Created verify-m011.sh with 7 check groups (ast.parse, tsc, vite build, response shape, caching values, timing values, migration chain) — all pass, exit 0**

## What Happened

Created `verify-m011.sh` at the project root with 7 integrated check groups:

1. **ast.parse** — Parses 3 backend Python files (migration, patients.py, dashboard.py)
2. **tsc --noEmit** — Frontend TypeScript compilation (exit 0, zero errors)
3. **vite build** — Frontend production build (4741 modules, exit 0)
4. **Response shape** — Confirms no M011 task commits modified `backend-hormonia/app/schemas/` and `response_model=` annotations present in both routers
5. **Caching values** — Confirms `ttl=60` in patients.py, `CACHE_TTL_REALTIME = 120` in dashboard.py, `user:{user_id}` in cache key
6. **Timing values** — Python-based audit evaluating JS math expressions (e.g., `5 * 60 * 1000 = 300000`), confirming 58 timing values comply with staleTime ≥ 60000 and refetchInterval ≥ 120000. Monitoring exclusions applied: `features/system`, `features/monitoring`, `hive-mind`, `ClinicalMonitoring`, `AdminMonitoringTab`, `useSystemStats`, `features/whatsapp`, `useOptimizedQuery`, `ProductionProvider`, and `queryPresets.realtime` in queryClient.ts
7. **Migration chain** — Confirms `down_revision = "m008_s01_t03_sessions_align"` and index name `idx_pfs_patient_started`

Key implementation choice: Group 6 uses embedded Python instead of bash grep because JS timing values use math expressions (`5 * 60 * 1000`) that bash can't evaluate. The Python auditor extracts numeric expressions via regex, `eval()`s them, and compares against thresholds.

## Verification

```
bash verify-m011.sh  →  exit 0
Results: 7/7 passed, 0 failed
✅ M011 verification PASSED — all 7 check groups green
```

All 7 must-haves confirmed:
- ✅ `verify-m011.sh` exists at project root and is executable
- ✅ All 7 check groups pass
- ✅ Script exits 0 on success
- ✅ Script output clearly labels each check group PASS/FAIL

Slice-level verification: `bash verify-m011.sh` exits 0 with all checks passing ✅

## Diagnostics

- **Re-run:** `bash verify-m011.sh` at any time to re-verify all M011 deliverables
- **Failure inspection:** Each failed group prints inline error output before the FAIL label — root cause visible without re-running individual checks
- **Exit code:** Non-zero on any failure, CI-friendly
- **No side effects:** Pure verification script, no mutations

## Deviations

- **Group 4** uses commit-message grep filtered to M011 task patterns (`S01.*T0`, `S02.*T0`, etc.) instead of `git diff` against merge-base — avoids SIGPIPE issues with `git log | head` under `set -o pipefail`
- **Group 6** uses embedded Python instead of bash grep — necessary because JS timing values like `5 * 60 * 1000` can't be numerically evaluated by bash regex. The plan's canonical `rg` command works for human review but can't programmatically verify threshold compliance

## Known Issues

None

## Files Created/Modified

- `verify-m011.sh` — Replayable M011 milestone verification script, 7 check groups, exits 0 when all pass
- `.gsd/milestones/M011/slices/S03/S03-PLAN.md` — Added Observability / Diagnostics section (pre-flight fix)
- `.gsd/milestones/M011/slices/S03/tasks/T01-PLAN.md` — Added Observability Impact section (pre-flight fix)
