"""
AI Service layer for message humanization and sentiment analysis.

Provides a concrete, production-ready interface backed by GeminiClient.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.ai.client import GeminiClient, get_gemini_client
from app.ai.models import PatientContext, ConcernLevel
from app.services.ai.output_profiles import (
    JSON_INSIGHTS,
    JSON_QUALITY,
    JSON_RECOMMENDATIONS,
    JSON_RISK,
)

logger = logging.getLogger(__name__)


class SentimentType(str, Enum):
    """Sentiment classification types."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    CONCERNING = "concerning"


@dataclass
class HumanizeResult:
    """Result of AI humanization."""

    humanized_message: str
    confidence_score: Optional[float] = None
    personalization_notes: List[str] = field(default_factory=list)


@dataclass
class SentimentResponse:
    """Structured sentiment analysis response."""

    sentiment: SentimentType
    confidence: float
    key_phrases: List[str] = field(default_factory=list)
    emotional_indicators: List[str] = field(default_factory=list)
    medical_concerns: List[str] = field(default_factory=list)


class ContextBuilder:
    """Builds patient context payloads for AI processing."""

    async def build_patient_context(
        self,
        patient_id: str,
        patient_data: Dict[str, Any],
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        medical_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "patient_id": patient_id,
            "name": patient_data.get("name"),
            "treatment_type": patient_data.get("treatment_type"),
            "current_day": patient_data.get("current_day"),
            "treatment_start_date": patient_data.get("treatment_start_date"),
            "age": patient_data.get("age"),
            "preferences": patient_data.get("preferences", {}),
            "recent_messages": recent_messages or [],
            "medical_history": medical_data or {},
        }


