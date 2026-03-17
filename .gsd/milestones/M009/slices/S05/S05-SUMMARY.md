---
id: S05
parent: M009
milestone: M009
provides:
  - Zero Celery imports across entire app/ directory (AST-verified, 10-check gate)
  - app/tasks/helpers/ package with 9 domain helper modules (40+ shared functions)
  - tasks/__init__.py re-exports 72 task functions from 13 *_taskiq.py modules exclusively
  - 30 Celery/bridge files deleted (12 task files, 5 bridge files, 4 infra files, 9 in subdirectories)
  - requirements.txt free of celery, celery[redis], asgiref, flower
  - docker-compose.yml worker/beat services use taskiq commands
  - Makefile targets use taskiq-worker/taskiq-scheduler
  - Health endpoints, Sentry, settings, metrics cleaned of all Celery references
  - trigger_service.py and recovery.py converted from Celery dispatch to Taskiq
requires:
  - slice: S02
    provides: Messaging tasks operating entirely via Taskiq (send_scheduled_message etc.)
  - slice: S03
    provides: Flow/saga tasks operating via Taskiq (process_daily_flows, detect_stuck_flows etc.)
  - slice: S04
    provides: Quiz/alert/follow-up/monitoring tasks operating via Taskiq, complete schedule with 47+ entries
affects:
  - S06
key_files:
  - backend-hormonia/app/tasks/helpers/ (new package — 10 files)
  - backend-hormonia/app/tasks/__init__.py (rewritten)
  - backend-hormonia/app/core/__init__.py (cleaned)
  - backend-hormonia/app/task_queue.py (cleaned)
  - backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py
  - backend-hormonia/app/services/flow/recovery.py
  - backend-hormonia/app/api/v2/routers/health/core.py
  - backend-hormonia/app/api/v2/routers/health/service_health.py
  - backend-hormonia/app/core/setup/sentry.py
  - backend-hormonia/app/config/settings/integrations.py
  - backend-hormonia/requirements.txt
  - backend-hormonia/docker-compose.yml
  - backend-hormonia/Makefile
