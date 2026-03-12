"""
Utility functions for Redis Manager

Provides global manager instances and utility functions.
"""

import logging
import os
import sys
import fnmatch
from urllib.parse import urlparse, urlunparse
from typing import Optional, TYPE_CHECKING, Any

from app.config import settings

if TYPE_CHECKING:
    from .manager import RedisManager

logger = logging.getLogger(__name__)

# Global Redis manager instances
_redis_manager: Optional["RedisManager"] = None
_redis_cache_manager: Optional["RedisManager"] = None
_redis_broker_manager: Optional["RedisManager"] = None
_null_redis_manager: Optional["RedisManager"] = None


def build_redis_url_for_db(redis_url: str, db_number: int) -> str:
    """
    Return a Redis URL with a deterministic database path.

    Preserves scheme, credentials, host, port and query parameters.
    Falls back to the original URL if parsing is not possible.
    """
    if not redis_url:
        return redis_url

    parsed = urlparse(redis_url)
    if not parsed.scheme or not parsed.netloc:
        return redis_url

    normalized_path = f"/{int(db_number)}"
    return urlunparse(parsed._replace(path=normalized_path))


def _is_test_environment() -> bool:
    return bool(
        "pytest" in sys.modules
        or os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("TESTING") == "1"
        or os.getenv("APP_ENVIRONMENT", "").lower() in ("test", "testing")
    )


def _should_disable_redis() -> bool:
    return _is_test_environment() and os.getenv("USE_TEST_REDIS", "").lower() not in (
        "1",
        "true",
        "yes",
    )


def _get_hash_bucket(store: dict[str, Any], key: str) -> dict[Any, Any]:
    value = store.get(key)
    if isinstance(value, dict):
        return value
    bucket: dict[Any, Any] = {}
    store[key] = bucket
    return bucket


def _get_list_bucket(store: dict[str, Any], key: str) -> list[Any]:
    value = store.get(key)
    if isinstance(value, list):
        return value
    bucket: list[Any] = []
    store[key] = bucket
    return bucket


def _coerce_list_value(store: dict[str, Any], key: str) -> list[Any]:
    value = store.get(key)
    if isinstance(value, list):
        return value
    return []


def _list_normalized_index(length: int, index: int) -> int:
    return index + length if index < 0 else index


def _list_range(values: list[Any], start: int, end: int) -> list[Any]:
    length = len(values)
    if length == 0:
        return []

    start_idx = _list_normalized_index(length, start)
    end_idx = _list_normalized_index(length, end)

    if start_idx < 0:
        start_idx = 0
    if end_idx < 0:
        return []
    if end_idx >= length:
        end_idx = length - 1
    if start_idx >= length or start_idx > end_idx:
        return []

    return values[start_idx : end_idx + 1]


