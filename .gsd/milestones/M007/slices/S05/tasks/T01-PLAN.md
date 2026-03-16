---
estimated_steps: 6
estimated_files: 4
---

# T01: Wire evaluator into quiz completion and persist notifications

**Slice:** S05 — Alertas do quiz mensal acionáveis para o médico
**Milestone:** M007

## Description

The `QuizResponseEvaluator` exists with 15 clinical alert rules but is never called anywhere in the runtime. The quiz completion flow in `session_coordinator.complete_quiz_session()` marks sessions complete and sends swarm analysis messages, but never evaluates responses against alert rules. Additionally, even when alerts would be created, no `Notification` model record is written — the evaluator's `_notify_medical_team()` sends WebSocket broadcasts and emails but doesn't persist to the `notifications` table. Finally, the alerts API serializer doesn't return `title`/`message`/`recommendation` fields, so the physician dashboard renders empty alert cards.

This task closes all three gaps: wires the evaluator call, adds Notification creation, and fixes the serializer + dashboard rendering.

## Steps

1. **Wire evaluator into session_coordinator.complete_quiz_session()**
   - After the `self.quiz_session_service.complete_session(context.session.id)` call (~line 233), add:
     - Transform `context.responses_so_far` (which is `List[Dict]`) into a flat `Dict[str, Any]` suitable for the evaluator. Each dict in the list may have keys like `question_id` and `response_value` — iterate and build `{question_id: response_value}`.
     - Import and instantiate `QuizResponseEvaluator(self.db_session)`.
     - Call `await evaluator.evaluate_quiz_session(context.session.id, context.patient_id, flat_responses)`.
     - Wrap the entire evaluator block in `try/except Exception` with error logging — quiz completion must not fail because evaluation failed.
   - Add import: `from app.domain.quizzes.evaluation.response_evaluator import QuizResponseEvaluator`

