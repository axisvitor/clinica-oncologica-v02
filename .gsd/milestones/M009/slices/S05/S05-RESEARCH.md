# S05: Celery removal + bridge cleanup — Research

**Date:** 2026-03-16
**Depth:** Targeted

## Summary

S05 is a large deletion + wiring cleanup slice. All 72 Taskiq tasks already exist across 13 `*_taskiq.py` modules (S02–S04). The work is: (1) relocate pure helpers that Taskiq modules import from Celery modules into standalone shared modules so imports survive deletion, (2) delete all Celery task files, `celery_app.py`, and bridge code (`async_context_manager.py`, `async_helpers.py`), (3) resolve the 3 TODO(S05) call sites (trigger_service.py × 2, recovery.py × 1) that still dispatch via Celery, (4) remove Celery deps from `requirements.txt`, (5) clean Celery references from health checks, task API, `task_queue.py`, Sentry, settings, docker-compose, Makefile, and metrics.

The primary risk is the **pure helper dependency chain**: 8 Taskiq modules import ~35 helper functions from Celery modules. Deleting Celery modules without relocating those helpers will break all Taskiq tasks at import time. The recommended approach is to extract helpers into per-domain `*_helpers.py` shared modules before deleting the Celery originals.

## Recommendation

**Build order: helpers extraction → TODO(S05) call sites → delete Celery files → clean non-task references → verify.**

The natural seam is between "task domain" work (helpers, deletions, call sites) and "infrastructure" work (health, settings, requirements, docker-compose, metrics). Task domain work must come first because it's the dependency-critical path. Infrastructure cleanup is independent and can follow.

## Implementation Landscape

### Key Files

**Files to delete (Celery tasks + bridge code — ~12,800 lines):**

- `app/celery_app.py` (477 lines) — Celery instance, beat_schedule, `run_async_in_celery()`
- `app/core/async_context_manager.py` (457 lines) — AsyncTaskTracker, event loop management for Celery
- `app/utils/async_helpers.py` (430 lines) — `run_async()`, `run_async_in_sync()`, `run_async_in_thread()`, `async_to_sync()`
- `app/tasks/__init__.py` (160 lines) — Celery task re-export package init
- `app/tasks/base.py` (228 lines) — BaseTask, DatabaseTask, MessageTask, MonitoringTask, ReportTask
- `app/tasks/config.py` (316 lines) — TaskConfig dataclasses, TASK_ROUTES
- `app/tasks/celery_metrics.py` (698 lines) — Celery-specific Prometheus metrics
- `app/tasks/queue_monitor.py` (258 lines) — Celery queue monitoring
- `app/tasks/messaging.py` (1231 lines)
- `app/tasks/alerts.py` (582 lines)
- `app/tasks/monitoring.py` (614 lines)
- `app/tasks/flow_automation.py` (637 lines)
- `app/tasks/follow_up.py` (895 lines)
- `app/tasks/lgpd_tasks.py` (624 lines)
- `app/tasks/quiz_link_tasks.py` (693 lines)
- `app/tasks/reports.py` (127 lines)
- `app/tasks/saga_monitoring.py` (396 lines)
- `app/tasks/saga_retry.py` (567 lines)
- `app/tasks/webhook_dlq.py` (329 lines)
- `app/tasks/audit_cleanup.py` (251 lines)
- `app/tasks/flows/` directory (2149 lines across 10 files) — base, batch_tasks, cleanup_tasks, flow_tasks, followup_retry, monitoring, monthly_tasks, send_retry, stuck_detection, __init__
- `app/tasks/quiz_flow/` directory (1513 lines across 6 files) — cleanup_tasks, helpers, question_tasks, response_tasks, trigger_tasks, __init__
- `app/tasks/lgpd/` directory (373 lines across 2 files) — reencrypt_patients, __init__
- `app/services/async_handler.py` (~300 lines) — FlowEngine async/sync bridge, zero importers
- `app/core/event_loop_manager.py` (210 lines) — EventLoopManager, only imported by `app/core/__init__.py`

**Pure helper dependencies (must relocate BEFORE deleting Celery modules):**

