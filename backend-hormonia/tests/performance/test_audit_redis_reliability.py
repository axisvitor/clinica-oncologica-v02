import pytest
import asyncio
import threading
from app.core.redis_manager import get_redis_manager, RedisManager
from unittest.mock import patch, MagicMock

@pytest.mark.performance
class TestRedisReliabilityAudit:
    """
    Audit verification tests for Redis Manager reliability and pooling.
    """

    @pytest.mark.asyncio
    async def test_async_client_lifecycle(self):
        """Verify that async Redis client can be created, used, and closed."""
        manager = RedisManager()
        try:
            client = await manager.get_async_client()
            await client.set("test_key", "test_value", ex=10)
            value = await client.get("test_key")
            assert value == "test_value"
        finally:
            await manager.close_all()

    def test_sync_client_lifecycle(self):
        """Verify that sync Redis client can be created, used, and closed."""
        manager = RedisManager()
        try:
            client = manager.get_sync_client()
            client.set("test_sync_key", "sync_val", ex=10)
            assert client.get("test_sync_key") == "sync_val"
        finally:
            manager.close_sync()

    def test_multithreaded_sync_access(self):
        """Verify thread-safety of the sync Redis client."""
        manager = RedisManager()
        client = manager.get_sync_client()
        
        def worker(i):
            key = f"thread_key_{i}"
            client.set(key, i, ex=5)
            val = client.get(key)
            assert int(val) == i
            
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        manager.close_sync()

    def test_client_compatibility_detection_sync(self):
        """Verify automatic client type detection in sync context."""
        manager = RedisManager()
        try:
            # In sync context, auto should return sync client or wrapper that works
            client = manager.get_compatible_client("auto")
            assert client is not None
            
            client.set("compat_key_sync", "compat_val", ex=5)
            assert client.get("compat_key_sync") == "compat_val"
        finally:
            manager.close_sync()
            
    @pytest.mark.asyncio
    async def test_concurrent_async_access(self):
        """Verify connection pool stability under concurrent async load."""
        manager = RedisManager()
        try:
            client = await manager.get_async_client()
            
            async def worker(i):
                key = f"concurrent_key_{i}"
                await client.set(key, i, ex=5)
                val = await client.get(key)
                assert int(val) == i
                
            tasks = [worker(i) for i in range(10)]
            await asyncio.gather(*tasks)
        finally:
            await manager.close_all()
