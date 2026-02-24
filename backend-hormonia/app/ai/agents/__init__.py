from __future__ import annotations

"""Pydantic-AI agents for healthcare messaging flows.

All agents inherit from PIISafeAgent to enforce mandatory LGPD PII redaction.
Direct agent.run() calls outside PIISafeAgent are prohibited.
"""

__all__ = ["AIDeps", "PIISafeAgent"]


def __getattr__(name: str):
    if name == "AIDeps":
        from app.ai.agents.deps import AIDeps

        return AIDeps
    if name == "PIISafeAgent":
        from app.ai.agents.base import PIISafeAgent

        return PIISafeAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
