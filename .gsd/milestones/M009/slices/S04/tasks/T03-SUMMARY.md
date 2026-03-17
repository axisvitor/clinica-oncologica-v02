---
id: T03
parent: S04
milestone: M009
provides:
  - 3 Taskiq modules (quiz_link, quiz_flow, follow_up) with 17 tasks and 7 schedule labels
  - Cross-module dispatch chains: quiz_flow→quiz_link_taskiq, follow_up→alerts_taskiq
  - 15+ async_to_sync bridges removed from follow_up, all bridges removed from quiz_flow
  - quiz_flow 4-file subpackage consolidated into single module
key_files:
  - backend-hormonia/app/tasks/quiz_link_taskiq.py
  - backend-hormonia/app/tasks/quiz_flow_taskiq.py
  - backend-hormonia/app/tasks/follow_up_taskiq.py
key_decisions:
  - send_quiz_reminder uses SmartRetryMiddleware with delay=3600 (base) for exponential backoff ~3600→7200→14400, replacing Celery's manual countdown=[3600,7200,14400] pattern
  - quiz_flow consolidation: 4 Celery subpackage files (cleanup, trigger, response, question) → single quiz_flow_taskiq.py with 8 tasks
  - follow_up async helpers: created _*_async() wrappers (lock, dedup, schedule) that call redis_store methods with await directly, while importing sync-only helpers (_is_follow_up_eligible, _get_last_follow_up_sent_at_db, _update_patient_last_message_sent_at) from Celery module
patterns_established:
  - Complex cross-module Taskiq dispatch: follow_up→alerts_taskiq via await process_alert_notification.kiq(), quiz_flow→quiz_link_taskiq via await send_quiz_reminder.kiq()
  - Hybrid sync/async pattern for follow_up: sync ORM helpers imported from Celery module + async redis_store calls via direct await in Taskiq tasks
  - quiz_flow progress update uses async session factory directly (already async in Celery via run_async) — no sync ORM bridge needed
observability_surfaces:
  - 17 tasks emit structured log_task_start/success/error with task_name, duration_ms, event fields
  - follow_up Prometheus metrics preserved (action_duration, actions_total, messages_deduplicated, messages_sent, pending_actions gauge)
  - 7 schedule labels on @broker.task decorators readable by taskiq scheduler
  - Resilience WARNING logs for high expiry rate >30% and low reminder success rate <70%
duration: ~25min
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T03: Migrate complex modules (quiz_link, quiz_flow, follow_up)

**Created 3 Taskiq modules with 17 async-native tasks (6 quiz_link + 8 quiz_flow + 3 follow_up) replacing Celery tasks with 15+ bridge removals and cross-module .kiq() dispatch chains.**

## What Happened

Created 3 Taskiq parallel modules for the most complex task groups:

1. **quiz_link_taskiq.py** (6 tasks, 3 periodic): Migrated all 6 quiz link tasks. `send_quiz_reminder` custom retry pattern (countdown=[3600,7200,14400]) replaced with SmartRetryMiddleware `delay=3600` exponential backoff. Distributed lock pattern preserved. Pure helpers (`_sanitize_limit`, `_token_fingerprint`, `_sanitize_error_message`, `_sanitize_dlq_record`) imported from Celery module. Cross-dispatch within module uses `await .kiq()`.

2. **quiz_flow_taskiq.py** (8 tasks, 1 periodic): Consolidated 4 Celery subpackage files (cleanup_tasks, trigger_tasks, response_tasks, question_tasks) into single module. All `async_to_sync()` and `run_async()` bridges removed — async service methods called directly with `await`. Cross-dispatch to `quiz_link_taskiq.send_quiz_reminder` via `.kiq()`. Private helpers `_notify_doctor_of_expired_session` and `_resume_patient_flow_after_expiration` replicated inline (tightly coupled to session cleanup logic). Pure helpers imported from subpackage files.

