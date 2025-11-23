# Celery Task Monitoring Guide

**Comprehensive monitoring for Celery tasks using Flower, Prometheus, and Grafana**

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Flower UI](#flower-ui)
- [Prometheus Metrics](#prometheus-metrics)
- [Grafana Dashboards](#grafana-dashboards)
- [Alert Rules](#alert-rules)
- [Health Checks](#health-checks)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## Overview

This monitoring stack provides real-time visibility into Celery task execution, queue health, and worker performance.

### Components

1. **Flower** - Web-based Celery monitoring UI
2. **Prometheus** - Metrics collection and storage
3. **Grafana** - Visualization and dashboards
4. **Queue Monitor** - Real-time queue length tracking
5. **Health Checks** - API endpoints for service health

### Key Features

- ✅ Real-time task monitoring
- ✅ Historical metrics and trends
- ✅ Queue length tracking
- ✅ Failure rate alerts
- ✅ Performance profiling
- ✅ Worker capacity monitoring

---

## Architecture

```
┌─────────────┐
│ Celery      │ ──► Metrics ──► ┌─────────────┐
│ Worker      │                 │ Prometheus  │
└─────────────┘                 └──────┬──────┘
                                       │
┌─────────────┐                        │
│ Celery Beat │ ──► Metrics ───────────┤
└─────────────┘                        │
                                       ▼
┌─────────────┐                ┌──────────────┐
│ Redis Queue │ ──► Metrics ──►│   Grafana    │
└─────────────┘                │  (Dashboard) │
                               └──────────────┘
┌─────────────┐
│   Flower    │ ──► UI for task inspection
└─────────────┘
```

---

## Quick Start

### 1. Deploy Monitoring Stack

```bash
# Development mode
cd backend-hormonia
./scripts/deploy_celery_monitoring.sh --dev

# Production mode (with authentication)
./scripts/deploy_celery_monitoring.sh --production
```

### 2. Access Monitoring Tools

- **Flower UI**: http://localhost:5555
  - Default credentials: `admin:admin123`
  - Real-time task monitoring

- **Prometheus**: http://localhost:9090
  - Metrics database and queries
  - Target health status

- **Grafana**: http://localhost:3000
  - Default credentials: `admin:admin`
  - Celery dashboard pre-configured

### 3. Verify Deployment

```bash
# Check all services are running
docker-compose -f monitoring/docker-compose.monitoring.yml ps

# View Flower logs
docker-compose -f monitoring/docker-compose.monitoring.yml logs -f flower

# Test health endpoint
curl http://localhost:8000/health/celery
```

---

## Flower UI

### Overview

Flower provides a web-based interface for monitoring Celery tasks in real-time.

### Features

#### 1. Task Monitoring
- **Active Tasks**: Currently executing tasks
- **Scheduled Tasks**: Tasks waiting in queue
- **Task History**: Recently completed tasks
- **Task Details**: Arguments, results, traceback

#### 2. Worker Management
- **Worker List**: All connected workers
- **Worker Stats**: CPU, memory usage
- **Worker Control**: Shutdown, restart workers
- **Pool Information**: Thread/process pool stats

#### 3. Broker Monitoring
- **Queue Lengths**: Tasks pending per queue
- **Message Rates**: Tasks/second
- **Connection Status**: Redis broker health

### Usage Examples

#### View Active Tasks
1. Navigate to http://localhost:5555/tasks
2. Filter by task state: SUCCESS, FAILURE, PENDING
3. Click task ID for details

#### Monitor Specific Task
```python
# Get task ID from application
from app.tasks import send_whatsapp_message

result = send_whatsapp_message.delay(patient_id=123, message="Test")
task_id = result.id  # Use this in Flower
```

#### Revoke Stuck Task
1. Go to http://localhost:5555/tasks
2. Find stuck task
3. Click "Revoke" button
4. Choose "Terminate" to force kill

### Configuration

Environment variables in `docker-compose.monitoring.yml`:

```yaml
environment:
  FLOWER_BASIC_AUTH: "admin:yourpassword"  # Change in production
  FLOWER_MAX_TASKS: 10000                  # Task history limit
  FLOWER_PERSISTENT: "true"                # Persist across restarts
  FLOWER_DB: /app/flower.db                # Database location
```

---

## Prometheus Metrics

### Available Metrics

#### Task Execution Metrics

```promql
# Total tasks executed
celery_task_total{task_name="send_whatsapp_message", status="success"}

# Task execution duration (histogram)
celery_task_duration_seconds_bucket{task_name="send_whatsapp_message"}

# Active tasks (gauge)
celery_task_active{task_name="send_whatsapp_message"}
```

#### Failure Tracking

```promql
# Total failures
celery_task_failures_total{task_name="send_whatsapp_message", exception_type="ConnectionError"}

# Task retry count
celery_task_retries_total{task_name="send_whatsapp_message", retry_count="1"}
```

#### Queue Metrics

```promql
# Queue length
celery_queue_length{queue_name="celery"}

# Worker status
celery_worker_active{worker_name="celery@worker1"}
```

### Common Queries

#### Task Success Rate (Last Hour)
```promql
sum(increase(celery_task_total{status="success"}[1h])) /
sum(increase(celery_task_total[1h])) * 100
```

#### P95 Task Duration
```promql
histogram_quantile(0.95,
  sum(rate(celery_task_duration_seconds_bucket[5m])) by (task_name, le)
)
```

#### Top 5 Failing Tasks
```promql
topk(5,
  sum by (task_name) (rate(celery_task_failures_total[1h]))
)
```

#### Average Queue Wait Time
```promql
avg(celery_queue_length) by (queue_name)
```

### Accessing Prometheus

```bash
# Query via API
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=celery_task_total'

# Check targets health
curl http://localhost:9090/api/v1/targets

# Reload configuration
curl -X POST http://localhost:9090/-/reload
```

---

## Grafana Dashboards

### Celery Monitoring Dashboard

Pre-configured dashboard with 12 panels:

#### Key Panels

1. **Task Execution Rate**
   - Tasks per minute by task type
   - Line graph, 5-minute rate

2. **Task Failure Rate**
   - Failures per minute
   - Alert threshold: >0.1/min

3. **Task Duration (P95/P99)**
   - 95th and 99th percentile
   - Identify slow tasks

4. **Active Tasks**
   - Currently executing tasks
   - Stacked by task name

5. **Queue Length**
   - Pending tasks per queue
   - Alert threshold: >1000

6. **Task Retry Rate**
   - Retries per minute
   - Indicates flaky dependencies

7. **Top Failing Tasks**
   - Table of worst offenders
   - Last hour window

8. **Slowest Tasks (P99)**
   - Table of slowest tasks
   - Duration in seconds

9. **Total Tasks (24h)**
   - Single stat with sparkline
   - Overall throughput

10. **Success Rate (24h)**
    - Percentage with color coding
    - Green >95%, Yellow 80-95%, Red <80%

11. **Active Workers**
    - Current worker count
    - Alert if <1

12. **Avg Task Duration (1h)**
    - Average execution time
    - Trend indicator

### Accessing Dashboards

1. Navigate to http://localhost:3000
2. Login: `admin` / `admin` (change in production)
3. Go to **Dashboards** → **Celery Tasks Monitoring**

### Creating Custom Panels

```json
{
  "targets": [{
    "expr": "rate(celery_task_total{task_name=\"my_task\"}[5m])",
    "legendFormat": "{{task_name}}"
  }],
  "title": "My Custom Task Rate"
}
```

---

## Alert Rules

### Configured Alerts

#### CRITICAL Alerts

**CeleryWorkerDown**
```yaml
expr: up{job="celery_worker"} == 0
for: 1m
severity: critical
```
- **Impact**: Tasks cannot be processed
- **Action**: Check worker logs, restart worker

**CeleryAllWorkersDown**
```yaml
expr: sum(celery_worker_active) == 0
for: 2m
severity: critical
```
- **Impact**: Complete system outage
- **Action**: IMMEDIATE - Check Redis, broker, containers

**CeleryTaskStuck**
```yaml
expr: celery_task_active > 0 and rate(celery_task_total[5m]) == 0
for: 10m
severity: critical
```
- **Impact**: Task deadlock
- **Action**: Review logs, revoke task

**CeleryQueueCriticalBacklog**
```yaml
expr: celery_queue_length > 5000
for: 5m
severity: critical
```
- **Impact**: Severe processing delay
- **Action**: Scale workers, investigate failures

#### WARNING Alerts

**CeleryTaskHighFailureRate**
```yaml
expr: sum(rate(celery_task_failures_total[5m])) by (task_name) > 0.1
for: 5m
severity: warning
```
- **Impact**: Reduced success rate
- **Action**: Check task logs, review implementation

**CeleryQueueBacklog**
```yaml
expr: celery_queue_length > 1000
for: 5m
severity: warning
```
- **Impact**: Delayed processing
- **Action**: Consider scaling workers

### Alert Notification

Configure Alertmanager to send notifications:

```yaml
# monitoring/alertmanager/config.yml
receivers:
  - name: 'team-email'
    email_configs:
      - to: 'ops-team@example.com'
        from: 'alerts@example.com'
        smarthost: 'smtp.example.com:587'
```

---

## Health Checks

### API Endpoints

#### Celery Health Check

```bash
GET /health/celery
```

**Response (Healthy)**:
```json
{
  "status": "healthy",
  "workers": 3,
  "active_tasks": 12,
  "registered_tasks": 45,
  "queue_lengths": {
    "celery": 5,
    "high_priority": 0,
    "quiz_flow": 2,
    "whatsapp": 8
  },
  "total_queued": 15,
  "stats": {
    "worker1": {
      "pool": {
        "max-concurrency": 4,
        "processes": [12345, 12346, 12347, 12348]
      }
    }
  }
}
```

**Response (Unhealthy)**:
```json
{
  "status": "unhealthy",
  "error": "No active Celery workers",
  "workers": 0,
  "active_tasks": 0
}
```

### Integration with Load Balancers

```nginx
# Nginx health check
location /health/celery {
    proxy_pass http://backend:8000;
    proxy_connect_timeout 5s;
    proxy_read_timeout 5s;
}
```

### Kubernetes Probes

```yaml
livenessProbe:
  httpGet:
    path: /health/celery
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 3
```

---

## Troubleshooting

### Common Issues

#### 1. No Metrics in Prometheus

**Symptoms**: Celery metrics not appearing in Prometheus

**Solution**:
```bash
# Check if worker is exposing metrics
curl http://localhost:9090/metrics | grep celery

# Verify Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="celery_worker")'

# Check worker environment variable
docker-compose exec worker env | grep CELERY_PROMETHEUS_METRICS
```

#### 2. Flower Not Showing Tasks

**Symptoms**: Flower UI shows no tasks

**Solution**:
```bash
# Check Flower logs
docker-compose -f monitoring/docker-compose.monitoring.yml logs flower

# Verify Redis connection
docker-compose exec flower celery -A app.celery_app inspect ping

# Check broker URL
docker-compose exec flower env | grep CELERY_BROKER_URL
```

#### 3. High Queue Backlog

**Symptoms**: Queue length >1000

**Solution**:
```bash
# Scale workers
docker-compose up -d --scale worker=5

# Check worker resource usage
docker stats hormonia-worker

# Purge old tasks
docker-compose exec worker celery -A app.celery_app purge
```

#### 4. Stuck Tasks

**Symptoms**: Tasks in PENDING state for >10 minutes

**Solution**:
```bash
# List active tasks
docker-compose exec worker celery -A app.celery_app inspect active

# Revoke specific task
docker-compose exec worker celery -A app.celery_app control revoke <task-id> --terminate

# Restart workers
docker-compose restart worker
```

### Debugging Commands

```bash
# Inspect registered tasks
docker-compose exec worker celery -A app.celery_app inspect registered

# Check worker stats
docker-compose exec worker celery -A app.celery_app inspect stats

# View active queues
docker-compose exec worker celery -A app.celery_app inspect active_queues

# Monitor in real-time
docker-compose exec worker celery -A app.celery_app events
```

---

## Best Practices

### 1. Task Design

```python
# ✅ GOOD: Idempotent, trackable
@app.task(bind=True, max_retries=3)
@track_task_time
def send_email(self, user_id, template):
    try:
        # Check if already sent
        if check_email_sent(user_id, template):
            return "already_sent"

        send_email_service(user_id, template)
        mark_email_sent(user_id, template)

    except Exception as e:
        self.retry(exc=e, countdown=60)
```

### 2. Monitoring

- Set up **alerts** for critical metrics
- Review **Grafana dashboards** daily
- Monitor **queue lengths** during peak hours
- Track **failure rates** per task type

### 3. Performance

- Use **appropriate task priorities**
- Configure **worker concurrency** based on task type
- Implement **rate limiting** for external APIs
- Enable **result backends** only when needed

### 4. Scaling

```yaml
# Scale workers based on queue length
deploy:
  replicas: 3
  resources:
    limits:
      cpus: '2'
      memory: 2G
  update_config:
    parallelism: 1
    delay: 10s
```

### 5. Maintenance

```bash
# Daily health check
curl http://localhost:8000/health/celery

# Weekly: Review slow tasks
# Check Grafana "Slowest Tasks (P99)" panel

# Monthly: Clean up Flower database
docker-compose exec flower rm -f /app/flower.db
docker-compose restart flower
```

---

## Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_PROMETHEUS_METRICS` | `false` | Enable metrics export |
| `FLOWER_BASIC_AUTH` | `admin:admin123` | Flower authentication |
| `FLOWER_MAX_TASKS` | `10000` | Task history limit |
| `FLOWER_PERSISTENT` | `true` | Persist data across restarts |

### Ports

| Service | Port | Description |
|---------|------|-------------|
| Flower | 5555 | Web UI |
| Prometheus | 9090 | Metrics database |
| Grafana | 3000 | Dashboards |
| Worker Metrics | 9090 | Prometheus exporter |

### Related Documentation

- [Celery Configuration](../guides/task-configuration.md)
- [Prometheus Setup](../operations/MONITORING_SETUP_SUMMARY.md)
- [Production Runbook](../operations/PRODUCTION_RUNBOOK.md)
- [Alert Rules Reference](../../monitoring/prometheus/alerts/celery_alerts.yml)

---

**Last Updated**: January 2025
**Maintainer**: DevOps Team
**Contact**: ops-team@example.com
