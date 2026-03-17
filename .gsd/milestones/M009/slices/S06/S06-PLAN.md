# S06: Verificação integrada ponta-a-ponta

**Goal:** All existing tests pass with Taskiq-only imports — zero Celery residue in tests/, complete M008 pipeline coverage verified, milestone done.
**Demo:** `pytest --collect-only` shows zero collection errors; `pytest -x --tb=short` exits 0; AST scan on `tests/` shows zero imports from deleted Celery modules.

## Must-Haves

- 7 dead Celery test files deleted (test infrastructure for deleted modules)
- 29 test files fixed — import paths updated from deleted Celery modules to `*_taskiq.py` / `helpers/` equivalents
- `.run()` calls converted to async invocation (`await fn()` or direct helper call)
- `celery.exceptions.MaxRetriesExceededError` replaced (exception propagation pattern)
- `.apply_async` mocks converted to `.kiq` or service-level mocks
- Mock patch targets updated from `app.tasks.messaging.*` to `app.tasks.messaging_taskiq.*`
- `schedule_celery_task` / `cancel_celery_task` test references updated to `schedule_task` / `cancel_task`
- `pytest --collect-only` — zero collection errors
- `pytest -x --tb=short` — exit code 0
- AST zero-import scan on `tests/` — zero imports from deleted modules or `from celery`

## Proof Level

- This slice proves: final-assembly
- Real runtime required: no (unit/integration tests with mocks — no live Dragonfly/WuzAPI needed)
- Human/UAT required: no

## Verification

- `cd backend-hormonia && python3 -m pytest --collect-only 2>&1 | grep -c "ERROR" | xargs test 0 -eq` — zero collection errors
- `cd backend-hormonia && python3 -m pytest -x --tb=short` — exit code 0
- AST zero-import scan on `tests/`:
  ```bash
  python3 -c "
  import ast, os, sys
  DELETED = {'app.tasks.alerts', 'app.tasks.audit_cleanup', 'app.tasks.reports',
    'app.tasks.webhook_dlq', 'app.tasks.follow_up', 'app.tasks.flow_automation',
    'app.tasks.monitoring', 'app.tasks.messaging', 'app.tasks.lgpd_tasks',
    'app.tasks.saga_retry', 'app.tasks.saga_monitoring', 'app.tasks.lgpd',
    'app.tasks.flows', 'app.tasks.quiz_flow', 'app.celery_app', 'celery'}
  errs = []
  for root, _, files in os.walk('backend-hormonia/tests'):
    for f in files:
      if not f.endswith('.py'): continue
      path = os.path.join(root, f)
      try:
        tree = ast.parse(open(path).read())
      except: continue
      for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
          mod = getattr(node, 'module', '') or ''
          if any(mod == d or mod.startswith(d+'.') for d in DELETED):
            errs.append(f'{path}:{node.lineno}: {mod}')
          if isinstance(node, ast.Import):
            for alias in node.names:
              if any(alias.name == d or alias.name.startswith(d+'.') for d in DELETED):
                errs.append(f'{path}:{node.lineno}: {alias.name}')
  if errs:
    for e in errs: print(e)
    sys.exit(1)
  print(f'PASS: zero deleted-module imports in tests/')
  "
  ```
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/__init__.py').read()); print('PASS')"` — package init still parses

## Observability / Diagnostics

- Runtime signals: pytest exit code + collection error count
- Inspection surfaces: AST zero-import scan script (reusable), `pytest --collect-only` for import health
- Failure visibility: each broken file reports `ModuleNotFoundError` or `ImportError` with exact module path and line number
- Redaction constraints: none

## Integration Closure

- Upstream surfaces consumed: all 13 `*_taskiq.py` modules, `app/tasks/helpers/*.py`, `app/tasks/__init__.py` (from S05)
- New wiring introduced in this slice: none — tests are updated to match existing wiring
- What remains before the milestone is truly usable end-to-end: nothing — this is the terminal slice

## Tasks

- [x] **T01: Delete dead Celery test files** `est:10m`
  - Why: 7 test files test infrastructure that was deleted in S05 (celery_app.py, celery_metrics, queue_monitor, etc). They cannot pass and have no Taskiq equivalent. Must be removed before pytest can collect without errors.
  - Files: `backend-hormonia/tests/tasks/test_celery_app_async_helper.py`, `backend-hormonia/tests/tasks/test_celery_metrics_lifecycle.py`, `backend-hormonia/tests/tasks/test_celery_schedule_alignment.py`, `backend-hormonia/tests/tasks/test_queue_monitor.py`, `backend-hormonia/tests/tasks/test_monitoring_task_registration.py`, `backend-hormonia/tests/validation/test_celery_ai_run_sync_path.py`, `backend-hormonia/tests/integration/test_celery_async_isolation.py`
  - Do: Delete all 7 files. Verify no other test files import from them.
  - Verify: `ls` confirms files gone; `find backend-hormonia/tests -name "*celery*" -type f` returns zero results
  - Done when: 7 dead test files deleted, no dangling imports to them

