---
id: T01
parent: S05
milestone: M007
provides:
  - evaluator wired into quiz completion flow
  - notification persistence for triggered alerts
  - duplicate alert guard
  - alert serializer returns title/message/recommendation
  - dashboard renders recommendation text
key_files:
  - backend-hormonia/app/domain/agents/quiz/session_coordinator.py
  - backend-hormonia/app/domain/quizzes/evaluation/response_evaluator.py
  - backend-hormonia/app/api/v2/routers/alerts.py
  - frontend-hormonia/src/pages/PhysicianDashboard.tsx
  - frontend-hormonia/src/lib/api-client/types/alerts.ts
  - backend-hormonia/tests/unit/services/flow/test_quiz_alert_notifications.py
key_decisions:
  - Notification creation wrapped in inner try/except inside _create_alert so alert creation succeeds even if notification fails
  - Audit service call wrapped in try/except (latent sync/async mismatch — contained, not fixed)
  - Duplicate guard uses JSONB astext filters on data.quiz_session_id + data.triggered_rule_id
patterns_established:
  - Notification creation alongside Alert creation in evaluator (not in _notify_medical_team)
  - NOTIFICATION_PRIORITY_MAP class constant for severity→priority mapping
observability_surfaces:
  - logger.info("Notification created for doctor {doctor_id} from alert {alert_id}")
  - logger.warning("No doctor_id for patient {patient_id}, skipping notification")
  - logger.info("Duplicate alert for session {quiz_session_id} rule {rule_id}, skipping")
  - logger.debug("Audit log skipped for quiz evaluation: {error}")
  - SELECT * FROM notifications WHERE notification_type = 'alert'
  - GET /api/v2/alerts response now includes title, message, recommendation fields
duration: 25min
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Wire evaluator into quiz completion and persist notifications

**Wired QuizResponseEvaluator into session_coordinator.complete_quiz_session(), added Notification creation for doctors on each triggered alert, added duplicate alert guard, fixed alert serializer to return title/message/recommendation, and added recommendation rendering to PhysicianDashboard**

## What Happened

1. **session_coordinator.py**: After `complete_session()`, transforms `context.responses_so_far` (List[Dict]) into flat `Dict[str, Any]` keyed by question_id, instantiates `QuizResponseEvaluator`, and calls `evaluate_quiz_session()`. Entire block is wrapped in try/except so quiz completion never fails on evaluator errors.

2. **response_evaluator.py**: 
   - Added imports for `Notification`, `NotificationType`, `NotificationPriority`, `Patient`.
   - Added `NOTIFICATION_PRIORITY_MAP` class constant mapping model severity to notification priority.
   - Added `_map_notification_priority()` method.
   - In `_create_alert()`: added duplicate guard checking same patient_id + alert_type + JSONB quiz_session_id + triggered_rule_id. Returns existing alert if found.
   - After creating the alert: queries Patient for doctor_id, creates `Notification` record with type=ALERT, mapped priority, title/message from rule, action_url, and metadata. Handles missing doctor_id with warning log.
   - Wrapped `audit_service.log_action()` in try/except (latent sync/async mismatch).

3. **alerts.py**: Added `title`, `message`, `recommendation` fields to `_serialize_alert()` output dict.

4. **alerts.ts**: Added `recommendation?: string` to frontend `Alert` interface.

5. **PhysicianDashboard.tsx**: Added recommendation text display below alert message with amber-600 styling and 💡 emoji.

6. **test_quiz_alert_notifications.py**: Created skeleton test file with 2 passing tests (severity mapping constants, serializer fields) and 3 skipped placeholders for T02.

## Verification

- `npx tsc --noEmit` — typecheck green (only pre-existing e2e config errors)
- `npm run build` — build succeeds
- `pytest tests/unit/services/flow/test_quiz_alert_notifications.py -v` — 2 passed, 3 skipped
- `pytest tests/api/v2/test_alerts.py -v` — 42 passed, 0 failed (no regressions)
- `pytest tests/unit/services/flow/ -v` — 156 passed, 7 skipped, 1 pre-existing failure (unrelated sequencing.py line count)
- Code inspection confirms: evaluator called in complete_quiz_session, Notification created in _create_alert, duplicate guard present, serializer returns title/message/recommendation

### Slice Verification Status (intermediate — T01 of 2)
- `test_quiz_alert_notifications.py` — 2 passed, 3 skipped (T02 will fill in integration tests)
- `test_alerts.py` — ✅ 42 passed
- `tests/unit/services/flow/` — ✅ 156 passed (1 pre-existing failure)
- `npx tsc --noEmit` — ✅ green
- Diagnostic failure-path check — ✅ evaluator errors caught in complete_quiz_session try/except
- Diagnostic inspection — ✅ _serialize_alert returns title, message, recommendation keys

## Diagnostics

- **Notification persistence**: `SELECT * FROM notifications WHERE notification_type = 'alert'` shows notifications created for doctors
- **Alert deduplication**: `logger.info("Duplicate alert for session...")` logged when duplicate detected
- **Missing doctor**: `logger.warning("No doctor_id for patient...")` logged when patient has no doctor
- **Evaluator failures**: `logger.error("Quiz response evaluation failed...")` with exc_info in session_coordinator
- **Audit skip**: `logger.debug("Audit log skipped...")` when audit service call fails (expected until async session fix)

## Deviations

- Plan Step 6 suggested using `(alert as any).recommendation` — unnecessary since `recommendation` was added to the Alert interface proper; used typed access `alert.recommendation` instead.
- Created skeleton test file with 2 real tests + 3 placeholders (plan assigns full test suite to T02).

## Known Issues

- Audit service `log_action` call is a no-op (sync Session passed to what expects AsyncSession). Wrapped in try/except per plan — fixing the audit service is out of scope.
- Pre-existing test failure: `test_split_files_under_500_lines` — `sequencing.py` has 521 lines, unrelated to this task.

## Files Created/Modified

- `backend-hormonia/app/domain/agents/quiz/session_coordinator.py` — wired evaluator call with response transformation and error containment
- `backend-hormonia/app/domain/quizzes/evaluation/response_evaluator.py` — added Notification creation, duplicate guard, priority mapping, audit try/except
- `backend-hormonia/app/api/v2/routers/alerts.py` — added title/message/recommendation to _serialize_alert
- `frontend-hormonia/src/lib/api-client/types/alerts.ts` — added recommendation field to Alert interface
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — added recommendation text rendering on alert cards
- `backend-hormonia/tests/unit/services/flow/test_quiz_alert_notifications.py` — created skeleton test file for T02
- `.gsd/milestones/M007/slices/S05/S05-PLAN.md` — marked T01 done, added diagnostic verification step
- `.gsd/milestones/M007/slices/S05/tasks/T01-PLAN.md` — added Observability Impact section
