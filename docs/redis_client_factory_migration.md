# Redis Client Factory Migration Guide

## Overview

The new `redis_client_factory.py` provides a centralized, consistent way to create Redis clients with proper TLS/SSL configuration. This fixes the async Redis TLS certificate validation issues while maintaining backward compatibility.

## Why Migrate?

### Problems Solved

1. **Async Redis TLS Failures**: The factory uses consistent SSL configuration for both sync and async clients, fixing certificate validation errors
2. **Inconsistent SSL Configuration**: Single source of truth for TLS parameters (certifi CA bundle, SNI support, etc.)
3. **Scattered Redis Imports**: Unified import location instead of multiple client implementations
4. **Poor Error Handling**: Comprehensive logging and graceful degradation
5. **No Health Checks**: Built-in health checking for both client types

### Key Benefits

- ✅ **Consistent TLS**: Same SSL context for sync and async clients
- ✅ **Proper CA Chain**: Uses `certifi.where()` for certificate validation
- ✅ **SNI Support**: Server Name Indication for cloud Redis instances
- ✅ **Connection Pooling**: Efficient resource management
- ✅ **Health Checks**: Built-in ping tests on client creation
- ✅ **Detailed Logging**: Comprehensive debug information

## Migration Steps

### 1. Update Imports

#### Before (Multiple Import Styles)
```python
# Old scattered imports
from app.core.redis_manager import get_sync_redis_client
from app.core.redis_unified import get_async_redis
from app.utils.redis_client import get_redis_client
```

#### After (Unified Factory)
```python
# New unified factory
from app.core.redis_client_factory import get_redis_client, get_redis_client_async
```

### 2. Update Sync Client Usage

#### Before
```python
from app.core.redis_manager import get_sync_redis_client

# Get sync client
redis = get_sync_redis_client()
redis.set('key', 'value', ex=3600)
```

#### After
```python
from app.core.redis_client_factory import get_redis_client

# Get sync client (default)
redis = get_redis_client()
redis.set('key', 'value', ex=3600)

# Or explicitly specify sync
redis = get_redis_client(async_mode=False)
```

### 3. Update Async Client Usage

#### Before
```python
from app.core.redis_manager import get_async_redis_client
import redis.asyncio as redis

# Get async client
redis = await get_async_redis_client()
await redis.set('key', 'value', ex=3600)
```

#### After
```python
from app.core.redis_client_factory import get_redis_client_async

# Get async client
redis = await get_redis_client_async()
await redis.set('key', 'value', ex=3600)
```

### 4. Update Session Manager

#### Before (`app/core/session_manager.py`)
```python
import redis.asyncio as redis
from app.config import settings

# Manual connection creation
_request_redis: ContextVar[Optional[redis.Redis]] = ContextVar(
    'request_redis',
    default=None
)

# Somewhere else in the code
redis_client = redis.from_url(settings.REDIS_URL)
```

#### After
```python
from app.core.redis_client_factory import get_redis_client_async

# Use factory
async def get_request_redis():
    """Get or create Redis client for this request."""
    existing = _request_redis.get()
    if existing:
        return existing

    # Create using factory (ensures proper TLS)
    client = await get_redis_client_async()
    _request_redis.set(client)
    return client
```

### 5. Update WebSocket Support

#### Before (`app/api/enhanced_websockets.py`)
```python
import redis.asyncio as redis
from app.config import settings

# Manual connection
self.redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)
```

#### After
```python
from app.core.redis_client_factory import get_redis_client_async

# Use factory
self.redis_client = await get_redis_client_async(
    decode_responses=True
)
```

### 6. Update AI Cache Service

#### Before (`app/services/ai_cache_service.py`)
```python
import redis.asyncio as redis

redis_config = get_performance_config().get_redis_config()
self.redis_client = redis.from_url(**redis_config)
```

#### After
```python
from app.core.redis_client_factory import get_redis_client_async

# Use factory (automatically handles SSL/TLS)
self.redis_client = await get_redis_client_async(
    db=1,  # Use separate DB for cache if needed
    decode_responses=True
)
```

### 7. Update Monitoring Services

#### Before (`app/monitoring/*.py`)
```python
from redis import Redis
from app.config import settings

redis_client = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=settings.MONITORING_REDIS_DB
)
```

#### After
```python
from app.core.redis_client_factory import get_redis_client

# Use factory with specific DB
redis_client = get_redis_client(
    db=settings.MONITORING_REDIS_DB,
    decode_responses=True
)
```

## Database Isolation

The factory supports Redis database isolation for different use cases:

```python
from app.core.redis_client_factory import get_redis_client

# Cache (DB 1)
cache_redis = get_redis_client(db=1)

# Celery broker (DB 0)
broker_redis = get_redis_client(db=0)

# Sessions (DB 2)
session_redis = get_redis_client(db=2)

# Rate limiting (DB 3)
ratelimit_redis = get_redis_client(db=3)
```

## Health Check Integration

### Add to Health Check Endpoint