- [x] **T02: Fix domain task test imports (alerts, audit, reports, webhook, follow-up, LGPD, quiz)** `est:45m`
  - Why: 8 test files in `tests/tasks/` and `tests/` import from deleted Celery modules (`app.tasks.alerts`, `app.tasks.audit_cleanup`, `app.tasks.reports`, `app.tasks.webhook_dlq`, `app.tasks.follow_up`, `app.tasks.flow_automation`, `app.tasks.lgpd.reencrypt_patients`, `app.tasks.quiz_flow.cleanup_tasks`). All imports must point to the Taskiq equivalents.
  - Files: `backend-hormonia/tests/tasks/test_alerts_tasks.py`, `backend-hormonia/tests/tasks/test_audit_cleanup_tasks.py`, `backend-hormonia/tests/tasks/test_reports_tasks.py`, `backend-hormonia/tests/tasks/test_webhook_dlq_tasks.py`, `backend-hormonia/tests/tasks/test_follow_up_tasks.py`, `backend-hormonia/tests/tasks/test_flow_automation_retry_config.py`, `backend-hormonia/tests/tasks/test_reencrypt_patients.py`, `backend-hormonia/tests/test_cleanup_expired_quiz_sessions_task.py`
  - Do: For each file: (1) update `from app.tasks.X import Y` → `from app.tasks.X_taskiq import Y` (see import map in task plan); (2) if test calls `.run()`, convert to direct helper call or `asyncio.run(task.fn(...))`; (3) if test mocks `.retry()` on bound task, remove mock — Taskiq tasks don't have .retry(); (4) update `@patch` target paths from deleted module to `*_taskiq` module; (5) if test uses `.apply_async`, mock `.kiq` instead.
  - Verify: `cd backend-hormonia && python3 -m pytest tests/tasks/test_alerts_tasks.py tests/tasks/test_audit_cleanup_tasks.py tests/tasks/test_reports_tasks.py tests/tasks/test_webhook_dlq_tasks.py tests/tasks/test_follow_up_tasks.py tests/tasks/test_flow_automation_retry_config.py tests/tasks/test_reencrypt_patients.py tests/test_cleanup_expired_quiz_sessions_task.py --collect-only 2>&1 | grep ERROR` — zero errors
  - Done when: all 8 files collect without errors; zero imports from deleted modules

- [x] **T03: Fix flow, batch, and simple service test files** `est:45m`
  - Why: 8 test files import from deleted flow subdirectories (`app.tasks.flows.batch_tasks`, `app.tasks.flows.flow_tasks`, `app.tasks.flows.monitoring`, `app.tasks.flows.monthly_tasks`) or from `app.tasks.messaging`/`app.tasks.flow_automation`. Helper functions moved to `app.tasks.helpers.flow_helpers`, task functions to `app.tasks.flows_taskiq`. `process_daily_flows_async` no longer exists — replaced by `process_daily_flows` in `flows_taskiq.py`.
  - Files: `backend-hormonia/tests/tasks/flows/test_batch_processing.py`, `backend-hormonia/tests/tasks/flows/test_flow_tasks_hardening.py`, `backend-hormonia/tests/tasks/flows/test_monitoring_health_task.py`, `backend-hormonia/tests/tasks/flows/test_monthly_tasks_async_bridge.py`, `backend-hormonia/tests/unit/tasks/test_auto_resume_flows.py`, `backend-hormonia/tests/unit/services/test_flow_pause_detection.py`, `backend-hormonia/tests/services/test_sanity_with_import.py`, `backend-hormonia/tests/services/test_patient_deletion.py`
  - Do: (1) `test_batch_processing.py`: all imports from `app.tasks.flows.batch_tasks` → `app.tasks.helpers.flow_helpers` (helper functions: `_update_scheduling`, `_get_message_template_for_day`, `_process_single_patient_flow`, `_process_single_patient_flow_by_id`); (2) `test_flow_tasks_hardening.py` + `test_flow_pause_detection.py`: `process_daily_flows_async` → `process_daily_flows` from `app.tasks.flows_taskiq`; (3) `test_monitoring_health_task.py`: `from app.tasks.flows.monitoring` → `from app.tasks.flows_taskiq`; convert `.run()` → async; (4) `test_monthly_tasks_async_bridge.py`: `from app.tasks.flows.monthly_tasks` → `from app.tasks.flows_taskiq`; (5) `test_auto_resume_flows.py`: `from app.tasks.flow_automation` → `from app.tasks.flows_taskiq`; `.run()` → async; (6) `test_sanity_with_import.py` + `test_patient_deletion.py`: `from app.tasks.messaging` → `from app.tasks.messaging_taskiq`.
  - Verify: `cd backend-hormonia && python3 -m pytest tests/tasks/flows/ tests/unit/tasks/test_auto_resume_flows.py tests/unit/services/test_flow_pause_detection.py tests/services/test_sanity_with_import.py tests/services/test_patient_deletion.py --collect-only 2>&1 | grep ERROR` — zero errors
  - Done when: all 8 files collect without errors; zero imports from deleted modules

