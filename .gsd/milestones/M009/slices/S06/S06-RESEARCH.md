# S06: Verificação integrada ponta-a-ponta — Research

**Date:** 2026-03-16
**Depth:** Targeted

## Summary

S06 is the terminal verification slice for M009. S05 removed all Celery code and confirmed zero Celery imports via AST scan. What remains is: (1) fixing 35 test files that still import from deleted Celery modules, deleted subpackages, or mock deleted Celery patterns, and (2) running the full test suite to confirm parity.

The codebase split is clean: the `app/` directory has zero Celery imports (AST-verified by S05). But the `tests/` directory was not touched — 26 test files import from deleted module paths (`app.tasks.alerts`, `app.tasks.flows.batch_tasks`, `app.celery_app`, etc.), 10 tests call `.run()` (Celery sync dispatch) on functions that are now `async def`, and 7 tests mock Celery-specific patterns (`.apply_async`, `celery.result.AsyncResult`). All 35 files must be fixed or deleted before `pytest` can pass.

The saga orchestrator and pipeline code (the M008 pipeline) do NOT use Celery dispatch — `steps.py` creates messages in PENDING status via `MessageService.schedule_message()` and relies on the periodic `process_scheduled_messages` task to pick them up. This means the M008 pipeline verification is primarily about import health + existing test pass, not about wiring new dispatch calls.

## Recommendation

**Three-phase approach: delete dead tests → fix imports/mocks → run full suite.**

1. **Delete 7 dead test files** — tests for `celery_app.py`, `celery_metrics`, `queue_monitor`, `monitoring.py` task registration, `celery_schedule_alignment`, `celery_ai_run_sync_path`, and `celery_async_isolation`. These test deleted infrastructure with no Taskiq equivalent.

2. **Fix 21 import-broken test files** — update `from app.tasks.alerts import X` → `from app.tasks.alerts_taskiq import X` (and equivalent for all 13 deleted modules + 3 deleted subpackages). Tests that call `.run()` must become `async def test_...` with `await task.fn(...)` or use `asyncio.run()`. Tests that use `celery.exceptions.MaxRetriesExceededError` need the exception replaced. Tests that mock `.retry()` on the task need adaptation (SmartRetryMiddleware handles retries externally — no `.retry()` method on Taskiq tasks).

3. **Fix 7 mock-pattern test files** — saga/onboarding tests that mock `app.tasks.messaging.send_scheduled_message` need the mock path updated to `app.tasks.messaging_taskiq.send_scheduled_message`. Tests patching `.apply_async` need to patch `.kiq` instead (or mock at the service level). `test_flow_cancel.py` patching `celery.result.AsyncResult` needs the revoke mock removed (D013: revoke is now a no-op).

4. **Run `pytest`** — all tests pass = slice done.

## Implementation Landscape

### Key Files

**Dead tests (delete):**
- `tests/tasks/test_celery_app_async_helper.py` (34 lines) — tests deleted `run_async_in_celery`
- `tests/tasks/test_celery_metrics_lifecycle.py` (111 lines) — tests deleted `celery_metrics` module
- `tests/tasks/test_celery_schedule_alignment.py` (114 lines) — tests deleted `celery_app.py` beat_schedule
- `tests/tasks/test_queue_monitor.py` (56 lines) — tests deleted `QueueMonitor`
- `tests/tasks/test_monitoring_task_registration.py` (112 lines) — tests deleted `monitoring.py` @task decorators
- `tests/validation/test_celery_ai_run_sync_path.py` (103 lines) — tests deleted `batch_tasks.py`, `flow_automation.py`
- `tests/integration/test_celery_async_isolation.py` (60 lines) — tests Celery async DB isolation

