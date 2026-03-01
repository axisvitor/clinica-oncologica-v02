"""
Shared Redis JSON cache helpers for service-layer classes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from app.core.redis_manager import get_async_redis_client as get_async_redis


class RedisJsonCacheMixin:
    """
    Reusable cache behavior for services that persist JSON payloads in Redis.

    Subclasses must set `_cache_namespace` and should set `_logger`.
    """

    _cache_namespace: str = "service"

    async def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        logger = getattr(self, "_logger", None)
        try:
            redis_client = await get_async_redis()
            if redis_client is None:
                return None
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as exc:
            if logger:
                logger.warning(f"Cache read failed: {exc}")
            return None

    async def _set_cached_result(self, cache_key: str, data: Any, ttl: int) -> None:
        logger = getattr(self, "_logger", None)
        try:
            redis_client = await get_async_redis()
            if redis_client is None:
                return

            if hasattr(data, "dict"):
                serialized = json.dumps(data.dict(), default=str)
            elif hasattr(data, "model_dump"):
                serialized = json.dumps(data.model_dump(), default=str)
            else:
                serialized = json.dumps(data, default=str)

            await redis_client.setex(cache_key, ttl, serialized)
        except Exception as exc:
            if logger:
                logger.warning(f"Cache write failed: {exc}")

    def _get_cache_key(self, endpoint: str, **params: Any) -> str:
        param_str = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        return f"{self._cache_namespace}:v2:{endpoint}:{param_hash}"
