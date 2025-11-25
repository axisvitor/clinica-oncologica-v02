# Redis Manager Package

Modular package structure for Redis client management.

## Structure

```
redis_manager/
├── __init__.py           # Main exports and package interface (58 lines)
├── manager.py            # RedisManager class - connection pooling (312 lines)
├── firebase_cache.py     # FirebaseRedisCache - 3-layer caching (350 lines)
├── session_cache.py      # Session management functionality (253 lines)
├── async_client.py       # Async Redis operations (96 lines)
├── sync_client.py        # Sync Redis operations and wrapper (225 lines)
└── utils.py              # Utility functions and globals (89 lines)
```

**Total:** 1,383 lines (original: 1,160 lines - includes proper documentation)

## Module Responsibilities

### `__init__.py` - Package Interface
- Re-exports all public APIs
- Single import point for all functionality
- Clear documentation of available exports

### `manager.py` - Core Manager
- `RedisManager` class
- Connection pooling (async and sync)
- SSL/TLS configuration
- Health checks and monitoring
- Resource cleanup

### `firebase_cache.py` - Firebase Caching
- `FirebaseRedisCache` class
- Layer 1: Token validation cache (1h TTL)
- Layer 2: User object cache (2h TTL)
- Layer 3: Session management (24h TTL)
- User creation and retrieval
- Cache statistics

### `session_cache.py` - Session Management
- `SessionCache` class
- `SessionCacheMixin` for FirebaseRedisCache
- Session creation and retrieval
- Session invalidation (single and global)
- Session listing and TTL management

### `async_client.py` - Async Operations
- `get_async_redis_client()` - Get async client
- `redis_transaction()` - Transaction context manager
- `cleanup_redis_connections()` - Cleanup function
- `redis_health_check()` - Health monitoring

### `sync_client.py` - Sync Operations
- `get_sync_redis_client()` - Get sync client
- `get_compatible_redis_client()` - Auto-detection
- `AsyncToSyncWrapper` - Compatibility layer
- Sync wrappers for all Redis operations

### `utils.py` - Utilities
- `get_redis_manager()` - Global manager instance
- `get_cache_redis_manager()` - Cache DB manager
- `get_broker_redis_manager()` - Broker DB manager
- Global instance management

## Usage

### Basic Import
```python
from app.core.redis_manager import (
    RedisManager,
    FirebaseRedisCache,
    get_redis_manager,
    get_async_redis_client,
    get_sync_redis_client
)
```

### Using Manager
```python
# Get default manager
manager = get_redis_manager()

# Get async client
async_client = await manager.get_async_client()

# Get sync client
sync_client = manager.get_sync_client()
```

### Using Firebase Cache
```python
# Initialize cache
cache = FirebaseRedisCache()

# Cache token (Layer 1)
cache.cache_validated_token(token, user_data)

# Cache user (Layer 2)
cache.cache_user(firebase_uid, user_dict)

# Create session (Layer 3)
await cache.create_session(session_id, user_id, firebase_uid)
```

### Transaction Example
```python
from app.core.redis_manager import redis_transaction

async with redis_transaction() as pipe:
    pipe.set('key1', 'value1')
    pipe.incr('counter')
    results = await pipe.execute()
```

## Benefits

1. **Modularity**: Each file has a single responsibility
2. **Maintainability**: Smaller files are easier to understand and modify
3. **Testability**: Each module can be tested independently
4. **Extensibility**: Easy to add new features without bloating files
5. **Documentation**: Clear separation of concerns with proper docstrings
6. **Backward Compatibility**: All existing imports continue to work

## Migration

The original `redis_manager.py` has been backed up to `redis_manager.py.bak`.

All existing code using:
```python
from app.core.redis_manager import ...
```

Will continue to work without any changes.

## Testing

Verify package integrity:
```bash
python3 -c "from app.core.redis_manager import *; print('OK')"
```

Test functionality:
```bash
python3 -c "
from app.core.redis_manager import get_redis_manager, FirebaseRedisCache
manager = get_redis_manager()
cache = FirebaseRedisCache()
print('✅ All imports successful')
"
```
