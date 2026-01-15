# Guia de Monitoramento de Performance - Backend Hormonia

**Data:** 2025-11-30
**Versão:** 1.0

---

## 📊 Dashboard de Monitoramento

### Métricas Críticas a Monitorar

#### 1. Database Performance

```python
# backend-hormonia/app/monitoring/database_metrics.py
"""
Database performance monitoring endpoint.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.utils.database_optimization import get_db_optimizer
from app.database import get_pool_status

router = APIRouter(prefix="/monitoring/database", tags=["monitoring"])


@router.get("/pool-status")
async def get_pool_status(db: Session = Depends(get_db)):
    """
    Monitor connection pool health.

    Returns:
        Current pool status and utilization metrics.
    """
    pool_status = get_pool_status()

    # Calcular métricas adicionais
    utilization = pool_status['utilization_percent']

    return {
        "status": "healthy" if utilization < 80 else "warning" if utilization < 90 else "critical",
        "pool_metrics": pool_status,
        "recommendations": _get_pool_recommendations(pool_status),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/query-stats")
async def get_query_stats():
    """
    Get database query performance statistics.

    Returns:
        Query performance metrics and slow query analysis.
    """
    optimizer = get_db_optimizer()
    stats = optimizer.get_query_stats()
    slowest = optimizer.get_slowest_queries(limit=10)

    return {
        "summary": stats,
        "slowest_queries": slowest,
        "alerts": _generate_query_alerts(stats),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/index-usage")
async def get_index_usage(db: Session = Depends(get_db)):
    """
    Analyze index usage and effectiveness.

    Returns:
        Index usage statistics and recommendations.
    """
    from sqlalchemy import text

    query = text("""
        SELECT
            schemaname,
            tablename,
            indexname,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch,
            pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
          AND tablename IN ('patients', 'messages', 'quiz_sessions')
        ORDER BY idx_scan DESC
    """)

    result = db.execute(query).fetchall()

    indexes = []
    for row in result:
        indexes.append({
            "table": row.tablename,
            "index": row.indexname,
            "scans": row.idx_scan,
            "tuples_read": row.idx_tup_read,
            "tuples_fetched": row.idx_tup_fetch,
            "size": row.index_size,
            "efficiency": (row.idx_tup_fetch / row.idx_tup_read * 100) if row.idx_tup_read > 0 else 0
        })

    return {
        "indexes": indexes,
        "unused_indexes": [idx for idx in indexes if idx['scans'] == 0],
        "recommendations": _generate_index_recommendations(indexes),
        "timestamp": datetime.utcnow().isoformat()
    }


def _get_pool_recommendations(pool_status: dict) -> list:
    """Generate pool configuration recommendations."""
    recommendations = []

    utilization = pool_status['utilization_percent']

    if utilization > 90:
        recommendations.append({
            "severity": "critical",
            "message": "Connection pool critically saturated",
            "action": "Increase pool_size immediately",
            "suggested_value": pool_status['pool_size'] * 1.5
        })
    elif utilization > 80:
        recommendations.append({
            "severity": "warning",
            "message": "Connection pool highly utilized",
            "action": "Consider increasing pool_size",
            "suggested_value": pool_status['pool_size'] * 1.25
        })

    if pool_status['overflow'] > 0:
        recommendations.append({
            "severity": "info",
            "message": f"Using overflow connections ({pool_status['overflow']})",
            "action": "Evaluate if base pool_size is sufficient"
        })

    return recommendations


def _generate_query_alerts(stats: dict) -> list:
    """Generate alerts based on query statistics."""
    alerts = []

    if stats['slow_query_percentage'] > 10:
        alerts.append({
            "severity": "critical",
            "message": f"High slow query rate: {stats['slow_query_percentage']}%",
            "action": "Review slow queries and add indexes",
            "threshold": "10%"
        })
    elif stats['slow_query_percentage'] > 5:
        alerts.append({
            "severity": "warning",
            "message": f"Elevated slow query rate: {stats['slow_query_percentage']}%",
            "action": "Monitor query performance",
            "threshold": "5%"
        })

    if stats['avg_duration_ms'] > 100:
        alerts.append({
            "severity": "warning",
            "message": f"High average query duration: {stats['avg_duration_ms']}ms",
            "action": "Optimize common queries",
            "target": "< 50ms"
        })

    return alerts


def _generate_index_recommendations(indexes: list) -> list:
    """Generate index optimization recommendations."""
    recommendations = []

    for idx in indexes:
        if idx['scans'] == 0:
            recommendations.append({
                "type": "unused_index",
                "index": idx['index'],
                "table": idx['table'],
                "action": f"Consider dropping {idx['index']} - never used",
                "impact": f"Save {idx['size']} of storage"
            })

        if idx['efficiency'] < 50 and idx['scans'] > 100:
            recommendations.append({
                "type": "inefficient_index",
                "index": idx['index'],
                "table": idx['table'],
                "efficiency": f"{idx['efficiency']:.1f}%",
                "action": "Index reads many rows but returns few - review query patterns"
            })

    return recommendations
```

