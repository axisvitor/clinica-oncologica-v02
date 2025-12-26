# Cache Invalidation Service

Centralized cache invalidation service with retry logic, pattern matching, and multi-backend support.

## Overview

The `CacheInvalidationService` provides a unified interface for invalidating cache entries across different backends (Redis, local memory) with built-in retry logic, detailed logging, and multiple invalidation strategies.

## Architecture

```
app/services/cache/
├── __init__.py                  # Package exports
├── invalidation_service.py      # Core invalidation service
├── key_builder.py              # Consistent key generation
└── examples.py                 # Usage examples
```

## Key Components

### 1. CacheInvalidationService

Core service providing invalidation capabilities:

- **Multiple Strategies**: Single key, pattern matching, tag-based, cascade
- **Retry Logic**: Exponential backoff with configurable retries
- **Multi-Backend**: Redis primary with local cache fallback
- **Metrics**: Track invalidations, retries, failures, fallbacks
- **Logging**: Detailed logging at all levels

### 2. CacheKeyBuilder

Utility for building consistent cache keys:

- **Namespacing**: Environment-specific key prefixes
- **Versioning**: Cache version management
- **Parameter Hashing**: Deterministic query parameter hashing
- **Pattern Generation**: Wildcard patterns for bulk operations
- **Key Parsing**: Extract components from existing keys

### 3. InvalidationStrategy (Enum)

```python
class InvalidationStrategy(str, Enum):
    SINGLE = "single"      # Invalidate one key
    PATTERN = "pattern"    # Wildcard pattern matching
    TAGS = "tags"         # Tag-based invalidation
    CASCADE = "cascade"   # Key + related keys
```

## Usage

### Basic Setup

```python
from app.services.cache import (
    CacheInvalidationService,
    CacheKeyBuilder,
    InvalidationStrategy,
)

# Initialize service
service = CacheInvalidationService(
    redis_client=redis_client,  # Optional
    key_builder=CacheKeyBuilder(namespace="hormonia", version="v1"),
    max_retries=3,
    retry_delay=0.1,
    retry_backoff=2.0,
)
```

### 1. Single Key Invalidation

```python
# Build key
key_builder = CacheKeyBuilder()
key = key_builder.build("patient", patient_id)

# Invalidate
await service.invalidate(
    key=key,
    strategy=InvalidationStrategy.SINGLE,
)
```

### 2. Pattern-Based Invalidation

```python
# Invalidate all patient lists
pattern = key_builder.build_pattern("patient", operation="list")

await service.invalidate(
    pattern=pattern,
    strategy=InvalidationStrategy.PATTERN,
)
```

### 3. Tag-Based Invalidation

```python
# Tag a key
await service.tag_key(
    key="patient:123",
    tags=["patient", "active", "oncology"],
)

# Invalidate by tag
await service.invalidate(
    tags=["active"],
    strategy=InvalidationStrategy.TAGS,
)
```

### 4. Entity-Level Invalidation (Recommended)

```python
# High-level entity invalidation
# Automatically invalidates:
# - patient:123
# - patient:list:*
# - patient:count:*
# - patient:search:*

await service.invalidate_entity(
    entity="patient",
    identifier="123",
    cascade=True,
)
```

### 5. Cascade Invalidation

```python
# Invalidate key and all related patterns
await service.invalidate(
    key=key,
    strategy=InvalidationStrategy.CASCADE,
)
```

## Integration with Services

### PatientCRUDService Example

```python
class PatientCRUDService:
    def __init__(self, db, cache_invalidation_service=None):
        self.db = db
        self._cache_invalidation = cache_invalidation_service or CacheInvalidationService(
            key_builder=CacheKeyBuilder(namespace="hormonia", version="v1"),
            max_retries=3,
        )

    def update_patient(self, patient_id: UUID, patient_data: PatientUpdate) -> Patient:
        # 1. Update in database
        with sync_transaction(self.db) as session:
            updated_patient = self.repository.update(patient, update_dict)

        # 2. Invalidate caches (best-effort, after commit)
        try:
            import asyncio
            asyncio.run(self._cache_invalidation.invalidate_entity(
                entity="patient",
                identifier=str(patient_id),
                cascade=True,
            ))
        except Exception as e:
            self._logger.warning(f"Cache invalidation failed: {e}")

        return updated_patient
```

