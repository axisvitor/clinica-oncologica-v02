"""Build quiz link URLs."""

from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
        if (
            self.config.MONTHLY_QUIZ_SHORT_BASE_URL
            and "localhost" in self.config.MONTHLY_QUIZ_SHORT_BASE_URL
            and self.config.ENVIRONMENT != "development"
        ):
            logger.warning(
                f"MONTHLY_QUIZ_SHORT_BASE_URL is set to localhost ({self.config.MONTHLY_QUIZ_SHORT_BASE_URL}) "
                "in non-development environment. Short links will be invalid for external users."
            )

    def build_link(self, token: str) -> str:
        """Build full quiz link URL with token.

        Args:
            token: JWT token for quiz access

        Returns:
            Complete quiz link URL
        """
        parsed = urlsplit(self.config.MONTHLY_QUIZ_BASE_URL)
        query_params = [
            (key, value) for key, value in parse_qsl(parsed.query) if key != "token"
        ]
        query_params.append(("token", token))
        query = urlencode(query_params)
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment)
        )

    def build_redacted_link(self) -> str:
        """Build redacted link URL for display purposes.

        Returns:
            Link URL with [REDACTED] token placeholder
        """
        return f"{self.config.MONTHLY_QUIZ_BASE_URL}?token=[REDACTED]"

    def build_short_link(self, short_code: str) -> Optional[str]:
        """Build short quiz link URL with short code."""
        if not self.config.MONTHLY_QUIZ_SHORT_BASE_URL:
            return None
        return f"{self.config.MONTHLY_QUIZ_SHORT_BASE_URL.rstrip('/')}/{short_code}"

    def build_preferred_link(self, token: str, short_code: Optional[str] = None) -> str:
        """Prefer short link when configured and available; fallback to full token link."""
        if short_code:
            short_link = self.build_short_link(short_code)
            if short_link:
                return short_link
        return self.build_link(token)
