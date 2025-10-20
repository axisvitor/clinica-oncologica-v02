"""
JWT Cache - Specialized JWT Token Caching
==========================================

Wrapper around CacheLayer for JWT-specific operations.

Features:
- Token validation caching
- Blacklist management
- Short TTL (minutes)
- Fast lookups
- User session management

Author: AI Architect
Date: 20 Jan 2025
Version: 2.0.0 (Consolidated)
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID

from app.services.ai.cache_layer import CacheLayer, CacheOperation, get_cache_layer

logger = logging.getLogger(__name__)


class JWTCache:
    """
    JWT token caching with blacklist management.

    Specialized wrapper around CacheLayer for JWT-specific operations.
    Provides token validation caching, blacklist management, and session tracking.

    Features:
    - Token validation caching (5 minutes default)
    - Blacklist management (24 hours default)
    - User session tracking
    - Fast Redis lookups
    - Automatic expiration

    Example:
        >>> jwt_cache = JWTCache()
        >>> await jwt_cache.initialize()
        >>>
        >>> # Cache token
        >>> await jwt_cache.cache_token("user:123", token_data, ttl=300)
        >>>
        >>> # Check validity
        >>> token = await jwt_cache.get_token("user:123")
        >>>
        >>> # Blacklist token
        >>> await jwt_cache.blacklist_token("token_jti_123")
        >>> is_blacklisted = await jwt_cache.is_blacklisted("token_jti_123")
    """

    # TTL configurations (in seconds)
    DEFAULT_TTL = 300  # 5 minutes for token cache
    BLACKLIST_TTL = 86400  # 24 hours for blacklist
    REFRESH_TOKEN_TTL = 604800  # 7 days for refresh tokens

    def __init__(self, cache_layer: Optional[CacheLayer] = None):
        """
        Initialize JWT cache.

        Args:
            cache_layer: Cache layer instance (optional, uses singleton if not provided)
        """
        self.cache = cache_layer
        self._initialized = False

        logger.info("JWTCache initialized")

    async def initialize(self):
        """Initialize cache layer connection."""
        if self._initialized:
            return

        if not self.cache:
            self.cache = await get_cache_layer()

        self._initialized = True
        logger.info("JWTCache initialized successfully")

    # Token caching methods

    async def cache_token(
        self,
        user_id: str,
        token_data: Dict[str, Any],
        ttl: Optional[int] = None,
        token_type: str = "access",
    ):
        """
        Cache JWT token data for a user.

        Args:
            user_id: User identifier
            token_data: Token data to cache (should include: token, jti, exp, etc)
            ttl: Time to live in seconds (default: 300 for access, 604800 for refresh)
            token_type: Type of token ("access" or "refresh")

        Example:
            >>> token_data = {
            ...     "token": "eyJ...",
            ...     "jti": "unique_token_id",
            ...     "exp": 1234567890,
            ...     "user_id": "123"
            ... }
            >>> await jwt_cache.cache_token("user:123", token_data)
        """
        # Determine TTL based on token type
        if ttl is None:
            ttl = (
                self.REFRESH_TOKEN_TTL if token_type == "refresh" else self.DEFAULT_TTL
            )

        # Build cache key
        key = self._build_token_key(user_id, token_type)

        # Add metadata
        cache_data = {
            **token_data,
            "_cached_at": datetime.utcnow().isoformat(),
            "_token_type": token_type,
        }

        await self.cache.set(
            key,
            cache_data,
            CacheOperation.RESPONSE_GENERATION,
            ttl=ttl,
            tags=[f"user:{user_id}", "jwt", f"jwt:{token_type}"],
        )

        logger.debug(f"Cached {token_type} token for user {user_id}, TTL: {ttl}s")

    async def get_token(
        self, user_id: str, token_type: str = "access"
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached token data for a user.

        Args:
            user_id: User identifier
            token_type: Type of token ("access" or "refresh")

        Returns:
            Token data if cached, None if not found or expired

        Example:
            >>> token = await jwt_cache.get_token("user:123")
            >>> if token:
            ...     print(f"Token: {token['token']}")
        """
        key = self._build_token_key(user_id, token_type)
        return await self.cache.get(key, CacheOperation.RESPONSE_GENERATION)

    async def invalidate_token(self, user_id: str, token_type: str = "access"):
        """
        Invalidate cached token for a user.

        Args:
            user_id: User identifier
            token_type: Type of token ("access" or "refresh")

        Example:
            >>> # User logged out
            >>> await jwt_cache.invalidate_token("user:123", "access")
        """
        key = self._build_token_key(user_id, token_type)
        await self.cache.invalidate(key)

        logger.info(f"Invalidated {token_type} token for user {user_id}")

    async def invalidate_all_user_tokens(self, user_id: str):
        """
        Invalidate all tokens (access + refresh) for a user.

        Args:
            user_id: User identifier

        Example:
            >>> # User password changed, invalidate all sessions
            >>> await jwt_cache.invalidate_all_user_tokens("user:123")
        """
        await self.cache.invalidate_by_tag(f"user:{user_id}")

        logger.info(f"Invalidated all tokens for user {user_id}")

    # Blacklist methods

    async def blacklist_token(
        self, token_jti: str, reason: Optional[str] = None, ttl: Optional[int] = None
    ):
        """
        Add token to blacklist.

        Blacklisted tokens will be rejected even if they are valid.
        Used for logout, token revocation, or security incidents.

        Args:
            token_jti: JWT Token ID (jti claim)
            reason: Optional reason for blacklisting
            ttl: Time to live in seconds (default: 24 hours)

        Example:
            >>> # User logged out, blacklist the token
            >>> await jwt_cache.blacklist_token(
            ...     "token_jti_123",
            ...     reason="user_logout"
            ... )
        """
        key = f"jwt:blacklist:{token_jti}"

        blacklist_data = {
            "blacklisted": True,
            "timestamp": datetime.utcnow().isoformat(),
            "jti": token_jti,
        }

        if reason:
            blacklist_data["reason"] = reason

        await self.cache.set(
            key,
            blacklist_data,
            CacheOperation.RESPONSE_GENERATION,
            ttl=ttl or self.BLACKLIST_TTL,
            tags=["jwt:blacklist"],
        )

        logger.warning(
            f"Token blacklisted: {token_jti}, reason: {reason or 'not specified'}"
        )

    async def is_blacklisted(self, token_jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token_jti: JWT Token ID (jti claim)

        Returns:
            True if token is blacklisted, False otherwise

        Example:
            >>> if await jwt_cache.is_blacklisted("token_jti_123"):
            ...     raise UnauthorizedError("Token has been revoked")
        """
        key = f"jwt:blacklist:{token_jti}"
        result = await self.cache.get(key, CacheOperation.RESPONSE_GENERATION)
        return result is not None

    async def get_blacklist_info(self, token_jti: str) -> Optional[Dict[str, Any]]:
        """
        Get blacklist information for a token.

        Args:
            token_jti: JWT Token ID

        Returns:
            Blacklist data if found, None otherwise
        """
        key = f"jwt:blacklist:{token_jti}"
        return await self.cache.get(key, CacheOperation.RESPONSE_GENERATION)

    async def remove_from_blacklist(self, token_jti: str):
        """
        Remove token from blacklist (emergency recovery).

        Args:
            token_jti: JWT Token ID

        Example:
            >>> # Token was blacklisted by mistake
            >>> await jwt_cache.remove_from_blacklist("token_jti_123")
        """
        key = f"jwt:blacklist:{token_jti}"
        await self.cache.invalidate(key)

        logger.warning(f"Token removed from blacklist: {token_jti}")

    # Session management

    async def track_session(
        self,
        session_id: str,
        user_id: str,
        session_data: Dict[str, Any],
        ttl: Optional[int] = None,
    ):
        """
        Track user session.

        Args:
            session_id: Unique session identifier
            user_id: User identifier
            session_data: Session data (device, IP, location, etc)
            ttl: Time to live in seconds (default: 7 days)

        Example:
            >>> session_data = {
            ...     "device": "Chrome/Windows",
            ...     "ip": "192.168.1.1",
            ...     "location": "São Paulo, BR"
            ... }
            >>> await jwt_cache.track_session(
            ...     "session_123",
            ...     "user:123",
            ...     session_data
            ... )
        """
        key = f"jwt:session:{session_id}"

        cache_data = {
            **session_data,
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        await self.cache.set(
            key,
            cache_data,
            CacheOperation.RESPONSE_GENERATION,
            ttl=ttl or self.REFRESH_TOKEN_TTL,
            tags=[f"user:{user_id}", "jwt:session"],
        )

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        key = f"jwt:session:{session_id}"
        return await self.cache.get(key, CacheOperation.RESPONSE_GENERATION)

    async def invalidate_session(self, session_id: str):
        """Invalidate a specific session."""
        key = f"jwt:session:{session_id}"
        await self.cache.invalidate(key)

        logger.info(f"Session invalidated: {session_id}")

    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a user.

        Note: This is a simplified implementation. For production,
        you might want to maintain a separate index of sessions per user.

        Args:
            user_id: User identifier

        Returns:
            List of active sessions
        """
        # This is a placeholder - in production you'd maintain a session index
        # For now, return empty list
        logger.warning(
            "get_user_sessions is not fully implemented - requires session index"
        )
        return []

    # Statistics and monitoring

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get JWT cache statistics.

        Returns:
            Dictionary with cache stats

        Example:
            >>> stats = await jwt_cache.get_stats()
            >>> print(f"Cache hit rate: {stats['hit_rate']}%")
        """
        cache_stats = await self.cache.get_stats()

        return {
            **cache_stats,
            "cache_type": "jwt",
            "default_ttl": self.DEFAULT_TTL,
            "blacklist_ttl": self.BLACKLIST_TTL,
        }

    # Private helper methods

    def _build_token_key(self, user_id: str, token_type: str) -> str:
        """Build cache key for token."""
        return f"jwt:token:{token_type}:{user_id}"


# Singleton instance
_jwt_cache: Optional[JWTCache] = None


async def get_jwt_cache() -> JWTCache:
    """
    Get or create singleton JWTCache instance.

    Returns:
        Initialized JWTCache instance

    Example:
        >>> jwt_cache = await get_jwt_cache()
        >>> await jwt_cache.cache_token("user:123", token_data)
    """
    global _jwt_cache

    if _jwt_cache is None:
        _jwt_cache = JWTCache()
        await _jwt_cache.initialize()

    return _jwt_cache


async def reset_jwt_cache():
    """Reset singleton instance (for testing)."""
    global _jwt_cache
    _jwt_cache = None