---

#### 2. Redis Performance

```python
# backend-hormonia/app/monitoring/redis_metrics.py
"""
Redis performance monitoring.
"""
from fastapi import APIRouter
from datetime import datetime
import asyncio
from app.core.redis_unified import get_async_redis, get_sync_redis

router = APIRouter(prefix="/monitoring/redis", tags=["monitoring"])


@router.get("/latency")
async def get_redis_latency():
    """
    Measure Redis operation latency.

    Returns:
        Latency metrics for common Redis operations.
    """
    import time

    redis = await get_async_redis()

    # Test SET operation
    set_times = []
    for _ in range(10):
        start = time.perf_counter()
        await redis.set("latency_test", "value", ex=60)
        set_times.append((time.perf_counter() - start) * 1000)

    # Test GET operation
    get_times = []
    for _ in range(10):
        start = time.perf_counter()
        await redis.get("latency_test")
        get_times.append((time.perf_counter() - start) * 1000)

    # Test DELETE operation
    start = time.perf_counter()
    await redis.delete("latency_test")
    del_time = (time.perf_counter() - start) * 1000

    return {
        "set_operation": {
            "avg_ms": sum(set_times) / len(set_times),
            "min_ms": min(set_times),
            "max_ms": max(set_times),
            "p95_ms": sorted(set_times)[int(len(set_times) * 0.95)]
        },
        "get_operation": {
            "avg_ms": sum(get_times) / len(get_times),
            "min_ms": min(get_times),
            "max_ms": max(get_times),
            "p95_ms": sorted(get_times)[int(len(get_times) * 0.95)]
        },
        "delete_operation": {
            "ms": del_time
        },
        "alerts": _generate_redis_alerts(set_times, get_times),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/memory")
async def get_redis_memory():
    """
    Get Redis memory usage statistics.

    Returns:
        Memory usage and key statistics.
    """
    redis = get_sync_redis()

    info = redis.info("memory")
    stats = redis.info("stats")

    return {
        "memory": {
            "used_mb": info['used_memory'] / (1024 * 1024),
            "peak_mb": info['used_memory_peak'] / (1024 * 1024),
            "rss_mb": info['used_memory_rss'] / (1024 * 1024),
            "fragmentation_ratio": info.get('mem_fragmentation_ratio', 0)
        },
        "keys": {
            "total": redis.dbsize(),
            "evicted": stats.get('evicted_keys', 0),
            "expired": stats.get('expired_keys', 0)
        },
        "connections": {
            "total": stats.get('total_connections_received', 0),
            "current": len(redis.client_list())
        },
        "recommendations": _generate_redis_memory_recommendations(info),
        "timestamp": datetime.utcnow().isoformat()
    }


def _generate_redis_alerts(set_times: list, get_times: list) -> list:
    """Generate Redis performance alerts."""
    alerts = []

    avg_set = sum(set_times) / len(set_times)
    avg_get = sum(get_times) / len(get_times)

    if avg_set > 10:
        alerts.append({
            "severity": "warning",
            "operation": "SET",
            "message": f"High SET latency: {avg_set:.2f}ms",
            "threshold": "10ms",
            "action": "Check network latency and Redis server load"
        })

    if avg_get > 5:
        alerts.append({
            "severity": "warning",
            "operation": "GET",
            "message": f"High GET latency: {avg_get:.2f}ms",
            "threshold": "5ms",
            "action": "Check connection pool and network"
        })

    return alerts


def _generate_redis_memory_recommendations(info: dict) -> list:
    """Generate Redis memory recommendations."""
    recommendations = []

    fragmentation = info.get('mem_fragmentation_ratio', 1.0)
    used_mb = info['used_memory'] / (1024 * 1024)

    if fragmentation > 1.5:
        recommendations.append({
            "type": "fragmentation",
            "message": f"High memory fragmentation: {fragmentation:.2f}",
            "action": "Consider restarting Redis during low-traffic period",
            "impact": "Reduced memory efficiency"
        })

    if used_mb > 500:
        recommendations.append({
            "type": "memory_usage",
            "message": f"High memory usage: {used_mb:.0f}MB",
            "action": "Review cache expiration policies",
            "suggestion": "Reduce TTL for less critical data"
        })

    return recommendations
```

