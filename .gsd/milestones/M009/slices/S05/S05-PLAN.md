# S05: Celery removal + bridge cleanup

**Goal:** Remove all Celery code, bridge code, and dependencies — leaving a clean codebase where all 72 tasks run exclusively through Taskiq with zero Celery imports.
**Demo:** `python3 -c "import ast, sys, os; ..."` AST scan finds zero Celery imports in the entire `app/` directory. `celery_app.py`, `async_context_manager.py`, `async_helpers.py` are deleted. `requirements.txt` has no celery/kombu/amqp/billiard/flower/asgiref. Backend imports `from app.taskiq_broker import broker` cleanly. All 13 `*_taskiq.py` modules parse without error.

## Must-Haves

- Pure helpers extracted from Celery modules into `app/tasks/helpers/` before any Celery file is deleted
- All 10 Taskiq modules updated to import helpers from new shared modules (not from Celery originals)
- TODO(S05) call sites resolved: trigger_service.py (2 sites) and recovery.py (1 site) converted to Taskiq dispatch
- `celery_app.py`, `async_context_manager.py`, `async_helpers.py`, `event_loop_manager.py`, `async_handler.py` deleted
- All 16 Celery task `.py` files deleted, plus `tasks/flows/`, `tasks/quiz_flow/`, `tasks/lgpd/` directories
- `tasks/base.py`, `tasks/config.py`, `tasks/celery_metrics.py`, `tasks/queue_monitor.py` deleted
- `tasks/__init__.py` rewritten to re-export from `*_taskiq.py` modules
- `core/__init__.py` cleaned (no event_loop_manager exports)
- Health endpoints, Sentry, settings, metrics cleaned of Celery references
- Task API endpoints (crud, operations, bulk) cleaned of Celery dispatch/revoke
- `celery`, `celery[redis]`, `asgiref`, `flower` removed from `requirements.txt`
- `docker-compose.yml` worker/beat services use `taskiq` commands
- `Makefile` targets use `taskiq` commands
- Zero Celery imports in AST scan of entire `app/` directory

## Proof Level

- This slice proves: operational (clean codebase with no Celery dependency)
- Real runtime required: no (AST parse + import verification; runtime proof is S06)
- Human/UAT required: no

## Verification

```bash
# V1: Zero Celery imports (AST-based, no false positives from comments)
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
                    if 'celery' in name.lower():
                        errors.append(f'{path}:{node.lineno}: {name}')
if errors:
    print('FAIL — Celery imports found:')
    for e in errors: print(f'  {e}')
    sys.exit(1)
else:
    print('PASS — Zero Celery imports')
"

# V2: All Taskiq modules parse cleanly
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

# V3: No celery/kombu/billiard/flower/asgiref in requirements.txt
! grep -iE 'celery|kombu|amqp|billiard|flower|asgiref' backend-hormonia/requirements.txt && echo PASS || echo FAIL

# V4: Key Celery files deleted
test ! -f backend-hormonia/app/celery_app.py && echo PASS || echo FAIL
test ! -f backend-hormonia/app/core/async_context_manager.py && echo PASS || echo FAIL
test ! -f backend-hormonia/app/utils/async_helpers.py && echo PASS || echo FAIL
test ! -f backend-hormonia/app/services/async_handler.py && echo PASS || echo FAIL
test ! -f backend-hormonia/app/core/event_loop_manager.py && echo PASS || echo FAIL

# V5: Celery task directories deleted
test ! -d backend-hormonia/app/tasks/flows && echo PASS || echo FAIL
test ! -d backend-hormonia/app/tasks/quiz_flow && echo PASS || echo FAIL
test ! -d backend-hormonia/app/tasks/lgpd && echo PASS || echo FAIL

# V6: Schedule labels preserved (Taskiq-side count — celery_app.py is deleted)
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

# V7: Helper modules exist and parse
python3 -c "
import ast, glob, sys
helpers = glob.glob('backend-hormonia/app/tasks/helpers/*.py')
helpers = [h for h in helpers if '__pycache__' not in h]
if len(helpers) < 9:
    print(f'FAIL — expected >=9 helper modules, found {len(helpers)}')
    sys.exit(1)
for f in helpers:
    try: ast.parse(open(f).read())
    except SyntaxError as e:
        print(f'FAIL: {f}: {e}')
        sys.exit(1)
print(f'PASS — {len(helpers)} helper modules parse OK')
"

# V8: No TODO(S05) remaining
! grep -rn 'TODO(S05)' backend-hormonia/app/ --include='*.py' && echo PASS || echo FAIL

# V9: tasks/__init__.py imports from *_taskiq modules (not Celery)
python3 -c "
import ast, sys
tree = ast.parse(open('backend-hormonia/app/tasks/__init__.py').read())
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        mod = node.module or ''
        if 'celery' in mod.lower() or (mod.startswith('.') and 'taskiq' not in mod and mod not in ['.helpers', '.helpers.*']):
            # Allow imports from helpers and taskiq modules only
            if 'helpers' not in mod and 'taskiq' not in mod:
                print(f'FAIL — non-taskiq import: {mod}')
                sys.exit(1)
print('PASS — tasks/__init__.py clean')
"
```

