# Quick Start: Phase 2.5 Monitoring Infrastructure

## Overview

This guide provides a quick reference for using the Phase 2.5 monitoring infrastructure including structured logging, health checks, and performance metrics.

## Health Check Endpoints

### Quick Test Commands

```bash
# Liveness check (Container orchestration)
curl http://localhost:8000/health/live

# Readiness check (Load balancer)
curl http://localhost:8000/health/ready

# System metrics
curl http://localhost:8000/health/metrics

# Application performance metrics
curl http://localhost:8000/health/performance

# Startup validation
curl http://localhost:8000/health/startup
```

### Expected Responses

**Liveness** - Returns immediately:
```json
{
  "status": "alive",
  "timestamp": "2025-10-09T22:00:00.000Z",
  "uptime_seconds": 3600.25
}
```

**Readiness** - Validates dependencies:
```json
{
  "status": "ready",
  "dependencies": {
    "database": {"status": "healthy", "response_time_ms": 12.5},
    "redis": {"status": "healthy", "response_time_ms": 5.2},
    "firebase": {"status": "healthy"}
  }
}
```

## Structured Logging

### Basic Usage

```python
from app.utils.structured_logger import StructuredLogger

logger = StructuredLogger(__name__)

# Simple log
logger.info("User action completed", user_id="123", action="login")

# Error with exception
try:
    # operation
    pass
except Exception as e:
    logger.error("Operation failed", exc_info=e, operation="payment")
```

### Performance Logging

```python
# Log operation timing
logger.log_performance(
    operation="api_call",
    duration_ms=125.5,
    endpoint="/api/v1/patients"
)

# Database query tracking
logger.log_query(
    query_type="SELECT",
    table="patients",
    duration_ms=45.2,
    rows_returned=100
)

# Cache operations
logger.log_cache_operation(
    operation="GET",
    hit=True,
    key="patient:123:profile"
)
```

### Context Management

```python
from app.utils.structured_logger import (
    set_correlation_id,
    set_request_id,
    set_user_id
)

# Middleware automatically sets these, but you can override:
set_correlation_id("custom-correlation-id")
set_request_id("custom-request-id")
set_user_id("user-123")

# All subsequent logs include this context
logger.info("Processing")  # Auto-includes correlation_id, request_id, user_id
```

## Performance Metrics

### Access Metrics

```python
from app.middleware.metrics import get_metrics

# Get current metrics
metrics = get_metrics()

# Check key values
print(f"Total requests: {metrics['requests']['total']}")
print(f"Cache hit rate: {metrics['cache']['hit_rate_percent']}%")
print(f"Avg response time: {metrics['requests']['avg_duration_ms']}ms")
```

### Record Custom Metrics

```python
from app.middleware.metrics import (
    record_cache_hit,
    record_cache_miss,
    increment_query_count
)

# Cache operations
if value_in_cache:
    record_cache_hit()
else:
    record_cache_miss()

# Query tracking (from request context)
increment_query_count(request, count=3)
```

### Response Headers

Every response includes:
- `X-Request-ID`: Unique request identifier
- `X-Correlation-ID`: For distributed tracing
- `X-Response-Time-Ms`: Request processing time
- `X-Query-Count`: Database queries executed

## Log Analysis

### View Structured Logs

```bash
# Pretty-print JSON logs
tail -f /var/log/app.log | jq '.'

# Filter by correlation ID
tail -f /var/log/app.log | jq 'select(.correlation_id == "corr-123")'

# Show only errors
tail -f /var/log/app.log | jq 'select(.level == "ERROR")'

# Performance metrics only
tail -f /var/log/app.log | jq 'select(.metric_type == "performance")'
```

### Common Queries

**Slowest operations**:
```bash
jq 'select(.metric_type == "performance") | select(.duration_ms > 1000)' app.log
```

**API calls by endpoint**:
```bash
jq 'select(.metric_type == "api_call") | .endpoint' app.log | sort | uniq -c
```

**Cache hit rate**:
```bash
jq 'select(.metric_type == "cache_operation") | .cache_hit' app.log | \
  awk '{hits+=$1; total++} END {print "Hit rate:", (hits/total)*100"%"}'
```

