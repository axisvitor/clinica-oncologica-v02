"""Build quiz link URLs."""

from __future__ import annotations

from app.core.monthly_quiz_config import get_monthly_quiz_config

import logging

logger = logging.getLogger(__name__)


class LinkBuilder:
    """Constructs quiz link URLs with tokens."""

    def __init__(self):
        self.config = get_monthly_quiz_config()

        # Warn if using localhost in production-like environment
        if (
            "localhost" in self.config.MONTHLY_QUIZ_BASE_URL
            and self.config.ENVIRONMENT != "development"
        ):
            logger.warning(
                f"MONTHLY_QUIZ_BASE_URL is set to localhost ({self.config.MONTHLY_QUIZ_BASE_URL}) "
                "in non-development environment. Quiz links will be invalid for external users."
            )

    def build_link(self, token: str) -> str:
        """Build full quiz link URL with token.

        Args:
            token: JWT token for quiz access

        Returns:
            Complete quiz link URL
        """
        return f"{self.config.MONTHLY_QUIZ_BASE_URL}?token={token}"

    def build_redacted_link(self) -> str:
        """Build redacted link URL for display purposes.

        Returns:
            Link URL with [REDACTED] token placeholder
        """
        return f"{self.config.MONTHLY_QUIZ_BASE_URL}?token=[REDACTED]"
