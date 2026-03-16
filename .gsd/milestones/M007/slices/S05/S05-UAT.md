# S05: Alertas do quiz mensal acionáveis para o médico — UAT

**Milestone:** M007
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: The slice wires existing components (evaluator, alert model, notification model, serializer, dashboard) — all integration points are proven by 14 focused tests with mock DB. No live runtime needed for the contract-level proof.

## Preconditions

- Backend dependencies installed: `cd backend-hormonia && pip install -r requirements.txt`
- Frontend dependencies installed: `cd frontend-hormonia && npm install`
- No running database or Redis required (tests use mocks)
- `quiz_alert_rules.py` contains 15 clinical rules (pain_score_critical, fever_with_chills, etc.)

## Smoke Test

```bash
cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_quiz_alert_notifications.py -v
```
All 14 tests pass — confirms evaluator→alert→notification chain works end to end.

## Test Cases

### 1. Alert creation from critical pain score

1. Call `evaluate_quiz_session()` with `pain_scale=9` (triggers `pain_score_critical` rule, threshold ≥ 7)
2. Verify an `Alert` record is created with `alert_type="quiz_response"`, `severity=CRITICAL`
3. Verify Alert `data` JSONB contains `quiz_session_id`, `triggered_rule_id="pain_score_critical"`, `rule_name`, `recommendation`
4. **Expected:** Alert created with correct CRITICAL severity and complete JSONB data

### 2. Notification targets patient's doctor

1. Create a mock patient with `doctor_id = UUID("doctor-abc")`
2. Trigger an alert via `_create_alert()`
3. Check `db.add()` calls for a `Notification` instance
4. **Expected:** `notification.user_id == patient.doctor_id`, `notification.related_patient_id == patient_id`, `notification.notification_type == NotificationType.ALERT`

### 3. Severity mapping chain

1. Verify `NOTIFICATION_PRIORITY_MAP` maps: `CRITICAL→URGENT`, `HIGH→HIGH`, `MEDIUM→MEDIUM`, `LOW→LOW`
2. Trigger alert with config severity WARNING → model severity HIGH → notification priority HIGH
3. **Expected:** Each severity level correctly maps through the chain from config→model→notification

### 4. Missing doctor_id — no notification, no crash

1. Create a mock patient with `doctor_id = None`
2. Trigger an alert via `_create_alert()`
3. **Expected:** Alert IS created successfully, but NO Notification record is added. Warning logged: "No doctor_id for patient {id}, skipping notification"

### 5. Duplicate alert prevention

1. Set up mock so `query().filter().first()` returns an existing Alert (simulating same session+rule)
2. Call `_create_alert()` with the same quiz_session_id + rule_id
3. **Expected:** Existing alert returned, no new Alert or Notification created, "Duplicate alert" logged

### 6. No rules trigger — clean pass

1. Call `evaluate_quiz_session()` with `pain_scale=0`, `sleep_quality=10`, no fever, etc.
2. **Expected:** Empty alerts list, `risk_score=0.0`, no Notification records

### 7. Alert serializer returns title/message/recommendation

1. Create an Alert with `data={"rule_name": "Dor Crítica", "recommendation": "Consulta urgente"}`, `description="Paciente relata dor severa"`
2. Call `_serialize_alert(alert)`
3. **Expected:** Output contains `title="Dor Crítica"`, `message="Paciente relata dor severa"`, `recommendation="Consulta urgente"`

### 8. Alert serializer fallback with empty data

1. Create an Alert with `data=None`, `alert_type="quiz_response"`, `description="Test"`
2. Call `_serialize_alert(alert)`
3. **Expected:** `title="quiz_response"` (fallback to alert_type), `recommendation=""` (fallback to empty string)

### 9. Frontend typecheck with recommendation field

1. Run `cd frontend-hormonia && npx tsc --noEmit`
2. **Expected:** No errors on app source files (only pre-existing e2e config errors)

### 10. Evaluator failure doesn't crash quiz completion

1. Inspect `session_coordinator.complete_quiz_session()` at L234-265
2. Verify the evaluator call is wrapped in try/except that catches Exception
3. Verify that `trigger_comprehensive_analysis()` runs regardless of evaluator success/failure
4. **Expected:** Quiz completion flow continues even when evaluator throws an exception

## Edge Cases

### fever_with_chills rule (compound condition)

1. Call `evaluate_quiz_session()` with `has_fever=True, has_chills=True`
2. **Expected:** Triggers `fever_with_chills` rule with CRITICAL severity alert

### Risk score from CRITICAL alert

1. Trigger a CRITICAL severity alert
2. **Expected:** `risk_score >= 50` in evaluation result

### Multiple rules trigger simultaneously

1. Send responses that trigger both `pain_score_critical` (pain_scale=9) and `fever_with_chills` (has_fever=True, has_chills=True)
2. **Expected:** Multiple Alert + Notification records created, one per triggered rule

## Failure Signals

- `test_quiz_alert_notifications.py` has any failures → alert→notification chain is broken
- `test_alerts.py` has regressions → serializer changes broke existing alert API behavior
- `npx tsc --noEmit` has new errors beyond pre-existing e2e config → Alert type changes broke frontend compilation
- Missing `recommendation` key in `_serialize_alert()` output → dashboard can't render recommendation text
- `Notification` records not created when doctor_id exists → doctor won't see quiz alerts in notification bell
- Application crashes on `complete_quiz_session()` → evaluator error containment is broken

## Requirements Proved By This UAT

- R062 — Quiz alerts create persistent Notification records for doctors, prevent duplicates, surface recommendation text, and appear in the physician dashboard

## Not Proven By This UAT

- Real runtime database behavior — tests use mock DB, not PostgreSQL
- WebSocket real-time push to doctor's browser — `_notify_medical_team()` is called but not tested in these unit tests
- Email notification delivery — notification persistence is proven, not email transport
- Dashboard visual rendering quality — typecheck proves compilation, not visual layout

## Notes for Tester

- The 1 failing test in `tests/unit/services/flow/` (`test_split_files_under_500_lines`) is pre-existing and unrelated to S05 — `sequencing.py` grew to 521 lines in S01/S04 work.
- The 6 TypeScript errors in `playwright.config.e2e.ts` are pre-existing and only affect e2e config, not app source.
- The audit service `log_action()` call is wrapped in try/except because it receives a sync Session but expects AsyncSession — this is a known pre-existing bug, not introduced by S05.
- To verify the dashboard rendering manually, look for `💡` emoji and `text-amber-600` styling in `PhysicianDashboard.tsx` around line 453-455.