---

#### 3. API Response Time

```python
# backend-hormonia/app/monitoring/api_metrics.py
"""
API performance monitoring.
"""
from fastapi import APIRouter, Request
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List
import time

router = APIRouter(prefix="/monitoring/api", tags=["monitoring"])


@dataclass
class EndpointMetrics:
    """Metrics for a single endpoint."""
    total_requests: int = 0
    total_duration_ms: float = 0.0
    response_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    status_codes: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    errors: int = 0


class APIMetricsCollector:
    """Collect API performance metrics."""

    def __init__(self):
        self.endpoints: Dict[str, EndpointMetrics] = defaultdict(EndpointMetrics)
        self.start_time = datetime.utcnow()

    def record_request(self, endpoint: str, duration_ms: float, status_code: int):
        """Record API request metrics."""
        metrics = self.endpoints[endpoint]

        metrics.total_requests += 1
        metrics.total_duration_ms += duration_ms
        metrics.response_times.append(duration_ms)
        metrics.status_codes[status_code] += 1

        if status_code >= 400:
            metrics.errors += 1

    def get_endpoint_stats(self, endpoint: str) -> dict:
        """Get statistics for a specific endpoint."""
        metrics = self.endpoints.get(endpoint)

        if not metrics or metrics.total_requests == 0:
            return None

        response_times = list(metrics.response_times)
        response_times.sort()

        return {
            "total_requests": metrics.total_requests,
            "avg_duration_ms": metrics.total_duration_ms / metrics.total_requests,
            "p50_ms": response_times[len(response_times) // 2] if response_times else 0,
            "p95_ms": response_times[int(len(response_times) * 0.95)] if response_times else 0,
            "p99_ms": response_times[int(len(response_times) * 0.99)] if response_times else 0,
            "error_rate": (metrics.errors / metrics.total_requests) * 100,
            "status_codes": dict(metrics.status_codes)
        }

    def get_all_stats(self) -> dict:
        """Get statistics for all endpoints."""
        return {
            endpoint: self.get_endpoint_stats(endpoint)
            for endpoint in self.endpoints.keys()
        }


# Global metrics collector
metrics_collector = APIMetricsCollector()


@router.get("/endpoints")
async def get_endpoint_metrics():
    """
    Get performance metrics for all API endpoints.

    Returns:
        Performance statistics for each endpoint.
    """
    all_stats = metrics_collector.get_all_stats()

    # Calcular top endpoints mais lentos
    slow_endpoints = sorted(
        [(k, v) for k, v in all_stats.items() if v],
        key=lambda x: x[1]['p95_ms'],
        reverse=True
    )[:10]

    # Endpoints com mais erros
    error_endpoints = sorted(
        [(k, v) for k, v in all_stats.items() if v and v['error_rate'] > 0],
        key=lambda x: x[1]['error_rate'],
        reverse=True
    )[:10]

    return {
        "summary": {
            "total_endpoints": len(all_stats),
            "uptime_seconds": (datetime.utcnow() - metrics_collector.start_time).total_seconds()
        },
        "slow_endpoints": [
            {
                "endpoint": endpoint,
                "p95_ms": stats['p95_ms'],
                "avg_ms": stats['avg_duration_ms'],
                "requests": stats['total_requests']
            }
            for endpoint, stats in slow_endpoints
        ],
        "error_endpoints": [
            {
                "endpoint": endpoint,
                "error_rate": stats['error_rate'],
                "errors": int(stats['total_requests'] * stats['error_rate'] / 100),
                "requests": stats['total_requests']
            }
            for endpoint, stats in error_endpoints
        ],
        "all_endpoints": all_stats,
        "timestamp": datetime.utcnow().isoformat()
    }


# Middleware para coletar métricas
from starlette.middleware.base import BaseHTTPMiddleware

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect API metrics."""

    async def dispatch(self, request: Request, call_next):
        """Collect metrics for each request."""
        start_time = time.perf_counter()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        endpoint = f"{request.method} {request.url.path}"
        metrics_collector.record_request(endpoint, duration_ms, response.status_code)

        # Add headers
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

        return response
```

