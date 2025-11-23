"""
Communication-focused agents for the Hive-Mind system.

These agents handle patient interactions, messaging, quiz conduction,
and response processing with intelligent personalization.
"""

from .message_composer import MessageComposerAgent
from .response_processor import ResponseProcessorAgent, ResponseAnalysis

__all__ = [
    "MessageComposerAgent",
    "ResponseProcessorAgent",
    "ResponseAnalysis"
]