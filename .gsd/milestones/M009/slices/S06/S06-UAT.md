# S06: Verificação integrada ponta-a-ponta — UAT

**Milestone:** M009
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S06 is a test-suite migration slice — no new runtime behavior. All verification is static analysis (AST scans, collection health, grep audits) against the codebase. No live Dragonfly/WuzAPI/worker needed.

## Preconditions

- Working directory: `backend-hormonia/`
- Python 3.12+ with project virtualenv activated
- Environment variables set: `DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db"` and `QUIZ_TOKEN_SECRET="test-secret-key-for-testing"`
- No live database connection needed (tests use mocks; we're verifying collection, not execution)

## Smoke Test

```bash
cd backend-hormonia && DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db" QUIZ_TOKEN_SECRET="test-secret" python3 -m pytest --collect-only 2>&1 | tail -5
```
**Expected:** Line shows `4796 tests collected` (±10) with ≤3 errors, none mentioning `celery`, `app.tasks.messaging`, `app.tasks.flows`, or any deleted module.

## Test Cases

### 1. Zero deleted-module imports in tests/ (AST scan)

1. Run the AST zero-import scan:
   ```bash
   cd backend-hormonia && python3 -c "
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
2. **Expected:** Output `PASS: zero deleted-module imports in tests/`, exit code 0.

### 2. Zero celery-named test files

1. Run: `find tests -name "*celery*" -type f`
2. **Expected:** Empty output — no files found.

### 3. Zero Celery dispatch patterns in tests

1. Run: `grep -rn 'apply_async\|schedule_celery_task\|cancel_celery_task' tests/ --include='*.py'`
2. **Expected:** Empty output — no matches.

### 4. Test collection health (pytest --collect-only)

1. Run:
   ```bash
   cd backend-hormonia && DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db" QUIZ_TOKEN_SECRET="test-secret" python3 -m pytest --collect-only 2>&1 | grep "ERROR\|collected"
   ```
2. **Expected:** Errors ≤ 3. None of the errors mention celery, app.tasks.messaging (without _taskiq), app.tasks.flows (without _taskiq), app.celery_app, or any deleted module. Pre-existing errors are:
   - `test_session_validation.py` — SECURITY_CSRF_SECRET env
   - `test_message_extractor.py` — tombstoned module
   - `test_async_helpers_loop_lifecycle.py` — deleted async_helpers

### 5. app/tasks/__init__.py parses clean

1. Run: `python3 -c "import ast; ast.parse(open('app/tasks/__init__.py').read()); print('PASS')"`
2. **Expected:** `PASS`

### 6. Domain task test files collect individually (T02 scope)

1. Run:
   ```bash
   DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db" QUIZ_TOKEN_SECRET="test-secret" python3 -m pytest \
     tests/tasks/test_alerts_tasks.py \
     tests/tasks/test_audit_cleanup_tasks.py \
     tests/tasks/test_reports_tasks.py \
     tests/tasks/test_webhook_dlq_tasks.py \
     tests/tasks/test_follow_up_tasks.py \
     tests/tasks/test_flow_automation_retry_config.py \
     tests/test_cleanup_expired_quiz_sessions_task.py \
     --collect-only 2>&1 | grep "ERROR\|collected"
   ```
2. **Expected:** `33 tests collected` (approximately), 0 errors.

### 7. Flow/batch test files collect individually (T03 scope)

1. Run:
   ```bash
   DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db" QUIZ_TOKEN_SECRET="test-secret" python3 -m pytest \
     tests/tasks/flows/ \
     tests/unit/tasks/test_auto_resume_flows.py \
     tests/unit/services/test_flow_pause_detection.py \
     tests/services/test_sanity_with_import.py \
     tests/services/test_patient_deletion.py \
     --collect-only 2>&1 | grep "ERROR\|collected"
   ```
2. **Expected:** `32 tests collected` (approximately), 0 errors.

### 8. Retry/exception test files collect individually (T04 scope)

1. Run:
   ```bash
   DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db" QUIZ_TOKEN_SECRET="test-secret" python3 -m pytest \
     tests/unit/tasks/test_followup_retry_task.py \
     tests/unit/tasks/test_send_retry_task.py \
     tests/unit/tasks/test_stuck_detection.py \
     tests/integration/test_flow_recovery_retry_e2e.py \
     tests/unit/tasks/test_messaging_dlq_wiring.py \
     tests/unit/services/test_flow_cancel.py \
     tests/unit/api/v2/test_task_registry_dragonfly_fallback.py \
     --collect-only 2>&1 | grep "ERROR\|collected"
   ```
2. **Expected:** `36 tests collected` (approximately), 0 errors.

### 9. Saga/integration test files collect individually (T05 scope)

1. Run:
   ```bash
   DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db" QUIZ_TOKEN_SECRET="test-secret" python3 -m pytest \
     tests/integration/test_patient_onboarding_e2e.py \
     tests/performance/test_saga_transaction_duration.py \
     tests/orchestration/test_saga_orchestrator.py \
     tests/unit/orchestration/test_saga_onboarding_happy_path.py \
     tests/domain/messaging/test_scheduler_status_contract.py \
     tests/services/follow_up_system/test_message_scheduler_integration.py \
     --collect-only 2>&1 | grep "ERROR\|collected"
   ```
2. **Expected:** `34 tests collected` (approximately), 0 errors.

### 10. Taskiq task module imports work

1. Run:
   ```bash
   DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db" QUIZ_TOKEN_SECRET="test-secret" python3 -c "
   modules = [
     'app.tasks.messaging_taskiq', 'app.tasks.flows_taskiq', 'app.tasks.alerts_taskiq',
     'app.tasks.audit_taskiq', 'app.tasks.reports_taskiq', 'app.tasks.webhook_dlq_taskiq',
     'app.tasks.follow_up_taskiq', 'app.tasks.monitoring_taskiq', 'app.tasks.quiz_flow_taskiq',
     'app.tasks.quiz_link_taskiq', 'app.tasks.lgpd_taskiq', 'app.tasks.saga_monitoring_taskiq',
     'app.tasks.saga_retry_taskiq'
   ]
   import importlib
   for m in modules:
     importlib.import_module(m)
     print(f'  OK: {m}')
   print(f'PASS: all {len(modules)} Taskiq modules import cleanly')
   "
   ```
2. **Expected:** All 13 modules print OK, final line `PASS: all 13 Taskiq modules import cleanly`.

## Edge Cases

### Pre-existing errors don't increase

1. Run `pytest --collect-only 2>&1 | grep -c ERROR`
2. **Expected:** Exactly 3 (or fewer). If more than 3, investigate — a new regression may have been introduced.

### No `from celery` in any Python file under app/

1. Run: `grep -rn 'from celery\|import celery' app/ --include='*.py' | grep -v '#'`
2. **Expected:** Empty output (no active Celery imports in production code).

### Renamed file still works

1. Run: `python3 -m pytest tests/integration/test_agent_sync_bridge.py --collect-only 2>&1 | grep "collected\|ERROR"`
2. **Expected:** Tests collected (≥1), 0 errors. Confirms rename from test_celery_agent_bridge.py preserved functionality.

## Failure Signals

- Any `ModuleNotFoundError` or `ImportError` mentioning `celery`, `app.tasks.messaging`, `app.tasks.flows`, `app.tasks.alerts`, `app.tasks.audit_cleanup`, `app.tasks.reports`, `app.tasks.webhook_dlq`, `app.tasks.follow_up`, `app.tasks.flow_automation`, `app.tasks.lgpd`, `app.tasks.quiz_flow`, `app.celery_app`
- AST scan exit code 1 (prints file:line:module for each violation)
- `find tests -name "*celery*"` returning any file
- `grep apply_async tests/` returning any match
- Collection error count > 3

## Requirements Proved By This UAT

- R077 — Taskiq broker replaces celery_app.py (test imports prove no celery_app dependency)
- R078 — Base task abstraction with SmartRetryMiddleware (retry test pattern proves middleware integration)
- R079 — Messaging tasks via Taskiq (messaging test files use messaging_taskiq exclusively)
- R080 — Flow tasks via Taskiq (flow test files use flows_taskiq exclusively)
- R081 — Quiz/alert/follow-up/monitoring via Taskiq (all test files use *_taskiq imports)
- R082 — Schedule parity (72 @broker.task decorators, 47 schedule labels)
- R083 — Zero .delay()/.apply_async() call sites (grep proves zero in tests)
- R084 — Bridge code removed (zero imports from deleted bridge modules)
- R085 — Celery dependencies removed (zero celery imports anywhere)
- R086 — M008 pipeline via Taskiq (pipeline test files use Taskiq-only imports)

## Not Proven By This UAT

- Live runtime task execution against real Dragonfly (tests use mocks)
- Live WuzAPI message delivery via Taskiq worker (proven by S02 runtime proof, not this UAT)
- Actual periodic schedule firing at correct UTC times (proven by S04 parity script)
- `pytest -x --tb=short` exit 0 — pre-existing failures unrelated to M009 prevent clean exit

## Notes for Tester

- All tests run with `DATABASE_URL` and `QUIZ_TOKEN_SECRET` env vars — they don't connect to a real database, but the import chain validates these settings via Pydantic.
- The 3 pre-existing collection errors are known and documented. They are NOT regressions from M009.
- If running `pytest` with execution (not just `--collect-only`), some tests will fail due to pre-existing issues (SagaOrchestrator constructor, TemplateLoaderService import, asyncpg MissingGreenlet). These all pre-date M009.
- The authoritative verification for this slice is **collection health + AST scan**, not full test execution.
