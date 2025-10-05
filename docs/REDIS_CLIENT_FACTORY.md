# Redis Client Factory

## Overview

Centralized Redis client factory providing unified TLS/SSL configuration for both synchronous and asynchronous Redis clients.

## Problem Statement

**Issue**: Async Redis TLS connections were failing with certificate validation errors while sync connections worked fine.

**Root Cause**: Inconsistent SSL configuration between sync and async Redis clients, missing proper CA certificate chain validation, and lack of SNI (Server Name Indication) support.

**Solution**: Single factory with consistent SSL configuration using `certifi` CA bundle, proper certificate validation, and SNI support for cloud Redis instances.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  RedisClientFactory                         │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  _create_ssl_context()                                │ │
│  │  - Uses certifi CA bundle                             │ │
│  │  - Configures CERT_REQUIRED                           │ │
│  │  - Enables hostname checking (SNI)                    │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│           ┌──────────────┴──────────────┐                  │
│           │                             │                  │
│  ┌────────▼────────┐          ┌────────▼────────┐         │
│  │  Sync Client    │          │  Async Client   │         │
│  │  redis.Redis    │          │  redis_async    │         │
│  │                 │          │     .Redis      │         │
│  │  - ConnectionPool│          │  - ConnectionPool│        │
│  │  - SSL Context  │          │  - SSL Context  │         │
│  │  - Health Check │          │  - Health Check │         │
│  └─────────────────┘          └─────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## Features

### 🔐 Security

- **TLS/SSL Support**: Full certificate validation with proper CA chain
- **Certificate Validation**: Uses `certifi` for trusted CA certificates
- **SNI Support**: Server Name Indication for cloud Redis instances
- **Flexible Cert Requirements**: Support for `none`, `optional`, and `required` modes

### ⚡ Performance

- **Connection Pooling**: Reuses connections for efficiency
- **Client Caching**: Singleton pattern for default DB (DB 0)
- **Lazy Initialization**: Creates connections only when needed
- **Health Checks**: Built-in ping tests on client creation

### 🎯 Usability

- **Unified API**: Single entry point for both sync and async clients
- **Database Isolation**: Support for multiple Redis DBs (0-15)
- **Comprehensive Logging**: Detailed debug information for troubleshooting
- **Error Handling**: Graceful degradation with clear error messages

## Installation

### Requirements

```bash
# Core dependencies
pip install redis>=5.0.0
pip install redis[hiredis]  # Optional: faster parser

# SSL/TLS support
pip install certifi
```

### Configuration

Add to your `.env` file:

```bash
# Redis Connection
REDIS_URL=rediss://default:password@redis-cloud.com:14149
REDIS_PASSWORD=your-redis-password

# SSL/TLS Configuration
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required  # Options: none, optional, required

# Connection Pool Settings
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=10.0
REDIS_SOCKET_CONNECT_TIMEOUT=5.0
REDIS_RETRY_ON_TIMEOUT=true
REDIS_HEALTH_CHECK_INTERVAL=30
REDIS_DECODE_RESPONSES=true

# Database Isolation (optional)
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0
REDIS_SESSION_DB=2
REDIS_RATE_LIMIT_DB=3
```

## Usage

### Quick Start

```python
from app.core.redis_client_factory import get_redis_client, get_redis_client_async

# Sync client
redis = get_redis_client()
redis.set('key', 'value', ex=3600)
value = redis.get('key')

# Async client
async def example():
    redis = await get_redis_client_async()
    await redis.set('key', 'value', ex=3600)
    value = await redis.get('key')
```

### Database Isolation

```python
# Use different databases for different purposes
cache_redis = get_redis_client(db=1)        # Cache
broker_redis = get_redis_client(db=0)       # Celery
session_redis = get_redis_client(db=2)      # Sessions
ratelimit_redis = get_redis_client(db=3)    # Rate limiting
```

### Health Check

```python
from app.core.redis_client_factory import redis_health_check

# Check Redis health
health = await redis_health_check()
print(health)
# {
#   "status": "healthy",
#   "sync": {"connected": true, "error": null},
#   "async": {"connected": true, "error": null},
#   "ssl_enabled": true,
#   "redis_url": "rediss://..."
# }
```

### Application Lifecycle

```python
from fastapi import FastAPI
from app.core.redis_client_factory import cleanup_redis_connections

app = FastAPI()

@app.on_event("shutdown")
async def shutdown():
    """Clean up Redis connections."""
    await cleanup_redis_connections()
```

## API Reference

### `get_redis_client()`

Get synchronous Redis client.

**Parameters:**
- `db` (int): Redis database number (0-15), default: 0
- `decode_responses` (bool): Decode responses to strings, default: True

**Returns:** `redis.Redis`

**Example:**
```python
redis = get_redis_client(db=1, decode_responses=True)
```

### `get_redis_client_async()`

Get asynchronous Redis client.

**Parameters:**
- `db` (int): Redis database number (0-15), default: 0
- `decode_responses` (bool): Decode responses to strings, default: True

**Returns:** `redis.asyncio.Redis`

**Example:**
```python
redis = await get_redis_client_async(db=1, decode_responses=True)
```

### `redis_health_check()`

Perform health check on Redis connections.

**Returns:** `Dict[str, Any]` with status information

**Example:**
```python
health = await redis_health_check()
```

### `cleanup_redis_connections()`

Clean up all Redis connections.

**Example:**
```python
await cleanup_redis_connections()
```

## SSL/TLS Configuration Details

### Certificate Requirements

