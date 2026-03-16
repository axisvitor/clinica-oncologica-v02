# S05 — Alertas do quiz mensal acionáveis para o médico — Research

**Date:** 2026-03-16

## Summary

The slice goal is simple: when the monthly quiz generates a clinical alert, the doctor must see it — both as a persistent notification and as a highlighted card in the dashboard with a clear recommended action.

The good news is that nearly all the pieces already exist. The 15 clinical alert rules in `quiz_alert_rules.py` are well-designed (5 CRITICAL, 7 WARNING, 4 INFO). The `QuizResponseEvaluator` class evaluates quiz responses against these rules and creates `Alert` records. The `Notification` model, repository, and API are fully built. The `NotificationCenter` component reads from the notifications API. The `PhysicianDashboard` already has an "Alertas Críticos" card that reads from the alerts API.

The bad news — and the core gap — is that **`QuizResponseEvaluator.evaluate_quiz_session()` is never called anywhere in the runtime**. It's exported in `__init__.py` barrels but no task, service, or endpoint invokes it. The quiz completion flow in `session_coordinator.complete_quiz_session()` marks the session complete and sends swarm analysis messages to other agents, but never evaluates responses against the alert rules. Additionally, even if alerts were created, no `Notification` model record is ever written — the evaluator's `_notify_medical_team()` sends WebSocket broadcasts and emails but doesn't persist to the `notifications` table.

This is a wiring slice, not a design slice. The work is connecting existing, well-built components in the right order.

## Recommendation

Wire `QuizResponseEvaluator` into the quiz completion flow, add `Notification` record creation when alerts are generated, and write focused tests proving the chain from quiz responses → alert evaluation → alert + notification creation → API visibility.

Three tasks:
1. **Wire evaluator + create notifications (backend)** — call `QuizResponseEvaluator.evaluate_quiz_session()` from `session_coordinator.complete_quiz_session()`, and in `_create_alert()` also persist a `Notification` record for the patient's doctor
2. **Frontend quiz alert visibility** — minor dashboard adjustments to show recommendation text and action URL from quiz alerts
3. **Focused tests** — prove the complete chain works

## Implementation Landscape

### Key Files

#### Backend — Alert evaluation (exists, needs wiring)

- `backend-hormonia/app/config/quiz_alert_rules.py` — 15 `QuizAlertRule` definitions with `rule_id`, `severity`, `condition`, `recommendation`. Each rule has `.evaluate(responses)` and `.generate_message(responses)`. **No changes needed.**
- `backend-hormonia/app/domain/quizzes/evaluation/response_evaluator.py` — `QuizResponseEvaluator` with `evaluate_quiz_session(quiz_session_id, patient_id, responses)`. Iterates `QUIZ_ALERT_RULES`, creates `Alert` records via `AlertRepository`, calls `_notify_medical_team()`. **Needs modification**: `_create_alert()` must also create a `Notification` record. Currently uses sync `Session` — needs async adaptation or a thin async wrapper.
- `backend-hormonia/app/domain/agents/quiz/session_coordinator.py` — `complete_quiz_session()` at line 222. Calls `self.quiz_session_service.complete_session(context.session.id)` then `trigger_comprehensive_analysis()`. **This is the integration point** — after completion, call `QuizResponseEvaluator.evaluate_quiz_session()` with the session's collected responses.

#### Backend — Alert model (exists, no changes needed)

- `backend-hormonia/app/models/alert.py` — `Alert` model with `patient_id`, `alert_type`, `severity` (LOW/MEDIUM/HIGH/CRITICAL enum), `description`, `data` (JSONB), `acknowledged` boolean, timestamps. Quiz alerts use `alert_type="quiz_response"` and store `quiz_session_id`, `triggered_rule_id`, `rule_name`, `recommendation` in `data` JSONB.
- `backend-hormonia/app/repositories/alert.py` — `AlertRepository` with `create()` method. **No changes needed.**

#### Backend — Notification model (exists, needs write path)

