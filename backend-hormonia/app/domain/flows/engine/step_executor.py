"""
Step executor for flow processing.
Handles step scheduling, execution, and action coordination.
"""

from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy.orm import Session

from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.models.message import MessageType
from app.repositories.patient import PatientRepository
from app.services.template_loader import FlowStep
from app.services.state_machine import StateMachine
from app.domain.messaging.core import MessageService
from app.services.quiz import QuizSessionService, QuizResponseService
from app.schemas.quiz import QuizSessionCreate, QuizResponseCreate, QuestionType
from app.config import is_ai_humanization_enabled
from app.core.async_context_manager import safe_create_task
from app.utils.db_retry import with_db_retry
from app.services.question_humanizer import get_question_humanizer

logger = logging.getLogger(__name__)


class StepExecutor:
    """Executes flow steps with intelligent humanization."""

    def __init__(self, db: Session):
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.message_service = MessageService(db)
        self.quiz_session_service = QuizSessionService(db)
        self.quiz_response_service = QuizResponseService(db)

    @with_db_retry(max_retries=3)
    async def schedule_step(
        self,
        flow_state: PatientFlowState,
        step: FlowStep,
        base_time: datetime,
        condition_evaluator=None,
    ) -> None:
        """Schedule actions for the given step based on its type with intelligent humanization."""
        scheduled_for = base_time + timedelta(hours=step.delay_hours)

        if step.type == "message" or step.type == "quiz":
            # Get original content
            original_content = step.content

            # Determine question type for selective humanization
            from app.domain.flows.engine.condition_evaluator import ConditionEvaluator

            if condition_evaluator is None:
                condition_evaluator = ConditionEvaluator(self.db)

            question_type = condition_evaluator.determine_question_type(step)

            # Apply intelligent question humanization if enabled
            try:
                patient = self.patient_repo.get(flow_state.patient_id)

                humanized_content = original_content

                if patient and is_ai_humanization_enabled():
                    question_humanizer = get_question_humanizer()

                    if step.type == "quiz":
                        question_id = getattr(
                            step, "name", f"quiz_step_{flow_state.current_step}"
                        )
                        humanized_content = (
                            await question_humanizer.humanize_quiz_question(
                                question=original_content,
                                question_id=question_id,
                                patient_id=str(flow_state.patient_id),
                                quiz_type=flow_state.state_data.get(
                                    "requested_flow_type", "monthly"
                                ),
                            )
                        )
                    else:
                        humanized_content = await question_humanizer.humanize_question(
                            question=original_content,
                            question_type=question_type,
                            patient=patient,
                            context={
                                "step_type": step.type,
                                "step_name": getattr(step, "name", "unknown"),
                                "flow_data": flow_state.state_data,
                            },
                        )
            except Exception as e:
                logger.error(f"Error in question humanization: {e}")
                humanized_content = original_content  # Safe fallback

            # Schedule outbound message for both message and quiz steps
            message = self.message_service.schedule_message(
                flow_state.patient_id,
                humanized_content,
                scheduled_for,
                message_type=MessageType.TEXT,
                message_metadata={
                    "original_content": original_content,
                    "humanized": humanized_content != original_content,
                    "step_type": step.type,
                    "question_type": question_type,
                    "flow_step_id": step.name if hasattr(step, "name") else "unknown",
                    "ai_processing": "question_humanizer",
                },
            )
            from app.tasks.messaging import send_scheduled_message

            send_scheduled_message.apply_async((str(message.id),), eta=scheduled_for)

        if step.type == "quiz" and step.quiz_template:
            # Start quiz session so responses can be collected
            template = self.quiz_session_service.template_repository.get_by_name(
                step.quiz_template
            )
            if template:
                session_data = QuizSessionCreate(
                    patient_id=flow_state.patient_id,
                    quiz_template_id=template.id,
                )
                # Create safe async task for quiz session start
                safe_create_task(
                    self.quiz_session_service.start_quiz_session(session_data),
                    name=f"quiz_session_start_{flow_state.patient_id}",
                    context={
                        "step_type": step.type,
                        "patient_id": str(flow_state.patient_id),
                    },
                )

    @with_db_retry(max_retries=3)
    async def schedule_step_actions(
        self,
        patient: Patient,
        step_id: int,
        state_machine: StateMachine,
        condition_evaluator=None,
    ) -> None:
        """Schedule actions for a specific flow step with AI humanization."""
        step = state_machine.get_current_step(step_id)
        if not step:
            return

        scheduled_for = datetime.now(timezone.utc) + timedelta(hours=step.delay_hours)

        # Get original content
        original_content = step.content

        # Apply AI humanization if enabled
        try:
            from app.domain.flows.engine.condition_evaluator import ConditionEvaluator

            if condition_evaluator is None:
                condition_evaluator = ConditionEvaluator(self.db)

            # FIXED: Direct async/await call - no more event loop creation
            humanized_content = await condition_evaluator.humanize_message_content(
                content=original_content,
                patient_id=patient.id,
                message_type=getattr(step, "type", "general"),
                context_builder=None,  # Pass if available
            )
        except Exception as e:
            logger.error(f"Error in step action humanization: {e}")
            humanized_content = original_content  # Fallback to original

        # Always schedule the step content as a message
        self.message_service.schedule_message(
            patient_id=patient.id,
            content=humanized_content,
            scheduled_for=scheduled_for,
            message_metadata={
                **(step.metadata or {}),
                "original_content": original_content,
                "humanized": humanized_content != original_content,
                "ai_processing_applied": True,
            },
        )

        # For quiz steps, start a session and log placeholder response
        if step.type == "quiz" and step.quiz_template:
            template = self.quiz_session_service.template_repository.get_by_name(
                step.quiz_template
            )
            if template:
                session_data = QuizSessionCreate(
                    patient_id=patient.id,
                    quiz_template_id=template.id,
                )
                # Create safe async tasks for quiz operations
                safe_create_task(
                    self.quiz_session_service.start_quiz_session(session_data),
                    name=f"quiz_session_{patient.id}",
                    context={
                        "patient_id": str(patient.id),
                        "template_id": str(template.id),
                    },
                )

                # Use humanized content for quiz question text
                placeholder = QuizResponseCreate(
                    patient_id=patient.id,
                    quiz_template_id=template.id,
                    question_id="__start__",
                    question_text=humanized_content,  # Use humanized content
                    response_type=QuestionType.OPEN_TEXT,
                    response_value="",
                    response_metadata={
                        "scheduled": True,
                        "original_question": original_content,
                        "humanized": humanized_content != original_content,
                    },
                    responded_at=scheduled_for,
                )
                safe_create_task(
                    self.quiz_response_service.create_response(placeholder),
                    name=f"quiz_response_{patient.id}",
                    context={"patient_id": str(patient.id), "question_id": "__start__"},
                )
