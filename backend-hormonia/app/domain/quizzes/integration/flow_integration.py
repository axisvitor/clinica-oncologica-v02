"""
Quiz trigger and flow integration system.
Handles monthly quiz initiation, conversational quiz presentation, and flow integration.
"""
import logging
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session

from app.models.quiz import QuizTemplate, QuizSession, QuizResponse
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.models.message import Message
from app.services.quiz import QuizTemplateService, QuizSessionService, QuizResponseService
from app.services.enhanced_flow_engine import get_enhanced_flow_engine, FlowType
from app.domain.messaging.delivery import MessageSender
from app.domain.messaging.core import MessageFactory
from app.domain.analytics.quiz import get_quiz_metrics_collector
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.schemas.quiz import QuizSessionCreate, QuizResponseCreate, QuestionType, QuizSessionResponse
from app.exceptions import NotFoundError, ValidationError
from app.integrations.gemini_client import get_gemini_client
from app.core.monthly_quiz_config import get_monthly_quiz_config
from app.services.monthly_quiz_message_integration import MonthlyQuizMessageIntegration
from app.schemas.monthly_quiz import DeliveryMethod

logger = logging.getLogger(__name__)


class QuizFlowState(Enum):
    """Quiz flow states."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AWAITING_RESPONSE = "awaiting_response"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class QuizTriggerService:
    """Service for triggering monthly quizzes within flow system."""
    
    def __init__(self, db: Session):
        self.db = db
        self.quiz_template_service = QuizTemplateService(db)
        self.quiz_session_service = QuizSessionService(db)
        self.flow_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self.message_sender = MessageSender(db)
        self.message_factory = MessageFactory(db)
    
    async def check_and_trigger_monthly_quizzes(self, limit: int = 50) -> dict[str, Any]:
        """
        Check for patients due for monthly quizzes and trigger them.
        
        Args:
            limit: Maximum number of patients to process
            
        Returns:
            Processing results
        """
        try:
            logger.info(f"Checking for patients due for monthly quizzes (limit: {limit})")
            
            # Get patients in monthly recurring flow
            monthly_flows = self.flow_repo.get_flows_by_type(
                flow_type=FlowType.MONTHLY_RECURRING.value,
                limit=limit
            )
            
            results = {
                "checked_patients": 0,
                "quizzes_triggered": 0,
                "already_completed": 0,
                "errors": [],
                "triggered_patients": []
            }
            
            for flow_state in monthly_flows:
                try:
                    results["checked_patients"] += 1
                    
                    # Check if patient is due for quiz
                    is_due, quiz_info = await self._is_patient_due_for_quiz(flow_state)
                    
                    if is_due:
                        # Trigger quiz for patient
                        trigger_result = await self._trigger_patient_quiz(
                            flow_state, quiz_info
                        )
                        
                        if trigger_result["success"]:
                            results["quizzes_triggered"] += 1
                            results["triggered_patients"].append({
                                "patient_id": str(flow_state.patient_id),
                                "quiz_template": quiz_info["template_name"],
                                "trigger_reason": quiz_info["trigger_reason"]
                            })
                        else:
                            results["errors"].append({
                                "patient_id": str(flow_state.patient_id),
                                "error": trigger_result["error"]
                            })
                    else:
                        if quiz_info.get("already_completed"):
                            results["already_completed"] += 1
                
                except Exception as e:
                    logger.error(f"Error checking patient {flow_state.patient_id} for quiz: {e}")
                    results["errors"].append({
                        "patient_id": str(flow_state.patient_id),
                        "error": str(e)
                    })
            
            logger.info(f"Monthly quiz check completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to check monthly quizzes: {e}")
            raise
    
    async def _is_patient_due_for_quiz(self, flow_state: PatientFlowState) -> tuple[bool, dict[str, Any]]:
        """
        Check if patient is due for monthly quiz.
        
        Args:
            flow_state: Patient flow state
            
        Returns:
            Tuple of (is_due, quiz_info)
        """
        try:
            patient = self.patient_repo.get(flow_state.patient_id)
            if not patient:
                return False, {"error": "Patient not found"}
            
            # Calculate days since enrollment
            enrollment_date = patient.enrollment_date or patient.created_at
            days_since_enrollment = (datetime.utcnow() - enrollment_date).days
            
            # Check if it's a monthly quiz day (every 30 days after day 45)
            if days_since_enrollment < 45:
                return False, {"reason": "Patient not yet in monthly phase"}
            
            # Calculate which monthly cycle we're in
            days_in_monthly_phase = days_since_enrollment - 45
            monthly_cycle = (days_in_monthly_phase // 30) + 1
            days_in_current_cycle = days_in_monthly_phase % 30
            
            # Quiz should be triggered on day 15 of each monthly cycle
            quiz_day = 15
            
            if days_in_current_cycle != quiz_day:
                return False, {
                    "reason": f"Not quiz day (day {days_in_current_cycle} of cycle {monthly_cycle})"
                }
            
            # Check if quiz already completed this month
            quiz_info = {
                "monthly_cycle": monthly_cycle,
                "template_name": f"monthly_checkup_cycle_{monthly_cycle}",
                "trigger_reason": f"Monthly quiz day {quiz_day} of cycle {monthly_cycle}"
            }
            
            # Check for existing quiz session this month
            existing_session = await self._get_current_month_quiz_session(
                flow_state.patient_id, monthly_cycle
            )
            
            if existing_session and existing_session.status == 'completed':
                return False, {**quiz_info, "already_completed": True}
            
            return True, quiz_info
            
        except Exception as e:
            logger.error(f"Error checking quiz due status: {e}")
            return False, {"error": str(e)}
    
    async def _get_current_month_quiz_session(self, 
                                            patient_id: UUID, 
                                            monthly_cycle: int) -> Optional[QuizSessionResponse]:
        """Get quiz session for current monthly cycle."""
        try:
            # Get active session for patient
            active_session = self.quiz_session_service.get_active_session(patient_id)
            
            if active_session:
                # Check if it's for current monthly cycle
                session_metadata = getattr(active_session, 'session_metadata', {}) or {}
                if session_metadata.get('monthly_cycle') == monthly_cycle:
                    return active_session
            
            # Check recent completed sessions
            sessions, _ = self.quiz_session_service.get_patient_sessions(patient_id, limit=10)
            
            for session in sessions:
                session_metadata = getattr(session, 'session_metadata', {}) or {}
                if session_metadata.get('monthly_cycle') == monthly_cycle:
                    return session
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current month quiz session: {e}")
            return None
    
    async def _trigger_patient_quiz(self,
                                  flow_state: PatientFlowState,
                                  quiz_info: dict[str, Any]) -> dict[str, Any]:
        """
        Trigger quiz for a specific patient.
        Detects delivery method (link vs conversational) based on configuration and rollout.

        Args:
            flow_state: Patient flow state
            quiz_info: Quiz information

        Returns:
            Trigger result
        """
        try:
            patient_id = flow_state.patient_id

            # Get monthly quiz configuration
            config = get_monthly_quiz_config()

            # Get or create monthly quiz template
            template = await self._get_or_create_monthly_template(quiz_info)

            # Determine if patient should receive link-based quiz
            from app.core.monthly_quiz_config import should_use_link_based_quiz
            use_link = should_use_link_based_quiz(str(patient_id))

            logger.info(f"Quiz trigger for patient {patient_id}: use_link={use_link}, "
                       f"rollout_percentage={config.MONTHLY_QUIZ_LINK_PERCENTAGE}%")

            if use_link:
                # Trigger quiz via link
                return await self._trigger_quiz_via_link(
                    patient_id=patient_id,
                    quiz_template_id=template.id,
                    quiz_info=quiz_info,
                    flow_state=flow_state
                )
            else:
                # Trigger quiz via WhatsApp conversational
                return await self._trigger_quiz_via_whatsapp(
                    patient_id=patient_id,
                    template=template,
                    quiz_info=quiz_info,
                    flow_state=flow_state
                )

        except Exception as e:
            logger.error(f"Error triggering patient quiz: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_or_create_monthly_template(self, quiz_info: dict[str, Any]) -> QuizTemplate:
        """Get or create monthly quiz template."""
        try:
            template_name = quiz_info["template_name"]
            
            # Try to get existing template
            try:
                template_response = self.quiz_template_service.get_template_by_name(template_name)
                return self.quiz_template_service.template_repository.get(template_response.id)
            except NotFoundError:
                pass
            
            # Create new monthly template
            from app.schemas.quiz import QuizTemplateCreate, QuizQuestion, QuestionOption
            
            questions = [
                QuizQuestion(
                    id="mood_assessment",
                    text="Como você tem se sentido emocionalmente nas últimas semanas?",
                    type=QuestionType.SCALE,
                    options=[
                        QuestionOption(id="1", text="Muito mal", value="1"),
                        QuestionOption(id="2", text="Mal", value="2"),
                        QuestionOption(id="3", text="Neutro", value="3"),
                        QuestionOption(id="4", text="Bem", value="4"),
                        QuestionOption(id="5", text="Muito bem", value="5")
                    ],
                    is_required=True
                ),
                QuizQuestion(
                    id="energy_levels",
                    text="Como estão seus níveis de energia?",
                    type=QuestionType.MULTIPLE_CHOICE,
                    options=[
                        QuestionOption(id="very_low", text="Muito baixos", value="very_low"),
                        QuestionOption(id="low", text="Baixos", value="low"),
                        QuestionOption(id="normal", text="Normais", value="normal"),
                        QuestionOption(id="high", text="Altos", value="high"),
                        QuestionOption(id="very_high", text="Muito altos", value="very_high")
                    ],
                    is_required=True
                ),
                QuizQuestion(
                    id="sleep_quality",
                    text="Como tem sido a qualidade do seu sono?",
                    type=QuestionType.SCALE,
                    options=[
                        QuestionOption(id="1", text="Muito ruim", value="1"),
                        QuestionOption(id="2", text="Ruim", value="2"),
                        QuestionOption(id="3", text="Regular", value="3"),
                        QuestionOption(id="4", text="Boa", value="4"),
                        QuestionOption(id="5", text="Excelente", value="5")
                    ],
                    is_required=True
                ),
                QuizQuestion(
                    id="side_effects",
                    text="Você tem experimentado algum efeito colateral do tratamento?",
                    type=QuestionType.OPEN_TEXT,
                    is_required=False
                ),
                QuizQuestion(
                    id="overall_satisfaction",
                    text="No geral, como você avalia seu progresso no tratamento?",
                    type=QuestionType.SCALE,
                    options=[
                        QuestionOption(id="1", text="Muito insatisfeita", value="1"),
                        QuestionOption(id="2", text="Insatisfeita", value="2"),
                        QuestionOption(id="3", text="Neutro", value="3"),
                        QuestionOption(id="4", text="Satisfeita", value="4"),
                        QuestionOption(id="5", text="Muito satisfeita", value="5")
                    ],
                    is_required=True
                )
            ]
            
            template_data = QuizTemplateCreate(
                name=template_name,
                version="1.0",
                questions=questions,
                is_active=True
            )
            
            template_response = self.quiz_template_service.create_template(template_data)
            return self.quiz_template_service.template_repository.get(template_response.id)
            
        except Exception as e:
            logger.error(f"Error getting/creating monthly template: {e}")
            raise
    
    async def _send_quiz_introduction_message(self, 
                                            patient_id: UUID, 
                                            session: Any, 
                                            template: QuizTemplate):
        """Send introduction message for quiz."""
        try:
            patient = self.patient_repo.get(patient_id)
            if not patient:
                raise NotFoundError("Patient not found")
            
            # Create message using factory
            first_question = template.questions[0]
            message = self.message_factory.create_quiz_introduction(
                patient_id=patient_id,
                patient_name=patient.name,
                session_id=str(session.id),
                first_question=first_question,
                total_questions=len(template.questions)
            )
            
            # Add additional metadata
            message.message_metadata["flow_context"] = {
                "flow_type": "quiz",
                "quiz_template_id": str(template.id)
            }
            
            self.db.commit()
            
            success = await self.message_sender.send_message(message)
            
            if success:
                logger.info(f"Quiz introduction sent to patient {patient_id}")
            else:
                logger.error(f"Failed to send quiz introduction to patient {patient_id}")
            
        except Exception as e:
            logger.error(f"Error sending quiz introduction: {e}")
            raise


class ConversationalQuizService:
    """Service for managing conversational quiz presentation via WhatsApp."""
    
    def __init__(self, db: Session):
        self.db = db
        self.quiz_session_service = QuizSessionService(db)
        self.quiz_response_service = QuizResponseService(db)
        self.quiz_template_service = QuizTemplateService(db)
        self.message_sender = MessageSender(db)
        self.flow_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self.message_factory = MessageFactory(db)
    
    async def process_quiz_response(self, 
                                  patient_id: UUID, 
                                  response_text: str,
                                  message_metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]:
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
                    "action": "ignore"
                }
            
            # Get quiz template
            template = self.quiz_template_service.get_template(active_session.quiz_template_id)
            questions = template.questions
            
            if active_session.current_question_index >= len(questions):
                return {
                    "success": False,
                    "error": "Quiz already completed",
                    "action": "complete_session"
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
                    "action": "request_clarification"
                }
            
            # Save response
            response_data = QuizResponseCreate(
                patient_id=patient_id,
                quiz_template_id=active_session.quiz_template_id,
                question_id=current_question['id'],
                question_text=current_question['text'],
                response_type=current_question['type'],
                response_value=processed_response["value"],
                response_metadata={
                    "original_text": response_text,
                    "processed_value": processed_response["value"],
                    "session_id": str(active_session.id),
                    "question_index": active_session.current_question_index
                },
                responded_at=datetime.utcnow()
            )

            quiz_response = await self.quiz_response_service.create_response(response_data)

            # Record response latency metric
            try:
                # Calculate latency from question sent to response received
                # (message_metadata should contain question_sent_at timestamp)
                if message_metadata and 'question_sent_at' in message_metadata:
                    question_sent_at = message_metadata['question_sent_at']
                    if isinstance(question_sent_at, str):
                        from datetime import datetime
                        question_sent_at = datetime.fromisoformat(question_sent_at)

                    response_latency = (datetime.utcnow() - question_sent_at).total_seconds()

                    metrics = await get_quiz_metrics_collector()
                    await metrics.record_response_latency(
                        template_id=active_session.quiz_template_id,
                        question_id=current_question['id'],
                        session_id=active_session.id,
                        latency_seconds=response_latency
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
                    "session_id": str(active_session.id)
                }
            else:
                # Advance to next question
                self.quiz_session_service.advance_session(active_session.id)
                
                # Send next question
                await self._send_next_question(
                    patient_id, active_session, questions, 
                    active_session.current_question_index + 1
                )
                
                return {
                    "success": True,
                    "action": "next_question",
                    "question_index": active_session.current_question_index + 1
                }
            
        except Exception as e:
            logger.error(f"Error processing quiz response: {e}")
            return {
                "success": False,
                "error": str(e),
                "action": "error"
            }
    
    async def _process_question_response(self, 
                                       question: dict[str, Any], 
                                       response_text: str,
                                       patient_id: UUID) -> dict[str, Any]:
        """Process and validate question response."""
        try:
            question_type = question['type']
            response_text = response_text.strip()
            
            if question_type == QuestionType.OPEN_TEXT.value:
                return {
                    "valid": True,
                    "value": response_text,
                    "type": "text"
                }
            
            elif question_type == QuestionType.SCALE.value:
                # Try to extract number from response
                import re
                numbers = re.findall(r'\d+', response_text)
                
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
                            "interpreted": True
                        }
                    
                    return {
                        "valid": False,
                        "error": "Por favor, responda com um número de 1 a 5"
                    }
                
                scale_value = int(numbers[0])
                if 1 <= scale_value <= 5:
                    return {
                        "valid": True,
                        "value": str(scale_value),
                        "type": "scale"
                    }
                else:
                    return {
                        "valid": False,
                        "error": "Por favor, escolha um número entre 1 e 5"
                    }
            
            elif question_type == QuestionType.MULTIPLE_CHOICE.value:
                # Try to match response with options
                options = question.get('options', [])
                
                # Direct text match
                for option in options:
                    if response_text.lower() in option['text'].lower() or \
                       option['text'].lower() in response_text.lower():
                        return {
                            "valid": True,
                            "value": option['value'],
                            "type": "multiple_choice"
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
                        "interpreted": True
                    }
                
                # Show options again
                options_text = "\n".join([f"• {opt['text']}" for opt in options])
                return {
                    "valid": False,
                    "error": f"Por favor, escolha uma das opções:\n{options_text}"
                }
            
            elif question_type == QuestionType.YES_NO.value:
                response_lower = response_text.lower()
                
                yes_words = ['sim', 'yes', 's', 'claro', 'certamente', 'com certeza']
                no_words = ['não', 'nao', 'no', 'n', 'nunca', 'jamais']
                
                if any(word in response_lower for word in yes_words):
                    return {
                        "valid": True,
                        "value": "yes",
                        "type": "yes_no"
                    }
                elif any(word in response_lower for word in no_words):
                    return {
                        "valid": True,
                        "value": "no",
                        "type": "yes_no"
                    }
                else:
                    return {
                        "valid": False,
                        "error": "Por favor, responda com 'sim' ou 'não'"
                    }
            
            else:
                return {
                    "valid": False,
                    "error": "Tipo de pergunta não suportado"
                }
            
        except Exception as e:
            logger.error(f"Error processing question response: {e}")
            return {
                "valid": False,
                "error": "Erro ao processar resposta"
            }
    
    async def _interpret_scale_response(self, 
                                      response_text: str, 
                                      question: dict[str, Any]) -> Optional[int]:
        """Use AI to interpret scale response."""
        try:
            gemini_client = get_gemini_client()
            
            prompt = f"""
            Analise a resposta do paciente para uma pergunta de escala de 1 a 5:
            
            Pergunta: {question['text']}
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
    
    async def _interpret_multiple_choice_response(self, 
                                                response_text: str, 
                                                options: List[dict[str, Any]]) -> Optional[str]:
        """Use AI to interpret multiple choice response."""
        try:
            gemini_client = get_gemini_client()
            
            options_text = "\n".join([f"- {opt['value']}: {opt['text']}" for opt in options])
            
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
                option_values = [opt['value'] for opt in options]
                if response.strip() in option_values:
                    return response.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error interpreting multiple choice response: {e}")
            return None
    
    async def _send_clarification_message(self, 
                                        patient_id: UUID, 
                                        question: dict[str, Any],
                                        error_message: str):
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
                error_message=error_message
            )
            
            await self.message_sender.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending clarification message: {e}")
    
    async def _send_next_question(self, 
                                patient_id: UUID, 
                                session: Any,
                                questions: List[Dict[str, Any]], 
                                question_index: int):
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
                total_questions=len(questions),  # FIX: Added missing total_questions argument
                patient_name=patient.name
            )
            
            await self.message_sender.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending next question: {e}")
    
    async def _complete_quiz_session(self, session: Any, patient_id: UUID):
        """Complete quiz session and send completion message."""
        try:
            # Complete the session
            await self.quiz_session_service.complete_session(session.id)

            # Schedule report generation
            from app.tasks.flows import generate_quiz_report
            report_task = generate_quiz_report.delay(str(session.id))
            logger.info(f"Scheduled quiz report generation: task {report_task.id}")

            # Update flow state and detect delivery method
            delivery_method = "whatsapp_conversational"  # default
            flow_states = self.flow_repo.get_by_patient_id(patient_id)
            for flow_state in flow_states:
                if flow_state.state_data and \
                   flow_state.state_data.get("quiz_session_id") == str(session.id):
                    flow_state.state_data["quiz_state"] = QuizFlowState.COMPLETED.value
                    flow_state.state_data["quiz_completed_at"] = datetime.utcnow().isoformat()

                    # Get delivery method from flow state
                    delivery_method = flow_state.state_data.get("quiz_delivery_method", "whatsapp_conversational")
                    break

            self.db.commit()

            # Send appropriate completion message based on delivery method
            patient = self.patient_repo.get(patient_id)
            if patient:
                if delivery_method == "link":
                    # Use MonthlyQuizMessageIntegration for link completion
                    from app.services.monthly_quiz_message_integration import MonthlyQuizMessageIntegration
                    quiz_integration = MonthlyQuizMessageIntegration(self.db)

                    await quiz_integration.send_completion_confirmation(
                        quiz_session_id=session.id
                    )
                    logger.info(f"Sent link-based completion message for patient {patient_id}")
                else:
                    # Use MessageFactory for conversational completion
                    message = self.message_factory.create_quiz_completion(
                        patient_id=patient_id,
                        patient_name=patient.name,
                        session_id=str(session.id)
                    )

                    await self.message_sender.send_message(message)
                    logger.info(f"Sent conversational completion message for patient {patient_id}")

        except Exception as e:
            logger.error(f"Error completing quiz session: {e}")
    
    async def pause_quiz_session(self, patient_id: UUID) -> Dict[str, Any]:
        """Pause active quiz session."""
        try:
            active_session = self.quiz_session_service.get_active_session(patient_id)
            
            if not active_session:
                return {
                    "success": False,
                    "error": "No active quiz session found"
                }
            
            # Update flow state
            flow_states = self.flow_repo.get_by_patient_id(patient_id)
            for flow_state in flow_states:
                if flow_state.state_data and \
                   flow_state.state_data.get("quiz_session_id") == str(active_session.id):
                    flow_state.state_data["quiz_state"] = QuizFlowState.PAUSED.value
                    flow_state.state_data["quiz_paused_at"] = datetime.utcnow().isoformat()
                    break
            
            self.db.commit()
            
            # Send pause confirmation
            patient = self.patient_repo.get(patient_id)
            if patient:
                # Create message using factory
                message = self.message_factory.create_quiz_pause(
                    patient_id=patient_id,
                    patient_name=patient.name,
                    session_id=str(active_session.id)
                )
                
                await self.message_sender.send_message(message)
            
            return {
                "success": True,
                "session_id": str(active_session.id),
                "action": "paused"
            }
            
        except Exception as e:
            logger.error(f"Error pausing quiz session: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def resume_quiz_session(self, patient_id: UUID) -> Dict[str, Any]:
        """Resume paused quiz session."""
        try:
            active_session = self.quiz_session_service.get_active_session(patient_id)
            
            if not active_session:
                return {
                    "success": False,
                    "error": "No active quiz session found"
                }
            
            # Check if session is paused
            flow_states = self.flow_repo.get_by_patient_id(patient_id)
            is_paused = False
            
            for flow_state in flow_states:
                if flow_state.state_data and \
                   flow_state.state_data.get("quiz_session_id") == str(active_session.id):
                    if flow_state.state_data.get("quiz_state") == QuizFlowState.PAUSED.value:
                        is_paused = True
                        flow_state.state_data["quiz_state"] = QuizFlowState.IN_PROGRESS.value
                        flow_state.state_data["quiz_resumed_at"] = datetime.utcnow().isoformat()
                    break
            
            if not is_paused:
                return {
                    "success": False,
                    "error": "Quiz session is not paused"
                }
            
            self.db.commit()
            
            # Get current question and send it
            template = self.quiz_template_service.get_template(active_session.quiz_template_id)
            questions = template.questions
            
            if active_session.current_question_index < len(questions):
                await self._send_next_question(
                    patient_id, active_session, questions, 
                    active_session.current_question_index
                )
            
            return {
                "success": True,
                "session_id": str(active_session.id),
                "action": "resumed",
                "current_question": active_session.current_question_index
            }
            
        except Exception as e:
            logger.error(f"Error resuming quiz session: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def get_quiz_trigger_service(db: Session) -> QuizTriggerService:
    """Get quiz trigger service instance."""
    return QuizTriggerService(db)


    async def _trigger_quiz_via_link(self,
                                   patient_id: UUID,
                                   quiz_template_id: UUID,
                                   quiz_info: dict[str, Any],
                                   flow_state: PatientFlowState) -> dict[str, Any]:
        """
        Trigger quiz via secure link delivery.

        Args:
            patient_id: Patient UUID
            quiz_template_id: Quiz template UUID
            quiz_info: Quiz information
            flow_state: Patient flow state

        Returns:
            Trigger result with link information
        """
        try:
            config = get_monthly_quiz_config()

            # Initialize monthly quiz message integration
            quiz_integration = MonthlyQuizMessageIntegration(self.db)

            # Determine delivery method from patient preferences or default
            delivery_method = await self._get_patient_preferred_delivery_method(patient_id)

            # Send quiz link with message
            result = await quiz_integration.send_quiz_link(
                patient_id=patient_id,
                quiz_template_id=quiz_template_id,
                delivery_method=delivery_method,
                expiry_hours=config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS,
                send_immediately=True
            )

            # Update flow state with link metadata
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data["quiz_session_id"] = result["quiz_session_id"]
            flow_state.state_data["quiz_state"] = QuizFlowState.AWAITING_RESPONSE.value
            flow_state.state_data["quiz_started_at"] = datetime.utcnow().isoformat()
            flow_state.state_data["quiz_delivery_method"] = "link"
            flow_state.state_data["quiz_link_token"] = result["token"]
            flow_state.state_data["quiz_link_expires_at"] = result["expires_at"]
            flow_state.state_data["monthly_cycle"] = quiz_info["monthly_cycle"]
            flow_state.state_data["quiz_link_created_at"] = datetime.utcnow().isoformat()
            flow_state.state_data["quiz_link_access_count"] = 0

            self.db.commit()

            # Schedule automatic reminders
            await self._schedule_link_reminders(
                quiz_session_id=UUID(result["quiz_session_id"]),
                expires_at=datetime.fromisoformat(result["expires_at"])
            )

            logger.info(f"Successfully triggered quiz via link for patient {patient_id}")

            return {
                "success": True,
                "patient_id": str(patient_id),
                "session_id": result["quiz_session_id"],
                "delivery_method": "link",
                "delivery_channel": delivery_method.value,
                "link_url": result["link_url"],
                "expires_at": result["expires_at"],
                "message_sent": result["message_sent"],
                "monthly_cycle": quiz_info["monthly_cycle"]
            }

        except Exception as e:
            logger.error(f"Error triggering quiz via link: {e}")
            # Fallback to WhatsApp conversational if link creation fails
            logger.warning(f"Attempting fallback to WhatsApp conversational for patient {patient_id}")
            return await self._trigger_quiz_via_whatsapp_with_fallback(
                patient_id=patient_id,
                quiz_template_id=quiz_template_id,
                quiz_info=quiz_info,
                flow_state=flow_state,
                error_reason=str(e)
            )

    async def _trigger_quiz_via_whatsapp(self,
                                       patient_id: UUID,
                                       template: QuizTemplate,
                                       quiz_info: dict[str, Any],
                                       flow_state: PatientFlowState) -> dict[str, Any]:
        """
        Trigger quiz via WhatsApp conversational flow (original method).

        Args:
            patient_id: Patient UUID
            template: Quiz template
            quiz_info: Quiz information
            flow_state: Patient flow state

        Returns:
            Trigger result
        """
        try:
            # Create quiz session
            session_data = QuizSessionCreate(
                patient_id=patient_id,
                quiz_template_id=template.id
            )

            session = await self.quiz_session_service.start_quiz_session(session_data)

            # Update session metadata with monthly cycle info
            session_metadata = {
                "monthly_cycle": quiz_info["monthly_cycle"],
                "triggered_by": "flow_system",
                "trigger_date": datetime.utcnow().isoformat(),
                "flow_state_id": str(flow_state.id),
                "delivery_method": "whatsapp_conversational"
            }

            # Update flow state to indicate quiz in progress
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data["quiz_session_id"] = str(session.id)
            flow_state.state_data["quiz_state"] = QuizFlowState.IN_PROGRESS.value
            flow_state.state_data["quiz_started_at"] = datetime.utcnow().isoformat()
            flow_state.state_data["quiz_delivery_method"] = "whatsapp_conversational"
            flow_state.state_data["monthly_cycle"] = quiz_info["monthly_cycle"]

            self.db.commit()

            # Send initial quiz message
            await self._send_quiz_introduction_message(patient_id, session, template)

            logger.info(f"Successfully triggered quiz via WhatsApp for patient {patient_id}")

            return {
                "success": True,
                "patient_id": str(patient_id),
                "session_id": str(session.id),
                "template_id": str(template.id),
                "delivery_method": "whatsapp_conversational",
                "monthly_cycle": quiz_info["monthly_cycle"]
            }

        except Exception as e:
            logger.error(f"Error triggering quiz via WhatsApp: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _schedule_link_reminders(self,
                                     quiz_session_id: UUID,
                                     expires_at: datetime) -> None:
        """
        Schedule automatic reminders for quiz link.

        Args:
            quiz_session_id: Quiz session UUID
            expires_at: Link expiration datetime
        """
        try:
            from app.tasks.quiz_flow import send_quiz_link_reminder_task
            config = get_monthly_quiz_config()

            # Calculate reminder times based on expiry
            # First reminder: 24h before expiry
            reminder_1_time = expires_at - timedelta(hours=24)

            # Second reminder: 6h before expiry
            reminder_2_time = expires_at - timedelta(hours=6)

            # Schedule reminders using Celery
            if reminder_1_time > datetime.utcnow():
                task_1 = send_quiz_link_reminder_task.apply_async(
                    args=[str(quiz_session_id), 24],
                    eta=reminder_1_time
                )
                logger.info(f"Scheduled first reminder for quiz {quiz_session_id} at {reminder_1_time} (task: {task_1.id})")

            if reminder_2_time > datetime.utcnow():
                task_2 = send_quiz_link_reminder_task.apply_async(
                    args=[str(quiz_session_id), 6],
                    eta=reminder_2_time
                )
                logger.info(f"Scheduled second reminder for quiz {quiz_session_id} at {reminder_2_time} (task: {task_2.id})")

            # Store reminder schedule in session metadata
            session = self.quiz_session_service.session_repository.get(quiz_session_id)
            if session:
                session_metadata = session.session_metadata or {}
                session_metadata['reminders_scheduled'] = {
                    'first_reminder': reminder_1_time.isoformat() if reminder_1_time > datetime.utcnow() else None,
                    'second_reminder': reminder_2_time.isoformat() if reminder_2_time > datetime.utcnow() else None,
                    'scheduled_at': datetime.utcnow().isoformat()
                }
                session.session_metadata = session_metadata
                self.db.commit()

        except Exception as e:
            logger.error(f"Error scheduling link reminders: {e}")

    async def _get_patient_preferred_delivery_method(self, patient_id: UUID) -> DeliveryMethod:
        """
        Get patient's preferred delivery method for quiz links.

        Args:
            patient_id: Patient UUID

        Returns:
            DeliveryMethod enum value
        """
        try:
            patient = self.patient_repo.get(patient_id)

            if patient and hasattr(patient, 'preferences'):
                preferences = patient.preferences or {}
                delivery_pref = preferences.get('quiz_delivery_method', 'whatsapp')
                return DeliveryMethod(delivery_pref)

            # Default to WhatsApp
            return DeliveryMethod.WHATSAPP

        except Exception as e:
            logger.warning(f"Error getting patient delivery preference: {e}, using default")
            return DeliveryMethod.WHATSAPP

    async def _trigger_quiz_via_whatsapp_with_fallback(self,
                                                      patient_id: UUID,
                                                      quiz_template_id: UUID,
                                                      quiz_info: dict[str, Any],
                                                      flow_state: PatientFlowState,
                                                      error_reason: str) -> dict[str, Any]:
        """
        Fallback to WhatsApp conversational when link creation fails.

        Args:
            patient_id: Patient UUID
            quiz_template_id: Quiz template UUID
            quiz_info: Quiz information
            flow_state: Patient flow state
            error_reason: Reason for fallback

        Returns:
            Trigger result
        """
        try:
            # Get template
            template = await self._get_or_create_monthly_template(quiz_info)

            # Trigger via WhatsApp
            result = await self._trigger_quiz_via_whatsapp(
                patient_id=patient_id,
                template=template,
                quiz_info=quiz_info,
                flow_state=flow_state
            )

            # Add fallback metadata
            if result["success"]:
                result["fallback_triggered"] = True
                result["fallback_reason"] = error_reason
                result["original_delivery_method"] = "link"

                # Update flow state to indicate fallback
                flow_state.state_data = flow_state.state_data or {}
                flow_state.state_data["quiz_fallback_triggered"] = True
                flow_state.state_data["quiz_fallback_reason"] = error_reason
                flow_state.state_data["quiz_fallback_at"] = datetime.utcnow().isoformat()
                self.db.commit()

            logger.info(f"Fallback to WhatsApp conversational successful for patient {patient_id}")
            return result

        except Exception as e:
            logger.error(f"Fallback to WhatsApp also failed: {e}")
            return {
                "success": False,
                "error": f"Both link and WhatsApp fallback failed: {str(e)}",
                "fallback_triggered": True,
                "fallback_failed": True
            }


def get_conversational_quiz_service(db: Session) -> ConversationalQuizService:
    """Get conversational quiz service instance."""
    return ConversationalQuizService(db)


async def trigger_monthly_quiz_via_link(
    db: Session,
    patient_id: UUID,
    quiz_template_id: UUID,
    quiz_info: dict[str, Any],
    flow_state: PatientFlowState,
    delivery_method: Optional[DeliveryMethod] = None
) -> dict[str, Any]:
    """
    Convenience function to trigger monthly quiz via link.

    Args:
        db: Database session
        patient_id: Patient UUID
        quiz_template_id: Quiz template UUID
        quiz_info: Quiz information
        flow_state: Patient flow state
        delivery_method: Optional delivery method override

    Returns:
        Trigger result dictionary
    """
    quiz_trigger_service = QuizTriggerService(db)
    return await quiz_trigger_service._trigger_quiz_via_link(
        patient_id=patient_id,
        quiz_template_id=quiz_template_id,
        quiz_info=quiz_info,
        flow_state=flow_state
    )