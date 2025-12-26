"""
Quiz Scheduling Module - Quiz Trigger and Execution Logic

Handles quiz scheduling, triggering, and execution for patient assessments.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.flow import PatientFlowState
from app.models.patient import Patient


logger = logging.getLogger(__name__)


class QuizScheduler:
    """
    Manages quiz scheduling and triggering.

    Responsibilities:
    - Determine when quizzes should be triggered
    - Execute quiz flow steps
    - Calculate monthly assessment cycles
    - Coordinate quiz delivery
    """

    def __init__(self, db: Session):
        """
        Initialize QuizScheduler.

        Args:
            db: Database session
        """
        self.db = db

        logger.info("QuizScheduler initialized")

    async def should_trigger_quiz(
        self, flow_type: str, current_day: int, flow_state: PatientFlowState
    ) -> bool:
        """
        Determine if quiz should be triggered for current flow step.

        Args:
            flow_type: Current flow type
            current_day: Current treatment day
            flow_state: Current flow state

        Returns:
            True if quiz should be triggered
        """
        try:
            # Use centralized quiz trigger policy
            from app.domain.quizzes.quiz_trigger_policy import QuizTriggerPolicy
            from app.repositories.patient import PatientRepository

            # Get patient enrollment info if available
            days_since_enrollment = None
            try:
                patient_repo = PatientRepository(self.db)
                patient = patient_repo.get(flow_state.patient_id)
                if patient:
                    enrollment_date = patient.enrollment_date or patient.created_at
                    days_since_enrollment = (datetime.now(timezone.utc) - enrollment_date).days
            except Exception as e:
                logger.warning(f"Could not get patient enrollment info: {e}")

            # Check using centralized policy
            is_quiz_day = QuizTriggerPolicy.is_quiz_day(
                current_day, flow_type, days_since_enrollment
            )

            if is_quiz_day:
                logger.info(
                    f"Quiz triggered for {flow_type} flow on day {current_day} "
                    f"(days since enrollment: {days_since_enrollment})"
                )

            return is_quiz_day

        except Exception as e:
            logger.error(f"Error checking quiz trigger: {e}")
            return False

    async def execute_quiz_step(
        self,
        patient_id: UUID,
        flow_state: PatientFlowState,
        flow_type: str,
        current_day: int,
    ) -> Dict[str, Any]:
        """
        Execute quiz-specific flow step.

        Args:
            patient_id: Patient UUID
            flow_state: Current flow state
            flow_type: Current flow type
            current_day: Current treatment day

        Returns:
            Quiz execution result
        """
        try:
            # Import quiz-specific services
            from app.domain.quizzes.integration.flow_integration import (
                QuizTriggerService,
            )
            from app.repositories.patient import PatientRepository

            quiz_trigger_service = QuizTriggerService(self.db)
            patient_repo = PatientRepository(self.db)

            # Get patient information
            patient = patient_repo.get(patient_id)
            if not patient:
                return {
                    "success": False,
                    "message": "Patient not found",
                    "error": "Patient not found",
                }

            # Calculate monthly cycle for quiz
            enrollment_date = patient.enrollment_date or patient.created_at
            days_since_enrollment = (datetime.now(timezone.utc) - enrollment_date).days

            # Determine quiz type based on flow phase
            if days_since_enrollment <= 45:
                quiz_type = "initial_assessment"
                monthly_cycle = 1
            else:
                days_in_monthly_phase = days_since_enrollment - 45
                monthly_cycle = (days_in_monthly_phase // 30) + 1
                quiz_type = "monthly_assessment"

            quiz_info = {
                "monthly_cycle": monthly_cycle,
                "template_name": f"{quiz_type}_cycle_{monthly_cycle}",
                "trigger_reason": f"Scheduled quiz for day {current_day}",
                "quiz_type": quiz_type,
            }

            # Trigger quiz
            result = await quiz_trigger_service._trigger_patient_quiz(
                flow_state=flow_state, quiz_info=quiz_info
            )

            logger.info(
                f"Quiz executed for patient {patient_id}: {quiz_type} cycle {monthly_cycle}"
            )

            return {
                "success": result.get("success", False),
                "message": "Quiz step executed",
                "quiz_triggered": True,
                "quiz_session_id": result.get("session_id"),
                "delivery_method": result.get("delivery_method"),
                "quiz_type": quiz_type,
                "monthly_cycle": monthly_cycle,
            }

        except Exception as e:
            logger.error(f"Error executing quiz step: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Quiz step execution failed: {str(e)}",
                "error": str(e),
            }

    async def schedule_monthly_assessment(
        self,
        patient: Patient,
        assessment_date: datetime,
        flow_state_creator: callable,
        analytics_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Schedule monthly assessment for patient.

        Args:
            patient: Patient object
            assessment_date: Assessment date
            flow_state_creator: Function to create flow state
            analytics_callback: Optional callback for analytics tracking

        Returns:
            Scheduling result dictionary
        """
        try:
            # Create quiz-specific flow context
            metadata = {
                "assessment_type": "monthly",
                "scheduled_for": assessment_date.isoformat(),
                "auto_scheduled": True,
            }

            # Create flow state for quiz
            quiz_flow_state = flow_state_creator(
                patient=patient,
                flow_type="quiz_monthly",
                current_day=1,
                operation="START",
                metadata=metadata,
            )

            # Execute quiz step
            quiz_result = await self.execute_quiz_step(
                patient_id=patient.id,
                flow_state=quiz_flow_state,
                flow_type="quiz_monthly",
                current_day=1,
            )

            # Track analytics if callback provided
            if analytics_callback:
                await analytics_callback(
                    patient_id=patient.id,
                    event_type="monthly_assessment_scheduled",
                    flow_type="quiz_monthly",
                    current_day=1,
                    metadata={
                        "assessment_date": assessment_date.isoformat(),
                        "quiz_result": quiz_result,
                    },
                )

            logger.info(
                f"Monthly assessment scheduled for patient {patient.id} on {assessment_date}"
            )

            return {
                "success": quiz_result.get("success", False),
                "message": "Monthly assessment scheduled",
                "assessment_date": assessment_date.isoformat(),
                "quiz_session_id": quiz_result.get("quiz_session_id"),
                "delivery_method": quiz_result.get("delivery_method"),
            }

        except Exception as e:
            logger.error(f"Error scheduling monthly assessment: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Monthly assessment scheduling failed: {str(e)}",
                "error": str(e),
            }
