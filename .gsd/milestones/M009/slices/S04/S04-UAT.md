# S04: Quiz/alert/follow-up/monitoring migradas + schedule completo — UAT

**Milestone:** M009
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: This slice is contract-level migration (task definitions, schedule labels, call site wiring) — no runtime execution required. All proof is via static analysis: AST parsing, schedule parity script, grep-based call site audit. Runtime verification is S06 scope.

## Preconditions

- Working directory is `backend-hormonia/` inside the M009 worktree
- Python 3.11+ available with `ast` module (standard library)
- `rg` (ripgrep) installed for call site audits
- `bash` available for `verify_schedule_parity.sh`
- All 13 `*_taskiq.py` files exist in `app/tasks/`

## Smoke Test

Run `bash scripts/verify_schedule_parity.sh` — should exit 0 with "PASS: All 47 beat_schedule entries have matching Taskiq schedule labels".

## Test Cases

### 1. All Taskiq modules parse without syntax errors

1. `cd backend-hormonia/`
2. Run: `python3 -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('app/tasks/*_taskiq.py')]; print('PASS')"`
3. **Expected:** Prints `PASS` with no exceptions. All 13 modules parse cleanly.

### 2. Schedule parity: 47/47 Celery→Taskiq

1. Run: `bash scripts/verify_schedule_parity.sh`
2. **Expected:** Output shows 47 Celery entries, 47 Taskiq functions, 47/47 matched, 0 missing, 0 extra. Exit code 0.

### 3. Total task count across all modules

1. Run: `grep -rc "@broker.task" app/tasks/*_taskiq.py | awk -F: '{s+=$2}END{print s}'`
2. **Expected:** Output is `72` (or higher if tasks were added).

### 4. All modules have error logging

1. Run: `grep -c "log_task_error" app/tasks/*_taskiq.py | awk -F: '$2>0{c++}END{print c"/13"}'`
2. **Expected:** Output is `13/13`.

### 5. No external Celery dispatch in non-task code (excluding TODO(S05))

1. Run: `rg "\.delay\(|\.apply_async\(" --glob "*.py" --glob "!app/tasks/*.py" --glob "!app/tasks/**/*.py" --glob "!app/celery_app.py" --glob "!**/test*" . | grep -v "TODO(S05)"`
2. **Expected:** Zero output (only a comment line from taskiq_broker.py mentioning `.apply_async` in prose, not a call site). All real call sites are either migrated to `.kiq()` or marked `TODO(S05)`.

### 6. LGPD middleware uses Taskiq dispatch

1. Run: `grep -n "from.*lgpd_taskiq" app/middleware/lgpd_middleware.py`
2. **Expected:** Shows import from `lgpd_taskiq` module (not `lgpd_tasks`).
3. Run: `grep -n "await.*\.kiq(" app/middleware/lgpd_middleware.py`
4. **Expected:** Shows `await persist_lgpd_audit_log.kiq(...)` — async Taskiq dispatch.
5. Run: `grep -n "\.delay(" app/middleware/lgpd_middleware.py`
6. **Expected:** Zero matches — no remaining Celery `.delay()` calls.

### 7. Cross-module dispatch uses Taskiq imports

1. Run: `grep "from.*quiz_link_taskiq.*import.*send_quiz_reminder" app/tasks/quiz_flow_taskiq.py`
2. **Expected:** Shows import of `send_quiz_reminder` from `quiz_link_taskiq`.
3. Run: `grep "from.*alerts_taskiq.*import.*process_alert_notification" app/tasks/follow_up_taskiq.py`
4. **Expected:** Shows import of `process_alert_notification` from `alerts_taskiq`.

### 8. Zero sync-async bridges in new modules

1. Run: `rg "async_to_sync|run_async" app/tasks/alerts_taskiq.py app/tasks/webhook_dlq_taskiq.py app/tasks/monitoring_taskiq.py app/tasks/quiz_link_taskiq.py app/tasks/quiz_flow_taskiq.py app/tasks/follow_up_taskiq.py | grep -v "^.*:#"`
2. **Expected:** Zero matches in code lines (comments mentioning removed bridges are OK).

### 9. BRT→UTC cron conversion correctness

1. Run: `grep -n 'cron("' app/tasks/audit_taskiq.py app/tasks/lgpd_taskiq.py app/tasks/webhook_dlq_taskiq.py app/tasks/follow_up_taskiq.py`
2. **Expected:** All cron hours are UTC (+3 from BRT). Examples: 02:00 BRT → `cron("0 5 * * *")`, 02:30 BRT → `cron("30 5 * * *")`, 03:00 BRT → `cron("0 6 * * *")`.

### 10. TODO(S05) markers on deferred call sites

1. Run: `grep -rn "TODO(S05)" app/domain/quizzes/integration/flow_integration/trigger_service.py app/services/flow/recovery.py`
2. **Expected:** 3 matches — lines 724, 732 in trigger_service.py and line 214 in recovery.py.

## Edge Cases

### MonitoringTask class hierarchy fully flattened

1. Run: `grep -c "MonitoringTask\|class.*Task.*:" app/tasks/monitoring_taskiq.py`
2. **Expected:** `0` — no class definitions or MonitoringTask references in the Taskiq module. All 8 monitoring tasks are standalone `@broker.task()` async functions.

### Quiz flow consolidation (4 files → 1)

1. Run: `grep -c "@broker.task" app/tasks/quiz_flow_taskiq.py`
2. **Expected:** `8` — all 4 quiz_flow subpackage files' tasks consolidated into single module.

### Reports cross-dispatch via .kiq()

1. Run: `grep "await.*generate_patient_report\.kiq" app/tasks/reports_taskiq.py`
2. **Expected:** Shows cross-dispatch from `generate_scheduled_reports` to `generate_patient_report` via `.kiq()`.

## Failure Signals

- `verify_schedule_parity.sh` exits 1 with missing entries → schedule label regression
- `ast.parse()` raises SyntaxError → module has Python syntax errors
- `rg "\.delay\("` finds non-TODO(S05) matches in non-task code → unmigrated call site
- `grep "from app.tasks.messaging import"` found in a new Taskiq module → wrong import (Celery instead of Taskiq)
- `grep "async_to_sync\|run_async"` in Taskiq module code → bridge not removed

## Requirements Proved By This UAT

- R081 — All remaining task groups (quiz, alerts, follow-up, LGPD, audit, webhook DLQ, monitoring) have Taskiq equivalents (contract-level: modules parse, tasks defined, patterns correct)
- R082 — All 47 beat_schedule entries have matching Taskiq schedule labels (proven by verify_schedule_parity.sh 47/47)
- R083 — All external call sites migrated to .kiq() or explicitly marked TODO(S05) (proven by grep audit)

## Not Proven By This UAT

- Runtime execution of any Taskiq task against Dragonfly (S06 scope)
- Correct cron timing under real taskiq scheduler process (S06 scope)
- Actual message delivery via migrated tasks (S06 scope)
- trigger_service.py and recovery.py full migration (S05 scope — currently TODO(S05))

## Notes for Tester

- This is purely artifact-driven UAT. No servers, databases, or Redis needed.
- The verify_schedule_parity.sh script is the single most important check — it mechanically proves all 47 schedule entries are covered.
- The "72 tasks" count exceeds the plan's "46+" estimate because monitoring was 8 tasks (flattened from 8 class-based tasks), alerts was 7, and quiz modules were larger than estimated.
- During Celery/Taskiq coexistence (until S05), both `messaging.py` and `messaging_taskiq.py` export the same function names — importing from the wrong module dispatches to the wrong queue. This is a known coexistence risk eliminated by S05.
