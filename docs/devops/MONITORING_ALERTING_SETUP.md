# Monitoring & Alerting Setup Guide
**Project:** Clínica Oncológica v02
**Platform:** Railway + External Monitoring Stack
**Monitoring Grade:** Enterprise-Level
**Last Updated:** October 9, 2025

## Overview

This guide establishes comprehensive monitoring and alerting for the Clínica Oncológica v02 application, providing enterprise-grade observability with proactive issue detection and automated response capabilities.

## Current Monitoring Architecture

### Existing Monitoring Stack ✅ EXCELLENT
```yaml
Current Components:
├── Application Monitoring
│   ├── Prometheus (Metrics Collection)
│   ├── Grafana (Visualization)
│   └── Custom APM (Application Performance)
├── Infrastructure Monitoring
│   ├── Railway Native Metrics
│   ├── PostgreSQL Exporter
│   ├── Redis Exporter
│   └── Node Exporter
├── Error Tracking
│   ├── Sentry Integration
│   ├── Structured Logging
│   └── Custom Error Handlers
└── Security Monitoring
    ├── Audit Logging
    ├── Authentication Monitoring
    └── Security Event Tracking
```

### Monitoring Features Already Implemented
1. **Health Check System**: Multi-layer health validation
2. **APM with Apdex Scoring**: User experience monitoring (0.5s threshold)
3. **Resource Monitoring**: CPU (80%) + Memory (85%) thresholds
4. **Database Performance**: Slow query detection (1s threshold)
5. **Redis Performance**: Cache hit rate monitoring
6. **Security Auditing**: Authentication and authorization events

## 1. Application Performance Monitoring (APM)

### Current APM Configuration
```python
# Backend APM Configuration (app/config.py)
APM_APDEX_THRESHOLD: float = 0.5  # 500ms
APM_SLOW_REQUEST_THRESHOLD: float = 1.0  # 1 second
MONITORING_ENABLED: bool = True
MONITORING_DEBUG: bool = False
```

### Enhanced APM Implementation

#### A. Request Performance Tracking
```python
# app/middleware/monitoring.py
import time
from fastapi import Request, Response
from app.services.monitoring import MonitoringService

async def performance_monitoring_middleware(request: Request, call_next):
    start_time = time.time()

    # Add request ID for tracing
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)

    duration = time.time() - start_time

    # Calculate Apdex score
    if duration <= 0.5:  # Satisfied
        apdex_rating = "satisfied"
    elif duration <= 2.0:  # Tolerating (4x threshold)
        apdex_rating = "tolerating"
    else:  # Frustrated
        apdex_rating = "frustrated"

    # Log performance metrics
    monitoring_service = MonitoringService()
    monitoring_service.record_request({
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "duration": duration,
        "status_code": response.status_code,
        "apdex_rating": apdex_rating
    })

    return response
```

#### B. Database Performance Monitoring
```python
# app/middleware/database_monitoring.py
from sqlalchemy import event
from sqlalchemy.engine import Engine
import logging

logger = logging.getLogger("database.performance")

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time

    if total > 1.0:  # Slow query threshold
        logger.warning(
            "Slow query detected",
            extra={
                "duration": total,
                "query": statement[:200],  # Truncate for logging
                "event_type": "slow_query"
            }
        )
```

### Frontend Performance Monitoring

#### A. Web Vitals Tracking
```typescript
// src/utils/performance-monitoring.ts
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

interface PerformanceMetric {
  name: string;
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  timestamp: number;
}

class PerformanceMonitor {
  private metrics: PerformanceMetric[] = [];
  private apiEndpoint = '/api/v1/monitoring/frontend';

  init() {
    // Core Web Vitals
    getCLS(this.sendMetric.bind(this));
    getFID(this.sendMetric.bind(this));
    getFCP(this.sendMetric.bind(this));
    getLCP(this.sendMetric.bind(this));
    getTTFB(this.sendMetric.bind(this));
  }

  private sendMetric(metric: any) {
    const performanceMetric: PerformanceMetric = {
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
      timestamp: Date.now()
    };

    this.metrics.push(performanceMetric);

    // Send to backend
    fetch(this.apiEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(performanceMetric)
    }).catch(console.error);
  }
}

export const performanceMonitor = new PerformanceMonitor();
```