3. **follow_up_taskiq.py** (3 tasks, 3 periodic): The most complex migration — 15+ `async_to_sync()` calls replaced with direct `await`. Created async helper functions (`_acquire_follow_up_lock_async`, `_release_follow_up_lock_async`, `_reserve_follow_up_message_slot_async`, etc.) that call `redis_store` methods directly. Sync-only helpers (`_is_follow_up_eligible`, `_get_last_follow_up_sent_at_db`, `_update_patient_last_message_sent_at`) imported from Celery module. Cross-dispatch to `alerts_taskiq.process_alert_notification` via `.kiq()`. Prometheus metrics fully preserved.

trigger_service.py NOT modified — sync caller keeps Celery `.apply_async()` per D010.

## Verification

All must-haves confirmed:

- **Parse check**: `ast.parse()` passes for all 3 modules → ✅
- **Task counts**: `@broker.task` count = 6 + 8 + 3 = 17 → ✅
- **Schedule counts**: `schedule=` count = 3 + 1 + 3 = 7 → ✅
- **Cross-imports**: `quiz_flow_taskiq` imports `send_quiz_reminder` from `quiz_link_taskiq` → ✅
- **Cross-imports**: `follow_up_taskiq` imports `process_alert_notification` from `alerts_taskiq` → ✅
- **Zero bridges (code)**: AST walk confirms zero `async_to_sync` or `run_async` in code (only in comments) → ✅
- **Cron conversion**: `cleanup_old_contexts` schedule = `cron("0 6 * * *")` (03:00 BRT → 06:00 UTC) → ✅
- **trigger_service.py**: not in changed files → ✅

Slice-level checks (partial — T03 is intermediate task):
- All 13 taskiq modules parse cleanly → ✅
- Total tasks across all taskiq modules: 72 (≥46 required) → ✅
- All 13 modules have error logging → ✅

## Diagnostics

- **Task failures**: `grep "event.*task_error" <log>` — all 17 tasks log structured errors with error_type and error_message
- **Schedule inspection**: 7 schedule labels on `@broker.task()` decorators; `taskiq scheduler --dump` reads all labels
- **Follow-up metrics**: Prometheus counters `follow_up_actions_total`, `follow_up_action_duration_seconds` track action execution; `follow_up_pending_actions` gauge shows backlog
- **Dedup visibility**: `follow_up_messages_deduplicated_total` counter tracks skipped messages by dedup_source (redis/db/lock)
- **Resilience health**: `monitor_resilience_metrics` logs WARNING for high expiry/low success rates
- **Cross-dispatch tracing**: quiz_flow→quiz_link via `.kiq()` linkage; follow_up→alerts_taskiq via `.kiq()` linkage

## Deviations

- `_notify_doctor_of_expired_session` and `_resume_patient_flow_after_expiration` replicated inline in `quiz_flow_taskiq.py` rather than imported from `cleanup_tasks.py` — these are private helper functions tightly coupled to the cleanup task's ORM session, not pure stateless helpers. Same pattern as T01's saga monitoring decision.
- `send_quiz_progress_update` uses `get_async_session_factory()` directly (the Celery version already used `run_async()` with an async inner function) — this is more natural in Taskiq than wrapping sync ORM.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/tasks/quiz_link_taskiq.py` — 6 Taskiq tasks for quiz link resilience (check expired, rotate token, send reminder, WhatsApp fallback, DLQ, metrics)
- `backend-hormonia/app/tasks/quiz_flow_taskiq.py` — 8 Taskiq tasks consolidated from 4 quiz_flow subpackage files (cleanup, triggers, responses, questions)
- `backend-hormonia/app/tasks/follow_up_taskiq.py` — 3 Taskiq tasks for follow-up system (pending execution, escalation, context cleanup) with 15+ bridges removed
- `.gsd/milestones/M009/slices/S04/tasks/T03-PLAN.md` — added Observability Impact section (pre-flight fix)