- [x] **T04: Fix retry, exception, and Celery-deep test files** `est:1h`
  - Why: 7 test files have deep Celery dependencies: `celery.exceptions.MaxRetriesExceededError`, `from app.celery_app`, `.run()` on Celery bound tasks, `celery.result.AsyncResult`, and the deleted `celery_integration` utility module. These need the most careful adaptation.
  - Files: `backend-hormonia/tests/unit/tasks/test_followup_retry_task.py`, `backend-hormonia/tests/unit/tasks/test_send_retry_task.py`, `backend-hormonia/tests/unit/tasks/test_stuck_detection.py`, `backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py`, `backend-hormonia/tests/unit/tasks/test_messaging_dlq_wiring.py`, `backend-hormonia/tests/unit/services/test_flow_cancel.py`, `backend-hormonia/tests/unit/api/v2/test_task_registry_dragonfly_fallback.py`
  - Do: (1) Replace `from celery.exceptions import MaxRetriesExceededError` — define a local `MaxRetriesExceededError = Exception` stand-in or use the raw exception the SmartRetryMiddleware propagates; (2) `test_followup_retry_task.py`: import from `app.tasks.helpers.flow_helpers` for constants (`FOLLOWUP_RETRY_MAX`) and from `app.tasks.flows_taskiq` for task functions; remove `.apply_async` mock; (3) `test_send_retry_task.py`: same pattern — `app.tasks.helpers.flow_helpers` for `SEND_RETRY_MAX_RETRIES` and functions; (4) `test_stuck_detection.py`: remove `from app.celery_app` import, import `detect_stuck_flows` from `app.tasks.flows_taskiq`; remove beat_schedule assertions; convert `.run()` → async; (5) `test_flow_recovery_retry_e2e.py`: replace all 3 `from app.tasks.flows.*` imports, replace MaxRetriesExceededError, convert `.run()` → async; (6) `test_messaging_dlq_wiring.py`: `from app.tasks.messaging` → `from app.tasks.messaging_taskiq`; (7) `test_flow_cancel.py`: remove `celery.result.AsyncResult` patch — per D013 revoke is a logged no-op; (8) `test_task_registry_dragonfly_fallback.py`: remove `from app.api.v2.routers.tasks.utils import celery_integration` import and the test that uses it (`test_register_task_persists_metadata_to_store`); keep the two `tasks_dependencies` tests.
  - Verify: `cd backend-hormonia && python3 -m pytest tests/unit/tasks/test_followup_retry_task.py tests/unit/tasks/test_send_retry_task.py tests/unit/tasks/test_stuck_detection.py tests/integration/test_flow_recovery_retry_e2e.py tests/unit/tasks/test_messaging_dlq_wiring.py tests/unit/services/test_flow_cancel.py tests/unit/api/v2/test_task_registry_dragonfly_fallback.py --collect-only 2>&1 | grep ERROR` — zero errors
  - Done when: all 7 files collect without errors; zero imports from `celery.*` or deleted modules

