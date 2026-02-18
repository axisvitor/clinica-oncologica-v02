"""
AI Flow Integration - AI service integration for Flow Services (QW-021).

This module provides integration between the consolidated flow system and
AI services (Google Gemini), enabling AI-powered flow decisions and responses.

Migration Note:
    This consolidates AI integration from:
    - flow.py (AI integration logic)
    - Various AI-related flow handlers
    - Enhanced flow engine AI features
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
import logging
import json

from ..types import (
    FlowContext,
)
from ..config import get_flow_config
from app.config import settings
from app.ai.client import get_gemini_client
from app.ai.pii_redaction import redact_conversation_history, redact_patient_context
from app.services.ai.guardrails import OutputKind
from app.utils.async_helpers import run_async_in_thread
from app.utils.timezone import now_sao_paulo, to_sao_paulo


logger = logging.getLogger(__name__)


class AIFlowIntegration:
    """
    Integration service for AI-powered flows.

    Handles AI interactions, decision-making, and response generation
    within flow execution.
    """

    def __init__(self):
        """Initialize AI flow integration."""
        self.config = get_flow_config().integrations
        self._gemini_client = get_gemini_client()

        # AI interaction tracking
        self._ai_interactions: Dict[UUID, List[Dict[str, Any]]] = {}
        self._ai_decisions: Dict[UUID, List[Dict[str, Any]]] = {}

        logger.info("AIFlowIntegration initialized")

    def _should_use_real_ai(self) -> bool:
        """Use real AI whenever simulation is explicitly disabled."""
        api_key = getattr(settings, "AI_GEMINI_API_KEY", "")
        return (
            not settings.ALLOW_AI_SIMULATION
            and isinstance(api_key, str)
            and bool(api_key.strip())
        )

    def _run_async_safe(self, coro):
        """
        Execute async coroutines safely from sync integration methods.
        """
        return run_async_in_thread(coro)

    def _sanitize_context_payload(self, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Redact PII before sending any payload to external AI providers."""
        if not isinstance(payload, dict):
            return {}
        return redact_patient_context(payload)

    def _sanitize_free_text(self, text: str) -> str:
        """Redact common PII patterns from free text while preserving semantics."""
        if not text:
            return ""
        redacted = redact_conversation_history([text])
        if redacted and isinstance(redacted[0], str):
            return redacted[0]
        return text

    # ========================================================================
    # AI Response Generation
    # ========================================================================

    def generate_response(
        self,
        flow_instance_id: UUID,
        prompt: str,
        context: Optional[FlowContext] = None,
    ) -> Optional[str]:
        """
        Generate AI response for flow step.

        Args:
            flow_instance_id: Flow instance ID.
            prompt: Prompt for AI.
            context: Optional flow context for additional information.

        Returns:
            Generated response if successful, None otherwise.
        """
        if not self.config.enable_ai_integration:
            logger.warning("AI integration is disabled")
            return None

        try:
            if self._should_use_real_ai():
                context_payload: Dict[str, Any] = {}
                if context:
                    if hasattr(context, "to_dict"):
                        context_payload = context.to_dict()
                    elif isinstance(context, dict):
                        context_payload = context
                safe_context_payload = self._sanitize_context_payload(context_payload)

                ai_prompt = (
                    "Reescreva a mensagem para acompanhamento de paciente oncológico. "
                    "Retorne apenas o texto final em português do Brasil.\n\n"
                    f"CONTEXTO:\n{json.dumps(safe_context_payload, ensure_ascii=False, default=str)}\n\n"
                    f"MENSAGEM BASE:\n{prompt}"
                )
                response = self._run_async_safe(
                    self._gemini_client.generate_content(
                        ai_prompt,
                        output_kind=OutputKind.MESSAGE,
                        require_ending_punctuation=True,
                        guardrail_retries=2,
                    )
                )
            else:
                # Simulation fallback for non-production environments.
                response = f"AI response to: {prompt[:50]}..."

            # Track interaction
            self._record_ai_interaction(
                flow_instance_id,
                "generate_response",
                prompt,
                response,
            )

            logger.debug(f"Generated AI response for flow {flow_instance_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to generate AI response: {e}", exc_info=True)
            return None

    def generate_personalized_message(
        self,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
        message_type: str,
    ) -> Optional[str]:
        """
        Generate personalized message using AI.

        Args:
            flow_instance_id: Flow instance ID.
            patient_data: Patient information.
            message_type: Type of message (greeting, reminder, etc.).

        Returns:
            Generated message if successful, None otherwise.
        """
        if not self.config.enable_ai_integration:
            return None

        # Build prompt
        prompt = self._build_message_prompt(patient_data, message_type)

        return self.generate_response(flow_instance_id, prompt)

    # ========================================================================
    # AI Decision Making
    # ========================================================================

    def make_decision(
        self,
        flow_instance_id: UUID,
        decision_type: str,
        decision_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Make AI-powered decision in flow.

        Args:
            flow_instance_id: Flow instance ID.
            decision_type: Type of decision to make.
            decision_data: Data for decision-making.

        Returns:
            Decision result if successful, None otherwise.
        """
        if not self.config.enable_ai_integration:
            logger.warning("AI integration is disabled")
            return None

        try:
            # Build decision prompt with redacted context
            prompt = self._build_decision_prompt(
                decision_type, self._sanitize_context_payload(decision_data)
            )
            if self._should_use_real_ai():
                raw_response = self._run_async_safe(
                    self._gemini_client.generate_content(
                        f"{prompt}\n\nResponda apenas JSON com recommendation, confidence e reasoning.",
                        output_kind=OutputKind.JSON,
                        required_keys=["recommendation", "confidence", "reasoning"],
                    )
                )
                parsed = json.loads(raw_response)
                confidence_raw = parsed.get("confidence", 0.75)
                try:
                    confidence = float(confidence_raw)
                except (TypeError, ValueError):
                    confidence = 0.75
                decision = {
                    "decision_type": decision_type,
                    "recommendation": str(parsed.get("recommendation", "continue")),
                    "confidence": confidence,
                    "reasoning": str(parsed.get("reasoning", "")),
                }
            else:
                # Simulation fallback
                decision = {
                    "decision_type": decision_type,
                    "recommendation": "continue",
                    "confidence": 0.85,
                    "reasoning": "Based on provided data",
                }

            # Track decision
            self._record_ai_decision(
                flow_instance_id,
                decision_type,
                decision_data,
                decision,
            )

            logger.debug(
                f"AI decision made for flow {flow_instance_id}: {decision_type}"
            )
            return decision

        except Exception as e:
            logger.error(f"Failed to make AI decision: {e}", exc_info=True)
            return {
                "decision_type": decision_type,
                "recommendation": "continue",
                "confidence": 0.75,
                "reasoning": "Fallback decision due to AI processing error",
            }

    def evaluate_condition(
        self,
        flow_instance_id: UUID,
        condition: str,
        context_data: Dict[str, Any],
    ) -> Optional[bool]:
        """
        Evaluate condition using AI.

        Args:
            flow_instance_id: Flow instance ID.
            condition: Condition to evaluate.
            context_data: Context data for evaluation.

        Returns:
            Evaluation result (True/False) if successful, None otherwise.
        """
        if not self.config.enable_ai_integration:
            return None

        try:
            # Build evaluation prompt
            safe_context_data = self._sanitize_context_payload(context_data)
            prompt = f"Evaluate condition: {condition}\nContext: {safe_context_data}"

            if self._should_use_real_ai():
                raw_response = self._run_async_safe(
                    self._gemini_client.generate_content(
                        f"{prompt}\nResponda apenas JSON com a chave `result` (true ou false).",
                        output_kind=OutputKind.JSON,
                        required_keys=["result"],
                    )
                )
                parsed = json.loads(raw_response)
                result = bool(parsed.get("result", False))
            else:
                # Simulation fallback
                result = True

            # Track interaction
            self._record_ai_interaction(
                flow_instance_id,
                "evaluate_condition",
                prompt,
                str(result),
            )

            logger.debug(
                f"AI condition evaluated for flow {flow_instance_id}: {result}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to evaluate condition: {e}", exc_info=True)
            return None

    # ========================================================================
    # AI Analysis
    # ========================================================================

    def analyze_response(
        self,
        flow_instance_id: UUID,
        question: str,
        response: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze user response using AI.

        Args:
            flow_instance_id: Flow instance ID.
            question: Question that was asked.
            response: User's response.

        Returns:
            Analysis result if successful, None otherwise.
        """
        if not self.config.enable_ai_integration:
            return None

        try:
            # Build analysis prompt
            safe_question = self._sanitize_free_text(question)
            safe_response = self._sanitize_free_text(response)
            prompt = (
                f"Question: {safe_question}\nResponse: {safe_response}\n"
                "Analyze sentiment and extract key information."
            )

            if self._should_use_real_ai():
                raw_response = self._run_async_safe(
                    self._gemini_client.generate_content(
                        (
                            "Analise a resposta e retorne apenas JSON com as chaves "
                            "sentiment, confidence, key_points, concerns e follow_up_needed.\n\n"
                            f"{prompt}"
                        ),
                        output_kind=OutputKind.JSON,
                        required_keys=[
                            "sentiment",
                            "confidence",
                            "key_points",
                            "concerns",
                            "follow_up_needed",
                        ],
                    )
                )
                parsed = json.loads(raw_response)
                confidence_raw = parsed.get("confidence", 0.75)
                try:
                    confidence = float(confidence_raw)
                except (TypeError, ValueError):
                    confidence = 0.75
                analysis = {
                    "sentiment": str(parsed.get("sentiment", "neutral")),
                    "confidence": confidence,
                    "key_points": parsed.get("key_points", []) or [],
                    "concerns": parsed.get("concerns", []) or [],
                    "follow_up_needed": bool(parsed.get("follow_up_needed", False)),
                }
            else:
                # Simulation fallback
                analysis = {
                    "sentiment": "neutral",
                    "confidence": 0.75,
                    "key_points": [],
                    "concerns": [],
                    "follow_up_needed": False,
                }

            # Track interaction
            self._record_ai_interaction(
                flow_instance_id,
                "analyze_response",
                prompt,
                str(analysis),
            )

            logger.debug(f"AI response analyzed for flow {flow_instance_id}")
            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze response: {e}", exc_info=True)
            fallback_analysis = {
                "sentiment": "neutral",
                "confidence": 0.5,
                "key_points": [],
                "concerns": [],
                "follow_up_needed": False,
            }
            return fallback_analysis

    def extract_symptoms(
        self,
        flow_instance_id: UUID,
        text: str,
    ) -> List[str]:
        """
        Extract symptoms from text using AI.

        Args:
            flow_instance_id: Flow instance ID.
            text: Text to analyze.

        Returns:
            List of extracted symptoms.
        """
        if not self.config.enable_ai_integration:
            return []

        try:
            if self._should_use_real_ai():
                raw_response = self._run_async_safe(
                    self._gemini_client.generate_content(
                        (
                            "Extraia sintomas mencionados no texto e retorne apenas JSON "
                            "com a chave `symptoms` (lista de strings).\n\n"
                            f"TEXTO:\n{self._sanitize_free_text(text)}"
                        ),
                        output_kind=OutputKind.JSON,
                        required_keys=["symptoms"],
                    )
                )
                parsed = json.loads(raw_response)
                symptoms = [
                    str(item).strip()
                    for item in (parsed.get("symptoms") or [])
                    if str(item).strip()
                ]
            else:
                # Simulation fallback
                symptoms = []

            # Track interaction
            self._record_ai_interaction(
                flow_instance_id,
                "extract_symptoms",
                text,
                str(symptoms),
            )

            return symptoms

        except Exception as e:
            logger.error(f"Failed to extract symptoms: {e}", exc_info=True)
            return []

    # ========================================================================
    # AI Recommendations
    # ========================================================================

    def get_next_step_recommendation(
        self,
        flow_instance_id: UUID,
        context: FlowContext,
    ) -> Optional[str]:
        """
        Get AI recommendation for next flow step.

        Args:
            flow_instance_id: Flow instance ID.
            context: Current flow context.

        Returns:
            Recommended next step ID if successful, None otherwise.
        """
        if not self.config.enable_ai_integration:
            return None

        try:
            # Build recommendation prompt
            prompt = self._build_recommendation_prompt(context)
            if self._should_use_real_ai():
                raw_response = self._run_async_safe(
                    self._gemini_client.generate_content(
                        (
                            f"{prompt}\n"
                            "Responda apenas JSON com a chave `next_step_id`."
                        ),
                        output_kind=OutputKind.JSON,
                        required_keys=["next_step_id"],
                    )
                )
                recommendation = str(json.loads(raw_response).get("next_step_id") or "")
                if not recommendation:
                    recommendation = "next_step_id"
            else:
                # Simulation fallback
                recommendation = "next_step_id"

            logger.debug(
                f"AI next step recommendation for flow {flow_instance_id}: {recommendation}"
            )
            return recommendation

        except Exception as e:
            logger.error(f"Failed to get recommendation: {e}", exc_info=True)
            return None

    def suggest_interventions(
        self,
        flow_instance_id: UUID,
        patient_data: Dict[str, Any],
        recent_responses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Suggest interventions based on patient data.

        Args:
            flow_instance_id: Flow instance ID.
            patient_data: Patient information.
            recent_responses: Recent patient responses.

        Returns:
            List of suggested interventions.
        """
        if not self.config.enable_ai_integration:
            return []

        try:
            if self._should_use_real_ai():
                safe_patient_data = self._sanitize_context_payload(patient_data)
                patient_names = [
                    str(v).strip()
                    for v in (
                        patient_data.get("name"),
                        patient_data.get("patient_name"),
                    )
                    if isinstance(v, str) and v.strip()
                ]
                safe_recent_responses = redact_conversation_history(
                    recent_responses, patient_names=patient_names
                )
                raw_response = self._run_async_safe(
                    self._gemini_client.generate_content(
                        (
                            "Sugira intervenções para acompanhamento de paciente oncológico. "
                            "Retorne apenas JSON com `interventions` (lista de objetos "
                            "com type, priority, rationale).\n\n"
                            f"patient_data={json.dumps(safe_patient_data, ensure_ascii=False, default=str)}\n"
                            f"recent_responses={json.dumps(safe_recent_responses, ensure_ascii=False, default=str)}"
                        ),
                        output_kind=OutputKind.JSON,
                        required_keys=["interventions"],
                    )
                )
                parsed = json.loads(raw_response)
                interventions = parsed.get("interventions", []) or []
                if not isinstance(interventions, list):
                    interventions = []
            else:
                # Simulation fallback
                interventions = []

            logger.debug(
                f"AI interventions suggested for flow {flow_instance_id}: {len(interventions)}"
            )
            return interventions

        except Exception as e:
            logger.error(f"Failed to suggest interventions: {e}", exc_info=True)
            return []

    # ========================================================================
    # AI Interaction Tracking
    # ========================================================================

    def _record_ai_interaction(
        self,
        flow_instance_id: UUID,
        interaction_type: str,
        input_data: str,
        output_data: str,
    ) -> None:
        """
        Record AI interaction for tracking.

        Args:
            flow_instance_id: Flow instance ID.
            interaction_type: Type of interaction.
            input_data: Input data.
            output_data: Output data.
        """
        if flow_instance_id not in self._ai_interactions:
            self._ai_interactions[flow_instance_id] = []

        interaction = {
            "type": interaction_type,
            "input": input_data[:500],  # Truncate for storage
            "output": output_data[:500],  # Truncate for storage
            "timestamp": now_sao_paulo().isoformat(),
        }

        self._ai_interactions[flow_instance_id].append(interaction)

        # Limit history size
        from ..constants import FlowEngine

        if (
            len(self._ai_interactions[flow_instance_id])
            > FlowEngine.MAX_AI_INTERACTION_HISTORY
        ):
            self._ai_interactions[flow_instance_id] = self._ai_interactions[
                flow_instance_id
            ][-FlowEngine.MAX_AI_INTERACTION_HISTORY :]

    def _record_ai_decision(
        self,
        flow_instance_id: UUID,
        decision_type: str,
        decision_data: Dict[str, Any],
        decision_result: Dict[str, Any],
    ) -> None:
        """
        Record AI decision for tracking.

        Args:
            flow_instance_id: Flow instance ID.
            decision_type: Type of decision.
            decision_data: Decision input data.
            decision_result: Decision result.
        """
        if flow_instance_id not in self._ai_decisions:
            self._ai_decisions[flow_instance_id] = []

        decision = {
            "type": decision_type,
            "data": decision_data,
            "result": decision_result,
            "timestamp": now_sao_paulo().isoformat(),
        }

        self._ai_decisions[flow_instance_id].append(decision)

        # Limit history size
        from ..constants import FlowEngine

        if len(self._ai_decisions[flow_instance_id]) > FlowEngine.MAX_AI_DECISION_HISTORY:
            self._ai_decisions[flow_instance_id] = self._ai_decisions[flow_instance_id][
                -FlowEngine.MAX_AI_DECISION_HISTORY :
            ]

    # ========================================================================
    # Query Methods
    # ========================================================================

    def get_ai_interactions(
        self,
        flow_instance_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Get AI interactions for a flow.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            List of AI interactions.
        """
        return self._ai_interactions.get(flow_instance_id, [])

    def get_ai_decisions(
        self,
        flow_instance_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Get AI decisions for a flow.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            List of AI decisions.
        """
        return self._ai_decisions.get(flow_instance_id, [])

    def get_ai_usage_stats(self) -> Dict[str, Any]:
        """
        Get AI usage statistics.

        Returns:
            Dictionary with AI usage stats.
        """
        total_interactions = sum(
            len(interactions) for interactions in self._ai_interactions.values()
        )
        total_decisions = sum(
            len(decisions) for decisions in self._ai_decisions.values()
        )

        return {
            "total_flows_with_ai": len(self._ai_interactions),
            "total_interactions": total_interactions,
            "total_decisions": total_decisions,
            "enabled": self.config.enable_ai_integration,
        }

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _build_message_prompt(
        self,
        patient_data: Dict[str, Any],
        message_type: str,
    ) -> str:
        """
        Build prompt for message generation.

        Args:
            patient_data: Patient information.
            message_type: Type of message.

        Returns:
            Constructed prompt.
        """
        safe_patient_data = self._sanitize_context_payload(patient_data)
        patient_name = safe_patient_data.get("name", "Paciente")

        prompts = {
            "greeting": f"Generate a warm, personalized greeting for {patient_name}.",
            "reminder": f"Generate a friendly reminder for {patient_name} to complete their health assessment.",
            "encouragement": f"Generate an encouraging message for {patient_name} about their treatment progress.",
            "follow_up": f"Generate a follow-up message for {patient_name} after their recent appointment.",
        }

        return prompts.get(message_type, f"Generate a message for {patient_name}.")

    def _build_decision_prompt(
        self,
        decision_type: str,
        decision_data: Dict[str, Any],
    ) -> str:
        """
        Build prompt for decision-making.

        Args:
            decision_type: Type of decision.
            decision_data: Decision data.

        Returns:
            Constructed prompt.
        """
        return f"Make a decision of type '{decision_type}' based on: {decision_data}"

    def _build_recommendation_prompt(self, context: FlowContext) -> str:
        """
        Build prompt for next step recommendation.

        Args:
            context: Flow context.

        Returns:
            Constructed prompt.
        """
        return (
            f"Recommend next step for flow {context.flow_type.value} "
            f"with {len(context.steps_completed)} steps completed."
        )

    # ========================================================================
    # Cleanup
    # ========================================================================

    def cleanup_old_data(self, days: int = 7) -> int:
        """
        Clean up old AI interaction data.

        Args:
            days: Age threshold in days.

        Returns:
            Number of flows cleaned up.
        """
        cutoff_date = now_sao_paulo() - timedelta(days=days)
        cleaned = 0

        def _parse_timestamp(raw_value: Any) -> Optional[datetime]:
            if not isinstance(raw_value, str):
                return None
            try:
                parsed = datetime.fromisoformat(raw_value)
            except ValueError:
                return None
            return to_sao_paulo(parsed)

        # Clean up interactions
        for flow_id in list(self._ai_interactions.keys()):
            interactions = self._ai_interactions[flow_id]
            recent_interactions = [
                i
                for i in interactions
                if (
                    (_timestamp := _parse_timestamp(i.get("timestamp"))) is not None
                    and _timestamp > cutoff_date
                )
            ]

            if not recent_interactions:
                del self._ai_interactions[flow_id]
                cleaned += 1
            else:
                self._ai_interactions[flow_id] = recent_interactions

        # Clean up decisions
        for flow_id in list(self._ai_decisions.keys()):
            decisions = self._ai_decisions[flow_id]
            recent_decisions = [
                d
                for d in decisions
                if (
                    (_timestamp := _parse_timestamp(d.get("timestamp"))) is not None
                    and _timestamp > cutoff_date
                )
            ]

            if not recent_decisions:
                del self._ai_decisions[flow_id]
                cleaned += 1
            else:
                self._ai_decisions[flow_id] = recent_decisions

        if cleaned > 0:
            logger.info(f"Cleaned up AI data for {cleaned} old flows")

        return cleaned


# ============================================================================
# Exports
# ============================================================================

__all__ = ["AIFlowIntegration"]