## Observability / Diagnostics

- Runtime signals: All 72 Taskiq tasks retain `log_task_start/success/error` structured logging (unchanged from S02-S04)
- Inspection surfaces: `bash backend-hormonia/scripts/verify_schedule_parity.sh` — confirms schedule parity preserved after deletions
- Failure visibility: AST-based import scan catches any surviving Celery references at file level, not just grep
- Diagnostic check: If any Taskiq module fails to parse after helper extraction, `python3 -c "import ast; ast.parse(open('...').read())"` surfaces the exact `SyntaxError` with line/col. If a helper import fails at runtime, the structured `log_task_error` in each Taskiq task emits the `ImportError` traceback to stdout/Sentry.
- Failure-path verification: `detect_stuck_flows` logs `"Failed to recover stuck flow"` with `flow_state_id`/`patient_id` on recovery failure and increments `failed_count` in its return dict. `attempt_recovery` raises `ValueError` on missing prompt_message_id — surfaced via Taskiq's structured error logging and Sentry.
- Redaction constraints: none

## Integration Closure

- Upstream surfaces consumed: All 13 `*_taskiq.py` modules from S02/S03/S04, `taskiq_broker.py` from S01, `schedule_task_at()` from S01
- New wiring introduced in this slice: `app/tasks/helpers/` package (shared helper modules), `tasks/__init__.py` re-export from Taskiq, trigger_service.py and recovery.py wired to Taskiq dispatch
- What remains before the milestone is truly usable end-to-end: S06 runtime verification (pipeline M008 end-to-end via Taskiq)

## Tasks

- [x] **T01: Extract pure helpers from Celery modules into shared helper package** `est:30m`
  - Why: 10 Taskiq modules import ~40+ helper functions from Celery modules that will be deleted in T03. Helpers must be relocated first or all Taskiq tasks break at import time. This is the hard prerequisite for the entire slice.
  - Files: `app/tasks/helpers/__init__.py` (new), `app/tasks/helpers/messaging_helpers.py` (new), `app/tasks/helpers/alerts_helpers.py` (new), `app/tasks/helpers/lgpd_helpers.py` (new), `app/tasks/helpers/reports_helpers.py` (new), `app/tasks/helpers/saga_helpers.py` (new), `app/tasks/helpers/follow_up_helpers.py` (new), `app/tasks/helpers/quiz_link_helpers.py` (new), `app/tasks/helpers/flow_helpers.py` (new), `app/tasks/helpers/quiz_flow_helpers.py` (new), plus all 10 `*_taskiq.py` modules (import updates)
  - Do: Copy each helper function/constant from its Celery source module into the corresponding `helpers/*_helpers.py` file. Include all necessary imports for each helper. Update all 10 Taskiq modules to import from `app.tasks.helpers.*` instead of from Celery modules. Verify each Taskiq module still parses after the import change.
  - Verify: `python3 -c "import ast; ..."` — all 13 `*_taskiq.py` parse OK, no imports from Celery task modules remain in any `*_taskiq.py` file
  - Done when: All Taskiq modules import helpers exclusively from `app/tasks/helpers/`, zero imports from Celery task modules in any `*_taskiq.py` file

