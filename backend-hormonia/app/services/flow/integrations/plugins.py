"""
Default plugin implementations that wrap the existing integration services.
"""

from __future__ import annotations

from typing import Dict, Any

from ..types import FlowContext, FlowStepData, FlowStepType
from .base import FlowIntegration
from .quiz_integration import QuizFlowIntegration
from .ai_integration import AIFlowIntegration


class QuizIntegrationPlugin(FlowIntegration):
    name = "quiz"

    def __init__(self, integration: QuizFlowIntegration):
        self.integration = integration

    async def on_flow_start(
        self,
        context: FlowContext,
        template: Dict[str, Any],
    ) -> None:
        quiz_metadata = template.get("metadata", {}).get("quiz")
        if not quiz_metadata:
            return

        quiz_type = quiz_metadata.get("type", "default")
        quiz_data = quiz_metadata.get("data")
        self.integration.create_quiz_flow(context.patient_id, quiz_type, quiz_data)

    async def on_flow_complete(
        self,
        context: FlowContext,
        template: Dict[str, Any],
    ) -> None:
        quiz_flow_id = context.metadata.get("quiz_flow_id")
        if quiz_flow_id:
            self.integration.complete_quiz_flow(quiz_flow_id, context.flow_data)


class AIIntegrationPlugin(FlowIntegration):
    name = "ai"

    def __init__(self, integration: AIFlowIntegration):
        self.integration = integration

    async def on_step_complete(
        self,
        context: FlowContext,
        template: Dict[str, Any],
        step_data: FlowStepData,
    ) -> None:
        if step_data.step_type == FlowStepType.QUESTION and step_data.output_data:
            prompt = step_data.output_data.get("question_asked")
            response = step_data.output_data.get("response")
            if prompt and response:
                self.integration.analyze_response(
                    context.flow_instance_id,
                    prompt,
                    response,
                )


__all__ = ["QuizIntegrationPlugin", "AIIntegrationPlugin"]
