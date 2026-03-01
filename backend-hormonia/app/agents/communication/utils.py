# DDD service agent - no LLM calls, not a pydantic-ai migration target.
"""Shared utilities for communication agents."""


def clean_message_content(content: str) -> str:
    """Clean and normalize message content from AI output.

    Strips whitespace, removes surrounding quotes, and normalizes spacing.
    """
    if not content:
        return content
    content = content.strip()
    if (content.startswith('"') and content.endswith('"')) or \
       (content.startswith("'") and content.endswith("'")):
        content = content[1:-1].strip()
    return content