## 2. Infrastructure Monitoring Setup

### Railway Native Monitoring
```yaml
# Railway provides built-in monitoring for:
Metrics Available:
├── CPU Usage (%)
├── Memory Usage (MB)
├── Network I/O (bytes)
├── Request Count
├── Response Time (ms)
├── Error Rate (%)
└── Deployment Status
```

### External Monitoring Stack

#### A. Prometheus Configuration
```yaml
# monitoring/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  # Railway Application Metrics
  - job_name: 'railway-backend'
    scrape_interval: 30s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['backend.railway.app:443']
    scheme: https

  # PostgreSQL Metrics
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Redis Metrics
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  # System Metrics
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

#### B. Grafana Dashboard Configuration
```json
{
  "dashboard": {
    "title": "Clínica Oncológica - Production Monitoring",
    "panels": [
      {
        "title": "Application Performance",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "Request Rate"
          },
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th Percentile Response Time"
          }
        ]
      },
      {
        "title": "Apdex Score",
        "type": "singlestat",
        "targets": [
          {
            "expr": "(rate(http_requests_satisfied_total[5m]) + rate(http_requests_tolerating_total[5m]) * 0.5) / rate(http_requests_total[5m])",
            "legendFormat": "Apdex Score"
          }
        ],
        "thresholds": "0.7,0.85"
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m]) * 100",
            "legendFormat": "5xx Error Rate %"
          }
        ]
      }
    ]
  }
}
```

## 3. Alerting Configuration

### Alert Rules Definition
```yaml
# monitoring/prometheus/alerts.yml
groups:
- name: application
  rules:
  # High Error Rate Alert
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100 > 5
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }}% for more than 2 minutes"

  # Slow Response Time Alert
  - alert: SlowResponseTime
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "Slow response time detected"
      description: "95th percentile response time is {{ $value }}s"

  # Low Apdex Score Alert
  - alert: LowApdexScore
    expr: (rate(http_requests_satisfied_total[5m]) + rate(http_requests_tolerating_total[5m]) * 0.5) / rate(http_requests_total[5m]) < 0.8
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Poor user experience detected"
      description: "Apdex score is {{ $value }} (below 0.8)"

- name: infrastructure
  rules:
  # High CPU Usage Alert
  - alert: HighCPUUsage
    expr: (100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)) > 80
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU usage detected"
      description: "CPU usage is {{ $value }}% on {{ $labels.instance }}"

  # High Memory Usage Alert
  - alert: HighMemoryUsage
    expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High memory usage detected"
      description: "Memory usage is {{ $value }}% on {{ $labels.instance }}"

  # Database Connection Alert
  - alert: DatabaseConnectionFailure
    expr: postgres_up == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Database connection failed"
      description: "PostgreSQL database is not responding"

  # Redis Connection Alert
  - alert: RedisConnectionFailure
    expr: redis_up == 0
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "Redis connection failed"
      description: "Redis cache is not responding"
```

### Alertmanager Configuration
```yaml
# monitoring/prometheus/alertmanager.yml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@clinica-oncologica.com'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
- name: 'web.hook'
  email_configs:
  - to: 'devops@clinica-oncologica.com'
    subject: 'Alert: {{ .GroupLabels.alertname }}'
    body: |
      {{ range .Alerts }}
      Alert: {{ .Annotations.summary }}
      Description: {{ .Annotations.description }}
      Labels: {{ .Labels }}
      {{ end }}

  slack_configs:
  - api_url: 'YOUR_SLACK_WEBHOOK_URL'
    channel: '#alerts'
    title: 'Alert: {{ .GroupLabels.alertname }}'
    text: |
      {{ range .Alerts }}
      {{ .Annotations.summary }}
      {{ .Annotations.description }}
      {{ end }}

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

## 4. Log Management & Analysis

### Structured Logging Configuration
```python
# app/utils/logging.py
import structlog
import logging
from typing import Dict, Any

def configure_structured_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

class ApplicationLogger:
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)

    def log_request(self, request_data: Dict[str, Any]):
        self.logger.info(
            "Request processed",
            **request_data,
            event_type="request"
        )

    def log_database_operation(self, operation_data: Dict[str, Any]):
        self.logger.info(
            "Database operation",
            **operation_data,
            event_type="database"
        )

    def log_authentication_event(self, auth_data: Dict[str, Any]):
        self.logger.info(
            "Authentication event",
            **auth_data,
            event_type="authentication"
        )
```