class _NullRedisPipelineBase:
    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store
        self._results: list[Any] = []

    def _record(self, value: Any):
        self._results.append(value)
        return self

    def get(self, key: str):
        return self._record(self._store.get(key))

    def set(self, key: str, value: Any, ex: Optional[int] = None, **kwargs):
        self._store[key] = value
        return self._record(True)

    def setex(self, key: str, seconds: int, value: Any):
        self._store[key] = value
        return self._record(True)

    def delete(self, *keys: str):
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return self._record(deleted)

    def exists(self, *keys: str):
        return self._record(sum(1 for key in keys if key in self._store))

    def incr(self, key: str, amount: int = 1):
        current = int(self._store.get(key, 0) or 0)
        current += amount
        self._store[key] = current
        return self._record(current)

    def hset(
        self,
        key: str,
        field: Optional[str] = None,
        value: Any = None,
        mapping: Optional[dict[Any, Any]] = None,
    ):
        bucket = _get_hash_bucket(self._store, key)
        created = 0

        if mapping:
            for map_field, map_value in mapping.items():
                if map_field not in bucket:
                    created += 1
                bucket[map_field] = map_value
            return self._record(created)

        if field is None:
            return self._record(0)

        if field not in bucket:
            created += 1
        bucket[field] = value
        return self._record(created)

    def hget(self, key: str, field: str):
        bucket = self._store.get(key)
        if not isinstance(bucket, dict):
            return self._record(None)
        return self._record(bucket.get(field))

    def hgetall(self, key: str):
        bucket = self._store.get(key)
        if not isinstance(bucket, dict):
            return self._record({})
        return self._record(dict(bucket))

    def hdel(self, key: str, *fields: str):
        bucket = self._store.get(key)
        if not isinstance(bucket, dict):
            return self._record(0)
        deleted = 0
        for field in fields:
            if field in bucket:
                del bucket[field]
                deleted += 1
        return self._record(deleted)

    def hincrby(self, key: str, field: str, amount: int = 1):
        bucket = _get_hash_bucket(self._store, key)
        current = int(bucket.get(field, 0) or 0)
        current += amount
        bucket[field] = current
        return self._record(current)

    def rpush(self, key: str, *values: Any):
        bucket = _get_list_bucket(self._store, key)
        bucket.extend(values)
        return self._record(len(bucket))

    def lpush(self, key: str, *values: Any):
        bucket = _get_list_bucket(self._store, key)
        for value in values:
            bucket.insert(0, value)
        return self._record(len(bucket))

    def lpop(self, key: str):
        bucket = _coerce_list_value(self._store, key)
        if not bucket:
            return self._record(None)
        return self._record(bucket.pop(0))

    def llen(self, key: str):
        bucket = _coerce_list_value(self._store, key)
        return self._record(len(bucket))

    def lindex(self, key: str, index: int):
        bucket = _coerce_list_value(self._store, key)
        if not bucket:
            return self._record(None)
        idx = _list_normalized_index(len(bucket), index)
        if idx < 0 or idx >= len(bucket):
            return self._record(None)
        return self._record(bucket[idx])

    def lrange(self, key: str, start: int, end: int):
        bucket = _coerce_list_value(self._store, key)
        return self._record(_list_range(bucket, start, end))

    def ltrim(self, key: str, start: int, end: int):
        if key not in self._store:
            return self._record(True)
        bucket = _coerce_list_value(self._store, key)
        self._store[key] = _list_range(bucket, start, end)
        return self._record(True)

    def lrem(self, key: str, count: int, value: Any):
        bucket = _coerce_list_value(self._store, key)
        if not bucket:
            return self._record(0)

        removed = 0
        if count == 0:
            self._store[key] = [item for item in bucket if item != value]
            removed = len(bucket) - len(self._store[key])
            return self._record(removed)

        if count > 0:
            kept = []
            for item in bucket:
                if item == value and removed < count:
                    removed += 1
                    continue
                kept.append(item)
            self._store[key] = kept
            return self._record(removed)

        target = abs(count)
        kept_reversed = []
        for item in reversed(bucket):
            if item == value and removed < target:
                removed += 1
                continue
            kept_reversed.append(item)
        self._store[key] = list(reversed(kept_reversed))
        return self._record(removed)

    def zremrangebyscore(self, key: str, min_score: float, max_score: float):
        return self._record(0)

    def zcard(self, key: str):
        return self._record(0)

    def zadd(self, key: str, mapping: dict[str, float]):
        return self._record(0)

    def expire(self, key: str, seconds: int):
        return self._record(True)

    def _consume_results(self) -> list[Any]:
        results = self._results
        self._results = []
        return results

    def execute(self) -> list[Any]:
        return self._consume_results()

    def __getattr__(self, name: str):
        def _noop(*args, **kwargs):
            return self._record(None)

        return _noop


class _NullRedisPipeline(_NullRedisPipelineBase):
    pass


class _NullAsyncRedisPipeline(_NullRedisPipelineBase):
    async def execute(self) -> list[Any]:
        return self._consume_results()


