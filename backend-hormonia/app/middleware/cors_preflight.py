"""
CORS Preflight Headers Middleware

Ensures OPTIONS responses include CORS allow headers even when the request
is not a formal preflight (missing Access-Control-Request-Method).
"""

from typing import Iterable, List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.cors import get_allowed_origins
from app.config import settings

DEFAULT_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
DEFAULT_HEADERS: List[str] = [
    "Content-Type",
    "Authorization",
    "Accept",
    "Origin",
    "X-Requested-With",
    "X-CSRF-Token",
    "X-CSRFToken",
    "X-XSRF-Token",
    "X-Session-ID",
    "X-Idempotency-Key",
]


class CORSPreflightHeadersMiddleware(BaseHTTPMiddleware):
    """Add CORS headers to OPTIONS responses when Origin is allowed."""

    def __init__(
        self,
        app,
        allow_methods: Iterable[str] | None = None,
        allow_headers: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.allow_methods = list(allow_methods or DEFAULT_METHODS)
        self.allow_headers = list(
            allow_headers
            or getattr(settings, "CORS_ALLOWED_HEADERS", DEFAULT_HEADERS)
        )
        self.allowed_origins = set(get_allowed_origins())

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.method != "OPTIONS":
            return response

        origin = request.headers.get("origin")
        if not origin or origin not in self.allowed_origins:
            return response

        if "Access-Control-Allow-Origin" not in response.headers:
            response.headers["Access-Control-Allow-Origin"] = origin
        if "Access-Control-Allow-Methods" not in response.headers:
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
        if "Access-Control-Allow-Headers" not in response.headers:
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
        if "Access-Control-Allow-Credentials" not in response.headers:
            response.headers["Access-Control-Allow-Credentials"] = "true"

        return response
