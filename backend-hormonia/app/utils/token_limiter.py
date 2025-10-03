"""
Token Limiter Utility for AI Context Management
Ensures predictable token usage and cost control
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class TokenLimiter:
    """
    Utility to limit tokens in AI context for cost and latency control.
    Uses approximation: 1 token ≈ 4 characters (conservative estimate)
    """

    # Conservative token estimation
    CHARS_PER_TOKEN = 4

    # Default limits
    DEFAULT_MAX_TOKENS = 500
    CONTEXT_MAX_TOKENS = 300  # For patient context
    MESSAGE_MAX_TOKENS = 100  # For individual messages

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count from text.
        Conservative: 1 token ≈ 4 characters
        """
        if not text:
            return 0
        return len(text) // TokenLimiter.CHARS_PER_TOKEN

    @staticmethod
    def truncate_to_tokens(text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed

        Returns:
            Truncated text
        """
        if not text:
            return text

        max_chars = max_tokens * TokenLimiter.CHARS_PER_TOKEN

        if len(text) <= max_chars:
            return text

        # Truncate and add ellipsis
        truncated = text[:max_chars - 3] + "..."
        logger.debug(f"Truncated text from {len(text)} to {len(truncated)} chars (~{max_tokens} tokens)")
        return truncated

    @staticmethod
    def limit_messages_history(
        messages: List[Dict[str, Any]],
        max_tokens: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Limit message history to fit within token budget.
        Prioritizes recent messages.

        Args:
            messages: List of message dictionaries
            max_tokens: Token budget for messages

        Returns:
            Limited list of messages
        """
        if not messages:
            return []

        limited_messages = []
        token_count = 0

        # Process messages in reverse (most recent first)
        for msg in reversed(messages):
            msg_text = msg.get('content', '') or msg.get('message', '')
            msg_tokens = TokenLimiter.estimate_tokens(msg_text)

            if token_count + msg_tokens > max_tokens:
                # If adding this message exceeds limit, truncate it
                remaining_tokens = max_tokens - token_count
                if remaining_tokens > 20:  # Only add if meaningful content
                    truncated_msg = msg.copy()
                    truncated_msg['content'] = TokenLimiter.truncate_to_tokens(
                        msg_text, remaining_tokens
                    )
                    limited_messages.insert(0, truncated_msg)
                break

            limited_messages.insert(0, msg)
            token_count += msg_tokens

        logger.info(f"Limited {len(messages)} messages to {len(limited_messages)} (≈{token_count} tokens)")
        return limited_messages

    @staticmethod
    def limit_patient_context(
        context: Dict[str, Any],
        max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> Dict[str, Any]:
        """
        Limit entire patient context to fit within token budget.

        Args:
            context: Patient context dictionary
            max_tokens: Total token budget (default 500)

        Returns:
            Limited context dictionary
        """
        limited_context = context.copy()

        # Allocate token budget
        metadata_tokens = 100  # For patient data, dates, etc.
        messages_tokens = 200  # For message history
        quiz_tokens = 100      # For quiz responses
        flow_tokens = 100      # For flow data

        # Limit each section
        if 'recent_messages' in limited_context:
            limited_context['recent_messages'] = TokenLimiter.limit_messages_history(
                limited_context['recent_messages'],
                max_tokens=messages_tokens
            )

        if 'quiz_responses' in limited_context:
            # Limit quiz responses to recent ones
            quiz_data = limited_context['quiz_responses']
            if isinstance(quiz_data, dict):
                # Keep only last 5 responses
                sorted_keys = sorted(quiz_data.keys())[-5:]
                limited_context['quiz_responses'] = {
                    k: quiz_data[k] for k in sorted_keys
                }

        if 'flow_data' in limited_context and isinstance(limited_context['flow_data'], dict):
            # Limit flow data keys
            flow_data = limited_context['flow_data']
            if len(str(flow_data)) > flow_tokens * TokenLimiter.CHARS_PER_TOKEN:
                # Keep only essential keys
                essential_keys = ['current_step', 'last_response', 'completion_percentage']
                limited_context['flow_data'] = {
                    k: v for k, v in flow_data.items()
                    if k in essential_keys
                }

        # Estimate total tokens
        total_text = str(limited_context)
        total_tokens = TokenLimiter.estimate_tokens(total_text)

        if total_tokens > max_tokens:
            logger.warning(f"Context still exceeds limit: {total_tokens} > {max_tokens} tokens")
            # Further truncation if needed
            if 'recent_messages' in limited_context:
                # Reduce message history further
                limited_context['recent_messages'] = limited_context['recent_messages'][-3:]

        logger.info(f"Limited context to approximately {total_tokens} tokens")
        return limited_context

    @staticmethod
    def prepare_ai_prompt(
        base_prompt: str,
        context: Dict[str, Any],
        max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str:
        """
        Prepare AI prompt with limited context.

        Args:
            base_prompt: Base prompt template
            context: Context to include
            max_tokens: Total token budget

        Returns:
            Complete prompt within token limit
        """
        # Reserve tokens for base prompt
        base_tokens = TokenLimiter.estimate_tokens(base_prompt)
        context_budget = max_tokens - base_tokens - 50  # Reserve buffer

        if context_budget < 100:
            logger.warning("Insufficient token budget for context")
            return base_prompt

        # Limit context
        limited_context = TokenLimiter.limit_patient_context(
            context,
            max_tokens=context_budget
        )

        # Format prompt with limited context
        prompt = base_prompt.format(**limited_context)

        # Final check
        final_tokens = TokenLimiter.estimate_tokens(prompt)
        if final_tokens > max_tokens:
            # Emergency truncation
            prompt = TokenLimiter.truncate_to_tokens(prompt, max_tokens)

        logger.debug(f"Prepared prompt with ~{final_tokens} tokens")
        return prompt


# Singleton instance
_token_limiter = TokenLimiter()

def get_token_limiter() -> TokenLimiter:
    """Get token limiter instance."""
    return _token_limiter