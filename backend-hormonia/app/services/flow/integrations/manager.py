"""
Flow Integration Manager - Integration coordinator for Flow Services (QW-021).

This module provides the main integration management service that coordinates
all flow integrations (Quiz, AI, Message, etc.).

Migration Note:
    This consolidates integration coordination from:
    - flow.py (FlowEngineIntegrationService)
    - Various integration handlers scattered across flow services
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from uuid import UUID
import logging
import inspect

from ..types import (
    FlowContext,
    FlowStepData,
)
from ..config import get_flow_config

from .quiz_integration import QuizFlowIntegration
from .ai_integration import AIFlowIntegration
from .base import FlowIntegration
from .plugins import QuizIntegrationPlugin, AIIntegrationPlugin


logger = logging.getLogger(__name__)


class FlowIntegrationManager:
    """
    Main integration coordinator for Flow Services.

    Manages all external integrations (Quiz, AI, Messages, etc.)
    and provides a unified interface for flow integration operations.
    """

    def __init__(
        self,
        quiz_integration: Optional[QuizFlowIntegration] = None,
        ai_integration: Optional[AIFlowIntegration] = None,
    ):
        """
        Initialize integration manager.

        Args:
            quiz_integration: Optional quiz integration instance.
            ai_integration: Optional AI integration instance.
        """
        self.config = get_flow_config().integrations

        # Initialize integrations
        self.quiz = quiz_integration or QuizFlowIntegration()
        self.ai = ai_integration or AIFlowIntegration()
        self._plugins: Dict[str, FlowIntegration] = {}
        self._register_builtin_plugins()

        logger.info("FlowIntegrationManager initialized")

    # ------------------------------------------------------------------ #
    # Plugin management
    # ------------------------------------------------------------------ #

    def _register_builtin_plugins(self) -> None:
        if self.config.enable_quiz_integration:
            self.register_plugin(QuizIntegrationPlugin(self.quiz))
        if self.config.enable_ai_integration:
            self.register_plugin(AIIntegrationPlugin(self.ai))

    def register_plugin(self, plugin: FlowIntegration) -> None:
        self._plugins[plugin.name] = plugin
        logger.info("Registered flow integration plugin: %s", plugin.name)

    async def notify(
        self,
        hook: str,
        context: FlowContext,
        template: Dict[str, Any],
        *args: Any,
    ) -> None:
        for plugin in self._plugins.values():
            handler = getattr(plugin, hook, None)
            if not handler:
                continue
            result = handler(context, template, *args)
            if inspect.isawaitable(result):
                await result

    # ========================================================================
    # Quiz Integration
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
            quiz_type: Type of quiz.
            quiz_data: Optional initial quiz data.

        Returns:
            Dictionary with quiz flow information.
        """
        return self.quiz.create_quiz_flow(patient_id, quiz_type, quiz_data)

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
        return self.quiz.complete_quiz_flow(flow_instance_id, final_data)

    def get_quiz_responses(
        self,
        flow_instance_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Get all quiz responses for a flow.

        Args:
            flow_instance_id: Flow instance ID.

        Returns:
            Dictionary with responses, or None if not found.
        """
        return self.quiz.get_quiz_responses(flow_instance_id)

    # ========================================================================
    # AI Integration
    # ========================================================================

    def generate_ai_response(
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
            context: Optional flow context.

        Returns:
            Generated response if successful, None otherwise.
        """
        return self.ai.generate_response(flow_instance_id, prompt, context)

    def make_ai_decision(
        self,
        flow_instance_id: UUID,
        decision_type: str,
        decision_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Make AI-powered decision in flow.

        Args:
            flow_instance_id: Flow instance ID.
            decision_type: Type of decision.
            decision_data: Decision data.

        Returns:
            Decision result if successful, None otherwise.
        """
        return self.ai.make_decision(flow_instance_id, decision_type, decision_data)

    def analyze_user_response(
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
        return self.ai.analyze_response(flow_instance_id, question, response)

    # ========================================================================
    # Step Processing with Integrations
    # ========================================================================

    def process_step_with_integrations(
        self,
        flow_instance_id: UUID,
        step_data: FlowStepData,
        context: FlowContext,
    ) -> Dict[str, Any]:
        """
        Process flow step with appropriate integrations.

        Args:
            flow_instance_id: Flow instance ID.
            step_data: Step data.
            context: Flow context.

        Returns:
            Dictionary with processing results.
        """
        results = {
            "step_id": step_data.step_id,
            "integrations_used": [],
            "data": {},
        }

        # Check if AI integration is needed
        if self._should_use_ai_for_step(step_data):
            ai_result = self._process_with_ai(flow_instance_id, step_data, context)
            if ai_result:
                results["integrations_used"].append("ai")
                results["data"]["ai"] = ai_result

        # Check if quiz integration is needed
        if self._should_use_quiz_for_step(step_data):
            quiz_result = self._process_with_quiz(flow_instance_id, step_data, context)
            if quiz_result:
                results["integrations_used"].append("quiz")
                results["data"]["quiz"] = quiz_result

        return results

    def process_response_with_integrations(
        self,
        flow_instance_id: UUID,
        step_data: FlowStepData,
        user_response: str,
        context: FlowContext,
    ) -> Dict[str, Any]:
        """
        Process user response with appropriate integrations.

        Args:
            flow_instance_id: Flow instance ID.
            step_data: Step data.
            user_response: User's response.
            context: Flow context.

        Returns:
            Dictionary with processing results.
        """
        results = {
            "response": user_response,
            "processed_by": [],
            "analysis": {},
        }

        # AI analysis
        if self.config.enable_ai_integration:
            question = step_data.input_data.get("question", "")
            analysis = self.ai.analyze_response(
                flow_instance_id, question, user_response
            )
            if analysis:
                results["processed_by"].append("ai")
                results["analysis"]["ai"] = analysis

        # Quiz response recording
        if self._is_quiz_flow(context):
            recorded = self.quiz.record_quiz_response(
                flow_instance_id,
                step_data.step_id,
                user_response,
            )
            if recorded:
                results["processed_by"].append("quiz")

        return results

    # ========================================================================
    # Integration Health and Status
    # ========================================================================

    def get_integration_status(self) -> Dict[str, Any]:
        """
        Get status of all integrations.

        Returns:
            Dictionary with integration status information.
        """
        return {
            "quiz": {
                "enabled": self.config.enable_quiz_integration,
                "active_flows": len(self.quiz.list_active_quiz_flows()),
            },
            "ai": {
                "enabled": self.config.enable_ai_integration,
                "usage_stats": self.ai.get_ai_usage_stats(),
            },
            "message": {
                "enabled": self.config.enable_message_sending,
                "rate_limit": self.config.message_rate_limit_per_minute,
            },
        }

    def get_integration_metrics(self) -> Dict[str, Any]:
        """
        Get metrics for all integrations.

        Returns:
            Dictionary with integration metrics.
        """
        return {
            "quiz": {
                "total_flows": len(self.quiz._quiz_flows),
                "active_flows": len(self.quiz.list_active_quiz_flows()),
            },
            "ai": self.ai.get_ai_usage_stats(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ========================================================================
    # Cleanup and Maintenance
    # ========================================================================

    def cleanup_old_data(self, days: int = 7) -> Dict[str, int]:
        """
        Clean up old integration data.

        Args:
            days: Age threshold in days.

        Returns:
            Dictionary with cleanup counts per integration.
        """
        results = {}

        # Quiz cleanup
        quiz_cleaned = self.quiz.cleanup_old_flows(days)
        results["quiz_flows_cleaned"] = quiz_cleaned

        # AI cleanup
        ai_cleaned = self.ai.cleanup_old_data(days)
        results["ai_data_cleaned"] = ai_cleaned

        logger.info(f"Integration cleanup completed: {results}")
        return results

    def cleanup_expired_flows(self) -> int:
        """
        Clean up expired flows across integrations.

        Returns:
            Total number of flows cleaned up.
        """
        total_cleaned = 0

        # Quiz flows
        quiz_cleaned = self.quiz.cleanup_expired_flows()
        total_cleaned += quiz_cleaned

        logger.info(f"Cleaned up {total_cleaned} expired flows")
        return total_cleaned

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _should_use_ai_for_step(self, step_data: FlowStepData) -> bool:
        """
        Check if AI should be used for this step.

        Args:
            step_data: Step data.

        Returns:
            True if AI should be used, False otherwise.
        """
        if not self.config.enable_ai_integration:
            return False

        # Check step metadata for AI flag
        return step_data.metadata.get("use_ai", False)

    def _should_use_quiz_for_step(self, step_data: FlowStepData) -> bool:
        """
        Check if quiz integration should be used for this step.

        Args:
            step_data: Step data.

        Returns:
            True if quiz should be used, False otherwise.
        """
        if not self.config.enable_quiz_integration:
            return False

        # Check step metadata for quiz flag
        return step_data.metadata.get("is_quiz_step", False)

    def _is_quiz_flow(self, context: FlowContext) -> bool:
        """
        Check if context represents a quiz flow.

        Args:
            context: Flow context.

        Returns:
            True if quiz flow, False otherwise.
        """
        quiz_flow_types = ["monthly_quiz", "onboarding", "symptom_tracking"]
        return context.flow_type.value in quiz_flow_types

    def _process_with_ai(
        self,
        flow_instance_id: UUID,
        step_data: FlowStepData,
        context: FlowContext,
    ) -> Optional[Dict[str, Any]]:
        """
        Process step with AI integration.

        Args:
            flow_instance_id: Flow instance ID.
            step_data: Step data.
            context: Flow context.

        Returns:
            AI processing result if successful, None otherwise.
        """
        try:
            # Generate AI response for step
            prompt = step_data.input_data.get("ai_prompt")
            if not prompt:
                return None

            response = self.ai.generate_response(flow_instance_id, prompt, context)
            if response:
                return {"response": response}

            return None

        except Exception as e:
            logger.error(f"Failed to process with AI: {e}", exc_info=True)
            return None

    def _process_with_quiz(
        self,
        flow_instance_id: UUID,
        step_data: FlowStepData,
        context: FlowContext,
    ) -> Optional[Dict[str, Any]]:
        """
        Process step with quiz integration.

        Args:
            flow_instance_id: Flow instance ID.
            step_data: Step data.
            context: Flow context.

        Returns:
            Quiz processing result if successful, None otherwise.
        """
        try:
            # Get quiz flow data
            quiz_flow = self.quiz.get_quiz_flow(flow_instance_id)
            if not quiz_flow:
                return None

            return {
                "quiz_id": str(quiz_flow["quiz_id"]),
                "status": quiz_flow["status"],
            }

        except Exception as e:
            logger.error(f"Failed to process with quiz: {e}", exc_info=True)
            return None


# ============================================================================
# Singleton Instance
# ============================================================================

_integration_manager_instance: Optional[FlowIntegrationManager] = None


def get_integration_manager() -> FlowIntegrationManager:
    """
    Get global integration manager instance.

    Returns:
        Global FlowIntegrationManager instance (singleton).
    """
    global _integration_manager_instance
    if _integration_manager_instance is None:
        _integration_manager_instance = FlowIntegrationManager()
    return _integration_manager_instance


def reset_integration_manager() -> None:
    """
    Reset global integration manager instance.

    Useful for testing.
    """
    global _integration_manager_instance
    _integration_manager_instance = None


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "FlowIntegrationManager",
    "get_integration_manager",
    "reset_integration_manager",
]
