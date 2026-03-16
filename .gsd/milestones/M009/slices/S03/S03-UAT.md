# S03: Flow/saga tasks migradas — UAT

**Milestone:** M009
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S03 proves contract parity (code structure, task counts, schedule labels, zero bridge code) — runtime verification is explicitly deferred to S06 per the slice plan's "Real runtime required: no" declaration.

## Preconditions

- Working directory: project root or `.gsd/worktrees/M009`
- Python 3.10+ available for AST parsing
- No running services required (artifact-driven)

## Smoke Test

```bash
python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/flows_taskiq.py').read()); ast.parse(open('backend-hormonia/app/tasks/saga_retry_taskiq.py').read()); print('SMOKE OK')"
```
Expected: `SMOKE OK`

## Test Cases

### 1. Task count verification — flows_taskiq.py has exactly 14 tasks

1. Run: `grep -c "@broker.task" backend-hormonia/app/tasks/flows_taskiq.py`
2. **Expected:** `14`

### 2. Task count verification — saga_retry_taskiq.py has exactly 3 tasks

1. Run: `grep -c "@broker.task" backend-hormonia/app/tasks/saga_retry_taskiq.py`
2. **Expected:** `3`

### 3. Schedule label count — 12 total (10 + 2)

1. Run: `grep -c "schedule=" backend-hormonia/app/tasks/flows_taskiq.py`
2. **Expected:** `10`
3. Run: `grep -c "schedule=" backend-hormonia/app/tasks/saga_retry_taskiq.py`
4. **Expected:** `2`

### 4. Zero bridge code in Taskiq files (AST-verified)

1. Run:
```bash
python3 -c "
import ast
for f in ['backend-hormonia/app/tasks/flows_taskiq.py', 'backend-hormonia/app/tasks/saga_retry_taskiq.py']:
    tree = ast.parse(open(f).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ('async_to_sync','run_async','run_async_in_sync','run_async_in_thread'):
                print(f'FAIL: bridge call {node.func.id} in {f}'); exit(1)
print('PASS: zero bridge calls')
"
```
2. **Expected:** `PASS: zero bridge calls`

### 5. Zero Celery dispatch in Taskiq files (AST-verified)

1. Run:
```bash
python3 -c "
import ast
for f in ['backend-hormonia/app/tasks/flows_taskiq.py', 'backend-hormonia/app/tasks/saga_retry_taskiq.py']:
    tree = ast.parse(open(f).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ('delay','apply_async'):
            print(f'FAIL: Celery dispatch .{node.func.attr}() in {f}'); exit(1)
print('PASS: zero Celery dispatch')
"
```
2. **Expected:** `PASS: zero Celery dispatch`

### 6. Celery originals intact (unchanged task counts)

1. Run:
```bash
for f in backend-hormonia/app/tasks/flow_automation.py backend-hormonia/app/tasks/saga_retry.py backend-hormonia/app/tasks/flows/flow_tasks.py backend-hormonia/app/tasks/flows/stuck_detection.py backend-hormonia/app/tasks/flows/monitoring.py backend-hormonia/app/tasks/flows/monthly_tasks.py backend-hormonia/app/tasks/flows/cleanup_tasks.py backend-hormonia/app/tasks/flows/followup_retry.py backend-hormonia/app/tasks/flows/send_retry.py; do
  echo -n "$f: "; grep -c "@celery_app.task" "$f"
done
```
2. **Expected:** All counts match original values:
   - flow_automation.py: 5
   - saga_retry.py: 3
   - flow_tasks.py: 1
   - stuck_detection.py: 1
   - monitoring.py: 2
   - monthly_tasks.py: 2
   - cleanup_tasks.py: 1
   - followup_retry.py: 1
   - send_retry.py: 1

### 7. External call sites import from flows_taskiq

1. Run: `grep "from app.tasks.flows_taskiq import" backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py backend-hormonia/app/services/follow_up_system/execution/message.py`
2. **Expected:** Each file shows a Taskiq import:
   - response_handler.py imports `generate_quiz_report`
   - delivery.py imports `retry_failed_flow_send`
   - message.py imports `retry_failed_followup_send`

### 8. External call sites have zero Celery dispatch for flow tasks

1. Run: `grep -c "\.delay(\|\.apply_async(" backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py backend-hormonia/app/services/follow_up_system/execution/message.py`
2. **Expected:** All three files show `0`

### 9. recovery.py retains Celery dispatch (intentional coexistence)

