"""
JWT Cache Wrapper
=================

In-memory JWT/session cache used by tests and cache invalidation routines.
Provides token storage, user-based invalidation, and blacklist tracking.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional, Set
from uuid import UUID

_jwt_cache_singleton: Optional["JWTCache"] = None


class JWTCache:
    """Simple async JWT cache with optional TTL support."""

    def __init__(self, cache_layer: Optional[Any] = None):
        self.cache_layer = cache_layer
        self._lock = asyncio.Lock()
        self._tokens: Dict[str, Dict[str, Any]] = {}
        self._user_index: Dict[str, Set[str]] = {}
        self._blacklist: Dict[str, Optional[float]] = {}

    async def cache_token(
        self,
        token_id: str,
        data: Dict[str, Any],
        *,
        user_id: Optional[UUID | str] = None,
        ttl: int = 3600,
    ) -> bool:
        """Store a token payload optionally linked to a user."""
        expires_at = time.monotonic() + ttl if ttl else None
        user_key = str(user_id) if user_id is not None else None

        async with self._lock:
            self._tokens[token_id] = {
                "value": data,
                "expires_at": expires_at,
                "user_id": user_key,
            }
            if user_key:
                self._user_index.setdefault(user_key, set()).add(token_id)
        return True

    async def get_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Return token payload if present and not expired/blacklisted."""
        async with self._lock:
            if token_id in self._blacklist and not self._blacklist[token_id]:
                return None
            entry = self._tokens.get(token_id)
            if not entry:
                return None
            expires_at = entry.get("expires_at")
            if expires_at and expires_at <= time.monotonic():
                await self._remove_token_locked(token_id)
                return None
            return entry["value"]

    async def blacklist_token(self, token_id: str, ttl: Optional[int] = None) -> bool:
        """Blacklists a token ID."""
        expires_at = time.monotonic() + ttl if ttl else None
        async with self._lock:
            self._blacklist[token_id] = expires_at
            await self._remove_token_locked(token_id)
        return True

    async def is_blacklisted(self, token_id: str) -> bool:
        """Check if token is blacklisted (and clean expired entries)."""
        async with self._lock:
            expires_at = self._blacklist.get(token_id)
            if expires_at is None:
                return token_id in self._blacklist
            if expires_at <= time.monotonic():
                self._blacklist.pop(token_id, None)
                return False
            return True

    async def invalidate_user_tokens(self, user_id: UUID | str) -> int:
        """Remove all tokens associated with a user."""
        user_key = str(user_id)
        async with self._lock:
            token_ids = list(self._user_index.get(user_key, []))
            for token_id in token_ids:
                await self._remove_token_locked(token_id)
            self._user_index.pop(user_key, None)
        return len(token_ids)

    async def clear_all(self) -> int:
        """Clear tokens and blacklist entries."""
        async with self._lock:
            deleted = len(self._tokens) + len(self._blacklist)
            self._tokens.clear()
            self._user_index.clear()
            self._blacklist.clear()
        return deleted

    async def _remove_token_locked(self, token_id: str) -> None:
        """Remove token assuming caller holds the lock."""
        entry = self._tokens.pop(token_id, None)
        if entry and entry.get("user_id"):
            user_key = entry["user_id"]
            token_set = self._user_index.get(user_key)
            if token_set:
                token_set.discard(token_id)
                if not token_set:
                    self._user_index.pop(user_key, None)

    async def get_stats(self) -> Dict[str, Any]:
        async with self._lock:
            stats = {
                "tokens": len(self._tokens),
                "users": len(self._user_index),
                "blacklisted": len(self._blacklist),
            }
        strategy_obj = getattr(self.cache_layer, "strategy", None)
        strategy = getattr(strategy_obj, "value", strategy_obj) or "memory"
        stats["strategy"] = strategy
        return stats


def get_jwt_cache() -> JWTCache:
    """Return singleton JWT cache instance."""
    global _jwt_cache_singleton
    if _jwt_cache_singleton is None:
        _jwt_cache_singleton = JWTCache()
    return _jwt_cache_singleton


__all__ = ["JWTCache", "get_jwt_cache"]
