# ADR-0003: Redis for Caching and Rate Limiting

## Status

Accepted

Date: 2024-01-17

## Context

The Clínica Hormonia system requires:
- **Performance**: Fast responses for frequently accessed data (patient lists, quiz templates)
- **Rate limiting**: Protect API from abuse and WhatsApp webhook flooding
- **Session management**: Distributed session storage for horizontal scaling
- **Background tasks**: Celery task queue and result backend
- **Real-time features**: WebSocket connection tracking and pub/sub messaging
- **Scalability**: Multiple backend instances behind load balancer

Specific requirements:
- Quiz templates accessed by multiple patients simultaneously
- API rate limits per IP and per user
- WhatsApp webhook deduplication
- Session data accessible across instances
- Celery task coordination across workers

## Decision

We will use **Redis 7+** as the primary caching layer, rate limiting store, session backend, and Celery broker/result backend.

Key uses:
1. **Application cache**: Frequently accessed read-only data (30-min to 24-hour TTL)
2. **Rate limiting**: Token bucket algorithm with sliding windows
3. **Session store**: User sessions with automatic expiration
4. **Celery broker**: Task queue for background jobs
5. **Celery results**: Task result storage with TTL
6. **WebSocket tracking**: Active connection registry
7. **Idempotency keys**: Prevent duplicate webhook processing
8. **Pub/Sub**: Real-time notifications across instances

## Consequences

### Positive Consequences

- **Performance**: 10-100x faster than PostgreSQL for cached data
- **Horizontal scaling**: Stateless backend instances
- **Rate limiting**: Built-in atomic operations for accurate limits
- **Reliability**: Celery tasks distributed across workers
- **Real-time**: Pub/Sub for WebSocket broadcasting
- **Simplicity**: Single technology for multiple use cases
- **Memory efficiency**: Automatic key expiration (TTL)
- **Observability**: Rich monitoring and metrics

### Negative Consequences

- **Data volatility**: Cache can be cleared/lost (need fallback to PostgreSQL)
- **Memory limits**: Need to monitor and plan capacity
- **Complexity**: Another service to maintain and monitor
- **Consistency**: Potential cache invalidation challenges
- **Cost**: Additional infrastructure cost

### Risks

- **Memory exhaustion**: Unbounded cache growth could crash Redis
- **Single point of failure**: Need Redis Sentinel or Cluster for HA
- **Cache stampede**: Multiple simultaneous cache misses could overwhelm database
- **Eviction issues**: Wrong eviction policy could remove important data
- **Security**: Need TLS and authentication for production

## Alternatives Considered

### Alternative 1: Memcached

**Description**: Traditional distributed caching system

**Pros**:
- Simple and fast
- Multi-threaded (better CPU utilization)
- Lower memory overhead per key

**Cons**:
- No persistence
- No pub/sub support
- No data structures (lists, sets, sorted sets)
- Cannot be used as Celery broker
- Less feature-rich than Redis

**Why rejected**: Lack of pub/sub, data structures, and Celery support

### Alternative 2: PostgreSQL for Everything

**Description**: Use PostgreSQL for caching and sessions

**Pros**:
- No additional infrastructure
- ACID guarantees
- Persistent storage
- Team already knows it

**Cons**:
- 10-100x slower than Redis
- Adds load to primary database
- Poor performance for rate limiting
- Not designed for volatile data
- No pub/sub capabilities

**Why rejected**: Performance requirements need in-memory store

### Alternative 3: Application-Level Cache (Python dict)

**Description**: In-process caching with LRU dict

**Pros**:
- No external dependencies
- Extremely fast (no network)
- Zero infrastructure cost

**Cons**:
- Not shared across instances
- Lost on restart
- No eviction control
- Memory leaks possible
- Cannot scale horizontally

**Why rejected**: Doesn't support horizontal scaling or distributed sessions

### Alternative 4: DynamoDB

**Description**: AWS managed NoSQL database

**Pros**:
- Fully managed
- Auto-scaling
- Low operational overhead

**Cons**:
- Much slower than Redis (10-50ms vs <1ms)
- Higher cost for high throughput
- Vendor lock-in to AWS
- No pub/sub
- Cannot be Celery broker
- Overkill for caching

**Why rejected**: Too slow for caching use case and not cost-effective

## Implementation Notes

### Cache Strategy

```python
# Cache with automatic fallback
@cache_with_fallback(ttl=1800, key_prefix="patient_list")
async def get_patient_list(physician_id: str):
    # Try cache first
    cached = await redis.get(f"patient_list:{physician_id}")
    if cached:
        return json.loads(cached)

    # Fallback to database
    patients = await db.query(Patient).filter_by(physician_id=physician_id).all()

    # Store in cache
    await redis.setex(
        f"patient_list:{physician_id}",
        1800,
        json.dumps(patients)
    )
    return patients
```

### Rate Limiting

```python
# Token bucket rate limiter
async def check_rate_limit(user_id: str, limit: int, window: int):
    key = f"rate_limit:{user_id}"
    current = await redis.incr(key)

    if current == 1:
        await redis.expire(key, window)

    if current > limit:
        raise RateLimitExceeded(f"Max {limit} requests per {window}s")
```

### Celery Configuration

```python
# Celery with Redis backend
app = Celery(
    'hormonia',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)

app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='America/Sao_Paulo',
    enable_utc=True,
    result_expires=3600,  # 1 hour TTL for task results
)
```

### Cache Invalidation Strategy

1. **TTL-based**: Most data auto-expires (30min - 24h)
2. **Event-based**: Invalidate on data mutations
3. **Tag-based**: Group related keys for bulk invalidation
4. **Versioned keys**: Include schema version in key names

### Redis Configuration

```redis
# Memory management
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence (for sessions and Celery)
save 900 1
save 300 10
save 60 10000

# Security
requirepass <strong-password>
bind 127.0.0.1

# TLS (production)
tls-port 6380
tls-cert-file /path/to/redis.crt
tls-key-file /path/to/redis.key
```

### Monitoring

- Redis INFO command metrics
- Slowlog for query analysis
- Memory usage alerts (>80%)
- Eviction rate monitoring
- Cache hit ratio (target >80%)

### Migration Path

1. ✅ Redis 7+ deployed
2. ✅ Celery broker/backend configured
3. ✅ Rate limiting middleware implemented
4. ✅ Session management with Redis
5. ✅ Cache decorators created
6. ✅ Pub/Sub for WebSocket notifications
7. 🔄 Redis Sentinel for high availability
8. 🔄 Monitoring dashboard setup

## References

- [Redis Documentation](https://redis.io/documentation)
- [Celery Redis Backend](https://docs.celeryproject.org/en/stable/getting-started/backends-and-brokers/redis.html)
- [Redis Best Practices](https://redis.io/topics/best-practices)
- [Rate Limiting Patterns](https://redis.io/topics/rate-limiting)
- [Cache Stampede Prevention](https://en.wikipedia.org/wiki/Cache_stampede)

## Metadata

- **Author**: Infrastructure Team
- **Reviewers**: Backend Team, DevOps Team
- **Last Updated**: 2024-01-17
- **Related ADRs**: ADR-0001 (FastAPI), ADR-0004 (Celery), ADR-0002 (PostgreSQL)
- **Tags**: caching, infrastructure, performance, scalability, redis
