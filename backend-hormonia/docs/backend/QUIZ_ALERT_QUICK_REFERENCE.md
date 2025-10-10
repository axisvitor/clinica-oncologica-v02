# Quiz Alert Evaluation - Quick Reference

**Sprint 2 - Week 1, Task 3**

## Quick Start

### 1. Run Database Migration

```bash
cd backend-hormonia
alembic upgrade head
```

### 2. Test Alert Evaluation

```python
from app.services.quiz_response_evaluator import QuizResponseEvaluator
from uuid import uuid4

# Initialize evaluator
evaluator = QuizResponseEvaluator(db)

# Evaluate quiz session
alerts, risk_score = await evaluator.evaluate_quiz_session(
    quiz_session_id=uuid4(),
    patient_id=uuid4(),
    responses={
        "pain_scale": 9,
        "nausea_days": 5,
        "has_fever": True
    }
)

print(f"Generated {len(alerts)} alerts with risk score: {risk_score}")
```

## Alert Rules Cheat Sheet

### CRITICAL (50 points)

| Rule ID | Trigger | Recommendation |
|---------|---------|----------------|
| `pain_score_critical` | Pain ≥7/10 | Immediate analgesia |
| `fever_with_chills` | Fever + chills | Urgent evaluation (neutropenia) |
| `severe_bleeding` | Severe bleeding | Emergency referral |
| `multiple_severe_symptoms` | ≥3 symptoms ≥7/10 | Comprehensive evaluation |
| `respiratory_distress` | Breathing difficulty ≥8/10 | Oxygen therapy |

### WARNING (30 points)

| Rule ID | Trigger | Recommendation |
|---------|---------|----------------|
| `prolonged_nausea` | Nausea ≥4 days | Antiemetics + hydration |
| `significant_weight_loss` | Weight loss ≥5% | Nutritional support |
| `severe_fatigue` | Fatigue ≥8/10 | Evaluate causes |
| `persistent_diarrhea` | Diarrhea ≥3 days or >5/day | Hydration assessment |
| `moderate_pain` | Pain 5-6/10 | Adjust analgesia |
| `oral_mucositis` | Mucositis ≥grade 2 | Oral care + nutrition |
| `peripheral_neuropathy` | Neuropathy ≥6/10 | Review chemo dose |

### INFO (10 points)

| Rule ID | Trigger | Recommendation |
|---------|---------|----------------|
| `mild_symptoms` | ≥2 symptoms ≥3/10 | Routine follow-up |
| `appetite_changes` | Decreased appetite | Nutritional guidance |
| `sleep_disturbance` | Sleep problems | Sleep hygiene |
| `anxiety_or_depression` | Anxiety/depression ≥6/10 | Psychological support |

## API Endpoints

### Get Patient Alerts

```bash
curl -X GET "https://api.example.com/api/v1/quiz-alerts/patient/{patient_id}?severity=CRITICAL" \
  -H "Authorization: Bearer {token}"
```

### Acknowledge Alert

```bash
curl -X POST "https://api.example.com/api/v1/quiz-alerts/acknowledge/{alert_id}" \
  -H "Authorization: Bearer {token}"
```

### Get Alert Summary

```bash
curl -X GET "https://api.example.com/api/v1/quiz-alerts/summary/{patient_id}?days=30" \
  -H "Authorization: Bearer {token}"
```

## Risk Score Examples

| Alerts | Calculation | Risk Score |
|--------|-------------|------------|
| 1 CRITICAL | 50 | 50 |
| 1 CRITICAL + 1 WARNING | 50 + 30 | 80 |
| 2 WARNING + 1 INFO | 30 + 30 + 10 | 70 |
| 3 CRITICAL | 50 + 50 + 50 | 100 (capped) |

## Common Response Keys

```python
# Pain and symptoms
pain_scale: 0-10
pain_level: 0-10
fatigue_scale: 0-10
fatigue_level: 0-10
nausea_scale: 0-10

# Duration
nausea_days: integer
vomiting_days: integer
diarrhea_days: integer

# Boolean flags
has_fever: boolean
has_chills: boolean
severe_bleeding: boolean
severe_dyspnea: boolean

# Numeric values
weight_loss_percent: float
breathing_difficulty: 0-10
diarrhea_episodes_per_day: integer
mucositis_grade: 0-4
```

## Testing

```bash
# Unit tests
pytest backend-hormonia/tests/unit/services/test_quiz_response_evaluator.py -v

# Integration tests
pytest backend-hormonia/tests/integration/test_quiz_alert_evaluation.py -v

# Specific rule test
pytest backend-hormonia/tests -k "test_pain_rule_conditions" -v
```

## Troubleshooting

### No alerts generated

1. Check response normalization:
```python
normalized = evaluator._normalize_responses(responses)
print(normalized)
```

2. Verify rule conditions:
```python
for rule in QUIZ_ALERT_RULES:
    if rule.evaluate(responses):
        print(f"Rule {rule.rule_id} triggered")
```

### Alert not appearing in API

1. Check database:
```sql
SELECT * FROM alerts
WHERE quiz_session_id = '{session_id}'
ORDER BY created_at DESC;
```

2. Check alert type:
```sql
SELECT alert_type, COUNT(*)
FROM alerts
GROUP BY alert_type;
```

## File Locations

| Component | Path |
|-----------|------|
| Alert Rules | `app/config/quiz_alert_rules.py` |
| Evaluator | `app/services/quiz_response_evaluator.py` |
| API Endpoints | `app/api/v1/quiz_alerts.py` |
| Models | `app/models/alert.py`, `app/models/quiz.py` |
| Migration | `alembic/versions/20251009_225600_*.py` |
| Tests | `tests/unit/services/test_quiz_response_evaluator.py` |
| Documentation | `docs/backend/QUIZ_ALERT_EVALUATION_SYSTEM.md` |

## Support

- **Logs**: `tail -f logs/app.log | grep "Quiz evaluation"`
- **Database**: Check `alerts` table with `quiz_session_id` not null
- **API Docs**: https://api.example.com/docs#/Quiz%20Alerts

---

**Last Updated**: 2025-10-09