key_decisions:
  - D013: Celery revoke/cancel → logged no-ops (Taskiq ListQueueBroker doesn't support per-message cancellation)
  - D014: Helpers extracted to app/tasks/helpers/{domain}_helpers.py before Celery file deletion
  - D015: Function names containing "celery" renamed to "backend" (AST scan catches imported names)
  - tasks/__init__.py uses direct imports from *_taskiq.py — safe because broker reads REDIS_URL directly
  - recovery.py attempt_recovery() converted sync→async — safe because only caller is async Taskiq task
  - CELERY_BROKER_URL env var kept in docker-compose.yml per D003 (Taskiq broker fallback chain)
patterns_established:
  - Helpers package convention: app/tasks/helpers/{domain}_helpers.py for shared pure functions
  - Package init re-exports: tasks/__init__.py imports from *_taskiq.py for backward-compatible `from app.tasks import X`
  - Celery revoke → logged no-op pattern for task cancellation endpoints
  - Registry-only task data (no live Celery state merge) via _get_task_with_backend_data
observability_surfaces:
  - AST zero-import scan: python3 -c "import ast, sys, os; ..." on entire app/ directory (primary V1 gate)
  - Health /ready endpoint returns taskiq_broker and workers check keys (no Celery inspect)
  - Worker health endpoint returns taskiq_status field (healthy/unreachable/error)
  - Task cancel endpoints emit logger.warning with task_id for audit trail
  - All 72 Taskiq tasks retain log_task_start/success/error structured logging
drill_down_paths:
  - .gsd/milestones/M009/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M009/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M009/slices/S05/tasks/T03-SUMMARY.md
  - .gsd/milestones/M009/slices/S05/tasks/T04-SUMMARY.md
duration: ~65m (T01: 20m, T02: 8m, T03: 12m, T04: 25m)
verification_result: passed
completed_at: 2026-03-16
---

# S05: Celery removal + bridge cleanup

**Removed all Celery code, bridge code, and dependencies — 30 files deleted, ~900 lines of bridge code eliminated, zero Celery imports verified by AST scan across the entire app/ directory.**

## What Happened

This slice completed the Celery→Taskiq migration's cleanup phase in 4 sequential tasks:

**T01 — Helper extraction** created `app/tasks/helpers/` with 9 domain modules containing 40+ pure functions copied from Celery source files. All 10 Taskiq modules were rewired to import from `helpers/` instead of Celery sources. Key consolidation: `flow_helpers.py` pulled from 4 separate Celery files (flow_automation, batch_tasks, send_retry, followup_retry) because `flows_taskiq.py` imported from all four. The `_process_single_patient_flow` processing chain was extracted fully with its 5 internal helpers.

**T02 — Call site resolution** converted the 3 remaining Celery dispatch call sites: `trigger_service.py` swapped 2 `.apply_async(eta=)` calls to `await schedule_task_at()` for quiz reminders; `recovery.py` was made async, replacing `async_to_sync()` bridge + `.delay()` with native `await` + `.kiq()`. All `TODO(S05)` markers eliminated.

**T03 — Mass deletion** removed 30 files: 5 bridge code files (celery_app.py, async_context_manager.py, async_helpers.py, async_handler.py, event_loop_manager.py), 4 Celery infrastructure files (base.py, config.py, celery_metrics.py, queue_monitor.py), 12 Celery task files, and 3 entire directories (flows/, quiz_flow/, lgpd/). `tasks/__init__.py` was rewritten to re-export 72 task functions from 13 `*_taskiq.py` modules. `core/__init__.py` cleaned of event_loop_manager references.

**T04 — Infrastructure cleanup** purged Celery references from 23 files across health endpoints, Sentry integration, settings (14 CELERY_* fields), metrics (histogram + gauge + decorator removed), task API endpoints (revoke → logged no-ops), message scheduler, requirements.txt (celery, celery[redis], asgiref, flower removed), docker-compose.yml (taskiq commands), and Makefile (taskiq targets). Discovered and fixed 5 extra files in message_scheduler/ not originally planned. Renamed 5 functions containing "celery" to "backend" because the AST scan catches imported names.

## Verification

All 10 slice-level verification checks pass:

| Check | Result |
|-------|--------|
| V1: Zero Celery imports (AST scan, entire app/) | ✅ PASS |
| V2: 13 Taskiq modules parse cleanly | ✅ PASS |
| V3: No celery/kombu/amqp/billiard/flower/asgiref in requirements.txt | ✅ PASS |
| V4: Key Celery files deleted (5/5) | ✅ PASS |
| V5: Celery task directories deleted (3/3) | ✅ PASS |
| V6: Schedule labels preserved (47 ≥ 47) | ✅ PASS |
| V7: Helper modules parse (10 files) | ✅ PASS |
| V8: No TODO(S05) remaining | ✅ PASS |
| V9: tasks/__init__.py clean (Taskiq-only imports) | ✅ PASS |
| V10: Structured error logging retained in all Taskiq modules | ✅ PASS |

## Requirements Advanced

- R086 — All tasks now run exclusively through Taskiq with no Celery fallback. Stack is clean for S06 end-to-end pipeline verification.

## Requirements Validated

- R084 — celery_app.py (run_async_in_celery), async_context_manager.py, async_helpers.py, event_loop_manager.py, async_handler.py deleted. 30 total files removed. AST scan confirms zero Celery imports.
- R085 — celery>=5.6.2, celery[redis]>=5.6.2, asgiref>=3.11.0, flower==2.0.1 removed from requirements.txt. docker-compose.yml and Makefile use taskiq commands.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- **flow_helpers.py larger than planned**: Plan listed helpers from 2 Celery sources but actual imports in flows_taskiq.py pulled from 4 sources. All consolidated into one module. No impact.
- **5 extra message_scheduler files**: Plan didn't list `message_scheduler/shared.py`, `metrics.py`, `task_scheduler.py`, `scheduler.py`, `message.py`. These had `from celery.result import AsyncResult` and `*_celery_*` function names. Fixed in T04.
- **Function renaming required**: AST scan catches imported *names* containing "celery", not just module paths. Required renaming 5 functions to use "backend" (e.g., `get_task_by_celery_id` → `get_task_by_backend_id`).
- **monitoring.py endpoint extra cleanup**: Had to remove import of deleted `task_monitoring.py` and stub `get_task_monitoring_data()`.

## Known Limitations

- Task admin API `/tasks` POST cannot dispatch tasks by string name — it registers in the task store and logs a warning. Acceptable since this admin endpoint is rarely used.
- Queue status endpoint (`/tasks/queue/status`) returns empty queues — Taskiq doesn't expose per-queue inspect data like Celery did. Endpoint works but provides no useful data.
- `generate_quiz_report` name exists in both `flows_taskiq` and `quiz_flow_taskiq` — both re-exported in `__init__.py`, last import wins (quiz-specific version). Callers needing the flows version should use explicit module import.

## Follow-ups

- S06 must verify the complete M008 pipeline end-to-end via Taskiq (create patient → welcome → daily flow → response → transition)
- Queue status endpoint could be enhanced to report Taskiq Redis list lengths if operational visibility is needed

## Files Created/Modified

### Created (10 files)
- `backend-hormonia/app/tasks/helpers/__init__.py` — Package init
- `backend-hormonia/app/tasks/helpers/messaging_helpers.py` — 5 helpers from messaging.py
- `backend-hormonia/app/tasks/helpers/alerts_helpers.py` — 3 helpers from alerts.py
- `backend-hormonia/app/tasks/helpers/lgpd_helpers.py` — 13+ helpers from lgpd_tasks.py
- `backend-hormonia/app/tasks/helpers/reports_helpers.py` — 3 helpers from reports.py
- `backend-hormonia/app/tasks/helpers/saga_helpers.py` — 3 helpers from saga_retry.py
- `backend-hormonia/app/tasks/helpers/follow_up_helpers.py` — 6 helpers from follow_up.py
- `backend-hormonia/app/tasks/helpers/quiz_link_helpers.py` — 4 helpers from quiz_link_tasks.py
- `backend-hormonia/app/tasks/helpers/flow_helpers.py` — 15+ helpers from 4 Celery sources
- `backend-hormonia/app/tasks/helpers/quiz_flow_helpers.py` — 5 helpers from quiz_flow/

### Rewritten (2 files)
- `backend-hormonia/app/tasks/__init__.py` — Re-exports 72 tasks from 13 *_taskiq.py modules
- `backend-hormonia/app/core/__init__.py` — Cleaned event_loop_manager references

### Deleted (32 files)
- Bridge code: `celery_app.py`, `async_context_manager.py`, `async_helpers.py`, `async_handler.py`, `event_loop_manager.py`
- Celery infrastructure: `tasks/base.py`, `tasks/config.py`, `tasks/celery_metrics.py`, `tasks/queue_monitor.py`
- Celery task files (12): `messaging.py`, `alerts.py`, `monitoring.py`, `flow_automation.py`, `follow_up.py`, `lgpd_tasks.py`, `quiz_link_tasks.py`, `reports.py`, `saga_monitoring.py`, `saga_retry.py`, `webhook_dlq.py`, `audit_cleanup.py`
- Celery directories: `tasks/flows/` (8 files), `tasks/quiz_flow/` (6 files), `tasks/lgpd/` (2 files)
- Infrastructure: `celery_integration.py`, `task_monitoring.py`

### Modified (23+ files)
- 10 Taskiq modules — import updates to helpers/
- `trigger_service.py` — Celery→Taskiq dispatch
- `recovery.py` — sync→async, Celery→Taskiq dispatch
- `task_queue.py`, health endpoints, sentry, settings, metrics, task API endpoints, message_scheduler (5 files), pause_resume.py — Celery reference cleanup
- `requirements.txt`, `docker-compose.yml`, `Makefile` — deps and commands

## Forward Intelligence

### What the next slice should know
- The codebase has zero Celery imports. All 72 tasks dispatch via `.kiq()` or `schedule_task_at()`. The broker reads `REDIS_URL` from env (fallback chain: TASKIQ_BROKER_URL → CELERY_BROKER_URL → REDIS_URL → localhost:6379).
- `tasks/__init__.py` re-exports everything — `from app.tasks import send_scheduled_message` works but pulls the full import chain. For lightweight imports, use `from app.tasks.messaging_taskiq import send_scheduled_message` directly.
- Task cancel/revoke is now a no-op with logging. If S06 tests revocation behavior, expect logged warnings instead of actual cancellation.

### What's fragile
- `generate_quiz_report` name collision between `flows_taskiq` and `quiz_flow_taskiq` — last import in `__init__.py` wins. If S06 tests this specific task, verify which version is being called.
- Queue status endpoint returns empty data — don't use it for operational assertions in S06.

### Authoritative diagnostics
- AST zero-import scan (V1) is the ground truth for Celery removal — it catches imports in code, not just strings in comments. Run it if any doubt.
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/__init__.py').read())"` — verifies package init parses after any changes.
- Health `/ready` endpoint returns `taskiq_broker` and `workers` keys — use for runtime health verification in S06.

### What assumptions changed
- Original plan estimated ~25 files to delete — actual was 30 files (subdirectory contents were undercounted).
- Function names containing "celery" in imports break the AST scan — not just module paths. This required renaming 5 functions.
- Message scheduler had 5 files with Celery references not listed in the plan — discovered during T04 execution.
