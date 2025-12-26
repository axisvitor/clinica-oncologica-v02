# Alert Evaluation & Follow-up Integration

## Overview
Quiz completion triggers automatic alert evaluation using **configurable alert rules**. Alerts can trigger immediate medical interventions, follow-up flows, and multi-channel notifications.

---

## Alert Evaluation Pipeline

### Trigger Point
```
Quiz Completion
  ↓
_complete_quiz_session()
  ├─ Mark session as completed
  ├─ Schedule report generation (Celery task)
  └─ Update flow state
  ↓
generate_quiz_report_task (async)
  ├─ Get quiz session + responses
  ├─ QuizResponseEvaluator.evaluate_quiz_session()
  └─ Notify healthcare providers
```

---

## QuizResponseEvaluator Architecture

### Initialization
```python
class QuizResponseEvaluator:
    def __init__(self, db: Session):
        self.db = db
        self.alert_repository = AlertRepository(db)
        self.audit_service = AuditService(db)
```

### Main Evaluation Method
```python
async def evaluate_quiz_session(
    quiz_session_id: UUID,
    patient_id: UUID,
    responses: Dict[str, Any]
) -> Tuple[List[Alert], float]:
    """
    Evaluate quiz responses against alert rules.

    Returns:
        (triggered_alerts, overall_risk_score)
    """
```

---

## Alert Rules Configuration

### Rule Structure
```python
# config/quiz_alert_rules.py

class QuizAlertRule:
    rule_id: str
    name: str
    description: str
    severity: AlertSeverity  # CRITICAL, WARNING, INFO
    condition: Callable[[Dict], bool]
    recommendation: str

    def evaluate(self, responses: Dict) -> bool:
        """Check if rule condition is met"""
        return self.condition(responses)

    def generate_message(self, responses: Dict) -> str:
        """Generate alert description"""
        return self.description
```

### Example Rules
```python
QUIZ_ALERT_RULES = [
    QuizAlertRule(
        rule_id="severe_mood_deterioration",
        name="Severe Mood Deterioration",
        description="Patient reported severe mood decline",
        severity=AlertSeverity.CRITICAL,
        condition=lambda r: (
            r.get("mood_assessment", 5) <= 2 and
            r.get("overall_satisfaction", 5) <= 2
        ),
        recommendation=(
            "Immediate psychological consultation recommended. "
            "Contact patient within 24h to assess mental health status."
        )
    ),

    QuizAlertRule(
        rule_id="severe_side_effects",
        name="Severe Treatment Side Effects",
        description="Patient experiencing severe side effects",
        severity=AlertSeverity.CRITICAL,
        condition=lambda r: (
            r.get("energy_levels") == "very_low" and
            r.get("sleep_quality", 5) <= 2 and
            "severe" in str(r.get("side_effects", "")).lower()
        ),
        recommendation=(
            "Review treatment plan immediately. "
            "Consider dose adjustment or alternative therapy."
        )
    ),

    QuizAlertRule(
        rule_id="declining_sleep_quality",
        name="Declining Sleep Quality",
        description="Persistent sleep quality issues detected",
        severity=AlertSeverity.WARNING,
        condition=lambda r: r.get("sleep_quality", 5) <= 2,
        recommendation=(
            "Monitor sleep patterns. "
            "Consider sleep hygiene counseling or medication review."
        )
    ),

    QuizAlertRule(
        rule_id="energy_depletion",
        name="Severe Energy Depletion",
        description="Patient reporting very low energy levels",
        severity=AlertSeverity.WARNING,
        condition=lambda r: r.get("energy_levels") in ["very_low", "low"],
        recommendation=(
            "Assess for anemia or nutritional deficiencies. "
            "Consider referral to nutritionist."
        )
    ),

    QuizAlertRule(
        rule_id="positive_progress",
        name="Positive Treatment Progress",
        description="Patient showing positive indicators",
        severity=AlertSeverity.INFO,
        condition=lambda r: (
            r.get("mood_assessment", 0) >= 4 and
            r.get("overall_satisfaction", 0) >= 4 and
            r.get("sleep_quality", 0) >= 4
        ),
        recommendation=(
            "Continue current treatment plan. "
            "Provide positive reinforcement to patient."
        )
    )
]
```

---

## Evaluation Process