### Log Aggregation Setup
```python
# app/monitoring/log_aggregator.py
import json
import asyncio
from typing import List, Dict
from datetime import datetime, timedelta

class LogAggregator:
    def __init__(self):
        self.log_buffer: List[Dict] = []
        self.flush_interval = 60  # seconds

    async def start_aggregation(self):
        while True:
            await asyncio.sleep(self.flush_interval)
            await self.flush_logs()

    async def flush_logs(self):
        if not self.log_buffer:
            return

        # Aggregate logs by type and severity
        aggregated = self.aggregate_logs(self.log_buffer)

        # Send to monitoring service
        await self.send_aggregated_logs(aggregated)

        # Clear buffer
        self.log_buffer.clear()

    def aggregate_logs(self, logs: List[Dict]) -> Dict:
        aggregation = {
            "timestamp": datetime.utcnow().isoformat(),
            "period_minutes": self.flush_interval / 60,
            "summary": {
                "total_logs": len(logs),
                "error_count": 0,
                "warning_count": 0,
                "info_count": 0
            },
            "events": {}
        }

        for log in logs:
            level = log.get("level", "info")
            event_type = log.get("event_type", "general")

            # Count by level
            aggregation["summary"][f"{level.lower()}_count"] += 1

            # Group by event type
            if event_type not in aggregation["events"]:
                aggregation["events"][event_type] = {
                    "count": 0,
                    "levels": {}
                }

            aggregation["events"][event_type]["count"] += 1
            aggregation["events"][event_type]["levels"][level] = \
                aggregation["events"][event_type]["levels"].get(level, 0) + 1

        return aggregation
```

## 5. Security Monitoring

### Authentication Monitoring
```python
# app/services/security_monitoring.py
from typing import Dict, Any
from datetime import datetime, timedelta
from app.utils.logging import ApplicationLogger

class SecurityMonitor:
    def __init__(self):
        self.logger = ApplicationLogger("security")
        self.failed_attempts = {}  # Track failed login attempts

    def log_authentication_attempt(self, event_data: Dict[str, Any]):
        """Log all authentication attempts for monitoring."""
        self.logger.log_authentication_event({
            "timestamp": datetime.utcnow().isoformat(),
            "event": "authentication_attempt",
            "success": event_data.get("success", False),
            "user_id": event_data.get("user_id"),
            "email": event_data.get("email"),
            "ip_address": event_data.get("ip_address"),
            "user_agent": event_data.get("user_agent"),
            "method": event_data.get("method", "password")
        })

        # Track failed attempts for rate limiting
        if not event_data.get("success"):
            self.track_failed_attempt(
                event_data.get("ip_address"),
                event_data.get("email")
            )

    def track_failed_attempt(self, ip_address: str, email: str):
        """Track failed login attempts for security monitoring."""
        current_time = datetime.utcnow()

        # Clean old attempts (older than 1 hour)
        cutoff_time = current_time - timedelta(hours=1)

        key = f"{ip_address}:{email}"
        if key not in self.failed_attempts:
            self.failed_attempts[key] = []

        # Add current attempt
        self.failed_attempts[key].append(current_time)

        # Remove old attempts
        self.failed_attempts[key] = [
            attempt for attempt in self.failed_attempts[key]
            if attempt > cutoff_time
        ]

        # Check for suspicious activity
        if len(self.failed_attempts[key]) >= 5:
            self.logger.logger.warning(
                "Suspicious authentication activity detected",
                ip_address=ip_address,
                email=email,
                attempt_count=len(self.failed_attempts[key]),
                event_type="security_alert"
            )
```

## 6. Custom Metrics & Dashboards