---

## 🔧 Scripts de Monitoramento

### Script 1: Health Check Completo

```bash
#!/bin/bash
# backend-hormonia/scripts/health_check.sh

echo "=== Health Check - Backend Hormonia ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# 1. Database Connection Pool
echo "📊 Database Connection Pool:"
curl -s http://localhost:8000/monitoring/database/pool-status | jq '.pool_metrics'
echo ""

# 2. Query Performance
echo "⚡ Query Performance:"
curl -s http://localhost:8000/monitoring/database/query-stats | jq '.summary'
echo ""

# 3. Redis Latency
echo "🔴 Redis Latency:"
curl -s http://localhost:8000/monitoring/redis/latency | jq '{
  set_avg: .set_operation.avg_ms,
  get_avg: .get_operation.avg_ms,
  alerts: .alerts
}'
echo ""

# 4. API Performance
echo "🚀 API Performance (Top 5 Slow):"
curl -s http://localhost:8000/monitoring/api/endpoints | jq '.slow_endpoints[:5]'
echo ""

# 5. System Resources
echo "💻 System Resources:"
echo "  CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
echo "  Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "  Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 " used)"}')"
echo ""

echo "=== End Health Check ==="
```

### Script 2: Slow Query Analyzer

```bash
#!/bin/bash
# backend-hormonia/scripts/analyze_slow_queries.sh

echo "=== Slow Query Analysis ==="
echo ""

# Get slow queries from API
SLOW_QUERIES=$(curl -s http://localhost:8000/monitoring/database/query-stats | jq -r '.slowest_queries')

echo "📈 Top 10 Slowest Queries:"
echo "$SLOW_QUERIES" | jq -r '.[] | "\(.duration_ms)ms - \(.query)"'
echo ""

# Generate recommendations
echo "💡 Recommendations:"
echo "$SLOW_QUERIES" | jq -r '.[] | select(.duration_ms > 1000) | "⚠️  Query taking \(.duration_ms)ms - Consider adding index"'
echo ""

# Check for N+1 patterns
echo "🔍 Potential N+1 Queries:"
echo "$SLOW_QUERIES" | jq -r '.[] | select(.row_count > 100) | "⚠️  Query returned \(.row_count) rows - Check for N+1 pattern"'
```