- [x] **T02: Resolve TODO(S05) call sites — trigger_service.py and recovery.py** `est:20m`
  - Why: 3 remaining call sites still dispatch via Celery `.apply_async(eta=)` and `.delay()`. These must be converted to Taskiq dispatch before Celery files are deleted in T03.
  - Files: `app/domain/quizzes/integration/flow_integration/trigger_service.py`, `app/services/flow/recovery.py`, `app/tasks/flows_taskiq.py`
  - Do: (1) trigger_service.py lines 724,732: replace `send_quiz_link_reminder_task.apply_async(args=[...], eta=...)` with `await schedule_task_at(send_quiz_reminder, reminder_time, str(quiz_session_id), hours)` — function is already `async def _schedule_link_reminders`. Import `schedule_task_at` from `taskiq_base` and `send_quiz_reminder` from `quiz_link_taskiq`. Remove the Celery import of `send_quiz_link_reminder_task`. (2) recovery.py: make `attempt_recovery()` async, replace `async_to_sync(flow_manager.advance_patient_flow)(...)` with `await flow_manager.advance_patient_flow(...)`, replace `retry_failed_flow_send.delay(...)` with `await retry_failed_flow_send.kiq(...)` importing from `flows_taskiq`. Remove `from asgiref.sync import async_to_sync` import. (3) flows_taskiq.py: update `detect_stuck_flows` to `await attempt_recovery(...)` since it's now async. Remove all TODO(S05) comments.
  - Verify: `grep -rn "TODO(S05)" backend-hormonia/app/ --include="*.py"` returns nothing. All 3 files parse with `ast.parse()`. No `.delay()` or `.apply_async()` in trigger_service.py or recovery.py.
  - Done when: Zero TODO(S05) markers, zero Celery dispatch calls in trigger_service.py and recovery.py, all files parse cleanly

- [ ] **T03: Delete all Celery task files, bridge code, and rewrite package inits** `est:30m`
  - Why: With helpers extracted (T01) and call sites resolved (T02), all Celery task files and bridge code are dead. Deleting them fulfills R084 (bridge code removal) and unblocks the infrastructure cleanup in T04.
  - Files: ~25 files deleted, `app/tasks/__init__.py` (rewrite), `app/core/__init__.py` (clean)
  - Do: (1) Delete bridge code: `celery_app.py`, `core/async_context_manager.py`, `utils/async_helpers.py`, `services/async_handler.py`, `core/event_loop_manager.py`. (2) Delete task infrastructure: `tasks/base.py`, `tasks/config.py`, `tasks/celery_metrics.py`, `tasks/queue_monitor.py`. (3) Delete all Celery task files: `tasks/messaging.py`, `tasks/alerts.py`, `tasks/monitoring.py`, `tasks/flow_automation.py`, `tasks/follow_up.py`, `tasks/lgpd_tasks.py`, `tasks/quiz_link_tasks.py`, `tasks/reports.py`, `tasks/saga_monitoring.py`, `tasks/saga_retry.py`, `tasks/webhook_dlq.py`, `tasks/audit_cleanup.py`. (4) Delete entire directories: `tasks/flows/`, `tasks/quiz_flow/`, `tasks/lgpd/`. (5) Rewrite `tasks/__init__.py` to re-export key task functions from `*_taskiq.py` modules. (6) Clean `core/__init__.py` — remove all event_loop_manager imports/exports.
  - Verify: Celery files don't exist. `tasks/__init__.py` parses and imports from taskiq modules only. All 13 `*_taskiq.py` modules parse. `bash scripts/verify_schedule_parity.sh` still passes.
  - Done when: All Celery task files + bridge code deleted, package inits rewritten, all Taskiq modules still parse cleanly

