---
estimated_steps: 8
estimated_files: 6
---

# T05: Fix mock-pattern saga/integration tests + run full verification

**Slice:** S06 — Verificação integrada ponta-a-ponta
**Milestone:** M009

## Description

Fix 6 test files that mock Celery dispatch patterns (`.apply_async`, `app.tasks.messaging.send_scheduled_message`, `schedule_celery_task`). Then run the complete test suite and AST verification scan to close the milestone.

## Steps

1. **`test_patient_onboarding_e2e.py`** (165 lines):
   - `from app.tasks import messaging as messaging_tasks` → `from app.tasks import messaging_taskiq as messaging_tasks`
   - The test monkeypatches `messaging_tasks.send_scheduled_message.apply_async` — replace with monkeypatch on `.kiq` (which returns an awaitable). Create a mock that returns an awaitable: `AsyncMock(return_value=SimpleNamespace(task_id="test-id"))`

2. **`test_saga_transaction_duration.py`** (190 lines):
   - Same pattern as onboarding: `from app.tasks import messaging as messaging_tasks` → `from app.tasks import messaging_taskiq as messaging_tasks`
   - 4 tests monkeypatch `.apply_async` → change to `.kiq`
   - `_slow_apply_async` → `_slow_kiq` (or equivalent async mock)

3. **`test_saga_orchestrator.py`** (614 lines):
   - `patch('app.tasks.messaging.send_scheduled_message')` → `patch('app.tasks.messaging_taskiq.send_scheduled_message')`
   - Search the entire file for all patch targets referencing `app.tasks.messaging` → `app.tasks.messaging_taskiq`

4. **`test_saga_onboarding_happy_path.py`** (186 lines):
   - `patch('app.tasks.messaging.send_scheduled_message')` (line 78) → `patch('app.tasks.messaging_taskiq.send_scheduled_message')`

5. **`test_scheduler_status_contract.py`** (261 lines):
   - Replace all `schedule_celery_task` → `schedule_task` (lines 28, 51, 79, 145)
   - Replace all `cancel_celery_task` → `cancel_task` (lines 50, 169)
   - Replace `.apply_async` mock (line 221) → `.kiq` mock
   - These reference `scheduler.task_scheduler.schedule_celery_task` — the actual TaskScheduler method is now `schedule_task` (verified: `task_scheduler.py` line 23)

6. **`test_message_scheduler_integration.py`** (219 lines):
   - Replace all `schedule_celery_task` → `schedule_task` (lines 99, 121, 141, 162, 180, 198)
   - These reference `message_scheduler.task_scheduler.schedule_celery_task` → now `schedule_task`

7. **Run full verification suite**:
   ```bash
   cd backend-hormonia

   # Check zero collection errors
   python3 -m pytest --collect-only 2>&1 | grep -c "ERROR"
   # Must be 0

   # Run full test suite
   python3 -m pytest -x --tb=short
   # Must exit 0

   # AST zero-import scan on tests/
   python3 -c "
   import ast, os, sys
   DELETED = {'app.tasks.alerts', 'app.tasks.audit_cleanup', 'app.tasks.reports',
     'app.tasks.webhook_dlq', 'app.tasks.follow_up', 'app.tasks.flow_automation',
     'app.tasks.monitoring', 'app.tasks.messaging', 'app.tasks.lgpd_tasks',
     'app.tasks.saga_retry', 'app.tasks.saga_monitoring', 'app.tasks.lgpd',
     'app.tasks.flows', 'app.tasks.quiz_flow', 'app.celery_app', 'celery'}
   errs = []
   for root, _, files in os.walk('tests'):
     for f in files:
       if not f.endswith('.py'): continue
       path = os.path.join(root, f)
       try: tree = ast.parse(open(path).read())
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

8. **Verify schedule labels preserved**:
   ```bash
   python3 -c "
   import re, os
   count = 0
   for root, _, files in os.walk('app/tasks'):
     for f in files:
       if f.endswith('_taskiq.py'):
         content = open(os.path.join(root, f)).read()
         count += len(re.findall(r'schedule_labels=', content))
   print(f'Schedule labels: {count}')
   assert count >= 47, f'Expected 47+ labels, got {count}'
   print('PASS')
   "
   ```

## Must-Haves

- [ ] Zero mock references to `.apply_async` in test files (replaced with `.kiq`)
- [ ] Zero references to `schedule_celery_task` / `cancel_celery_task` in test files
- [ ] Zero mock patch targets referencing `app.tasks.messaging.` (without `_taskiq`)
- [ ] `pytest --collect-only` zero errors
- [ ] `pytest -x --tb=short` exit 0
- [ ] AST scan on tests/ passes

## Verification

- `cd backend-hormonia && python3 -m pytest --collect-only 2>&1 | grep -c "ERROR"` → 0
- `cd backend-hormonia && python3 -m pytest -x --tb=short` → exit 0
- AST scan → PASS
- Schedule labels ≥ 47

## Inputs

- T01-T04 complete (all import-broken and Celery-deep test files fixed)
- `app/domain/messaging/scheduling/message_scheduler/task_scheduler.py` uses `schedule_task` (line 23) and `cancel_task` (line 106) — no more `celery` in method names
- D013: revoke is logged no-op
- D015: function names containing "celery" renamed to "backend"

## Expected Output

- 6 test files with corrected mock patterns
- Full test suite passing (exit 0)
- AST verification scan passing on both `app/` and `tests/`
- Milestone M009 verification complete — all success criteria met