```python
from app.core.redis_client_factory import redis_health_check

@router.get("/health/redis")
async def redis_health():
    """Check Redis connection health."""
    return await redis_health_check()
```

### Example Response

```json
{
  "status": "healthy",
  "sync": {
    "connected": true,
    "error": null
  },
  "async": {
    "connected": true,
    "error": null
  },
  "ssl_enabled": true,
  "redis_url": "rediss://redis-cloud.com:14149"
}
```

## Error Handling

The factory provides comprehensive error handling:

```python
from app.core.redis_client_factory import get_redis_client
from redis.exceptions import ConnectionError, TimeoutError

try:
    redis = get_redis_client()
    redis.set('key', 'value')
except ConnectionError as e:
    logger.error(f"Redis connection failed: {e}")
    # Fallback to in-memory cache or degraded mode
except TimeoutError as e:
    logger.error(f"Redis operation timed out: {e}")
    # Retry or use fallback
```

## Environment Variables

### Required Settings

Make sure your `.env` has these Redis configuration variables:

```bash
# Redis Connection
REDIS_URL=rediss://default:password@redis-cloud.com:14149
REDIS_PASSWORD=your-redis-password

# SSL/TLS Configuration
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required  # Options: none, optional, required

# Connection Pool
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=10.0
REDIS_SOCKET_CONNECT_TIMEOUT=5.0
REDIS_RETRY_ON_TIMEOUT=true
REDIS_HEALTH_CHECK_INTERVAL=30

# Decode Responses
REDIS_DECODE_RESPONSES=true
```

### SSL Certificate Requirements

- `none`: No certificate validation (⚠️ INSECURE, testing only)
- `optional`: Optional certificate validation
- `required`: Full certificate validation with CA chain (✅ RECOMMENDED)

## Testing

### Unit Tests

```python
import pytest
from app.core.redis_client_factory import get_redis_client, get_redis_client_async

def test_sync_redis_connection():
    """Test sync Redis client."""
    redis = get_redis_client()
    assert redis.ping() is True

@pytest.mark.asyncio
async def test_async_redis_connection():
    """Test async Redis client."""
    redis = await get_redis_client_async()
    assert await redis.ping() is True
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_redis_ssl_connection():
    """Test that SSL connection works for both sync and async."""
    from app.core.redis_client_factory import redis_health_check

    health = await redis_health_check()

    assert health["status"] == "healthy"
    assert health["sync"]["connected"] is True
    assert health["async"]["connected"] is True
    assert health["ssl_enabled"] is True
```

## Cleanup

### Application Shutdown

Add cleanup to your application lifecycle:

```python
from app.core.redis_client_factory import cleanup_redis_connections

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up Redis connections on shutdown."""
    await cleanup_redis_connections()
    logger.info("Redis connections cleaned up")
```

## Troubleshooting

### Issue: "Certificate verify failed"

**Solution**: Ensure you have `certifi` installed and `REDIS_SSL_CERT_REQS=required`

```bash
pip install certifi
```

### Issue: "Async Redis connection fails but sync works"

**Solution**: This is exactly what the factory fixes. Both clients now use the same SSL configuration.

### Issue: "Connection timeout"

**Solution**: Check your firewall/network settings and increase timeouts:

```bash
REDIS_SOCKET_CONNECT_TIMEOUT=10.0
REDIS_SOCKET_TIMEOUT=15.0
```

### Issue: "Too many connections"

**Solution**: Adjust pool size:

```bash
REDIS_MAX_CONNECTIONS=100
```

## Rollback Plan

If you need to rollback to the old implementation:

1. Keep `redis_manager.py` as fallback
2. Update imports back to original modules
3. Ensure `REDIS_SSL` environment variable is correctly configured

## Performance Impact

The factory has minimal performance overhead:

- ✅ Connection pooling (same as before)
- ✅ Client caching (reuses instances)
- ✅ Lazy initialization (creates on first use)
- ⚠️ SSL context creation (one-time cost per client type)

## Next Steps

1. ✅ Install certifi: `pip install certifi`
2. ✅ Update environment variables
3. ✅ Migrate imports in key files:
   - `app/core/session_manager.py`
   - `app/api/enhanced_websockets.py`
   - `app/services/ai_cache_service.py`
   - `app/monitoring/*.py`
4. ✅ Add health check endpoint
5. ✅ Run tests to verify SSL connections
6. ✅ Add cleanup to shutdown event
7. ✅ Monitor logs for SSL-related errors

## Support

For issues or questions:

1. Check logs for detailed SSL configuration information
2. Run health check: `/health/redis`
3. Verify certifi is installed: `python -c "import certifi; print(certifi.where())"`
4. Test connection manually:
   ```python
   from app.core.redis_client_factory import redis_health_check
   import asyncio

   result = asyncio.run(redis_health_check())
   print(result)
   ```

## References

- [redis-py Documentation](https://redis-py.readthedocs.io/)
- [Redis TLS/SSL](https://redis.io/docs/management/security/encryption/)
- [certifi Package](https://github.com/certifi/python-certifi)
- [Python SSL Module](https://docs.python.org/3/library/ssl.html)
