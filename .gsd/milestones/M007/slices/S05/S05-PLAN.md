# S05: Alertas do quiz mensal acionáveis para o médico

**Goal:** When the monthly quiz generates a clinical alert, a persistent Notification is created for the patient's doctor, the alert appears highlighted in the physician dashboard with recommendation text, and the notification bell shows it immediately.

**Demo:** A quiz session completes with responses that trigger alert rules → Alert records are created in the database → Notification records are created for the patient's assigned doctor → The alerts API returns `title`, `message`, and `recommendation` fields → The physician dashboard renders the recommendation text alongside each quiz alert.

## Must-Haves

- `QuizResponseEvaluator.evaluate_quiz_session()` is called from `session_coordinator.complete_quiz_session()` after marking session complete
- Each triggered alert also creates a `Notification` record for the patient's doctor (via `patient.doctor_id`)
- If `patient.doctor_id` is None, no notification is created (logged warning, no crash)
- Duplicate alerts for the same `quiz_session_id` + `rule_id` are prevented
- Alert API serializer returns `title` (from `data.rule_name`), `message` (from `description`), and `recommendation` (from `data.recommendation`)
- Physician dashboard renders recommendation text on quiz alert cards
- Severity mapping: config CRITICAL→model CRITICAL→notification URGENT, config WARNING→model HIGH→notification HIGH, config INFO→model MEDIUM→notification MEDIUM

## Proof Level

- This slice proves: contract + integration
- Real runtime required: no (proven via focused unit/integration tests against mock DB)
- Human/UAT required: no

## Verification

- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_quiz_alert_notifications.py -v` — all tests pass
- `cd backend-hormonia && python3 -m pytest tests/api/v2/test_alerts.py -v` — existing alert tests pass (no regressions)
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — all flow tests pass
- `cd frontend-hormonia && npx tsc --noEmit` — frontend typecheck green
- Diagnostic failure-path check: verify that evaluator errors are caught in `complete_quiz_session()` (try/except wraps the call) — a failing evaluator must not crash quiz completion
- Diagnostic inspection: `_serialize_alert()` returns `title`, `message`, `recommendation` keys — verifiable via code review or test assertion

## Observability / Diagnostics

- Runtime signals: `logger.info("Alert {id} created for patient {patient_id}")` + `logger.info("Notification created for doctor {doctor_id}")` + `logger.warning("No doctor_id for patient {patient_id}, skipping notification")`
- Inspection surfaces: `SELECT * FROM notifications WHERE notification_type = 'alert'` for persistent notifications; `GET /api/v2/notifications?unread_only=true` for doctor's view; `GET /api/v2/alerts?alert_type=quiz_response&status=pending` for pending quiz alerts
- Failure visibility: duplicate alert skip logged; missing doctor_id logged; evaluator errors logged per-rule with `exc_info=True` (existing behavior)
- Redaction constraints: patient IDs in logs are UUIDs (no PII); notification content contains clinical alert text (acceptable for doctor-facing system)

## Integration Closure

- Upstream surfaces consumed:
  - `backend-hormonia/app/config/quiz_alert_rules.py` — 15 alert rules with evaluate/generate_message
  - `backend-hormonia/app/domain/quizzes/evaluation/response_evaluator.py` — QuizResponseEvaluator with _create_alert
  - `backend-hormonia/app/domain/agents/quiz/session_coordinator.py` — complete_quiz_session integration point
  - `backend-hormonia/app/models/notification.py` — Notification model (NotificationType.ALERT, NotificationPriority)
  - `backend-hormonia/app/models/alert.py` — Alert model with JSONB data field
  - `backend-hormonia/app/api/v2/routers/alerts.py` — _serialize_alert for API response shape
  - `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — alert card rendering
- New wiring introduced in this slice:
  - `session_coordinator.complete_quiz_session()` → `QuizResponseEvaluator.evaluate_quiz_session()`
  - `QuizResponseEvaluator._create_alert()` → `Notification()` creation for patient's doctor
  - `_serialize_alert()` → `title`/`message`/`recommendation` field projection from JSONB data
