"""Domain-specific AI methods for healthcare messaging flows.

Extends the core GeminiClient with methods for humanization, question variation,
sentiment analysis, and empathetic follow-up generation.
"""

import logging
from typing import Any, Dict, List, Optional

from app.ai.client import GeminiClient, GeminiAPIError

logger = logging.getLogger(__name__)


class GeminiDomainClient(GeminiClient):
    """
    Domain-specific extension of GeminiClient for healthcare messaging.

    Provides methods for message humanization, question variation,
    sentiment analysis, and empathetic follow-up generation.
    All methods delegate to LangGraph graphs for structured execution.
    """

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
        from app.ai.langgraph.graphs import get_humanization_graph

        thread_id = (
            (patient_context or {}).get("patient_id")
            or (patient_context or {}).get("id")
            or patient_name
            or "humanize"
        )
        graph = get_humanization_graph()
        state = {
            "template": template,
            "context": {**(patient_context or {}), "patient_name": patient_name},
            "history": conversation_history or [],
            "hints": personalization_hints or [],
            "metadata": {
                "few_shot_examples": few_shot_examples or [],
                "ai_instructions": ai_instructions,
            },
        }
        result = await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": f"humanize:{thread_id}"}},
        )
        output = result.get("output") if isinstance(result, dict) else None
        if not output:
            raise GeminiAPIError("Humanization graph returned empty output")
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
        from app.ai.langgraph.graphs import get_question_variation_graph

        thread_id = (
            (patient_context or {}).get("patient_id")
            or (patient_context or {}).get("id")
            or (patient_context or {}).get("patient_name")
            or "question_variation"
        )
        graph = get_question_variation_graph()
        state = {
            "input_text": base_question,
            "history": previous_questions or [],
            "context": patient_context or {},
            "metadata": {
                "few_shot_examples": few_shot_examples or [],
                "ai_instructions": ai_instructions,
            },
        }
        result = await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": f"question_variation:{thread_id}"}},
        )
        output = result.get("output") if isinstance(result, dict) else None
        if not output:
            raise GeminiAPIError("Question variation graph returned empty output")
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
        from app.ai.langgraph.graphs import get_sentiment_graph

        thread_id = (
            (patient_context or {}).get("patient_id")
            or (patient_context or {}).get("id")
            or (patient_context or {}).get("patient_name")
            or "sentiment"
        )
        graph = get_sentiment_graph()
        state = {"input_text": response, "context": patient_context or {}}
        result = await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": f"sentiment:{thread_id}"}},
        )
        analysis = result.get("output") if isinstance(result, dict) else None
        if not isinstance(analysis, dict):
            raise GeminiAPIError("Sentiment graph returned invalid output")
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
        from app.ai.langgraph.graphs import get_empathetic_follow_up_graph

        thread_id = (
            (patient_context or {}).get("patient_id")
            or (patient_context or {}).get("id")
            or (patient_context or {}).get("patient_name")
            or "follow_up"
        )
        graph = get_empathetic_follow_up_graph()
        state = {
            "input_text": patient_response,
            "history": conversation_history or [],
            "context": patient_context or {},
            "metadata": {"few_shot_examples": few_shot_examples or []},
        }
        result = await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": f"follow_up:{thread_id}"}},
        )
        output = result.get("output") if isinstance(result, dict) else None
        if not output:
            raise GeminiAPIError("Empathetic follow-up graph returned empty output")
        logger.info(
            "Empathetic follow-up generated",
            extra={"operation": "follow_up"},
        )
        return output
