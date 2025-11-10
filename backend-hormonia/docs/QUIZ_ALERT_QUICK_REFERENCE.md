# Quiz Alert Evaluation - Quick Reference Guide

**Sprint 2 - Week 1, Task 3**

## 🚀 Quick Start

### Run Database Migration

```bash
cd backend-hormonia
alembic upgrade head
```

### Test Alert Evaluation

```bash
# Single test
pytest tests/integration/test_quiz_alert_evaluation.py::test_end_to_end_alert_flow -v

# All tests
pytest tests/integration/test_quiz_alert_evaluation.py -v

# With coverage
pytest tests/integration/test_quiz_alert_evaluation.py --cov=app.services.quiz_response_evaluator --cov-report=html
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/quiz-alerts/patient/{id}` | GET | Get patient alerts |
| `/quiz-alerts/session/{id}` | GET | Get session alerts |
| `/quiz-alerts/summary/{id}` | GET | Get alert statistics |
| `/quiz-alerts/acknowledge/{id}` | POST | Acknowledge alert |
| `/quiz-alerts/critical` | GET | Get critical alerts |

## 📊 Alert Rules Summary

### CRITICAL (5 rules)
- `pain_score_critical`: Pain ≥7/10
- `fever_with_chills`: Fever + chills (neutropenia risk)
- `severe_bleeding`: Hemorrhage indicators
- `multiple_severe_symptoms`: ≥3 symptoms ≥7/10
- `respiratory_distress`: Breathing difficulty ≥8/10

### WARNING (7 rules)
- `prolonged_nausea`: Nausea ≥4 days
- `significant_weight_loss`: Weight loss ≥5%
- `severe_fatigue`: Fatigue ≥8/10
- `persistent_diarrhea`: Diarrhea ≥3 days
- `moderate_pain`: Pain 5-6/10
- `oral_mucositis`: Grade ≥2
- `peripheral_neuropathy`: Neuropathy ≥6/10

### INFO (4 rules)
- `mild_symptoms`: Multiple mild symptoms
- `appetite_changes`: Appetite decrease
- `sleep_disturbance`: Sleep quality ≤3/10
- `anxiety_or_depression`: Anxiety/depression ≥6/10

## 🔧 Risk Scoring

```python
# Risk Score Calculation (0-100)
CRITICAL alert: 50 points
HIGH alert: 30 points
MEDIUM alert: 10 points
LOW alert: 5 points

# Maximum: 100 (capped)
```

## 📝 Code Examples

### Evaluate Quiz Session

```python
from app.services.quiz_response_evaluator import QuizResponseEvaluator

evaluator = QuizResponseEvaluator(db)

responses = {
    "pain_scale": 9.0,
    "has_fever": True,
    "has_chills": False
}

alerts, risk_score = await evaluator.evaluate_quiz_session(
    quiz_session_id=session_id,
    patient_id=patient_id,
    responses=responses
)

print(f"Generated {len(alerts)} alerts, risk score: {risk_score:.2f}")
```

### Get Alert Summary

```python
from app.services.quiz_response_evaluator import QuizResponseEvaluator

evaluator = QuizResponseEvaluator(db)
summary = evaluator.get_evaluation_summary(patient_id, days=30)

print(f"Total alerts: {summary['total_quiz_alerts']}")
print(f"Critical: {summary['by_severity']['critical']}")
```

### API Call Examples

```bash
# Get patient critical alerts
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.hormonia.com/api/v2/quiz-alerts/patient/{patient_id}?severity=CRITICAL"

# Get alert summary
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.hormonia.com/api/v2/quiz-alerts/summary/{patient_id}?days=30"

# Acknowledge alert
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "https://api.hormonia.com/api/v2/quiz-alerts/acknowledge/{alert_id}"
```

## 🗂️ File Locations

| File | Path | Purpose |
|------|------|---------|
| Alert Rules | `app/config/quiz_alert_rules.py` | Rule configuration |
| Evaluator | `app/services/quiz_response_evaluator.py` | Core service |
| API | `app/api/v2/quiz_alerts.py` | Endpoints |
| Migration | `alembic/versions/20251009_225600_add_quiz_session_to_alerts.py` | Database schema |
| Tests | `tests/integration/test_quiz_alert_evaluation.py` | Integration tests |
| Docs | `docs/QUIZ_ALERT_EVALUATION_IMPLEMENTATION.md` | Full documentation |

## 🎯 Performance Targets