- What remains before the milestone is truly usable end-to-end: S06 (monthly summary by AI consuming responses + alerts)

## Tasks

- [x] **T01: Wire evaluator into quiz completion and persist notifications** `est:1h`
  - Why: The evaluator exists but is never called; alerts never generate Notification records; the dashboard can't show recommendation text because the serializer doesn't project it. This task closes all three gaps.
  - Files: `backend-hormonia/app/domain/agents/quiz/session_coordinator.py`, `backend-hormonia/app/domain/quizzes/evaluation/response_evaluator.py`, `backend-hormonia/app/api/v2/routers/alerts.py`, `frontend-hormonia/src/pages/PhysicianDashboard.tsx`
  - Do:
    1. In `session_coordinator.complete_quiz_session()`, after `complete_session()` call, transform `context.responses_so_far` (List[Dict]) into flat `Dict[str, Any]`, instantiate `QuizResponseEvaluator(self.db_session)`, call `await evaluator.evaluate_quiz_session()`. Wrap in try/except to not break quiz completion on evaluator failure.
    2. In `response_evaluator.py._create_alert()`, after creating the Alert, resolve `patient.doctor_id` via a query on Patient model. If doctor_id exists, create a `Notification` record with type=ALERT, priority mapped from severity, title from rule.name, message from rule.generate_message(), action_url pointing to patient, and notification_metadata containing alert_id/quiz_session_id/rule_id/recommendation/severity.
    3. Add duplicate alert guard: before creating an alert, check if an alert with same `quiz_session_id` + `rule_id` in data JSONB already exists for this patient. Skip if found.
    4. Wrap the `await self.audit_service.log_action()` call in try/except (audit service expects AsyncSession but gets sync Session — latent bug in existing code).
    5. In `alerts.py._serialize_alert()`, add `title` (from `data.rule_name` falling back to `alert_type`), `message` (from `description`), and `recommendation` (from `data.recommendation`) to the serialized output.
    6. In `PhysicianDashboard.tsx`, add recommendation text display below the alert message in the quiz alert cards.
  - Verify: `cd frontend-hormonia && npx tsc --noEmit` — typecheck green
  - Done when: evaluator is called on quiz completion, notifications are created for doctors, alert API returns title/message/recommendation, dashboard shows recommendation

- [x] **T02: Focused tests proving alert→notification chain** `est:45m`
  - Why: The wiring in T01 needs contract-level proof that the chain from quiz responses → alert evaluation → Alert + Notification creation works correctly, with edge cases for missing doctor, duplicates, and severity mapping.
  - Files: `backend-hormonia/tests/unit/services/flow/test_quiz_alert_notifications.py`
  - Do:
    1. Create test file with mock DB session (same shim pattern as test_sequential_message_handler.py).
    2. Test: `evaluate_quiz_session()` with triggering responses creates both Alert and Notification records.
    3. Test: Notification is created for the correct doctor (via patient.doctor_id lookup).
    4. Test: Severity mapping — config CRITICAL→notification URGENT, WARNING→HIGH, INFO→MEDIUM.
    5. Test: No notification when patient has no doctor_id (warning logged, no crash).
    6. Test: Duplicate alert prevention — second evaluation of same session+rule doesn't create duplicate.
    7. Test: No alerts/notifications created when no rules trigger.
    8. Test: Alert serializer includes title, message, recommendation fields.
    9. Run existing test suites for regression check.
  - Verify: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_quiz_alert_notifications.py -v` — all tests pass; `python3 -m pytest tests/api/v2/test_alerts.py -v` — no regressions; `python3 -m pytest tests/unit/services/flow/ -v` — all flow tests pass
  - Done when: all focused tests pass proving the complete chain, existing tests show 0 regressions

## Files Likely Touched

- `backend-hormonia/app/domain/agents/quiz/session_coordinator.py`
- `backend-hormonia/app/domain/quizzes/evaluation/response_evaluator.py`
- `backend-hormonia/app/api/v2/routers/alerts.py`
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx`
- `backend-hormonia/tests/unit/services/flow/test_quiz_alert_notifications.py`
