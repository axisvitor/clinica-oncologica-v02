"""
Deprecated shim for legacy imports.
Use app.integrations.gemini_orchestrator instead.
"""

from app.integrations.gemini_orchestrator import (
    LangChainOrchestrator,
    PromptManager,
    SentimentType,
    MessagePersonalizationRequest,
    SentimentAnalysisRequest,
    PersonalizationResponse,
    SentimentAnalysisResponse,
    GeminiClientError,
    get_langchain_orchestrator,
    get_prompt_manager,
    get_gemini_orchestrator,
)


class OpenAIClientError(GeminiClientError):
    """Backward-compatible alias for Gemini-only orchestration errors."""


def get_openai_client() -> LangChainOrchestrator:  # pragma: no cover
    """Alias for backward compatibility."""
    return get_langchain_orchestrator()


__all__ = [
    "LangChainOrchestrator",
    "PromptManager",
    "SentimentType",
    "MessagePersonalizationRequest",
    "SentimentAnalysisRequest",
    "PersonalizationResponse",
    "SentimentAnalysisResponse",
    "GeminiClientError",
    "OpenAIClientError",
    "get_langchain_orchestrator",
    "get_prompt_manager",
    "get_gemini_orchestrator",
    "get_openai_client",
]
