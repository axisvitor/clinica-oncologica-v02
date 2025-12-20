from datetime import datetime, timezone
from typing import Optional, Dict
import json

import redis.asyncio as redis

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ConnectionStateRepository:
    """Repository for storing WhatsApp instance connection states."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self._local_cache: Dict[str, Dict[str, str]] = {}

    async def _get_client(self) -> Optional[redis.Redis]:
        if self.redis_client:
            return self.redis_client
        try:
            client = redis.from_url(settings.REDIS_URL)
            await client.ping()
            return client
        except Exception as e:  # pragma: no cover - fallback when redis unavailable
            logger.warning(f"Redis not available: {e}")
            return None

    async def set_state(self, instance: str, state: str) -> None:
        data = {
            "instance": instance,
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        client = await self._get_client()
        key = f"connection_state:{instance}"
        if client:
            await client.set(key, json.dumps(data))
        self._local_cache[instance] = data

    async def get_state(self, instance: str) -> Optional[Dict[str, str]]:
        client = await self._get_client()
        key = f"connection_state:{instance}"
        if client:
            cached = await client.get(key)
            if cached:
                return json.loads(cached)
        return self._local_cache.get(instance)
