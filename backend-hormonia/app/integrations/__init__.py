"""Integration package exports.

Keep package import side effects minimal so deep imports can load focused
submodules without bootstrapping unrelated integrations or runtime settings.
"""

from __future__ import annotations

from importlib import import_module

_EXPORTS: dict[str, tuple[str, str]] = {
    # Gemini/LangChain
    "LangChainOrchestrator": (
        "app.integrations.gemini_orchestrator",
        "LangChainOrchestrator",
    ),
    "SentimentType": ("app.integrations.gemini_orchestrator", "SentimentType"),
    "MessagePersonalizationRequest": (
        "app.integrations.gemini_orchestrator",
        "MessagePersonalizationRequest",
    ),
    "SentimentAnalysisRequest": (
        "app.integrations.gemini_orchestrator",
        "SentimentAnalysisRequest",
    ),
    "PersonalizationResponse": (
        "app.integrations.gemini_orchestrator",
        "PersonalizationResponse",
    ),
    "SentimentAnalysisResponse": (
        "app.integrations.gemini_orchestrator",
        "SentimentAnalysisResponse",
    ),
    "GeminiClientError": (
        "app.integrations.gemini_orchestrator",
        "GeminiClientError",
    ),
    "get_langchain_orchestrator": (
        "app.integrations.gemini_orchestrator",
        "get_langchain_orchestrator",
    ),
    # PDF Generation
    "MedicalReportGenerator": (
        "app.integrations.pdf_generator",
        "MedicalReportGenerator",
    ),
    "ReportSection": ("app.integrations.pdf_generator", "ReportSection"),
    "PatientReportData": (
        "app.integrations.pdf_generator",
        "PatientReportData",
    ),
    "PDFGeneratorError": ("app.integrations.pdf_generator", "PDFGeneratorError"),
    "get_pdf_generator": ("app.integrations.pdf_generator", "get_pdf_generator"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value
