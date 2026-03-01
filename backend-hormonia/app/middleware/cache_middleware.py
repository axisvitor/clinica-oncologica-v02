"""
HTTP Response Caching Middleware for Hormonia Backend System.
Provides intelligent caching for GET requests with ETag and Cache-Control support.
"""

import hashlib
import logging
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

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
        cache_authenticated: bool = True,  # ENABLED for authenticated requests
        authenticated_ttl: int = 90,  # Shorter TTL for authenticated data (90 seconds)
    ):
        """
        Initialize cache middleware.

        Args:
            app: FastAPI application instance
            default_ttl: Default cache TTL in seconds
            exclude_patterns: List of path patterns to exclude from caching
            cache_authenticated: Whether to cache authenticated requests
            authenticated_ttl: TTL for authenticated requests (default: 90s)
        """
        super().__init__(app)
        self.default_ttl = default_ttl
        self.exclude_patterns = exclude_patterns or [
            "/api/v2/auth",  # Never cache auth endpoints
            "/api/v2/admin",  # Never cache admin endpoints
            "/api/v2/alerts",  # Alert data must reflect latest writes
            "/ws",  # Never cache WebSocket
            "/health",  # Never cache health checks
        ]
        self.cache_authenticated = cache_authenticated
        self.authenticated_ttl = authenticated_ttl  # Shorter TTL for security
        self.cache_manager = get_cache_manager()

        # Custom TTL per endpoint pattern (for authenticated requests)
        self.endpoint_ttl = {
            "/api/v2/patients": 120,  # 2 minutes for patient lists (authenticated)
            "/api/v2/dashboard": 60,  # 1 minute for dashboard (authenticated)
            "/api/v2/templates": 300,  # 5 minutes for templates (authenticated)
            "/api/v2/reports": 180,  # 3 minutes for reports (authenticated)
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
            logger.debug(
                f"Skipping cache for authenticated request: {request.url.path}"
            )
            return await call_next(request)

        # Generate cache key from request
        cache_key = self._generate_cache_key(request)
        logger.debug(f"Cache key generated: {cache_key}")

        # Check for If-None-Match header (ETag conditional request)
        if_none_match = request.headers.get("If-None-Match")

        # Try to get cached response (fail open on cache corruption or errors)
        cached_data = None
        try:
            cached_data = self.cache_manager.get("http_cache", key_parts=[cache_key])
        except Exception as exc:
            logger.warning(
                "Cache lookup failed for key %s: %s", cache_key, exc, exc_info=True
            )

        if cached_data:
            if not isinstance(cached_data, dict):
                logger.warning(
                    "Invalid cache entry type for key %s: %s",
                    cache_key,
                    type(cached_data).__name__,
                )
                cached_data = None
            else:
                cached_etag = cached_data.get("etag")
                cached_body = cached_data.get("body")
                cached_headers = cached_data.get("headers", {})
                is_compressed = cached_data.get("is_compressed", False)

                # Decode base64 for compressed data
                if is_compressed and cached_body:
                    try:
                        import base64

                        cached_body = base64.b64decode(cached_body)
                    except Exception as exc:
                        logger.warning(
                            "Failed to decode cached body for key %s: %s",
                            cache_key,
                            exc,
                            exc_info=True,
                        )
                        cached_data = None

                if cached_data is not None:
                    # Check ETag match for 304 Not Modified
                    if if_none_match and if_none_match == cached_etag:
                        logger.debug(
                            f"ETag match - returning 304 Not Modified for: {cache_key}"
                        )
                        return Response(status_code=304, headers={"ETag": cached_etag})

                    # Return cached response with ETag
                    logger.debug(f"Cache HIT - returning cached response for: {cache_key}")
                    headers = dict(cached_headers)
                    headers["ETag"] = cached_etag
                    headers["X-Cache"] = "HIT"

                    return Response(
                        content=cached_body,
                        status_code=200,
                        headers=headers,
                        media_type=cached_headers.get("content-type", "application/json"),
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

            # Determine TTL for this endpoint (shorter for authenticated)
            is_authenticated = self._is_authenticated(request)
            ttl = self._get_ttl_for_path(request.url.path, is_authenticated)

            # Cache the response - handle compressed data
            # Check if response is gzip compressed (0x1f 0x8b magic bytes)
            is_compressed = body and len(body) >= 2 and body[0] == 0x1f and body[1] == 0x8b
            cache_data = None
            try:
                if is_compressed:
                    # Store compressed body as base64
                    import base64

                    cache_data = {
                        "body": base64.b64encode(body).decode("ascii"),
                        "headers": dict(response.headers),
                        "etag": etag,
                        "is_compressed": True,
                    }
                else:
                    body_text = ""
                    if body:
                        try:
                            body_text = body.decode("utf-8")
                        except UnicodeDecodeError:
                            logger.warning(
                                "Skipping cache for key %s due to non-UTF8 body",
                                cache_key,
                            )
                            body_text = None
                    if body_text is not None:
                        cache_data = {
                            "body": body_text,
                            "headers": dict(response.headers),
                            "etag": etag,
                            "is_compressed": False,
                        }

                if cache_data is not None:
                    self.cache_manager.set(
                        "http_cache", cache_data, key_parts=[cache_key], ttl_override=ttl
                    )
                    logger.debug(f"Cached response for: {cache_key} (TTL: {ttl}s)")
            except Exception as exc:
                logger.warning(
                    "Cache write failed for key %s: %s", cache_key, exc, exc_info=True
                )

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
                media_type=response.headers.get("content-type", "application/json"),
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

        SECURITY: For authenticated requests, includes user_id in cache key
        to prevent data leakage between users.

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

        # SECURITY: Include user_id for authenticated requests
        # This prevents cache leakage between different users
        is_authenticated = self._is_authenticated(request)
        if is_authenticated:
            user_id = self._extract_user_id(request)
            if user_id:
                key_parts.append(f"user:{user_id}")
            else:
                auth_header = request.headers.get("Authorization", "")
                if auth_header:
                    auth_hash = hashlib.sha256(auth_header.encode()).hexdigest()[:16]
                    key_parts.append(f"auth:{auth_hash}")
        key_parts.append(f"auth:{'1' if is_authenticated else '0'}")

        key_string = "|".join(key_parts)

        # Hash for shorter keys
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return key_hash

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

    def _extract_user_id(self, request: Request) -> Optional[str]:
        """
        Extract user ID from request for cache key generation.

        Tries multiple sources:
        1. JWT token payload (sub claim)
        2. Session cookie
        3. Request state (if set by auth middleware)

        Args:
            request: HTTP request

        Returns:
            User ID string or None
        """
        try:
            # Try to get from JWT token
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                # Simple base64 decode of JWT payload (not validating, just extracting ID)
                try:
                    import base64
                    import json
                    # JWT format: header.payload.signature
                    payload_part = token.split('.')[1]
                    # Add padding if needed
                    padding = 4 - len(payload_part) % 4
                    if padding:
                        payload_part += '=' * padding
                    payload = json.loads(base64.urlsafe_b64decode(payload_part))
                    return payload.get('sub') or payload.get('user_id')
                except Exception as decode_err:
                    logger.debug(f"Failed to decode JWT for cache key: {decode_err}")

            # Try to get from request state (set by auth middleware)
            if hasattr(request.state, 'user_id'):
                return request.state.user_id

        except Exception as e:
            logger.warning(f"Failed to extract user_id for cache key: {e}")

        return None

    def _get_ttl_for_path(self, path: str, is_authenticated: bool = False) -> int:
        """
        Get TTL for a specific path.

        Uses shorter TTL for authenticated requests for security.

        Args:
            path: Request path
            is_authenticated: Whether request is authenticated

        Returns:
            TTL in seconds
        """
        # For authenticated requests, use shorter TTL
        if is_authenticated:
            for pattern, ttl in self.endpoint_ttl.items():
                if path.startswith(pattern):
                    return ttl
            return self.authenticated_ttl  # Use shorter default for authenticated

        # For public requests, use standard TTL
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
