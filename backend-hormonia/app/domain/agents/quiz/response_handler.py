"""
Response Handler - Processes and interprets patient responses.

Handles response validation, AI-enhanced processing, and swarm analysis coordination.
"""

from __future__ import annotations

# Standard library imports
import logging
import re
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

# Third-party imports
from sqlalchemy.orm import Session

# Local application imports
from app.agents.base import MessagePriority
from app.agents.registry import ALERT_ANALYZER_ID, PATIENT_MONITOR_ID, FLOW_COORDINATOR_ID
from app.schemas.quiz import QuestionType, QuizResponseCreate
from app.services.quiz import QuizResponseService, QuizSessionService
from app.services.ai.guardrails import OutputKind
from app.services.ai.output_profiles import MESSAGE_STANDARD
from app.domain.quizzes.integration.flow_integration.utils import process_quiz_response_with_debounce
from app.utils.thread_ids import sanitize_thread_component
from app.utils.timezone import now_sao_paulo

if TYPE_CHECKING:
    from app.domain.agents.quiz.types import QuizContext


class ResponseHandler:
    """
    Handles quiz response processing and interpretation.

    Processes patient responses with validation, AI-enhanced
    interpretation, and multi-agent swarm analysis.

    Attributes:
        db_session: Database session.
        quiz_session_service: Session service.
        quiz_response_service: Response service.
        agent_id: ID of owning agent.
        gemini_client: AI client for interpretation.
        knowledge_graph: Knowledge graph instance.
        ai_interpretation_confidence_threshold: Threshold for AI processing.
        require_human_review_threshold: Threshold for human review.
    """

    def __init__(
        self,
        db_session: Session,
        quiz_session_service: QuizSessionService,
        quiz_response_service: QuizResponseService,
        agent_id: str,
        gemini_client=None,
        knowledge_graph=None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize response handler.

        Args:
            db_session: Database session.
            quiz_session_service: Quiz session service.
            quiz_response_service: Quiz response service.
            agent_id: Agent identifier.
            gemini_client: Gemini AI client.
            knowledge_graph: Knowledge graph instance.
            logger: Logger instance.
        """
        self.db_session = db_session
        self.quiz_session_service = quiz_session_service
        self.quiz_response_service = quiz_response_service
        self.agent_id = agent_id
        self.gemini_client = gemini_client
        self.knowledge_graph = knowledge_graph
        self._logger = logger or logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Processing thresholds
        self.ai_interpretation_confidence_threshold = 0.8
        self.require_human_review_threshold = 0.3

    async def process_quiz_response(
        self,
        payload: Dict[str, Any],
        build_context_callback,
        send_next_question_callback,
        complete_session_callback,
        send_clarification_callback,
    ) -> Dict[str, Any]:
        """
        Process patient response with swarm analysis.

        HIGH-005 FIX: Implements debouncing to prevent duplicate responses.
        """
        try:
            patient_id = UUID(str(payload["patient_id"]))
        except (KeyError, TypeError, ValueError):
            return {
                "success": False,
                "action": "error",
                "error": "Invalid or missing patient_id",
            }
        response_text = payload["response_text"]
        message_metadata = dict(payload.get("message_metadata", {}))

        active_session = self.quiz_session_service.get_active_session(patient_id)
        if not active_session:
            return {"success": False, "error": "No active quiz session"}

        current_question_id = str(getattr(active_session, "current_question", "unknown"))

        context = await self._build_context_safe(
            build_context_callback, patient_id, active_session
        )

        try:
            result = await process_quiz_response_with_debounce(
                self.db_session,
                patient_id=patient_id,
                quiz_session_id=active_session.id,
                current_question_id=str(current_question_id),
                response_text=response_text,
                message_metadata=message_metadata,
                debounce_window_seconds=3,
            )
        except Exception as exc:
            self._logger.error(
                "Primary quiz response flow failed, activating fallback: %s",
                exc,
            )
            result = {"success": False, "action": "error", "error": str(exc)}

        action = result.get("action")

        # Keep debounce behavior unchanged.
        if action == "debounced":
            return result

        # Re-enable callback-driven orchestration (next question/completion/clarification).
        if action == "request_clarification":
            await self._invoke_callback(
                send_clarification_callback,
                context,
                result.get("error", "Não consegui entender sua resposta."),
            )
            return {
                "success": False,
                "action": "clarification_requested",
                "error": result.get("error"),
            }

        if action in {"next_question", "quiz_completed", "complete_session"}:
            if action == "next_question":
                if context is not None:
                    next_question_index = result.get("question_index")
                    try:
                        if next_question_index is not None:
                            context.current_question = max(int(next_question_index), 0)
                    except (TypeError, ValueError):
                        pass

                # Skip callback only when upstream flow explicitly reports
                # it already dispatched the next question.
                if not result.get("next_question_sent", False):
                    await self._invoke_callback(send_next_question_callback, context)
            else:
                await self._invoke_callback(complete_session_callback, context)
            return result

        # Fallback path when AI or integration flow fails.
        if action == "error" or not result.get("success", False):
            return await self._process_quiz_response_fallback(
                context=context,
                active_session=active_session,
                response_text=response_text,
                send_next_question_callback=send_next_question_callback,
                complete_session_callback=complete_session_callback,
                send_clarification_callback=send_clarification_callback,
                original_result=result,
            )

        return result

    async def _build_context_safe(
        self,
        build_context_callback,
        patient_id: UUID,
        active_session: Any,
    ) -> Optional["QuizContext"]:
        """Build quiz context from canonical callback signature."""
        if not build_context_callback:
            return None

        context: Optional["QuizContext"] = None
        try:
            maybe_context = build_context_callback(patient_id, "current")
            context = await maybe_context if isawaitable(maybe_context) else maybe_context
        except Exception as exc:
            self._logger.error("Failed to build quiz context: %s", exc)
            return None

        if context is None:
            return None

        if getattr(context, "session", None) is None:
            context.session = active_session

        try:
            context.current_question = int(
                getattr(active_session, "current_question", 0) or 0
            )
        except (TypeError, ValueError):
            context.current_question = 0

        return context

    async def _invoke_callback(self, callback, *args):
        """Invoke callback supporting sync or async callables."""
        if not callback:
            return None

        # Skip context-based callbacks when context is unavailable.
        if args and args[0] is None:
            return None

        result = callback(*args)
        return await result if isawaitable(result) else result

    async def _process_quiz_response_fallback(
        self,
        *,
        context: Optional["QuizContext"],
        active_session: Any,
        response_text: str,
        send_next_question_callback,
        complete_session_callback,
        send_clarification_callback,
        original_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Local fallback when canonical response flow fails.

        This path keeps quiz progression working even when AI/integration layers fail.
        """
        if context is None:
            return {
                "success": False,
                "action": "error",
                "error": original_result.get(
                    "error", "Unable to process response without quiz context"
                ),
            }

        template = getattr(context, "template", None)
        questions = getattr(template, "questions", None) if template else None
        if not isinstance(questions, list) or not questions:
            return {
                "success": False,
                "action": "error",
                "error": "Quiz template unavailable for active session",
            }

        current_index = max(int(getattr(context, "current_question", 0) or 0), 0)
        if current_index >= len(questions):
            await self._invoke_callback(complete_session_callback, context)
            return {
                "success": True,
                "action": "quiz_completed",
                "session_id": str(getattr(active_session, "id", "")),
                "fallback": True,
            }

        processed = await self.process_response_with_swarm(context, response_text)
        if not processed.get("valid"):
            error_msg = processed.get("error") or original_result.get(
                "error", "Não consegui entender sua resposta."
            )
            await self._invoke_callback(send_clarification_callback, context, error_msg)
            return {
                "success": False,
                "action": "clarification_requested",
                "error": error_msg,
                "fallback": True,
            }

        current_question = questions[current_index]
        self._persist_fallback_response(
            context=context,
            active_session=active_session,
            question=current_question,
            current_index=current_index,
            response_text=response_text,
            processed_response=processed,
        )

        is_last_question = current_index >= len(questions) - 1
        if is_last_question:
            await self._invoke_callback(complete_session_callback, context)
            return {
                "success": True,
                "action": "quiz_completed",
                "session_id": str(getattr(active_session, "id", "")),
                "fallback": True,
            }

        try:
            advanced_session = self.quiz_session_service.advance_session(active_session.id)
            if advanced_session and hasattr(advanced_session, "current_question"):
                context.current_question = int(
                    getattr(advanced_session, "current_question", current_index + 1)
                    or current_index + 1
                )
            else:
                context.current_question = current_index + 1
        except Exception as exc:
            self._logger.warning("Failed to advance session in fallback path: %s", exc)
            context.current_question = current_index + 1

        await self._invoke_callback(send_next_question_callback, context)
        return {
            "success": True,
            "action": "next_question",
            "question_index": context.current_question,
            "fallback": True,
        }

    def _persist_fallback_response(
        self,
        *,
        context: "QuizContext",
        active_session: Any,
        question: Dict[str, Any],
        current_index: int,
        response_text: str,
        processed_response: Dict[str, Any],
    ) -> None:
        """Persist response when fallback processing succeeds."""
        try:
            response_type = str(question.get("type", QuestionType.OPEN_TEXT.value))
            valid_types = {item.value for item in QuestionType}
            if response_type not in valid_types:
                raise ValueError(f"Unsupported question type for fallback save: {response_type}")
            processed_value = processed_response.get("processed_value")
            if processed_value is None:
                processed_value = ""

            response_data = QuizResponseCreate(
                patient_id=context.patient_id,
                quiz_template_id=active_session.quiz_template_id,
                quiz_session_id=active_session.id,
                question_id=question.get("id", f"q_{current_index}"),
                question_text=question.get("text", f"Pergunta {current_index + 1}"),
                response_type=response_type,
                response_value=processed_value,
                response_metadata={
                    "fallback_mode": True,
                    "original_text": response_text,
                    "processed_value": processed_value,
                    "question_index": current_index,
                    "confidence": processed_response.get("confidence"),
                },
                responded_at=now_sao_paulo(),
            )
            self.quiz_response_service.create_response(response_data)
        except Exception as exc:
            self._logger.error("Failed to persist fallback quiz response: %s", exc)

    async def _invoke_interpretation_graph(self, prompt: str, thread_id: str) -> str:
        """Helper to call Gemini for interpretation. Phase 8 (AI-03): direct generate_content()."""
        from app.ai.client import get_gemini_client
        client = get_gemini_client()
        return await client.generate_content(
            prompt,
            output_kind=OutputKind.MESSAGE,
            profile=MESSAGE_STANDARD,
        )

    async def process_response_with_swarm(
        self, context: "QuizContext", response_text: str
    ) -> Dict[str, Any]:
        """Process response with swarm intelligence and AI analysis."""
        template = getattr(context, "template", None)
        questions = getattr(template, "questions", None) if template else None
        if not isinstance(questions, list) or not questions:
            return {
                "valid": False,
                "error": "Quiz template unavailable for active session",
            }

        current_index = max(int(getattr(context, "current_question", 0) or 0), 0)
        if current_index >= len(questions):
            return {"valid": False, "error": "No active question"}

        current_question = questions[current_index]

        # Basic processing
        basic_result = await self.basic_response_processing(
            current_question, response_text
        )

        # If basic processing is uncertain, use AI enhancement
        if (
            basic_result.get("confidence", 1.0)
            < self.ai_interpretation_confidence_threshold
        ):
            ai_result = None
            try:
                ai_result = await self.ai_enhanced_processing(
                    current_question, response_text, context
                )
            except Exception as exc:
                self._logger.warning(
                    "AI enhancement failed; keeping deterministic processing: %s",
                    exc,
                )

            if ai_result and ai_result.get("confidence", 0) > basic_result.get(
                "confidence", 0
            ):
                basic_result.update(ai_result)
                basic_result["ai_processed"] = True

        # Request swarm analysis for complex responses
        if basic_result.get("confidence", 1.0) < self.require_human_review_threshold:
            swarm_analysis = await self.request_swarm_analysis(
                context, response_text, basic_result
            )
            basic_result["swarm_analysis"] = swarm_analysis

        # Add context information
        basic_result.update(
            {
                "question_id": current_question["id"],
                "question_text": current_question["text"],
                "response_type": current_question["type"],
            }
        )

        return basic_result

    async def basic_response_processing(
        self, question: Dict, response_text: str
    ) -> Dict[str, Any]:
        """Basic response processing without AI."""
        question_type = question["type"]
        response_text = response_text.strip()

        if question_type == QuestionType.OPEN_TEXT.value:
            return {"valid": True, "processed_value": response_text, "confidence": 1.0}

        elif question_type == QuestionType.SCALE.value:
            # Try to extract number
            numbers = re.findall(r"\d+", response_text)

            if numbers:
                scale_value = int(numbers[0])
                if 1 <= scale_value <= 5:
                    return {
                        "valid": True,
                        "processed_value": str(scale_value),
                        "confidence": 1.0,
                    }

            return {
                "valid": False,
                "error": "Por favor, responda com um número de 1 a 5",
                "confidence": 0.0,
            }

        elif question_type == QuestionType.MULTIPLE_CHOICE.value:
            options = question.get("options", [])

            # Direct text match
            for option in options:
                option_text = option.get("text") or option.get("label") or ""
                if not option_text:
                    continue
                if (
                    response_text.lower() in option_text.lower()
                    or option_text.lower() in response_text.lower()
                ):
                    return {
                        "valid": True,
                        "processed_value": option["value"],
                        "confidence": 0.9,
                    }

            # Return uncertain result for AI processing
            return {
                "valid": False,
                "error": "Não consegui entender sua resposta",
                "confidence": 0.2,
                "options": options,
            }

        elif question_type == QuestionType.YES_NO.value:
            response_lower = response_text.lower()

            yes_words = ["sim", "yes", "s", "claro", "certamente", "com certeza"]
            no_words = ["não", "nao", "no", "n", "nunca", "jamais"]

            if any(word in response_lower for word in yes_words):
                return {"valid": True, "processed_value": "yes", "confidence": 0.9}
            elif any(word in response_lower for word in no_words):
                return {"valid": True, "processed_value": "no", "confidence": 0.9}

            return {
                "valid": False,
                "error": "Por favor, responda com 'sim' ou 'não'",
                "confidence": 0.0,
            }

        return {
            "valid": False,
            "error": "Tipo de pergunta não suportado",
            "confidence": 0.0,
        }

    async def ai_enhanced_processing(
        self, question: Dict, response_text: str, context: "QuizContext"
    ) -> Optional[Dict[str, Any]]:
        """AI-enhanced response processing using Gemini."""
        try:
            if not self.gemini_client:
                return None

            question_type = question["type"]

            recent_lines = []
            recent_responses = context.responses_so_far[-5:] if context.responses_so_far else []
            for idx, resp in enumerate(recent_responses, start=1):
                question_label = resp.get("question_text") or resp.get("question_id") or "Pergunta"
                value_label = resp.get("processed_value")
                recent_lines.append(f"{idx}. {question_label}: {value_label}")

            recent_block = (
                "\nContexto recente (últimas respostas):\n" + "\n".join(recent_lines)
                if recent_lines
                else ""
            )

            if question_type == QuestionType.SCALE.value:
                patient_name = getattr(getattr(context, "patient_data", None), "name", "Paciente")
                prompt = f"""
                Analise a resposta do paciente para uma pergunta de escala de 1 a 5:

                Pergunta: {question["text"]}
                Resposta: "{response_text}"
                {recent_block}

                Contexto do paciente: {patient_name} está em tratamento de terapia hormonal.

                Escala:
                1 = Muito ruim/baixo/negativo
                2 = Ruim/baixo/negativo
                3 = Neutro/regular/médio
                4 = Bom/alto/positivo
                5 = Muito bom/alto/positivo

                Retorne apenas o número (1-5) que melhor representa a resposta.
                Se não conseguir interpretar, retorne "INVALID".

                Regras de saída (obrigatório):
                - Responda apenas com "1", "2", "3", "4", "5" ou "INVALID"
                - Não inclua explicações, raciocínios ou meta-comentários
                - Não mencione prompt, instruções, políticas ou sistema
                - Não use markdown ou blocos de código
                """

            elif question_type == QuestionType.MULTIPLE_CHOICE.value:
                options_text = "\n".join(
                    [
                        f"- {opt.get('value')}: {opt.get('text') or opt.get('label')}"
                        for opt in question.get("options", [])
                    ]
                )

                prompt = f"""
                Analise a resposta do paciente e determine qual opção ela melhor representa:

                Pergunta: {question["text"]}
                Resposta: "{response_text}"
                {recent_block}

                Opções disponíveis:
                {options_text}

                Retorne apenas o valor (value) da opção que melhor corresponde.
                Se não conseguir determinar, retorne "INVALID".

                Regras de saída (obrigatório):
                - Responda apenas com o value da opção ou "INVALID"
                - Não inclua explicações, raciocínios ou meta-comentários
                - Não mencione prompt, instruções, políticas ou sistema
                - Não use markdown ou blocos de código
                """
            else:
                return None

            # Use helper to call LangGraph
            ai_response = await self._invoke_interpretation_graph(
                prompt,
                thread_id=self._build_interpretation_thread_id(context, question),
            )

            if not ai_response:
                raise ValueError("AI returned empty response")
            if ai_response.strip() == "INVALID":
                raise ValueError("AI could not interpret response")

            # Validate AI response
            if question_type == QuestionType.SCALE.value:
                if ai_response.strip().isdigit():
                    value = int(ai_response.strip())
                    if 1 <= value <= 5:
                        return {
                            "valid": True,
                            "processed_value": str(value),
                            "confidence": 0.8,
                            "ai_interpreted": True,
                        }

            elif question_type == QuestionType.MULTIPLE_CHOICE.value:
                options = question.get("options", [])
                option_values = [opt["value"] for opt in options]
                if ai_response.strip() in option_values:
                    return {
                        "valid": True,
                        "processed_value": ai_response.strip(),
                        "confidence": 0.8,
                        "ai_interpreted": True,
                    }

            raise ValueError("AI response did not match any valid option")

        except Exception as e:
            self._logger.error(f"AI response processing failed: {e}")
            return None

    def _build_interpretation_thread_id(
        self, context: "QuizContext", question: Dict[str, Any]
    ) -> str:
        """Build deterministic thread_id for quiz interpretation graph calls."""
        patient_key = sanitize_thread_component(context.patient_id)
        session_key = sanitize_thread_component(getattr(context.session, "id", None))
        question_key = sanitize_thread_component(
            question.get("id", context.current_question)
        )
        return (
            f"quiz:interpretation:"
            f"patient:{patient_key}:session:{session_key}:question:{question_key}"
        )

    async def request_swarm_analysis(
        self,
        context: "QuizContext",
        response_text: str,
        basic_result: Dict,
        send_message_callback=None,
    ) -> Dict[str, Any]:
        """Request analysis from other agents in the swarm."""
        try:
            if not send_message_callback:
                return {}

            # Request analysis from relevant agents
            analysis_requests = {
                "mood_analysis": ALERT_ANALYZER_ID,
                "medical_significance": PATIENT_MONITOR_ID,
                "flow_impact": FLOW_COORDINATOR_ID,
            }

            template = getattr(context, "template", None)
            questions = getattr(template, "questions", None) if template else None
            current_index = max(
                int(getattr(context, "current_question", 0) or 0), 0
            )
            question_context = (
                questions[current_index]
                if isinstance(questions, list) and current_index < len(questions)
                else {}
            )

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
                            "question_context": question_context,
                            "basic_processing": basic_result,
                            "analysis_type": analysis_type,
                        },
                        MessagePriority.HIGH,
                    )

                    # For now, simulate analysis results
                    # In real implementation, would wait for responses
                    swarm_analysis[analysis_type] = {
                        "agent": agent_id,
                        "confidence": 0.7,
                        "insights": ["response_processed_by_swarm"],
                    }

                except Exception as e:
                    self._logger.error(
                        f"Failed to request {analysis_type} from {agent_id}: {e}"
                    )

            return swarm_analysis

        except Exception as e:
            self._logger.error(f"Swarm analysis request failed: {e}")
            return {}
