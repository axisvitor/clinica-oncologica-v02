"""Domain-specific AI methods for healthcare messaging flows.

Extends the core GeminiClient with methods for humanization, question variation,
sentiment analysis, and empathetic follow-up generation.
"""

import logging
from typing import Any, Dict, List, Optional

from app.ai.agents.deps import AIDeps
from app.ai.agents.empathy_agent import EmpathyAgent
from app.ai.agents.humanize_agent import HumanizeAgent
from app.ai.agents.sentiment_agent import SentimentAgent
from app.ai.agents.variation_agent import VariationAgent
from app.ai.context_compactor import compact_patient_context
from app.ai.client import GeminiClient

logger = logging.getLogger(__name__)


class GeminiDomainClient(GeminiClient):
    """
    Domain-specific extension of GeminiClient for healthcare messaging.

    Provides methods for message humanization, question variation,
    sentiment analysis, and empathetic follow-up generation.
    All methods delegate to pydantic-ai agents.
    """

    def _build_ai_deps(self) -> AIDeps:
        api_key: str = self.api_key if isinstance(self.api_key, str) else ""
        model_name: str = (
            self.model_name if isinstance(self.model_name, str) else "gemini-3-flash-preview"
        )
        return AIDeps(gemini_api_key=api_key, model_name=model_name)

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
        deps = self._build_ai_deps()
        return await HumanizeAgent().humanize(
            template=template,
            patient_name=patient_name,
            patient_context=patient_context,
            conversation_history=conversation_history,
            personalization_hints=personalization_hints,
            ai_instructions=ai_instructions,
            deps=deps,
        )

    def humanize_flow_message_sync(
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
        del few_shot_examples, strict
        deps = self._build_ai_deps()
        return HumanizeAgent().humanize_sync(
            template=template,
            patient_name=patient_name,
            patient_context=patient_context,
            conversation_history=conversation_history,
            personalization_hints=personalization_hints,
            ai_instructions=ai_instructions,
            deps=deps,
        )

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
        deps = self._build_ai_deps()
        return await VariationAgent().vary(
            base_question=base_question,
            previous_questions=previous_questions,
            patient_context=patient_context,
            ai_instructions=ai_instructions,
            deps=deps,
        )

    def generate_varied_question_sync(
        self,
        base_question: str,
        previous_questions: List[str],
        patient_context: Dict[str, Any],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        ai_instructions: Optional[str] = None,
        strict: bool = False,
    ) -> str:
        del few_shot_examples, strict
        deps = self._build_ai_deps()
        return VariationAgent().vary_sync(
            base_question=base_question,
            previous_questions=previous_questions,
            patient_context=patient_context,
            ai_instructions=ai_instructions,
            deps=deps,
        )

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
        deps = self._build_ai_deps()
        context_snapshot = compact_patient_context(patient_context or {})
        result = await SentimentAgent().analyze(
            response=response,
            context_snapshot=context_snapshot,
            deps=deps,
        )
        return result.model_dump()

    def analyze_response_sentiment_sync(
        self, response: str, patient_context: Dict[str, Any], strict: bool = False
    ) -> Dict[str, Any]:
        del strict
        deps = self._build_ai_deps()
        context_snapshot = compact_patient_context(patient_context or {})
        result = SentimentAgent().analyze_sync(
            response=response,
            context_snapshot=context_snapshot,
            deps=deps,
        )
        return result.model_dump()

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
        deps = self._build_ai_deps()
        return await EmpathyAgent().follow_up(
            patient_response=patient_response,
            conversation_history=conversation_history or [],
            patient_context=patient_context,
            few_shot_examples=few_shot_examples,
            deps=deps,
        )

    def create_empathetic_follow_up_sync(
        self,
        patient_response: str,
        conversation_history: List[str],
        patient_context: Dict[str, Any],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        strict: bool = False,
    ) -> str:
        del strict
        deps = self._build_ai_deps()
        return EmpathyAgent().follow_up_sync(
            patient_response=patient_response,
            conversation_history=conversation_history or [],
            patient_context=patient_context,
            few_shot_examples=few_shot_examples,
            deps=deps,
        )
