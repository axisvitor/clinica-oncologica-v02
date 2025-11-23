"""
Response Handler - Processes and interprets patient responses.

Handles response validation, AI-enhanced processing, and swarm analysis coordination.
"""

import logging
import re
from typing import Dict, Optional, Any
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.quiz import QuizResponseCreate, QuestionType
from app.services.quiz import QuizSessionService, QuizResponseService
from app.agents.base import MessagePriority


class ResponseHandler:
    """
    Handles quiz response processing and interpretation.

    Responsibilities:
    - Process quiz responses
    - Perform basic response validation
    - Apply AI-enhanced interpretation
    - Coordinate swarm analysis for complex responses
    - Store validated responses
    - Determine next actions (continue/complete quiz)
    """

    def __init__(
        self,
        db_session: Session,
        quiz_session_service: QuizSessionService,
        quiz_response_service: QuizResponseService,
        agent_id: str,
        gemini_client=None,
        knowledge_graph=None,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize response handler."""
        self.db_session = db_session
        self.quiz_session_service = quiz_session_service
        self.quiz_response_service = quiz_response_service
        self.agent_id = agent_id
        self.gemini_client = gemini_client
        self.knowledge_graph = knowledge_graph
        self.logger = logger or logging.getLogger(__name__)

        # Processing thresholds
        self.ai_interpretation_confidence_threshold = 0.8
        self.require_human_review_threshold = 0.3

    async def process_quiz_response(
        self,
        payload: Dict[str, Any],
        build_context_callback,
        send_next_question_callback,
        complete_session_callback,
        send_clarification_callback
    ) -> Dict[str, Any]:
        """
        Process patient response with swarm analysis.

        HIGH-005 FIX: Implements debouncing to prevent duplicate responses.
        """
        patient_id = UUID(payload["patient_id"])
        response_text = payload["response_text"]
        message_metadata = payload.get("message_metadata", {})

        # Get active session
        active_session = self.quiz_session_service.get_active_session(patient_id)
        if not active_session:
            return {"success": False, "error": "No active quiz session"}

        # HIGH-005 FIX: Add debounce check
        from app.services.quiz_response_debounce import get_quiz_debouncer

        debouncer = get_quiz_debouncer(debounce_window_seconds=3)

        # Get current question ID
        current_question_id = (
            active_session.current_question
            if hasattr(active_session, 'current_question') and active_session.current_question
            else str(active_session.current_question_index) if hasattr(active_session, 'current_question_index')
            else "unknown"
        )

        # Check debounce
        should_process = await debouncer.should_process_response(
            session_id=active_session.id,
            question_id=current_question_id,
            message_metadata=message_metadata
        )

        if not should_process:
            # Response debounced
            self.logger.info(
                f"Response debounced for patient {patient_id}",
                extra={
                    "patient_id": str(patient_id),
                    "session_id": str(active_session.id),
                    "question_id": current_question_id,
                    "agent_id": self.agent_id
                }
            )
            return {
                "success": False,
                "action": "debounced",
                "message": "Response ignored - within debounce window"
            }

        # Build context
        context = await build_context_callback(patient_id, "current")

        # Process response with AI and swarm intelligence
        processing_result = await self.process_response_with_swarm(context, response_text)

        if not processing_result["valid"]:
            # Send clarification message
            await send_clarification_callback(context, processing_result["error"])
            return {
                "success": False,
                "action": "clarification_requested",
                "error": processing_result["error"]
            }

        # Store response
        response_data = QuizResponseCreate(
            patient_id=patient_id,
            quiz_template_id=active_session.quiz_template_id,
            question_id=processing_result["question_id"],
            question_text=processing_result["question_text"],
            response_type=processing_result["response_type"],
            response_value=processing_result["processed_value"],
            response_metadata={
                "original_text": response_text,
                "ai_processed": processing_result.get("ai_processed", False),
                "confidence_score": processing_result.get("confidence", 1.0),
                "swarm_analysis": processing_result.get("swarm_analysis", {}),
                "processed_by_agent": self.agent_id
            },
            responded_at=datetime.utcnow()
        )

        response = await self.quiz_response_service.create_response(response_data)

        # Update knowledge graph
        if self.knowledge_graph and response:
            try:
                await self.knowledge_graph.add_quiz_response_node(response)
            except Exception as e:
                self.logger.error(f"Failed to update knowledge graph: {e}")

        # Determine next action
        if context.current_question_index >= len(context.template.questions) - 1:
            # Complete quiz
            await complete_session_callback(context)

            # HIGH-005 FIX: Clear debounce state on completion
            from app.services.quiz_response_debounce import get_quiz_debouncer
            debouncer = get_quiz_debouncer()
            await debouncer.clear_debounce(active_session.id)

            return {
                "success": True,
                "action": "quiz_completed",
                "session_id": str(active_session.id)
            }
        else:
            # Advance to next question
            self.quiz_session_service.advance_session(active_session.id)

            # Send next question (with potential adaptation)
            next_context = await build_context_callback(patient_id, "current")
            await send_next_question_callback(next_context)

            return {
                "success": True,
                "action": "next_question",
                "question_index": context.current_question_index + 1
            }

    async def process_response_with_swarm(self, context: 'QuizContext', response_text: str) -> Dict[str, Any]:
        """Process response with swarm intelligence and AI analysis."""
        if context.current_question_index >= len(context.template.questions):
            return {"valid": False, "error": "No active question"}

        current_question = context.template.questions[context.current_question_index]

        # Basic processing
        basic_result = await self.basic_response_processing(current_question, response_text)

        # If basic processing is uncertain, use AI enhancement
        if basic_result.get("confidence", 1.0) < self.ai_interpretation_confidence_threshold:
            ai_result = await self.ai_enhanced_processing(current_question, response_text, context)

            if ai_result and ai_result.get("confidence", 0) > basic_result.get("confidence", 0):
                basic_result.update(ai_result)
                basic_result["ai_processed"] = True

        # Request swarm analysis for complex responses
        if basic_result.get("confidence", 1.0) < self.require_human_review_threshold:
            swarm_analysis = await self.request_swarm_analysis(context, response_text, basic_result)
            basic_result["swarm_analysis"] = swarm_analysis

        # Add context information
        basic_result.update({
            "question_id": current_question['id'],
            "question_text": current_question['text'],
            "response_type": current_question['type']
        })

        return basic_result

    async def basic_response_processing(self, question: Dict, response_text: str) -> Dict[str, Any]:
        """Basic response processing without AI."""
        question_type = question['type']
        response_text = response_text.strip()

        if question_type == QuestionType.OPEN_TEXT.value:
            return {
                "valid": True,
                "processed_value": response_text,
                "confidence": 1.0
            }

        elif question_type == QuestionType.SCALE.value:
            # Try to extract number
            numbers = re.findall(r'\d+', response_text)

            if numbers:
                scale_value = int(numbers[0])
                if 1 <= scale_value <= 5:
                    return {
                        "valid": True,
                        "processed_value": str(scale_value),
                        "confidence": 1.0
                    }

            return {
                "valid": False,
                "error": "Por favor, responda com um número de 1 a 5",
                "confidence": 0.0
            }

        elif question_type == QuestionType.MULTIPLE_CHOICE.value:
            options = question.get('options', [])

            # Direct text match
            for option in options:
                if (response_text.lower() in option['text'].lower() or
                    option['text'].lower() in response_text.lower()):
                    return {
                        "valid": True,
                        "processed_value": option['value'],
                        "confidence": 0.9
                    }

            # Return uncertain result for AI processing
            return {
                "valid": False,
                "error": "Não consegui entender sua resposta",
                "confidence": 0.2,
                "options": options
            }

        elif question_type == QuestionType.YES_NO.value:
            response_lower = response_text.lower()

            yes_words = ['sim', 'yes', 's', 'claro', 'certamente', 'com certeza']
            no_words = ['não', 'nao', 'no', 'n', 'nunca', 'jamais']

            if any(word in response_lower for word in yes_words):
                return {"valid": True, "processed_value": "yes", "confidence": 0.9}
            elif any(word in response_lower for word in no_words):
                return {"valid": True, "processed_value": "no", "confidence": 0.9}

            return {
                "valid": False,
                "error": "Por favor, responda com 'sim' ou 'não'",
                "confidence": 0.0
            }

        return {
            "valid": False,
            "error": "Tipo de pergunta não suportado",
            "confidence": 0.0
        }

    async def ai_enhanced_processing(self, question: Dict, response_text: str, context: 'QuizContext') -> Optional[Dict[str, Any]]:
        """AI-enhanced response processing using Gemini."""
        try:
            if not self.gemini_client:
                return None

            question_type = question['type']

            if question_type == QuestionType.SCALE.value:
                prompt = f"""
                Analise a resposta do paciente para uma pergunta de escala de 1 a 5:

                Pergunta: {question['text']}
                Resposta: "{response_text}"

                Contexto do paciente: {context.patient_data.name} está em tratamento de terapia hormonal.

                Escala:
                1 = Muito ruim/baixo/negativo
                2 = Ruim/baixo/negativo
                3 = Neutro/regular/médio
                4 = Bom/alto/positivo
                5 = Muito bom/alto/positivo

                Retorne apenas o número (1-5) que melhor representa a resposta.
                Se não conseguir interpretar, retorne "INVALID".
                """

            elif question_type == QuestionType.MULTIPLE_CHOICE.value:
                options_text = "\n".join([f"- {opt['value']}: {opt['text']}" for opt in question.get('options', [])])

                prompt = f"""
                Analise a resposta do paciente e determine qual opção ela melhor representa:

                Pergunta: {question['text']}
                Resposta: "{response_text}"

                Opções disponíveis:
                {options_text}

                Retorne apenas o valor (value) da opção que melhor corresponde.
                Se não conseguir determinar, retorne "INVALID".
                """
            else:
                return None

            # Get AI response
            ai_response = await self.gemini_client.generate_content(prompt)

            if not ai_response or ai_response.strip() == "INVALID":
                return None

            # Validate AI response
            if question_type == QuestionType.SCALE.value:
                if ai_response.strip().isdigit():
                    value = int(ai_response.strip())
                    if 1 <= value <= 5:
                        return {
                            "valid": True,
                            "processed_value": str(value),
                            "confidence": 0.8,
                            "ai_interpreted": True
                        }

            elif question_type == QuestionType.MULTIPLE_CHOICE.value:
                options = question.get('options', [])
                option_values = [opt['value'] for opt in options]
                if ai_response.strip() in option_values:
                    return {
                        "valid": True,
                        "processed_value": ai_response.strip(),
                        "confidence": 0.8,
                        "ai_interpreted": True
                    }

            return None

        except Exception as e:
            self.logger.error(f"AI response processing failed: {e}")
            return None

    async def request_swarm_analysis(
        self,
        context: 'QuizContext',
        response_text: str,
        basic_result: Dict,
        send_message_callback=None
    ) -> Dict[str, Any]:
        """Request analysis from other agents in the swarm."""
        try:
            if not send_message_callback:
                return {}

            # Request analysis from relevant agents
            analysis_requests = {
                "mood_analysis": "alert_analyzer_agent",
                "medical_significance": "patient_monitor_agent",
                "flow_impact": "flow_coordinator_agent"
            }

            swarm_analysis = {}

            for analysis_type, agent_id in analysis_requests.items():
                try:
                    # Send analysis request
                    await send_message_callback(
                        agent_id,
                        "analyze_quiz_response",
                        {
                            "patient_id": str(context.patient_id),
                            "response_text": response_text,
                            "question_context": context.template.questions[context.current_question_index],
                            "basic_processing": basic_result,
                            "analysis_type": analysis_type
                        },
                        MessagePriority.HIGH
                    )

                    # For now, simulate analysis results
                    # In real implementation, would wait for responses
                    swarm_analysis[analysis_type] = {
                        "agent": agent_id,
                        "confidence": 0.7,
                        "insights": ["response_processed_by_swarm"]
                    }

                except Exception as e:
                    self.logger.error(f"Failed to request {analysis_type} from {agent_id}: {e}")

            return swarm_analysis

        except Exception as e:
            self.logger.error(f"Swarm analysis request failed: {e}")
            return {}
