```markdown
# Quiz Alert Evaluation System

**Sprint 2 - Week 1, Task 3: Automatic Alert Evaluation**

## Overview

The Quiz Alert Evaluation System automatically analyzes patient quiz responses and generates alerts when risk thresholds are exceeded, enabling immediate medical intervention.

### Problem Solved

- ✅ Automatic evaluation of quiz responses
- ✅ Real-time alert generation for high-risk conditions
- ✅ Immediate notification to medical team
- ✅ Risk scoring and severity classification
- ✅ Comprehensive alert tracking and acknowledgment

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Quiz Completion Flow                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Patient Completes Quiz                                   │
│           ↓                                                   │
│  2. QuizSessionService.complete_session()                    │
│           ↓                                                   │
│  3. Collect Quiz Responses                                   │
│           ↓                                                   │
│  4. QuizResponseEvaluator.evaluate_quiz_session()            │
│           ↓                                                   │
│  5. Evaluate Against Alert Rules (16+ rules)                 │
│           ↓                                                   │
│  6. Generate Alerts for Triggered Rules                      │
│           ↓                                                   │
│  7. Calculate Risk Score (0-100)                             │
│           ↓                                                   │
│  8. Notify Medical Team                                      │
│           ↓                                                   │
│  9. Log Audit Trail                                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Key Files

#### Configuration
- **`app/config/quiz_alert_rules.py`**: Alert rule definitions (16 rules)

#### Services
- **`app/services/quiz_response_evaluator.py`**: Alert evaluation engine
- **`app/services/quiz.py`**: Quiz session management (updated)

#### Models
- **`app/models/alert.py`**: Alert model (updated with quiz_session_id)
- **`app/models/quiz.py`**: Quiz models (updated with alerts relationship)

#### API
- **`app/api/v1/quiz_alerts.py`**: Quiz alert endpoints

#### Migrations
- **`alembic/versions/20251009_225600_add_quiz_session_to_alerts.py`**: Database schema update

#### Tests
- **`tests/unit/services/test_quiz_response_evaluator.py`**: Unit tests
- **`tests/integration/test_quiz_alert_evaluation.py`**: Integration tests

## Alert Rules

### Critical Alerts (50 points each)

1. **Pain Score Critical** (`pain_score_critical`)
   - **Condition**: Pain scale ≥7/10
   - **Action**: Urgent medical intervention recommended
   - **Recommendation**: Immediate analgesia evaluation

2. **Fever with Chills** (`fever_with_chills`)
   - **Condition**: Fever AND chills present
   - **Action**: Possible neutropenic fever
   - **Recommendation**: Urgent medical assessment

3. **Severe Bleeding** (`severe_bleeding`)
   - **Condition**: Severe bleeding or hemorrhage reported
   - **Action**: Emergency evaluation required
   - **Recommendation**: Immediate emergency referral

4. **Multiple Severe Symptoms** (`multiple_severe_symptoms`)
   - **Condition**: ≥3 symptoms with severity ≥7/10
   - **Action**: Complex clinical condition
   - **Recommendation**: Comprehensive medical evaluation

5. **Respiratory Distress** (`respiratory_distress`)
   - **Condition**: Breathing difficulty ≥8/10 OR severe dyspnea
   - **Action**: Urgent respiratory assessment
   - **Recommendation**: Oxygen therapy consideration

### Warning Alerts (30 points each)

6. **Prolonged Nausea** (`prolonged_nausea`)
   - **Condition**: Nausea/vomiting ≥4 days
   - **Action**: Dehydration risk
   - **Recommendation**: Antiemetics and hydration assessment

7. **Significant Weight Loss** (`significant_weight_loss`)
   - **Condition**: Weight loss ≥5% in past month
   - **Action**: Nutritional concern
   - **Recommendation**: Nutritional assessment and support

8. **Severe Fatigue** (`severe_fatigue`)
   - **Condition**: Fatigue level ≥8/10 affecting daily activities
   - **Action**: Quality of life impact
   - **Recommendation**: Reversible causes evaluation

9. **Persistent Diarrhea** (`persistent_diarrhea`)
   - **Condition**: Diarrhea ≥3 days OR >5 episodes/day
   - **Action**: Dehydration and electrolyte imbalance risk
   - **Recommendation**: Hydration assessment and antidiarrheals

10. **Moderate Pain** (`moderate_pain`)
    - **Condition**: Pain scale 5-6/10
    - **Action**: Pain management review needed
    - **Recommendation**: Analgesic adjustment

11. **Oral Mucositis** (`oral_mucositis`)
    - **Condition**: Mucositis grade ≥2 OR difficulty eating
    - **Action**: Nutrition impact
    - **Recommendation**: Intensive oral care and nutrition evaluation

12. **Peripheral Neuropathy** (`peripheral_neuropathy`)
    - **Condition**: Neuropathy scale ≥6/10 OR severe tingling
    - **Action**: Treatment side effect
    - **Recommendation**: Chemotherapy dose evaluation

### Info Alerts (10 points each)

13. **Mild Symptoms** (`mild_symptoms`)
    - **Condition**: ≥2 symptoms with severity ≥3/10
    - **Action**: Monitoring recommended
    - **Recommendation**: Routine follow-up

14. **Appetite Changes** (`appetite_changes`)
    - **Condition**: Decreased appetite OR appetite change ≥3
    - **Action**: Nutritional monitoring
    - **Recommendation**: Nutritional guidance

15. **Sleep Disturbance** (`sleep_disturbance`)
    - **Condition**: Sleep problems OR sleep quality ≤3/10
    - **Action**: Quality of life concern
    - **Recommendation**: Sleep hygiene assessment

16. **Anxiety/Depression** (`anxiety_or_depression`)
    - **Condition**: Anxiety OR depression score ≥6/10
    - **Action**: Mental health concern
    - **Recommendation**: Psychological support consideration

## Risk Scoring Algorithm

### Calculation

```python
risk_score = min(
    sum(severity_weights[alert.severity] for alert in triggered_alerts),
    100.0
)