## Key Building Patterns

### Simple Keys

```python
key_builder = CacheKeyBuilder(namespace="hormonia", version="v1")

# Entity by ID
key = key_builder.build("patient", "123")
# Result: "hormonia:v1:patient:123"

# List operation
key = key_builder.build("patient", operation="list")
# Result: "hormonia:v1:patient:list"
```

### Complex Keys with Parameters

```python
# Query with filters
params = {
    "status": "active",
    "treatment_type": "oncology",
    "page": 1,
}

key = key_builder.build(
    entity="patient",
    operation="list",
    params=params,
)
# Result: "hormonia:v1:patient:list:abc12345"
# (hash is deterministic for same params)
```

### Pattern Matching

```python
# All patient keys
pattern = key_builder.build_pattern("patient")
# Result: "hormonia:v1:patient:*"

# Specific patient, all operations
pattern = key_builder.build_pattern("patient", "123")
# Result: "hormonia:v1:patient:123:*"

# All list operations
pattern = key_builder.build_pattern("patient", operation="list")
# Result: "hormonia:v1:patient:list:*"
```

## Features

### Retry Logic

```python
# Configured with exponential backoff
service = CacheInvalidationService(
    max_retries=3,        # Maximum retry attempts
    retry_delay=0.1,      # Initial delay (seconds)
    retry_backoff=2.0,    # Multiplier for each retry
)

# Retry sequence: 0.1s, 0.2s, 0.4s
```

### Automatic Fallback

```python
# If Redis fails, automatically falls back to local cache
service = CacheInvalidationService(redis_client=None)

# Metrics track fallbacks
metrics = await service.get_metrics()
print(metrics["fallbacks"])  # Number of fallback operations
```

### Metrics and Monitoring

```python
metrics = await service.get_metrics()

# Returns:
{
    "invalidations": 42,     # Total operations
    "retries": 3,           # Number of retries
    "failures": 1,          # Failed operations
    "fallbacks": 2,         # Fallback to local cache
    "timestamp": "2025-12-23T20:00:00",
    "backend": "redis",     # or "local"
}
```

## Best Practices

### 1. Use Entity-Level Invalidation

```python
# ✅ GOOD: High-level, comprehensive
await service.invalidate_entity("patient", patient_id, cascade=True)

# ❌ AVOID: Manual, error-prone
await service.invalidate(key=f"patient:{patient_id}")
await service.invalidate(pattern=f"patient:list:*")
await service.invalidate(pattern=f"patient:count:*")
```

### 2. Invalidate After Database Commit

```python
# ✅ GOOD: Cache invalidation after DB commit
with sync_transaction(self.db) as session:
    updated_patient = self.repository.update(patient, data)
    # Transaction commits here

# Now invalidate cache (best-effort)
try:
    await service.invalidate_entity("patient", patient_id)
except Exception as e:
    logger.warning(f"Cache invalidation failed: {e}")

# ❌ AVOID: Invalidation inside transaction
with sync_transaction(self.db) as session:
    await service.invalidate_entity("patient", patient_id)
    updated_patient = self.repository.update(patient, data)
```

### 3. Use Tags for Related Entities

```python
# Tag related entities
await service.tag_key("patient:123", ["oncology", "active", "2025"])
await service.tag_key("quiz:456", ["oncology", "active", "2025"])

# Invalidate all oncology-related data
await service.invalidate(tags=["oncology"], strategy=InvalidationStrategy.TAGS)
```

### 4. Consistent Key Namespacing

```python
# Use environment-specific namespaces
prod_builder = CacheKeyBuilder(namespace="prod", version="v1")
staging_builder = CacheKeyBuilder(namespace="staging", version="v1")

# Keys won't conflict across environments
```

### 5. Handle Failures Gracefully

```python
# Cache invalidation is best-effort
try:
    await service.invalidate_entity("patient", patient_id)
except Exception as e:
    # Log but don't fail the operation
    logger.warning(f"Cache invalidation failed: {e}")
    # Application continues normally
```

## Performance Considerations

### Batch Operations

```python
# ✅ GOOD: Use patterns for bulk operations
pattern = key_builder.build_pattern("patient", operation="list")
await service.invalidate(pattern=pattern, strategy=InvalidationStrategy.PATTERN)

# ❌ AVOID: Individual invalidations in loop
for patient_id in patient_ids:
    await service.invalidate(key=f"patient:{patient_id}")
```

