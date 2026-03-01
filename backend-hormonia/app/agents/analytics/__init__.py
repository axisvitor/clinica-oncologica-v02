# DDD service agent - no LLM calls, not a pydantic-ai migration target.
"""Analytics agents for alert analysis and monitoring."""

from app.agents.analytics.alert_analyzer import AlertAnalyzerAgent

__all__ = ["AlertAnalyzerAgent"]
