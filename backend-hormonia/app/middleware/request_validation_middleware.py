"""
Request Validation Middleware
Middleware to catch and handle problematic requests before they reach endpoints.
"""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time

logger = logging.getLogger(__name__)


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate and sanitize request parameters before they reach endpoints.

    This middleware specifically handles cases where invalid parameters are sent
    that would cause validation errors in FastAPI endpoints.
    """

    def __init__(self, app, max_page_size: int = 100):
        super().__init__(app)
        self.max_page_size = max_page_size

    async def dispatch(self, request: Request, call_next):
        """Process request and validate parameters."""
        start_time = time.time()

        # Check if this is a request to patients endpoint
        if "/api/v2/patients" in str(request.url.path):
            request = await self._validate_patients_request(request)

        # Process the request
        try:
            response = await call_next(request)

            # Log slow requests
            process_time = time.time() - start_time
            if process_time > 1.0:  # Log requests taking more than 1 second
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} "
                    f"took {process_time:.2f}s"
                )

            return response

        except Exception as e:
            logger.error(f"Request processing error: {e}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    async def _validate_patients_request(self, request: Request) -> Request:
        """Validate and sanitize patients endpoint requests."""

        # Parse query parameters
        query_params = dict(request.query_params)
        original_params = query_params.copy()
        modified = False

        # Validate and fix size parameter
        if "size" in query_params:
            try:
                size = int(query_params["size"])
                if size > self.max_page_size:
                    logger.warning(
                        f"Invalid size parameter {size} from {request.client.host if request.client else 'unknown'}. "
                        f"URL: {request.url}. Clamping to {self.max_page_size}."
                    )
                    query_params["size"] = str(self.max_page_size)
                    modified = True
                elif size < 1:
                    logger.warning(
                        f"Invalid size parameter {size} from {request.client.host if request.client else 'unknown'}. "
                        f"URL: {request.url}. Setting to 20."
                    )
                    query_params["size"] = "20"
                    modified = True
            except ValueError:
                logger.warning(
                    f"Non-numeric size parameter '{query_params['size']}' from "
                    f"{request.client.host if request.client else 'unknown'}. Setting to 20."
                )
                query_params["size"] = "20"
                modified = True

        # Validate page parameter
        if "page" in query_params:
            try:
                page = int(query_params["page"])
                if page < 1:
                    logger.warning(
                        f"Invalid page parameter {page} from {request.client.host if request.client else 'unknown'}. "
                        f"Setting to 1."
                    )
                    query_params["page"] = "1"
                    modified = True
            except ValueError:
                logger.warning(
                    f"Non-numeric page parameter '{query_params['page']}' from "
                    f"{request.client.host if request.client else 'unknown'}. Setting to 1."
                )
                query_params["page"] = "1"
                modified = True

        # If we modified parameters, create a new request with corrected query string
        if modified:
            logger.info(
                f"Modified request parameters - Original: {original_params}, "
                f"Corrected: {query_params}, Client: {request.client.host if request.client else 'unknown'}"
            )

            # Rebuild query string
            new_query_string = "&".join([f"{k}={v}" for k, v in query_params.items()])

            # Create new URL with corrected parameters
            url_parts = str(request.url).split("?")
            new_url = url_parts[0]
            if new_query_string:
                new_url += "?" + new_query_string

            # Update request scope with new query string
            request.scope["query_string"] = new_query_string.encode()
            request._query_params = None  # Reset cached query params

        return request
