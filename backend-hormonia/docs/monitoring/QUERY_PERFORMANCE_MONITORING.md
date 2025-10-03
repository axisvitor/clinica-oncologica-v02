# Query Performance Monitoring

## Overview

The Query Performance Monitoring system correlates database queries with API endpoints, enabling you to identify performance bottlenecks, detect N+1 query patterns, and optimize slow endpoints.

## Features

- **Request-Query Correlation**: Every request is assigned a unique `request_id` that tracks all associated database queries
- **Slow Query Detection**: Automatically logs queries exceeding 1 second with full endpoint context
- **N+1 Pattern Detection**: Identifies endpoints executing more than 50 queries per request
- **High DB Time Warnings**: Alerts when database time exceeds 50% of total request time
- **Endpoint Statistics**: Tracks performance metrics over time for each endpoint
- **Performance Headers**: Includes query metrics in every HTTP response

## Architecture

### Components

1. **QueryPerformanceMiddleware**: Intercepts all HTTP requests and tracks database queries
2. **QueryPerformanceTracker**: Aggregates statistics per endpoint for trend analysis
3. **SQLAlchemy Event Listeners**: Captures query execution times at the database layer
4. **Monitoring Endpoints**: Exposes performance metrics via REST API

### Data Flow

```
HTTP Request
    ↓
[Middleware: Generate request_id]
    ↓
[SQLAlchemy: Track all queries with timestamps]
    ↓
[Middleware: Calculate totals, detect patterns]
    ↓
[Tracker: Record endpoint statistics]
    ↓
HTTP Response (with performance headers)
```

## Performance Headers

Every API response includes these headers:

| Header | Description | Example |
|--------|-------------|---------|
| `X-Request-ID` | Unique identifier for this request | `a3f2c1b4-5678-90ab-cdef-1234567890ab` |
| `X-Query-Count` | Number of database queries executed | `23` |
| `X-DB-Time-Ms` | Total database time in milliseconds | `487` |
| `X-Request-Duration` | Total request time in seconds | `0.652s` |

### Example Response Headers

```http
HTTP/1.1 200 OK
X-Request-ID: a3f2c1b4-5678-90ab-cdef-1234567890ab
X-Query-Count: 23
X-DB-Time-Ms: 487
X-Request-Duration: 0.652s
Content-Type: application/json
```

## Log Format

### Request Summary (INFO)

Logged for every request:

```
REQUEST | GET /api/v1/patients | Status: 200 | Total: 0.652s | DB: 0.487s (74.7%) | Queries: 23 | Request ID: a3f2c1b4-...
```

### Slow Query (WARNING)

Logged when a single query exceeds 1 second:

```
SLOW QUERY (1.234s) | Endpoint: GET /api/v1/patients | Request ID: a3f2c1b4-... | Query: SELECT patients.* FROM patients WHERE...
```

### High DB Time (WARNING)

Logged when database time exceeds 50% of total request time:

```
HIGH DB TIME | GET /api/v1/patients | DB: 0.487s / Total: 0.652s (74.7%) | Request ID: a3f2c1b4-...
```

### N+1 Pattern (ERROR)

Logged when a request executes more than 50 queries:

```
POSSIBLE N+1 PATTERN | GET /api/v1/patients | 127 queries | Request ID: a3f2c1b4-...
```

### Slow Request (WARNING)

Logged when total request time exceeds 1 second:

```
SLOW REQUEST | GET /api/v1/patients | Duration: 2.34s | Queries: 127 | DB Time: 2.12s (90.6%) | Query Types: {'SELECT': 126, 'UPDATE': 1}
```

## Monitoring API

### Get Performance Statistics

Retrieve aggregated performance metrics and identify slowest endpoints.

**Endpoint**: `GET /api/v1/database/query-performance`

**Response**:

