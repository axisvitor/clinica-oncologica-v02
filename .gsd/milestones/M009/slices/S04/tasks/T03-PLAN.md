---
estimated_steps: 7
estimated_files: 3
---

# T03: Migrate complex modules (quiz_link, quiz_flow, follow_up)

**Slice:** S04 — Quiz/alert/follow-up/monitoring migradas + schedule completo
**Milestone:** M009

## Description

Create 3 Taskiq parallel modules for the most complex task groups: quiz_link (6 tasks), quiz_flow (8 tasks consolidated from 4 subpackage files), and follow_up (3 tasks with 15+ bridge removals). These modules have the heaviest cross-module dispatch chains and the most bridge code to remove.

## Steps

1. **Create `quiz_link_taskiq.py`** (6 tasks, 3 periodic):
   - Read source file: `app/tasks/quiz_link_tasks.py` (693 lines, 6 tasks).
   - Import pure helpers from Celery module: `_sanitize_limit`, `_token_fingerprint`, `_sanitize_error_message`, `_sanitize_dlq_record`. Do NOT import `QuizLinkTask` base class (Celery-specific).
   - 6 tasks:
     - `check_expired_links` — periodic 1800s. Checks expired quiz links and triggers rotation.
     - `rotate_expired_token` — on-demand. Generates new token for expired link.
     - `send_quiz_reminder` — on-demand with retry. **Key translation**: Celery version uses `self.request.retries` + `self.retry(countdown=retry_delay)` with escalating delays [3600, 7200, 14400]. In Taskiq, use SmartRetryMiddleware: `retry_on_error=True, max_retries=3, delay=3600`. SmartRetryMiddleware applies exponential backoff automatically. The custom countdown pattern is unnecessary.
     - `fallback_to_whatsapp` — on-demand. Called when quiz link delivery fails.
     - `process_dead_letter_queue` — periodic 7200s. Processes quiz-specific DLQ.
     - `monitor_resilience_metrics` — periodic 3600s.
   - Distributed lock usage: `check_expired_links` uses `get_distributed_lock()` — keep this pattern, it's not Celery-specific.
   - Cross-dispatch within module: `check_expired_links` may call `rotate_expired_token.delay()` and `send_quiz_reminder.delay()` → change to `await rotate_expired_token.kiq()` and `await send_quiz_reminder.kiq()`.
   - Import `QuizLinkResilienceService`, `LinkBuilder`, `MonthlyQuizMessageIntegration` from their original locations.

2. **Create `quiz_flow_taskiq.py`** (8 tasks, 1 periodic):
   - Read 4 source files and consolidate into single module:
     - `app/tasks/quiz_flow/cleanup_tasks.py` (328 lines, 1 task) — `cleanup_expired_quiz_sessions_task`
     - `app/tasks/quiz_flow/trigger_tasks.py` (428 lines, 3 tasks) — `check_quiz_triggers_task`, `send_quiz_link_reminder_task`, `monitor_quiz_links_task`
     - `app/tasks/quiz_flow/response_tasks.py` (294 lines, 2 tasks) — `process_quiz_response_task`, `generate_quiz_report_task`
     - `app/tasks/quiz_flow/question_tasks.py` (309 lines, 2 tasks) — `send_quiz_question_task`, `send_quiz_progress_update_task`
   - Only `cleanup_expired_quiz_sessions_task` is periodic (interval 7200s). The rest are on-demand.
   - Key translations: `async_to_sync(service.method)()` → `await service.method()` for quiz services. `run_async()` bridge → direct `await`.
   - Cross-dispatch to `send_quiz_reminder` from quiz_link: import from `app.tasks.quiz_link_taskiq import send_quiz_reminder` (NOT from Celery module). Where trigger_tasks dispatches `send_quiz_link_reminder_task.apply_async(countdown=...)`, the Taskiq equivalent is `await send_quiz_reminder.kiq(...)` (SmartRetryMiddleware handles delay).
   - **trigger_service.py sync caller**: `app/domain/quizzes/integration/flow_integration/trigger_service.py` (lines 724, 732) calls `send_quiz_link_reminder_task.apply_async()` from sync code. Per D010, keep Celery `.apply_async()` in this sync caller with `TODO(S05)` marker. Do NOT modify trigger_service.py in this task.
   - Import pure helpers from subpackage files: `_sanitize_limit` from trigger_tasks, `_parse_uuid` from response_tasks/question_tasks, `_sanitize_max_age_hours` from cleanup_tasks.
   - Import `_notify_providers_of_quiz_completion` from `app.tasks.quiz_flow.helpers`.

