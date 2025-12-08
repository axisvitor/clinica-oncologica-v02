# Monitoring Setup Guide

## Overview

Sistema completo de observabilidade com Prometheus, Grafana, AlertManager e structured logging.

## Componentes

### 1. Prometheus Metrics

**Localização:** `app/monitoring/metrics.py`

#### Métricas de Segurança

```python
from app.monitoring import (
    failed_auth_total,
    unauthorized_access_total,
    rate_limit_hits_total,
    webhook_signature_failures_total,
    sql_injection_attempts_total,
    csrf_failures_total
)

# Track failed authentication
failed_auth_total.labels(method="jwt", reason="invalid_token").inc()

# Track unauthorized access
unauthorized_access_total.labels(
    endpoint="/api/v2/admin",
    role="patient",
    required_role="admin"
).inc()

# Track rate limiting
rate_limit_hits_total.labels(
    endpoint="/api/v2/quiz",
    tier="authenticated"
).inc()
```

#### Métricas de Performance

```python
from app.monitoring import (
    track_request_duration,
    track_db_query,
    track_cache_access,
    n1_query_detected_total
)

# Track HTTP request duration
with track_request_duration("GET", "/api/v2/patients", 200):
    result = await get_patients()

# Track database query
with track_db_query("SELECT", "patients"):
    patients = session.query(Patient).all()

# Track cache performance
track_cache_access("redis", hits=95, misses=5)

# Detect N+1 queries
n1_query_detected_total.labels(
    endpoint="/api/v2/patients",
    model="Patient"
).inc()
```

#### Métricas de Negócio

```python
from app.monitoring import (
    track_saga_execution,
    patient_created_total,
    webhook_processed_total
)

# Track saga execution
with track_saga_execution("patient_onboarding", "success"):
    await saga.execute()

# Track business events
patient_created_total.labels(source="web").inc()
webhook_processed_total.labels(
    source="evolution",
    event_type="message",
    status="success"
).inc()
```

### 2. Structured Logging

**Localização:** `app/monitoring/logging_config.py`

#### Configuração

```python
from app.monitoring import configure_structured_logging

# Configure on application startup
configure_structured_logging(
    log_level="INFO",
    log_file="/var/log/hormonia/app.log"
)
```

#### Uso

```python
from app.monitoring import (
    get_structured_logger,
    log_security_event,
    log_performance_event,
    log_business_event
)

logger = get_structured_logger(__name__)

# Log security event
log_security_event(
    logger=logger,
    event_type="failed_auth",
    severity="high",
    details={
        "method": "jwt",
        "reason": "invalid_token",
        "endpoint": "/api/v2/login"
    },
    user_id=123,
    ip_address="192.168.1.100"
)

# Log performance event
log_performance_event(
    logger=logger,
    event_type="slow_query",
    duration_ms=1500,
    details={
        "query": "SELECT * FROM patients",
        "table": "patients"
    },
    threshold_exceeded=True
)

# Log business event
log_business_event(
    logger=logger,
    event_type="patient_created",
    entity_type="patient",
    entity_id=456,
    details={
        "source": "web",
        "onboarding_type": "standard"
    },
    user_id=789
)
```

### 3. Grafana Dashboards

**Localização:** `monitoring/grafana/dashboards/`

#### Dashboards Disponíveis

1. **Saga Monitoring** (`saga_monitoring.json`)
   - Success rate
   - Execution rate
   - Compensation rate
   - Duration percentiles (p50, p95, p99)
   - Failures by type

2. **Performance Monitoring** (`performance_monitoring.json`)
   - HTTP response time (p95, p99)
   - Request rate by status
   - Database query duration
   - Cache hit rate
   - N+1 query detections
   - Error rates

3. **Security Monitoring** (`security_monitoring.json`)
   - Failed authentication attempts
   - Unauthorized access
   - SQL injection attempts
   - CSRF failures
   - Webhook signature failures
   - Rate limit hits