```json
{
  "overall": {
    "total_requests": 1523,
    "total_queries": 8942,
    "avg_queries_per_request": 5.87,
    "slow_request_rate": 0.034,
    "n1_pattern_rate": 0.012,
    "high_db_time_rate": 0.089,
    "tracked_endpoints": 27
  },
  "slowest_endpoints": [
    {
      "endpoint": "GET /api/v1/patients",
      "avg_db_time": 2.341,
      "avg_total_time": 2.567,
      "avg_queries": 127.3,
      "total_requests": 89,
      "slow_requests": 45,
      "n1_requests": 89,
      "high_db_time_requests": 82,
      "slow_request_rate": 0.506,
      "n1_pattern_rate": 1.0
    },
    {
      "endpoint": "GET /api/v1/reports/patient/{id}",
      "avg_db_time": 1.823,
      "avg_total_time": 2.012,
      "avg_queries": 34.2,
      "total_requests": 234,
      "slow_requests": 156,
      "n1_requests": 0,
      "high_db_time_requests": 198,
      "slow_request_rate": 0.667,
      "n1_pattern_rate": 0.0
    }
  ]
}
```

### Reset Statistics

Clear all tracked statistics (useful after optimizations).

**Endpoint**: `POST /api/v1/database/query-performance/reset`

**Response**:

```json
{
  "status": "success",
  "message": "Query performance statistics reset"
}
```

## Identifying Performance Issues

### N+1 Query Pattern

**Symptoms**:
- `n1_pattern_rate` > 0.1 (10% of requests)
- `avg_queries` > 50
- Log shows `POSSIBLE N+1 PATTERN`

**Example**:
```
GET /api/v1/patients executes:
  1 query:  SELECT * FROM patients
  100 queries: SELECT * FROM appointments WHERE patient_id = ?
```

**Solution**:
```python
# Before (N+1)
patients = session.query(Patient).all()
for patient in patients:
    appointments = patient.appointments  # Lazy load = 1 query per patient

# After (Eager Loading)
patients = session.query(Patient).options(
    joinedload(Patient.appointments)
).all()  # 1 query total
```

### Slow Queries

**Symptoms**:
- `avg_db_time` > 1.0 seconds
- Log shows `SLOW QUERY`
- `slow_request_rate` > 0.1

**Investigation**:
1. Check logs for the actual query:
   ```
   SLOW QUERY (1.234s) | Endpoint: GET /api/v1/patients | Query: SELECT patients.* FROM patients WHERE status = 'active' ORDER BY created_at DESC
   ```

2. Analyze with EXPLAIN:
   ```sql
   EXPLAIN ANALYZE SELECT patients.* FROM patients
   WHERE status = 'active' ORDER BY created_at DESC;
   ```

3. Add missing indexes:
   ```sql
   CREATE INDEX idx_patients_status_created
   ON patients(status, created_at DESC);
   ```

### High Database Time Percentage

**Symptoms**:
- `high_db_time_rate` > 0.2 (20% of requests)
- DB time is >50% of total request time
- Log shows `HIGH DB TIME`

**Possible Causes**:
1. Missing indexes
2. Inefficient queries (full table scans)
3. Too many round-trips to database
4. Network latency to database

**Solutions**:
- Add appropriate indexes
- Use query result caching (Redis)
- Batch database operations
- Use connection pooling
- Consider read replicas for read-heavy endpoints

## Optimization Workflow

### 1. Identify Problem Endpoints

```bash
# Call monitoring endpoint
curl http://localhost:8000/api/v1/database/query-performance | jq '.slowest_endpoints[:5]'
```

### 2. Analyze Logs

```bash
# Find all N+1 patterns
grep "N+1 PATTERN" app.log

# Find slow queries for specific endpoint
grep "SLOW QUERY.*GET /api/v1/patients" app.log
```

### 3. Investigate Queries

```python
# Enable query logging in development
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### 4. Apply Optimizations

**Eager Loading** (for N+1):
```python
from sqlalchemy.orm import joinedload, selectinload

# Join strategy (single query with JOIN)
patients = session.query(Patient).options(
    joinedload(Patient.appointments)
).all()