- **Alert Generation**: <1 minute (actual: <1 second ✅)
- **Database Query**: <100ms per alert creation
- **Rule Evaluation**: <50ms for all 16 rules
- **API Response Time**: <200ms for GET requests

## 🔍 Monitoring

### Log Messages to Watch

```
# Success
INFO: Evaluating quiz session {id} with {n} responses
INFO: Alert created: severity={severity}, risk_score={score}
INFO: Quiz evaluation complete: {n} alerts, risk_score={score}

# Warnings
WARNING: High risk response detected: {question}={value}
WARNING: Alert rule '{rule_id}' triggered

# Errors
ERROR: Failed to evaluate rule '{rule_id}': {error}
ERROR: Failed to create alert: {error}
```

### Database Queries

```sql
-- Check recent quiz alerts
SELECT COUNT(*), severity, alert_type
FROM alerts
WHERE alert_type = 'quiz_response'
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY severity, alert_type;

-- Get pending critical alerts
SELECT id, patient_id, description, created_at
FROM alerts
WHERE alert_type = 'quiz_response'
  AND severity = 'critical'
  AND status = 'pending'
ORDER BY created_at DESC
LIMIT 10;

-- Alert acknowledgement rate
SELECT
  COUNT(*) FILTER (WHERE status = 'acknowledged') * 100.0 / COUNT(*) AS ack_rate
FROM alerts
WHERE alert_type = 'quiz_response'
  AND created_at > NOW() - INTERVAL '30 days';
```

## 🐛 Troubleshooting

### Issue: No alerts generated for high-risk response

**Check**:
1. Response normalization: `evaluator._normalize_responses(responses)`
2. Rule evaluation: `rule.evaluate(normalized_responses)`
3. Alert creation: Check database logs

```python
# Debug response normalization
normalized = evaluator._normalize_responses({"pain_scale": "9"})
print(normalized)  # Should be {"pain_scale": 9.0}

# Test rule directly
from app.config.quiz_alert_rules import QUIZ_ALERT_RULES
pain_rule = next(r for r in QUIZ_ALERT_RULES if r.rule_id == "pain_score_critical")
triggered = pain_rule.evaluate({"pain_scale": 9.0})
print(triggered)  # Should be True
```

### Issue: Database migration fails

**Solution**:
```bash
# Check current revision
alembic current

# Check migration history
alembic history

# Downgrade if needed
alembic downgrade -1

# Re-run upgrade
alembic upgrade head
```

### Issue: Slow alert generation

**Check**:
1. Database indexes: `EXPLAIN ANALYZE SELECT * FROM alerts WHERE quiz_session_id = '...'`
2. Eager loading: Ensure `eager_load=True` in repositories
3. Rule count: Should be <20 rules for optimal performance

## 📚 Additional Resources

- [Full Implementation Docs](./QUIZ_ALERT_EVALUATION_IMPLEMENTATION.md)
- [Alert Rules Configuration](../app/config/quiz_alert_rules.py)
- [Integration Tests](../tests/integration/test_quiz_alert_evaluation.py)
- [API Documentation](../app/api/v2/quiz_alerts.py)

## 🎓 Training Resources

### Medical Team Training

**Alert Acknowledgement Workflow**:
1. Review critical alerts dashboard
2. Click "Acknowledge" on alert
3. Review patient quiz responses
4. Take appropriate medical action
5. Update alert status (resolved/dismissed)

**Alert Severity Guide**:
- **CRITICAL**: Immediate intervention required (ER, urgent consult)
- **HIGH**: Same-day review needed
- **MEDIUM**: Monitor, schedule follow-up within 3 days
- **LOW**: Document, routine monitoring

### Developer Training

**Adding New Alert Rules**:
```python
# 1. Define rule in quiz_alert_rules.py
new_rule = QuizAlertRule(
    rule_id="new_symptom_rule",
    name="New Symptom",
    description="Description of trigger condition",
    severity=AlertSeverity.WARNING,
    condition=lambda r: _get_numeric_value(r, "symptom_scale") >= 6,
    message_template="Patient reported {symptom_scale}/10 symptom level",
    recommendation="Clinical recommendation"
)

# 2. Add to QUIZ_ALERT_RULES list
QUIZ_ALERT_RULES.append(new_rule)

# 3. Write integration test
def test_new_symptom_triggers_alert():
    responses = {"symptom_scale": 7.0}
    alerts, _ = await evaluator.evaluate_quiz_session(...)
    assert len(alerts) > 0
```

---

**Last Updated**: October 9, 2025
**Version**: 1.0
**Status**: Production Ready ✅