class AIService:
    """Main AI service wrapper around GeminiClient."""

    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        self.gemini_client = gemini_client or get_gemini_client()

    async def humanize_message(
        self,
        template_message: str,
        patient_context: Optional[PatientContext] = None,
        message_type: str = "general",
        context: Optional[Dict[str, Any]] = None,
    ) -> HumanizeResult:
        ctx = self._normalize_context(patient_context, context)
        patient_name = ctx.get("name") or ctx.get("patient_name") or "Paciente"
        conversation_history = ctx.get("recent_responses") or ctx.get("conversation_history") or []
        personalization_hints = []
        if message_type:
            personalization_hints.append(f"type:{message_type}")
        if ctx.get("preferences"):
            personalization_hints.append("preferences")

        humanized = await self.gemini_client.humanize_flow_message(
            template=template_message,
            patient_name=patient_name,
            patient_context=ctx,
            conversation_history=conversation_history,
            personalization_hints=personalization_hints,
        )

        return HumanizeResult(
            humanized_message=humanized,
            confidence_score=None,
            personalization_notes=personalization_hints,
        )

    async def analyze_sentiment(
        self, message_text: str, patient_context: Dict[str, Any] | PatientContext
    ) -> Tuple[SentimentResponse, ConcernLevel]:
        ctx = self._normalize_context(patient_context)
        analysis = await self.gemini_client.analyze_response_sentiment(
            message_text, ctx
        )

        sentiment_raw = str(analysis.get("sentiment", "neutral")).lower()
        sentiment = (
            SentimentType(sentiment_raw)
            if sentiment_raw in SentimentType._value2member_map_
            else SentimentType.NEUTRAL
        )
        confidence = float(analysis.get("confidence", 0.0))

        response = SentimentResponse(
            sentiment=sentiment,
            confidence=confidence,
            key_phrases=analysis.get("key_themes", []) or [],
            emotional_indicators=analysis.get("emotional_indicators", []) or [],
            medical_concerns=analysis.get("medical_concerns", []) or [],
        )

        concern_level = self._infer_concern_level(analysis, response)
        return response, concern_level

    async def generate_risk_analysis(
        self,
        *,
        patient_id: str,
        patient_name: str,
        treatment_type: Any,
        current_day: Any,
        analysis_days: int,
    ) -> Dict[str, Any]:
        prompt = f"""
Analise o risco de acompanhamento para a paciente abaixo e retorne apenas JSON valido.
patient_id: {patient_id}
name: {patient_name}
treatment_type: {treatment_type or "unknown"}
current_day: {current_day if current_day is not None else "unknown"}
analysis_days: {analysis_days}

Retorne JSON com as chaves:
- risk_level: low|moderate|high|critical
- risk_score: numero entre 0 e 1
- risk_factors: lista de {{factor, impact, confidence}}
- protective_factors: lista de strings
- recommendations: lista de strings
- trend: increasing|decreasing|stable
- confidence: numero entre 0 e 1
"""
        return await self._generate_structured_json(prompt, profile=JSON_RISK)

    async def analyze_message_quality(
        self,
        *,
        message: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt = f"""
Avalie a qualidade da mensagem e retorne apenas JSON valido.
mensagem: {message}
contexto: {context or "none"}

Retorne JSON com as chaves:
- quality_score: numero entre 0 e 100
- readability_score: numero entre 0 e 100
- empathy_score: numero entre 0 e 1
- professionalism_score: numero entre 0 e 1
- clarity_score: numero entre 0 e 1
- suggestions: lista de strings
- strengths: lista de strings
"""
        return await self._generate_structured_json(prompt, profile=JSON_QUALITY)

    async def generate_patient_insights(
        self,
        *,
        patient_id: str,
        patient_name: str,
        treatment_type: Any,
        current_day: Any,
        analysis_type: str,
        days_window: int,
    ) -> Dict[str, Any]:
        prompt = f"""
Gere insights clinicos e de engajamento para acompanhamento oncologico.
patient_id: {patient_id}
patient_name: {patient_name}
treatment_type: {treatment_type or "unknown"}
current_day: {current_day if current_day is not None else "unknown"}
analysis_type: {analysis_type}
days_window: {days_window}

Retorne apenas JSON valido com as chaves:
- overall_status (string)
- risk_level (low|moderate|high|critical)
- adherence_score (0 a 1)
- key_insights (lista de strings)
- alerts (lista de objetos com title, severity e detail)
- engagement_metrics (objeto com metricas numericas)
- sentiment_trends (lista de objetos com metric, direction, change_percentage)
"""
        return await self._generate_structured_json(prompt, profile=JSON_INSIGHTS)

    async def generate_patient_recommendations(
        self,
        *,
        patient_id: str,
    ) -> List[Dict[str, Any]]:
        prompt = f"""
Gere recomendacoes de acompanhamento para a paciente {patient_id}.
Retorne apenas JSON valido com a chave "recommendations".
Cada item deve conter:
- type: clinical|engagement|treatment|monitoring
- priority: low|medium|high
- description: texto curto
- rationale: justificativa objetiva
"""
        parsed = await self._generate_structured_json(prompt, profile=JSON_RECOMMENDATIONS)
        recommendations = parsed.get("recommendations", [])
        if not isinstance(recommendations, list):
            raise ValueError("recommendations must be a list")
        return [item for item in recommendations if isinstance(item, dict)]

    async def _generate_structured_json(self, prompt: str, *, profile: Any) -> Dict[str, Any]:
        raw_response = await self.gemini_client.generate_content(
            prompt,
            profile=profile,
        )
        parsed = json.loads(raw_response)
        if not isinstance(parsed, dict):
            raise ValueError("AI structured response must be a JSON object")
        return parsed

    def _infer_concern_level(
        self, analysis: Dict[str, Any], response: SentimentResponse
    ) -> ConcernLevel:
        requires_attention = bool(analysis.get("requires_attention"))
        if requires_attention:
            if response.confidence >= 0.75:
                return ConcernLevel.HIGH
            if response.sentiment in {SentimentType.NEGATIVE, SentimentType.CONCERNING}:
                return ConcernLevel.MEDIUM
            return ConcernLevel.LOW
        if response.sentiment in {SentimentType.NEGATIVE, SentimentType.CONCERNING}:
            return ConcernLevel.MEDIUM if response.confidence >= 0.5 else ConcernLevel.LOW
        return ConcernLevel.LOW

    def _normalize_context(
        self,
        patient_context: Optional[PatientContext] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if patient_context is not None:
            if isinstance(patient_context, dict):
                return patient_context
            if hasattr(patient_context, "to_dict"):
                return patient_context.to_dict()
        return context or {}


_ai_service: Optional[AIService] = None
_context_builder: Optional[ContextBuilder] = None


def get_ai_service() -> AIService:
    """Singleton accessor for AIService."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


async def get_sentiment_analyzer() -> "SentimentAnalyzer":
    """Async accessor for sentiment analyzer."""
    return SentimentAnalyzer(get_ai_service())


def get_context_builder() -> ContextBuilder:
    """Singleton accessor for ContextBuilder."""
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder()
    return _context_builder


class SentimentAnalyzer:
    """Sentiment analysis façade used by response processing."""

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    async def analyze_sentiment(
        self, message_text: str, patient_context: Dict[str, Any]
    ) -> Tuple[SentimentResponse, ConcernLevel]:
        return await self.ai_service.analyze_sentiment(message_text, patient_context)
