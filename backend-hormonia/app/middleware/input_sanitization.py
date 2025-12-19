"""
Input sanitization middleware module.

This middleware sanitizes request input data to prevent injection attacks
and ensure data integrity.
"""

import json
from typing import Callable, Dict, Any

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logging import get_logger
from app.utils.input_sanitization import get_sanitizer

logger = get_logger(__name__)


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Middleware for sanitizing request input data."""

    def __init__(self, app):
        super().__init__(app)
        self.sanitizer = get_sanitizer()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only sanitize requests with body content
        if request.method in ["POST", "PUT", "PATCH"] and self._should_sanitize(
            request
        ):
            try:
                # Read and sanitize request body
                body = await request.body()
                if body:
                    content_type = request.headers.get("Content-Type", "")

                    if "application/json" in content_type:
                        try:
                            data = json.loads(body.decode())

                            # Validate JSON structure
                            self.sanitizer.validate_json_structure(data)

                            # Sanitize the data
                            sanitized_data = self._sanitize_request_data(
                                data, request.url.path
                            )

                            # Replace request body with sanitized data
                            sanitized_body = json.dumps(sanitized_data).encode()

                            # Create new request with sanitized body
                            async def receive():
                                return {
                                    "type": "http.request",
                                    "body": sanitized_body,
                                    "more_body": False,
                                }

                            # Update request's receive callable
                            request._receive = receive

                        except (json.JSONDecodeError, ValueError) as e:
                            logger.warning(
                                f"Invalid JSON in request: {e}",
                                extra={
                                    "event_type": "invalid_json_request",
                                    "path": request.url.path,
                                    "method": request.method,
                                },
                            )
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid JSON format",
                            )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error sanitizing request: {e}")
                # Continue without sanitization rather than failing

        return await call_next(request)

    def _should_sanitize(self, request: Request) -> bool:
        """Determine if request should be sanitized."""
        # Skip sanitization for certain endpoints
        skip_paths = ["/docs", "/redoc", "/openapi.json", "/health"]
        return not any(skip_path in request.url.path for skip_path in skip_paths)

    def _sanitize_request_data(self, data: Dict[str, Any], path: str) -> Dict[str, Any]:
        """Sanitize request data based on endpoint."""
        # Define field rules based on common patterns
        field_rules = {}

        # Authentication endpoints
        if "/auth/" in path:
            field_rules = {
                "email": {"max_length": 254},
                "password": {"max_length": 128, "strip_whitespace": False},
                "full_name": {"max_length": 100},
            }

        # Patient endpoints
        elif "/patients/" in path:
            field_rules = {
                "name": {"max_length": 100},
                "email": {"max_length": 254},
                "phone": {"max_length": 20},
                "treatment_type": {"max_length": 50},
                "notes": {"max_length": 1000, "allow_html": True},
            }

        # Message endpoints
        elif "/messages/" in path:
            field_rules = {
                "content": {"max_length": 4096, "allow_html": False},
                "type": {"max_length": 20},
            }

        # Quiz endpoints
        elif "/quiz/" in path:
            field_rules = {
                "question": {"max_length": 500},
                "answer": {"max_length": 1000},
                "title": {"max_length": 200},
            }

        return self.sanitizer.sanitize_dict(data, field_rules)


__all__ = ["InputSanitizationMiddleware"]
