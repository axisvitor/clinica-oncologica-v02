"""
Alert detection and generation service for Hormonia Backend System.

⚠️  DEPRECATED: This is the legacy alert service (pre-QW-020).
    Use app.services.alerts.alert_manager.AlertManager instead.
    This service will be removed in a future version.
"""

import logging
import warnings
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.patient import Patient
from app.models.message import Message, MessageDirection
from app.models.quiz import QuizResponse
from app.repositories.alert import AlertRepository
from app.repositories.patient import PatientRepository
from app.repositories.message import MessageRepository
from app.repositories.quiz import QuizResponseRepository
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType

logger = logging.getLogger(__name__)


def _emit_deprecation_warning(method_name: str) -> None:
    """Emit deprecation warning for legacy alert service methods."""
    try:
        from app.config.settings import Settings

        settings = Settings()

        if settings.ALERTS_LEGACY_DEPRECATION_WARNING:
            warnings.warn(
                f"AlertService.{method_name} is deprecated and will be removed in a future version. "
                f"Please migrate to app.services.alerts.alert_manager.AlertManager. "
                f"See QW-020 migration guide for details.",
                DeprecationWarning,
                stacklevel=3,
            )
            logger.warning(
                f"DEPRECATED: AlertService.{method_name} called. "
                f"Migrate to AlertManager (QW-020). "
                f"Set USE_CONSOLIDATED_ALERTS=True in settings to use new system."
            )
    except Exception as e:
        # Fail silently if settings not available
        logger.debug(f"Could not emit deprecation warning: {e}")


@dataclass
class AlertRule:
    """Configuration for alert detection rules."""

    rule_type: str
    severity: AlertSeverity
    threshold: float
    time_window_hours: int
    description_template: str
    enabled: bool = True


