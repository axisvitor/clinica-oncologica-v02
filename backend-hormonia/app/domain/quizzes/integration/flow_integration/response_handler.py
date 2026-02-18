"""
Conversational quiz service for managing quiz presentation via WhatsApp.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, List, Dict
from datetime import datetime, timezone
from uuid import UUID
import re

from sqlalchemy.orm import Session

from app.services.quiz import (
    QuizSessionService,
    QuizResponseService,
    QuizTemplateService,
)
from app.domain.messaging.delivery.idempotent_sender import IdempotentMessageSender
from app.domain.messaging.core import MessageFactory
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.schemas.quiz import QuizResponseCreate, QuestionType
from app.ai.client import get_gemini_client
from app.domain.analytics.quiz import get_quiz_metrics_collector

from .enums import QuizFlowState
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class ConversationalQuizService:
    """Service for managing conversational quiz presentation via WhatsApp."""

    def __init__(self, db: Session):
        self.db = db
        self.quiz_session_service = QuizSessionService(db)
        self.quiz_response_service = QuizResponseService(db)
        self.quiz_template_service = QuizTemplateService(db)
        self.message_sender = IdempotentMessageSender(db)
        self.flow_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self.message_factory = MessageFactory(db)

    @staticmethod
    def _resolve_option_value(option: Any) -> str:
        """Resolve option value safely, even when 'value' key is missing."""
        if isinstance(option, dict):
            raw_value = option.get("value")
            if raw_value is None:
                raw_value = option.get("text") or option.get("label")
            return str(raw_value).strip() if raw_value is not None else ""

        return str(option).strip() if option is not None else ""

    async def process_quiz_response(
        self,
        patient_id: UUID,
        response_text: str,
        message_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Process patient response to quiz question.

        Args:
            patient_id: Patient ID
            response_text: Patient's response text
            message_metadata: Original message metadata

        Returns:
            Processing result
        """
        try:
            # Get active quiz session
            active_session = self.quiz_session_service.get_active_session(patient_id)

            if not active_session:
                return {
                    "success": False,
                    "error": "No active quiz session found",
                    "action": "ignore",
                }

            # Get quiz template
            template = await self.quiz_template_service.get_template(
                active_session.quiz_template_id
            )
            questions = template.questions

            if active_session.current_question_index >= len(questions):
                return {
                    "success": False,
                    "error": "Quiz already completed",
                    "action": "complete_session",
                }

            current_question = questions[active_session.current_question_index]

            # Validate and process response
            processed_response = await self._process_question_response(
                current_question, response_text, patient_id
            )

            if not processed_response["valid"]:
                # Send clarification message
                await self._send_clarification_message(
                    patient_id, current_question, processed_response["error"]
                )

                return {
                    "success": False,
                    "error": processed_response["error"],
                    "action": "request_clarification",
                }

            # Save response
            response_data = QuizResponseCreate(
                patient_id=patient_id,
                quiz_template_id=active_session.quiz_template_id,
                quiz_session_id=active_session.id,
                question_id=current_question["id"],
                question_text=current_question["text"],
                response_type=current_question["type"],
                response_value=processed_response["value"],
                response_metadata={
                    "original_text": response_text,
                    "processed_value": processed_response["value"],
                    "session_id": str(active_session.id),
                    "question_index": active_session.current_question_index,
                },
                responded_at=now_sao_paulo(),
            )

            self.quiz_response_service.create_response(response_data)

            # Record response latency metric
            try:
                # Calculate latency from question sent to response received
                # (message_metadata should contain question_sent_at timestamp)
                if message_metadata and "question_sent_at" in message_metadata:
                    question_sent_at = message_metadata["question_sent_at"]
                    if isinstance(question_sent_at, str):
                        question_sent_at = datetime.fromisoformat(question_sent_at)

                    response_latency = (
                        now_sao_paulo() - question_sent_at
                    ).total_seconds()

                    metrics = await get_quiz_metrics_collector()
                    await metrics.record_response_latency(
                        template_id=active_session.quiz_template_id,
                        question_id=current_question["id"],
                        session_id=active_session.id,
                        latency_seconds=response_latency,
                    )
            except Exception as e:
                logger.debug(f"Failed to record response latency metric: {e}")

            # Advance to next question or complete quiz
            if active_session.current_question_index >= len(questions) - 1:
                # Complete quiz
                await self._complete_quiz_session(active_session, patient_id)

                return {
                    "success": True,
                    "action": "quiz_completed",
                    "session_id": str(active_session.id),
                }
            else:
                # Advance to next question
                advanced_session = self.quiz_session_service.advance_session(
                    active_session.id
                )
                next_question_index = (
                    advanced_session.current_question_index
                    if advanced_session
                    else active_session.current_question_index + 1
                )

                # Send next question
                await self._send_next_question(
                    patient_id,
                    active_session,
                    questions,
                    next_question_index,
                )

                return {
                    "success": True,
                    "action": "next_question",
                    "question_index": next_question_index,
                }

        except Exception as e:
            logger.error(f"Error processing quiz response: {e}")
            return {"success": False, "error": str(e), "action": "error"}

    async def _process_question_response(
        self, question: dict[str, Any], response_text: str, patient_id: UUID
    ) -> dict[str, Any]:
        """Process and validate question response."""
        try:
            question_type = question["type"]
            if question_type == QuestionType.SINGLE_CHOICE.value:
                question_type = QuestionType.MULTIPLE_CHOICE.value
            elif question_type == "free_text":
                question_type = QuestionType.OPEN_TEXT.value
            response_text = response_text.strip()

            if question_type == QuestionType.OPEN_TEXT.value:
                return {"valid": True, "value": response_text, "type": "text"}

            elif question_type == QuestionType.SCALE.value:
                # Try to extract number from response
                numbers = re.findall(r"\d+", response_text)

                if not numbers:
                    # Use AI to interpret response
                    interpreted_value = await self._interpret_scale_response(
                        response_text, question
                    )
                    if interpreted_value:
                        return {
                            "valid": True,
                            "value": str(interpreted_value),
                            "type": "scale",
                            "interpreted": True,
                        }

                    return {
                        "valid": False,
                        "error": "Por favor, responda com um número de 1 a 5",
                    }

                scale_value = int(numbers[0])
                if 1 <= scale_value <= 5:
                    return {"valid": True, "value": str(scale_value), "type": "scale"}
                else:
                    return {
                        "valid": False,
                        "error": "Por favor, escolha um número entre 1 e 5",
                    }

            elif question_type == QuestionType.MULTIPLE_CHOICE.value:
                # Try to match response with options
                options = question.get("options", [])

                # Direct text match
                for option in options:
                    if isinstance(option, dict):
                        option_text = option.get("text") or option.get("label") or ""
                    else:
                        option_text = str(option)

                    if not option_text:
                        continue
                    if (
                        response_text.lower() in option_text.lower()
                        or option_text.lower() in response_text.lower()
                    ):
                        option_value = self._resolve_option_value(option)
                        if not option_value:
                            continue
                        return {
                            "valid": True,
                            "value": option_value,
                            "type": "multiple_choice",
                        }

                # Use AI to interpret response
                interpreted_option = await self._interpret_multiple_choice_response(
                    response_text, options
                )

                if interpreted_option:
                    return {
                        "valid": True,
                        "value": interpreted_option,
                        "type": "multiple_choice",
                        "interpreted": True,
                    }

                # Show options again
                options_text = "\n".join(
                    [
                        f"• {opt.get('text') or opt.get('label') or self._resolve_option_value(opt)}"
                        if isinstance(opt, dict)
                        else f"• {self._resolve_option_value(opt)}"
                        for opt in options
                    ]
                )
                return {
                    "valid": False,
                    "error": f"Por favor, escolha uma das opções:\n{options_text}",
                }

            elif question_type == QuestionType.YES_NO.value:
                response_lower = response_text.lower()

                yes_words = ["sim", "yes", "s", "claro", "certamente", "com certeza"]
                no_words = ["não", "nao", "no", "n", "nunca", "jamais"]

                if any(word in response_lower for word in yes_words):
                    return {"valid": True, "value": "yes", "type": "yes_no"}
                elif any(word in response_lower for word in no_words):
                    return {"valid": True, "value": "no", "type": "yes_no"}
                else:
                    return {
                        "valid": False,
                        "error": "Por favor, responda com 'sim' ou 'não'",
                    }

            else:
                return {"valid": False, "error": "Tipo de pergunta não suportado"}

        except Exception as e:
            logger.error(f"Error processing question response: {e}")
            return {"valid": False, "error": "Erro ao processar resposta"}

    async def _interpret_scale_response(
        self, response_text: str, question: dict[str, Any]
    ) -> Optional[int]:
        """Use AI to interpret scale response."""
        try:
            gemini_client = get_gemini_client()

            prompt = f"""
            Analise a resposta do paciente para uma pergunta de escala de 1 a 5:

            Pergunta: {question["text"]}
            Resposta do paciente: "{response_text}"

            Escala:
            1 = Muito ruim/baixo/negativo
            2 = Ruim/baixo/negativo
            3 = Neutro/regular/médio
            4 = Bom/alto/positivo
            5 = Muito bom/alto/positivo

            Retorne apenas o número (1-5) que melhor representa a resposta do paciente.
            Se não conseguir interpretar, retorne "INVALID".
            """

            response = await gemini_client.generate_content(prompt)

            if response and response.strip().isdigit():
                value = int(response.strip())
                if 1 <= value <= 5:
                    return value

            return None

        except Exception as e:
            logger.error(f"Error interpreting scale response: {e}")
            return None

    async def _interpret_multiple_choice_response(
        self, response_text: str, options: List[dict[str, Any]]
    ) -> Optional[str]:
        """Use AI to interpret multiple choice response."""
        try:
            gemini_client = get_gemini_client()

            option_values: List[str] = []
            rendered_options: List[str] = []
            for opt in options:
                opt_value = self._resolve_option_value(opt)
                if not opt_value:
                    continue
                option_values.append(opt_value)
                if isinstance(opt, dict):
                    opt_label = opt.get("text") or opt.get("label") or opt_value
                else:
                    opt_label = str(opt)
                rendered_options.append(f"- {opt_value}: {opt_label}")

            options_text = "\n".join(rendered_options)

            prompt = f"""
            Analise a resposta do paciente e determine qual opção ela melhor representa:

            Resposta do paciente: "{response_text}"

            Opções disponíveis:
            {options_text}

            Retorne apenas o valor (value) da opção que melhor corresponde à resposta.
            Se não conseguir determinar, retorne "INVALID".
            """

            response = await gemini_client.generate_content(prompt)

            if response and response.strip() != "INVALID":
                # Validate that returned value exists in options
                if response.strip() in option_values:
                    return response.strip()

            return None

        except Exception as e:
            logger.error(f"Error interpreting multiple choice response: {e}")
            return None

    async def _send_clarification_message(
        self, patient_id: UUID, question: dict[str, Any], error_message: str
    ):
        """Send clarification message for invalid response."""
        try:
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return

            # Create message using factory
            message = self.message_factory.create_quiz_clarification(
                patient_id=patient_id,
                patient_name=patient.name,
                question=question,
                error_message=error_message,
            )

            await self.message_sender.send_message(message)

        except Exception as e:
            logger.error(f"Error sending clarification message: {e}")

    async def _send_next_question(
        self,
        patient_id: UUID,
        session: Any,
        questions: List[Dict[str, Any]],
        question_index: int,
    ):
        """Send next quiz question."""
        try:
            if question_index >= len(questions):
                return

            patient = self.patient_repo.get(patient_id)
            if not patient:
                return

            question = questions[question_index]

            # Create message using factory
            message = self.message_factory.create_quiz_message(
                patient_id=patient_id,
                question=question,
                session_id=str(session.id),
                question_index=question_index,
                total_questions=len(questions),
                patient_name=patient.name,
            )

            await self.message_sender.send_message(message)

        except Exception as e:
            logger.error(f"Error sending next question: {e}")

    async def _complete_quiz_session(self, session: Any, patient_id: UUID):
        """Complete quiz session and send completion message."""
        try:
            # Complete the session
            self.quiz_session_service.complete_session(session.id)

            # Schedule report generation
            from app.tasks.flows import generate_quiz_report

            report_task = generate_quiz_report.delay(str(session.id))
            logger.info(f"Scheduled quiz report generation: task {report_task.id}")

            # Update flow state and detect delivery method
            delivery_method = "whatsapp_conversational"  # default
            flow_states = self.flow_repo.get_by_patient_id(patient_id)
            for flow_state in flow_states:
                if flow_state.state_data and flow_state.state_data.get(
                    "quiz_session_id"
                ) == str(session.id):
                    flow_state.state_data["quiz_state"] = QuizFlowState.COMPLETED.value
                    flow_state.state_data["quiz_completed_at"] = (
                        now_sao_paulo().isoformat()
                    )

                    # Get delivery method from flow state
                    delivery_method = flow_state.state_data.get(
                        "quiz_delivery_method", "whatsapp_conversational"
                    )
                    break

            self.db.commit()

            # Send appropriate completion message based on delivery method
            patient = self.patient_repo.get(patient_id)
            if patient:
                if delivery_method == "link":
                    # Use MonthlyQuizMessageIntegration for link completion
                    from app.services.monthly_quiz_message_integration import (
                        MonthlyQuizMessageIntegration,
                    )

                    quiz_integration = MonthlyQuizMessageIntegration(self.db)

                    await quiz_integration.send_completion_confirmation(
                        quiz_session_id=session.id
                    )
                    logger.info(
                        f"Sent link-based completion message for patient {patient_id}"
                    )
                else:
                    # Use MessageFactory for conversational completion
                    message = self.message_factory.create_quiz_completion(
                        patient_id=patient_id,
                        patient_name=patient.name,
                        session_id=str(session.id),
                    )

                    await self.message_sender.send_message(message)
                    logger.info(
                        f"Sent conversational completion message for patient {patient_id}"
                    )

        except Exception as e:
            logger.error(f"Error completing quiz session: {e}")

    async def pause_quiz_session(self, patient_id: UUID) -> Dict[str, Any]:
        """Pause active quiz session."""
        try:
            active_session = self.quiz_session_service.get_active_session(patient_id)

            if not active_session:
                return {"success": False, "error": "No active quiz session found"}

            # Update flow state
            flow_states = self.flow_repo.get_by_patient_id(patient_id)
            for flow_state in flow_states:
                if flow_state.state_data and flow_state.state_data.get(
                    "quiz_session_id"
                ) == str(active_session.id):
                    flow_state.state_data["quiz_state"] = QuizFlowState.PAUSED.value
                    flow_state.state_data["quiz_paused_at"] = (
                        now_sao_paulo().isoformat()
                    )
                    break

            self.db.commit()

            # Send pause confirmation
            patient = self.patient_repo.get(patient_id)
            if patient:
                # Create message using factory
                message = self.message_factory.create_quiz_pause(
                    patient_id=patient_id,
                    patient_name=patient.name,
                    session_id=str(active_session.id),
                )

                await self.message_sender.send_message(message)

            return {
                "success": True,
                "session_id": str(active_session.id),
                "action": "paused",
            }

        except Exception as e:
            logger.error(f"Error pausing quiz session: {e}")
            return {"success": False, "error": str(e)}

    async def resume_quiz_session(self, patient_id: UUID) -> Dict[str, Any]:
        """Resume paused quiz session."""
        try:
            active_session = self.quiz_session_service.get_active_session(patient_id)

            if not active_session:
                return {"success": False, "error": "No active quiz session found"}

            # Check if session is paused
            flow_states = self.flow_repo.get_by_patient_id(patient_id)
            is_paused = False

            for flow_state in flow_states:
                if flow_state.state_data and flow_state.state_data.get(
                    "quiz_session_id"
                ) == str(active_session.id):
                    if (
                        flow_state.state_data.get("quiz_state")
                        == QuizFlowState.PAUSED.value
                    ):
                        is_paused = True
                        flow_state.state_data["quiz_state"] = (
                            QuizFlowState.IN_PROGRESS.value
                        )
                        flow_state.state_data["quiz_resumed_at"] = (
                            now_sao_paulo().isoformat()
                        )
                    break

            if not is_paused:
                return {"success": False, "error": "Quiz session is not paused"}

            self.db.commit()

            # Get current question and send it
            template = await self.quiz_template_service.get_template(
                active_session.quiz_template_id
            )
            questions = template.questions

            if active_session.current_question_index < len(questions):
                await self._send_next_question(
                    patient_id,
                    active_session,
                    questions,
                    active_session.current_question_index,
                )

            return {
                "success": True,
                "session_id": str(active_session.id),
                "action": "resumed",
                "current_question": active_session.current_question_index,
            }

        except Exception as e:
            logger.error(f"Error resuming quiz session: {e}")
            return {"success": False, "error": str(e)}