## Kubernetes Integration

### Probes Configuration

```yaml
# Liveness Probe
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10

# Readiness Probe
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10
```

## Docker Compose

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/live"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 15s
```

## Monitoring Alerts

### Critical Alerts

```yaml
# Health check failure
- alert: ServiceUnhealthy
  expr: up{job="api"} == 0
  for: 1m

# High error rate
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 5m

# Slow response time
- alert: SlowResponseTime
  expr: histogram_quantile(0.95, http_request_duration_ms) > 2000
  for: 5m
```

### Warning Alerts

```yaml
# Low cache hit rate
- alert: LowCacheHitRate
  expr: cache_hit_rate < 0.70
  for: 10m

# High query count
- alert: HighQueryCount
  expr: avg_queries_per_request > 10
  for: 10m
```

## Troubleshooting

### Issue: No logs appearing

**Check**:
1. Verify logging configured: `configure_structured_logging()`
2. Check log level: `DEBUG` vs `INFO`
3. Verify log file permissions

**Solution**:
```python
# In app/core/lifespan.py
configure_structured_logging(log_level='DEBUG')
```

### Issue: Health check returns 503

**Check**:
1. Database connectivity
2. Redis connectivity
3. Firebase configuration

**Debug**:
```bash
# Test database
curl http://localhost:8000/health/startup

# View detailed error
curl http://localhost:8000/health/ready | jq '.dependencies'
```

### Issue: Missing correlation IDs

**Check**:
1. PerformanceMetricsMiddleware registered
2. Middleware order correct

**Verify**:
```bash
# Check response headers
curl -I http://localhost:8000/api/v1/patients
# Should see: X-Correlation-ID, X-Request-ID
```

## Best Practices

### 1. Correlation IDs

Always propagate correlation IDs to downstream services:

```python
import httpx

correlation_id = get_correlation_id()
headers = {"X-Correlation-ID": correlation_id}
response = await httpx.get(url, headers=headers)
```

### 2. Sensitive Data

Never log sensitive data:

```python
# ❌ Bad
logger.info(f"User password: {password}")

# ✅ Good
logger.info(f"User authenticated", user_id=user_id)
```

### 3. Performance Tracking

Track key operations:

```python
from app.utils.structured_logger import log_execution_time

@log_execution_time(logger, "process_payment")
async def process_payment(amount):
    # Automatically logs execution time
    pass
```

### 4. Error Context

Include context in error logs:

```python
try:
    result = await process_order(order_id)
except Exception as e:
    logger.error(
        "Order processing failed",
        exc_info=e,
        order_id=order_id,
        customer_id=customer_id,
        total_amount=amount
    )
    raise
```

## Quick Reference

### Configuration

```python
# Structured logging
from app.utils.structured_logger import configure_logging
configure_logging(log_level='INFO', log_file='/var/log/app.log')
```

### Metrics

```python
from app.middleware.metrics import get_metrics, reset_metrics
metrics = get_metrics()  # Get snapshot
reset_metrics()  # Reset (testing only)
```

### Context

```python
from app.utils.structured_logger import (
    get_correlation_id, set_correlation_id, clear_context
)
```

### Health Endpoints

- `/health/live` - Liveness (fast)
- `/health/ready` - Readiness (validates dependencies)
- `/health/metrics` - System metrics
- `/health/performance` - App performance
- `/health/startup` - Config validation

## Files Reference

**Implementation**:
- `app/utils/structured_logger.py` - Logging utility
- `app/routers/health.py` - Health endpoints
- `app/middleware/metrics.py` - Metrics middleware

**Configuration**:
- `app/core/router_registry.py` - Router registration
- `app/core/middleware_setup.py` - Middleware setup
- `app/core/lifespan.py` - Startup configuration

**Documentation**:
- `docs/monitoring/PHASE_2_5_MONITORING_INFRASTRUCTURE.md` - Full docs
- `docs/monitoring/QUICK_START_MONITORING.md` - This file

---

**Need Help?** See full documentation: `PHASE_2_5_MONITORING_INFRASTRUCTURE.md`
