---
estimated_steps: 9
estimated_files: 1
---

# T02: Focused tests proving alert→notification chain

**Slice:** S05 — Alertas do quiz mensal acionáveis para o médico
**Milestone:** M007

## Description

T01 wired the evaluator into quiz completion and added Notification creation. This task proves the complete chain with focused tests: quiz responses → rule evaluation → Alert creation → Notification creation → correct doctor targeting → severity mapping → duplicate prevention → serializer output. Also runs existing test suites to verify zero regressions.

## Steps

1. **Create test file structure**
   - Create `backend-hormonia/tests/unit/services/flow/test_quiz_alert_notifications.py`
   - Use the same mock DB shim pattern established in `test_sequential_message_handler.py` — mock `Session` with `query()`, `add()`, `commit()`, `flush()`, `rollback()`, `refresh()` methods.
   - Create helper to build a mock Patient with configurable `doctor_id` (UUID or None).
   - Create helper to build mock quiz responses that trigger known alert rules. Refer to `backend-hormonia/app/config/quiz_alert_rules.py` for actual rule conditions — use `pain_scale >= 8` (CRITICAL rule `critical_pain`) and `has_fever=True + has_chills=True` (CRITICAL rule `fever_with_chills`) as test triggers.

2. **Test: evaluate_quiz_session with triggering responses creates Alert**
   - Setup: mock DB, mock AlertRepository.create() to capture the alert, mock Patient query to return patient with doctor_id.
   - Input: responses `{"pain_scale": 9}` to trigger `critical_pain` rule.
   - Assert: `AlertRepository.create()` was called, alert has `alert_type="quiz_response"`, `severity=CRITICAL`, `data` contains `quiz_session_id`, `triggered_rule_id`, `rule_name`, `recommendation`.

3. **Test: Notification created for correct doctor**
   - Setup: same as above, mock Patient with `doctor_id=UUID("...")`.
   - Assert: `db.add()` was called with a `Notification` instance where `user_id == patient.doctor_id`, `related_patient_id == patient_id`, `notification_type == NotificationType.ALERT`.

4. **Test: Severity mapping CRITICAL→URGENT, WARNING→HIGH, INFO→MEDIUM**
   - For each severity level, trigger a rule of that severity and verify the created Notification has the correct `NotificationPriority`.
   - Use `SEVERITY_MAP` and `NOTIFICATION_PRIORITY_MAP` constants to verify the chain: config AlertSeverity → model AlertSeverity → NotificationPriority.

5. **Test: No notification when patient has no doctor_id**
   - Setup: mock Patient with `doctor_id=None`.
   - Input: triggering responses.
   - Assert: Alert IS created (alert system works), but NO Notification is created (db.add not called with Notification). A warning is logged.

6. **Test: Duplicate alert prevention**
   - Setup: mock `db.query(Alert).filter(...).first()` to return an existing alert on second call.
   - Call `evaluate_quiz_session()` twice with same session_id and responses.
   - Assert: second call returns the existing alert, no new Alert or Notification created.

7. **Test: No alerts when no rules trigger**
   - Input: responses `{"pain_scale": 1}` (low pain, no fever, no symptoms).
   - Assert: returned alerts list is empty, risk score is 0.0, no Notification created.

8. **Test: Alert serializer includes title, message, recommendation**
   - Import `_serialize_alert` from `app.api.v2.routers.alerts`.
   - Create a mock Alert with `data={"rule_name": "Dor Crítica", "recommendation": "Avaliar paciente"}` and `description="Paciente relata dor 9/10"`.
   - Assert serialized output has `title == "Dor Crítica"`, `message == "Paciente relata dor 9/10"`, `recommendation == "Avaliar paciente"`.

9. **Run regression checks**
   - `cd backend-hormonia && python3 -m pytest tests/api/v2/test_alerts.py -v` — existing alert tests pass.
   - `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — all flow tests pass.

## Must-Haves

- [ ] Test file created with ≥7 focused tests
- [ ] Alert creation proven with correct JSONB data fields
- [ ] Notification→doctor targeting proven via patient.doctor_id
- [ ] All three severity mappings proven
- [ ] Missing doctor_id graceful handling proven
- [ ] Duplicate prevention proven
- [ ] Serializer output shape proven
- [ ] Existing tests show 0 regressions

## Verification

- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_quiz_alert_notifications.py -v` — all tests pass
- `cd backend-hormonia && python3 -m pytest tests/api/v2/test_alerts.py -v` — existing tests pass
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — all flow tests green

## Inputs

- `backend-hormonia/app/domain/quizzes/evaluation/response_evaluator.py` — the evaluator modified by T01 with `_create_alert()` now creating Notifications, `_map_notification_priority()`, and duplicate guard
- `backend-hormonia/app/domain/agents/quiz/session_coordinator.py` — `complete_quiz_session()` now calling evaluator (modified by T01)
- `backend-hormonia/app/config/quiz_alert_rules.py` — 15 rules: `critical_pain` (pain_scale ≥ 8, CRITICAL), `fever_with_chills` (has_fever + has_chills, CRITICAL), various WARNING and INFO rules
- `backend-hormonia/app/models/alert.py` — Alert model with JSONB `data` field, `AlertSeverity` enum (LOW/MEDIUM/HIGH/CRITICAL), `AlertStatus` enum
- `backend-hormonia/app/models/notification.py` — Notification model with `NotificationType` (ALERT), `NotificationPriority` (LOW/MEDIUM/HIGH/URGENT)
- `backend-hormonia/app/api/v2/routers/alerts.py` — `_serialize_alert()` modified by T01 to include title/message/recommendation
- `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py` — reference for mock DB shim pattern
- T01 summary — confirms all wiring changes and method signatures

## Expected Output

- `backend-hormonia/tests/unit/services/flow/test_quiz_alert_notifications.py` — ≥7 focused tests proving the complete alert→notification chain with edge cases
