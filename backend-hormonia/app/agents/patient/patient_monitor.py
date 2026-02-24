from __future__ import annotations

# DDD service agent - no LLM calls, not a pydantic-ai migration target.
"""
Patient Monitor Agent.

Responsible for continuous monitoring of patient status, adherence to treatment,
and detection of potential issues requiring intervention.
"""

# Standard library
from datetime import timedelta
from typing import Any, Dict, List
from uuid import UUID

# Third-party
from sqlalchemy.orm import Session

# Local
from app.agents.base import AgentCapabilities, BaseAgent
from app.agents.patient.flow_coordinator.constants import ONBOARDING_END_DAY, DAILY_FOLLOWUP_END_DAY
from app.agents.registry import PATIENT_MONITOR_ID
from app.models.quiz import QuizSession
from app.repositories.patient import PatientRepository
from app.utils.logging import get_logger
from app.utils.timezone import now_sao_paulo, to_sao_paulo, SAO_PAULO_TZ


class PatientMonitorAgent(BaseAgent):
    """
    Monitors patient status and treatment adherence.

    Continuously tracks patient engagement, detects potential
    issues, and triggers alerts when intervention is needed.

    Capabilities:
    - Monitor treatment adherence.
    - Detect missed check-ins.
    - Track patient engagement.
    - Trigger reminders and alerts.

    Attributes:
        patient_repo: Patient repository.
        logger: Logger instance.
        monitoring_config: Monitoring configuration parameters.
    """

    def __init__(self, db_session: Session):
        """Initialize Patient Monitor Agent."""
        super().__init__(
            agent_id=PATIENT_MONITOR_ID,
            agent_type="patient",
            specialization="patient_monitor",
            db_session=db_session,
            capabilities=[
                AgentCapabilities.PATIENT_ADAPTATION,
                AgentCapabilities.FLOW_COORDINATION,
            ],
        )

        self.patient_repo = PatientRepository(db_session)
        self.logger = get_logger(f"agent.{self.agent_id}")

        # Monitoring configuration
        self.monitoring_config = {
            "check_in_window_hours": 24,
            "max_missed_checkins": 2,
            "engagement_threshold_days": 7,
            "adherence_alert_threshold": 0.7,  # 70% adherence
        }

        self.logger.info("Patient Monitor Agent initialized")

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process monitoring task."""
        try:
            task_type = task.get("task_type")
            payload = task.get("payload", {})

            if task_type == "check_patient_status":
                return await self._check_patient_status(payload)
            elif task_type == "monitor_adherence":
                return await self._monitor_adherence(payload)
            elif task_type == "detect_engagement_drop":
                return await self._detect_engagement_drop(payload)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}

        except Exception as e:
            self.logger.error(f"Task processing failed: {e}")
            return {"success": False, "error": str(e)}

    async def _check_patient_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Check status of a specific patient."""
        try:
            patient_id_str = payload.get("patient_id")
            if not patient_id_str:
                return {"success": False, "error": "Missing patient_id"}

            patient_id = UUID(patient_id_str)
            patient = self.patient_repo.get(patient_id)

            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Perform status checks
            last_interaction = patient.updated_at or patient.created_at
            if last_interaction.tzinfo is None:
                last_interaction = last_interaction.replace(tzinfo=SAO_PAULO_TZ)
            days_since_interaction = (
                now_sao_paulo().date() - to_sao_paulo(last_interaction).date()
            ).days

            status_report = {
                "patient_id": str(patient.id),
                "status": patient.status,
                "days_since_interaction": days_since_interaction,
                "needs_attention": days_since_interaction
                > self.monitoring_config["engagement_threshold_days"],
                "alerts": [],
            }

            if status_report["needs_attention"]:
                status_report["alerts"].append("Low engagement detected")

            return {"success": True, "report": status_report}

        except Exception as e:
            self.logger.error(f"Patient status check failed: {e}")
            return {"success": False, "error": str(e)}

    async def _monitor_adherence(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Monitor treatment adherence for a patient.

        Calculates adherence rate based on completed quizzes vs expected quizzes.
        Triggers alert when adherence falls below threshold (70%).

        Args:
            payload: Dict containing patient_id and optional days_back (default 30)

        Returns:
            Dict with adherence_rate, total_expected, total_completed, and alerts
        """
        try:
            patient_id_str = payload.get("patient_id")
            if not patient_id_str:
                return {"success": False, "error": "Missing patient_id"}

            patient_id = UUID(patient_id_str)
            days_back = payload.get("days_back", 30)

            # Get patient
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Calculate date range for analysis
            end_local = now_sao_paulo()
            start_local = end_local - timedelta(days=days_back)
            end_date = end_local.astimezone(SAO_PAULO_TZ)
            start_date = start_local.astimezone(SAO_PAULO_TZ)

            # Query completed quiz sessions in the period
            completed_sessions = (
                self.db_session.query(QuizSession)
                .filter(
                    QuizSession.patient_id == patient_id,
                    QuizSession.status == "completed",
                    QuizSession.completed_at >= start_date,
                    QuizSession.completed_at <= end_date,
                )
                .count()
            )

            # Query all quiz sessions (including incomplete) in the period
            total_sessions = (
                self.db_session.query(QuizSession)
                .filter(
                    QuizSession.patient_id == patient_id,
                    QuizSession.started_at >= start_date,
                    QuizSession.started_at <= end_date,
                )
                .count()
            )

            # Calculate expected quizzes based on treatment phase
            # Monthly recurring expects ~1 quiz per month
            # Initial phase expects more frequent quizzes
            current_day = getattr(patient, "current_day", 0) or 0
            if current_day <= ONBOARDING_END_DAY:
                expected_quizzes = max(1, days_back // 5)  # Every 5 days initially
            elif current_day <= DAILY_FOLLOWUP_END_DAY:
                expected_quizzes = max(1, days_back // 10)  # Every 10 days
            else:
                expected_quizzes = max(1, days_back // 30)  # Monthly

            # Use max of expected or actual sent
            total_expected = max(expected_quizzes, total_sessions)

            # Calculate adherence rate
            if total_expected > 0:
                adherence_rate = completed_sessions / total_expected
            else:
                adherence_rate = 1.0  # No quizzes expected yet

            # Build response
            alerts: List[str] = []
            threshold = self.monitoring_config["adherence_alert_threshold"]

            if adherence_rate < threshold:
                alerts.append(
                    f"Low adherence: {adherence_rate:.1%} (threshold: {threshold:.0%})"
                )
                self.logger.warning(
                    f"Patient {patient_id} adherence {adherence_rate:.1%} below threshold"
                )

            return {
                "success": True,
                "patient_id": str(patient_id),
                "adherence_rate": round(adherence_rate, 3),
                "total_expected": total_expected,
                "total_completed": completed_sessions,
                "total_started": total_sessions,
                "days_analyzed": days_back,
                "threshold": threshold,
                "below_threshold": adherence_rate < threshold,
                "alerts": alerts,
            }

        except Exception as e:
            self.logger.error(f"Adherence monitoring failed: {e}")
            return {"success": False, "error": str(e)}

    async def _detect_engagement_drop(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect drops in patient engagement.

        Analyzes interaction frequency to identify disengaged patients
        based on days since last activity and quiz participation trends.

        Args:
            payload: Dict containing patient_id and optional lookback_days

        Returns:
            Dict with engagement status, days_since_activity, and alerts
        """
        try:
            patient_id_str = payload.get("patient_id")
            if not patient_id_str:
                return {"success": False, "error": "Missing patient_id"}

            patient_id = UUID(patient_id_str)
            lookback_days = payload.get(
                "lookback_days", self.monitoring_config["engagement_threshold_days"]
            )

            # Get patient
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}

            now = now_sao_paulo()

            # Check last quiz activity
            last_quiz = (
                self.db_session.query(QuizSession)
                .filter(QuizSession.patient_id == patient_id)
                .order_by(QuizSession.started_at.desc())
                .first()
            )

            # Calculate days since last activity
            last_activity = patient.updated_at or patient.created_at
            if last_quiz and last_quiz.started_at:
                quiz_activity = last_quiz.started_at
                if quiz_activity.tzinfo is None:
                    quiz_activity = quiz_activity.replace(tzinfo=SAO_PAULO_TZ)
                if quiz_activity > last_activity:
                    last_activity = quiz_activity

            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=SAO_PAULO_TZ)

            days_since_activity = (now - last_activity).days

            # Calculate engagement trend (compare recent vs past activity)
            recent_period = now - timedelta(days=lookback_days)
            past_period_start = recent_period - timedelta(days=lookback_days)

            recent_quizzes = (
                self.db_session.query(QuizSession)
                .filter(
                    QuizSession.patient_id == patient_id,
                    QuizSession.started_at >= recent_period,
                )
                .count()
            )

            past_quizzes = (
                self.db_session.query(QuizSession)
                .filter(
                    QuizSession.patient_id == patient_id,
                    QuizSession.started_at >= past_period_start,
                    QuizSession.started_at < recent_period,
                )
                .count()
            )

            # Detect engagement drop
            engagement_dropped = False
            drop_percentage = 0.0

            if past_quizzes > 0:
                drop_percentage = (past_quizzes - recent_quizzes) / past_quizzes
                engagement_dropped = drop_percentage > 0.5  # 50% drop threshold

            # Build alerts
            alerts: List[str] = []
            threshold = self.monitoring_config["engagement_threshold_days"]

            if days_since_activity > threshold:
                alerts.append(
                    f"No activity in {days_since_activity} days (threshold: {threshold})"
                )

            if engagement_dropped:
                alerts.append(
                    f"Engagement dropped {drop_percentage:.0%} compared to previous period"
                )

            # Determine engagement status
            if days_since_activity <= 3:
                engagement_status = "active"
            elif days_since_activity <= threshold:
                engagement_status = "moderate"
            else:
                engagement_status = "low"

            if engagement_dropped:
                engagement_status = "declining"

            self.logger.info(
                f"Patient {patient_id} engagement: {engagement_status}, "
                f"days since activity: {days_since_activity}"
            )

            return {
                "success": True,
                "patient_id": str(patient_id),
                "engagement_status": engagement_status,
                "days_since_activity": days_since_activity,
                "recent_quizzes": recent_quizzes,
                "past_quizzes": past_quizzes,
                "engagement_dropped": engagement_dropped,
                "drop_percentage": round(drop_percentage, 3) if engagement_dropped else 0,
                "threshold_days": threshold,
                "needs_attention": days_since_activity > threshold or engagement_dropped,
                "alerts": alerts,
            }

        except Exception as e:
            self.logger.error(f"Engagement drop detection failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities."""
        return [
            AgentCapabilities.PATIENT_ADAPTATION,
            AgentCapabilities.FLOW_COORDINATION,
        ]

    async def validate_task(self, task_data: Dict[str, Any]) -> bool:
        """Validate if task can be handled."""
        valid_types = [
            "check_patient_status",
            "monitor_adherence",
            "detect_engagement_drop",
        ]
        return task_data.get("task_type") in valid_types
