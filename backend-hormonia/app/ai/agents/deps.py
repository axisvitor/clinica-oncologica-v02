from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AIDeps:
    """Dependency container for pydantic-ai agents.

    Carries Gemini API key and model name into every agent invocation
    via pydantic-ai's dependency injection pattern.
    """

    gemini_api_key: str
    model_name: str = "gemini-2.0-flash"
