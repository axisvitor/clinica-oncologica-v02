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

from ..types import (
    FlowContext,
)
from ..config import get_flow_config


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

        # AI interaction tracking
        self._ai_interactions: Dict[UUID, List[Dict[str, Any]]] = {}
        self._ai_decisions: Dict[UUID, List[Dict[str, Any]]] = {}

        logger.info("AIFlowIntegration initialized")

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
            # In production: Call AI service (e.g., Google Gemini)
            # response = ai_service.generate(prompt, context_data)

            # Mock response for now
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
            # Build decision prompt
            self._build_decision_prompt(decision_type, decision_data)

            # In production: Call AI service for decision
            # decision = ai_service.make_decision(prompt, decision_data)

            # Mock decision
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
            return None

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
            prompt = f"Evaluate condition: {condition}\nContext: {context_data}"

            # In production: Call AI service
            # result = ai_service.evaluate_condition(condition, context_data)

            # Mock evaluation
            result = True  # Simplified for now

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
            prompt = f"Question: {question}\nResponse: {response}\nAnalyze sentiment and extract key information."

            # In production: Call AI service
            # analysis = ai_service.analyze_text(response, question)

            # Mock analysis
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
            return None

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
            # In production: Call AI service for NER
            # symptoms = ai_service.extract_entities(text, entity_type="symptom")

            # Mock symptom extraction
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
            self._build_recommendation_prompt(context)

            # In production: Call AI service
            # recommendation = ai_service.recommend_next_step(context_data)

            # Mock recommendation
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
            # In production: Call AI service for recommendations
            # interventions = ai_service.suggest_interventions(patient_data, recent_responses)

            # Mock interventions
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
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._ai_interactions[flow_instance_id].append(interaction)

        # Limit history size
        if len(self._ai_interactions[flow_instance_id]) > 100:
            self._ai_interactions[flow_instance_id] = self._ai_interactions[
                flow_instance_id
            ][-100:]

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
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._ai_decisions[flow_instance_id].append(decision)

        # Limit history size
        if len(self._ai_decisions[flow_instance_id]) > 50:
            self._ai_decisions[flow_instance_id] = self._ai_decisions[flow_instance_id][
                -50:
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
        patient_name = patient_data.get("name", "Patient")

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
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        cleaned = 0

        # Clean up interactions
        for flow_id in list(self._ai_interactions.keys()):
            interactions = self._ai_interactions[flow_id]
            recent_interactions = [
                i
                for i in interactions
                if datetime.fromisoformat(i["timestamp"]) > cutoff_date
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
                if datetime.fromisoformat(d["timestamp"]) > cutoff_date
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