### Step 1: Response Normalization
```python
def _normalize_responses(responses: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize response values for consistent evaluation.

    Handles:
    - Nested structures (extract "value" field)
    - String numbers → float
    - Boolean strings → bool
    """
    normalized = {}

    for key, value in responses.items():
        # Extract nested values
        if isinstance(value, dict):
            value = value.get("value", value.get("response_value", value))

        # Convert string numbers
        if isinstance(value, str) and value.replace(".", "", 1).isdigit():
            value = float(value)

        # Normalize booleans
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in ("yes", "sim", "true", "1", "y", "s"):
                value = True
            elif value_lower in ("no", "não", "nao", "false", "0", "n"):
                value = False

        normalized[key] = value

    return normalized
```

**Example Normalization**:
```python
Input:
{
    "mood_assessment": {"value": "2", "interpreted": True},
    "energy_levels": "very_low",
    "sleep_quality": "3",
    "side_effects": {"value": "Nausea and fatigue", "type": "text"}
}

Output:
{
    "mood_assessment": 2.0,
    "energy_levels": "very_low",
    "sleep_quality": 3.0,
    "side_effects": "Nausea and fatigue"
}
```

---

### Step 2: Rule Evaluation
```python
triggered_alerts = []

for rule in QUIZ_ALERT_RULES:
    try:
        if rule.evaluate(normalized_responses):
            # Rule triggered
            alert = await _create_alert(
                quiz_session_id=quiz_session_id,
                patient_id=patient_id,
                rule=rule,
                responses=normalized_responses
            )

            triggered_alerts.append(alert)

    except Exception as e:
        logger.error(f"Error evaluating rule '{rule.rule_id}': {e}")
        # Continue with other rules
```

---

### Step 3: Alert Creation
```python
async def _create_alert(
    quiz_session_id: UUID,
    patient_id: UUID,
    rule: QuizAlertRule,
    responses: Dict[str, Any]
) -> Alert:
    """Create alert from triggered rule"""

    # Map severity from config to model
    model_severity = SEVERITY_MAP.get(rule.severity, AlertSeverity.MEDIUM)

    # Create alert
    alert = Alert(
        patient_id=patient_id,
        alert_type="quiz_response",
        severity=model_severity,
        description=rule.generate_message(responses),
        status=AlertStatus.PENDING,
        data={
            "quiz_session_id": str(quiz_session_id),
            "triggered_rule_id": rule.rule_id,
            "rule_name": rule.name,
            "rule_description": rule.description,
            "recommendation": rule.recommendation,
            "relevant_responses": _extract_relevant_responses(responses, rule),
            "evaluated_at": datetime.now(timezone.utc).isoformat()
        }
    )

    # Save to database
    created_alert = alert_repository.create(alert)
    db.commit()

    # Trigger notifications asynchronously
    await _notify_medical_team(created_alert, rule)

    return created_alert
```

---

### Step 4: Risk Score Calculation
```python
def _calculate_risk_score(alerts: List[Alert]) -> float:
    """
    Calculate overall risk score (0-100) based on triggered alerts.

    Scoring:
    - CRITICAL: 50 points each
    - HIGH:     30 points each
    - MEDIUM:   10 points each
    - LOW:       5 points each
    - Capped at 100
    """
    severity_weights = {
        AlertSeverity.CRITICAL: 50,
        AlertSeverity.HIGH: 30,
        AlertSeverity.MEDIUM: 10,
        AlertSeverity.LOW: 5
    }

    total_score = sum(
        severity_weights.get(alert.severity, 0)
        for alert in alerts
    )

    return min(float(total_score), 100.0)
```

**Risk Score Examples**:
```
1 CRITICAL alert              → 50/100 (High Risk)
1 CRITICAL + 1 HIGH           → 80/100 (Very High Risk)
2 HIGH + 1 MEDIUM             → 70/100 (High Risk)
3 MEDIUM                      → 30/100 (Moderate Risk)
1 INFO                        → 10/100 (Low Risk)
No alerts                     → 0/100  (No Risk)
```

---

## Multi-Channel Notification System

### Notification Decision Tree
```
Alert Created
  ↓
┌─────────────────────────────────────┐
│  Notification Channel Selection     │
└─────────────────────────────────────┘
  │
  ├─ Dashboard (Always)
  │   └─ WebSocket broadcast to medical team
  │
  ├─ Email (HIGH + CRITICAL only)
  │   ├─ To: Assigned physician
  │   └─ CC: Admin (if CRITICAL)
  │
  └─ WhatsApp (CRITICAL only)
      ├─ To: Assigned physician
      └─ CC: On-call phone
```

