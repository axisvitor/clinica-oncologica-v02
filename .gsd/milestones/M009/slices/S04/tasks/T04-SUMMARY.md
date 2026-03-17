---
id: T04
parent: S04
milestone: M009
provides:
  - verify_schedule_parity.sh — single-command proof of 47/47 beat_schedule ↔ Taskiq schedule parity
  - TODO(S05) markers on all remaining external Celery dispatch sites (trigger_service.py, recovery.py)
  - Verified 72 total @broker.task declarations across 13 Taskiq modules
key_files:
  - backend-hormonia/scripts/verify_schedule_parity.sh
  - backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py
  - backend-hormonia/app/services/flow/recovery.py
key_decisions:
  - TODO(S05) markers placed inline on .delay()/.apply_async() lines (not separate comment lines) so grep -v "TODO(S05)" filtering works correctly on line-by-line verification commands
patterns_established:
  - Schedule parity verification via script extraction of both Celery "task" values and Taskiq schedule= labels with function-name-suffix mapping + known renamings table
observability_surfaces:
  - bash scripts/verify_schedule_parity.sh — exits 0 (47/47 matched) or 1 (lists missing entries)
  - rg "\.delay\(|\.apply_async\(" --glob "!**/tasks/**" — shows only TODO(S05)-marked external sites
  - grep -rc "@broker.task" app/tasks/*_taskiq.py — confirms 72 total broker tasks across 13 modules
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T04: Schedule parity verification + call site audit

**Created verify_schedule_parity.sh proving 47/47 Celery beat_schedule → Taskiq schedule label parity, audited all external .delay()/.apply_async() call sites with TODO(S05) markers on remaining sync callers.**

## What Happened

1. Extracted all 47 `beat_schedule` entries from `celery_app.py` and all 47 scheduled functions from 13 `*_taskiq.py` modules. Confirmed 1:1 parity with no missing or extra entries.

2. Created `scripts/verify_schedule_parity.sh` — an executable script that:
   - Extracts Celery task names via regex on `"task":` values
   - Extracts Taskiq function names by finding `schedule=[` labels and scanning forward for `async def`
   - Maps Celery dotted paths to Taskiq function names (last segment match) with 3 known renamings: `refresh_performance_metrics` → `refresh_ai_performance_metrics`, `cleanup_expired_quiz_sessions_task` → `cleanup_expired_quiz_sessions`, `cleanup_expired_audit_logs` → `cleanup_expired_lgpd_audit_logs`
   - Reports matched/missing/extra with color-coded output; exits 0 on full match, 1 on gaps

3. Audited external `.delay()`/`.apply_async()` call sites. Added inline `TODO(S05)` markers to:
   - `trigger_service.py` lines 724 and 732 (2 `.apply_async()` calls for quiz reminders)
   - `recovery.py` line 214 (`.delay()` already had comment-line TODO(S05), added inline marker)

4. Verified 72 total `@broker.task` declarations across 13 modules (9 messaging + 14 flows + 3 saga_retry + 4 audit + 2 lgpd + 2 reports + 3 saga_monitoring + 7 alerts + 3 webhook_dlq + 8 monitoring + 6 quiz_link + 8 quiz_flow + 3 follow_up = 72).

## Verification

All checks passed:

- `bash scripts/verify_schedule_parity.sh` → **PASS: 47/47 matched**, exit 0
- `python3 -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('app/tasks/*_taskiq.py')]"` → **PASS**: all 13 modules parse cleanly
- External call sites in domain/services code: **0 non-TODO(S05)** matches (trigger_service.py and recovery.py both marked)
- `grep -rc "@broker.task" app/tasks/*_taskiq.py` → **72 total** broker tasks
- `grep -c "log_task_error" app/tasks/*_taskiq.py` → **13/13** modules have error logging

### Slice-level verification status (final task — all must pass):

| Check | Result |
|-------|--------|
| All 13 taskiq modules parse cleanly | ✅ PASS |
| Schedule parity: 47/47 matched | ✅ PASS |
| Zero external .delay()/.apply_async() in non-task code (excl. TODO(S05)) | ✅ PASS |
| Total @broker.task ≥ 46 (actual: 72) | ✅ PASS |
| All taskiq modules have error logging (13/13) | ✅ PASS |

## Diagnostics

- **Schedule drift detection:** Run `bash scripts/verify_schedule_parity.sh` after any Taskiq module change. Script reports exact missing/extra entries.
- **Call site audit:** `rg "\.delay\(|\.apply_async\(" --glob "!**/tasks/**" --glob "!app/celery_app.py"` — only TODO(S05) lines should appear.
- **Remaining S05 work:** `grep -rn "TODO(S05)" backend-hormonia/` lists all deferred migration points.

## Deviations

- Plan's verification command `!app/tasks/*.py` glob doesn't match subdirectories like `app/tasks/quiz_flow/trigger_tasks.py`. Actual external call site verification uses `!**/tasks/**` for correct recursive exclusion. The plan's glob still works for its stated purpose (the subdirectory files are Celery modules deleted in S05).
- Added inline TODO(S05) to `recovery.py` `.delay()` line (was only on preceding comment line) so line-level grep filtering works.

## Known Issues

- None. All slice verification checks pass.

## Files Created/Modified

- `backend-hormonia/scripts/verify_schedule_parity.sh` — new executable schedule parity verification script (47/47 beat_schedule ↔ Taskiq mapping)
- `backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py` — added inline TODO(S05) markers on 2 `.apply_async()` lines (724, 732)
- `backend-hormonia/app/services/flow/recovery.py` — added inline TODO(S05) marker on `.delay()` line (214)
- `.gsd/milestones/M009/slices/S04/tasks/T04-PLAN.md` — added Observability Impact section (pre-flight fix)