1. Run: `grep "retry_failed_flow_send.delay" backend-hormonia/app/services/flow/recovery.py`
2. **Expected:** At least 1 match (the `.delay()` call at ~line 214)
3. Run: `grep "TODO(S05)" backend-hormonia/app/services/flow/recovery.py`
4. **Expected:** At least 1 match (the coexistence marker)

### 10. All modified files pass AST parse

1. Run:
```bash
python3 -c "
import ast
files = [
    'backend-hormonia/app/tasks/flows_taskiq.py',
    'backend-hormonia/app/tasks/saga_retry_taskiq.py',
    'backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py',
    'backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py',
    'backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py',
    'backend-hormonia/app/services/follow_up_system/execution/message.py',
    'backend-hormonia/app/services/flow/recovery.py',
]
for f in files:
    ast.parse(open(f).read())
    print(f'{f}: OK')
print('ALL PASS')
"
```
2. **Expected:** All 7 files print `OK`, final line `ALL PASS`

### 11. Task name inventory — all 17 expected tasks present

1. Run: `grep "@broker.task" backend-hormonia/app/tasks/flows_taskiq.py backend-hormonia/app/tasks/saga_retry_taskiq.py`
2. **Expected:** 17 lines showing task decorators. The following task names must be present:
   - flows_taskiq.py: process_daily_flows, check_and_start_pending_flows, send_daily_reminders, resume_paused_flows, cleanup_expired_quiz_links, send_flow_day_for_patient, process_monthly_quizzes, generate_quiz_report, detect_stuck_flows, monitor_flow_task_health, evaluate_flow_alerts, cleanup_old_flow_data, retry_failed_flow_send, retry_failed_followup_send
   - saga_retry_taskiq.py: retry_patient_onboarding_saga, scan_and_retry_failed_sagas, cleanup_old_completed_sagas

## Edge Cases

### grep false positives in docstrings

1. Run: `grep -c "async_to_sync\|run_async_in_sync\|run_async_in_thread" backend-hormonia/app/tasks/flows_taskiq.py`
2. **Expected:** Non-zero count (docstrings mention "replaced X with Y")
3. Run: AST-based check from Test Case 4
4. **Expected:** `PASS` — confirms zero actual bridge calls despite grep noise

### SmartRetryMiddleware labels on retry tasks

1. Run: `grep "retry_on_error" backend-hormonia/app/tasks/flows_taskiq.py backend-hormonia/app/tasks/saga_retry_taskiq.py`
2. **Expected:** At least 3 matches (retry_failed_flow_send, retry_failed_followup_send, retry_patient_onboarding_saga)

## Failure Signals

- Any AST parse failure → syntax error in task file
- `@broker.task` count != 14 in flows_taskiq.py or != 3 in saga_retry_taskiq.py → tasks missing or duplicated
- `schedule=` count != 12 total → periodic schedule labels missing
- AST bridge/dispatch check finds calls → bridge code or Celery dispatch leaked into Taskiq files
- External call sites still showing `.delay()` or `.apply_async()` → migration incomplete
- Celery original task counts changed → originals were modified instead of preserved

## Requirements Proved By This UAT

- R080 (partial) — Contract parity for all 17 flow/saga tasks proven via artifact checks. Runtime proof remains for S06.
- R082 (partial) — 12 of 40+ schedule labels contributed. S04 completes the schedule.
- R083 (partial) — 3 external call sites migrated. Remaining call sites deferred to S04/S05.

## Not Proven By This UAT

- Runtime execution of any Taskiq task (no worker started, no Dragonfly connection)
- End-to-end pipeline (create patient → welcome → daily flow → response → transition) — deferred to S06
- SmartRetryMiddleware actual retry behavior under failure conditions
- schedule_task_at delayed dispatch timing accuracy
- Cross-task dispatch (send_daily_reminders → send_scheduled_message) runtime delivery

## Notes for Tester

- All test cases use only `python3`, `grep`, and `bash` — no running services needed.
- The AST-based checks (Test Cases 4, 5) are the authoritative verification for zero bridge/dispatch code. Grep-based checks will show false positives from docstrings.
- The Celery original files (Test Case 6) should have identical task counts to pre-S03 state. If any count differs, Celery files were accidentally modified.
- recovery.py's retained `.delay()` (Test Case 9) is intentional — the function is sync and cannot be made async without cascading changes. S05 handles this.
