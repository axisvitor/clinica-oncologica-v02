"""Domain-specific AI methods for healthcare messaging flows.

Extends the core GeminiClient with methods for humanization, question variation,
sentiment analysis, and empathetic follow-up generation.

Phase 8 (AI-03): All methods now call generate_content() directly instead of
going through single-node LangGraph StateGraph wrappers.
"""

import logging
from typing import Any, Dict, List, Optional

from app.ai.client import GeminiClient, GeminiAPIError
from app.core.exceptions import FeatureNotAvailableError
from app.services.ai.output_profiles import JSON_SENTIMENT, MESSAGE_HUMANIZED, MESSAGE_STANDARD

logger = logging.getLogger(__name__)


class GeminiDomainClient(GeminiClient):
    """
    Domain-specific extension of GeminiClient for healthcare messaging.

    Provides methods for message humanization, question variation,
    sentiment analysis, and empathetic follow-up generation.
    All methods call generate_content() directly — no LangGraph intermediary.
    """

    def _use_pydantic_agents(self) -> bool:
        """Check if pydantic-ai agents should be used instead of direct generate_content."""
        from app.config import settings

        ai_framework = getattr(settings, "AI_FRAMEWORK", "legacy")
        if ai_framework != "pydantic-ai":
            logger.info(
                "AI_FRAMEWORK=%s -- using GeminiClient.generate_content() path",
                ai_framework,
            )
            return False
        return True

    async def humanize_flow_message(
        self,
        template: str,
        patient_name: str,
        patient_context: Dict[str, Any],
        conversation_history: List[str],
        personalization_hints: List[str],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        ai_instructions: Optional[str] = None,
        strict: bool = False,
    ) -> str:
        """
        Transform template message into natural, human-like conversation.

        Args:
            template: Base message template
            patient_name: Patient's name for personalization
            patient_context: Patient context and preferences
            conversation_history: Recent conversation messages
            personalization_hints: Hints for personalization approach
            few_shot_examples: Optional list of example inputs and outputs for few-shot prompting.
            ai_instructions: Optional AI-specific instructions for the template.
            strict: Whether to enforce strict output validation.

        Returns:
            Humanized message text
        """
        if self._use_pydantic_agents():
            from app.ai.agents.deps import AIDeps
            from app.ai.agents.humanize_agent import HumanizeAgent

            deps = AIDeps(gemini_api_key=self.api_key, model_name=self.model_name)
            return await HumanizeAgent().humanize(
                template=template,
                patient_name=patient_name,
                patient_context=patient_context,
                conversation_history=conversation_history,
                personalization_hints=personalization_hints,
                ai_instructions=ai_instructions,
                deps=deps,
            )

        from app.ai.langgraph.nodes_ai import _coerce_recent_interactions, _replace_patient_name
        from app.ai.langgraph.prompts import build_humanization_prompt

        context = {**(patient_context or {}), "patient_name": patient_name}
        recent_interactions = _coerce_recent_interactions(
            context.get("recent_interactions"),
            fallback_history=conversation_history or [],
        )
        template_with_name = _replace_patient_name(template, patient_name)
        prompt = build_humanization_prompt(
            template=template_with_name,
            ai_instructions=ai_instructions,
            recent_interactions=recent_interactions,
        )
        output = await self.generate_content(prompt, profile=MESSAGE_HUMANIZED)
        if not output:
            raise FeatureNotAvailableError(
                "humanization returned no output",
                "humanization",
                "humanize_flow_message",
            )
        logger.info(
            "Message humanized successfully",
            extra={
                "operation": "humanize",
                "patient": patient_name,
                "template_length": len(template),
            },
        )
        return output

    async def generate_varied_question(
        self,
        base_question: str,
        previous_questions: List[str],
        patient_context: Dict[str, Any],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        ai_instructions: Optional[str] = None,
        strict: bool = False,
    ) -> str:
        """
        Generate question variation to avoid repetition.

        Args:
            base_question: Original question template
            previous_questions: Recently asked questions
            patient_context: Patient context for personalization
            few_shot_examples: Optional list of example inputs and outputs for few-shot prompting.
            ai_instructions: Optional AI-specific instructions for the template.
            strict: Whether to enforce strict output validation.

        Returns:
            Varied question text
        """
        if self._use_pydantic_agents():
            from app.ai.agents.deps import AIDeps
            from app.ai.agents.variation_agent import VariationAgent

            deps = AIDeps(gemini_api_key=self.api_key, model_name=self.model_name)
            return await VariationAgent().vary(
                base_question=base_question,
                previous_questions=previous_questions,
                patient_context=patient_context,
                ai_instructions=ai_instructions,
                deps=deps,
            )

        from app.ai.langgraph.nodes_ai import (
            _coerce_recent_interactions,
            _extract_recent_questions,
            _is_too_similar_to_recent,
            _build_non_repetitive_question,
            _replace_patient_name,
        )
        from app.ai.langgraph.prompts import build_question_variation_prompt

        context = patient_context or {}
        patient_name = context.get("patient_name") or context.get("name") or ""
        recent_interactions = _coerce_recent_interactions(
            context.get("recent_interactions"),
            fallback_history=previous_questions or [],
        )
        recent_questions = _extract_recent_questions(
            recent_interactions,
            previous_questions or [],
        )
        question_with_name = _replace_patient_name(base_question, patient_name)
        prompt = build_question_variation_prompt(
            base_question=question_with_name,
            ai_instructions=ai_instructions,
            recent_interactions=recent_interactions,
        )
        output = await self.generate_content(prompt, profile=MESSAGE_STANDARD)
        if _is_too_similar_to_recent(output, recent_questions):
            output = _build_non_repetitive_question(base_question, recent_questions)
        logger.info(
            "Question variation generated",
            extra={"operation": "question_variation"},
        )
        return output

    async def analyze_response_sentiment(
        self, response: str, patient_context: Dict[str, Any], strict: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze patient response sentiment and extract insights.

        Args:
            response: Patient's response text
            patient_context: Patient context for analysis
            strict: Whether to enforce strict output validation.

        Returns:
            Sentiment analysis results
        """
        if self._use_pydantic_agents():
            from app.ai.agents.deps import AIDeps
            from app.ai.agents.sentiment_agent import SentimentAgent
            from app.ai.context_compactor import compact_patient_context

            deps = AIDeps(gemini_api_key=self.api_key, model_name=self.model_name)
            context_snapshot = compact_patient_context(patient_context or {})
            result = await SentimentAgent().analyze(
                response=response,
                context_snapshot=context_snapshot,
                deps=deps,
            )
            return result.model_dump()

        from app.ai.langgraph.nodes_ai import _parse_sentiment_analysis
        from app.ai.langgraph.prompts import build_sentiment_prompt
        from app.ai.context_compactor import compact_patient_context

        context_snapshot = compact_patient_context(patient_context or {})
        prompt = build_sentiment_prompt(
            response=response,
            context_snapshot=context_snapshot,
        )
        analysis_text = await self.generate_content(prompt, profile=JSON_SENTIMENT)
        if not analysis_text:
            raise FeatureNotAvailableError(
                "sentiment analysis returned no output",
                "sentiment",
                "analyze_response_sentiment",
            )
        analysis = _parse_sentiment_analysis(analysis_text)
        logger.info(
            "Sentiment analysis completed",
            extra={"operation": "sentiment"},
        )
        return analysis

    async def create_empathetic_follow_up(
        self,
        patient_response: str,
        conversation_history: List[str],
        patient_context: Dict[str, Any],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        strict: bool = False,
    ) -> str:
        """
        Create empathetic follow-up message based on patient response.

        Args:
            patient_response: Patient's latest response
            conversation_history: Recent conversation messages
            patient_context: Patient context and preferences
            few_shot_examples: Optional list of example inputs and outputs for few-shot prompting.
            strict: Whether to enforce strict output validation.

        Returns:
            Empathetic follow-up message
        """
        if self._use_pydantic_agents():
            from app.ai.agents.deps import AIDeps
            from app.ai.agents.empathy_agent import EmpathyAgent

            deps = AIDeps(gemini_api_key=self.api_key, model_name=self.model_name)
            return await EmpathyAgent().follow_up(
                patient_response=patient_response,
                conversation_history=conversation_history,
                patient_context=patient_context,
                few_shot_examples=few_shot_examples,
                deps=deps,
            )

        from app.ai.langgraph.prompts import build_empathetic_prompt
        from app.ai.context_compactor import compact_patient_context

        context_snapshot = compact_patient_context(patient_context or {})
        prompt = build_empathetic_prompt(
            patient_response=patient_response,
            conversation_history=conversation_history or [],
            context_snapshot=context_snapshot,
            examples=few_shot_examples or [],
            allow_questions=False,
            day_complete=False,
        )
        output = await self.generate_content(prompt, profile=MESSAGE_HUMANIZED)
        if not output:
            raise FeatureNotAvailableError(
                "empathetic follow-up returned no output",
                "empathetic_follow_up",
                "create_empathetic_follow_up",
            )
        logger.info(
            "Empathetic follow-up generated",
            extra={"operation": "follow_up"},
        )
        return output
