# P0 Monitoring - Quick Reference Card

**Print this and keep it handy for on-call rotations**

## 🚨 Critical Alerts (Immediate Response <5 min)

| Alert | Threshold | First Action |
|-------|-----------|-------------|
| **P0_SagaTimeoutBreach** | >300s | Check saga execution logs, verify DB connections |
| **P0_SagaTimeoutCount** | >0 | Review failed sagas in DB, page on-call |
| **P0_SagaFallbackRaceCondition** | >0 | REGRESSION! Escalate to engineering lead |
| **P0_EventLoopBlocked** | >0 | Check async/sync boundaries, review recent deploys |
| **P0_ErrorRateSpike** | >1% | Check app logs, consider circuit breaker |

## 📊 Quick Access URLs

- **P0 Dashboard:** http://localhost:3000/d/p0-monitoring
- **Prometheus:** http://localhost:9090
- **Alertmanager:** http://localhost:9093
- **Full Guide:** `/docs/operations/P0_MONITORING_GUIDE.md`

## 🔍 Essential Commands

### Check Recent Saga Timeouts
```sql
SELECT saga_id, saga_type, status,
       EXTRACT(EPOCH FROM (completed_at - started_at)) AS duration_seconds
FROM saga_execution
WHERE started_at > NOW() - INTERVAL '1 hour'
  AND EXTRACT(EPOCH FROM (completed_at - started_at)) > 300
ORDER BY started_at DESC LIMIT 10;
```

### Check Application Errors
```bash
kubectl logs -l app=backend --tail=100 | grep ERROR
```

### Check Event Loop Blocking
```bash
grep -r "sync_to_async\|async_to_sync" app/services/ | grep -v ".pyc"
```

### Check Slow Queries
```sql
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY mean_exec_time DESC LIMIT 20;
```

### Restart Monitoring Stack
```bash
docker-compose -f monitoring/docker-compose.monitoring.yml restart
```

## 🎯 Alert Thresholds at a Glance

| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| Saga Duration | <60s | 60-300s | **>300s** |
| Event Loop Blocks | 0 | 0 | **>0** |
| Template Load | <50ms | 50-100ms | **>100ms** |
| HTTP Latency P95 | <100ms | 100-200ms | **>200ms** |
| Error Rate | <0.1% | 0.1-1% | **>1%** |

## 📞 Escalation Path

1. **Primary:** Backend Team Lead
2. **Secondary:** Senior Backend Engineer
3. **Critical (>15 min unresolved):** Engineering Director
4. **Severity 1 (>30 min):** CTO

## 🔧 Emergency Actions

### If Saga Timeouts Persist
```bash
# Check DB connection pool
psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Kill stuck queries
psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
         WHERE state = 'active' AND now() - query_start > interval '10 minutes';"
```

### If Event Loop Blocked
```bash
# Restart workers
kubectl rollout restart deployment/backend

# Check async task queue
redis-cli LLEN celery
```

### If Template Loading Fails
```bash
# Clear template cache
redis-cli FLUSHDB

# Verify templates exist
ls -la app/templates/quiz/

# Restart application
kubectl rollout restart deployment/backend
```

### If Error Rate Spikes
```bash
# Check recent deployments
git log --oneline -5

# Consider rollback
kubectl rollout undo deployment/backend

# Scale up if resource issue
kubectl scale deployment/backend --replicas=5
```

## 📱 Slack Channels

- `#p0-critical-alerts` - All critical P0 alerts
- `#p0-saga-alerts` - Saga-specific issues
- `#p0-engineering-critical` - Race conditions, regressions
- `#p0-oncall` - On-call notifications

## ✅ Health Check Checklist

Daily (5 min):
- [ ] Check Grafana P0 dashboard for anomalies
- [ ] Verify zero critical alerts firing
- [ ] Review error rate trends

Weekly (15 min):
- [ ] Review alert noise and false positives
- [ ] Check monitoring stack health
- [ ] Update on-call notes

## 🚀 Deployment Validation

After any deployment:
```bash
# Run validation script
./scripts/validate_p0_monitoring.sh

# Check all targets UP
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'

# Verify no alerts firing
curl -s http://localhost:9093/api/v2/alerts | jq '.[] | select(.status.state == "firing")'
```

## 🎓 Training Resources

1. **Full Guide:** `/docs/operations/P0_MONITORING_GUIDE.md`
2. **Setup Summary:** `/docs/operations/MONITORING_SETUP_SUMMARY.md`
3. **Alert Runbooks:** See P0_MONITORING_GUIDE.md sections
4. **Prometheus Docs:** https://prometheus.io/docs/
5. **Grafana Docs:** https://grafana.com/docs/

---

**Keep this accessible during on-call rotation!**
**Last Updated:** 2025-11-15