# Subquery strategy (2 queries, good for one-to-many)
patients = session.query(Patient).options(
    selectinload(Patient.appointments)
).all()
```

**Indexing** (for slow queries):
```sql
-- Find missing indexes
SELECT schemaname, tablename, attname
FROM pg_stats
WHERE schemaname = 'public'
  AND n_distinct > 100
  AND correlation < 0.5;

-- Create appropriate indexes
CREATE INDEX idx_patients_status ON patients(status);
CREATE INDEX idx_appointments_patient_date
ON appointments(patient_id, appointment_date);
```

**Caching** (for repeated queries):
```python
from functools import lru_cache
from app.core.redis import get_redis_client

@lru_cache(maxsize=1000)
def get_patient_cached(patient_id: int):
    redis = get_redis_client()
    cached = redis.get(f"patient:{patient_id}")
    if cached:
        return json.loads(cached)

    patient = session.query(Patient).get(patient_id)
    redis.setex(f"patient:{patient_id}", 300, json.dumps(patient.dict()))
    return patient
```

### 5. Verify Improvements

```bash
# Reset statistics
curl -X POST http://localhost:8000/api/v1/database/query-performance/reset

# Run load tests
ab -n 1000 -c 10 http://localhost:8000/api/v1/patients

# Check new statistics
curl http://localhost:8000/api/v1/database/query-performance | jq '.slowest_endpoints[:5]'
```

## Setting Up Alerts

### Prometheus Metrics

Export metrics for monitoring:

```python
from prometheus_client import Counter, Histogram

slow_queries = Counter(
    'slow_queries_total',
    'Total number of slow queries',
    ['endpoint', 'method']
)

db_time = Histogram(
    'database_time_seconds',
    'Database time per request',
    ['endpoint', 'method']
)
```

### Alert Rules

```yaml
groups:
  - name: query_performance
    rules:
      - alert: HighN1PatternRate
        expr: query_n1_pattern_rate > 0.1
        for: 5m
        annotations:
          summary: "N+1 pattern detected"
          description: "{{ $labels.endpoint }} has N+1 patterns in {{ $value }}% of requests"

      - alert: SlowEndpoint
        expr: query_avg_db_time_seconds > 1.0
        for: 5m
        annotations:
          summary: "Slow endpoint detected"
          description: "{{ $labels.endpoint }} average DB time: {{ $value }}s"
```

## Best Practices

### Development

1. **Monitor Query Count**: Aim for <10 queries per request
2. **Use Eager Loading**: Always specify `joinedload()` or `selectinload()` for relationships
3. **Test with Production Data Volume**: Performance issues often only appear at scale
4. **Profile Regularly**: Check `/api/v1/database/query-performance` weekly

### Production

1. **Set Up Alerts**: Monitor `n1_pattern_rate`, `slow_request_rate`, and `avg_db_time`
2. **Track Trends**: Export metrics to Prometheus/Datadog/New Relic
3. **Regular Reviews**: Review slowest endpoints monthly
4. **Performance Budget**: Set targets (e.g., all endpoints <500ms, <5 queries)

### Performance Targets

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Average Queries per Request | <5 | 5-10 | >10 |
| Average DB Time | <100ms | 100-500ms | >500ms |
| Slow Request Rate | <1% | 1-5% | >5% |
| N+1 Pattern Rate | 0% | 0-1% | >1% |
| High DB Time Rate | <10% | 10-20% | >20% |

## Troubleshooting

### Middleware Not Logging

**Check**:
1. Middleware is registered in `app/core/middleware_setup.py`
2. SQLAlchemy event listeners are set up
3. Log level is set to INFO or lower

```python
# In app/core/middleware_setup.py
from app.middleware.query_logger import QueryPerformanceMiddleware
app.add_middleware(QueryPerformanceMiddleware)

