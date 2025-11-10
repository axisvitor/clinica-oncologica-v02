"""
HTTP Response Caching Middleware for Hormonia Backend System.
Provides intelligent caching for GET requests with ETag and Cache-Control support.
"""

import hashlib
import json
import logging
from typing import Callable, Optional
from datetime import timedelta

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers

from app.core.redis_unified import get_sync_redis
from app.infrastructure.cache import get_unified_cache_manager as get_cache_manager

logger = logging.getLogger(__name__)


class CacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware for HTTP response caching with ETag and conditional request support.

    Features:
    - Caches GET requests only
    - ETag generation and If-None-Match header support
    - Cache-Control header configuration
    - Configurable TTL per endpoint pattern
    - Excludes authenticated endpoints by default
    """

    def __init__(
        self,
        app,
        default_ttl: int = 300,  # 5 minutes default
        exclude_patterns: Optional[list[str]] = None,
        cache_authenticated: bool = False
    ):
        """
        Initialize cache middleware.

        Args:
            app: FastAPI application instance
            default_ttl: Default cache TTL in seconds
            exclude_patterns: List of path patterns to exclude from caching
            cache_authenticated: Whether to cache authenticated requests
        """
        super().__init__(app)
        self.default_ttl = default_ttl
        self.exclude_patterns = exclude_patterns or [
            "/api/v2/auth",  # Never cache auth endpoints
            "/api/v2/admin",  # Never cache admin endpoints
            "/ws",  # Never cache WebSocket
            "/health",  # Never cache health checks
        ]
        self.cache_authenticated = cache_authenticated
        self.cache_manager = get_cache_manager()

        # Custom TTL per endpoint pattern
        self.endpoint_ttl = {
            "/api/v2/patients": 300,  # 5 minutes for patient lists
            "/api/v2/dashboard": 60,  # 1 minute for dashboard
            "/api/v2/templates": 3600,  # 1 hour for templates
            "/api/v2/reports": 600,  # 10 minutes for reports
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and handle caching logic.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            HTTP response (cached or fresh)
        """
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)

        # Check if path should be excluded
        if self._should_exclude(request.url.path):
            logger.debug(f"Excluded from cache: {request.url.path}")
            return await call_next(request)

        # Check if authenticated request (skip caching unless configured)
        if not self.cache_authenticated and self._is_authenticated(request):
            logger.debug(f"Skipping cache for authenticated request: {request.url.path}")
            return await call_next(request)

        # Generate cache key from request
        cache_key = self._generate_cache_key(request)
        logger.debug(f"Cache key generated: {cache_key}")

        # Check for If-None-Match header (ETag conditional request)
        if_none_match = request.headers.get("If-None-Match")

        # Try to get cached response
        cached_data = self.cache_manager.get(cache_key, namespace="http_cache")

        if cached_data:
            cached_etag = cached_data.get("etag")
            cached_body = cached_data.get("body")
            cached_headers = cached_data.get("headers", {})

            # Check ETag match for 304 Not Modified
            if if_none_match and if_none_match == cached_etag:
                logger.debug(f"ETag match - returning 304 Not Modified for: {cache_key}")
                return Response(
                    status_code=304,
                    headers={"ETag": cached_etag}
                )

            # Return cached response with ETag
            logger.debug(f"Cache HIT - returning cached response for: {cache_key}")
            headers = dict(cached_headers)
            headers["ETag"] = cached_etag
            headers["X-Cache"] = "HIT"

            return Response(
                content=cached_body,
                status_code=200,
                headers=headers,
                media_type=cached_headers.get("content-type", "application/json")
            )

        # Cache MISS - execute request
        logger.debug(f"Cache MISS - fetching fresh response for: {cache_key}")
        response = await call_next(request)

        # Only cache successful responses
        if response.status_code == 200:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Generate ETag from response body
            etag = self._generate_etag(body)

            # Determine TTL for this endpoint
            ttl = self._get_ttl_for_path(request.url.path)

            # Cache the response
            cache_data = {
                "body": body.decode("utf-8") if body else "",
                "headers": dict(response.headers),
                "etag": etag
            }

            self.cache_manager.set(
                cache_key,
                cache_data,
                ttl=ttl,
                namespace="http_cache"
            )
            logger.debug(f"Cached response for: {cache_key} (TTL: {ttl}s)")

            # Build response headers
            response_headers = dict(response.headers)
            response_headers["ETag"] = etag
            response_headers["Cache-Control"] = f"public, max-age={ttl}"
            response_headers["X-Cache"] = "MISS"

            # Return fresh response with caching headers
            return Response(
                content=body,
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.headers.get("content-type", "application/json")
            )

        return response

    def _should_exclude(self, path: str) -> bool:
        """
        Check if path should be excluded from caching.

        Args:
            path: Request path

        Returns:
            True if should exclude, False otherwise
        """
        for pattern in self.exclude_patterns:
            if path.startswith(pattern):
                return True
        return False

    def _is_authenticated(self, request: Request) -> bool:
        """
        Check if request contains authentication.

        Args:
            request: HTTP request

        Returns:
            True if authenticated, False otherwise
        """
        auth_header = request.headers.get("Authorization")
        return auth_header is not None and auth_header.startswith("Bearer ")

    def _generate_cache_key(self, request: Request) -> str:
        """
        Generate unique cache key from request.

        Args:
            request: HTTP request

        Returns:
            Cache key string
        """
        # Include path, query params, and selected headers
        key_parts = [
            request.url.path,
            str(request.url.query),
        ]

        # Include Accept header for content negotiation
        accept = request.headers.get("Accept", "")
        if accept:
            key_parts.append(accept)

        key_string = "|".join(key_parts)

        # Hash for shorter keys
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"http:{key_hash}"

    def _generate_etag(self, content: bytes) -> str:
        """
        Generate ETag from response content.

        Args:
            content: Response body bytes

        Returns:
            ETag string
        """
        content_hash = hashlib.md5(content).hexdigest()
        return f'"{content_hash}"'

    def _get_ttl_for_path(self, path: str) -> int:
        """
        Get TTL for a specific path.

        Args:
            path: Request path

        Returns:
            TTL in seconds
        """
        for pattern, ttl in self.endpoint_ttl.items():
            if path.startswith(pattern):
                return ttl
        return self.default_ttl


def invalidate_http_cache_pattern(pattern: str) -> int:
    """
    Invalidate HTTP cache entries matching a pattern.

    Args:
        pattern: Cache key pattern (supports wildcards)

    Returns:
        Number of entries invalidated
    """
    cache_manager = get_cache_manager()
    deleted = cache_manager.invalidate_pattern(pattern, namespace="http_cache")
    logger.info(f"Invalidated {deleted} HTTP cache entries matching: {pattern}")
    return deleted


def invalidate_http_cache_for_path(path: str) -> int:
    """
    Invalidate all HTTP cache entries for a specific path.

    Args:
        path: URL path

    Returns:
        Number of entries invalidated
    """
    # Generate pattern to match all cache keys for this path
    # Since we hash the keys, we need to invalidate the entire namespace
    # or maintain a separate index - for now, we'll use pattern matching
    cache_manager = get_cache_manager()
    deleted = cache_manager.invalidate_pattern("http:*", namespace="http_cache")
    logger.info(f"Invalidated {deleted} HTTP cache entries for path: {path}")
    return deleted
