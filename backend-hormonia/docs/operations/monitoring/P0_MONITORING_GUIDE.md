# P0 Critical Implementation - Monitoring & Alerting Guide

**Document Version:** 1.0
**Last Updated:** 2025-11-15
**Status:** Production Ready

## Table of Contents

- [Overview](#overview)
- [Alert Thresholds](#alert-thresholds)
- [Setup Instructions](#setup-instructions)
- [Alert Runbooks](#alert-runbooks)
- [Dashboard Guide](#dashboard-guide)
- [Troubleshooting](#troubleshooting)

---

## Overview

This monitoring infrastructure provides comprehensive post-deployment validation for P0 critical implementations:

1. **Saga Orchestration** - Timeout detection, race condition monitoring, compensation failures
2. **Event Loop Blocking** - Async/sync boundary violations, performance degradation
3. **Template Loading** - Load failures, latency monitoring, cache efficiency
4. **Performance Metrics** - HTTP latency, database query performance, error rates
5. **System Health** - Resource utilization, capacity monitoring

### Key Metrics Monitored

| Metric | Target | Critical Threshold | Component |
|--------|--------|-------------------|-----------|
| `saga_execution_duration_seconds` | <300s | >300s | Saga Orchestrator |
| `saga_timeout_count` | 0 | >0 | Saga Orchestrator |
| `async_event_loop_blocked` | 0 | >0 | Async Runtime |
| `template_load_time` | <100ms | >100ms | Template Loader |
| `http_request_duration_p95` | <200ms | >200ms | API Layer |
| `error_rate` | <1% | >1% | Application |

---

## Alert Thresholds

### Critical Alerts (P0 - Immediate Response Required)

#### Saga Orchestration

```yaml
Alert: P0_SagaTimeoutBreach
Threshold: saga_execution_duration_seconds > 300
For: 1m
Action: Page on-call engineer
Impact: Service degradation, user-facing delays
```

```yaml
Alert: P0_SagaTimeoutCount
Threshold: saga_timeout_total > 0
For: 1m
Action: Immediate investigation
Impact: Data consistency risk
```

```yaml
Alert: P0_SagaFallbackRaceCondition
Threshold: saga_fallback_race_condition_total > 0
For: 1m
Action: Emergency escalation
Impact: Critical regression, code-level bug
```

#### Event Loop Blocking

```yaml
Alert: P0_EventLoopBlocked
Threshold: async_event_loop_blocked_total > 0
For: 30s
Action: Investigate async/sync boundaries
Impact: Severe performance degradation
```

#### Template Loading

```yaml
Alert: P0_TemplateLoadingFailure
Threshold: template_loading_failed_total > 0 (5m window)
For: 1m
Action: Check template files and cache
Impact: Quiz functionality degraded
```

#### Error Rates

```yaml
Alert: P0_ErrorRateSpike
Threshold: error_rate > 1%
For: 3m
Action: Check logs and recent deployments
Impact: Service availability at risk
```

### High Priority Alerts (P0 - Response Within 15 Minutes)

```yaml
Alert: P0_HTTPRequestLatencyP95
Threshold: p95_latency > 200ms
For: 5m
Action: Performance investigation
Impact: User experience degradation
```

```yaml
Alert: P0_TemplateLoadingLatency
Threshold: template_load_p95 > 100ms
For: 5m
Action: Check cache and database
Impact: Slow quiz interactions
```

---

## Setup Instructions

### 1. Prerequisites

```bash
# Ensure Docker and Docker Compose are installed
docker --version
docker-compose --version

# Create environment configuration
cd backend-hormonia/monitoring
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `monitoring/.env`:

```bash
# Slack Integration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=alerts@hormonia.io
SMTP_PASSWORD=your-smtp-password

# PagerDuty
PAGERDUTY_P0_CRITICAL_KEY=your-pagerduty-service-key
PAGERDUTY_P0_HIGH_KEY=your-pagerduty-high-priority-key
PAGERDUTY_P0_ONCALL_KEY=your-pagerduty-oncall-key

# Alert Recipients
P0_ONCALL_EMAIL=oncall@hormonia.io
P0_TEAM_EMAIL=backend-team@hormonia.io

# Grafana
GRAFANA_ADMIN_PASSWORD=secure-password-here
```

### 3. Deploy Monitoring Stack

```bash
# Start monitoring infrastructure
docker-compose -f docker-compose.monitoring.yml up -d

# Verify services are running
docker-compose -f docker-compose.monitoring.yml ps

# Expected output:
# prometheus        Up      9090/tcp
# grafana           Up      3000/tcp
# alertmanager      Up      9093/tcp
# node-exporter     Up      9100/tcp
# postgres-exporter Up      9187/tcp
# redis-exporter    Up      9121/tcp
```

### 4. Verify Prometheus Configuration

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'

# Reload Prometheus configuration
curl -X POST http://localhost:9090/-/reload

# Verify alert rules loaded
curl http://localhost:9090/api/v1/rules | jq '.data.groups[] | {name, file}'
```

### 5. Access Dashboards

- **Grafana**: http://localhost:3000
  - Username: `admin`
  - Password: `${GRAFANA_ADMIN_PASSWORD}`

- **Prometheus**: http://localhost:9090

- **Alertmanager**: http://localhost:9093

### 6. Import P0 Dashboard

1. Login to Grafana (http://localhost:3000)
2. Navigate to **Dashboards** → **Import**
3. Upload: `monitoring/grafana/dashboards/p0_dashboard.json`
4. Select Prometheus datasource
5. Click **Import**

---

## Alert Runbooks

### P0_SagaTimeoutBreach

**Severity:** Critical
**Response Time:** Immediate (<5 minutes)

#### Symptoms
- Saga execution exceeding 300 seconds
- User-facing delays in patient onboarding
- Potential data inconsistency

#### Investigation Steps

1. **Check Recent Saga Executions**
```sql
SELECT
  saga_id,
  saga_type,
  status,
  EXTRACT(EPOCH FROM (completed_at - started_at)) AS duration_seconds,
  error_message
FROM saga_execution
WHERE started_at > NOW() - INTERVAL '1 hour'
  AND EXTRACT(EPOCH FROM (completed_at - started_at)) > 300
ORDER BY started_at DESC
LIMIT 10;
```

2. **Review Application Logs**
```bash
# Check for saga timeout errors
kubectl logs -l app=backend --tail=100 | grep -i "saga_timeout\|SagaTimeoutError"

# Check saga orchestrator logs
tail -f /var/log/hormonia/saga_orchestrator.log | grep "TIMEOUT"
```

3. **Database Connection Pool Status**
```sql
SELECT
  count(*) as active_connections,
  max_conn as max_connections,
  (count(*) * 100.0 / max_conn) as usage_percent
FROM pg_stat_activity
CROSS JOIN (SELECT setting::int as max_conn FROM pg_settings WHERE name = 'max_connections') s
WHERE state = 'active';
```

4. **Check for Stuck Transactions**
```sql
SELECT
  pid,
  now() - pg_stat_activity.query_start AS duration,
  query,
  state
FROM pg_stat_activity
WHERE state != 'idle'
  AND now() - pg_stat_activity.query_start > interval '5 minutes'
ORDER BY duration DESC;
```

#### Resolution Actions

**Immediate:**
1. If duration >600s, consider manual saga cancellation
2. Check database locks: `SELECT * FROM pg_locks WHERE NOT granted;`
3. Verify external API connectivity (WhatsApp, Firebase)

**Short-term:**
1. Increase saga timeout if legitimate long-running operations
2. Add saga step performance monitoring
3. Implement saga step timeout overrides

**Long-term:**
1. Refactor long-running saga steps
2. Implement saga step parallelization
3. Add saga performance profiling

#### Escalation
- If unresolved in 15 minutes → Escalate to Engineering Lead
- If duration >1800s → Escalate to CTO
- Create incident ticket in all cases

---

### P0_EventLoopBlocked

**Severity:** Critical
**Response Time:** Immediate (<5 minutes)

#### Symptoms
- HTTP request timeouts
- WebSocket connection drops
- Celery task queue backlog

#### Investigation Steps

1. **Identify Blocking Code**
```bash
# Check for synchronous operations in async context
grep -r "sync_to_async\|async_to_sync" app/services/ app/api/v2/

# Review recent code changes
git log --since="1 day ago" --name-only | grep -E "\.(py)$"
```

2. **Check Database Query Times**
```sql
SELECT
  query,
  mean_exec_time,
  calls,
  total_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 100  -- queries >100ms
ORDER BY mean_exec_time DESC
LIMIT 20;
```

3. **Monitor Async Task Queue**
```bash
# Celery inspect
celery -A app.celery_app inspect active
celery -A app.celery_app inspect stats

# Redis queue depth
redis-cli LLEN celery
```

#### Resolution Actions

**Immediate:**
1. Identify and kill long-running queries
2. Restart affected workers if necessary
3. Review recent deployments for rollback candidates

**Short-term:**
1. Add `sync_to_async` wrappers for blocking operations
2. Move heavy computations to Celery tasks
3. Implement connection pooling for external APIs

**Long-term:**
1. Implement async/sync boundary testing
2. Add event loop monitoring to CI/CD
3. Code review checklist for async violations

---

### P0_TemplateLoadingFailure

**Severity:** Critical
**Response Time:** <10 minutes

#### Symptoms
- Quiz questions not loading
- WhatsApp messages failing to send
- Template rendering errors

#### Investigation Steps

1. **Check Template Files**
```bash
# Verify template file existence
ls -la app/templates/quiz/
ls -la app/templates/messages/

# Check file permissions
find app/templates/ -type f ! -perm 644
```

2. **Verify Template Syntax**
```bash
# Test template compilation
python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('app/templates'))
try:
    template = env.get_template('quiz/question.html')
    print('Template OK')
except Exception as e:
    print(f'Template Error: {e}')
"
```

3. **Check Database Templates**
```sql
SELECT
  id,
  name,
  template_type,
  is_active,
  last_modified
FROM message_templates
WHERE is_active = true
ORDER BY last_modified DESC;
```

4. **Review Template Cache**
```bash
# Check Redis cache
redis-cli KEYS "template:*"
redis-cli GET "template:quiz:question:v1"
```

#### Resolution Actions

**Immediate:**
1. Verify template migration status
2. Clear template cache: `redis-cli FLUSHDB`
3. Restart application to reload templates

**Short-term:**
1. Implement template validation in CI/CD
2. Add template preloading on startup
3. Increase cache TTL for stable templates

**Long-term:**
1. Implement template versioning
2. Add template A/B testing
3. Automated template syntax validation

---

### P0_ErrorRateSpike

**Severity:** Critical
**Response Time:** <5 minutes

#### Symptoms
- 5xx HTTP errors increasing
- User-facing service disruptions
- Database connection failures

#### Investigation Steps

1. **Check Application Logs**
```bash
# Recent errors
tail -f /var/log/hormonia/application.log | grep ERROR

# Error distribution
grep ERROR /var/log/hormonia/application.log | awk '{print $5}' | sort | uniq -c | sort -rn
```

2. **Identify Failing Endpoints**
```bash
# Nginx access logs
tail -f /var/log/nginx/access.log | grep " 5[0-9][0-9] "

# Endpoint error rates
cat /var/log/nginx/access.log | awk '{print $7, $9}' | grep " 5[0-9][0-9]$" | awk '{print $1}' | sort | uniq -c | sort -rn
```

3. **Check Database Connectivity**
```bash
# Test database connection
psql -h localhost -U postgres -d hormonia -c "SELECT 1;"

# Active connections
psql -c "SELECT count(*) FROM pg_stat_activity;"
```

4. **Review Recent Deployments**
```bash
# Git history
git log --oneline -10

# Deployment logs
kubectl logs deployment/backend --tail=50
```

#### Resolution Actions

**Immediate:**
1. If error rate >5%, consider circuit breaker activation
2. Check external API dependencies (WhatsApp, Firebase)
3. Scale up pods if resource-constrained: `kubectl scale deployment/backend --replicas=5`

**Short-term:**
1. Rollback deployment if caused by recent release
2. Implement retry logic for transient failures
3. Add health checks for dependencies

**Long-term:**
1. Implement circuit breaker pattern
2. Add comprehensive error tracking (Sentry)
3. Automated canary deployments

---

## Dashboard Guide

### P0 Critical Implementation Monitoring Dashboard

**Access:** http://localhost:3000/d/p0-monitoring

#### Dashboard Sections

1. **Overview (Row 1)**
   - **P0 Critical Alerts**: Count of firing critical alerts
   - **P0 System Health**: Overall health indicator (HEALTHY/UNHEALTHY)

2. **Saga Orchestration (Rows 2-3)**
   - **Saga Execution Duration**: P95/P99 latencies with 300s threshold line
   - **Saga Critical Events**: Timeout count, race conditions, compensation failures
   - **Target**: All metrics should be 0

3. **Event Loop Monitoring (Rows 4-5)**
   - **Event Loop Blocking Detection**: Blocking events and sync-in-async violations
   - **Async Task Queue Depth**: Current queue depth with 1000 task threshold
   - **Target**: Zero blocking events, queue <1000

4. **Template Loading (Rows 6-7)**
   - **Template Loading Performance**: P95/P99 load times with 100ms threshold
   - **Template Loading Failures**: Failure count over time
   - **Template Cache Miss Rate**: Cache efficiency (target <20%)

5. **Performance Metrics (Rows 8-9)**
   - **HTTP Request Latency P95**: API response times with 200ms threshold
   - **HTTP Error Rate**: 5xx error percentage (target <1%)

6. **Critical Errors (Row 10)**
   - **Database Connection Errors**: Connection failure count
   - **Critical Exceptions**: Application exception count

#### How to Use

**Real-time Monitoring:**
1. Set dashboard auto-refresh to 30s
2. Enable alert annotations to see when alerts fire
3. Use time range selector for incident investigation

**Incident Investigation:**
1. Identify spike or anomaly in metrics
2. Click on data point to see exact timestamp
3. Use "Explore" to drill down into related metrics
4. Check alert annotations for correlation

**Performance Baselines:**
- Normal saga duration: 1-5s (P95)
- Normal HTTP latency: 50-100ms (P95)
- Normal error rate: <0.1%
- Template load time: 10-50ms (P95)

---

## Troubleshooting

### Prometheus Not Scraping Metrics

**Symptoms:**
- Missing data in Grafana
- Targets showing as "DOWN" in Prometheus

**Resolution:**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify application metrics endpoint
curl http://localhost:8000/metrics

# Check Prometheus logs
docker logs hormonia-prometheus

# Restart Prometheus
docker-compose -f docker-compose.monitoring.yml restart prometheus
```

### Alerts Not Firing

**Symptoms:**
- No alerts received despite metric threshold breach
- Alertmanager showing no active alerts

**Resolution:**
```bash
# Check alert rules evaluation
curl http://localhost:9090/api/v1/rules

# Verify Alertmanager configuration
curl http://localhost:9093/api/v1/status

# Test alert routing
amtool config routes test --config.file=monitoring/alertmanager/p0_config.yml

# Check Alertmanager logs
docker logs hormonia-alertmanager
```

### Grafana Dashboard Not Loading

**Symptoms:**
- Dashboard shows "No data" or "N/A"
- Panels not rendering

**Resolution:**
```bash
# Check Prometheus datasource
curl http://localhost:3000/api/datasources

# Verify queries in Prometheus
curl 'http://localhost:9090/api/v1/query?query=saga_execution_duration_seconds'

# Check Grafana logs
docker logs hormonia-grafana

# Re-import dashboard
# Grafana UI → Dashboards → Import → Upload p0_dashboard.json
```

### Slack Notifications Not Working

**Symptoms:**
- Alerts firing but no Slack messages
- Alertmanager logs show send errors

**Resolution:**
```bash
# Test Slack webhook
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test alert"}' \
  ${SLACK_WEBHOOK_URL}

# Verify Alertmanager config
grep -A 5 "slack_configs:" monitoring/alertmanager/p0_config.yml

# Check Alertmanager logs for errors
docker logs hormonia-alertmanager | grep -i slack

# Reload Alertmanager config
curl -X POST http://localhost:9093/-/reload
```

### PagerDuty Integration Issues

**Symptoms:**
- No pages sent for critical alerts
- PagerDuty shows no events

**Resolution:**
```bash
# Verify PagerDuty service key
echo ${PAGERDUTY_P0_CRITICAL_KEY}

# Test PagerDuty API
curl -X POST https://events.pagerduty.com/v2/enqueue \
  -H 'Content-Type: application/json' \
  -d '{
    "routing_key": "'${PAGERDUTY_P0_CRITICAL_KEY}'",
    "event_action": "trigger",
    "payload": {
      "summary": "Test alert",
      "severity": "critical",
      "source": "monitoring-test"
    }
  }'

# Check Alertmanager logs
docker logs hormonia-alertmanager | grep -i pagerduty
```

---

## Production Deployment Checklist

### Pre-Deployment

- [ ] Environment variables configured in `.env`
- [ ] Slack webhook tested
- [ ] SMTP credentials verified
- [ ] PagerDuty service keys validated
- [ ] Alert recipient emails confirmed
- [ ] Grafana admin password set

### Deployment

- [ ] Monitoring stack deployed: `docker-compose -f docker-compose.monitoring.yml up -d`
- [ ] All services healthy: `docker-compose ps`
- [ ] Prometheus targets UP: Check http://localhost:9090/targets
- [ ] Alert rules loaded: Check http://localhost:9090/rules
- [ ] Grafana accessible: http://localhost:3000
- [ ] P0 dashboard imported successfully

### Post-Deployment Validation

- [ ] Test alert sent to Slack
- [ ] Test alert sent to email
- [ ] PagerDuty incident created and resolved
- [ ] All panels in P0 dashboard showing data
- [ ] Alert annotations visible in Grafana
- [ ] Recording rules producing data

### Ongoing Maintenance

- [ ] Weekly review of alert thresholds
- [ ] Monthly review of alert noise and false positives
- [ ] Quarterly review of monitoring coverage
- [ ] Document all production incidents
- [ ] Update runbooks based on learnings

---

## Support and Escalation

### On-Call Rotation
- **Primary:** Backend Team Lead
- **Secondary:** Senior Backend Engineer
- **Escalation:** Engineering Director

### Communication Channels
- **Critical Alerts:** #p0-critical-alerts (Slack)
- **Incident Updates:** #incidents (Slack)
- **Post-Mortems:** #post-mortems (Slack)

### Documentation
- **Alert Runbooks:** `/docs/operations/P0_MONITORING_GUIDE.md`
- **Architecture:** `/docs/architecture/P0.2_IMPLEMENTATION_SUMMARY.md`
- **Deployment:** `/docs/deployment/P0_DEPLOYMENT_GUIDE.md`

---

## Appendix

### Metrics Reference

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `saga_execution_duration_seconds` | Histogram | `saga_type`, `status` | Saga execution duration |
| `saga_timeout_total` | Counter | `saga_type` | Total saga timeouts |
| `saga_fallback_race_condition_total` | Counter | - | Race condition occurrences |
| `async_event_loop_blocked_total` | Counter | `location` | Event loop blocking events |
| `template_load_duration_seconds` | Histogram | `template_name` | Template load time |
| `template_loading_failed_total` | Counter | `template_name`, `error_type` | Template load failures |
| `http_request_duration_seconds` | Histogram | `endpoint`, `method`, `status` | HTTP request duration |
| `http_requests_total` | Counter | `endpoint`, `method`, `status` | Total HTTP requests |

### Alert Severity Levels

| Severity | Response Time | Escalation | Examples |
|----------|--------------|------------|----------|
| **Critical** | <5 minutes | Immediate page | Saga timeout, Event loop blocked |
| **High** | <15 minutes | Slack alert | Performance degradation, High error rate |
| **Medium** | <1 hour | Slack notification | Cache inefficiency, Slow queries |
| **Warning** | <4 hours | Email notification | Resource warnings |

---

**Document Maintainer:** Backend Infrastructure Team
**Last Review Date:** 2025-11-15
**Next Review Date:** 2025-12-15