3. **Create `follow_up_taskiq.py`** (3 tasks, 3 periodic):
   - Read source file: `app/tasks/follow_up.py` (895 lines, 3 tasks — the most complex file).
   - 3 tasks:
     - `execute_pending_follow_ups` — periodic 300s. The core follow-up processor.
     - `process_escalation_alerts` — periodic 600s. Escalation processing.
     - `cleanup_old_contexts` — cron `cron("0 6 * * *")` (was 03:00 BRT → 06:00 UTC).
   - **Bridge removal**: The Celery version has 15+ `async_to_sync()` calls for FollowUpSystemService methods and Redis store interactions. In Taskiq async tasks, call these methods with `await` directly. The FollowUpSystemService methods are likely async. Verify by checking if the service methods are `async def` — if so, `await` them; if sync, wrap with `get_scoped_session()`.
   - **Pure helpers**: Import helper functions from `app.tasks.follow_up` — there are ~20 helpers (validation, sanitization, formatting). Use these imports to avoid duplication.
   - **Cross-dispatch**: `follow_up.py` calls `process_alert_notification.delay(...)` from `app.tasks.alerts`. In `follow_up_taskiq.py`, import `process_alert_notification` from `app.tasks.alerts_taskiq` (T02 output) and use `await process_alert_notification.kiq(...)`.
   - **Prometheus metrics**: Import existing metric objects (`follow_up_action_duration_seconds`, `follow_up_actions_total`, etc.) from `app.monitoring.metrics`. These are compatible with async code.
   - **Distributed locks**: Follow-up tasks use distributed locking for deduplication. Keep this pattern — it's not Celery-specific.

4. **Verify all 3 modules parse and have correct counts.**

## Must-Haves

- [ ] `quiz_link_taskiq.py` with 6 `@broker.task` functions, 3 schedule labels, `send_quiz_reminder` uses SmartRetryMiddleware
- [ ] `quiz_flow_taskiq.py` with 8 `@broker.task` functions, 1 schedule label, consolidated from 4 subpackage files
- [ ] `follow_up_taskiq.py` with 3 `@broker.task` functions, 3 schedule labels, zero `async_to_sync` imports
- [ ] Cross-module dispatch uses Taskiq imports: `quiz_flow_taskiq` → `quiz_link_taskiq.send_quiz_reminder`, `follow_up_taskiq` → `alerts_taskiq.process_alert_notification`
- [ ] Cron conversion: 03:00 BRT → 06:00 UTC for `cleanup_old_contexts`
- [ ] Pure helpers imported from Celery modules, no logic duplication
- [ ] trigger_service.py NOT modified — sync caller keeps Celery per D010
- [ ] All files pass `ast.parse()`

## Verification

- `python3 -c "import ast; ast.parse(open('app/tasks/quiz_link_taskiq.py').read()); ast.parse(open('app/tasks/quiz_flow_taskiq.py').read()); ast.parse(open('app/tasks/follow_up_taskiq.py').read()); print('All 3 modules parse OK')"` from backend-hormonia/
- `grep -c "@broker.task" app/tasks/quiz_link_taskiq.py app/tasks/quiz_flow_taskiq.py app/tasks/follow_up_taskiq.py` → 6 + 8 + 3 = 17
- `grep -c "schedule=" app/tasks/quiz_link_taskiq.py app/tasks/quiz_flow_taskiq.py app/tasks/follow_up_taskiq.py` → 3 + 1 + 3 = 7
- `grep "from app.tasks.quiz_link_taskiq" app/tasks/quiz_flow_taskiq.py` confirms cross-import
- `grep "from app.tasks.alerts_taskiq" app/tasks/follow_up_taskiq.py` confirms cross-import
- `grep -c "async_to_sync\|run_async" app/tasks/quiz_link_taskiq.py app/tasks/quiz_flow_taskiq.py app/tasks/follow_up_taskiq.py` → 0 (zero bridges)

## Inputs

- `backend-hormonia/app/tasks/quiz_link_tasks.py` — Celery source: 6 tasks, custom retry, distributed lock
- `backend-hormonia/app/tasks/quiz_flow/cleanup_tasks.py` — Celery source: 1 task, sync ORM
- `backend-hormonia/app/tasks/quiz_flow/trigger_tasks.py` — Celery source: 3 tasks, `async_to_sync`, cross-dispatch
- `backend-hormonia/app/tasks/quiz_flow/response_tasks.py` — Celery source: 2 tasks, `async_to_sync`, `run_async`
- `backend-hormonia/app/tasks/quiz_flow/question_tasks.py` — Celery source: 2 tasks, `async_to_sync`, `run_async`
- `backend-hormonia/app/tasks/follow_up.py` — Celery source: 3 tasks, 15+ bridges, cross-dispatch, Prometheus metrics
- T02 output: `backend-hormonia/app/tasks/alerts_taskiq.py` — provides `process_alert_notification` for follow_up cross-dispatch
- T01 established pattern reference from `audit_taskiq.py`, `lgpd_taskiq.py`

## Expected Output

- `backend-hormonia/app/tasks/quiz_link_taskiq.py` — 6 Taskiq tasks, SmartRetryMiddleware-based retry for send_quiz_reminder
- `backend-hormonia/app/tasks/quiz_flow_taskiq.py` — 8 Taskiq tasks consolidated from 4 subpackage files
- `backend-hormonia/app/tasks/follow_up_taskiq.py` — 3 Taskiq tasks, 15+ bridges removed, cross-dispatch to alerts_taskiq