- `backend-hormonia/app/models/notification.py` — `Notification` model with `user_id` (FK to users), `related_patient_id` (FK to patients), `notification_type` (info/warning/error/success/alert/reminder), `priority` (low/medium/high/urgent), `title`, `message`, `action_url`, `action_label`, `notification_metadata` (JSONB), `is_read`, `read_at`. **No model changes needed** — the schema already supports everything.
- `backend-hormonia/app/repositories/notification.py` — `NotificationRepository` with full CRUD. Uses sync `Session`. **No changes needed.**
- `backend-hormonia/app/api/v2/routers/notifications.py` — Async notification list, mark-read, unread-count endpoints. Uses `get_current_user_from_session` auth. **No changes needed.**

#### Backend — Quiz alert API (exists, no changes needed)

- `backend-hormonia/app/api/v2/routers/quiz_alerts.py` — 5 endpoints for quiz alerts: list, detail, acknowledge, statistics, create-rule. Filters by `alert_type == "quiz_response"`. RBAC: doctors see their patients' alerts, admin sees all. **No changes needed.**
- `backend-hormonia/app/api/v2/routers/alerts.py` — Generic alerts API used by the physician dashboard. Already has list with severity/status/patient filtering. **No changes needed.**

#### Backend — Patient-doctor link

- `backend-hormonia/app/models/patient.py` — `Patient` has `doctor_id` FK to `users.id`. This is how we resolve which doctor gets the notification for a given patient.

#### Frontend — Dashboard (exists, minor enhancement)

- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — Lines 172-180: fetches alerts via `apiClient.alerts.list({severity: 'high', status: 'pending', size: 10})`. Lines 435-460: renders "Alertas Críticos" card with title, message, and "Revisar" button. **Currently shows `alert.title` and `alert.message`** — but the `Alert` model doesn't have `title`/`message` fields (it has `alert_type` and `description`). The serializer in `alerts.py` maps `description` but not `title`. The dashboard also doesn't show `recommendation`.
- `frontend-hormonia/src/components/layout/NotificationCenter.tsx` — Bell icon popover showing notifications from `/api/v2/notifications`. Already handles `type: 'alert'` with red icon. **No changes needed** — once notifications are created in the DB, they'll appear here automatically.
- `frontend-hormonia/src/lib/api-client/alerts.ts` — `createAlertsApi` with full CRUD. **No changes needed.**
- `frontend-hormonia/src/lib/api-client/types/alerts.ts` — `Alert` interface with `title`, `message`, `severity`, `status`, `patient_id`, etc. **No changes needed.**

### Critical Implementation Details

#### Sync vs Async Gap

`QuizResponseEvaluator` uses sync `Session` and `AlertRepository(db)`. The `session_coordinator.py` operates in async context with `self.db_session`. The evaluator's `_create_alert()` calls `self.db.commit()` synchronously. Two options:
1. **Adapt the evaluator to async** — change `Session` to `AsyncSession`, use `await db.commit()`. This is cleaner but touches more code.
2. **Keep sync and run in executor** — wrap the sync evaluator call in `asyncio.to_thread()` or use a separate sync session. Riskier with transaction boundaries.

**Recommendation:** Option 1 — adapt `QuizResponseEvaluator` to async. The evaluator is self-contained enough to modify safely.

#### Notification Creation Logic

When `_create_alert()` creates an `Alert`, it should also create a `Notification`:
```python
notification = Notification(
    user_id=doctor_id,  # from patient.doctor_id
    related_patient_id=patient_id,
    notification_type=NotificationType.ALERT,
    priority=NotificationPriority.HIGH if severity >= HIGH else NotificationPriority.MEDIUM,
    title=f"Alerta: {rule.name}",
    message=rule.generate_message(responses),
    action_url=f"/patients/{patient_id}",  # or quiz-specific URL
    action_label="Revisar Paciente",
    notification_metadata={
        "alert_id": str(alert.id),
        "quiz_session_id": str(quiz_session_id),
        "rule_id": rule.rule_id,
        "recommendation": rule.recommendation,
        "severity": severity.value,
    },
)
```

#### Dashboard Alert Rendering Gap

The `PhysicianDashboard` renders `alert.title` and `alert.message`, but the `/api/v2/alerts` serializer returns `alert_type` and `description`, not `title`/`message`. Looking at the serializer, it maps:
- `alert_type` → `alert_type`
- `description` → `description`

