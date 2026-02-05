# Database Connection Pool Tuning Guide

**Part of:** MEDIUM-007 - Connection Pool Optimization
**Status:** ✅ Implemented
**Expected Impact:** Reduced latency, improved throughput, fewer connection errors

---

## Table of Contents

1. [Overview](#overview)
2. [Current Configuration](#current-configuration)
3. [Load Testing Methodology](#load-testing-methodology)
4. [Optimal Settings](#optimal-settings)
5. [Monitoring](#monitoring)
6. [Troubleshooting](#troubleshooting)
7. [Scaling Guidelines](#scaling-guidelines)

---

## Overview

The database connection pool is critical for application performance. Properly tuned pool settings can:

- **Reduce latency** by maintaining ready connections
- **Improve throughput** by handling concurrent requests efficiently
- **Prevent errors** from connection exhaustion
- **Optimize resource usage** on both application and database servers

### Key Metrics

- **Pool Size**: Number of persistent connections maintained
- **Max Overflow**: Additional connections created under load
- **Pool Timeout**: Maximum wait time for a connection
- **Pool Recycle**: Time before connections are recycled

---

## Current Configuration

### Environment-Aware Settings

Our application automatically adjusts pool settings based on environment:

```python
# Production (AWS RDS)
pool_size = 10
max_overflow = 10
total_per_worker = 20
workers = 4
total_connections = 80

# Staging
pool_size = 15
max_overflow = 15
total_per_worker = 30

# Development
pool_size = 20
max_overflow = 30
total_per_worker = 50
```

### Configuration File

Settings are defined in `/backend-hormonia/app/core/database_config.py`:

```python
from app.core.database_config import get_pool_config

# Automatic environment detection
pool_config = get_pool_config()

engine = create_async_engine(
    DATABASE_URL,
    pool_size=pool_config.pool_size,
    max_overflow=pool_config.max_overflow,
    pool_timeout=pool_config.pool_timeout,
    pool_recycle=pool_config.pool_recycle,
    pool_pre_ping=pool_config.pool_pre_ping
)
```

### Environment Variables

Override defaults with environment variables:

```bash
# .env
DATABASE_POOL_SIZE=20
DATABASE_POOL_MAX_OVERFLOW=40
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600
```

---

## Load Testing Methodology

### Prerequisites

Install load testing tools:

```bash
pip install locust gevent
```

### Running Load Tests

#### Single Configuration Test

```bash
# Test with specific pool settings
export DATABASE_POOL_SIZE=20
export DATABASE_POOL_MAX_OVERFLOW=40

# Restart backend
docker-compose restart backend

# Run load test
python scripts/test_connection_pool.py \
  --pool-size 20 \
  --max-overflow 40 \
  --users 100 \
  --spawn-rate 10 \
  --duration 60
```

#### Full Test Suite

Test multiple configurations automatically:

```bash
python scripts/test_connection_pool.py --full-suite
```

This will test:
- Current default (5/10)
- 2x increase (10/20)
- 4x increase (20/40) ← **Recommended**
- 6x increase (30/60)
- 8x increase (40/80)

### Test Scenarios

The load test simulates realistic workloads:

| Operation | Weight | Type | Complexity |
|-----------|--------|------|------------|
| List patients | 10 | Read | Simple SELECT |
| Get patient details | 5 | Read | Single row |
| Create patient | 3 | Write | INSERT |
| Update patient | 2 | Write | UPDATE |
| Start quiz session | 8 | Read/Write | Multi-table JOIN |
| Submit quiz response | 5 | Write | JSONB insert |
| List messages | 4 | Read | Conversation history |
| Dashboard stats | 2 | Read | Complex aggregations |

### Interpreting Results

Key metrics to analyze:

```
📊 Results:
   Total requests: 10,000
   Failures: 23 (0.23%)          ← Should be <1%
   Avg response time: 145.32ms    ← Should be <200ms
   Median response time: 98.45ms  ← Should be <150ms
   P95 response time: 452.67ms    ← Should be <500ms
   P99 response time: 891.23ms    ← Should be <1000ms
   Requests/sec: 167.43           ← Higher is better
```

**Good Configuration:**
- Failure rate < 1%
- P95 < 500ms
- P99 < 1000ms
- High requests/sec

**Poor Configuration:**
- Failure rate > 5%
- P95 > 1000ms
- P99 > 2000ms
- Connection timeout errors in logs

---

## Optimal Settings

### Production (AWS RDS t3.micro)

Based on load testing with 100 concurrent users:

```python
# Recommended configuration
DATABASE_POOL_SIZE=20
DATABASE_POOL_MAX_OVERFLOW=40
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600

# Total connections per worker: 60
# With 4 workers: 240 total
# (Ensure database max_connections > 240)
```

**Why these numbers?**

- **20 pool_size**: Maintains ready connections for typical load
- **40 max_overflow**: Handles traffic spikes (3x pool_size)
- **30s timeout**: Reasonable wait for connection during peak load
- **3600s recycle**: Refresh connections hourly (prevents stale connections)

### Scaling by Load

| Concurrent Users | pool_size | max_overflow | Total per Worker |
|-----------------|-----------|--------------|------------------|
| < 50 | 10 | 10 | 20 |
| 50-100 | 20 | 40 | 60 |
| 100-200 | 30 | 60 | 90 |
| 200-500 | 40 | 80 | 120 |
| 500+ | Consider PgBouncer + horizontal scaling |

### Database Limits

**AWS RDS Connection Limits:**

| Instance Type | max_connections | Available for App* |
|---------------|-----------------|-------------------|
| t3.micro | 87 | ~70 |
| t3.small | 150 | ~130 |
| t3.medium | 279 | ~250 |
| t3.large | 540 | ~500 |

*After reserving ~20 connections for monitoring, admin, PgBouncer

**Calculate Your Needs:**

```python
# Total connections needed
total = (pool_size + max_overflow) * worker_count

# Example with recommended settings
total = (20 + 40) * 4 = 240 connections

# Ensure: total < database max_connections
```

---

## Monitoring

### Prometheus Metrics

Pool metrics are automatically exported:

```prometheus
# Pool size metrics
db_pool_size{app="hormonia"} 20
db_pool_checked_out{app="hormonia"} 15
db_pool_overflow{app="hormonia"} 5

# Wait time histogram
db_pool_wait_time_seconds_bucket{le="0.1"} 1500
db_pool_wait_time_seconds_bucket{le="0.5"} 2800
db_pool_wait_time_seconds_bucket{le="1.0"} 2950
```

### Grafana Dashboard

Import dashboard from `/backend-hormonia/monitoring/grafana_pool_dashboard.json`:

Key panels:
- Pool utilization over time
- Connection wait times (P50, P95, P99)
- Pool exhaustion events
- Connection errors by type

### Health Check Endpoint

Check pool status via API:

```bash
curl http://localhost:8000/health/detailed

{
  "database": {
    "status": "healthy",
    "pool": {
      "size": 20,
      "checked_out": 8,
      "overflow": 2,
      "available": 10,
      "utilization": 40.0
    }
  }
}
```

### Alerts

Set up alerts for pool issues:

```yaml
# prometheus/alerts.yml
groups:
  - name: database_pool
    rules:
      - alert: PoolNearExhaustion
        expr: db_pool_checked_out / db_pool_size > 0.9
        for: 5m
        annotations:
          summary: "Connection pool utilization > 90%"

      - alert: PoolWaitTimeHigh
        expr: db_pool_wait_time_seconds{quantile="0.95"} > 1.0
        for: 5m
        annotations:
          summary: "95th percentile wait time > 1s"
```

---

## Troubleshooting

### Issue: Connection Timeout Errors

**Symptoms:**
```
sqlalchemy.exc.TimeoutError: QueuePool limit exceeded
```

**Diagnosis:**
```bash
# Check current pool utilization
curl http://localhost:8000/health/detailed | jq '.database.pool'

# Check database connections
psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='hormonia';"
```

**Solutions:**

1. **Increase pool size** (if database has capacity):
   ```bash
   export DATABASE_POOL_SIZE=30
   export DATABASE_POOL_MAX_OVERFLOW=60
   ```

2. **Increase timeout** (temporary fix):
   ```bash
   export DATABASE_POOL_TIMEOUT=60
   ```

3. **Check for connection leaks**:
   ```python
   # Look for sessions not being closed
   with get_scoped_session() as db:
       # ... operations ...
       # Session auto-closed on exit
   ```

### Issue: Slow Query Performance

**Symptoms:**
- P95 response times > 1s
- High database CPU usage

**Diagnosis:**
```sql
-- Find slow queries
SELECT query, calls, mean_exec_time, max_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check for missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
  AND correlation < 0.1;
```

**Solutions:**

1. **Add missing indexes** (see MEDIUM-014 for GIN indexes)
2. **Optimize queries** (use EXPLAIN ANALYZE)
3. **Increase pool_recycle** to prevent stale query plans:
   ```bash
   export DATABASE_POOL_RECYCLE=1800  # 30 minutes
   ```

### Issue: Pool Exhaustion Spikes

**Symptoms:**
- Intermittent connection errors
- Pool exhaustion alerts
- Normal utilization most of the time

**Diagnosis:**
```bash
# Check for traffic spikes in application logs
grep "Pool limit exceeded" /var/log/hormonia/*.log | \
  awk '{print $1, $2}' | \
  sort | uniq -c

# Check for long-running transactions
psql -c "SELECT pid, now() - xact_start AS duration, state, query
         FROM pg_stat_activity
         WHERE state != 'idle'
         ORDER BY duration DESC;"
```

**Solutions:**

1. **Increase max_overflow** for burst capacity:
   ```bash
   export DATABASE_POOL_MAX_OVERFLOW=80
   ```

2. **Set statement timeout** to kill long queries:
   ```sql
   ALTER DATABASE hormonia SET statement_timeout = '30s';
   ```

3. **Implement connection pooling** with PgBouncer for high-traffic apps

---

## Scaling Guidelines

### Horizontal Scaling

When adding more workers/servers:

```python
# Calculate per-worker allocation
database_max_connections = 500  # Your database limit
reserved_connections = 50        # For monitoring, admin
worker_count = 8                 # Total workers across all servers

available = database_max_connections - reserved_connections  # 450
per_worker = available / worker_count  # 56.25

# Set pool config
pool_size = per_worker * 0.4      # ~22
max_overflow = per_worker * 0.6   # ~34
```

### PgBouncer Integration

For > 500 concurrent connections, use PgBouncer:

```ini
# pgbouncer.ini
[databases]
hormonia = host=rds.amazonaws.com port=5432 dbname=hormonia

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 50
reserve_pool_size = 10
```

Update application:

```bash
# Point to PgBouncer instead of direct RDS
DATABASE_URL=postgresql://pgbouncer:6432/hormonia

# Reduce application pool (PgBouncer handles pooling)
DATABASE_POOL_SIZE=5
DATABASE_POOL_MAX_OVERFLOW=10
```

### Cloud Database Scaling

**Vertical Scaling (Upgrade instance):**

| Upgrade | Cost Impact | Connection Increase |
|---------|-------------|---------------------|
| t3.micro → t3.small | +100% | 87 → 150 (+72%) |
| t3.small → t3.medium | +100% | 150 → 279 (+86%) |
| t3.medium → t3.large | +100% | 279 → 540 (+93%) |

**Horizontal Scaling (Read replicas):**

```python
# Use read replicas for read-heavy workloads
WRITER_URL = "postgresql://rds-writer.amazonaws.com/hormonia"
READER_URL = "postgresql://rds-reader.amazonaws.com/hormonia"

# Separate pools for read/write
writer_engine = create_engine(WRITER_URL, pool_size=10)
reader_engine = create_engine(READER_URL, pool_size=30)
```

---

## Best Practices

1. **Start conservative, scale up based on data**
   - Begin with default settings
   - Run load tests to find optimal values
   - Monitor in production

2. **Monitor continuously**
   - Set up Prometheus + Grafana
   - Configure alerts for pool issues
   - Review metrics weekly

3. **Plan for peak load**
   - Set max_overflow to 2-3x pool_size
   - Ensure database can handle total connections
   - Load test at 2x expected peak traffic

4. **Recycle connections regularly**
   - Set pool_recycle to 1-2 hours
   - Prevents stale connections
   - Refreshes query plans

5. **Use connection pooling middleware**
   - For > 500 connections, use PgBouncer
   - Reduces database overhead
   - Enables connection multiplexing

---

## References

- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [PostgreSQL Connection Limits](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [AWS RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [Load Testing Script](../../scripts/test_connection_pool.py)
- [Pool Configuration](../../app/core/database_config.py)

---

**Last Updated:** 2025-01-16
**Implemented By:** MEDIUM-007 Performance Optimization
**Status:** ✅ Production Ready
