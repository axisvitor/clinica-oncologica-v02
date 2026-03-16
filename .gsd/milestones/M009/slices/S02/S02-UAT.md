# S02: Messaging tasks migradas — UAT

**Milestone:** M009
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: This slice produces code artifacts (Taskiq task module, updated call sites) that can be verified by AST parse, grep counts, and import analysis. Full runtime proof (worker processing real messages against Dragonfly) is deferred to S06 verification slice. The code-level proof is comprehensive: 14 checks covering task count, schedule labels, dispatch pattern elimination, and Celery coexistence.

## Preconditions

- Working directory is the M009 worktree with all 4 task changes applied
- Python 3.11+ available for `ast.parse()` verification
- `backend-hormonia/` directory contains the codebase
- No runtime services needed (all checks are static analysis)

## Smoke Test

Run: `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/messaging_taskiq.py').read())"` — must succeed without error. This confirms the new 1237-line module with all 9 tasks is syntactically valid.

## Test Cases

### 1. All 9 Taskiq messaging tasks exist

1. Run: `grep -c "@broker.task" backend-hormonia/app/tasks/messaging_taskiq.py`
2. **Expected:** Output is `9`

### 2. All 7 schedule labels present

1. Run: `grep -c "schedule=" backend-hormonia/app/tasks/messaging_taskiq.py`
2. **Expected:** Output is `7`

### 3. No Celery .delay() dispatch in new module

1. Run: `grep -n "\.delay(" backend-hormonia/app/tasks/messaging_taskiq.py | grep -v "^.*#\|docstring\|\"\"\""`
2. **Expected:** No matches in actual code (only in docstring comments describing the migration)

### 4. No run_async bridge in new module

1. Run: `grep -n "run_async(" backend-hormonia/app/tasks/messaging_taskiq.py | grep -v "^.*#\|docstring\|\"\"\""`
2. **Expected:** No matches in actual code (only in docstring comments)

### 5. No sync session in main task flow

1. Run: `grep -n "get_scoped_session\|get_db_session" backend-hormonia/app/tasks/messaging_taskiq.py`
2. **Expected:** Only in `_route_to_dlq` helper, `process_whatsapp_dlq`, and `process_dlq_messages` — NOT in send_scheduled_message main flow or other tasks

### 6. AST parse all modified files

1. Run each:
   ```
   python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/messaging_taskiq.py').read())"
   python3 -c "import ast; ast.parse(open('backend-hormonia/app/taskiq_broker.py').read())"
   python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/taskiq_base.py').read())"
   python3 -c "import ast; ast.parse(open('backend-hormonia/app/api/v2/messages/retry.py').read())"
   python3 -c "import ast; ast.parse(open('backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py').read())"
   python3 -c "import ast; ast.parse(open('backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py').read())"
   ```
2. **Expected:** All 6 succeed without error

### 7. retry.py dispatches via Taskiq

1. Run: `grep "send_scheduled_message\.\(delay\|apply_async\)" backend-hormonia/app/api/v2/messages/retry.py`
2. **Expected:** No matches (Celery dispatch patterns removed)
3. Run: `grep "messaging_taskiq" backend-hormonia/app/api/v2/messages/retry.py`
4. **Expected:** Import from `app.tasks.messaging_taskiq`
5. Run: `grep "\.kiq(" backend-hormonia/app/api/v2/messages/retry.py`
6. **Expected:** At least 2 matches (send_scheduled_message.kiq and retry_failed_messages.kiq)

### 8. task_scheduler.py dispatches via Taskiq schedule_task_at

1. Run: `grep "send_scheduled_message\.\(delay\|apply_async\)" backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py`
2. **Expected:** No matches
3. Run: `grep "schedule_task_at" backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py`
4. **Expected:** At least 1 match (the schedule_task_at call)

### 9. retry_handler.py dispatches via Taskiq schedule_task_at

1. Run: `grep "send_scheduled_message\.\(delay\|apply_async\)" backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py`
2. **Expected:** No matches
3. Run: `grep "schedule_task_at" backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py`
4. **Expected:** At least 1 match

### 10. Celery messaging tasks intact

1. Run: `grep -c "@celery_app.task" backend-hormonia/app/tasks/messaging.py`
2. **Expected:** Output is `9` (all 9 Celery tasks still present and untouched)

### 11. External callers still use Celery

