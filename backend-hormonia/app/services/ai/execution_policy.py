"""
Centralized execution policy for AI readiness and simulation fallback decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import settings


@dataclass(frozen=True)
class AIFailureDecision:
    """Decision returned when real AI execution fails."""

    use_simulation: bool
    status_code: int
    detail: str


def is_real_ai_ready(api_key: Optional[str] = None) -> bool:
    """
    Return True when a non-empty Gemini API key is available.

    Accepts an explicit key to support tests that patch module-local settings.
    """
    resolved = api_key if api_key is not None else getattr(settings, "AI_GEMINI_API_KEY", "")
    return isinstance(resolved, str) and bool(resolved.strip())


def decide_ai_failure(
    operation: str,
    *,
    allow_simulation: Optional[bool] = None,
    detail: Optional[str] = None,
) -> AIFailureDecision:
    """
    Decide whether callers should use simulation fallback or return HTTP 502.
    """
    simulation_enabled = (
        bool(getattr(settings, "ALLOW_AI_SIMULATION", True))
        if allow_simulation is None
        else bool(allow_simulation)
    )
    return AIFailureDecision(
        use_simulation=simulation_enabled,
        status_code=502,
        detail=detail or f"{operation} failed and simulation fallback is disabled.",
    )
