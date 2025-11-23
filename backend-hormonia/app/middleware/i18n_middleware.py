"""
i18n Middleware for FastAPI

Automatically detects and sets the locale for each request based on:
1. Query parameter (?lang=en-US)
2. Accept-Language header
3. Cookie (locale=en-US)
4. Default (pt-BR)

Adds Content-Language header to responses to indicate the language used.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging

from app.config.i18n import get_locale_from_request, set_locale

logger = logging.getLogger(__name__)


class I18nMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle i18n locale detection and setting.

    Usage:
        app.add_middleware(I18nMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        """
        Process request and set locale before passing to endpoint.

        Args:
            request: FastAPI Request object
            call_next: Next middleware/endpoint in chain

        Returns:
            Response with Content-Language header set
        """
        # Detect locale from request
        locale = get_locale_from_request(request)

        # Set locale for this request
        set_locale(locale)

        # Store locale in request state for easy access
        request.state.locale = locale

        logger.debug(f"Request locale set to: {locale}")

        # Process request
        response: Response = await call_next(request)

        # Add Content-Language header to response
        response.headers['Content-Language'] = locale

        return response


async def i18n_middleware(request: Request, call_next):
    """
    Functional middleware for i18n (alternative to class-based).

    Usage:
        app.middleware("http")(i18n_middleware)

    Args:
        request: FastAPI Request object
        call_next: Next middleware/endpoint in chain

    Returns:
        Response with Content-Language header set
    """
    # Detect locale from request
    locale = get_locale_from_request(request)

    # Set locale for this request
    set_locale(locale)

    # Store locale in request state
    request.state.locale = locale

    logger.debug(f"Request locale set to: {locale}")

    # Process request
    response: Response = await call_next(request)

    # Add Content-Language header
    response.headers['Content-Language'] = locale

    return response