### Redis vs Local Cache

| Feature | Redis | Local Cache |
|---------|-------|-------------|
| Speed | Network latency | In-memory (fastest) |
| Persistence | Yes | No (process-bound) |
| Distributed | Yes | No |
| Pattern matching | Native SCAN | Python regex |
| Recommended for | Production | Development/Testing |

## Error Handling

### Automatic Retries

```python
# Service automatically retries on transient errors
# Logs each attempt with delay information

# Example log output:
# WARNING: Retrying cache invalidation (attempt 1, delay 0.1s)
# WARNING: Retrying cache invalidation (attempt 2, delay 0.2s)
# ERROR: Cache invalidation failed after 3 retries
```

### Fallback Behavior

```python
# If Redis fails completely, falls back to local cache
# Metrics track this for monitoring

if metrics["fallbacks"] > threshold:
    alert("Redis may be down, check connection")
```

## Testing

### Unit Tests

```python
import pytest
from app.services.cache import CacheInvalidationService, CacheKeyBuilder

@pytest.mark.asyncio
async def test_entity_invalidation():
    service = CacheInvalidationService()

    success = await service.invalidate_entity(
        entity="patient",
        identifier="123",
        cascade=True,
    )

    assert success is True
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_redis_invalidation(redis_client):
    service = CacheInvalidationService(redis_client=redis_client)

    # Set value
    redis_client.set("test:key", "value")

    # Invalidate
    await service.invalidate(key="test:key", strategy=InvalidationStrategy.SINGLE)

    # Verify
    assert redis_client.get("test:key") is None
```

## Migration Guide

### From Legacy Cache Functions

```python
# OLD
from app.infrastructure.cache import invalidate_patient_cache
invalidate_patient_cache(patient_id)

# NEW
from app.services.cache import CacheInvalidationService
service = CacheInvalidationService()
await service.invalidate_entity("patient", patient_id, cascade=True)
```

### From Manual Pattern Invalidation

```python
# OLD
cache_manager.invalidate_pattern(f"patient:*:{patient_id}*")
cache_manager.invalidate_pattern(f"patient:list:*")

# NEW
await service.invalidate_entity("patient", patient_id, cascade=True)
```

## Configuration

### Environment Variables

```bash
# Redis configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Cache configuration
CACHE_NAMESPACE=hormonia
CACHE_VERSION=v1
CACHE_MAX_RETRIES=3
CACHE_RETRY_DELAY=0.1
```

### Application Setup

```python
from app.services.cache import CacheInvalidationService, CacheKeyBuilder

# Global service instance
cache_invalidation_service = CacheInvalidationService(
    redis_client=redis_client,
    key_builder=CacheKeyBuilder(
        namespace=settings.CACHE_NAMESPACE,
        version=settings.CACHE_VERSION,
    ),
    max_retries=settings.CACHE_MAX_RETRIES,
    retry_delay=settings.CACHE_RETRY_DELAY,
)
```

## API Reference

### CacheInvalidationService

#### `__init__(redis_client, key_builder, max_retries, retry_delay, retry_backoff)`

Initialize the service.

#### `invalidate(key, pattern, tags, strategy, cascade) -> bool`

Invalidate cache entries based on strategy.

#### `invalidate_entity(entity, identifier, cascade) -> bool`

High-level entity invalidation (recommended).

#### `tag_key(key, tags) -> bool`

Associate tags with a cache key.

#### `get_metrics() -> dict`

Get invalidation metrics.

#### `clear_all(confirm) -> bool`

Clear all cache entries (dangerous).

### CacheKeyBuilder

#### `__init__(namespace, version)`

Initialize the key builder.

#### `build(entity, identifier, operation, params) -> str`

Build a cache key.

#### `build_pattern(entity, identifier, operation) -> str`

Build a wildcard pattern.

#### `build_tag_key(tag) -> str`

Build a tag set key.

#### `parse(key) -> dict`

Parse a cache key into components.

#### `get_entity_patterns(entity) -> List[str]`

Get common invalidation patterns for an entity.

## See Also

- [Cache Strategy Documentation](./CACHE_STRATEGY.md)
- [Redis Configuration](./REDIS_CONFIG.md)
- [Performance Optimization](./PERFORMANCE.md)
