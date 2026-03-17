---
estimated_steps: 8
estimated_files: 8
---

# T02: Fix domain task test imports (alerts, audit, reports, webhook, follow-up, LGPD, quiz)

**Slice:** S06 — Verificação integrada ponta-a-ponta
**Milestone:** M009

## Description

Fix 8 test files that import from deleted Celery task modules. Each needs import paths updated to `*_taskiq.py` or `helpers/` equivalents, `.run()` calls converted to async, `.retry()` mocks removed, and `@patch` targets updated.

## Import Map

| Deleted Module | Taskiq Equivalent |
|---|---|
| `app.tasks.alerts` | `app.tasks.alerts_taskiq` |
| `app.tasks.audit_cleanup` | `app.tasks.audit_taskiq` |
| `app.tasks.reports` | `app.tasks.reports_taskiq` (helpers: `app.tasks.helpers.reports_helpers`) |
| `app.tasks.webhook_dlq` | `app.tasks.webhook_dlq_taskiq` |
| `app.tasks.follow_up` | `app.tasks.follow_up_taskiq` |
| `app.tasks.flow_automation` | `app.tasks.flows_taskiq` |
| `app.tasks.lgpd.reencrypt_patients` | `app.tasks.lgpd_taskiq` |
| `app.tasks.quiz_flow.cleanup_tasks` | `app.tasks.quiz_flow_taskiq` |

## Steps

1. **`test_alerts_tasks.py`** (116 lines): Replace all `from app.tasks.alerts import X` → `from app.tasks.alerts_taskiq import X` (lazy imports inside test bodies). If tests mock `.retry()` on bound task, remove — Taskiq tasks don't have `.retry()`. Update `@patch('app.tasks.alerts.X')` → `@patch('app.tasks.alerts_taskiq.X')`. If tests call `.run()`, convert to async.

2. **`test_audit_cleanup_tasks.py`** (118 lines): Replace `from app.tasks.audit_cleanup import X` → `from app.tasks.audit_taskiq import X`. Check function name changes: `cleanup_expired_audit_logs` → `cleanup_expired_logs`; `generate_daily_audit_report` → `generate_daily_report`. Update `@patch` targets.

3. **`test_reports_tasks.py`** (106 lines): `_get_system_actor_uuid` → `from app.tasks.helpers.reports_helpers`. Task functions → `from app.tasks.reports_taskiq`. Update `@patch` targets. If `.apply_async` mocked, convert to `.kiq`.

4. **`test_webhook_dlq_tasks.py`** (191 lines): Replace `from app.tasks.webhook_dlq import X` → `from app.tasks.webhook_dlq_taskiq import X`. Update `@patch` targets.

5. **`test_follow_up_tasks.py`** (129 lines): Replace `from app.tasks.follow_up import X` → `from app.tasks.follow_up_taskiq import X`. Update `@patch` targets.

6. **`test_flow_automation_retry_config.py`** (55 lines): Replace `from app.tasks.flow_automation import X` → `from app.tasks.flows_taskiq import X`. Check if `RETRY_DELAYS`, `MAX_RETRY_DELAY`, `calculate_retry_delay` are in `flows_taskiq.py` or `helpers/flow_helpers.py` or `app.config.settings.tasks`.

7. **`test_reencrypt_patients.py`** (401 lines): Replace all 6 lazy `from app.tasks.lgpd.reencrypt_patients import batch_reencrypt_patients` → `from app.tasks.lgpd_taskiq import batch_reencrypt_patients`. Update `@patch('app.tasks.lgpd.reencrypt_patients.*')` → `@patch('app.tasks.lgpd_taskiq.*')`. Helper functions → `app.tasks.helpers.lgpd_helpers`.

8. **`test_cleanup_expired_quiz_sessions_task.py`** (529 lines): Replace `from app.tasks.quiz_flow.cleanup_tasks import X` → `from app.tasks.quiz_flow_taskiq import X`. Helpers → `app.tasks.helpers.quiz_flow_helpers`. Update `@patch` targets.

**For each file**: verify syntax with `python3 -c "import ast; ast.parse(open('FILE').read())"` and collection with `pytest FILE --collect-only`.

## Must-Haves

- [ ] Zero imports from deleted modules in these 8 files
- [ ] All 8 files parse without syntax errors
- [ ] All 8 files collect without import errors

## Verification

- `cd backend-hormonia && python3 -m pytest tests/tasks/test_alerts_tasks.py tests/tasks/test_audit_cleanup_tasks.py tests/tasks/test_reports_tasks.py tests/tasks/test_webhook_dlq_tasks.py tests/tasks/test_follow_up_tasks.py tests/tasks/test_flow_automation_retry_config.py tests/tasks/test_reencrypt_patients.py tests/test_cleanup_expired_quiz_sessions_task.py --collect-only 2>&1 | grep ERROR` — empty

## Inputs

- T01 complete (dead files deleted)
- S05 `*_taskiq.py` modules and `helpers/*.py` modules contain all task functions and helpers
- Taskiq tasks are `async def` — `.run()` must become async invocation

## Expected Output

- 8 test files with corrected imports, all collecting successfully