| Taskiq Module | Imports From | Helpers |
|---|---|---|
| `messaging_taskiq.py` | `messaging.py` | `_build_idempotency_key`, `_compute_next_reminder_time`, `_schedule_next_reminder` |
| `alerts_taskiq.py` | `alerts.py` | `_ALERT_METADATA_REDACTED_FIELDS`, `_sanitize_alert_metadata`, `_build_patient_context` |
| `lgpd_taskiq.py` | `lgpd_tasks.py` | 13 helpers: `_is_patient_context`, `_normalize_action`, `_normalize_data_category`, `_normalize_fields_accessed`, `_normalize_legal_basis`, `_normalize_optional_text`, `_normalize_purpose`, `_normalize_resource_type`, `_resolve_patient_identifier`, `_resolve_patient_uuid`, `_safe_parse_uuid`, `_sanitize_additional_data`, `_SENSITIVE_DATA_CATEGORIES` |
| `reports_taskiq.py` | `reports.py` | `_build_safe_report_path`, `_get_system_actor_uuid`, `_sanitize_report_type` |
| `saga_retry_taskiq.py` | `saga_retry.py` | `_calculate_exponential_backoff`, `_alert_admin_max_retries_exceeded` |
| `follow_up_taskiq.py` | `follow_up.py` | `FOLLOW_UP_DEDUP_WINDOW_SECONDS`, `FOLLOW_UP_DEDUP_LOCK_SECONDS`, `_get_last_follow_up_sent_at_db`, `_is_follow_up_eligible`, `_update_patient_last_message_sent_at` |
| `quiz_link_taskiq.py` | `quiz_link_tasks.py` | `_sanitize_dlq_record`, `_sanitize_error_message`, `_sanitize_limit`, `_token_fingerprint` |
| `flows_taskiq.py` | `flow_automation.py` | `_determine_template_for_patient`, `_get_reminder_message`, `_is_auto_resume_due` |

**TODO(S05) call sites (3 locations, must convert before Celery removal):**

1. `app/domain/quizzes/integration/flow_integration/trigger_service.py:724,732` — `send_quiz_link_reminder_task.apply_async(args=[...], eta=...)` → `await schedule_task_at(send_quiz_reminder, reminder_time, str(quiz_session_id), hours)`. Already `async def _schedule_link_reminders`, so conversion is direct.

2. `app/services/flow/recovery.py:214` — `retry_failed_flow_send.delay(...)` → needs async conversion. `attempt_recovery()` is sync (line 128), uses `async_to_sync` for `flow_manager.advance_patient_flow`. Called by `detect_stuck_flows` Celery task (stuck_detection.py:54). Since the Taskiq version `detect_stuck_flows` in `flows_taskiq.py` already wraps everything in sync session, recovery.py just needs its `.delay()` replaced. Options: (a) make `attempt_recovery` async and use `await retry_failed_flow_send.kiq()` — would need `detect_stuck_flows` Taskiq task to call it with `await`; (b) use `asyncio.get_event_loop().run_until_complete()` for the single `.kiq()` call inside the sync function. Option (a) is cleaner since the Taskiq task is already async.

**Non-task files to clean (infrastructure references to Celery):**