- [ ] **T04: Clean infrastructure Celery references, update requirements, docker-compose, Makefile** `est:30m`
  - Why: After Celery code is deleted (T03), infrastructure files still reference Celery in health checks, settings, metrics, Sentry, task API endpoints, and build/deploy configs. Cleaning these fulfills R085 (deps removed) and makes the AST zero-import scan pass.
  - Files: `app/task_queue.py`, `app/api/v2/routers/health/core.py`, `app/api/v2/routers/health/service_health.py`, `app/api/v2/routers/tasks/utils/celery_integration.py` (delete), `app/api/v2/routers/tasks/dependencies.py`, `app/api/v2/routers/tasks/endpoints/operations.py`, `app/api/v2/routers/tasks/endpoints/bulk.py`, `app/api/v2/routers/tasks/endpoints/crud.py`, `app/utils/task_monitoring.py` (delete), `app/services/flow/management/pause_resume.py`, `app/core/setup/sentry.py`, `app/core/monitoring_config.py`, `app/core/metrics.py`, `app/config/settings/integrations.py`, `app/config/settings/__init__.py`, `app/config/settings/performance.py`, `requirements.txt`, `docker-compose.yml`, `Makefile`
  - Do: (1) `task_queue.py`: remove `TaskQueue` class, `task_queue` singleton, `ensure_task_registry_loaded()`, all Celery imports — keep Redis store functions (`store_task`, `update_task`, `get_task`, `list_tasks`, `append_task_log`, `delete_task`) and `get_taskiq_broker()`/`get_taskiq_broker_health()`. (2) Health endpoints: remove Celery inspect blocks from `core.py` (lines 126-139, 145-146), keep Taskiq-only check. Remove `celery:metrics:*` read and Celery inspect from `service_health.py`. (3) Delete `celery_integration.py` and `task_monitoring.py`. (4) Task API: clean `dependencies.py` (remove celery_integration imports), `operations.py` and `bulk.py` (replace `celery_app.control.revoke()` with no-op/log), `crud.py` (replace `celery_app.send_task()` with stub or Taskiq dispatch). (5) `pause_resume.py`: remove `AsyncResult.revoke()` block (lines 227-240), replace with a logged no-op. (6) Sentry: remove `CeleryIntegration` from `sentry.py` and `monitoring_config.py`. (7) Settings: remove `CELERY_*` fields from `integrations.py`, `__init__.py`, `performance.py`. (8) Metrics: remove `app_celery_task_duration_seconds`, `app_celery_queue_size`, `track_celery_task_metrics`, `update_celery_queue_size` from `metrics.py`. (9) `requirements.txt`: remove `celery>=5.6.2,<6.0.0`, `celery[redis]>=5.6.2,<6.0.0`, `asgiref>=3.11.0,<4.0.0`, `flower==2.0.1`. (10) `docker-compose.yml`: worker service command → `taskiq worker app.taskiq_broker:broker`, beat service command → `taskiq scheduler app.taskiq_broker:scheduler`. Keep `CELERY_BROKER_URL` env var (Taskiq broker reads it as fallback per D003). (11) `Makefile`: replace celery targets with taskiq equivalents.
  - Verify: AST zero-import scan passes. `grep -iE 'celery|kombu|amqp|billiard|flower|asgiref' requirements.txt` returns nothing. All modified files parse with `ast.parse()`.
  - Done when: Zero Celery imports in AST scan, zero Celery deps in requirements.txt, docker-compose and Makefile use Taskiq commands, all infrastructure files clean

## Files Likely Touched

- `app/tasks/helpers/` (new package — ~10 helper modules)
- `app/tasks/*_taskiq.py` (import updates — 10 files)
- `app/tasks/__init__.py` (rewrite)
- `app/core/__init__.py` (clean)
- `app/domain/quizzes/integration/flow_integration/trigger_service.py`
- `app/services/flow/recovery.py`
- `app/tasks/flows_taskiq.py`
- `app/celery_app.py` (delete)
- `app/core/async_context_manager.py` (delete)
- `app/utils/async_helpers.py` (delete)
- `app/services/async_handler.py` (delete)
- `app/core/event_loop_manager.py` (delete)
- `app/tasks/base.py`, `config.py`, `celery_metrics.py`, `queue_monitor.py` (delete)
- `app/tasks/messaging.py`, `alerts.py`, `monitoring.py`, etc. (delete — 12 files)
- `app/tasks/flows/` (delete directory)
- `app/tasks/quiz_flow/` (delete directory)
- `app/tasks/lgpd/` (delete directory)
- `app/task_queue.py`
- `app/api/v2/routers/health/core.py`, `service_health.py`
- `app/api/v2/routers/tasks/utils/celery_integration.py` (delete)
- `app/api/v2/routers/tasks/dependencies.py`
- `app/api/v2/routers/tasks/endpoints/operations.py`, `bulk.py`, `crud.py`
- `app/utils/task_monitoring.py` (delete)
- `app/services/flow/management/pause_resume.py`
- `app/core/setup/sentry.py`, `app/core/monitoring_config.py`, `app/core/metrics.py`
- `app/config/settings/integrations.py`, `__init__.py`, `performance.py`
- `requirements.txt`
- `docker-compose.yml`
- `Makefile`
