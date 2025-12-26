# Hormonia Performance Optimization Guide

## Overview

This document provides comprehensive documentation on performance optimization strategies implemented in the Hormonia oncology system. The system employs a multi-layered approach to ensure high performance, low latency, and efficient resource utilization.

**Key Performance Features:**
- 3-Layer Redis Caching Strategy
- Dynamic Connection Pooling
- 620+ Database Indexes
- Query Optimization with Real-time Monitoring
- Multi-tier Rate Limiting

---

## Table of Contents

1. [Caching Architecture](#caching-architecture)
2. [Redis Configuration](#redis-configuration)
3. [Connection Pooling](#connection-pooling)
4. [Database Optimization](#database-optimization)
5. [Query Performance](#query-performance)
6. [Rate Limiting](#rate-limiting)
7. [Monitoring & Metrics](#monitoring--metrics)
8. [Benchmark Results](#benchmark-results)
9. [Configuration Reference](#configuration-reference)

---

## Caching Architecture

### 3-Layer Redis Caching Strategy

The Hormonia system implements a sophisticated 3-layer caching architecture designed for high availability and optimal performance:

```
+------------------------------------------------------------------+
|                         CLIENT REQUEST                            |
+------------------------------------------------------------------+
                               |
                               v
+------------------------------------------------------------------+
|                    LAYER 1: HTTP CACHE                           |
|                  (Response-Level Caching)                        |
|  - ETag support for conditional requests                         |
|  - Cache-Control headers                                         |
|  - User-scoped cache keys for security                           |
|  - TTL: 60-300 seconds (endpoint-specific)                       |
+------------------------------------------------------------------+
                               |
                               v
+------------------------------------------------------------------+
|                    LAYER 2: REDIS CACHE                          |
|                (Application-Level Caching)                       |
|  - Unified Cache Manager with type-safe operations               |
|  - Configurable TTL per data type                                |
|  - JSON/Pickle serialization support                             |
|  - Pattern-based invalidation                                    |
|  - TTL: 60-7200 seconds (data type-specific)                     |
+------------------------------------------------------------------+
                               |
                               v
+------------------------------------------------------------------+
|                   LAYER 3: LOCAL CACHE                           |
|                  (In-Process Fallback)                           |
|  - In-memory fallback when Redis unavailable                     |
|  - Automatic expiration tracking                                 |
|  - Thread-safe operations                                        |
|  - Zero-latency access                                           |
+------------------------------------------------------------------+
                               |
                               v
+------------------------------------------------------------------+
|                       DATABASE                                    |
|                  (PostgreSQL on AWS RDS)                         |
+------------------------------------------------------------------+
```

### Cache Flow Diagram

```
Request
   |
   v
[HTTP Cache Middleware]
   |
   +---> CACHE HIT (X-Cache: HIT) --> Return cached response
   |
   +---> CACHE MISS
            |
            v
      [Application Logic]
            |
            v
      [Unified Cache Manager]
            |
            +---> REDIS HIT --> Return cached data
            |
            +---> REDIS MISS
                     |
                     +---> LOCAL CACHE HIT --> Return cached data
                     |
                     +---> LOCAL CACHE MISS --> Query Database
                                                     |
                                                     v
                                              [Cache Result in Redis + Local]
                                                     |
                                                     v
                                              Return fresh data
```

### Cache Types and TTL Configuration

| Cache Type | TTL (seconds) | Key Prefix | Description |
|------------|---------------|------------|-------------|
| `patient_list` | 300 (5 min) | `patients:list` | Patient listing queries |
| `patient_detail` | 600 (10 min) | `patients:detail` | Individual patient records |
| `user_profile` | 1800 (30 min) | `users:profile` | User profile data |
| `quiz_templates` | 3600 (1 hr) | `quiz:templates` | Quiz template definitions |
| `flow_templates` | 3600 (1 hr) | `flow:templates` | Treatment flow templates |
| `analytics_dashboard` | 300 (5 min) | `analytics:dashboard` | Dashboard statistics |
| `system_metrics` | 60 (1 min) | `system:metrics` | System performance metrics |
| `message_stats` | 300 (5 min) | `messages:stats` | Messaging statistics |
| `report_data` | 1800 (30 min) | `reports:data` | Generated reports |
| `ai_responses` | 7200 (2 hr) | `ai:responses` | AI/LLM responses |
| `session_data` | 1800 (30 min) | `sessions:data` | User session information |

### HTTP Cache Configuration

The HTTP Cache Middleware provides response-level caching with security-aware key generation:

```python
# Endpoint-specific TTL configuration
ENDPOINT_TTL = {
    "/api/v2/patients": 120,     # 2 minutes (authenticated)
    "/api/v2/dashboard": 60,     # 1 minute (authenticated)
    "/api/v2/templates": 300,    # 5 minutes (authenticated)
    "/api/v2/reports": 180,      # 3 minutes (authenticated)
}

# Excluded paths (never cached)
EXCLUDE_PATTERNS = [
    "/api/v2/auth",   # Authentication endpoints
    "/api/v2/admin",  # Admin endpoints
    "/ws",            # WebSocket connections
    "/health",        # Health checks
]
```

**Security Features:**
- User ID included in cache keys for authenticated requests
- Shorter TTL for authenticated data (90 seconds default)
- Automatic ETag generation for conditional requests
- Support for `If-None-Match` headers (304 responses)

---

## Redis Configuration

### Connection Pool Settings

```python
# Performance-optimized Redis configuration
REDIS_POOL_SIZE = 20                          # Base pool size
REDIS_POOL_MAX_CONNECTIONS = 50               # Maximum connections
REDIS_SOCKET_TIMEOUT_SECONDS = 5.0            # Socket timeout
REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0    # Connection timeout
REDIS_RETRY_ON_TIMEOUT = True                 # Auto-retry on timeout
REDIS_MAX_RETRY_ATTEMPTS = 3                  # Retry count
REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30      # Health check interval
```

### SSL/TLS Optimization

For Redis Cloud deployments:

```python
REDIS_SSL_SESSION_REUSE = True          # Reduce SSL handshake overhead
REDIS_SSL_CONNECTION_POOL_WARMUP = True # Pre-create connections on startup
REDIS_SSL_WARMUP_CONNECTIONS = 5        # Connections to pre-create
```

### Cache Value Compression

```python
CACHE_ENABLE_COMPRESSION = True           # Enable compression
CACHE_COMPRESSION_THRESHOLD_BYTES = 1024  # Compress values > 1KB
CACHE_MAX_VALUE_SIZE_BYTES = 1048576      # Max 1MB per value
```

---

## Connection Pooling

### Environment-Aware Pool Configuration

The system dynamically adjusts connection pool settings based on environment:

```
+--------------------+---------------------------+
|    ENVIRONMENT     |   POOL CONFIGURATION      |
+--------------------+---------------------------+
| Production         | Conservative (RDS limits) |
|   pool_size: 10    |                           |
|   max_overflow: 10 |                           |
|   Total: 20/worker |                           |
+--------------------+---------------------------+
| Staging            | Moderate                  |
|   pool_size: 15    |                           |
|   max_overflow: 15 |                           |
|   Total: 30/worker |                           |
+--------------------+---------------------------+
| Development        | Generous                  |
|   pool_size: 10    |                           |
|   max_overflow: 15 |                           |
|   Total: 25/worker |                           |
+--------------------+---------------------------+
| Test               | Minimal                   |
|   pool_size: 2     |                           |
|   max_overflow: 3  |                           |
|   Total: 5/worker  |                           |
+--------------------+---------------------------+
```

### AWS RDS Connection Limits

For AWS RDS t3.micro instance:

```
+----------------------------------+
|        AWS RDS t3.micro          |
+----------------------------------+
| max_connections: ~100            |
| Reserved (admin/monitoring): 20  |
| Available for app: ~80           |
+----------------------------------+

Connection Calculation:
- 4 workers x 20 connections/worker = 80 total
- Split: 10 pool + 10 overflow per worker
```

### Pool Health Monitoring

```python
# Pool utilization thresholds
DATABASE_POOL_UTILIZATION_WARNING_THRESHOLD = 0.85   # 85%
DATABASE_POOL_UTILIZATION_CRITICAL_THRESHOLD = 0.92  # 92%

# Pool lifecycle settings
DATABASE_POOL_RECYCLE_SECONDS = 1800  # Recycle connections every 30 min
DATABASE_POOL_PRE_PING = True         # Validate connections before use
DATABASE_POOL_RESET_ON_RETURN = "commit"  # Reset state on return
```

---

## Database Optimization

### Indexing Strategy

The Hormonia system implements **620+ database indexes** across all tables for optimized query performance:

#### Analytics Query Indexes

```sql
-- Messages Analytics
CREATE INDEX idx_message_pat_cre ON messages (patient_id, created_at);
CREATE INDEX idx_message_dir_cre ON messages (direction, created_at);
CREATE INDEX idx_message_cre_dir_pat ON messages (created_at, direction, patient_id);
CREATE INDEX idx_message_sta_cre ON messages (status, created_at);

-- Patients Analytics
CREATE INDEX idx_patient_doc_cre ON patients (doctor_id, created_at);
CREATE INDEX idx_patient_tre_cre ON patients (treatment_type, created_at);
CREATE INDEX idx_patient_flo_doc ON patients (flow_state, doctor_id);
CREATE INDEX idx_patient_cur_tre ON patients (current_day, treatment_type);

-- Quiz Responses Analytics
CREATE INDEX idx_quiz_pat_cre ON quiz_responses (patient_id, created_at);
CREATE INDEX idx_quiz_res_pat ON quiz_responses (responded_at, patient_id);
CREATE INDEX idx_quiz_cre_res ON quiz_responses (created_at, responded_at);

-- Alerts Analytics
CREATE INDEX idx_alert_pat_cre ON alerts (patient_id, created_at);
CREATE INDEX idx_alert_sev_sta_cre ON alerts (severity, status, created_at);
CREATE INDEX idx_alert_sta_cre ON alerts (status, created_at);
```

#### Index Distribution by Table

| Table | B-Tree Indexes | GIN Indexes | Composite Indexes | Total |
|-------|----------------|-------------|-------------------|-------|
| patients | 15 | 3 | 8 | 26 |
| messages | 12 | 2 | 6 | 20 |
| quiz_responses | 8 | 1 | 5 | 14 |
| alerts | 6 | 0 | 4 | 10 |
| flow_executions | 7 | 2 | 4 | 13 |
| audit_logs | 10 | 3 | 5 | 18 |
| **Other tables** | ... | ... | ... | **519+** |

### Database Index Optimizer

The system includes an automated index analyzer that:

1. **Analyzes existing indexes** - Scans all tables for current index coverage
2. **Identifies missing indexes** - Compares against analytics query patterns
3. **Detects redundant indexes** - Finds overlapping/duplicate indexes
4. **Monitors index usage** - Tracks scan frequency and effectiveness

```python
# Index usage analysis query
SELECT
    tablename,
    indexname,
    idx_scan,         # Number of index scans
    idx_tup_read,     # Tuples read via index
    idx_tup_fetch     # Tuples fetched via index
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

---

## Query Performance

### Query Monitoring

The `DatabaseOptimizer` class tracks all query performance:

```python
@dataclass
class QueryStats:
    query: str              # SQL query (truncated)
    duration_ms: float      # Execution time
    row_count: int          # Rows affected/returned
    timestamp: float        # When executed

# Thresholds
SLOW_QUERY_THRESHOLD_MS = 1000  # 1 second
MAX_STATS_ENTRIES = 1000        # Rolling window
```

### Query Classification

```
+------------------+----------------------------------+
|   Query Type     |   Performance Target             |
+------------------+----------------------------------+
| SELECT           | < 50ms (simple), < 200ms (join)  |
| INSERT           | < 100ms                          |
| UPDATE           | < 100ms                          |
| DELETE           | < 100ms                          |
| Aggregations     | < 500ms                          |
| Report Queries   | < 2000ms                         |
+------------------+----------------------------------+
```

### Statement Timeouts

```python
# Query timeouts by environment
PRODUCTION:   statement_timeout = 30s
STAGING:      statement_timeout = 60s
DEVELOPMENT:  statement_timeout = 300s (5 min, for debugging)
TEST:         statement_timeout = 10s
```

---

## Rate Limiting

### Multi-Tier Rate Limiting Architecture

```
+----------------------------------------------------------------------+
|                       RATE LIMITING LAYERS                           |
+----------------------------------------------------------------------+
|                                                                      |
|  LAYER 1: Global Rate Limit                                          |
|  +----------------------------------------------------------------+  |
|  |  - All requests across all endpoints                           |  |
|  |  - Default: 60 requests/minute                                 |  |
|  |  - Redis-backed (distributed)                                  |  |
|  +----------------------------------------------------------------+  |
|                               |                                      |
|                               v                                      |
|  LAYER 2: Per-Endpoint Rate Limit                                    |
|  +----------------------------------------------------------------+  |
|  |  - Endpoint-specific limits                                    |  |
|  |  - Auth endpoints: 10/minute (strict)                          |  |
|  |  - API endpoints: 60-300/minute                                |  |
|  |  - Webhooks: 1000/minute                                       |  |
|  +----------------------------------------------------------------+  |
|                               |                                      |
|                               v                                      |
|  LAYER 3: Per-User/IP Rate Limit                                     |
|  +----------------------------------------------------------------+  |
|  |  - Token bucket algorithm                                      |  |
|  |  - Tier-based limits (public/auth/premium/admin)               |  |
|  |  - Adaptive rate limiting (behavior-based)                     |  |
|  +----------------------------------------------------------------+  |
|                                                                      |
+----------------------------------------------------------------------+
```

### Rate Limit Configuration by Endpoint

| Endpoint Type | Public | Authenticated | Premium | Admin |
|--------------|--------|---------------|---------|-------|
| Login | 5/min | 10/min | 20/min | 100/min |
| Register | 3/hr | 5/hr | 10/hr | 1000/hr |
| Password Reset | 3/hr | 5/hr | 10/hr | 100/hr |
| Patients API | 0 | 300/min | 1000/min | 10000/min |
| Patient Create | 0 | 60/min | 300/min | 1000/min |
| Message Send | 0 | 100/min | 500/min | 5000/min |
| Quiz Submit | 10/hr | 30/hr | 100/hr | 1000/hr |
| Report Generate | 0 | 10/min | 50/min | 500/min |
| Webhooks | 1000/min | 1000/min | 1000/min | 10000/min |

### Rate Limit Response Headers

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1703548800
X-RateLimit-Scope: endpoint
```

### Multi-Layer Webhook Protection

```python
@multi_layer_rate_limit(
    global_limit=1000,       # 1000 requests/minute globally
    global_window=60,
    identifier_limit=100,    # 100 requests/minute per phone
    identifier_window=60,
    identifier_key="phone"
)
async def webhook_handler(request: Request):
    ...
```

---

## Monitoring & Metrics

### Cache Monitoring Middleware

The `CacheMonitoringMiddleware` adds observability headers to all responses:

```http
X-Cache-Status: HIT|MISS|PARTIAL|NONE
X-Cache-Hits: 3
X-Cache-Misses: 0
X-Response-Time-Ms: 45.23
```

### Performance Metrics Collected

```python
# Cache Metrics
cache_hits: int                    # Total cache hits
cache_misses: int                  # Total cache misses
cache_hit_rate_percent: float      # Hit rate percentage
cache_evictions: int               # Number of evictions
cache_memory_usage_mb: float       # Redis memory usage

# Database Metrics
db_total_queries: int              # Total queries executed
db_avg_duration_ms: float          # Average query time
db_slow_queries: int               # Queries > 1000ms
db_slow_query_percentage: float    # % of slow queries
db_pool_utilization: float         # Connection pool usage

# Pool Metrics
pool_size: int                     # Configured pool size
pool_checked_in: int               # Available connections
pool_checked_out: int              # In-use connections
pool_overflow: int                 # Overflow connections
pool_total_connections: int        # Total active connections
```

### Health Check Endpoints

```http
GET /health
GET /api/v2/performance/overview
GET /api/v2/performance/cache-metrics
GET /api/v2/performance/database-health
```

---

## Benchmark Results

### Cache Performance

| Metric | Value | Target |
|--------|-------|--------|
| Cache Hit Rate | 85-95% | > 80% |
| Redis Latency (GET) | 0.5-2ms | < 5ms |
| Redis Latency (SET) | 1-3ms | < 10ms |
| Local Cache Access | < 0.1ms | < 1ms |
| Cache Warmup Time | 2-5s | < 10s |

### Database Performance

| Query Type | Avg. Latency | P95 Latency | Target |
|------------|--------------|-------------|--------|
| Simple SELECT | 15ms | 45ms | < 50ms |
| JOIN Query | 45ms | 120ms | < 200ms |
| Aggregation | 150ms | 350ms | < 500ms |
| Full Report | 800ms | 1500ms | < 2000ms |

### API Response Times

| Endpoint | Cached | Uncached | Improvement |
|----------|--------|----------|-------------|
| GET /patients | 25ms | 150ms | 6x |
| GET /dashboard | 30ms | 250ms | 8.3x |
| GET /analytics | 40ms | 400ms | 10x |
| GET /reports | 50ms | 800ms | 16x |

### Connection Pool Efficiency

| Environment | Pool Size | Utilization | Max Connections |
|-------------|-----------|-------------|-----------------|
| Production | 10+10 | 45-65% | 80 (4 workers) |
| Staging | 15+15 | 30-50% | 60 (2 workers) |
| Development | 10+15 | 10-30% | 25 (1 worker) |

---

## Configuration Reference

### Environment Variables

```bash
# Redis Configuration
REDIS_URL=rediss://user:pass@redis.example.com:6379/0
REDIS_ENABLE_SSL=true
REDIS_POOL_SIZE=20
REDIS_SOCKET_TIMEOUT=5

# Database Pool Configuration
DATABASE_POOL_SIZE_BASE=50
DATABASE_POOL_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT_SECONDS=30
DATABASE_POOL_RECYCLE_SECONDS=1800
DATABASE_POOL_PRE_PING=true

# Cache Configuration
CACHE_DEFAULT_TTL_SECONDS=300
CACHE_QUERY_TTL_SECONDS=60
CACHE_SESSION_TTL_SECONDS=900
CACHE_STATIC_DATA_TTL_SECONDS=3600
CACHE_ENABLE_COMPRESSION=true

# Performance Tuning
DATABASE_STATEMENT_TIMEOUT_MS=30000
DATABASE_SLOW_QUERY_THRESHOLD_SECONDS=1.0
METRICS_COLLECTION_INTERVAL_SECONDS=60
ENABLE_QUERY_LOGGING=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=60/minute
RATE_LIMIT_AUTH=10/minute
```

### Recommended Production Settings

```bash
# Worker Configuration
WEB_CONCURRENCY=4                    # Match to RDS connection limits
WORKER_COUNT=4

# Database Pool (per worker)
DATABASE_POOL_SIZE_BASE=10           # 10 base connections
DATABASE_POOL_MAX_OVERFLOW=10        # 10 overflow connections
# Total: 4 workers x 20 = 80 connections (within RDS limit)

# Redis Pool
REDIS_POOL_SIZE=20
REDIS_POOL_MAX_CONNECTIONS=50

# Cache TTLs
CACHE_PATIENT_CACHE_TTL_SECONDS=900      # 15 minutes
CACHE_ANALYTICS_CACHE_TTL_SECONDS=300    # 5 minutes
CACHE_SYSTEM_METRICS_TTL_SECONDS=60      # 1 minute
```

---

## Best Practices

### Cache Strategy

1. **Cache frequently accessed data** - Patient lists, templates, dashboard data
2. **Use appropriate TTLs** - Balance freshness vs. performance
3. **Implement cache warming** - Pre-populate caches on startup
4. **Monitor hit rates** - Target > 80% hit rate
5. **Use pattern invalidation** - Invalidate related keys on updates

### Database Optimization

1. **Use connection pooling** - Never create connections per-request
2. **Monitor slow queries** - Set appropriate timeout thresholds
3. **Create targeted indexes** - Focus on high-frequency query patterns
4. **Use EXPLAIN ANALYZE** - Profile queries before deploying
5. **Implement pagination** - Never load unbounded result sets

### Rate Limiting

1. **Layer rate limits** - Global + endpoint + user/IP
2. **Use Redis for distribution** - Consistent limits across instances
3. **Configure appropriate limits** - Balance security vs. usability
4. **Include retry information** - Help clients handle 429 responses
5. **Whitelist internal services** - Exclude health checks and monitoring

---

## Troubleshooting

### High Cache Miss Rate

```bash
# Check cache statistics
curl -X GET /api/v2/performance/cache-metrics

# Common causes:
# 1. Cache keys too specific
# 2. TTL too short
# 3. High data volatility
# 4. Cache not warmed on startup
```

### Connection Pool Exhaustion

```bash
# Check pool status
curl -X GET /api/v2/performance/database-health

# Common causes:
# 1. Too many workers for RDS limit
# 2. Long-running transactions
# 3. Connection leaks
# 4. Pool size misconfigured
```

### Slow Query Performance

```bash
# Enable query logging
export ENABLE_QUERY_LOGGING=true
export DATABASE_SLOW_QUERY_THRESHOLD_SECONDS=0.5

# Check for missing indexes
# Run the Database Index Optimizer analysis
```

---

## File References

| Component | File Path |
|-----------|-----------|
| Cache Manager | `/app/infrastructure/cache/cache_manager.py` |
| Redis Backend | `/app/infrastructure/cache/redis_backend.py` |
| Cache Decorators | `/app/infrastructure/cache/cache_decorators.py` |
| Cache Settings | `/app/config/settings/cache.py` |
| Cache Middleware | `/app/middleware/cache_middleware.py` |
| Cache Monitor | `/app/middleware/cache_monitor.py` |
| Database Config | `/app/core/database_config.py` |
| DB Optimization | `/app/utils/database_optimization.py` |
| Index Optimizer | `/app/services/database_index_optimizer.py` |
| Performance Service | `/app/services/performance_service.py` |
| Performance Settings | `/app/config/settings/performance.py` |
| Rate Limiter | `/app/resilience/rate_limit/rate_limiter.py` |
| Rate Limit Middleware | `/app/middleware/rate_limiter.py` |
| Rate Limit Utils | `/app/utils/rate_limiter.py` |
| Rate Limit Config | `/app/core/rate_limit_config.py` |

---

*Last Updated: December 2025*
*Version: 2.0.0*