### Business Metrics Collection
```python
# app/services/business_metrics.py
from typing import Dict
from datetime import datetime

class BusinessMetricsCollector:
    def __init__(self):
        self.metrics = {}

    def record_user_action(self, action: str, user_id: str, metadata: Dict = None):
        """Record user actions for business intelligence."""
        metric_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "metadata": metadata or {}
        }

        # Store metric (would typically go to a time-series database)
        self.store_metric("user_action", metric_data)

    def record_system_event(self, event: str, severity: str, details: Dict = None):
        """Record system events for operational monitoring."""
        metric_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "severity": severity,
            "details": details or {}
        }

        self.store_metric("system_event", metric_data)

    def store_metric(self, metric_type: str, data: Dict):
        """Store metric data (implementation depends on chosen storage)."""
        # This would typically send to Prometheus, InfluxDB, or similar
        pass
```

### Custom Grafana Dashboard
```json
{
  "dashboard": {
    "title": "Clínica Oncológica - Business Metrics",
    "panels": [
      {
        "title": "Active Users",
        "type": "graph",
        "targets": [
          {
            "expr": "increase(user_login_total[1h])",
            "legendFormat": "Hourly Logins"
          }
        ]
      },
      {
        "title": "Patient Operations",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(patient_created_total[5m])",
            "legendFormat": "Patient Registrations/min"
          },
          {
            "expr": "rate(appointment_scheduled_total[5m])",
            "legendFormat": "Appointments Scheduled/min"
          }
        ]
      },
      {
        "title": "System Health Score",
        "type": "singlestat",
        "targets": [
          {
            "expr": "(apdex_score * 0.4) + (uptime_percentage * 0.3) + (error_rate_inverted * 0.3)",
            "legendFormat": "Health Score"
          }
        ],
        "thresholds": "70,85"
      }
    ]
  }
}
```

## 7. Implementation Steps

### Phase 1: Core Monitoring (Week 1)
1. **Deploy Monitoring Stack**
   ```bash
   # Deploy monitoring infrastructure
   docker-compose -f docker-compose.monitoring.yml up -d

   # Verify all services are running
   docker-compose ps
   ```

2. **Configure Prometheus Targets**
   - Add Railway application endpoints
   - Configure service discovery
   - Set up metric collection

3. **Set Up Basic Dashboards**
   - Import pre-built Grafana dashboards
   - Configure data sources
   - Set up basic alert rules

### Phase 2: Advanced Features (Week 2)
1. **Implement Custom Metrics**
   - Add business metrics collection
   - Configure custom exporters
   - Set up log aggregation

2. **Configure Alerting**
   - Set up Alertmanager
   - Configure notification channels
   - Test alert routing

### Phase 3: Optimization (Week 3)
1. **Performance Tuning**
   - Optimize metric collection frequency
   - Configure retention policies
   - Set up automated cleanup

2. **Advanced Analytics**
   - Implement predictive alerting
   - Set up trend analysis
   - Configure capacity planning metrics

## 8. Maintenance & Operations

### Daily Operations Checklist
- [ ] Check dashboard for any red alerts
- [ ] Review error rate trends
- [ ] Verify backup completion
- [ ] Check resource utilization trends

### Weekly Operations Checklist
- [ ] Review alert accuracy and adjust thresholds
- [ ] Analyze performance trends
- [ ] Update monitoring documentation
- [ ] Test alert notification channels

### Monthly Operations Checklist
- [ ] Review and optimize metric retention policies
- [ ] Analyze cost vs. value of monitoring data
- [ ] Update monitoring tools and configurations
- [ ] Conduct monitoring system health check

## 9. Troubleshooting Guide

### Common Issues & Solutions

#### High Memory Usage on Monitoring Stack
```bash
# Check Prometheus memory usage
docker stats prometheus

# Optimize Prometheus configuration
# In prometheus.yml:
global:
  scrape_interval: 30s  # Increase from 15s
  evaluation_interval: 30s

# Reduce retention period
storage:
  tsdb:
    retention.time: 15d  # Reduce from 30d
```

#### Missing Metrics
```bash
# Check if application exposes metrics endpoint
curl https://backend.railway.app/metrics

# Verify Prometheus can scrape target
curl -G 'http://prometheus:9090/api/v1/targets'
```

#### Alert Fatigue
```yaml
# Optimize alert rules to reduce false positives
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100 > 5
  for: 5m  # Increase from 2m to reduce noise
```

---

**Monitoring Setup Version**: 1.0
**Implementation Timeline**: 3 weeks
**Next Review**: January 9, 2026
**Estimated Monthly Cost**: $50-100 (monitoring infrastructure)