- `app/task_queue.py` (238 lines) — `TaskQueue` class wraps `celery_app`. The `store_task`, `update_task`, `get_task`, `list_tasks`, `append_task_log`, `delete_task` functions are pure Redis-based and Celery-independent — keep them. Remove `TaskQueue` class, `task_queue` singleton, `ensure_task_registry_loaded()` (loads Celery modules). Keep `get_taskiq_broker()` and `get_taskiq_broker_health()`.
- `app/api/v2/routers/health/core.py:113-155` — Readiness probe has dual Taskiq+Celery check. Remove Celery branch, keep Taskiq-only check.
- `app/api/v2/routers/health/service_health.py:86,105-134` — `_read_avg_task_duration()` reads `celery:metrics:*` Redis key. `check_worker_health()` has Celery inspect block. Remove Celery sections.
- `app/api/v2/routers/tasks/utils/celery_integration.py` (141 lines) — Entire file is Celery-specific (`AsyncResult`, `celery.states`). Delete or replace with Taskiq-based task status retrieval.
- `app/api/v2/routers/tasks/dependencies.py` — Imports from `celery_integration.py`. Update to remove Celery references.
- `app/api/v2/routers/tasks/endpoints/operations.py:78` — `celery_app.control.revoke()`. Replace with no-op or Taskiq equivalent.
- `app/api/v2/routers/tasks/endpoints/bulk.py:101` — `celery_app.control.revoke()`. Same treatment.
- `app/api/v2/routers/tasks/endpoints/crud.py:332` — `celery_app.send_task()`. Replace with Taskiq dispatch.
- `app/utils/task_monitoring.py` (320 lines) — `TaskMonitor` class wraps Celery's `State()` and `control.inspect()`. Only imported by `monitoring.py` endpoint. Delete or stub.
- `app/services/flow/management/pause_resume.py:227-240` — `AsyncResult(...).revoke()` for cancelling pending messages. Replace with no-op or Taskiq cancellation.
- `app/core/setup/sentry.py:38,63` — `CeleryIntegration(monitor_beat_tasks=True)`. Remove from integrations list.
- `app/core/monitoring_config.py:94` — `from sentry_sdk.integrations.celery import CeleryIntegration`. Same treatment.
- `app/core/metrics.py:70-78,217-229,319-321` — Celery-specific Prometheus histograms/gauges. Remove (no external callers).
- `app/core/__init__.py` — Exports from `event_loop_manager`. Update after deleting event_loop_manager.
- `app/config/settings/integrations.py:283-322` — CELERY_* settings fields. Remove.
- `app/config/settings/__init__.py:148-151` — CELERY_* boolean field names. Remove.
- `app/config/settings/performance.py` — CELERY_WORKER_* performance settings. Remove.
- `app/schemas/v2/tasks.py:185,294` — `celery_task_name`, `celery_task_id` fields. These are API-facing — rename to `task_name_ref` / `backend_task_id` or keep as-is for API stability. Recommend keeping field names for backward compat since they're just string fields.
- `docker-compose.yml:42,59` — `worker` and `beat` services use `celery` commands. Replace with `taskiq worker` and `taskiq scheduler` commands.
- `Makefile:22,38,41,92-101,183-185` — Celery make targets. Replace with Taskiq equivalents.
- `requirements.txt` — Remove: `celery>=5.6.2,<6.0.0`, `celery[redis]>=5.6.2,<6.0.0`, `asgiref>=3.11.0,<4.0.0`, `flower==2.0.1`. Keep: `prometheus-client` (used elsewhere), `redis` (used by Taskiq).

**Files with Celery in comments/docstrings only (cosmetic — low priority):**

- `app/orchestration/saga_orchestrator/orchestrator.py:57` — comment about sync Session from Celery
- `app/orchestration/saga_orchestrator/db_adapter.py:4` — docstring about Celery tasks
- Various `.md` docs, ARCHITECTURE files — documentation references
- `app/models/message.py`, `app/domain/messaging/scheduling/*` — comments mentioning Celery

### Build Order

1. **T1: Extract pure helpers from Celery modules into shared modules** — Create `app/tasks/helpers/` package with per-domain helper modules (e.g., `messaging_helpers.py`, `alerts_helpers.py`, etc.). Copy the ~35 helper functions/constants from Celery modules. Update all 8 Taskiq modules to import from new locations. This unblocks all subsequent deletions.

2. **T2: Resolve TODO(S05) call sites** — Convert trigger_service.py (2 sites) from `.apply_async(eta=)` to `await schedule_task_at()`. Convert recovery.py: make `attempt_recovery()` async, replace `.delay()` with `await .kiq()`, update the Taskiq `detect_stuck_flows` caller to `await attempt_recovery()`. Remove `from asgiref.sync import async_to_sync` from recovery.py.

3. **T3: Delete all Celery task files + bridge code** — Delete `celery_app.py`, `async_context_manager.py`, `async_helpers.py`, `tasks/__init__.py`, `tasks/base.py`, `tasks/config.py`, `tasks/celery_metrics.py`, `tasks/queue_monitor.py`, all 16 Celery task `.py` files, entire `tasks/flows/` directory, entire `tasks/quiz_flow/` directory, `tasks/lgpd/` directory, `services/async_handler.py`, `core/event_loop_manager.py`. Rewrite `tasks/__init__.py` to export from `*_taskiq.py` modules. Update `core/__init__.py`.

4. **T4: Clean non-task infrastructure references** — Clean `task_queue.py` (remove TaskQueue class + Celery imports, keep Redis store functions + Taskiq accessors). Clean health endpoints (remove Celery inspect, keep Taskiq-only checks). Clean/delete `celery_integration.py`, `task_monitoring.py`. Clean Sentry (remove CeleryIntegration). Clean settings (remove CELERY_* fields). Clean metrics (remove Celery histograms/gauges). Clean `pause_resume.py` (remove AsyncResult.revoke). Clean task API endpoints (crud, operations, bulk — replace Celery dispatch/revoke). Update `requirements.txt` (remove celery, celery[redis], asgiref, flower). Update `docker-compose.yml` and `Makefile` (Celery → Taskiq commands).

### Verification Approach