1. Run: `grep "from app.tasks.messaging import" backend-hormonia/app/tasks/flow_automation.py`
2. **Expected:** `from app.tasks.messaging import send_scheduled_message` (Celery module, not messaging_taskiq)
3. Run: `grep "from app.tasks.messaging import" backend-hormonia/app/tasks/flows/batch_tasks.py`
4. **Expected:** `from app.tasks.messaging import send_scheduled_message` (Celery module)
5. Run: `grep "send_scheduled_message.delay" backend-hormonia/app/tasks/flow_automation.py backend-hormonia/app/tasks/flows/batch_tasks.py`
6. **Expected:** Matches found — external callers still use Celery .delay()

### 12. ListRedisScheduleSource in broker

1. Run: `grep "dynamic_schedule_source" backend-hormonia/app/taskiq_broker.py`
2. **Expected:** At least 2 matches (definition and scheduler usage)
3. Run: `grep "ListRedisScheduleSource" backend-hormonia/app/taskiq_broker.py`
4. **Expected:** At least 1 match (import)

### 13. schedule_task_at helper in taskiq_base

1. Run: `grep "schedule_task_at" backend-hormonia/app/tasks/taskiq_base.py`
2. **Expected:** At least 2 matches (def + docstring)

### 14. No Celery imports in new module

1. Run: `grep "from celery\|import celery\|celery_app" backend-hormonia/app/tasks/messaging_taskiq.py`
2. **Expected:** No matches — the Taskiq module must not depend on Celery

## Edge Cases

### DLQ routing with sync session isolation

1. Run: `grep -A2 "get_scoped_session" backend-hormonia/app/tasks/messaging_taskiq.py | head -20`
2. **Expected:** `get_scoped_session()` appears ONLY inside `_route_to_dlq` helper, `process_whatsapp_dlq`, and `process_dlq_messages` — not in the main flow of send_scheduled_message or other async tasks. This confirms sync sessions are isolated to DLQ exception paths.

### Retry count via SmartRetryMiddleware labels

1. Run: `grep "_retries" backend-hormonia/app/tasks/messaging_taskiq.py`
2. **Expected:** `context.message.labels.get('_retries', 0)` pattern used for retry count (not `self.request.retries` which is Celery-specific)

### Pure helper imports from Celery module (no duplication)

1. Run: `grep "from app.tasks.messaging import" backend-hormonia/app/tasks/messaging_taskiq.py`
2. **Expected:** Imports of pure helpers like `_build_idempotency_key`, `_compute_next_reminder_time`, `_schedule_next_reminder` — functions reused without duplication

## Failure Signals

- Any AST parse failure → syntax error in modified file, blocks all downstream slices
- `@broker.task` count ≠ 9 → missing task migration, schedule gaps
- `schedule=` count ≠ 7 → missing periodic entries, tasks won't fire automatically
- `.delay` or `.apply_async` found in migrated call sites → dispatch going to Celery instead of Taskiq
- `@celery_app.task` count in messaging.py ≠ 9 → Celery tasks accidentally modified, breaks external callers
- `from app.tasks.messaging_taskiq` in flow_automation.py or batch_tasks.py → premature migration of S03-scope callers

## Requirements Proved By This UAT

- R079 (partial) — All 9 messaging tasks have Taskiq equivalents with correct patterns. Code-level proof complete; runtime proof deferred to S06.
- R082 (partial) — 7 messaging schedule entries migrated to Taskiq labels. 30+ remaining entries are S04 scope.
- R083 (partial) — 3 messaging-domain call sites migrated to .kiq()/schedule_task_at(). ~17 remaining call sites are S03/S04 scope.

## Not Proven By This UAT

- Runtime execution of Taskiq tasks against live Dragonfly worker (S06 scope)
- Actual message delivery via WuzAPI through Taskiq worker (S06 scope)
- SmartRetryMiddleware retry behavior under real failure conditions
- ListRedisScheduleSource firing scheduled tasks at correct time via Dragonfly
- Taskiq scheduler correctly dispatching the 7 periodic tasks

## Notes for Tester

- All checks are static analysis (grep, AST parse) — no running services needed.
- The `.delay` grep may match inside docstring comments explaining the migration. Filter for actual code lines only.
- `get_scoped_session` in messaging_taskiq.py is intentional and correct — it's isolated to DLQ helpers that need sync sessions for sync-only services.
- messaging_taskiq.py is 1237 lines — larger than estimated but all content is necessary.
- During S02-S04 coexistence, both messaging.py (Celery) and messaging_taskiq.py (Taskiq) export tasks with the same names. The import path determines which queue receives the task.
