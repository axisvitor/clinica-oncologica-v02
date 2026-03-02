"""
Integration modules for external services.

This package contains clients and utilities for integrating with external services:
- WuzAPI for WhatsApp Business communication
- Gemini/LangChain for AI-powered message personalization and sentiment analysis
- PDF generation utilities for medical reports
"""

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