### Script 3: Performance Baseline

```bash
#!/bin/bash
# backend-hormonia/scripts/performance_baseline.sh

echo "=== Creating Performance Baseline ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# Run load test
echo "Running load test (100 requests)..."
ab -n 100 -c 10 http://localhost:8000/api/v2/patients/ > /tmp/ab_results.txt

# Extract metrics
echo "📊 Baseline Metrics:"
echo "  Requests/sec: $(grep 'Requests per second' /tmp/ab_results.txt | awk '{print $4}')"
echo "  Time/request: $(grep 'Time per request' /tmp/ab_results.txt | head -1 | awk '{print $4}')ms"
echo "  95th percentile: $(grep '95%' /tmp/ab_results.txt | awk '{print $2}')ms"
echo ""

# Save to file
BASELINE_FILE="performance_baseline_$(date +%Y%m%d_%H%M%S).json"
cat > "$BASELINE_FILE" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "database": $(curl -s http://localhost:8000/monitoring/database/query-stats | jq '.summary'),
  "redis": $(curl -s http://localhost:8000/monitoring/redis/latency),
  "api": $(curl -s http://localhost:8000/monitoring/api/endpoints | jq '.summary')
}
EOF

echo "✅ Baseline saved to: $BASELINE_FILE"
```

---

## 📈 Alertas e Thresholds

### Configuração de Alertas

```python
# backend-hormonia/app/monitoring/alerts.py
"""
Performance alerts configuration.
"""
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertThreshold:
    """Alert threshold configuration."""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    unit: str
    description: str


# Thresholds de alerta
ALERT_THRESHOLDS = [
    # Database
    AlertThreshold(
        metric_name="db_pool_utilization",
        warning_threshold=80.0,
        critical_threshold=90.0,
        unit="%",
        description="Database connection pool utilization"
    ),
    AlertThreshold(
        metric_name="db_query_avg_duration",
        warning_threshold=100.0,
        critical_threshold=500.0,
        unit="ms",
        description="Average database query duration"
    ),
    AlertThreshold(
        metric_name="db_slow_query_rate",
        warning_threshold=5.0,
        critical_threshold=10.0,
        unit="%",
        description="Percentage of slow queries (>1s)"
    ),

    # Redis
    AlertThreshold(
        metric_name="redis_latency_avg",
        warning_threshold=10.0,
        critical_threshold=30.0,
        unit="ms",
        description="Average Redis operation latency"
    ),
    AlertThreshold(
        metric_name="redis_memory_usage",
        warning_threshold=500.0,
        critical_threshold=800.0,
        unit="MB",
        description="Redis memory usage"
    ),

    # API
    AlertThreshold(
        metric_name="api_response_time_p95",
        warning_threshold=200.0,
        critical_threshold=500.0,
        unit="ms",
        description="API response time (95th percentile)"
    ),
    AlertThreshold(
        metric_name="api_error_rate",
        warning_threshold=1.0,
        critical_threshold=5.0,
        unit="%",
        description="API error rate (4xx/5xx responses)"
    ),
]


def check_threshold(metric_name: str, value: float) -> Optional[dict]:
    """
    Check if metric value exceeds thresholds.

    Args:
        metric_name: Name of the metric
        value: Current metric value

    Returns:
        Alert dict if threshold exceeded, None otherwise
    """
    threshold = next(
        (t for t in ALERT_THRESHOLDS if t.metric_name == metric_name),
        None
    )

    if not threshold:
        return None

    if value >= threshold.critical_threshold:
        logger.error(
            f"CRITICAL ALERT: {threshold.description} = {value}{threshold.unit} "
            f"(threshold: {threshold.critical_threshold}{threshold.unit})"
        )
        return {
            "severity": AlertSeverity.CRITICAL.value,
            "metric": metric_name,
            "value": value,
            "threshold": threshold.critical_threshold,
            "unit": threshold.unit,
            "description": threshold.description
        }

    elif value >= threshold.warning_threshold:
        logger.warning(
            f"WARNING: {threshold.description} = {value}{threshold.unit} "
            f"(threshold: {threshold.warning_threshold}{threshold.unit})"
        )
        return {
            "severity": AlertSeverity.WARNING.value,
            "metric": metric_name,
            "value": value,
            "threshold": threshold.warning_threshold,
            "unit": threshold.unit,
            "description": threshold.description
        }

    return None


async def check_all_metrics() -> List[dict]:
    """
    Check all performance metrics against thresholds.

    Returns:
        List of active alerts
    """
    from app.monitoring.database_metrics import get_pool_status, get_query_stats
    from app.monitoring.redis_metrics import get_redis_latency, get_redis_memory
    from app.monitoring.api_metrics import get_endpoint_metrics

    alerts = []

    # Check database metrics
    pool_status = await get_pool_status()
    if alert := check_threshold("db_pool_utilization", pool_status['pool_metrics']['utilization_percent']):
        alerts.append(alert)

    query_stats = await get_query_stats()
    if alert := check_threshold("db_query_avg_duration", query_stats['summary']['avg_duration_ms']):
        alerts.append(alert)
    if alert := check_threshold("db_slow_query_rate", query_stats['summary']['slow_query_percentage']):
        alerts.append(alert)

    # Check Redis metrics
    redis_latency = await get_redis_latency()
    if alert := check_threshold("redis_latency_avg", redis_latency['get_operation']['avg_ms']):
        alerts.append(alert)

    redis_memory = await get_redis_memory()
    if alert := check_threshold("redis_memory_usage", redis_memory['memory']['used_mb']):
        alerts.append(alert)

    # Check API metrics
    api_metrics = await get_endpoint_metrics()
    # Calcular P95 médio
    p95_values = [stats['p95_ms'] for stats in api_metrics['all_endpoints'].values() if stats]
    if p95_values:
        avg_p95 = sum(p95_values) / len(p95_values)
        if alert := check_threshold("api_response_time_p95", avg_p95):
            alerts.append(alert)

    return alerts
```