### 1. Dashboard Notification (WebSocket)
```python
async def _send_dashboard_notification(alert: Alert, rule: QuizAlertRule):
    """Send real-time notification to dashboard"""

    notification_payload = {
        "type": "alert_notification",
        "alert_id": str(alert.id),
        "patient_id": str(alert.patient_id),
        "severity": alert.severity.value,
        "title": f"Alerta: {rule.name}",
        "message": alert.description,
        "rule_id": rule.rule_id,
        "recommendation": rule.recommendation,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requires_action": alert.severity in [
            AlertSeverity.CRITICAL,
            AlertSeverity.HIGH
        ]
    }

    connection_manager = get_connection_manager()

    # Broadcast to alerts room (all subscribed medical staff)
    await connection_manager.broadcast_to_room(
        room="alerts",
        message=notification_payload
    )

    # Send to patient-specific room (assigned doctor)
    await connection_manager.broadcast_to_room(
        room=f"patient_{alert.patient_id}",
        message=notification_payload
    )
```

---

### 2. Email Notification (HIGH/CRITICAL)
```python
async def _send_email_notification(alert: Alert, rule: QuizAlertRule):
    """Send email to assigned physician"""

    # Get patient and doctor info
    patient = patient_repo.get(alert.patient_id)
    patient_name = patient.name if patient else "Paciente"
    doctor_email = patient.assigned_doctor.email if patient.assigned_doctor else None

    # Build email content
    severity_label = {
        AlertSeverity.CRITICAL: "CRÍTICO",
        AlertSeverity.HIGH: "ALTO"
    }[alert.severity]

    subject = f"[{severity_label}] Alerta de Saúde - {patient_name}"

    message = f"""
Alerta de Avaliação de Quiz

Paciente: {patient_name}
Severidade: {severity_label}
Regra Acionada: {rule.name}

Descrição:
{alert.description}

Recomendação:
{rule.recommendation}

---
Este alerta foi gerado automaticamente pelo sistema de avaliação de respostas.
Por favor, revise o caso e tome as medidas apropriadas.

Data/Hora: {datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")}
ID do Alerta: {alert.id}
    """

    # Get recipients
    recipients = [doctor_email] if doctor_email else []

    # Add admin for CRITICAL
    if alert.severity == AlertSeverity.CRITICAL:
        admin_email = settings.ADMIN_ALERT_EMAIL
        if admin_email and admin_email not in recipients:
            recipients.append(admin_email)

    # Send notification
    if recipients:
        await notification_service.send_notification(
            channels=[NotificationChannel.EMAIL],
            subject=subject,
            message=message,
            recipients=recipients,
            priority=NotificationPriority.CRITICAL
                if alert.severity == AlertSeverity.CRITICAL
                else NotificationPriority.HIGH
        )
```

---

### 3. WhatsApp Notification (CRITICAL only)
```python
async def _send_whatsapp_notification(alert: Alert, rule: QuizAlertRule):
    """Send WhatsApp for critical alerts"""

    # Get patient and doctor info
    patient = patient_repo.get(alert.patient_id)
    patient_name = patient.name if patient else "Paciente"
    doctor_phone = patient.assigned_doctor.phone if patient.assigned_doctor else None

    # Build concise message for mobile
    message = f"""
🔴 *ALERTA CRÍTICO* 🔴

*Paciente:* {patient_name}
*Tipo:* {rule.name}

{alert.description[:200]}...

*Ação:* {rule.recommendation[:150]}

⚠️ Acesse o sistema para mais detalhes.
    """.strip()

    # Get recipients
    recipients = [doctor_phone] if doctor_phone else []

    # Add on-call phone
    oncall_phone = settings.ONCALL_WHATSAPP
    if oncall_phone and oncall_phone not in recipients:
        recipients.append(oncall_phone)

    # Send notification
    if recipients:
        await notification_service.send_notification(
            channels=[NotificationChannel.WHATSAPP],
            subject=f"Alerta Crítico - {patient_name}",
            message=message,
            recipients=recipients,
            priority=NotificationPriority.CRITICAL
        )
```

---

## Follow-up Flow Integration

### Alert-Triggered Follow-ups
```python
# After alert creation, check if follow-up flow should be triggered

if alert.severity == AlertSeverity.CRITICAL:
    # Trigger urgent intervention flow
    await _trigger_intervention_flow(
        patient_id=alert.patient_id,
        alert_id=alert.id,
        reason="critical_quiz_alert"
    )
```