class _NullRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str):
        return self._store.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None, **kwargs):
        self._store[key] = value
        return True

    def setex(self, key: str, seconds: int, value: Any):
        self._store[key] = value
        return True

    def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return deleted

    def exists(self, *keys: str) -> int:
        return sum(1 for key in keys if key in self._store)

    def ttl(self, key: str) -> int:
        return -1

    def keys(self, pattern: str = "*") -> list[str]:
        return [key for key in self._store.keys() if fnmatch.fnmatch(key, pattern)]

    def incr(self, key: str, amount: int = 1) -> int:
        current = int(self._store.get(key, 0) or 0)
        current += amount
        self._store[key] = current
        return current

    def hset(
        self,
        key: str,
        field: Optional[str] = None,
        value: Any = None,
        mapping: Optional[dict[Any, Any]] = None,
    ) -> int:
        bucket = _get_hash_bucket(self._store, key)
        created = 0

        if mapping:
            for map_field, map_value in mapping.items():
                if map_field not in bucket:
                    created += 1
                bucket[map_field] = map_value
            return created

        if field is None:
            return 0

        if field not in bucket:
            created += 1
        bucket[field] = value
        return created

    def hget(self, key: str, field: str):
        bucket = self._store.get(key)
        if not isinstance(bucket, dict):
            return None
        return bucket.get(field)

    def hgetall(self, key: str) -> dict[Any, Any]:
        bucket = self._store.get(key)
        if not isinstance(bucket, dict):
            return {}
        return dict(bucket)

    def hdel(self, key: str, *fields: str) -> int:
        bucket = self._store.get(key)
        if not isinstance(bucket, dict):
            return 0
        deleted = 0
        for field in fields:
            if field in bucket:
                del bucket[field]
                deleted += 1
        return deleted

    def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        bucket = _get_hash_bucket(self._store, key)
        current = int(bucket.get(field, 0) or 0)
        current += amount
        bucket[field] = current
        return current

    def rpush(self, key: str, *values: Any) -> int:
        bucket = _get_list_bucket(self._store, key)
        bucket.extend(values)
        return len(bucket)

    def lpush(self, key: str, *values: Any) -> int:
        bucket = _get_list_bucket(self._store, key)
        for value in values:
            bucket.insert(0, value)
        return len(bucket)

    def lpop(self, key: str):
        bucket = _coerce_list_value(self._store, key)
        if not bucket:
            return None
        return bucket.pop(0)

    def llen(self, key: str) -> int:
        bucket = _coerce_list_value(self._store, key)
        return len(bucket)

    def lindex(self, key: str, index: int):
        bucket = _coerce_list_value(self._store, key)
        if not bucket:
            return None
        idx = _list_normalized_index(len(bucket), index)
        if idx < 0 or idx >= len(bucket):
            return None
        return bucket[idx]

    def lrange(self, key: str, start: int, end: int) -> list[Any]:
        bucket = _coerce_list_value(self._store, key)
        return _list_range(bucket, start, end)

    def ltrim(self, key: str, start: int, end: int) -> bool:
        if key not in self._store:
            return True
        bucket = _coerce_list_value(self._store, key)
        self._store[key] = _list_range(bucket, start, end)
        return True

    def lrem(self, key: str, count: int, value: Any) -> int:
        bucket = _coerce_list_value(self._store, key)
        if not bucket:
            return 0

        removed = 0
        if count == 0:
            self._store[key] = [item for item in bucket if item != value]
            return len(bucket) - len(self._store[key])

        if count > 0:
            kept = []
            for item in bucket:
                if item == value and removed < count:
                    removed += 1
                    continue
                kept.append(item)
            self._store[key] = kept
            return removed

        target = abs(count)
        kept_reversed = []
        for item in reversed(bucket):
            if item == value and removed < target:
                removed += 1
                continue
            kept_reversed.append(item)
        self._store[key] = list(reversed(kept_reversed))
        return removed

    def scan(
        self,
        cursor: int = 0,
        match: Optional[str] = None,
        count: Optional[int] = None,
    ) -> tuple[int, list[str]]:
        keys = self.keys(match or "*")
        return 0, keys

    def ping(self) -> bool:
        return True

    def pipeline(self):
        return _NullRedisPipeline(self._store)

    def execute(self):
        return []

    def scan_iter(self, match: Optional[str] = None, count: Optional[int] = None):
        for key in list(self._store.keys()):
            if match is None or fnmatch.fnmatch(key, match):
                yield key

    def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        return 0

    def zcard(self, key: str) -> int:
        return 0

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        return 0

    def expire(self, key: str, seconds: int) -> bool:
        return True

    def close(self) -> None:
        return None

    def __getattr__(self, name: str):
        def _noop(*args, **kwargs):
            return None

        return _noop


