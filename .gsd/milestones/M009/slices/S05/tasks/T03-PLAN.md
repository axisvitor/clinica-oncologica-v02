---
estimated_steps: 6
estimated_files: 30
---

# T03: Delete all Celery task files, bridge code, and rewrite package inits

**Slice:** S05 — Celery removal + bridge cleanup
**Milestone:** M009

## Description

With helpers extracted into `app/tasks/helpers/` (T01) and TODO(S05) call sites resolved (T02), all Celery task files and bridge code are dead code. This task deletes ~25 files and 3 directories, then rewrites package init files to export from Taskiq modules.

## Steps

1. **Delete bridge code files** (5 files):
   ```bash
   rm backend-hormonia/app/celery_app.py
   rm backend-hormonia/app/core/async_context_manager.py
   rm backend-hormonia/app/utils/async_helpers.py
   rm backend-hormonia/app/services/async_handler.py
   rm backend-hormonia/app/core/event_loop_manager.py
   ```

2. **Delete Celery task infrastructure** (4 files):
   ```bash
   rm backend-hormonia/app/tasks/base.py
   rm backend-hormonia/app/tasks/config.py
   rm backend-hormonia/app/tasks/celery_metrics.py
   rm backend-hormonia/app/tasks/queue_monitor.py
   ```

3. **Delete all Celery task files** (12 files):
   ```bash
   rm backend-hormonia/app/tasks/messaging.py
   rm backend-hormonia/app/tasks/alerts.py
   rm backend-hormonia/app/tasks/monitoring.py
   rm backend-hormonia/app/tasks/flow_automation.py
   rm backend-hormonia/app/tasks/follow_up.py
   rm backend-hormonia/app/tasks/lgpd_tasks.py
   rm backend-hormonia/app/tasks/quiz_link_tasks.py
   rm backend-hormonia/app/tasks/reports.py
   rm backend-hormonia/app/tasks/saga_monitoring.py
   rm backend-hormonia/app/tasks/saga_retry.py
   rm backend-hormonia/app/tasks/webhook_dlq.py
   rm backend-hormonia/app/tasks/audit_cleanup.py
   ```

4. **Delete entire Celery task directories** (3 directories):
   ```bash
   rm -rf backend-hormonia/app/tasks/flows/
   rm -rf backend-hormonia/app/tasks/quiz_flow/
   rm -rf backend-hormonia/app/tasks/lgpd/
   ```