severity_weights = {
    CRITICAL: 50,
    HIGH: 30,      # WARNING mapped to HIGH
    MEDIUM: 10,    # INFO mapped to MEDIUM
    LOW: 5
}
```

### Examples

- **Single CRITICAL alert**: 50 points
- **CRITICAL + WARNING**: 50 + 30 = 80 points
- **3 CRITICAL alerts**: 150 → capped at 100 points
- **2 WARNING + 1 INFO**: 30 + 30 + 10 = 70 points

## Notification System

### Notification Channels

| Alert Severity | Dashboard | Email | SMS |
|---------------|-----------|-------|-----|
| CRITICAL      | ✅ Yes    | ✅ Yes | ✅ Yes (optional) |
| WARNING (HIGH)| ✅ Yes    | ✅ Yes | ❌ No |
| INFO (MEDIUM) | ✅ Yes    | ❌ No  | ❌ No |

### Implementation

```python
async def _notify_medical_team(alert: Alert, rule: QuizAlertRule):
    # Dashboard notification (always)
    await _send_dashboard_notification(alert, rule)

    # Email for CRITICAL and WARNING
    if alert.severity in (CRITICAL, HIGH):
        await _send_email_notification(alert, rule)

    # SMS for CRITICAL only
    if alert.severity == CRITICAL:
        await _send_sms_notification(alert, rule)
