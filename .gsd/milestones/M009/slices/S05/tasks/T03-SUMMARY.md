---
id: T03
parent: S05
milestone: M009
provides:
  - All Celery task files (12), bridge code (5), infra files (4), and 3 directories deleted — 30 files total
  - tasks/__init__.py re-exports 72 task functions from 13 *_taskiq.py modules only
  - core/__init__.py cleaned of all event_loop_manager references
key_files:
  - backend-hormonia/app/tasks/__init__.py
  - backend-hormonia/app/core/__init__.py
key_decisions:
  - tasks/__init__.py uses direct imports (not lazy) from all 13 *_taskiq.py modules — safe because Taskiq modules import broker from taskiq_broker which reads REDIS_URL directly, not from app.config.settings
patterns_established:
  - Package init re-exports pattern: app/tasks/__init__.py imports public functions from *_taskiq.py modules and exposes them in __all__ for backward-compatible from app.tasks import X
observability_surfaces:
  - All 72 Taskiq tasks retain log_task_start/success/error structured logging unchanged
  - If a task import breaks at runtime, the ImportError traceback surfaces via log_task_error in each Taskiq task (stdout + Sentry)
  - AST parse check: python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/__init__.py').read())" verifies package init is syntactically valid
duration: 12m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T03: Delete all Celery task files, bridge code, and rewrite package inits

**Deleted 30 Celery/bridge files across 3 directories and rewrote package inits to re-export from Taskiq modules exclusively.**

## What Happened

Executed the planned 6-step deletion and rewrite:

1. **Deleted 5 bridge code files**: `celery_app.py`, `async_context_manager.py`, `async_helpers.py`, `async_handler.py`, `event_loop_manager.py`
2. **Deleted 4 Celery infrastructure files**: `base.py`, `config.py`, `celery_metrics.py`, `queue_monitor.py`
3. **Deleted 12 Celery task files**: `messaging.py`, `alerts.py`, `monitoring.py`, `flow_automation.py`, `follow_up.py`, `lgpd_tasks.py`, `quiz_link_tasks.py`, `reports.py`, `saga_monitoring.py`, `saga_retry.py`, `webhook_dlq.py`, `audit_cleanup.py`
4. **Deleted 3 directories** (9 additional files): `flows/` (8 files + `__init__`), `quiz_flow/` (6 files + `__init__`), `lgpd/` (1 file + `__init__`)
5. **Rewrote `tasks/__init__.py`**: New init imports and re-exports 72 public task functions from all 13 `*_taskiq.py` modules. Uses direct imports grouped by domain. Includes comprehensive `__all__` list.
6. **Cleaned `core/__init__.py`**: Removed all `event_loop_manager` imports/exports. Now contains only docstring and redis_circuit_breaker import note.

## Verification

### Task-level checks (all PASS):
- ✅ V1: Key files deleted (celery_app.py, async_context_manager, async_helpers, async_handler, event_loop_manager, base.py, messaging.py)
- ✅ V2: Directories deleted (flows/, quiz_flow/, lgpd/)
- ✅ V3: 13 Taskiq modules parse OK
- ✅ V4: tasks/__init__.py imports only from taskiq/helpers modules
- ✅ V5: core/__init__.py has no event_loop_manager references
- ✅ V6: 47 schedule labels preserved (≥47 threshold met)

### Slice-level checks:
- ❌ V1 (Zero Celery imports): Expected fail — remaining references in non-task files (task_queue.py, celery_integration.py, sentry.py, etc.) are T04 scope
- ✅ V2: 13 Taskiq modules parse OK
- ❌ V3 (requirements.txt): Expected fail — celery/asgiref/flower removal is T04 scope
- ✅ V4: Key Celery files deleted
- ✅ V5: Celery task directories deleted
- ✅ V6: 47 schedule labels preserved
- ✅ V7: 10 helper modules parse OK
- ✅ V8: No TODO(S05) remaining
- ✅ V9: tasks/__init__.py clean (imports from taskiq modules only)

## Diagnostics

- **Import verification**: `python3 -c "import ast; tree = ast.parse(open('backend-hormonia/app/tasks/__init__.py').read()); print('OK')"` — confirms package init parses
- **Task function availability**: `python3 -c "from app.tasks import send_scheduled_message; print(type(send_scheduled_message))"` — confirms re-export works (requires REDIS_URL env)
- **Schedule parity**: `python3 -c "import re, glob; count = sum(len(re.findall(r'schedule=', open(f).read())) for f in glob.glob('backend-hormonia/app/tasks/*_taskiq.py')); print(f'{count} schedules')"` — should show ≥47
- **Remaining Celery references** (T04 scope): `python3 -c "import ast, os, sys; ..."` AST scan shows ~34 references in task_queue.py, API routers, sentry, settings — all tracked for T04

## Deviations

- Plan noted "~25 files" but actual count was 30 files (21 direct + 9 in subdirectories). No impact — all were Celery dead code.
- `generate_quiz_report` exists in both `flows_taskiq` and `quiz_flow_taskiq` — both re-exported (the latter shadows the former in `__all__`, matching the quiz-specific version). This matches pre-existing Celery behavior where the same name existed in both modules.

## Known Issues

- Remaining Celery imports in non-task files (task_queue.py, celery_integration.py, sentry.py, monitoring_config.py, pause_resume.py, settings, metrics) — all scoped to T04.
- `generate_quiz_report` name collision between flows_taskiq and quiz_flow_taskiq — both exported, last import wins. Callers should use explicit module import if they need the flows version.

## Files Created/Modified

- `backend-hormonia/app/tasks/__init__.py` — Rewritten: re-exports 72 task functions from 13 *_taskiq.py modules
- `backend-hormonia/app/core/__init__.py` — Cleaned: removed all event_loop_manager imports/exports
- `backend-hormonia/app/celery_app.py` — Deleted
- `backend-hormonia/app/core/async_context_manager.py` — Deleted
- `backend-hormonia/app/core/event_loop_manager.py` — Deleted
- `backend-hormonia/app/utils/async_helpers.py` — Deleted
- `backend-hormonia/app/services/async_handler.py` — Deleted
- `backend-hormonia/app/tasks/base.py` — Deleted
- `backend-hormonia/app/tasks/config.py` — Deleted
- `backend-hormonia/app/tasks/celery_metrics.py` — Deleted
- `backend-hormonia/app/tasks/queue_monitor.py` — Deleted
- `backend-hormonia/app/tasks/messaging.py` — Deleted
- `backend-hormonia/app/tasks/alerts.py` — Deleted
- `backend-hormonia/app/tasks/monitoring.py` — Deleted
- `backend-hormonia/app/tasks/flow_automation.py` — Deleted
- `backend-hormonia/app/tasks/follow_up.py` — Deleted
- `backend-hormonia/app/tasks/lgpd_tasks.py` — Deleted
- `backend-hormonia/app/tasks/quiz_link_tasks.py` — Deleted
- `backend-hormonia/app/tasks/reports.py` — Deleted
- `backend-hormonia/app/tasks/saga_monitoring.py` — Deleted
- `backend-hormonia/app/tasks/saga_retry.py` — Deleted
- `backend-hormonia/app/tasks/webhook_dlq.py` — Deleted
- `backend-hormonia/app/tasks/audit_cleanup.py` — Deleted
- `backend-hormonia/app/tasks/flows/` — Deleted directory (8 files)
- `backend-hormonia/app/tasks/quiz_flow/` — Deleted directory (6 files)
- `backend-hormonia/app/tasks/lgpd/` — Deleted directory (2 files)
