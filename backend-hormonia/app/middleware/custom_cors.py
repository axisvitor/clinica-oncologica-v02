"""
Custom CORS middleware with pattern matching support.

Extends FastAPI's CORSMiddleware to support wildcard patterns for Railway deployments
and other dynamic domain configurations.
"""
import re
from typing import List, Pattern
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PatternCORSMiddleware(CORSMiddleware):
    """
    Enhanced CORS middleware that supports pattern matching for allowed origins.

    Features:
    - Wildcard pattern support (*.domain.com)
    - Regex pattern support
    - Standard CORS origin validation
    - Railway deployment pattern support
    """

    def __init__(
        self,
        app: ASGIApp,
        allow_origins: List[str] = None,
        allow_origin_patterns: List[str] = None,
        **kwargs
    ):
        """
        Initialize custom CORS middleware.

        Args:
            app: ASGI application
            allow_origins: Standard list of allowed origins
            allow_origin_patterns: List of patterns for dynamic origin matching
            **kwargs: Additional CORS configuration options
        """
        # Extract pattern origins from allow_origins
        if allow_origins:
            standard_origins = []
            pattern_origins = allow_origin_patterns or []

            for origin in allow_origins:
                if '*' in origin:
                    pattern_origins.append(origin)
                else:
                    standard_origins.append(origin)

            allow_origins = standard_origins
            allow_origin_patterns = pattern_origins

        # Initialize parent with non-pattern origins
        super().__init__(app, allow_origins=allow_origins or [], **kwargs)

        # Compile patterns for efficient matching
        self.origin_patterns: List[Pattern] = []
        if allow_origin_patterns:
            for pattern in allow_origin_patterns:
                try:
                    # Convert wildcard patterns to regex
                    regex_pattern = self._wildcard_to_regex(pattern)
                    compiled_pattern = re.compile(regex_pattern, re.IGNORECASE)
                    self.origin_patterns.append(compiled_pattern)
                    logger.info(f"Compiled CORS pattern: {pattern} -> {regex_pattern}")
                except Exception as e:
                    logger.warning(f"Failed to compile CORS pattern '{pattern}': {e}")

    def _wildcard_to_regex(self, pattern: str) -> str:
        r"""
        Convert wildcard pattern to regex.

        Examples:
        - "https://*.railway.app" -> r"^https://[^./]+\.railway\.app$"
        - "https://quiz-*.railway.app" -> r"^https://quiz-[^./]+\.railway\.app$"
        """
        # Escape regex special characters except *
        escaped = re.escape(pattern)
        # Replace escaped asterisks with regex pattern
        regex = escaped.replace(r'\*', r'[^./]+')
        # Anchor the pattern
        return f"^{regex}$"

    def is_allowed_origin(self, origin: str) -> bool:
        """
        Check if origin is allowed using both standard and pattern matching.

        Args:
            origin: Origin to check

        Returns:
            bool: True if origin is allowed
        """
        # Check standard origins first (parent implementation)
        if super().is_allowed_origin(origin):
            return True

        # Check against compiled patterns
        for pattern in self.origin_patterns:
            if pattern.match(origin):
                logger.debug(f"Origin '{origin}' matched pattern: {pattern.pattern}")
                return True

        logger.debug(f"Origin '{origin}' not allowed")
        return False


def create_enhanced_cors_middleware(
    allowed_origins: List[str],
    **cors_config
) -> PatternCORSMiddleware:
    """
    Create enhanced CORS middleware with pattern support.

    Args:
        allowed_origins: List of allowed origins (including patterns)
        **cors_config: Additional CORS configuration

    Returns:
        PatternCORSMiddleware: Configured CORS middleware
    """
    return PatternCORSMiddleware(
        app=None,  # Will be set when added to FastAPI
        allow_origins=allowed_origins,
        allow_credentials=cors_config.get('allow_credentials', True),
        allow_methods=cors_config.get('allow_methods', [
            "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"
        ]),
        allow_headers=cors_config.get('allow_headers', [
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-Request-ID",
            "X-Correlation-ID",
            # WebSocket specific headers
            "Sec-WebSocket-Protocol",
            "Sec-WebSocket-Extensions",
            "Sec-WebSocket-Key",
            "Sec-WebSocket-Version",
            "Upgrade",
            "Connection"
        ]),
        expose_headers=cors_config.get('expose_headers', [
            "X-Request-ID",
            "X-Correlation-ID",
            "X-Process-Time",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ]),
        max_age=cors_config.get('max_age', 86400)
    )


# Quiz-specific CORS configuration
def get_quiz_cors_patterns() -> List[str]:
    """Get CORS patterns based on environment - NO wildcards in production."""
    import os

    environment = os.getenv('ENVIRONMENT', 'development').lower()

    patterns = [
        # Local development
        "http://localhost:3001",
        "http://localhost:5174",
        # Railway production - EXPLICIT URLs ONLY
        "https://interface-quiz-production.up.railway.app",
        "https://quiz-mensal-interface.railway.app",
        "https://quiz-interface-production.up.railway.app",
        "https://frontend-production-18bb.up.railway.app",
        "https://hormonia-frontend.railway.app"
    ]

    # ONLY allow wildcards in development/staging
    if environment in ['development', 'staging', 'dev']:
        patterns.extend([
            "https://*.railway.app",
            "https://quiz-*.railway.app",
            "https://*-quiz.railway.app"
        ])

    return patterns

QUIZ_CORS_PATTERNS = get_quiz_cors_patterns()


def get_quiz_cors_config() -> dict:
    """Get CORS configuration optimized for quiz interface."""
    return {
        'allow_credentials': True,
        'allow_methods': ["GET", "POST", "PUT", "OPTIONS"],
        'allow_headers': [
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-Request-ID",
            "X-Quiz-Token",  # Quiz-specific header
            "X-Patient-ID"   # Quiz patient identification
        ],
        'expose_headers': [
            "X-Request-ID",
            "X-Quiz-Session-ID",
            "X-Quiz-Progress",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining"
        ],
        'max_age': 3600  # Shorter cache for quiz interface
    }