### Intervention Flow Trigger
```python
async def _trigger_intervention_flow(
    patient_id: UUID,
    alert_id: UUID,
    reason: str
):
    """Trigger immediate intervention flow"""

    from app.services.flow.core import FlowEngineService

    flow_engine = FlowEngineService(db)

    # Create intervention flow state
    intervention_flow = await flow_engine.create_flow_state(
        patient_id=patient_id,
        flow_type="urgent_intervention",
        metadata={
            "triggered_by": "quiz_alert",
            "alert_id": str(alert_id),
            "trigger_reason": reason,
            "priority": "critical"
        }
    )

    # Send immediate message to patient
    await _send_intervention_message(patient_id, alert_id)

    # Notify care team
    await _notify_care_team_intervention(patient_id, alert_id)
```

### Intervention Message
```python
async def _send_intervention_message(patient_id: UUID, alert_id: UUID):
    """Send immediate check-in message to patient"""

    patient = patient_repo.get(patient_id)

    message_content = f"""
Olá {patient.name},

Notamos nas suas respostas recentes alguns sinais que nos preocupam
e gostaríamos de verificar como você está.

Um membro da nossa equipe médica entrará em contato com você nas
próximas 24 horas para uma conversa.

Se precisar de atenção imediata, por favor entre em contato:
📞 Telefone de emergência: {settings.EMERGENCY_PHONE}

Estamos aqui para você! 💙
    """

    message = message_factory.create_urgent_message(
        patient_id=patient_id,
        content=message_content,
        metadata={
            "alert_id": str(alert_id),
            "message_type": "intervention_notification"
        }
    )

    await message_sender.send_message(message)
```

---

## Audit & Tracking

### Evaluation Audit Log
```python
# After evaluation
await audit_service.log_action(
    user_id=None,  # System-generated
    action="quiz_response_evaluation",
    resource_type="quiz_session",
    resource_id=str(quiz_session_id),
    details={
        "patient_id": str(patient_id),
        "alerts_generated": len(triggered_alerts),
        "risk_score": risk_score,
        "triggered_rule_ids": [
            a.data.get("triggered_rule_id")
            for a in triggered_alerts
        ]
    }
)
```

### Alert Acknowledgment Tracking
```python
# When medical team acknowledges alert
def acknowledge_alert(alert_id: UUID, user_id: UUID):
    alert = alert_repository.get(alert_id)

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by = user_id
    alert.acknowledged_at = datetime.now(timezone.utc)

    db.commit()

    # Log acknowledgment
    audit_service.log_action(
        user_id=user_id,
        action="alert_acknowledged",
        resource_type="alert",
        resource_id=str(alert_id)
    )
```

---

## Performance Metrics

### Evaluation Summary
```python
def get_evaluation_summary(patient_id: UUID, days: int = 30) -> Dict:
    """Get evaluation statistics for patient"""

    alerts = alert_repository.get_by_patient(patient_id, limit=1000)
    quiz_alerts = [a for a in alerts if a.alert_type == "quiz_response"]

    return {
        "patient_id": str(patient_id),
        "total_quiz_alerts": len(quiz_alerts),
        "by_severity": {
            "critical": len([a for a in quiz_alerts if a.severity == AlertSeverity.CRITICAL]),
            "high": len([a for a in quiz_alerts if a.severity == AlertSeverity.HIGH]),
            "medium": len([a for a in quiz_alerts if a.severity == AlertSeverity.MEDIUM]),
            "low": len([a for a in quiz_alerts if a.severity == AlertSeverity.LOW])
        },
        "most_common_rules": _get_most_triggered_rules(quiz_alerts),
        "acknowledgement_rate": _calculate_acknowledgement_rate(quiz_alerts),
        "avg_response_time": _calculate_avg_response_time(quiz_alerts)
    }
```

---

## Integration with Patient Monitor Agent

### Agent Notification
```python
# After quiz completion and alert evaluation
if triggered_alerts:
    # Notify PatientMonitorAgent
    await send_agent_message(
        agent_id="patient_monitor_agent",
        message_type="quiz_alerts_generated",
        payload={
            "patient_id": str(patient_id),
            "session_id": str(quiz_session_id),
            "alerts": [
                {
                    "id": str(alert.id),
                    "severity": alert.severity.value,
                    "rule_id": alert.data.get("triggered_rule_id"),
                    "recommendation": alert.data.get("recommendation")
                }
                for alert in triggered_alerts
            ],
            "risk_score": risk_score
        }
    )
```

---

## Next: Error Scenarios & Edge Cases
See `05_ERROR_SCENARIOS_EDGE_CASES.md` for comprehensive error handling documentation.
