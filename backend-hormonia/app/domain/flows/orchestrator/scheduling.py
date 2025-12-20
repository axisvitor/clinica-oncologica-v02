"""
Flow Orchestrator - Scheduling Module

Handles quiz and follow-up scheduling orchestration for flow execution.
"""

import logging
from typing import Dict, Any, Optional, Callable
from uuid import UUID
from datetime import datetime, timezone

from app.models.patient import Patient
from app.utils.date_helpers import get_next_scheduled_time
from ..scheduling import QuizScheduler, FollowUpScheduler
from .models import FlowExecutionResult, FlowOperationType

logger = logging.getLogger(__name__)


class FlowSchedulingOrchestrator:
    """Orchestrates quiz and follow-up scheduling for flow execution."""

    def __init__(
        self, quiz_scheduler: QuizScheduler, follow_up_scheduler: FollowUpScheduler
    ):
        """
        Initialize FlowSchedulingOrchestrator.

        Args:
            quiz_scheduler: QuizScheduler instance
            follow_up_scheduler: FollowUpScheduler instance
        """
        self.quiz_scheduler = quiz_scheduler
        self.follow_up_scheduler = follow_up_scheduler

    async def execute_quiz_step(
        self, patient_id: UUID, flow_state: Any, flow_type: str, current_day: int
    ) -> Dict[str, Any]:
        """
        Execute quiz step if needed.

        Args:
            patient_id: UUID of patient
            flow_state: Current flow state
            flow_type: Type of flow
            current_day: Current treatment day

        Returns:
            Dict containing execution result
        """
        try:
            if await self.quiz_scheduler.should_trigger_quiz(
                flow_type, current_day, flow_state
            ):
                return await self.quiz_scheduler.execute_quiz_step(
                    patient_id, flow_state, flow_type, current_day
                )

            return {
                "success": True,
                "message": "No quiz scheduled for this day",
                "quiz_triggered": False,
            }

        except Exception as e:
            logger.error(
                f"Error executing quiz step: {e}",
                extra={
                    "patient_id": str(patient_id),
                    "flow_type": flow_type,
                    "day": current_day,
                },
            )
            return {
                "success": False,
                "message": f"Quiz execution failed: {str(e)}",
                "error": str(e),
                "quiz_triggered": False,
            }

    async def schedule_monthly_assessment(
        self,
        patient: Patient,
        assessment_date: Optional[datetime],
        flow_state_creator: Callable,
        analytics_callback: Callable,
        logger_instance: Optional[logging.Logger] = None,
    ) -> FlowExecutionResult:
        """
        Schedule monthly assessment for patient.

        Args:
            patient: Patient model instance
            assessment_date: Optional date for assessment
            flow_state_creator: Callback to create flow state
            analytics_callback: Callback for analytics tracking
            logger_instance: Optional logger instance

        Returns:
            FlowExecutionResult with scheduling outcome
        """
        log = logger_instance or logger
        patient_id = patient.id

        try:
            # Calculate assessment timing
            if assessment_date is None:
                assessment_date = get_next_scheduled_time("monthly")

            # Schedule assessment
            result = await self.quiz_scheduler.schedule_monthly_assessment(
                patient=patient,
                assessment_date=assessment_date,
                flow_state_creator=flow_state_creator,
                analytics_callback=analytics_callback,
            )

            return FlowExecutionResult(
                success=result.get("success", False),
                patient_id=patient_id,
                operation=FlowOperationType.START,
                message=result.get("message", "Monthly assessment scheduled"),
                data=result,
            )

        except Exception as e:
            log.error(
                f"Error scheduling monthly assessment: {e}",
                extra={"patient_id": str(patient_id)},
            )

            return FlowExecutionResult(
                success=False,
                patient_id=patient_id,
                operation=FlowOperationType.START,
                message=f"Monthly assessment scheduling failed: {str(e)}",
                errors=[str(e)],
            )