5. **Rewrite `app/tasks/__init__.py`** — Replace the current Celery-centric init with one that re-exports key task names from `*_taskiq.py` modules. The goal is that `from app.tasks import send_scheduled_message` still works but now points to the Taskiq version.

   The new init should:
   - Have a docstring like `"""Taskiq tasks package for Hormonia Backend System."""`
   - Import and re-export the most commonly used task functions from Taskiq modules
   - NOT import from any Celery module (obviously — they're deleted)
   - Import from the helpers package for shared utility re-exports if needed
   - Keep the `__all__` list updated

   Key re-exports to include (these are the task names that external code may reference):
   - From `messaging_taskiq`: `send_scheduled_message`, `process_scheduled_messages`, `retry_failed_messages`, `send_bulk_messages`, `cleanup_old_messages`, `generate_message_analytics`, `process_whatsapp_dlq`, `process_dlq_messages`, `retry_pending_welcome_messages`
   - From `flows_taskiq`: `process_daily_flows`, `cleanup_old_flow_data`, `process_monthly_quizzes`, `generate_quiz_report`, `monitor_flow_task_health`, `detect_stuck_flows`, `retry_failed_flow_send`
   - From `alerts_taskiq`: `check_patient_alerts`, `process_alert_escalation`, `process_alert_notification`, `cleanup_resolved_alerts`, `generate_alert_metrics`, `periodic_alert_check`, `periodic_escalation_check`
   - From `follow_up_taskiq`: `execute_pending_follow_ups`, `process_escalation_alerts`, `cleanup_old_contexts`
   - From `lgpd_taskiq`: `persist_lgpd_audit_log`, `cleanup_expired_lgpd_audit_logs`
   - From `reports_taskiq`: `generate_patient_report`, `generate_scheduled_reports`
   - From `monitoring_taskiq`: `system_health_check`, `performance_metrics_collection`, etc. (use actual function names from the module)
   - From `quiz_flow_taskiq`, `quiz_link_taskiq`, `saga_retry_taskiq`, `saga_monitoring_taskiq`, `audit_taskiq`, `webhook_dlq_taskiq`: key task names

   **IMPORTANT:** Check the actual function names in each `*_taskiq.py` module. The Taskiq versions may have slightly different names than the Celery originals (e.g., `system_health_check` vs `system_health_check_task`). Use the actual names.

   **IMPORTANT:** Keep the init lightweight — use lazy imports or standard imports but do NOT trigger the entire settings validation chain. The Taskiq modules import `broker` from `taskiq_broker` which reads Redis URL from env vars directly (per D003), NOT from app.config.settings. So importing them should be safe without DATABASE_URL etc. However, some Taskiq modules import from `app.config.settings.tasks` for constants — this may trigger settings validation. If this is a concern, wrap imports in a try/except or use lazy import pattern. Test this after writing.

6. **Clean `app/core/__init__.py`** — Remove all event_loop_manager imports and exports:
   - Remove: `from .event_loop_manager import (EventLoopManager, async_to_sync, AsyncFlowEngineBase, ManagedAsyncService, get_event_loop_manager, cleanup_all_loops)`
   - Remove all those names from `__all__`
   - If nothing else is exported, make the file a minimal package init with just a docstring

## Must-Haves

- [ ] All 25+ Celery files deleted
- [ ] All 3 Celery task directories deleted (`flows/`, `quiz_flow/`, `lgpd/`)
- [ ] `celery_app.py` deleted
- [ ] `async_context_manager.py` deleted
- [ ] `async_helpers.py` deleted
- [ ] `event_loop_manager.py` deleted
- [ ] `async_handler.py` deleted
- [ ] `tasks/__init__.py` re-exports from `*_taskiq.py` modules only
- [ ] `core/__init__.py` has no event_loop_manager references
- [ ] All 13 `*_taskiq.py` modules still parse after deletions
- [ ] Taskiq schedule label count preserved (≥47, matching S04's verified parity)

## Verification

```bash
# 1. Key files deleted
test ! -f backend-hormonia/app/celery_app.py && echo PASS || echo "FAIL: celery_app.py"
test ! -f backend-hormonia/app/core/async_context_manager.py && echo PASS || echo "FAIL: async_context_manager"
test ! -f backend-hormonia/app/utils/async_helpers.py && echo PASS || echo "FAIL: async_helpers"
test ! -f backend-hormonia/app/services/async_handler.py && echo PASS || echo "FAIL: async_handler"
test ! -f backend-hormonia/app/core/event_loop_manager.py && echo PASS || echo "FAIL: event_loop_manager"
test ! -f backend-hormonia/app/tasks/base.py && echo PASS || echo "FAIL: base.py"
test ! -f backend-hormonia/app/tasks/messaging.py && echo PASS || echo "FAIL: messaging.py"

# 2. Directories deleted
test ! -d backend-hormonia/app/tasks/flows && echo PASS || echo "FAIL: flows/"
test ! -d backend-hormonia/app/tasks/quiz_flow && echo PASS || echo "FAIL: quiz_flow/"
test ! -d backend-hormonia/app/tasks/lgpd && echo PASS || echo "FAIL: lgpd/"

# 3. All Taskiq modules still parse
python3 -c "
import ast, glob, sys
errors = []
for f in glob.glob('backend-hormonia/app/tasks/*_taskiq.py'):
    try:
        ast.parse(open(f).read())
    except SyntaxError as e:
        errors.append(f'{f}: {e}')
if errors:
    print('FAIL:', errors)
    sys.exit(1)
print(f'PASS — {len(glob.glob(\"backend-hormonia/app/tasks/*_taskiq.py\"))} Taskiq modules parse OK')
"

# 4. tasks/__init__.py parses and imports only from taskiq/helpers
python3 -c "
import ast, sys
tree = ast.parse(open('backend-hormonia/app/tasks/__init__.py').read())
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom) and node.module:
        mod = node.module
        # Allow: .xxx_taskiq, app.tasks.xxx_taskiq, .helpers.xxx, app.tasks.helpers.xxx, .taskiq_base
        if 'taskiq' not in mod and 'helpers' not in mod:
            print(f'FAIL — unexpected import: from {mod}')
            sys.exit(1)
print('PASS — tasks/__init__.py imports only from taskiq/helpers modules')
"

# 5. core/__init__.py has no event_loop_manager
! grep 'event_loop_manager' backend-hormonia/app/core/__init__.py && echo PASS || echo "FAIL"

# 6. Schedule labels preserved (Taskiq-side only — celery_app.py is now deleted)
python3 -c "
import re, glob, sys
count = 0
for f in glob.glob('backend-hormonia/app/tasks/*_taskiq.py'):
    content = open(f).read()
    count += len(re.findall(r'schedule=', content))
if count < 47:
    print(f'FAIL — expected >=47 schedule labels, found {count}')
    sys.exit(1)
print(f'PASS — {count} schedule labels preserved')
"
```

## Inputs

- T01 completed: all helpers extracted to `app/tasks/helpers/`, all Taskiq modules import from helpers
- T02 completed: all TODO(S05) call sites resolved, no Celery dispatch in trigger_service.py or recovery.py
- `backend-hormonia/scripts/verify_schedule_parity.sh` — schedule parity verification script from S04

## Expected Output

- ~25 Celery files deleted, 3 directories deleted
- `backend-hormonia/app/tasks/__init__.py` — rewritten to export from Taskiq modules
- `backend-hormonia/app/core/__init__.py` — cleaned of event_loop_manager exports
