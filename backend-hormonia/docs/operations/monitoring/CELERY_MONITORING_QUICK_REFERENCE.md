# Celery Monitoring - Quick Reference Card

**Last Updated**: January 16, 2025

---

## 🚀 Quick Start

```bash
# Deploy monitoring stack
cd backend-hormonia
./scripts/deploy_celery_monitoring.sh --dev

# Access monitoring tools
open http://localhost:5555  # Flower UI
open http://localhost:9090  # Prometheus
open http://localhost:3000  # Grafana
```

---

## 🌐 Access Points

| Service | URL | Credentials | Purpose |
|---------|-----|-------------|---------|
| **Flower** | http://localhost:5555 | admin:admin123 | Task monitoring UI |
| **Prometheus** | http://localhost:9090 | - | Metrics database |
| **Grafana** | http://localhost:3000 | admin:admin | Dashboards |
| **Health API** | http://localhost:8000/health/celery | - | Celery health check |

---

## 📊 Key Metrics

### Prometheus Queries

```promql
# Task success rate (last hour)
sum(increase(celery_task_total{status="success"}[1h])) /
sum(increase(celery_task_total[1h])) * 100

# P95 task duration
histogram_quantile(0.95,
  sum(rate(celery_task_duration_seconds_bucket[5m])) by (task_name, le)
)

# Active tasks by type
sum(celery_task_active) by (task_name)

# Queue backlog
sum(celery_queue_length) by (queue_name)

# Top 5 failing tasks
topk(5, sum by (task_name) (rate(celery_task_failures_total[1h])))
```

---

## 🚨 Alert Thresholds

| Alert | Threshold | Severity | Action |
|-------|-----------|----------|--------|
| Worker Down | No response 1min | CRITICAL | Restart worker |
| All Workers Down | No workers 2min | CRITICAL | Check Redis/broker |
| Task Stuck | Running >10min | CRITICAL | Revoke task |
| Queue Backlog (Critical) | >5000 tasks | CRITICAL | Scale workers |
| High Failure Rate | >0.1/min | WARNING | Check logs |
| Queue Backlog | >1000 tasks | WARNING | Monitor trend |

---

## 🔧 Common Commands

### Docker Operations
```bash
# View Flower logs
docker-compose -f monitoring/docker-compose.monitoring.yml logs -f flower

# Restart monitoring stack
docker-compose -f monitoring/docker-compose.monitoring.yml restart

# Scale workers
docker-compose up -d --scale worker=5

# Check worker stats
docker stats hormonia-worker
```

### Celery Operations
```bash
# Inspect active tasks
docker-compose exec worker celery -A app.celery_app inspect active

# Revoke stuck task
docker-compose exec worker celery -A app.celery_app control revoke <task-id> --terminate

# Check registered tasks
docker-compose exec worker celery -A app.celery_app inspect registered

# Purge all tasks
docker-compose exec worker celery -A app.celery_app purge
```

### Health Checks
```bash
# Check Celery health
curl http://localhost:8000/health/celery | jq

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="celery_worker")'

# Check Grafana health
curl http://localhost:3000/api/health
```

---

## 🐛 Troubleshooting

### No Metrics in Prometheus
```bash
# 1. Check environment variable
docker-compose exec worker env | grep CELERY_PROMETHEUS_METRICS
# Should show: CELERY_PROMETHEUS_METRICS=true

# 2. Check metrics endpoint
curl http://localhost:9090/metrics | grep celery

# 3. Verify Prometheus scrape config
curl http://localhost:9090/api/v1/targets
```

### Flower Not Showing Tasks
```bash
# 1. Check Flower logs
docker-compose -f monitoring/docker-compose.monitoring.yml logs flower

# 2. Verify broker connection
docker-compose exec flower env | grep CELERY_BROKER_URL

# 3. Test Celery connection
docker-compose exec flower celery -A app.celery_app inspect ping
```

### High Queue Backlog
```bash
# 1. Check current queue lengths
curl http://localhost:8000/health/celery | jq '.queue_lengths'

# 2. Scale workers temporarily
docker-compose up -d --scale worker=5

# 3. Check for failing tasks
docker-compose logs worker | grep ERROR
```

### Stuck Tasks
```bash
# 1. Identify stuck task
docker-compose exec worker celery -A app.celery_app inspect active

# 2. Revoke task (soft)
docker-compose exec worker celery -A app.celery_app control revoke <task-id>

# 3. Revoke task (force terminate)
docker-compose exec worker celery -A app.celery_app control revoke <task-id> --terminate

# 4. Restart worker if needed
docker-compose restart worker
```

---

## 📈 Grafana Dashboard Panels

| Panel # | Name | Type | Purpose |
|---------|------|------|---------|
| 1 | Task Execution Rate | Graph | Tasks/min by type |
| 2 | Task Failure Rate | Graph | Failures/min |
| 3 | Task Duration P95 | Graph | Latency percentiles |
| 4 | Active Tasks | Stacked Graph | Current execution |
| 5 | Queue Length | Graph | Pending tasks |
| 6 | Task Retry Rate | Graph | Retries/min |
| 7 | Top Failing Tasks | Table | Worst offenders |
| 8 | Slowest Tasks (P99) | Table | Performance issues |
| 9 | Total Tasks (24h) | Single Stat | Overall throughput |
| 10 | Success Rate (24h) | Single Stat | Reliability metric |
| 11 | Active Workers | Single Stat | Worker count |
| 12 | Avg Duration (1h) | Single Stat | Performance trend |

---

## 🔐 Security Notes

### Production Configuration

1. **Change Flower Password**:
   ```bash
   # In .env file
   FLOWER_BASIC_AUTH=admin:your_secure_password
   ```

2. **Change Grafana Password**:
   ```bash
   # In .env file
   GRAFANA_ADMIN_PASSWORD=your_secure_password
   ```

3. **Restrict Network Access**:
   ```yaml
   # In docker-compose
   ports:
     - "127.0.0.1:5555:5555"  # Only localhost
   ```

---

## 📞 Emergency Contacts

### Critical Issues
- **All Workers Down**: Restart Redis + workers
- **Task Stuck >30min**: Revoke + investigate
- **Queue >10000**: IMMEDIATE scaling required

### Support Channels
- **DevOps Team**: ops-team@example.com
- **On-Call**: Use PagerDuty escalation
- **Documentation**: `/docs/operations/CELERY_MONITORING.md`

---

## 🎯 Key Performance Indicators

### Healthy System
- ✅ Success Rate: >95%
- ✅ P95 Duration: <10s
- ✅ Active Workers: ≥1
- ✅ Queue Length: <100
- ✅ Failure Rate: <0.01/min

### Warning Signs
- ⚠️ Success Rate: 80-95%
- ⚠️ P95 Duration: 10-60s
- ⚠️ Queue Length: 100-1000
- ⚠️ Failure Rate: 0.01-0.1/min

### Critical Issues
- 🚨 Success Rate: <80%
- 🚨 P95 Duration: >60s
- 🚨 Active Workers: 0
- 🚨 Queue Length: >1000
- 🚨 Failure Rate: >0.1/min

---

## 📚 Related Documentation

- **Full Guide**: `/docs/operations/CELERY_MONITORING.md`
- **Implementation Summary**: `/docs/operations/MEDIUM-010-IMPLEMENTATION-SUMMARY.md`
- **Deployment Script**: `/scripts/deploy_celery_monitoring.sh`
- **Alert Rules**: `/monitoring/prometheus/alerts/celery_alerts.yml`
- **Production Runbook**: `/docs/operations/PRODUCTION_RUNBOOK.md`

---

**Print this card and keep it handy for quick reference!**