But the frontend `Alert` type expects `title` and `message`. The existing dashboard works because the apiClient normalizes the response. The `data` JSONB field contains `rule_name` and `recommendation` — these should be surfaced in the dashboard as `title` and action context.

The simplest fix: in the alerts serializer, also include `title` (from `data.rule_name` or a formatted string) and `recommendation` (from `data.recommendation`). Or adjust the frontend rendering to use `alert_type` and `description`.

### Build Order

1. **T01 (Backend wiring + notification creation):** 
   - Adapt `QuizResponseEvaluator` to async (change `Session` → `AsyncSession`, add `await` to DB calls)
   - In `_create_alert()`, after creating the `Alert`, also create a `Notification` for the patient's doctor
   - Wire `evaluate_quiz_session()` into `session_coordinator.complete_quiz_session()` — call it after marking session complete, passing the collected responses
   - Add `recommendation` field to alert API serialization

2. **T02 (Frontend enhancement):**
   - Show recommendation text on quiz alert cards in `PhysicianDashboard`
   - Ensure the "Revisar" button navigates to the patient detail with quiz context

3. **T03 (Tests):**
   - Test that `QuizResponseEvaluator.evaluate_quiz_session()` with triggering responses creates both `Alert` and `Notification` records
   - Test that `Notification` is created for the correct doctor (via `patient.doctor_id`)
   - Test severity mapping from config `AlertSeverity` to model `AlertSeverity` to `NotificationPriority`
   - Test that no notification is created when no rules trigger
   - Test that `session_coordinator.complete_quiz_session()` invokes evaluation

### Verification Approach

```bash
# Run focused tests
cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_quiz_alert_notifications.py -v

# Run existing quiz/alert tests to check for regressions
cd backend-hormonia && python3 -m pytest tests/api/v2/test_alerts.py -v

# Frontend build check
cd frontend-hormonia && npx tsc --noEmit && npm run build
```

## Constraints

- `QuizResponseEvaluator` currently uses sync `Session` — must adapt to async for integration with the async session coordinator
- The `Notification.user_id` is required (not nullable) — if a patient has no `doctor_id`, we cannot create a notification. Must handle this gracefully (skip notification, log warning).
- `QuizResponseEvaluator.SEVERITY_MAP` maps config `CRITICAL→model CRITICAL`, `WARNING→model HIGH`, `INFO→model MEDIUM`. The `NotificationPriority` mapping should follow this: CRITICAL→URGENT, HIGH→HIGH, MEDIUM→MEDIUM.
- The evaluator's `_notify_medical_team()` already has email/WhatsApp notification logic — but it relies on `get_notification_service()` which requires SMTP config. In dev/test, this will no-op. The critical path is the persistent `Notification` record, not the email delivery.

## Common Pitfalls

- **Missing doctor_id** — If `patient.doctor_id` is None (the column is nullable), the notification creation will fail because `Notification.user_id` is required. Guard with an early check and log a warning.
- **Sync/async session mixing** — The evaluator's `self.db.commit()` is sync. If called with an `AsyncSession`, it will fail. Must fully convert or use a separate sync session. Don't mix.
- **Transaction scope** — `_create_alert()` calls `self.db.commit()` after each alert. In async context, this should be coordinated — either commit all alerts at once or commit per-alert. The existing pattern commits per-alert, which is acceptable for quiz evaluation (typically 0-3 alerts per session).
- **Duplicate alerts** — If the evaluator is called twice for the same session (retry, race condition), duplicate alerts could be created. The `data` JSONB already contains `quiz_session_id` — consider checking for existing alerts with the same `quiz_session_id` + `rule_id` before creating.

## Open Risks

- The `QuizResponseEvaluator` has never been executed against real data — its `_normalize_responses()` may not correctly handle the actual response format coming from `context.responses_so_far` (which is a list of dicts, not a flat key-value dict). The evaluator expects `Dict[str, Any]` with keys like `pain_scale`, `has_fever`, etc. — the quiz template question IDs need to match these keys, or the normalization needs adjustment.