```bash
# 1. Zero Celery imports in the codebase (excluding docs, comments)
python3 -c "
import ast, sys, os
errors = []
for root, dirs, files in os.walk('backend-hormonia/app'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if not f.endswith('.py'): continue
        path = os.path.join(root, f)
        try:
            tree = ast.parse(open(path).read())
        except: continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, 'module', '') or ''
                names = [a.name for a in node.names]
                for name in [mod] + names:
                    if 'celery' in name.lower() and 'celery_integration' not in name:
                        errors.append(f'{path}:{node.lineno}: {name}')
if errors:
    print('FAIL — Celery imports found:')
    for e in errors: print(f'  {e}')
    sys.exit(1)
else:
    print('PASS — Zero Celery imports')
"

# 2. All Taskiq modules parse cleanly
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

# 3. No celery/kombu/billiard/flower in requirements.txt
grep -iE 'celery|kombu|amqp|billiard|flower|asgiref' backend-hormonia/requirements.txt && echo FAIL || echo PASS

# 4. celery_app.py deleted
test ! -f backend-hormonia/app/celery_app.py && echo PASS || echo FAIL

# 5. Bridge code deleted
test ! -f backend-hormonia/app/core/async_context_manager.py && echo PASS || echo FAIL
test ! -f backend-hormonia/app/utils/async_helpers.py && echo PASS || echo FAIL

# 6. Schedule parity preserved
bash backend-hormonia/scripts/verify_schedule_parity.sh

# 7. Backend imports without error
cd backend-hormonia && python3 -c "from app.taskiq_broker import broker; print('Broker import OK')"
```

## Constraints

- **Pure helper extraction is a hard prerequisite** — 8 Taskiq modules will fail to import if their source Celery modules are deleted first. Helpers must be relocated before any deletion.
- **recovery.py `async_to_sync` import from `asgiref`** — recovery.py uses `asgiref.sync.async_to_sync` for `flow_manager.advance_patient_flow()` (line 198). If asgiref is removed from requirements, this call must be converted to direct `await` or the function made async. Since `attempt_recovery` needs to become async anyway for `.kiq()`, this resolves itself.
- **Task API backward compatibility** — `celery_task_name` and `celery_task_id` are API-facing schema fields. Renaming breaks clients. Recommend keeping field names as-is (they're just strings).
- **`app/services/dlq/message_processor.py`** uses `_run_async()` internally (self-contained bridge, not from async_helpers). This is NOT Celery-specific — it's the DLQ processor's own async bridge. Do not delete.
- **`app/core/redis_manager/sync_client.py`** has `_run_async()` — self-contained method on the SyncRedisClient class. Not related to Celery. Do not touch.
- **`app/domain/quizzes/resilience/link_resilience.py`** has `_run_async_safely()` — self-contained method. Not Celery-related. Do not touch.

## Common Pitfalls

- **Deleting Celery modules before extracting helpers** — 8 Taskiq modules import ~35 helpers from Celery modules. Delete order matters: extract → update imports → delete. Reversing this breaks all task imports.
- **`grep "celery"` false positives** — Comments, docstrings, schema field names, and Redis key names (`celery:metrics:*`) will match. Use AST-based analysis for import verification, not grep.
- **`asgiref` removal breaks recovery.py** — `recovery.py` line 9 imports `from asgiref.sync import async_to_sync`. Must convert `attempt_recovery` to async before removing asgiref from requirements.
- **Task API CRUD endpoint** — `crud.py:332` uses `celery_app.send_task()` to dynamically dispatch tasks by name. This needs a Taskiq equivalent or the endpoint must be disabled/stubbed. The planner should decide whether to implement a Taskiq name-based dispatch or mark this endpoint as deprecated.
- **`_read_avg_task_duration` Redis key** — Reads from `celery:metrics:avg_task_duration`. After removing celery_metrics.py, this key will never be populated. The health endpoint should return 0.0 or be removed.

## Open Risks

- **Task revocation** — `operations.py` and `bulk.py` use `celery_app.control.revoke()` to cancel tasks. Taskiq does not have a built-in revoke mechanism. These endpoints may need to be stubbed or use a Redis-based cancellation flag pattern. Low risk since task revocation is rarely used in this system (only admin API).
- **`crud.py` dynamic task dispatch** — `celery_app.send_task(task_name, ...)` dispatches by registered name. Taskiq tasks are dispatched by reference (`await task.kiq()`), not by string name. This endpoint may need a registry mapping task names to Taskiq task references.
