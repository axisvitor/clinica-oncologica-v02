"""
Integration modules for external services.

This package contains clients and utilities for integrating with external services:
- Evolution API for WhatsApp Business communication
- Gemini/LangChain for AI-powered message personalization and sentiment analysis
- PDF generation utilities for medical reports
"""

from .evolution import (
    EvolutionClient,
    EvolutionAPIError,
    WebhookEvent,
    MessageType,
    get_evolution_client,
    close_evolution_client,
)

from .gemini_orchestrator import (
    LangChainOrchestrator,
    SentimentType,
    MessagePersonalizationRequest,
    SentimentAnalysisRequest,
    PersonalizationResponse,
    SentimentAnalysisResponse,
    GeminiClientError,
    get_langchain_orchestrator,
)



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
    "get_evolution_client",
    "close_evolution_client",
    # Gemini/LangChain
    "LangChainOrchestrator",
    "SentimentType",
    "MessagePersonalizationRequest",
    "SentimentAnalysisRequest",
    "PersonalizationResponse",
    "SentimentAnalysisResponse",
    "GeminiClientError",
    "get_langchain_orchestrator",
    # PDF Generation
    "MedicalReportGenerator",
    "ReportSection",
    "PatientReportData",
    "PDFGeneratorError",
    "get_pdf_generator",
]
