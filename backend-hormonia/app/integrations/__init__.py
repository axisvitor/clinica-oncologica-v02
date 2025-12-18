"""
Integration modules for external services.

This package contains clients and utilities for integrating with external services:
- Evolution API for WhatsApp Business communication
- OpenAI/LangChain for AI-powered message personalization and sentiment analysis
- PDF generation utilities for medical reports
"""

from .evolution import (
    EvolutionClient,
    EvolutionAPIError,
    WebhookEvent,
    MessageType,
    MessageStatus,
    get_evolution_client,
    close_evolution_client,
)

# Optional OpenAI/LangChain integration. These imports may fail when the
# heavy AI dependencies are not installed (e.g. during unit tests). In that
# case we provide lightweight fallbacks so that the rest of the application
# can be imported without error.
try:  # pragma: no cover - exercised in environments with AI dependencies
    from .openai_client import (
        LangChainOrchestrator,
        PromptManager,
        SentimentType,
        MessagePersonalizationRequest,
        SentimentAnalysisRequest,
        PersonalizationResponse,
        SentimentAnalysisResponse,
        OpenAIClientError,
        get_langchain_orchestrator,
        get_prompt_manager,
    )
except Exception:  # pragma: no cover - we simply expose stubs

    class OpenAIClientError(Exception):
        """Fallback error when AI features are unavailable."""

    LangChainOrchestrator = PromptManager = None  # type: ignore
    SentimentType = MessagePersonalizationRequest = None  # type: ignore
    SentimentAnalysisRequest = PersonalizationResponse = None  # type: ignore
    SentimentAnalysisResponse = None  # type: ignore

    def get_langchain_orchestrator(*args, **kwargs):
        raise OpenAIClientError("LangChain integration is not available")

    def get_prompt_manager(*args, **kwargs):
        raise OpenAIClientError("LangChain integration is not available")


from .pdf_generator import (
    MedicalReportGenerator,
    ReportSection,
    PatientReportData,
    PDFGeneratorError,
    get_pdf_generator,
)

__all__ = [
    # Evolution API
    "EvolutionClient",
    "EvolutionAPIError",
    "WebhookEvent",
    "MessageType",
    "MessageStatus",
    "get_evolution_client",
    "close_evolution_client",
    # OpenAI/LangChain
    "LangChainOrchestrator",
    "PromptManager",
    "SentimentType",
    "MessagePersonalizationRequest",
    "SentimentAnalysisRequest",
    "PersonalizationResponse",
    "SentimentAnalysisResponse",
    "OpenAIClientError",
    "get_langchain_orchestrator",
    "get_prompt_manager",
    # PDF Generation
    "MedicalReportGenerator",
    "ReportSection",
    "PatientReportData",
    "PDFGeneratorError",
    "get_pdf_generator",
]
