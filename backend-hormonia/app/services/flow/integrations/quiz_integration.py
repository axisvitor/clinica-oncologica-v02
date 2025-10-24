"""
Quiz Flow Integration - Quiz service integration for Flow Services (QW-021).

This module provides integration between the consolidated flow system and
the quiz service, enabling quiz-based flows and data synchronization.

Migration Note:
    This consolidates quiz integration from:
    - flow.py (FlowEngineIntegrationService)
    - quiz_flow.py (quiz flow logic)
    - Various quiz-related flow handlers
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
import logging

from ..types import (
    FlowType,
    FlowContext,
    FlowStatus,
)
from ..config import get_flow_config


logger = logging.getLogger(__name__)


class QuizFlowIntegration:
    """
    Integration service for quiz flows.

    Handles quiz flow creation, monitoring, and result processing.
    """

    def __init__(self):
        """Initialize quiz flow integration."""
        self.config = get_flow_config().integrations

        # Quiz flow tracking (in-memory, should use DB in production)
        self._quiz_flows: Dict[UUID, Dict[str, Any]] = {}
        self._flow_to_quiz: Dict[UUID, UUID] = {}  # flow_id -> quiz_id
        self._quiz_to_flow: Dict[UUID, UUID] = {}  # quiz_id -> flow_id

        logger.info("QuizFlowIntegration initialized")

    # ========================================================================
    # Quiz Flow Creation
    # ========================================================================

    def create_quiz_flow(
        self,
        patient_id: UUID,
        quiz_type: str,
        quiz_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a quiz flow for a patient.

        Args:
            patient_id: Patient ID.
            quiz_type: Type of quiz (monthly, symptom, etc.).
            quiz_data: Optional initial quiz data.

        Returns:
            Dictionary with quiz flow information.
        """
        if not self.config.enable_quiz_integration:
            raise RuntimeError("Quiz integration is disabled")

        quiz_id = UUID()  # In production, get from quiz service
        flow_instance_id = UUID()  # In production, create actual flow

        # Map flow type based on quiz type
        flow_type_map = {
            "monthly": FlowType.MONTHLY_QUIZ,
            "symptom": FlowType.SYMPTOM_TRACKING,
            "onboarding": FlowType.ONBOARDING,
        }
        flow_type = flow_type_map.get(quiz_type, FlowType.CUSTOM)

        # Store mappings
        self._flow_to_quiz[flow_instance_id] = quiz_id
        self._quiz_to_flow[quiz_id] = flow_instance_id

        # Track quiz flow
        quiz_flow = {
            "quiz_id": quiz_id,
            "flow_instance_id": flow_instance_id,
            "patient_id": patient_id,
            "quiz_type": quiz_type,
            "flow_type": flow_type.value,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow()
            + timedelta(hours=self.config.quiz_timeout_hours),
            "data": quiz_data or {},
        }

        self._quiz_flows[flow_instance_id] = quiz_flow

        logger.info(
            f"Created quiz flow: {flow_instance_id} (type: {quiz_type}, "
            f"patient: {patient_id})"
        )

        return quiz_flow

    def start_quiz_flow(
        self,
        flow_instance_id: UUID,
        context: Optional[FlowContext] = None,
    ) -> bool:
        """
        Start a quiz flow.

        Args:
            flow_instance_id: Flow instance ID.
            context: Optional flow context.

        Returns:
            True if started successfully, False otherwise.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if not quiz_flow:
            logger.warning(f"Quiz flow not found: {flow_instance_id}")
            return False

        quiz_flow["status"] = "active"
        quiz_flow["started_at"] = datetime.utcnow()

        # In production: Call quiz service to start quiz
        # quiz_service.start_quiz(quiz_flow["quiz_id"])

        logger.info(f"Started quiz flow: {flow_instance_id}")
        return True

    # ========================================================================
    # Quiz Flow Monitoring
    # ========================================================================

    def get_quiz_flow_status(self, flow_instance_id: UUID) -> Optional[str]:
        """
        Get status of a quiz flow.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            Status string if found, None otherwise.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if not quiz_flow:
            return None

        return quiz_flow["status"]

    def is_quiz_flow_expired(self, flow_instance_id: UUID) -> bool:
        """
        Check if quiz flow has expired.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            True if expired, False otherwise.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if not quiz_flow:
            return False

        expires_at = quiz_flow.get("expires_at")
        if not expires_at:
            return False

        return datetime.utcnow() > expires_at

    def check_quiz_completion(self, flow_instance_id: UUID) -> bool:
        """
        Check if quiz has been completed.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            True if completed, False otherwise.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if not quiz_flow:
            return False

        # In production: Check with quiz service
        # return quiz_service.is_quiz_completed(quiz_flow["quiz_id"])

        return quiz_flow["status"] == "completed"

    # ========================================================================
    # Quiz Response Handling
    # ========================================================================

    def record_quiz_response(
        self,
        flow_instance_id: UUID,
        question_id: str,
        response: Any,
    ) -> bool:
        """
        Record a quiz response.

        Args:
            flow_instance_id: Flow instance ID.
            question_id: Question ID.
            response: Response value.

        Returns:
            True if recorded successfully, False otherwise.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if not quiz_flow:
            logger.warning(f"Quiz flow not found: {flow_instance_id}")
            return False

        # Store response
        if "responses" not in quiz_flow["data"]:
            quiz_flow["data"]["responses"] = {}

        quiz_flow["data"]["responses"][question_id] = {
            "value": response,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # In production: Send to quiz service
        # quiz_service.record_response(quiz_flow["quiz_id"], question_id, response)

        logger.debug(
            f"Recorded quiz response for flow {flow_instance_id}: "
            f"{question_id} = {response}"
        )

        return True

    def get_quiz_responses(
        self,
        flow_instance_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Get all quiz responses.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            Dictionary with responses, or None if not found.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if not quiz_flow:
            return None

        return quiz_flow["data"].get("responses", {})

    # ========================================================================
    # Quiz Completion
    # ========================================================================

    def complete_quiz_flow(
        self,
        flow_instance_id: UUID,
        final_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Complete a quiz flow.

        Args:
            flow_instance_id: Flow instance ID.
            final_data: Optional final quiz data.

        Returns:
            True if completed successfully, False otherwise.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if not quiz_flow:
            logger.warning(f"Quiz flow not found: {flow_instance_id}")
            return False

        quiz_flow["status"] = "completed"
        quiz_flow["completed_at"] = datetime.utcnow()

        if final_data:
            quiz_flow["data"].update(final_data)

        # In production: Notify quiz service
        # quiz_service.complete_quiz(quiz_flow["quiz_id"], final_data)

        logger.info(f"Completed quiz flow: {flow_instance_id}")
        return True

    def cancel_quiz_flow(
        self,
        flow_instance_id: UUID,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Cancel a quiz flow.

        Args:
            flow_instance_id: Flow instance ID.
            reason: Optional cancellation reason.

        Returns:
            True if cancelled successfully, False otherwise.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if not quiz_flow:
            logger.warning(f"Quiz flow not found: {flow_instance_id}")
            return False

        quiz_flow["status"] = "cancelled"
        quiz_flow["cancelled_at"] = datetime.utcnow()
        quiz_flow["cancellation_reason"] = reason

        # In production: Notify quiz service
        # quiz_service.cancel_quiz(quiz_flow["quiz_id"], reason)

        logger.info(f"Cancelled quiz flow: {flow_instance_id} (reason: {reason})")
        return True

    # ========================================================================
    # Quiz Reminders
    # ========================================================================

    def should_send_reminder(self, flow_instance_id: UUID) -> bool:
        """
        Check if reminder should be sent for quiz.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            True if reminder should be sent, False otherwise.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if not quiz_flow:
            return False

        # Don't send reminders for completed/cancelled flows
        if quiz_flow["status"] in ["completed", "cancelled"]:
            return False

        # Check if reminder interval has passed
        last_reminder = quiz_flow["data"].get("last_reminder_at")
        if last_reminder:
            last_reminder_dt = datetime.fromisoformat(last_reminder)
            time_since_reminder = datetime.utcnow() - last_reminder_dt
            if time_since_reminder < timedelta(
                hours=self.config.quiz_reminder_interval_hours
            ):
                return False

        return True

    def record_reminder_sent(self, flow_instance_id: UUID) -> None:
        """
        Record that a reminder was sent.

        Args:
            flow_instance_id: Flow instance ID.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if quiz_flow:
            quiz_flow["data"]["last_reminder_at"] = datetime.utcnow().isoformat()
            reminder_count = quiz_flow["data"].get("reminder_count", 0)
            quiz_flow["data"]["reminder_count"] = reminder_count + 1

    # ========================================================================
    # Quiz Data Access
    # ========================================================================

    def get_quiz_flow(self, flow_instance_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get quiz flow data.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            Quiz flow data if found, None otherwise.
        """
        return self._quiz_flows.get(flow_instance_id)

    def get_quiz_id_for_flow(self, flow_instance_id: UUID) -> Optional[UUID]:
        """
        Get quiz ID associated with flow.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            Quiz ID if found, None otherwise.
        """
        return self._flow_to_quiz.get(flow_instance_id)

    def get_flow_id_for_quiz(self, quiz_id: UUID) -> Optional[UUID]:
        """
        Get flow ID associated with quiz.

        Args:
            quiz_id: Quiz ID.

        Returns:
            Flow instance ID if found, None otherwise.
        """
        return self._quiz_to_flow.get(quiz_id)

    def list_active_quiz_flows(
        self,
        patient_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        List active quiz flows.

        Args:
            patient_id: Optional filter by patient ID.

        Returns:
            List of active quiz flows.
        """
        active_flows = []

        for quiz_flow in self._quiz_flows.values():
            if quiz_flow["status"] == "active":
                if patient_id is None or quiz_flow["patient_id"] == patient_id:
                    active_flows.append(quiz_flow)

        return active_flows

    # ========================================================================
    # Quiz Analytics
    # ========================================================================

    def get_quiz_flow_metrics(self, flow_instance_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get metrics for a quiz flow.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            Dictionary with metrics, or None if not found.
        """
        quiz_flow = self._quiz_flows.get(flow_instance_id)
        if not quiz_flow:
            return None

        metrics = {
            "quiz_id": str(quiz_flow["quiz_id"]),
            "flow_instance_id": str(flow_instance_id),
            "quiz_type": quiz_flow["quiz_type"],
            "status": quiz_flow["status"],
            "response_count": len(quiz_flow["data"].get("responses", {})),
            "reminder_count": quiz_flow["data"].get("reminder_count", 0),
        }

        # Calculate duration if completed
        if "started_at" in quiz_flow and "completed_at" in quiz_flow:
            started_at = quiz_flow["started_at"]
            completed_at = quiz_flow["completed_at"]
            duration = (completed_at - started_at).total_seconds()
            metrics["duration_seconds"] = duration

        return metrics

    def get_quiz_completion_rate(self, patient_id: UUID) -> float:
        """
        Get quiz completion rate for a patient.

        Args:
            patient_id: Patient ID.

        Returns:
            Completion rate (0.0 to 1.0).
        """
        patient_flows = [
            flow
            for flow in self._quiz_flows.values()
            if flow["patient_id"] == patient_id
        ]

        if not patient_flows:
            return 0.0

        completed = sum(1 for flow in patient_flows if flow["status"] == "completed")
        return completed / len(patient_flows)

    # ========================================================================
    # Cleanup
    # ========================================================================

    def cleanup_expired_flows(self) -> int:
        """
        Clean up expired quiz flows.

        Returns:
            Number of flows cleaned up.
        """
        expired_flows = []

        for flow_id, quiz_flow in self._quiz_flows.items():
            if self.is_quiz_flow_expired(flow_id):
                if quiz_flow["status"] not in ["completed", "cancelled"]:
                    expired_flows.append(flow_id)

        # Cancel expired flows
        for flow_id in expired_flows:
            self.cancel_quiz_flow(flow_id, reason="expired")

        if expired_flows:
            logger.info(f"Cleaned up {len(expired_flows)} expired quiz flows")

        return len(expired_flows)

    def cleanup_old_flows(self, days: int = 30) -> int:
        """
        Clean up old completed/cancelled flows.

        Args:
            days: Age threshold in days.

        Returns:
            Number of flows cleaned up.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        old_flows = []

        for flow_id, quiz_flow in self._quiz_flows.items():
            if quiz_flow["status"] in ["completed", "cancelled"]:
                completed_at = quiz_flow.get("completed_at") or quiz_flow.get(
                    "cancelled_at"
                )
                if completed_at and completed_at < cutoff_date:
                    old_flows.append(flow_id)

        # Remove old flows
        for flow_id in old_flows:
            quiz_id = self._flow_to_quiz.get(flow_id)
            if quiz_id:
                del self._quiz_to_flow[quiz_id]
                del self._flow_to_quiz[flow_id]
            del self._quiz_flows[flow_id]

        if old_flows:
            logger.info(f"Cleaned up {len(old_flows)} old quiz flows")

        return len(old_flows)


# ============================================================================
# Exports
# ============================================================================

__all__ = ["QuizFlowIntegration"]