- [x] **T05: Fix mock-pattern saga/integration tests + run full verification** `est:1h`
  - Why: 6 test files mock Celery dispatch patterns (`apply_async`, `app.tasks.messaging.send_scheduled_message`, `schedule_celery_task`). Plus 2 tests referencing renamed scheduler methods. After fixing, run the complete test suite and AST verification scan to close the milestone.
  - Files: `backend-hormonia/tests/integration/test_patient_onboarding_e2e.py`, `backend-hormonia/tests/performance/test_saga_transaction_duration.py`, `backend-hormonia/tests/orchestration/test_saga_orchestrator.py`, `backend-hormonia/tests/unit/orchestration/test_saga_onboarding_happy_path.py`, `backend-hormonia/tests/domain/messaging/test_scheduler_status_contract.py`, `backend-hormonia/tests/services/follow_up_system/test_message_scheduler_integration.py`
  - Do: (1) `test_patient_onboarding_e2e.py` + `test_saga_transaction_duration.py`: change `from app.tasks import messaging as messaging_tasks` → `from app.tasks import messaging_taskiq as messaging_tasks`; replace `.apply_async` monkeypatch with `.kiq` mock (returns an awaitable); (2) `test_saga_orchestrator.py`: change `patch('app.tasks.messaging.send_scheduled_message')` → `patch('app.tasks.messaging_taskiq.send_scheduled_message')`; (3) `test_saga_onboarding_happy_path.py`: same mock path fix; (4) `test_scheduler_status_contract.py`: replace all `schedule_celery_task` → `schedule_task` and `cancel_celery_task` → `cancel_task`; replace `.apply_async` mock; (5) `test_message_scheduler_integration.py`: replace all `schedule_celery_task` → `schedule_task`; (6) Run full verification: `pytest --collect-only` → zero errors; `pytest -x --tb=short` → exit 0; AST zero-import scan on tests/; verify 47+ schedule labels preserved in app/.
  - Verify: Full suite: `cd backend-hormonia && python3 -m pytest -x --tb=short` — exit code 0; AST scan on tests/ passes (zero deleted-module imports); `python3 -m pytest --collect-only 2>&1 | grep -c "ERROR"` returns 0
  - Done when: `pytest` exit 0, zero collection errors, AST scan passes on both `app/` and `tests/`, milestone verification complete

## Files Likely Touched

**Deleted (7):**
- `backend-hormonia/tests/tasks/test_celery_app_async_helper.py`
- `backend-hormonia/tests/tasks/test_celery_metrics_lifecycle.py`
- `backend-hormonia/tests/tasks/test_celery_schedule_alignment.py`
- `backend-hormonia/tests/tasks/test_queue_monitor.py`
- `backend-hormonia/tests/tasks/test_monitoring_task_registration.py`
- `backend-hormonia/tests/validation/test_celery_ai_run_sync_path.py`
- `backend-hormonia/tests/integration/test_celery_async_isolation.py`

**Modified (29):**
- `backend-hormonia/tests/tasks/test_alerts_tasks.py`
- `backend-hormonia/tests/tasks/test_audit_cleanup_tasks.py`
- `backend-hormonia/tests/tasks/test_reports_tasks.py`
- `backend-hormonia/tests/tasks/test_webhook_dlq_tasks.py`
- `backend-hormonia/tests/tasks/test_follow_up_tasks.py`
- `backend-hormonia/tests/tasks/test_flow_automation_retry_config.py`
- `backend-hormonia/tests/tasks/test_reencrypt_patients.py`
- `backend-hormonia/tests/test_cleanup_expired_quiz_sessions_task.py`
- `backend-hormonia/tests/tasks/flows/test_batch_processing.py`
- `backend-hormonia/tests/tasks/flows/test_flow_tasks_hardening.py`
- `backend-hormonia/tests/tasks/flows/test_monitoring_health_task.py`
- `backend-hormonia/tests/tasks/flows/test_monthly_tasks_async_bridge.py`
- `backend-hormonia/tests/unit/tasks/test_auto_resume_flows.py`
- `backend-hormonia/tests/unit/tasks/test_followup_retry_task.py`
- `backend-hormonia/tests/unit/tasks/test_send_retry_task.py`
- `backend-hormonia/tests/unit/tasks/test_stuck_detection.py`
- `backend-hormonia/tests/unit/tasks/test_messaging_dlq_wiring.py`
- `backend-hormonia/tests/unit/services/test_flow_pause_detection.py`
- `backend-hormonia/tests/unit/services/test_flow_cancel.py`
- `backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py`
- `backend-hormonia/tests/services/test_patient_deletion.py`
- `backend-hormonia/tests/services/test_sanity_with_import.py`
- `backend-hormonia/tests/integration/test_patient_onboarding_e2e.py`
- `backend-hormonia/tests/performance/test_saga_transaction_duration.py`
- `backend-hormonia/tests/orchestration/test_saga_orchestrator.py`
- `backend-hormonia/tests/unit/orchestration/test_saga_onboarding_happy_path.py`
- `backend-hormonia/tests/domain/messaging/test_scheduler_status_contract.py`
- `backend-hormonia/tests/services/follow_up_system/test_message_scheduler_integration.py`
- `backend-hormonia/tests/unit/api/v2/test_task_registry_dragonfly_fallback.py`