```

## API Endpoints

### Get Patient Quiz Alerts

```http
GET /api/v1/quiz-alerts/patient/{patient_id}?severity=CRITICAL&status=PENDING&skip=0&limit=50
```

**Response:**
```json
{
  "alerts": [
    {
      "id": "uuid",
      "patient_id": "uuid",
      "quiz_session_id": "uuid",
      "alert_type": "quiz_response",
      "severity": "critical",
      "description": "Paciente relatou dor intensa (nível 9/10)",
      "status": "pending",
      "data": {
        "triggered_rule_id": "pain_score_critical",
        "rule_name": "Dor Crítica",
        "recommendation": "Avaliar necessidade de analgesia imediata"
      },
      "created_at": "2025-10-09T22:00:00Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 50
}
```

### Get Quiz Session Alerts

```http
GET /api/v1/quiz-alerts/session/{session_id}
```

### Get Alert Summary

```http
GET /api/v1/quiz-alerts/summary/{patient_id}?days=30
```

**Response:**
```json
{
  "patient_id": "uuid",
  "total_quiz_alerts": 15,
  "by_severity": {
    "critical": 3,
    "high": 5,
    "medium": 7,
    "low": 0
  },
  "most_common_rules": [
    ["pain_score_critical", 3],
    ["prolonged_nausea", 2],
    ["severe_fatigue", 2]
  ],
  "acknowledgement_rate": 80.0
}
```

### Acknowledge Alert

```http
POST /api/v1/quiz-alerts/acknowledge/{alert_id}
```

### Get Critical Alerts

```http
GET /api/v1/quiz-alerts/critical?skip=0&limit=50
```

## Database Schema

### Alerts Table Updates

```sql
-- Add quiz_session_id foreign key
ALTER TABLE alerts ADD COLUMN quiz_session_id UUID REFERENCES quiz_sessions(id) ON DELETE SET NULL;

-- Add indexes for performance
CREATE INDEX idx_alerts_quiz_session_id ON alerts(quiz_session_id);
CREATE INDEX idx_alerts_patient_quiz_session ON alerts(patient_id, quiz_session_id);
```

### Data Structure

```python
class Alert:
    patient_id: UUID                # Patient reference
    quiz_session_id: UUID           # Quiz session reference (NEW)
    alert_type: str                 # 'quiz_response'
    severity: AlertSeverity         # CRITICAL, HIGH, MEDIUM, LOW
    description: str                # Human-readable message
    status: AlertStatus             # PENDING, ACKNOWLEDGED, RESOLVED
    data: dict = {
        "quiz_session_id": str,
        "triggered_rule_id": str,
        "rule_name": str,
        "rule_description": str,
        "recommendation": str,
        "relevant_responses": dict,
        "evaluated_at": str
    }
```

## Usage Examples

### Example 1: High Pain Score

**Quiz Responses:**
```json
{
  "pain_scale": 9,
  "nausea_days": 1
}
```

**Generated Alerts:**
- **CRITICAL**: "Paciente relatou dor intensa (nível 9/10)"
- **Risk Score**: 50

### Example 2: Multiple Severe Symptoms

**Quiz Responses:**
```json
{
  "pain_scale": 8,
  "fatigue_scale": 9,
  "nausea_scale": 7
}
```

**Generated Alerts:**
- **CRITICAL**: "Dor intensa (nível 8/10)"
- **CRITICAL**: "Múltiplos sintomas severos detectados"
- **Risk Score**: 100 (capped)

### Example 3: Fever with Chills

**Quiz Responses:**
```json
{
  "has_fever": true,
  "has_chills": true
}
```

**Generated Alerts:**
- **CRITICAL**: "Febre com calafrios relatados. Possível neutropenia febril."
- **Risk Score**: 50

## Testing

### Unit Tests

```bash
# Run quiz response evaluator tests
pytest backend-hormonia/tests/unit/services/test_quiz_response_evaluator.py -v

# Test alert rules
pytest backend-hormonia/tests/unit/services/test_quiz_response_evaluator.py::TestAlertRules -v
```

### Integration Tests

```bash
# Run end-to-end alert evaluation tests
pytest backend-hormonia/tests/integration/test_quiz_alert_evaluation.py -v
```

### Test Coverage

- ✅ 16 alert rules tested
- ✅ Response normalization (strings, booleans, nested values)
- ✅ Risk score calculation
- ✅ Alert severity mapping
- ✅ End-to-end quiz completion flow
- ✅ Database integration
- ✅ Error handling

## Deployment

### 1. Run Database Migration

```bash
cd backend-hormonia
alembic upgrade head
```

### 2. Verify Migration

```sql
-- Check if quiz_session_id column exists
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'alerts'
AND column_name = 'quiz_session_id';
```

### 3. Test Alert Evaluation

```bash
# Run integration tests
pytest tests/integration/test_quiz_alert_evaluation.py -v

# Check logs for evaluation messages
tail -f logs/app.log | grep "Quiz evaluation"
```

## Monitoring

### Key Metrics

- **Alert Generation Rate**: Alerts generated per quiz completion
- **Severity Distribution**: CRITICAL vs WARNING vs INFO
- **Acknowledgement Time**: Time to acknowledge alerts
- **Risk Score Distribution**: Distribution of risk scores

### Logging

```python
logger.info(
    f"Quiz session {session_id} evaluation: "
    f"{len(triggered_alerts)} alerts, risk score: {risk_score:.2f}"
)

logger.warning(
    f"Alert rule '{rule.rule_id}' triggered for patient {patient_id} "
    f"(severity: {rule.severity.value})"
)
```

## Security

### Authorization

- **Médico**: Can view and acknowledge alerts for their patients
- **Admin**: Can view and acknowledge all alerts
- **Patient**: No direct access to alert endpoints

### Rate Limiting

- **Patient Alerts**: 100 requests/minute
- **Alert Summary**: 50 requests/minute
- **Acknowledge**: 100 requests/minute

## Performance Considerations

### Database Indexes

```sql
-- Existing indexes
idx_alerts_patient_id
idx_alerts_severity
idx_alerts_status

-- New indexes for quiz alerts
idx_alerts_quiz_session_id
idx_alerts_patient_quiz_session
idx_alerts_type_created
```

### Optimization

- Eager loading of relationships to prevent N+1 queries
- Batch alert creation for multiple triggered rules
- Async notification to avoid blocking quiz completion
- Graceful error handling to prevent evaluation failures

## Future Enhancements

1. **Machine Learning**: Predictive risk scoring based on historical data
2. **Custom Rules**: Allow medical staff to define custom alert rules
3. **Alert Aggregation**: Group similar alerts to reduce noise
4. **Trend Analysis**: Alert patterns over time
5. **WhatsApp Integration**: Send critical alerts via WhatsApp
6. **Voice Calls**: Automated voice calls for CRITICAL alerts
7. **Escalation**: Automatic escalation of unacknowledged critical alerts

## Success Criteria

- ✅ **16 alert rules** implemented (CRITICAL: 5, WARNING: 7, INFO: 4)
- ✅ **Automatic alert generation** on quiz completion
- ✅ **Risk scoring** (0-100 scale)
- ✅ **Multi-channel notifications** (Dashboard, Email, SMS)
- ✅ **Comprehensive testing** (unit + integration)
- ✅ **API endpoints** for alert management
- ✅ **Database migration** completed
- ✅ **Documentation** complete

## Support

- **Technical Issues**: Check logs in `logs/app.log`
- **Rule Configuration**: See `app/config/quiz_alert_rules.py`
- **API Documentation**: Swagger UI at `/docs`
- **Database Issues**: Review migration in `alembic/versions/`

---

**Sprint 2 - Week 1, Task 3 Complete**
Generated: 2025-10-09
```