**Import-broken tests (fix imports, adapt async):**
- `tests/tasks/test_alerts_tasks.py` (116 lines) — `from app.tasks.alerts` → `from app.tasks.alerts_taskiq`; `.run()` → `await fn()`. Also uses `.retry()` mock pattern (Celery bound task) that doesn't exist on Taskiq tasks.
- `tests/tasks/test_audit_cleanup_tasks.py` (118 lines) — `from app.tasks.audit_cleanup` → `from app.tasks.audit_taskiq`
- `tests/tasks/test_reports_tasks.py` (106 lines) — `from app.tasks.reports` → `from app.tasks.reports_taskiq`; also mocks `.apply_async`
- `tests/tasks/test_webhook_dlq_tasks.py` (191 lines) — `from app.tasks.webhook_dlq` → `from app.tasks.webhook_dlq_taskiq`
- `tests/tasks/test_follow_up_tasks.py` (129 lines) — `from app.tasks.follow_up` → `from app.tasks.follow_up_taskiq`
- `tests/tasks/test_flow_automation_retry_config.py` (55 lines) — `from app.tasks.flow_automation` → `from app.tasks.flows_taskiq`
- `tests/tasks/test_reencrypt_patients.py` (401 lines) — `from app.tasks.lgpd.reencrypt_patients` → `from app.tasks.lgpd_taskiq` (batch_reencrypt_patients)
- `tests/test_cleanup_expired_quiz_sessions_task.py` (?) — `from app.tasks.quiz_flow.cleanup_tasks` → `from app.tasks.quiz_flow_taskiq`
- `tests/tasks/flows/test_batch_processing.py` (424 lines) — `from app.tasks.flows.batch_tasks` → `from app.tasks.helpers.flow_helpers`
- `tests/tasks/flows/test_flow_tasks_hardening.py` (97 lines) — `from app.tasks.flows.flow_tasks` → `from app.tasks.flows_taskiq`
- `tests/tasks/flows/test_monitoring_health_task.py` (68 lines) — `from app.tasks.flows.monitoring` → `from app.tasks.flows_taskiq`
- `tests/tasks/flows/test_monthly_tasks_async_bridge.py` (89 lines) — `from app.tasks.flows.monthly_tasks` → `from app.tasks.flows_taskiq`
- `tests/unit/tasks/test_auto_resume_flows.py` (90 lines) — `from app.tasks.flow_automation` → `from app.tasks.flows_taskiq`
- `tests/unit/tasks/test_followup_retry_task.py` (190 lines) — `from app.tasks.flows.followup_retry` + `celery.exceptions.MaxRetriesExceededError`
- `tests/unit/tasks/test_send_retry_task.py` (299 lines) — `from app.tasks.flows.send_retry` + `celery.exceptions.MaxRetriesExceededError`
- `tests/unit/tasks/test_stuck_detection.py` (147 lines) — `from app.tasks.flows.stuck_detection` + `from app.celery_app`; tests beat_schedule entry
- `tests/unit/tasks/test_messaging_dlq_wiring.py` (175 lines) — `from app.tasks.messaging` → `from app.tasks.messaging_taskiq`
- `tests/unit/services/test_flow_pause_detection.py` (125 lines) — `from app.tasks.flows.flow_tasks` → `from app.tasks.flows_taskiq`
- `tests/integration/test_flow_recovery_retry_e2e.py` (?) — `from app.tasks.flows.*` + `celery.exceptions`
- `tests/services/test_patient_deletion.py` — `from app.tasks.messaging` → `from app.tasks.messaging_taskiq`
- `tests/services/test_sanity_with_import.py` — `from app.tasks.messaging` → `from app.tasks.messaging_taskiq`

**Mock-pattern tests (fix mock targets/patterns):**
- `tests/integration/test_patient_onboarding_e2e.py` — monkeypatches `.apply_async` on `messaging_tasks.send_scheduled_message`; needs to mock `.kiq` or mock at `MessageService.schedule_message` level
- `tests/performance/test_saga_transaction_duration.py` — same `.apply_async` mock pattern (4 tests)
- `tests/orchestration/test_saga_orchestrator.py` — patches `app.tasks.messaging.send_scheduled_message` → needs `app.tasks.messaging_taskiq.send_scheduled_message`
- `tests/unit/orchestration/test_saga_onboarding_happy_path.py` — patches `app.tasks.messaging.send_scheduled_message`
- `tests/domain/messaging/test_scheduler_status_contract.py` — uses `schedule_celery_task` / `cancel_celery_task` mock names
- `tests/unit/services/test_flow_cancel.py` — patches `celery.result.AsyncResult` for revoke test
- `tests/unit/api/v2/test_task_registry_dragonfly_fallback.py` — imports `celery_integration` from tasks utils (module may have been renamed/cleaned)

### Build Order

**T01: Delete dead Celery test files** — 7 files, ~590 lines. No dependencies. Removes guaranteed-broken test files.

**T02: Fix import-broken test files** — 21 files, ~2,500+ lines. This is the bulk of work. Each file needs:
- Import path update (mechanical)
- `.run()` → async invocation pattern (Celery `.run()` was sync; Taskiq tasks are `async def`)
- `.retry()` mock removal (SmartRetryMiddleware handles retries, no `.retry()` on the task)
- `celery.exceptions.MaxRetriesExceededError` replacement
- `get_scoped_session` vs `get_db_session` patch target alignment (Taskiq modules may use different session helpers)
- Mock patch target paths updated from `app.tasks.alerts.X` to `app.tasks.alerts_taskiq.X`