2. **Add Notification creation in response_evaluator._create_alert()**
   - After the `created_alert = self.alert_repository.create(alert)` and `self.db.commit()` block, add notification creation:
     - Query `Patient` model to get `doctor_id`: `patient = self.db.query(Patient).filter(Patient.id == patient_id).first()`
     - If `patient` is None or `patient.doctor_id` is None, log warning and skip notification (don't crash).
     - Create `Notification` instance:
       ```python
       notification = Notification(
           user_id=patient.doctor_id,
           related_patient_id=patient_id,
           notification_type=NotificationType.ALERT,
           priority=self._map_notification_priority(model_severity),
           title=f"Alerta: {rule.name}",
           message=rule.generate_message(responses),
           action_url=f"/patients/{patient_id}",
           action_label="Revisar Paciente",
           notification_metadata={
               "alert_id": str(created_alert.id),
               "quiz_session_id": str(quiz_session_id),
               "rule_id": rule.rule_id,
               "recommendation": rule.recommendation,
               "severity": model_severity.value,
           },
       )
       self.db.add(notification)
       self.db.commit()
       ```
   - Add new method `_map_notification_priority()`:
     ```python
     NOTIFICATION_PRIORITY_MAP = {
         ModelAlertSeverity.CRITICAL: NotificationPriority.URGENT,
         ModelAlertSeverity.HIGH: NotificationPriority.HIGH,
         ModelAlertSeverity.MEDIUM: NotificationPriority.MEDIUM,
         ModelAlertSeverity.LOW: NotificationPriority.LOW,
     }
     def _map_notification_priority(self, severity):
         return self.NOTIFICATION_PRIORITY_MAP.get(severity, NotificationPriority.MEDIUM)
     ```
   - Add imports: `from app.models.notification import Notification, NotificationType, NotificationPriority` and `from app.models.patient import Patient`

3. **Add duplicate alert guard in response_evaluator._create_alert()**
   - Before creating the Alert instance, query for existing alerts with same patient_id + alert_type='quiz_response' and matching `quiz_session_id` + `rule_id` in the `data` JSONB:
     ```python
     existing = self.db.query(Alert).filter(
         Alert.patient_id == patient_id,
         Alert.alert_type == "quiz_response",
         Alert.data["quiz_session_id"].astext == str(quiz_session_id),
         Alert.data["triggered_rule_id"].astext == rule.rule_id,
     ).first()
     if existing:
         logger.info(f"Duplicate alert for session {quiz_session_id} rule {rule.rule_id}, skipping")
         return existing
     ```

4. **Wrap audit_service.log_action in try/except**
   - The `AuditService(db)` in `evaluate_quiz_session()` is instantiated with a sync Session, but `AuditService` expects `AsyncSession` (it uses `async def log_event`). The `await self.audit_service.log_action()` call will fail because `log_action` doesn't exist (the real method is `log_event`).
   - Wrap the entire audit block in `try/except Exception` with a debug-level log. This is a pre-existing latent bug — don't fix the audit service, just prevent it from crashing the evaluator.

5. **Fix alert API serializer to include title/message/recommendation**
   - In `alerts.py._serialize_alert()`, add three fields to the output dict:
     ```python
     "title": (alert.data or {}).get("rule_name", alert.alert_type),
     "message": alert.description,
     "recommendation": (alert.data or {}).get("recommendation", ""),
     ```
   - This ensures the frontend `Alert` interface (which expects `title` and `message`) receives proper values.

6. **Show recommendation text in PhysicianDashboard alert cards**
   - In `PhysicianDashboard.tsx`, in the alert card rendering (~line 451-452), add recommendation display:
     - After `<p className="text-sm text-muted-foreground">{alert.message}</p>`, add:
       ```tsx
       {(alert as any).recommendation && (
         <p className="text-xs text-amber-600 mt-1">💡 {(alert as any).recommendation}</p>
       )}
       ```
   - Also add `recommendation` to the frontend `Alert` type in `alerts.ts`:
     ```typescript
     recommendation?: string
     ```

## Must-Haves

- [ ] `evaluate_quiz_session()` is called from `complete_quiz_session()` with properly transformed responses
- [ ] Each triggered alert creates a Notification for the patient's assigned doctor
- [ ] Missing doctor_id is handled gracefully (warning log, no crash)
- [ ] Duplicate alerts for same session+rule are prevented
- [ ] Alert API serializer returns title, message, and recommendation
- [ ] Dashboard shows recommendation text on alert cards

## Verification

- `cd frontend-hormonia && npx tsc --noEmit` — typecheck green, no new errors
- `cd frontend-hormonia && npm run build` — build succeeds
- Manual code inspection: `session_coordinator.complete_quiz_session()` now calls evaluator
- Manual code inspection: `_create_alert()` now creates Notification record

## Inputs

- `backend-hormonia/app/domain/agents/quiz/session_coordinator.py` — integration point at `complete_quiz_session()` (~line 222). Uses sync `Session` as `self.db_session`. `context.responses_so_far` is `List[Dict]` (each dict has question_id/response_value).
- `backend-hormonia/app/domain/quizzes/evaluation/response_evaluator.py` — evaluator with `_create_alert()` that creates Alert records. Uses sync `Session`. Has `SEVERITY_MAP` mapping config→model severity. `_notify_medical_team()` does WebSocket/email but NOT Notification records.
- `backend-hormonia/app/models/notification.py` — `Notification` model with `user_id` (required, FK users), `related_patient_id` (nullable, FK patients), `notification_type` (NotificationType enum: ALERT), `priority` (NotificationPriority enum: LOW/MEDIUM/HIGH/URGENT), `title`, `message`, `action_url`, `action_label`, `notification_metadata` (JSONB).
- `backend-hormonia/app/models/alert.py` — `Alert` model. `data` JSONB stores `quiz_session_id`, `triggered_rule_id`, `rule_name`, `recommendation`.
- `backend-hormonia/app/models/patient.py` — `Patient.doctor_id` is nullable FK to `users.id`.
- `backend-hormonia/app/api/v2/routers/alerts.py` — `_serialize_alert()` at ~line 100. Returns `alert_type`, `description` but NOT `title`/`message`/`recommendation`.
- `frontend-hormonia/src/lib/api-client/types/alerts.ts` — frontend `Alert` interface expects `title`, `message` strings.
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — renders `alert.title` and `alert.message` at lines 451-452.
- S04 provides `patient_flow_responses` table — not directly consumed by this task but contextually relevant.

## Expected Output

- `backend-hormonia/app/domain/agents/quiz/session_coordinator.py` — `complete_quiz_session()` now calls `QuizResponseEvaluator.evaluate_quiz_session()` with transformed responses
- `backend-hormonia/app/domain/quizzes/evaluation/response_evaluator.py` — `_create_alert()` now also creates `Notification` for doctor; `_map_notification_priority()` added; duplicate guard added; audit wrapped in try/except
- `backend-hormonia/app/api/v2/routers/alerts.py` — `_serialize_alert()` now returns `title`, `message`, `recommendation`
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — alert cards show recommendation text
- `frontend-hormonia/src/lib/api-client/types/alerts.ts` — `recommendation` field added to Alert interface
