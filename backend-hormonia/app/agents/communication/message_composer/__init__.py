# DDD service agent - no LLM calls, not a pydantic-ai migration target.
"""
Message Composer Agent Package

Specialized agent responsible for intelligent message composition and personalization.
Uses AI to create contextually appropriate, empathetic messages adapted to patient state.
"""

from app.agents.communication.message_composer.agent import MessageComposerAgent

__all__ = ["MessageComposerAgent"]
