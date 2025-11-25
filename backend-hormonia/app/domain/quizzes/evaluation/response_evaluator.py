"""
Quiz Response Evaluator Service for Hormonia Backend System.

This service automatically evaluates quiz responses against alert rules
and generates alerts when risk thresholds are exceeded.

Sprint 2 - Week 1, Task 3: Automatic Alert Evaluation
"""
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from app.config.quiz_alert_rules import QUIZ_ALERT_RULES, AlertSeverity, QuizAlertRule
from app.repositories.alert import AlertRepository
from app.models.alert import Alert, AlertStatus, AlertSeverity as ModelAlertSeverity
from app.exceptions import ValidationError, DatabaseError
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


class QuizResponseEvaluator:
    """
    Evaluates quiz responses and generates alerts based on configured rules.

    This service:
    1. Evaluates quiz responses against all configured alert rules
    2. Creates alerts for triggered rules
    3. Calculates overall risk scores
    4. Triggers notifications to medical team
    """

    # Map config AlertSeverity to model AlertSeverity
    SEVERITY_MAP = {
        AlertSeverity.CRITICAL: ModelAlertSeverity.CRITICAL,
        AlertSeverity.WARNING: ModelAlertSeverity.HIGH,
        AlertSeverity.INFO: ModelAlertSeverity.MEDIUM
    }

    def __init__(self, db: Session):
        self.db = db
        self.alert_repository = AlertRepository(db)
        self.audit_service = AuditService(db)

    async def evaluate_quiz_session(
        self,
        quiz_session_id: UUID,
        patient_id: UUID,
        responses: Dict[str, Any]
    ) -> Tuple[List[Alert], float]:
        """
        Evaluate quiz responses against alert rules.

        Args:
            quiz_session_id: UUID of the quiz session
            patient_id: UUID of the patient
            responses: Dictionary of question_id -> response_value mappings

        Returns:
            Tuple of (triggered alerts list, overall risk score)

        Raises:
            ValidationError: If inputs are invalid
            DatabaseError: If database operations fail
        """
        if not quiz_session_id:
            raise ValidationError("quiz_session_id is required")
        if not patient_id:
            raise ValidationError("patient_id is required")
        if not responses or not isinstance(responses, dict):
            raise ValidationError("responses must be a non-empty dictionary")

        logger.info(
            f"Evaluating quiz session {quiz_session_id} for patient {patient_id} "
            f"with {len(responses)} responses"
        )

        triggered_alerts = []

        # Normalize responses for easier evaluation
        normalized_responses = self._normalize_responses(responses)

        # Evaluate each rule
        for rule in QUIZ_ALERT_RULES:
            try:
                if rule.evaluate(normalized_responses):
                    logger.warning(
                        f"Alert rule '{rule.rule_id}' triggered for patient {patient_id} "
                        f"(severity: {rule.severity.value})"
                    )

                    # Create alert
                    alert = await self._create_alert(
                        quiz_session_id=quiz_session_id,
                        patient_id=patient_id,
                        rule=rule,
                        responses=normalized_responses
                    )

                    triggered_alerts.append(alert)

            except Exception as e:
                logger.error(
                    f"Error evaluating rule '{rule.rule_id}' for patient {patient_id}: {e}",
                    exc_info=True
                )
                # Continue with other rules even if one fails

        # Calculate overall risk score
        risk_score = self._calculate_risk_score(triggered_alerts)

        # Log evaluation summary
        logger.info(
            f"Quiz evaluation complete for session {quiz_session_id}: "
            f"{len(triggered_alerts)} alerts generated, risk score: {risk_score:.2f}"
        )

        # Audit log the evaluation
        await self.audit_service.log_action(
            user_id=None,  # System-generated
            action="quiz_response_evaluation",
            resource_type="quiz_session",
            resource_id=str(quiz_session_id),
            details={
                "patient_id": str(patient_id),
                "alerts_generated": len(triggered_alerts),
                "risk_score": risk_score,
                "triggered_rule_ids": [a.data.get("triggered_rule_id") for a in triggered_alerts]
            }
        )

        return triggered_alerts, risk_score

    def _normalize_responses(self, responses: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize response values for consistent evaluation.

        Handles:
        - Converting string numbers to floats
        - Normalizing boolean values
        - Extracting nested values

        Args:
            responses: Raw response dictionary

        Returns:
            Normalized response dictionary
        """
        normalized = {}

        for key, value in responses.items():
            # Handle nested response structures
            if isinstance(value, dict):
                if "value" in value:
                    value = value["value"]
                elif "response_value" in value:
                    value = value["response_value"]

            # Convert string numbers to float
            if isinstance(value, str) and value.replace(".", "", 1).isdigit():
                try:
                    value = float(value)
                except ValueError:
                    pass

            # Normalize boolean strings
            if isinstance(value, str):
                value_lower = value.lower()
                if value_lower in ("yes", "sim", "true", "1", "y", "s"):
                    value = True
                elif value_lower in ("no", "não", "nao", "false", "0", "n"):
                    value = False

            normalized[key] = value

        return normalized

    async def _create_alert(
        self,
        quiz_session_id: UUID,
        patient_id: UUID,
        rule: QuizAlertRule,
        responses: Dict[str, Any]
    ) -> Alert:
        """
        Create alert from triggered rule.

        Args:
            quiz_session_id: UUID of quiz session
            patient_id: UUID of patient
            rule: Triggered QuizAlertRule
            responses: Normalized responses

        Returns:
            Created Alert instance

        Raises:
            DatabaseError: If alert creation fails
        """
        try:
            # Map severity from config to model
            model_severity = self.SEVERITY_MAP.get(rule.severity, ModelAlertSeverity.MEDIUM)

            # Create alert instance
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
                    "relevant_responses": self._extract_relevant_responses(responses, rule),
                    "evaluated_at": datetime.utcnow().isoformat()
                }
            )

            # Save to database
            created_alert = self.alert_repository.create(alert)
            self.db.commit()

            logger.info(f"Alert {created_alert.id} created for patient {patient_id}")

            # Trigger notifications asynchronously
            await self._notify_medical_team(created_alert, rule)

            return created_alert

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create alert for rule '{rule.rule_id}': {e}", exc_info=True)
            raise DatabaseError(f"Failed to create alert: {str(e)}")

    def _extract_relevant_responses(
        self,
        responses: Dict[str, Any],
        rule: QuizAlertRule
    ) -> Dict[str, Any]:
        """
        Extract responses relevant to the triggered rule.

        Args:
            responses: All normalized responses
            rule: Triggered rule

        Returns:
            Dictionary of relevant responses
        """
        # For now, return all responses
        # In the future, we could analyze the rule condition to extract only relevant fields
        return responses

    def _calculate_risk_score(self, alerts: List[Alert]) -> float:
        """
        Calculate overall risk score (0-100) based on triggered alerts.

        Scoring algorithm:
        - CRITICAL alerts: 50 points each
        - WARNING (HIGH) alerts: 30 points each
        - INFO (MEDIUM) alerts: 10 points each
        - Maximum score capped at 100

        Args:
            alerts: List of triggered alerts

        Returns:
            Risk score from 0 to 100
        """
        if not alerts:
            return 0.0

        severity_weights = {
            ModelAlertSeverity.CRITICAL: 50,
            ModelAlertSeverity.HIGH: 30,
            ModelAlertSeverity.MEDIUM: 10,
            ModelAlertSeverity.LOW: 5
        }

        total_score = sum(
            severity_weights.get(alert.severity, 0)
            for alert in alerts
        )

        # Cap at 100
        return min(float(total_score), 100.0)

    async def _notify_medical_team(self, alert: Alert, rule: QuizAlertRule):
        """
        Send notifications to medical team about the alert.

        Notification channels:
        - Dashboard notification (always)
        - Email for CRITICAL and WARNING alerts
        - SMS for CRITICAL alerts (optional)

        Args:
            alert: Created alert
            rule: Triggered rule
        """
        logger.info(f"Sending notifications for alert {alert.id} (severity: {alert.severity.value})")

        try:
            # Dashboard notification (always)
            await self._send_dashboard_notification(alert, rule)

            # Email for CRITICAL and WARNING
            if alert.severity in (ModelAlertSeverity.CRITICAL, ModelAlertSeverity.HIGH):
                await self._send_email_notification(alert, rule)

            # SMS for CRITICAL only (optional)
            if alert.severity == ModelAlertSeverity.CRITICAL:
                await self._send_sms_notification(alert, rule)

        except Exception as e:
            logger.error(f"Error sending notifications for alert {alert.id}: {e}", exc_info=True)
            # Don't raise - notification failures shouldn't block alert creation

    async def _send_dashboard_notification(self, alert: Alert, rule: QuizAlertRule):
        """Send real-time notification to dashboard via WebSocket."""
        # TODO: Implement WebSocket notification
        logger.info(f"Dashboard notification: {alert.id}")
        pass

    async def _send_email_notification(self, alert: Alert, rule: QuizAlertRule):
        """Send email notification to assigned physician."""
        # TODO: Implement email notification
        logger.info(f"Email notification: {alert.id}")
        pass

    async def _send_sms_notification(self, alert: Alert, rule: QuizAlertRule):
        """Send SMS notification for critical alerts."""
        # TODO: Implement SMS notification
        logger.info(f"SMS notification: {alert.id}")
        pass

    def get_evaluation_summary(self, patient_id: UUID, days: int = 30) -> Dict[str, Any]:
        """
        Get summary of alert evaluations for a patient.

        Args:
            patient_id: UUID of patient
            days: Number of days to look back

        Returns:
            Dictionary with evaluation statistics
        """
        try:
            # Get recent alerts
            alerts = self.alert_repository.get_by_patient(patient_id, limit=1000)

            # Filter quiz-related alerts
            quiz_alerts = [a for a in alerts if a.alert_type == "quiz_response"]

            # Calculate statistics
            total_alerts = len(quiz_alerts)
            by_severity = {
                "critical": len([a for a in quiz_alerts if a.severity == ModelAlertSeverity.CRITICAL]),
                "high": len([a for a in quiz_alerts if a.severity == ModelAlertSeverity.HIGH]),
                "medium": len([a for a in quiz_alerts if a.severity == ModelAlertSeverity.MEDIUM]),
                "low": len([a for a in quiz_alerts if a.severity == ModelAlertSeverity.LOW])
            }

            # Get most common triggered rules
            rule_counts = {}
            for alert in quiz_alerts:
                rule_id = alert.data.get("triggered_rule_id")
                if rule_id:
                    rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1

            return {
                "patient_id": str(patient_id),
                "total_quiz_alerts": total_alerts,
                "by_severity": by_severity,
                "most_common_rules": sorted(
                    rule_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5],
                "acknowledgement_rate": self._calculate_acknowledgement_rate(quiz_alerts)
            }

        except Exception as e:
            logger.error(f"Error generating evaluation summary for patient {patient_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to generate evaluation summary: {str(e)}")

    def _calculate_acknowledgement_rate(self, alerts: List[Alert]) -> float:
        """Calculate percentage of acknowledged alerts."""
        if not alerts:
            return 0.0

        acknowledged = len([a for a in alerts if a.status == AlertStatus.ACKNOWLEDGED])
        return (acknowledged / len(alerts)) * 100.0