class _NullAsyncRedis:
    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None, **kwargs):
        self._store[key] = value
        return True

    async def setex(self, key: str, seconds: int, value: Any):
        self._store[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return deleted

    async def exists(self, *keys: str) -> int:
        return sum(1 for key in keys if key in self._store)

    async def keys(self, pattern: str = "*") -> list[str]:
        return [key for key in self._store.keys() if fnmatch.fnmatch(key, pattern)]

    async def hset(
        self,
        key: str,
        field: Optional[str] = None,
        value: Any = None,
        mapping: Optional[dict[Any, Any]] = None,
    ) -> int:
        bucket = _get_hash_bucket(self._store, key)
        created = 0

        if mapping:
            for map_field, map_value in mapping.items():
                if map_field not in bucket:
                    created += 1
                bucket[map_field] = map_value
            return created

        if field is None:
            return 0

        if field not in bucket:
            created += 1
        bucket[field] = value
        return created

    async def hget(self, key: str, field: str):
        bucket = self._store.get(key)
        if not isinstance(bucket, dict):
            return None
        return bucket.get(field)

    async def hgetall(self, key: str) -> dict[Any, Any]:
        bucket = self._store.get(key)
        if not isinstance(bucket, dict):
            return {}
        return dict(bucket)

    async def hdel(self, key: str, *fields: str) -> int:
        bucket = self._store.get(key)
        if not isinstance(bucket, dict):
            return 0
        deleted = 0
        for field in fields:
            if field in bucket:
                del bucket[field]
                deleted += 1
        return deleted

    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        bucket = _get_hash_bucket(self._store, key)
        current = int(bucket.get(field, 0) or 0)
        current += amount
        bucket[field] = current
        return current

    async def rpush(self, key: str, *values: Any) -> int:
        bucket = _get_list_bucket(self._store, key)
        bucket.extend(values)
        return len(bucket)

    async def lpush(self, key: str, *values: Any) -> int:
        bucket = _get_list_bucket(self._store, key)
        for value in values:
            bucket.insert(0, value)
        return len(bucket)

    async def lpop(self, key: str):
        bucket = _coerce_list_value(self._store, key)
        if not bucket:
            return None
        return bucket.pop(0)

    async def llen(self, key: str) -> int:
        bucket = _coerce_list_value(self._store, key)
        return len(bucket)

    async def lindex(self, key: str, index: int):
        bucket = _coerce_list_value(self._store, key)
        if not bucket:
            return None
        idx = _list_normalized_index(len(bucket), index)
        if idx < 0 or idx >= len(bucket):
            return None
        return bucket[idx]

    async def lrange(self, key: str, start: int, end: int) -> list[Any]:
        bucket = _coerce_list_value(self._store, key)
        return _list_range(bucket, start, end)

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        if key not in self._store:
            return True
        bucket = _coerce_list_value(self._store, key)
        self._store[key] = _list_range(bucket, start, end)
        return True

    async def lrem(self, key: str, count: int, value: Any) -> int:
        bucket = _coerce_list_value(self._store, key)
        if not bucket:
            return 0

        removed = 0
        if count == 0:
            self._store[key] = [item for item in bucket if item != value]
            return len(bucket) - len(self._store[key])

        if count > 0:
            kept = []
            for item in bucket:
                if item == value and removed < count:
                    removed += 1
                    continue
                kept.append(item)
            self._store[key] = kept
            return removed

        target = abs(count)
        kept_reversed = []
        for item in reversed(bucket):
            if item == value and removed < target:
                removed += 1
                continue
            kept_reversed.append(item)
        self._store[key] = list(reversed(kept_reversed))
        return removed

    async def scan(
        self,
        cursor: int = 0,
        match: Optional[str] = None,
        count: Optional[int] = None,
    ) -> tuple[int, list[str]]:
        keys = await self.keys(match or "*")
        return 0, keys

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    def pipeline(self):
        return _NullAsyncRedisPipeline(self._store)

    async def execute(self):
        return []

    async def scan_iter(self, match: Optional[str] = None, count: Optional[int] = None):
        for key in list(self._store.keys()):
            if match is None or fnmatch.fnmatch(key, match):
                yield key

    def __getattr__(self, name: str):
        async def _noop(*args, **kwargs):
            return None

        return _noop


class _NullRedisManager:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._sync_client = _NullRedis()
        self._async_client = _NullAsyncRedis(self._sync_client._store)
        self._sessions: dict[str, dict[str, Any]] = {}
        self._users_by_id: dict[str, dict[str, Any]] = {}
        self._users_by_uid: dict[str, dict[str, Any]] = {}
        self.max_connections = 0

    def get_sync_client(self) -> _NullRedis:
        return self._sync_client

    async def get_async_client(self) -> _NullAsyncRedis:
        return self._async_client

    def get_compatible_client(self, preferred_type: str = "auto"):
        return self._sync_client

    async def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        session = self._sessions.get(str(session_id))
        return dict(session) if session else None

    async def create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        firebase_uid: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        ttl: Optional[int] = None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        payload = {
            "session_id": str(session_id),
            "user_id": str(user_id) if user_id is not None else None,
            "firebase_uid": firebase_uid,
            "ttl": ttl if ttl is not None else ttl_seconds,
        }
        if isinstance(metadata, dict):
            payload.update(metadata)
        self._sessions[str(session_id)] = payload
        return True

    async def invalidate_session(self, session_id: str) -> bool:
        return self._sessions.pop(str(session_id), None) is not None

    async def invalidate_all_user_sessions(self, identity: Optional[str]) -> int:
        if not identity:
            return 0
        identity = str(identity)
        to_delete = [
            session_id
            for session_id, payload in self._sessions.items()
            if str(payload.get("user_id") or "") == identity
            or str(payload.get("firebase_uid") or "") == identity
        ]
        for session_id in to_delete:
            self._sessions.pop(session_id, None)
        return len(to_delete)

    async def cache_user_data(self, firebase_uid: Optional[str], user_data: dict[str, Any], ttl: Optional[int] = None):
        if firebase_uid:
            self._users_by_uid[str(firebase_uid)] = dict(user_data)
        return True

    async def cache_user_data_by_user_id(self, user_id: Optional[str], user_data: dict[str, Any], ttl: Optional[int] = None):
        if user_id:
            self._users_by_id[str(user_id)] = dict(user_data)
        firebase_uid = user_data.get("firebase_uid")
        if firebase_uid:
            self._users_by_uid[str(firebase_uid)] = dict(user_data)
        return True

    async def get_user_by_id(self, user_id: str):
        user = self._users_by_id.get(str(user_id))
        return dict(user) if user else None

    async def get_user_by_uid(self, firebase_uid: str):
        user = self._users_by_uid.get(str(firebase_uid))
        return dict(user) if user else None

    async def update_session_activity(
        self,
        session_id: str,
        extend_ttl: bool = False,
        custom_ttl: Optional[int] = None,
    ) -> bool:
        payload = self._sessions.get(str(session_id))
        if not payload:
            return False
        if extend_ttl and custom_ttl is not None:
            payload["ttl"] = custom_ttl
        self._sessions[str(session_id)] = payload
        return True

    async def close_all(self) -> None:
        return None


def get_redis_manager(db_number: Optional[int] = None) -> "RedisManager":
    """
    Get or create global Redis manager instance.

    Args:
        db_number: Optional Redis DB number for isolation (0-15)

    Returns:
        RedisManager instance
    """
    global _redis_manager, _null_redis_manager
    if _should_disable_redis():
        if _null_redis_manager is None:
            _null_redis_manager = _NullRedisManager()
        return _null_redis_manager
    if db_number is None:
        if _redis_manager is None:
            from .manager import RedisManager

            _redis_manager = RedisManager()
        return _redis_manager
    else:
        # Create isolated manager for specific DB
        from .manager import RedisManager

        return RedisManager(db_number=db_number)


def get_cache_redis_manager() -> "RedisManager":
    """
    Get Redis manager for cache operations (DB 1 by default).

    Returns:
        RedisManager instance configured for cache
    """
    global _redis_cache_manager, _null_redis_manager
    if _should_disable_redis():
        if _null_redis_manager is None:
            _null_redis_manager = _NullRedisManager()
        return _null_redis_manager
    if _redis_cache_manager is None:
        if getattr(settings, "REDIS_ENABLE_CLUSTER_MODE", False):
            cache_db = 0
        else:
            cache_db = getattr(
                settings,
                "REDIS_CACHE_DB_NUMBER",
                getattr(settings, "REDIS_CACHE_DB", 1),
            )
        from .manager import RedisManager

        _redis_cache_manager = RedisManager(db_number=cache_db)
    return _redis_cache_manager


def get_broker_redis_manager() -> "RedisManager":
    """
    Get Redis manager for Celery broker operations (DB 0 by default).

    Note: Celery manages its own connections via CELERY_BROKER_URL.
    This is for direct broker inspection/management only.

    Returns:
        RedisManager instance configured for broker
    """
    global _redis_broker_manager, _null_redis_manager
    if _should_disable_redis():
        if _null_redis_manager is None:
            _null_redis_manager = _NullRedisManager()
        return _null_redis_manager
    if _redis_broker_manager is None:
        if getattr(settings, "REDIS_ENABLE_CLUSTER_MODE", False):
            broker_db = 0
        else:
            broker_db = getattr(
                settings,
                "REDIS_BROKER_DB_NUMBER",
                getattr(settings, "REDIS_BROKER_DB", 0),
            )
        from .manager import RedisManager

        _redis_broker_manager = RedisManager(db_number=broker_db)
    return _redis_broker_manager


async def _cleanup_managers():
    """Internal function to cleanup all global managers."""
    global _redis_manager, _redis_cache_manager, _redis_broker_manager

    if _redis_manager:
        await _redis_manager.close_all()
        _redis_manager = None

    if _redis_cache_manager:
        await _redis_cache_manager.close_all()
        _redis_cache_manager = None

    if _redis_broker_manager:
        await _redis_broker_manager.close_all()
        _redis_broker_manager = None