#### `CERT_REQUIRED` (Recommended for Production)

```bash
REDIS_SSL_CERT_REQS=required
```

- Full certificate validation
- Hostname checking enabled
- Uses certifi CA bundle
- **Recommended for production**

#### `CERT_OPTIONAL`

```bash
REDIS_SSL_CERT_REQS=optional
```

- Optional certificate validation
- Hostname checking disabled
- Use for testing with self-signed certificates

#### `CERT_NONE` (Insecure)

```bash
REDIS_SSL_CERT_REQS=none
```

- No certificate validation
- Hostname checking disabled
- **⚠️ INSECURE - Testing only!**

### SSL Context Configuration

The factory automatically configures SSL context based on settings:

```python
ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
ssl_context.check_hostname = True  # For CERT_REQUIRED
ssl_context.verify_mode = ssl.CERT_REQUIRED
ssl_context.load_verify_locations(cafile=certifi.where())
```

## Testing

### Run Validation Script

```bash
# From project root
python scripts/validate_redis_factory.py
```

### Unit Tests

```bash
# Run factory tests
pytest tests/unit/redis/test_redis_client_factory.py -v
```

### Manual Testing

```python
# Test sync client
from app.core.redis_client_factory import get_redis_client

redis = get_redis_client()
assert redis.ping() is True
redis.set('test', 'value', ex=60)
assert redis.get('test') == 'value'

# Test async client
from app.core.redis_client_factory import get_redis_client_async
import asyncio

async def test():
    redis = await get_redis_client_async()
    assert await redis.ping() is True
    await redis.set('test', 'value', ex=60)
    assert await redis.get('test') == 'value'

asyncio.run(test())
```

## Troubleshooting

### "Certificate verify failed"

**Cause**: Missing or outdated CA certificates

**Solution:**
```bash
pip install --upgrade certifi
```

### "Connection refused" or "Connection timeout"

**Cause**: Firewall, network, or Redis server issues

**Solution:**
1. Check `REDIS_URL` is correct
2. Verify Redis server is running
3. Check firewall rules
4. Increase timeout:
   ```bash
   REDIS_SOCKET_CONNECT_TIMEOUT=10.0
   ```

### "Too many connections"

**Cause**: Connection pool exhausted

**Solution:**
```bash
REDIS_MAX_CONNECTIONS=100
```

### Async works but sync fails (or vice versa)

**Cause**: Inconsistent SSL configuration (this should be fixed by the factory!)

**Solution:**
1. Ensure using the factory for both client types
2. Run validation script: `python scripts/validate_redis_factory.py`
3. Check logs for SSL configuration details

## Migration Guide

See [docs/redis_client_factory_migration.md](./redis_client_factory_migration.md) for detailed migration instructions.

## Performance Considerations

### Connection Pooling

- Default pool size: 50 connections
- Configurable via `REDIS_MAX_CONNECTIONS`
- Automatic connection health checks every 30 seconds

### Client Caching

- Default DB (0) client is cached and reused
- Other DBs create new instances
- Use `force_new=True` to bypass cache

### Best Practices

1. **Reuse clients**: Don't create new clients for every operation
2. **Use connection pooling**: Let the factory manage pools
3. **Database isolation**: Use different DBs for different purposes
4. **Health checks**: Monitor connection status regularly
5. **Cleanup**: Always call `cleanup_redis_connections()` on shutdown

## Security Best Practices

1. ✅ Always use `REDIS_SSL=true` in production
2. ✅ Set `REDIS_SSL_CERT_REQS=required` for full validation
3. ✅ Keep `certifi` package updated
4. ✅ Use strong Redis passwords
5. ✅ Enable Redis AUTH
6. ✅ Use Redis ACLs for fine-grained access control
7. ❌ Never use `CERT_NONE` in production
8. ❌ Never commit Redis passwords to git

## Monitoring

### Log Levels

The factory provides detailed logging at different levels:

- **INFO**: Connection status, SSL configuration
- **DEBUG**: Detailed SSL parameters, connection kwargs
- **WARNING**: certifi not found, SSL disabled
- **ERROR**: Connection failures, SSL errors

### Metrics

Track these metrics for monitoring:

- Connection success/failure rate
- SSL handshake time
- Ping latency
- Pool utilization
- Error rates by type (timeout, connection, SSL)

## Files

```
backend-hormonia/
├── app/
│   └── core/
│       └── redis_client_factory.py       # Main factory implementation
├── tests/
│   └── unit/
│       └── redis/
│           └── test_redis_client_factory.py  # Unit tests
├── scripts/
│   └── validate_redis_factory.py         # Validation script
└── docs/
    ├── REDIS_CLIENT_FACTORY.md          # This file
    └── redis_client_factory_migration.md  # Migration guide
```

## Support

For issues or questions:

1. Check logs for SSL/TLS configuration details
2. Run validation script: `python scripts/validate_redis_factory.py`
3. Verify environment variables are set correctly
4. Test manual connection: `python -c "from app.core.redis_client_factory import redis_health_check; import asyncio; print(asyncio.run(redis_health_check()))"`

## License

See project LICENSE file.

## Changelog

### Version 1.0.0 (2025-01-XX)

- ✅ Initial release
- ✅ Unified sync/async client creation
- ✅ Consistent SSL/TLS configuration
- ✅ certifi integration for CA certificates
- ✅ SNI support for cloud Redis
- ✅ Connection pooling and caching
- ✅ Comprehensive health checks
- ✅ Database isolation support
- ✅ Detailed logging and error handling
