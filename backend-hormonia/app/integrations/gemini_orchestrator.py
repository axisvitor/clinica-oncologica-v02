"""
Gemini/LangChain orchestrator for AI-powered messaging.

Provides high-level AI utilities used by webhook handlers and response processing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from app.ai.client import GeminiClient, get_gemini_client
from app.services.ai.guardrails import OutputKind

logger = logging.getLogger(__name__)


class GeminiClientError(RuntimeError):
    """Raised when Gemini orchestration fails."""


class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    CONCERNING = "concerning"


@dataclass
class MessagePersonalizationRequest:
    template_message: str
    patient_context: Dict[str, Any]
    message_type: str = "general"


@dataclass
class SentimentAnalysisRequest:
    message_text: str
    patient_context: Dict[str, Any]


@dataclass
class PersonalizationResponse:
    personalized_message: str
    confidence_score: Optional[float] = None


@dataclass
class SentimentAnalysisResponse:
    sentiment: SentimentType
    confidence: float
    key_phrases: List[str]
    emotional_indicators: List[str]
    medical_concerns: List[str]


class LangChainOrchestrator:
    """High-level AI orchestrator backed by GeminiClient."""

    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        self.gemini_client = gemini_client or get_gemini_client()

    async def generate_contextual_response(
        self,
        patient_message: str,
        patient_context: Dict[str, Any],
        conversation_history: List[str],
    ) -> str:
        prompt = (
            "Você é um assistente empático para pacientes em tratamento.\n\n"
            f"Contexto do paciente: {patient_context}\n"
            f"Histórico recente: {conversation_history}\n"
            f"Mensagem do paciente: \"{patient_message}\"\n\n"
            "Responda com empatia, clareza e objetividade. "
            "Evite termos técnicos desnecessários."
        )
        return await self.gemini_client.generate_content(
            prompt,
            output_kind=OutputKind.MESSAGE,
            require_ending_punctuation=True,
        )

    async def personalize_message(
        self, request: MessagePersonalizationRequest
    ) -> PersonalizationResponse:
        patient_name = request.patient_context.get("name", "Paciente")
        humanized = await self.gemini_client.humanize_flow_message(
            template=request.template_message,
            patient_name=patient_name,
            patient_context=request.patient_context,
            conversation_history=request.patient_context.get("recent_messages", []),
            personalization_hints=[f"type:{request.message_type}"],
        )
        return PersonalizationResponse(personalized_message=humanized)

    async def analyze_sentiment(
        self, request: SentimentAnalysisRequest
    ) -> SentimentAnalysisResponse:
        analysis = await self.gemini_client.analyze_response_sentiment(
            response=request.message_text,
            patient_context=request.patient_context,
        )
        sentiment_raw = str(analysis.get("sentiment", "neutral")).lower()
        sentiment = (
            SentimentType(sentiment_raw)
            if sentiment_raw in SentimentType._value2member_map_
            else SentimentType.NEUTRAL
        )
        return SentimentAnalysisResponse(
            sentiment=sentiment,
            confidence=float(analysis.get("confidence", 0.0)),
            key_phrases=analysis.get("key_themes", []) or [],
            emotional_indicators=analysis.get("emotional_indicators", []) or [],
            medical_concerns=analysis.get("medical_concerns", []) or [],
        )

    async def generate_content(self, prompt: str, **kwargs) -> str:
        """Compatibility wrapper for ConcernDetector."""
        return await self.gemini_client.generate_content(prompt, **kwargs)


_orchestrator: Optional[LangChainOrchestrator] = None


def get_langchain_orchestrator() -> LangChainOrchestrator:
    """Singleton accessor for LangChainOrchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = LangChainOrchestrator()
    return _orchestrator