---

## 🎯 Checklist de Implementação

### 1. Adicionar ao main.py

```python
# backend-hormonia/app/main.py

from app.monitoring.database_metrics import router as db_metrics_router
from app.monitoring.redis_metrics import router as redis_metrics_router
from app.monitoring.api_metrics import router as api_metrics_router, MetricsMiddleware

# Add monitoring routers
app.include_router(db_metrics_router)
app.include_router(redis_metrics_router)
app.include_router(api_metrics_router)

# Add metrics middleware
app.add_middleware(MetricsMiddleware)
```

### 2. Configurar Cron Job

```bash
# Adicionar ao crontab
# Health check a cada 5 minutos
*/5 * * * * /path/to/backend-hormonia/scripts/health_check.sh >> /var/log/hormonia_health.log 2>&1

# Baseline diário às 2am
0 2 * * * /path/to/backend-hormonia/scripts/performance_baseline.sh >> /var/log/hormonia_baseline.log 2>&1
```

### 3. Integrar com Grafana (opcional)

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'hormonia_backend'
    metrics_path: '/monitoring/metrics'
    static_configs:
      - targets: ['localhost:8000']
```

---

## 📚 Referências

1. [FastAPI Monitoring Best Practices](https://fastapi.tiangolo.com/advanced/monitoring/)
2. [PostgreSQL Performance Monitoring](https://www.postgresql.org/docs/current/monitoring.html)
3. [Redis Monitoring Guide](https://redis.io/docs/management/monitoring/)

---

*Gerado automaticamente em 2025-11-30*