**T03: Fix mock-pattern tests** — 7 files. Saga tests need the mock path for `send_scheduled_message` updated. Performance tests need `.apply_async` → `.kiq` mock update. Cancel test needs revoke logic removed. Registry test needs `celery_integration` reference updated.

**T04: Run full test suite + verification** — `pytest -x` to run all tests. Verify 0 failures. Run the AST zero-import scan on `tests/` to confirm no residual Celery imports. Run health endpoint check script.

### Verification Approach

1. **AST zero-import scan on tests/**: extend S05's AST scan to cover `tests/` — verify zero imports from deleted modules and zero `from celery` / `import celery` imports
2. **`pytest` passes**: `pytest -x --tb=short` returns exit code 0
3. **No collection errors**: `pytest --collect-only 2>&1 | grep ERROR` returns empty — no import failures during collection
4. **Schedule label count**: verify 47+ schedule labels still present (unchanged from S05)
5. **Package init parses**: `python3 -c "import ast; ast.parse(open('app/tasks/__init__.py').read())"` still passes

## Constraints

- Tests calling `.run()` on Celery tasks were invoking the underlying sync function directly. Taskiq tasks are `async def` — calling `.fn()` on a Taskiq task returns the bare coroutine, but there's no `.run()` method. Tests must use `await task.fn(args)` inside `async def test_*` with `pytest-asyncio`, or restructure to test the helper function directly.
- Some tests mock `.retry()` on the Celery bound task (e.g., `patch.object(process_alert_escalation, "retry", ...)`). Taskiq tasks don't have a `.retry()` method — SmartRetryMiddleware intercepts exceptions automatically. These tests need to either: (a) verify the exception is raised (middleware will catch it), or (b) test the helper function without the retry concern.
- `celery.exceptions.MaxRetriesExceededError` used in 3 test files (followup_retry, send_retry, flow_recovery_retry_e2e). Since Taskiq uses SmartRetryMiddleware, the equivalent signal is that the middleware stops retrying and lets the exception propagate. Tests should verify the original exception is raised.
- `tests/tasks/flows/test_batch_processing.py` imports helper functions (`_update_scheduling`, `_get_message_template_for_day`, `_process_single_patient_flow`) from `app.tasks.flows.batch_tasks` which was deleted. These helpers were moved to `app/tasks/helpers/flow_helpers.py` by S05. Import paths must point there.
- Constants like `SEND_RETRY_MAX_RETRIES`, `FOLLOWUP_RETRY_MAX` that lived in deleted modules may now live in the `*_taskiq.py` modules or helpers. Must locate them before updating imports.

## Common Pitfalls

- **Patching wrong module path** — `from app.tasks.alerts import check_patient_alerts` imports from `__init__.py` re-export. But patching `app.tasks.alerts.get_db_session` targets the now-deleted module. The patch target must be `app.tasks.alerts_taskiq.get_db_session` (where the function is looked up at runtime).
- **`.run()` silently returns a coroutine** — If you change the import but don't change `.run()` to `await`, the test passes but doesn't actually execute the async body. Must use `pytest.mark.asyncio` + `await task.fn(args)` or call `asyncio.run(task.fn(args))`.
- **Helper functions vs task functions** — `_process_single_patient_flow` in `test_batch_processing.py` is a helper (not a task). It was moved to `app/tasks/helpers/flow_helpers.py`, not to a `*_taskiq.py` module. Don't confuse the import target.
- **`generate_quiz_report` name collision** — S05 noted this: exists in both `flows_taskiq` and `quiz_flow_taskiq`. `__init__.py` re-exports the last import (quiz version). If any test needs the flows version, use explicit module import.

## Open Risks

- Some tests may test behavior that genuinely changed (e.g., retry mechanics). If Celery's `self.retry(countdown=X)` was tested and Taskiq's SmartRetryMiddleware handles this differently (labels-based, automatic), the test assertion may need rethinking — not just import path updates.
- The `test_patient_onboarding_e2e.py` and `test_saga_transaction_duration.py` tests mock at the task dispatch level. The saga orchestrator no longer dispatches tasks — it calls `MessageService.schedule_message()` to create PENDING messages. These mock patterns may be testing a code path that no longer exists (the mock may not even be hit). Need to verify the mock is still meaningful.