class AlertService:
    """
    Service for detecting patterns and generating alerts.

    ⚠️  DEPRECATED: This is the legacy alert service (pre-QW-020).
        Use app.services.alerts.alert_manager.AlertManager instead.

        Migration Path:
        1. Set USE_CONSOLIDATED_ALERTS=True in settings
        2. Update imports: from app.services.alerts.alert_manager import AlertManager
        3. Replace AlertService(db) with AlertManager(db)
        4. Update method calls to new API (see QW-020 docs)
    """

    def __init__(self, db: Session):
        _emit_deprecation_warning("__init__")

        self.db = db
        self.alert_repo = AlertRepository(db)
        self.patient_repo = PatientRepository(db)
        self.message_repo = MessageRepository(db)
        self.quiz_repo = QuizResponseRepository(db)

        # Default alert rules - can be made configurable later
        self.alert_rules = {
            "no_response": AlertRule(
                rule_type="no_response",
                severity=AlertSeverity.MEDIUM,
                threshold=48.0,  # hours
                time_window_hours=72,
                description_template="Patient has not responded to messages for {hours} hours",
            ),
            "missed_quiz": AlertRule(
                rule_type="missed_quiz",
                severity=AlertSeverity.HIGH,
                threshold=2.0,  # missed quizzes
                time_window_hours=168,  # 1 week
                description_template="Patient has missed {count} scheduled quizzes in the past week",
            ),
            "negative_sentiment": AlertRule(
                rule_type="negative_sentiment",
                severity=AlertSeverity.HIGH,
                threshold=0.8,  # sentiment score threshold
                time_window_hours=24,
                description_template="Patient responses show concerning negative sentiment (score: {score})",
            ),
            "treatment_adherence": AlertRule(
                rule_type="treatment_adherence",
                severity=AlertSeverity.CRITICAL,
                threshold=0.5,  # adherence percentage
                time_window_hours=168,  # 1 week
                description_template="Patient treatment adherence is below threshold ({percentage}%)",
            ),
            "emergency_keywords": AlertRule(
                rule_type="emergency_keywords",
                severity=AlertSeverity.CRITICAL,
                threshold=1.0,  # any occurrence
                time_window_hours=1,
                description_template="Patient message contains emergency keywords: {keywords}",
            ),
        }

    def evaluate_patient_alerts(self, patient_id: UUID) -> List[Alert]:
        """Evaluate all alert rules for a specific patient."""
        logger.info(f"Evaluating alerts for patient {patient_id}")

        patient = self.patient_repo.get(patient_id)
        if not patient:
            logger.warning(f"Patient {patient_id} not found")
            return []

        generated_alerts = []

        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue

            try:
                alert = self._evaluate_rule(patient, rule)
                if alert:
                    # Check if similar alert already exists recently
                    if not self._has_recent_alert(
                        patient_id, rule.rule_type, hours=rule.time_window_hours
                    ):
                        generated_alerts.append(alert)
                        logger.info(
                            f"Generated {rule.rule_type} alert for patient {patient_id}"
                        )
                    else:
                        logger.debug(
                            f"Skipping duplicate {rule.rule_type} alert for patient {patient_id}"
                        )

            except Exception as e:
                logger.error(
                    f"Error evaluating rule {rule_name} for patient {patient_id}: {e}"
                )

        return generated_alerts

    def _evaluate_rule(self, patient: Patient, rule: AlertRule) -> Optional[Alert]:
        """Evaluate a specific alert rule for a patient."""
        if rule.rule_type == "no_response":
            return self._check_no_response(patient, rule)
        elif rule.rule_type == "missed_quiz":
            return self._check_missed_quiz(patient, rule)
        elif rule.rule_type == "negative_sentiment":
            return self._check_negative_sentiment(patient, rule)
        elif rule.rule_type == "treatment_adherence":
            return self._check_treatment_adherence(patient, rule)
        elif rule.rule_type == "emergency_keywords":
            return self._check_emergency_keywords(patient, rule)
        else:
            logger.warning(f"Unknown alert rule type: {rule.rule_type}")
            return None

    def _check_no_response(self, patient: Patient, rule: AlertRule) -> Optional[Alert]:
        """Check if patient hasn't responded within threshold time."""
        cutoff_time = datetime.utcnow() - timedelta(hours=rule.threshold)

        # Get last inbound message from patient
        last_response = (
            self.db.query(Message)
            .filter(
                Message.patient_id == patient.id,
                Message.direction == MessageDirection.INBOUND,
            )
            .order_by(Message.created_at.desc())
            .first()
        )

        # Check if we've sent messages since last response
        outbound_since_response = (
            self.db.query(Message)
            .filter(
                Message.patient_id == patient.id,
                Message.direction == MessageDirection.OUTBOUND,
                Message.created_at
                > (last_response.created_at if last_response else datetime.min),
            )
            .count()
        )

        if outbound_since_response > 0 and (
            not last_response or last_response.created_at < cutoff_time
        ):
            hours_since = (
                datetime.utcnow()
                - (last_response.created_at if last_response else patient.created_at)
            ).total_seconds() / 3600

            return Alert(
                patient_id=patient.id,
                alert_type=rule.rule_type,
                severity=rule.severity,
                description=rule.description_template.format(hours=int(hours_since)),
                data={
                    "hours_since_response": hours_since,
                    "last_response_at": last_response.created_at.isoformat()
                    if last_response
                    else None,
                },
            )

        return None

    def _check_missed_quiz(self, patient: Patient, rule: AlertRule) -> Optional[Alert]:
        """Check if patient has missed scheduled quizzes."""
        cutoff_time = datetime.utcnow() - timedelta(hours=rule.time_window_hours)

        # This is a simplified check - in a real system, you'd have scheduled quiz data
        # For now, we'll check if patient hasn't completed any quizzes recently
        recent_responses = (
            self.db.query(QuizResponse)
            .filter(
                QuizResponse.patient_id == patient.id,
                QuizResponse.created_at >= cutoff_time,
            )
            .count()
        )

        # Assume patient should complete at least 1 quiz per week
        expected_quizzes = 1
        missed_count = max(0, expected_quizzes - recent_responses)

        if missed_count >= rule.threshold:
            return Alert(
                patient_id=patient.id,
                alert_type=rule.rule_type,
                severity=rule.severity,
                description=rule.description_template.format(count=missed_count),
                data={"missed_count": missed_count, "expected_count": expected_quizzes},
            )

        return None

    def _check_negative_sentiment(
        self, patient: Patient, rule: AlertRule
    ) -> Optional[Alert]:
        """Check for concerning negative sentiment in patient responses."""
        cutoff_time = datetime.utcnow() - timedelta(hours=rule.time_window_hours)

        # Get recent inbound messages
        recent_messages = (
            self.db.query(Message)
            .filter(
                Message.patient_id == patient.id,
                Message.direction == MessageDirection.INBOUND,
                Message.created_at >= cutoff_time,
            )
            .all()
        )

        if not recent_messages:
            return None

        # Check for negative sentiment indicators in message metadata
        negative_scores = []
        for message in recent_messages:
            if message.metadata and "sentiment_score" in message.metadata:
                score = message.metadata["sentiment_score"]
                if score < 0:  # Negative sentiment
                    negative_scores.append(abs(score))

        if negative_scores:
            avg_negative_score = sum(negative_scores) / len(negative_scores)
            if avg_negative_score >= rule.threshold:
                return Alert(
                    patient_id=patient.id,
                    alert_type=rule.rule_type,
                    severity=rule.severity,
                    description=rule.description_template.format(
                        score=round(avg_negative_score, 2)
                    ),
                    data={
                        "sentiment_score": avg_negative_score,
                        "message_count": len(negative_scores),
                    },
                )

        return None

    def _check_treatment_adherence(
        self, patient: Patient, rule: AlertRule
    ) -> Optional[Alert]:
        """Check treatment adherence based on quiz responses."""
        cutoff_time = datetime.utcnow() - timedelta(hours=rule.time_window_hours)

        # Get recent quiz responses about adherence
        adherence_responses = (
            self.db.query(QuizResponse)
            .filter(
                QuizResponse.patient_id == patient.id,
                QuizResponse.created_at >= cutoff_time,
            )
            .all()
        )

        if not adherence_responses:
            return None

        # Calculate adherence percentage from responses
        adherence_scores = []
        for response in adherence_responses:
            if (
                response.response_metadata
                and "adherence_score" in response.response_metadata
            ):
                adherence_scores.append(response.response_metadata["adherence_score"])

        if adherence_scores:
            avg_adherence = sum(adherence_scores) / len(adherence_scores)
            if avg_adherence < rule.threshold:
                return Alert(
                    patient_id=patient.id,
                    alert_type=rule.rule_type,
                    severity=rule.severity,
                    description=rule.description_template.format(
                        percentage=round(avg_adherence * 100, 1)
                    ),
                    data={
                        "adherence_percentage": avg_adherence,
                        "response_count": len(adherence_scores),
                    },
                )

        return None

    def _check_emergency_keywords(
        self, patient: Patient, rule: AlertRule
    ) -> Optional[Alert]:
        """Check for emergency keywords in recent messages."""
        cutoff_time = datetime.utcnow() - timedelta(hours=rule.time_window_hours)

        emergency_keywords = [
            "emergency",
            "urgent",
            "help",
            "pain",
            "bleeding",
            "dizzy",
            "chest pain",
            "can't breathe",
            "suicide",
            "hurt myself",
        ]

        recent_messages = (
            self.db.query(Message)
            .filter(
                Message.patient_id == patient.id,
                Message.direction == MessageDirection.INBOUND,
                Message.created_at >= cutoff_time,
            )
            .all()
        )

        found_keywords = []
        for message in recent_messages:
            content_lower = message.content.lower()
            for keyword in emergency_keywords:
                if keyword in content_lower:
                    found_keywords.append(keyword)

        if found_keywords:
            return Alert(
                patient_id=patient.id,
                alert_type=rule.rule_type,
                severity=rule.severity,
                description=rule.description_template.format(
                    keywords=", ".join(set(found_keywords))
                ),
                data={
                    "keywords": list(set(found_keywords)),
                    "message_count": len(recent_messages),
                },
            )

        return None

    def _has_recent_alert(
        self, patient_id: UUID, alert_type: str, hours: int = 24
    ) -> bool:
        """Check if a similar alert already exists recently."""
        recent_alerts = self.alert_repo.get_recent_alerts(patient_id, alert_type, hours)
        return len(recent_alerts) > 0

    async def create_alert(self, alert: Alert) -> Alert:
        """Create and persist a new alert."""
        try:
            created_alert = self.alert_repo.create(alert)
            logger.info(
                f"Created alert {created_alert.id} for patient {alert.patient_id}"
            )

            # Publish WebSocket event for new alert
            await websocket_events.publish_alert_event(
                event_type=WebSocketEventType.ALERT_CREATED,
                alert_id=created_alert.id,
                patient_id=created_alert.patient_id,
                alert_type=created_alert.alert_type,
                severity=created_alert.severity.value,
                title=f"{created_alert.alert_type.replace('_', ' ').title()} Alert",
                description=created_alert.description,
            )

            return created_alert
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            raise

    async def acknowledge_alert(self, alert_id: UUID, user_id: UUID) -> Optional[Alert]:
        """Acknowledge an alert."""
        alert = self.alert_repo.get(alert_id)
        if not alert:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.utcnow()

        updated_alert = self.alert_repo.update(alert)
        logger.info(f"Alert {alert_id} acknowledged by user {user_id}")

        # Publish WebSocket event for alert acknowledgment
        await websocket_events.publish_alert_event(
            event_type=WebSocketEventType.ALERT_ACKNOWLEDGED,
            alert_id=updated_alert.id,
            patient_id=updated_alert.patient_id,
            alert_type=updated_alert.alert_type,
            severity=updated_alert.severity.value,
            title=f"{updated_alert.alert_type.replace('_', ' ').title()} Alert",
            description=updated_alert.description,
            acknowledged=True,
            acknowledged_by=user_id,
            acknowledged_at=updated_alert.acknowledged_at,
        )

        return updated_alert

    async def resolve_alert(self, alert_id: UUID, user_id: UUID) -> Optional[Alert]:
        """Resolve an alert."""
        alert = self.alert_repo.get(alert_id)
        if not alert:
            return None

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()

        updated_alert = self.alert_repo.update(alert)
        logger.info(f"Alert {alert_id} resolved by user {user_id}")

        # Publish WebSocket event for alert resolution
        await websocket_events.publish_alert_event(
            event_type=WebSocketEventType.ALERT_RESOLVED,
            alert_id=updated_alert.id,
            patient_id=updated_alert.patient_id,
            alert_type=updated_alert.alert_type,
            severity=updated_alert.severity.value,
            title=f"{updated_alert.alert_type.replace('_', ' ').title()} Alert",
            description=updated_alert.description,
            resolved=True,
            resolved_by=user_id,
            resolved_at=updated_alert.resolved_at,
        )

        return updated_alert

    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert system statistics."""
        return {
            "total_pending": self.alert_repo.count_unacknowledged(),
            "critical_count": self.alert_repo.count_by_severity(AlertSeverity.CRITICAL),
            "high_count": self.alert_repo.count_by_severity(AlertSeverity.HIGH),
            "medium_count": self.alert_repo.count_by_severity(AlertSeverity.MEDIUM),
            "low_count": self.alert_repo.count_by_severity(AlertSeverity.LOW),
            "active_rules": len([r for r in self.alert_rules.values() if r.enabled]),
        }

    def update_alert_rule(self, rule_type: str, **kwargs) -> bool:
        """Update an alert rule configuration."""
        if rule_type not in self.alert_rules:
            return False

        rule = self.alert_rules[rule_type]
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        logger.info(f"Updated alert rule {rule_type}")
        return True