# In your logging config
logging.getLogger('app.middleware.query_logger').setLevel(logging.INFO)
```

### Headers Not Appearing

**Check CORS configuration**:
```python
# In app/core/middleware_setup.py
expose_headers=[
    "X-Request-ID",
    "X-Query-Count",
    "X-DB-Time-Ms",
    "X-Request-Duration"
]
```

### Statistics Not Accumulating

**Check tracker initialization**:
```python
from app.middleware.query_logger import get_performance_tracker
tracker = get_performance_tracker()
print(tracker.get_stats())  # Should show non-zero values after requests
```

## Configuration

### Thresholds

Adjust in `app/core/middleware_setup.py`:

```python
app.add_middleware(
    QueryPerformanceMiddleware,
    slow_request_threshold=1.0,  # Seconds
    slow_query_threshold=1.0     # Seconds
)
```

### N+1 Detection Threshold

Modify in `app/middleware/query_logger.py`:

```python
# Current: >50 queries triggers warning
if query_count > 50:
    logger.error(f"POSSIBLE N+1 PATTERN...")

# Adjust to your needs:
if query_count > 20:  # More sensitive
    logger.error(f"POSSIBLE N+1 PATTERN...")
```

### High DB Time Threshold

Modify in `app/middleware/query_logger.py`:

```python
# Current: >50% DB time triggers warning
if (db_time / total_time) > 0.5:
    logger.warning(f"HIGH DB TIME...")

# Adjust to your needs:
if (db_time / total_time) > 0.3:  # More sensitive (>30%)
    logger.warning(f"HIGH DB TIME...")
```

## Examples

### Python Client

```python
import requests

response = requests.get('http://localhost:8000/api/v1/patients')

print(f"Request ID: {response.headers['X-Request-ID']}")
print(f"Queries: {response.headers['X-Query-Count']}")
print(f"DB Time: {response.headers['X-DB-Time-Ms']}ms")
print(f"Total Time: {response.headers['X-Request-Duration']}")
```

### JavaScript Client

```javascript
fetch('http://localhost:8000/api/v1/patients')
  .then(response => {
    console.log('Request ID:', response.headers.get('X-Request-ID'));
    console.log('Queries:', response.headers.get('X-Query-Count'));
    console.log('DB Time:', response.headers.get('X-DB-Time-Ms'), 'ms');
    console.log('Total Time:', response.headers.get('X-Request-Duration'));
    return response.json();
  });
```

### cURL

```bash
curl -v http://localhost:8000/api/v1/patients 2>&1 | grep "^< X-"
```

Output:
```
< X-Request-ID: a3f2c1b4-5678-90ab-cdef-1234567890ab
< X-Query-Count: 23
< X-DB-Time-Ms: 487
< X-Request-Duration: 0.652s
```

## Integration with Monitoring Tools

### Datadog

```python
from datadog import statsd

# In middleware
statsd.histogram('api.db_time', db_time, tags=[f'endpoint:{path}', f'method:{method}'])
statsd.increment('api.queries', query_count, tags=[f'endpoint:{path}'])
```

### Prometheus

```python
from prometheus_client import Histogram, Counter

DB_TIME = Histogram('http_db_time_seconds', 'Database time', ['method', 'endpoint'])
QUERY_COUNT = Counter('http_query_count_total', 'Total queries', ['method', 'endpoint'])

# In middleware
DB_TIME.labels(method=method, endpoint=path).observe(db_time)
QUERY_COUNT.labels(method=method, endpoint=path).inc(query_count)
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Query Performance",
    "panels": [
      {
        "title": "Average DB Time by Endpoint",
        "targets": [{
          "expr": "avg(http_db_time_seconds) by (endpoint)"
        }]
      },
      {
        "title": "N+1 Pattern Detection",
        "targets": [{
          "expr": "http_query_count_total > 50"
        }]
      }
    ]
  }
}
```

## References

- [SQLAlchemy Performance Best Practices](https://docs.sqlalchemy.org/en/14/faq/performance.html)
- [FastAPI Middleware Guide](https://fastapi.tiangolo.com/advanced/middleware/)
- [N+1 Query Problem Explained](https://stackoverflow.com/questions/97197/what-is-the-n1-selects-problem)
- [Database Indexing Strategies](https://use-the-index-luke.com/)