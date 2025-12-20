"""
Medico Statistics Service for dashboard metrics.

Provides comprehensive statistics for doctor's dashboard including:
- Active patients count
- Today's consultations/appointments
- Pending tasks (exams + messages)
- Message engagement metrics
- Alert counts by severity
"""

from sqlalchemy import func, case
from datetime import datetime, timedelta, date, time, timezone
from typing import Dict, Any, Optional
import logging

from app.models.patient import Patient
from app.models.message import Message, MessageDirection, MessageStatus
from app.models.alert import Alert, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)


class MedicoStatsService:
    """Service for calculating medico dashboard statistics."""

    def __init__(self, db: Any, medico_id: str):
        """
        Initialize medico stats service.

        Args:
            db: SQLAlchemy database session
            medico_id: UUID of the medico (doctor)
        """
        self.db = db
        self.medico_id = medico_id

    def get_pacientes_ativos(self) -> int:
        """
        Count active patients for this medico.

        Returns:
            Number of active patients
        """
        try:
            count = (
                self.db.query(Patient)
                .filter(
                    Patient.doctor_id == self.medico_id,
                    # Active patients are those not in inactive or completed state
                    Patient.flow_state.notin_(["inactive", "completed"]),
                )
                .count()
            )

            logger.debug(f"Medico {self.medico_id}: {count} active patients")
            return count
        except Exception as e:
            logger.error(f"Error counting active patients: {e}")
            return 0

    def get_consultas_hoje(self) -> int:
        """
        Count today's consultations/appointments.

        Since we don't have an appointments table yet, we'll count
        messages sent today as a proxy for consultations.

        Returns:
            Number of consultations today
        """
        try:
            today_start = datetime.combine(date.today(), time.min)
            today_end = datetime.combine(date.today(), time.max)

            # Count outbound messages sent today as proxy for consultations
            count = (
                self.db.query(Message)
                .join(Patient, Message.patient_id == Patient.id)
                .filter(
                    Patient.doctor_id == self.medico_id,
                    Message.direction == MessageDirection.OUTBOUND,
                    Message.created_at >= today_start,
                    Message.created_at <= today_end,
                )
                .count()
            )

            logger.debug(f"Medico {self.medico_id}: {count} consultations today")
            return count
        except Exception as e:
            logger.error(f"Error counting today's consultations: {e}")
            return 0

    def get_pendencias(self) -> int:
        """
        Count pending tasks (unread messages from last 48h).

        Since we don't have exams table yet, we count pending messages only.

        Returns:
            Number of pending tasks
        """
        try:
            two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)

            # Count unread inbound messages from last 48h
            # Join with patients to ensure they belong to this medico
            pending_messages = (
                self.db.query(Message)
                .join(Patient, Message.patient_id == Patient.id)
                .filter(
                    Patient.doctor_id == self.medico_id,
                    Message.direction == MessageDirection.INBOUND,
                    Message.status.notin_([MessageStatus.READ]),
                    Message.created_at >= two_days_ago,
                )
                .count()
            )

            logger.debug(
                f"Medico {self.medico_id}: {pending_messages} pending messages"
            )
            return pending_messages
        except Exception as e:
            logger.error(f"Error counting pending tasks: {e}")
            return 0

    def get_exames_aguardando(self) -> int:
        """
        Count exams awaiting review.

        Since we don't have exams table yet, return 0.
        TODO: Implement when exams table is available.

        Returns:
            Number of exams awaiting review
        """
        # Placeholder - no exams table yet
        logger.debug(f"Medico {self.medico_id}: Exams table not implemented")
        return 0

    def get_engagement_metrics(self) -> Dict[str, Any]:
        """
        Calculate message engagement metrics.

        Returns:
            Dictionary with engagement metrics:
            - messages_today: Messages sent today
            - messages_unread: Unread inbound messages
            - response_rate: Percentage of messages responded to (last 7 days)
            - avg_response_time_minutes: Average response time
        """
        try:
            today_start = datetime.combine(date.today(), time.min)
            today_end = datetime.combine(date.today(), time.max)
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)

            # Messages sent today by medico
            messages_today = (
                self.db.query(Message)
                .join(Patient, Message.patient_id == Patient.id)
                .filter(
                    Patient.doctor_id == self.medico_id,
                    Message.direction == MessageDirection.OUTBOUND,
                    Message.created_at >= today_start,
                    Message.created_at <= today_end,
                )
                .count()
            )

            # Unread inbound messages
            messages_unread = (
                self.db.query(Message)
                .join(Patient, Message.patient_id == Patient.id)
                .filter(
                    Patient.doctor_id == self.medico_id,
                    Message.direction == MessageDirection.INBOUND,
                    Message.status.notin_([MessageStatus.READ]),
                )
                .count()
            )

            # Response rate calculation (last 7 days)
            # Count inbound messages
            inbound_count = (
                self.db.query(Message)
                .join(Patient, Message.patient_id == Patient.id)
                .filter(
                    Patient.doctor_id == self.medico_id,
                    Message.direction == MessageDirection.INBOUND,
                    Message.created_at >= week_ago,
                )
                .count()
            )

            # Count read inbound messages (proxy for responded)
            read_count = (
                self.db.query(Message)
                .join(Patient, Message.patient_id == Patient.id)
                .filter(
                    Patient.doctor_id == self.medico_id,
                    Message.direction == MessageDirection.INBOUND,
                    Message.status == MessageStatus.READ,
                    Message.created_at >= week_ago,
                )
                .count()
            )

            response_rate = (read_count / inbound_count) if inbound_count > 0 else 0.0

            # Average response time calculation
            # This is simplified - actual implementation would need message threading
            avg_response_time = self._calculate_avg_response_time()

            metrics = {
                "messages_today": messages_today,
                "messages_unread": messages_unread,
                "response_rate": round(response_rate, 2),
                "avg_response_time_minutes": avg_response_time,
            }

            logger.debug(f"Medico {self.medico_id} engagement metrics: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"Error calculating engagement metrics: {e}")
            return {
                "messages_today": 0,
                "messages_unread": 0,
                "response_rate": 0.0,
                "avg_response_time_minutes": None,
            }

    def _calculate_avg_response_time(self) -> Optional[int]:
        """
        Calculate average response time in minutes.

        Simplified implementation - would need proper message threading
        to calculate accurate response times.

        Returns:
            Average response time in minutes, or None if not calculable
        """
        try:
            datetime.now(timezone.utc) - timedelta(days=7)

            # Get pairs of inbound and next outbound messages
            # This is a simplified approach - production would need proper threading

            # For now, return None (indicating data not available)
            # TODO: Implement proper response time calculation with message threading
            return None

        except Exception as e:
            logger.error(f"Error calculating average response time: {e}")
            return None

    def get_alert_metrics(self) -> Dict[str, Any]:
        """
        Count alerts by severity for medico's patients.

        Returns:
            Dictionary with alert counts:
            - total: Total active alerts
            - critical: Critical alerts
            - high: High priority alerts
            - medium: Medium priority alerts
            - low: Low priority alerts
        """
        try:
            # Get patient IDs for this medico
            patient_ids_query = self.db.query(Patient.id).filter(
                Patient.doctor_id == self.medico_id
            )

            # Count active alerts by severity
            # Use case statement for conditional counting
            alert_counts = (
                self.db.query(
                    func.count(Alert.id).label("total"),
                    func.sum(
                        case((Alert.severity == AlertSeverity.CRITICAL, 1), else_=0)
                    ).label("critical"),
                    func.sum(
                        case((Alert.severity == AlertSeverity.HIGH, 1), else_=0)
                    ).label("high"),
                    func.sum(
                        case((Alert.severity == AlertSeverity.MEDIUM, 1), else_=0)
                    ).label("medium"),
                    func.sum(
                        case((Alert.severity == AlertSeverity.LOW, 1), else_=0)
                    ).label("low"),
                )
                .filter(
                    Alert.patient_id.in_(patient_ids_query),
                    Alert.status.in_([AlertStatus.PENDING, AlertStatus.ACTIVE]),
                )
                .first()
            )

            if not alert_counts:
                return {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}

            metrics = {
                "total": alert_counts.total or 0,
                "critical": alert_counts.critical or 0,
                "high": alert_counts.high or 0,
                "medium": alert_counts.medium or 0,
                "low": alert_counts.low or 0,
            }

            logger.debug(f"Medico {self.medico_id} alert metrics: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"Error calculating alert metrics: {e}")
            return {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}

    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get all dashboard statistics.

        Executes all metric calculations and returns complete dashboard data.

        Returns:
            Dictionary with all dashboard statistics
        """
        try:
            logger.info(f"Calculating dashboard stats for medico {self.medico_id}")

            stats = {
                "pacientes_ativos": self.get_pacientes_ativos(),
                "consultas_hoje": self.get_consultas_hoje(),
                "pendencias": self.get_pendencias(),
                "exames_aguardando": self.get_exames_aguardando(),
                "engagement": self.get_engagement_metrics(),
                "alerts": self.get_alert_metrics(),
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            }

            logger.info(
                f"Dashboard stats calculated for medico {self.medico_id}: {stats}"
            )
            return stats

        except Exception as e:
            logger.error(
                f"Error calculating all stats for medico {self.medico_id}: {e}"
            )
            # Return zero stats on error
            return {
                "pacientes_ativos": 0,
                "consultas_hoje": 0,
                "pendencias": 0,
                "exames_aguardando": 0,
                "engagement": {
                    "messages_today": 0,
                    "messages_unread": 0,
                    "response_rate": 0.0,
                    "avg_response_time_minutes": None,
                },
                "alerts": {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            }
