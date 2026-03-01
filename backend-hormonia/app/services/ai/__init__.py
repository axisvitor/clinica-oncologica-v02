"""
AI Services Module (Consolidated)
==================================

This module provides high-level AI services, primarily batch processing
and specialized summary services.

Integrated with LangGraph and GeminiClient (app/ai/).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ai.models import PatientContext, ConcernLevel
from .guardrails import normalize_ai_output, validate_ai_output, OutputKind
from .execution_policy import AIFailureDecision, decide_ai_failure, is_real_ai_ready
from .output_profiles import OutputProfile, list_output_profiles, resolve_output_profile

if TYPE_CHECKING:
    from .batch_processor import (
        BatchProcessor,
        AIOperation,
        BatchResult,
        get_batch_processor,
    )
    from .patient_summary_service import (
        PatientSummaryService,
        get_patient_summary_service,
    )
    from .summary_data_aggregator import (
        SummaryDataAggregator,
        AggregatedPatientData,
    )

__all__ = [
    "PatientContext",
    "ConcernLevel",
    "normalize_ai_output",
    "validate_ai_output",
    "OutputKind",
    "AIFailureDecision",
    "decide_ai_failure",
    "is_real_ai_ready",
    "OutputProfile",
    "resolve_output_profile",
    "list_output_profiles",
    "SentimentType",
    "AIService",
    "HumanizeResult",
    "SentimentResponse",
    "SentimentAnalyzer",
    "ContextBuilder",
    "get_ai_service",
    "get_sentiment_analyzer",
    "get_context_builder",
    "BatchProcessor",
    "AIOperation",
    "BatchResult",
    "get_batch_processor",
    "PatientSummaryService",
    "get_patient_summary_service",
    "SummaryDataAggregator",
    "AggregatedPatientData",
]


def __getattr__(name: str):
    if name in {
        "AIService",
        "ContextBuilder",
        "HumanizeResult",
        "SentimentAnalyzer",
        "SentimentResponse",
        "SentimentType",
        "get_ai_service",
        "get_context_builder",
        "get_sentiment_analyzer",
    }:
        from .ai_service import (
            AIService,
            ContextBuilder,
            HumanizeResult,
            SentimentAnalyzer,
            SentimentResponse,
            SentimentType,
            get_ai_service,
            get_context_builder,
            get_sentiment_analyzer,
        )

        return {
            "AIService": AIService,
            "ContextBuilder": ContextBuilder,
            "HumanizeResult": HumanizeResult,
            "SentimentAnalyzer": SentimentAnalyzer,
            "SentimentResponse": SentimentResponse,
            "SentimentType": SentimentType,
            "get_ai_service": get_ai_service,
            "get_context_builder": get_context_builder,
            "get_sentiment_analyzer": get_sentiment_analyzer,
        }[name]

    """Lazy import heavy modules to avoid circular imports."""
    if name in {"BatchProcessor", "AIOperation", "BatchResult", "get_batch_processor"}:
        from .batch_processor import (
            BatchProcessor,
            AIOperation,
            BatchResult,
            get_batch_processor,
        )

        return {
            "BatchProcessor": BatchProcessor,
            "AIOperation": AIOperation,
            "BatchResult": BatchResult,
            "get_batch_processor": get_batch_processor,
        }[name]

    if name in {"PatientSummaryService", "get_patient_summary_service"}:
        from .patient_summary_service import (
            PatientSummaryService,
            get_patient_summary_service,
        )

        return {
            "PatientSummaryService": PatientSummaryService,
            "get_patient_summary_service": get_patient_summary_service,
        }[name]

    if name in {"SummaryDataAggregator", "AggregatedPatientData"}:
        from .summary_data_aggregator import (
            SummaryDataAggregator,
            AggregatedPatientData,
        )

        return {
            "SummaryDataAggregator": SummaryDataAggregator,
            "AggregatedPatientData": AggregatedPatientData,
        }[name]

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