### 4. Prometheus Alerts

**Localização:** `monitoring/prometheus/alert_rules.yml`

#### Alertas Configurados

**Segurança:**
- High failed auth rate (>10/sec for 5m)
- SQL injection attempts (any in 1m)
- Webhook signature failures (>5/sec for 5m)
- Unauthorized access spike (>20/sec for 5m)

**Performance:**
- High response time (p95 > 2s for 5m)
- Slow database queries (p95 > 1s for 5m)
- Low cache hit rate (<70% for 10m)
- N+1 query detected (>1/sec for 2m)
- High error rate (>5% for 5m)

**Negócio:**
- High saga failure rate (>10% for 10m)
- Saga compensation spike (>5/sec for 5m)
- Long-running sagas (p95 > 60s for 10m)
- Webhook processing failures (>10% for 5m)

## Setup

### 1. Instalar Dependências

```bash
pip install prometheus-client python-json-logger
```

### 2. Configurar Aplicação

```python
# In main.py or app initialization
from app.monitoring import configure_structured_logging
from app.middleware.prometheus_middleware import PrometheusMiddleware
from app.api.v2.metrics import router as metrics_router

# Configure logging
configure_structured_logging(log_level="INFO")

# Add Prometheus middleware
app.add_middleware(PrometheusMiddleware)

# Add metrics endpoint
app.include_router(metrics_router)
```

### 3. Iniciar Stack de Monitoring

```bash
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

### 4. Acessar Interfaces

- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (admin/admin)
- **AlertManager:** http://localhost:9093
- **Metrics Endpoint:** http://localhost:8000/metrics

## Configuração de Alertas

### Slack Integration

1. Create Slack webhook URL
2. Set environment variable:
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
   ```

### Email Alerts

Configure in `monitoring/alertmanager/config.yml`:

```yaml
email_configs:
  - to: 'ops-team@example.com'
    from: 'alertmanager@example.com'
    smarthost: 'smtp.example.com:587'
    auth_username: '${SMTP_USERNAME}'
    auth_password: '${SMTP_PASSWORD}'
```

## Best Practices

### 1. Metric Naming

- Use consistent naming: `{namespace}_{metric}_{unit}`
- Examples: `http_request_duration_seconds`, `saga_total`

### 2. Label Cardinality

- Keep label cardinality low (<1000 unique combinations)
- Avoid user IDs or timestamps as labels
- Use aggregation for high-cardinality data

### 3. Alert Thresholds

- Set realistic thresholds based on baseline metrics
- Use percentiles (p95, p99) for latency alerts
- Add `for` duration to reduce false positives

### 4. Dashboard Organization

- Group related metrics together
- Use consistent color schemes
- Add alert thresholds as annotations
- Include documentation links

## Troubleshooting

### Metrics Not Appearing

1. Check Prometheus targets: http://localhost:9090/targets
2. Verify metrics endpoint: http://localhost:8000/metrics
3. Check firewall rules
4. Review Prometheus logs:
   ```bash
   docker logs hormonia-prometheus
   ```

### Alerts Not Firing

1. Check alert rules: http://localhost:9090/alerts
2. Review AlertManager config: http://localhost:9093
3. Verify notification channels
4. Check AlertManager logs:
   ```bash
   docker logs hormonia-alertmanager
   ```

### High Cardinality Issues

1. Review metric labels
2. Use aggregation or recording rules
3. Reduce label combinations
4. Consider using exemplars for high-cardinality data

## Performance Impact

- **Metrics Collection:** <1ms overhead per request
- **Memory Usage:** ~50MB for 10k active metrics
- **Storage:** ~1GB per million samples (30d retention)

## Maintenance

### Daily

- Review critical alerts
- Check dashboard health
- Monitor storage usage

### Weekly

- Review metric cardinality
- Optimize slow queries
- Update alert thresholds

### Monthly

- Audit unused metrics
- Review retention policies
- Update dashboards
- Test backup/restore

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [AlertManager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
