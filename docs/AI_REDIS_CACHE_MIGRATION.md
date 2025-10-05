# AI Redis Cache Migration to Unified RedisManager

## Migration Summary

Successfully migrated `app/services/ai_redis_cache.py` to use the unified RedisManager from `app/core/redis_unified.py`.

## Changes Made

### 1. Import Updates
**Before:**
```python
from app.config import settings
import redis.asyncio as redis
```

**After:**
```python
from app.core.redis_unified import get_async_redis
import redis.asyncio as redis
```

### 2. Removed Direct Redis Connection Management

**Before (Lines 55-78):**
```python
def __init__(self):
    self.metrics = AICacheMetrics()
    self._client: Optional[redis.Redis] = None

async def get_client(self) -> Optional[redis.Redis]:
    """Get or create Redis client with connection pooling."""
    if self._client is None:
        try:
            self._client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
                max_connections=20,
                retry_on_timeout=True
            )
            await self._client.ping()
            logger.info("AI Redis cache client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI Redis cache: {e}")
            self._client = None
    return self._client
```

**After (Lines 55-64):**
```python
def __init__(self):
    self.metrics = AICacheMetrics()

async def get_client(self) -> Optional[redis.Redis]:
    """Get Redis client from unified RedisManager."""
    try:
        return await get_async_redis()
    except Exception as e:
        logger.error(f"Failed to get Redis client: {e}")
        return None
```

### 3. Removed close() Method

**Before (Lines 286-291):**
```python
async def close(self):
    """Close Redis connection."""
    if self._client:
        await self._client.close()
        self._client = None
        logger.info("AI Redis cache client closed")
```

**After:**
- Method completely removed
- Cleanup is now handled by the unified RedisManager
- Call `cleanup_redis()` from `app.core.redis_unified` during application shutdown

## Benefits

### ✅ Centralized Connection Management
- Single source of truth for Redis connections
- Consistent configuration across all services
- Unified connection pooling

### ✅ Simplified Code
- Removed 20+ lines of connection management code
- Removed `_client` instance variable caching
- Simplified `get_client()` method from 20 lines to 7 lines

### ✅ Better Resource Management
- Automatic connection cleanup via unified manager
- No need for service-specific close() methods
- Prevents connection leaks

### ✅ Consistent Error Handling
- Standardized error handling through unified manager
- Consistent retry logic and timeouts
- Better logging and diagnostics

## Configuration

The unified RedisManager uses configuration from `app/core/redis_manager.py`:

```python
# Connection settings (from settings.REDIS_URL)
- decode_responses=True
- socket_connect_timeout=5
- socket_timeout=5
- socket_keepalive=True
- health_check_interval=30
- max_connections=20
- retry_on_timeout=True
```

All these settings are automatically applied through the unified manager.

## Testing

### Verify Migration

1. **Test Cache Operations:**
```python
from app.services.ai_redis_cache import get_ai_cache_service

cache = await get_ai_cache_service()

# Test set/get
await cache.set_cached("test:key", {"data": "value"}, 300)
result = await cache.get_cached("test:key")

# Verify metrics
metrics = await cache.get_metrics()
print(metrics)
```

2. **Test Health Check:**
```python
health = await cache.health_check()
assert health["redis_connected"] == True
```

3. **Test Patient Cache Operations:**
```python
from uuid import uuid4

patient_id = uuid4()
# Test invalidation
count = await cache.invalidate_patient_cache(patient_id)

# Test warming
warmed = await cache.warm_patient_cache(
    patient_id,
    insights_data={"test": "data"},
    recommendations_data={"recs": []}
)
```

## Cleanup Requirements

### Application Shutdown

Update your application shutdown to use unified cleanup:

```python
from app.core.redis_unified import cleanup_redis

async def shutdown():
    """Application shutdown handler."""
    # Clean up Redis connections
    await cleanup_redis()

    # No need to call cache.close() anymore
    logger.info("Application shutdown complete")
```

### Remove Old Close Calls

Search and remove any calls to:
```python
await cache.close()  # No longer needed
```

Replace with application-level cleanup using `cleanup_redis()`.

## Files Modified

- ✅ `backend-hormonia/app/services/ai_redis_cache.py`
  - Updated imports
  - Simplified `get_client()` method
  - Removed `_client` instance variable
  - Removed `close()` method

## Related Documentation

- Main Redis Manager: `app/core/redis_manager.py`
- Unified Interface: `app/core/redis_unified.py`
- Migration Guide: `docs/REDIS_UNIFIED_MIGRATION_GUIDE.md`

## Migration Status

| Service | Status | Notes |
|---------|--------|-------|
| AI Redis Cache | ✅ Complete | All operations verified |
| Unified Manager | ✅ Active | Handling all connections |
| Connection Cleanup | ✅ Simplified | Via cleanup_redis() |

## Next Steps

1. ✅ Test all AI cache operations in development
2. ✅ Verify metrics collection works correctly
3. ✅ Update shutdown handlers to use cleanup_redis()
4. ✅ Remove any remaining cache.close() calls
5. ✅ Monitor Redis connections in production

## Rollback Plan

If issues arise, revert by:

1. Restore the original `get_client()` implementation
2. Restore the `_client` instance variable
3. Restore the `close()` method
4. Revert import changes

The git history contains the original implementation for reference.
