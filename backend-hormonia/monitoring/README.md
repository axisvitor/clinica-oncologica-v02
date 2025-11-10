# Quiz Metrics Monitoring Stack

Complete monitoring solution for the Hormonia quiz system with Grafana dashboards, Prometheus alerts, and operational runbooks.

## Quick Start

### 1. Start Monitoring Stack

```bash
cd monitoring

# Configure environment
cp .env.example .env
# Edit .env with your settings (Redis host, Slack webhooks, etc.)

# Start all services
docker-compose -f docker-compose.monitoring.yml up -d

# Verify services are healthy
docker-compose -f docker-compose.monitoring.yml ps
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093
- **Redis Exporter**: http://localhost:9121/metrics

### 3. Import Dashboard

1. Open Grafana: http://localhost:3000
2. Login with admin/admin
3. Navigate to Dashboards → Import
4. Upload `grafana/dashboards/quiz_metrics_dashboard.json`
5. Select "Prometheus" as datasource
6. Click Import

### 4. Configure Alerting

1. **Update Alertmanager config:**
   ```bash
   vim alertmanager/alertmanager.yml
   # Update Slack webhook URL
   # Update PagerDuty service key
   # Update email SMTP settings
   ```

2. **Reload Alertmanager:**
   ```bash
   docker-compose -f docker-compose.monitoring.yml restart alertmanager
   ```

3. **Test alert routing:**
   ```bash
   # Send test alert
   curl -X POST http://localhost:9093/api/v2/alerts \
     -H "Content-Type: application/json" \
     -d '[{
       "labels": {
         "alertname": "TestAlert",
         "severity": "warning",
         "service": "quiz_system"
       },
       "annotations": {
         "summary": "Test alert from setup"
       }
     }]'
   ```

## Architecture

```
┌─────────────┐
│   Backend   │ ─────┐
│  (FastAPI)  │      │
└─────────────┘      │
                     ├──> Redis ──> Redis Exporter ──> Prometheus
┌─────────────┐      │                                     │
│  Evolution  │ ─────┘                                     │
│     API     │                                            │
└─────────────┘                                            ▼
                                                      Alertmanager
                                                           │
                                                           ├──> Slack
                                                           ├──> PagerDuty
                                                           └──> Email

                                                      Grafana
                                                      (Dashboards)
```

## Metrics Collected

### Quiz Completion Metrics
- `quiz_completion_total{template_id}` - Total completions
- `quiz_abandonment_total{template_id}` - Sessions started but not completed
- `quiz_completion_rate{template_id}` - Completion / (Completion + Abandonment)

### Latency Metrics
- `quiz_send_latency_seconds{template_id, message_type, percentile}` - Message delivery time
- `quiz_response_latency_seconds{template_id, question_id, percentile}` - Patient response time

### Quality Metrics
- `quiz_clarification_total{template_id, question_id}` - Invalid responses requiring retry
- `quiz_clarification_rate{template_id, question_id}` - Clarifications / Total responses

### Infrastructure Metrics
- `webhook_duplication_rate` - Duplicate webhook requests blocked
- `whatsapp_send_success_rate` - Message delivery success rate

## Dashboard Panels

1. **Quiz Completion Rate by Template** - Trend over time with SLO thresholds
2. **Total Completions (24h)** - Stat panel with color coding
3. **Abandonment Count (24h)** - Stat panel with alerting
4. **Send Latency Distribution** - p50/p95/p99 timeseries
5. **Response Latency by Question** - Heatmap of patient response times
6. **Daily Completion Trend** - 7-day trend with template breakdown
7. **Clarification Rate** - Gauge showing invalid response rate
8. **Active Quiz Sessions** - Real-time session count
9. **Webhook Idempotency** - Duplicate webhook block rate
10. **Message Send Success Rate** - WhatsApp delivery success

## Alerting Rules

### Critical Alerts (PagerDuty + Slack)
- `CriticalQuizAbandonmentRate` - Abandonment > 40%
- `CriticalQuizSendLatency` - p95 > 5s
- `RedisMetricsUnavailable` - Metrics collection stopped

### Warning Alerts (Slack)
- `HighQuizAbandonmentRate` - Abandonment > 20%
- `HighQuizSendLatency` - p95 > 2s
- `HighClarificationRate` - Clarifications > 15%
- `ZeroCompletionsIn24Hours` - No completions for a template

### Info Alerts (Email)
- `SlowPatientResponseTime` - p50 > 10 min
- `QuizEngagementDropping` - 30% week-over-week drop

## Configuration Files

```
monitoring/
├── docker-compose.monitoring.yml   # Docker Compose stack
├── grafana/
│   ├── dashboards/
│   │   └── quiz_metrics_dashboard.json
│   └── datasources.yml
├── prometheus/
│   ├── prometheus.yml              # Scrape configs
│   └── rules/
│       └── quiz_alerts.yml         # Alert rules
├── alertmanager/
│   └── alertmanager.yml            # Alert routing
└── README.md
```

## Operational Runbook

For detailed troubleshooting procedures, see [RUNBOOK_QUIZ_METRICS.md](../docs/RUNBOOK_QUIZ_METRICS.md).

Quick links:
- [High Abandonment Rate](../docs/RUNBOOK_QUIZ_METRICS.md#highquizabandonmentrate)
- [High Send Latency](../docs/RUNBOOK_QUIZ_METRICS.md#highquizsendlatency)
- [High Clarification Rate](../docs/RUNBOOK_QUIZ_METRICS.md#highclarificationrate)
- [Zero Completions](../docs/RUNBOOK_QUIZ_METRICS.md#zerocompletionsin24hours)

## Maintenance

### Daily
- [ ] Check Grafana dashboard for anomalies
- [ ] Review active alerts in Alertmanager

### Weekly
- [ ] Review alert history and false positive rate
- [ ] Check metric retention (Redis memory usage)
- [ ] Review completion trends and patient engagement

### Monthly
- [ ] Tune alert thresholds based on historical data
- [ ] Review SLO targets with product team
- [ ] Optimize Redis metrics storage (TTL, sample limits)

## Troubleshooting

### Dashboard shows "No data"

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v2/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Check Redis exporter
curl http://localhost:9121/metrics | grep quiz_metrics

# Manually query Redis
redis-cli --scan --pattern "quiz_metrics:*"
```

### Alerts not firing

```bash
# Check Prometheus rules
curl http://localhost:9090/api/v2/rules | jq '.data.groups[].rules[] | {alert: .name, state: .state}'

# Test alert manually
promtool test rules prometheus/rules/quiz_alerts.yml

# Check Alertmanager config
amtool config show --alertmanager.url=http://localhost:9093
```

### Redis metrics not updating

```bash
# Check backend is writing metrics
docker logs hormonia-backend | grep "quiz_metrics"

# Check Redis connection
redis-cli ping

# Verify metric keys exist
redis-cli --scan --pattern "quiz_metrics:completions:*" | head -5

# Check Redis exporter logs
docker logs hormonia-redis-exporter
```

## Production Deployment Checklist

- [ ] Configure production Redis host in `.env`
- [ ] Update Slack webhook URLs in `alertmanager/alertmanager.yml`
- [ ] Set PagerDuty service key in `alertmanager/alertmanager.yml`
- [ ] Configure SMTP for email alerts
- [ ] Set Grafana admin password (change from default)
- [ ] Enable HTTPS for Grafana (reverse proxy or TLS config)
- [ ] Configure remote write for long-term Prometheus storage (optional)
- [ ] Set up backup for Grafana dashboards (provisioning or API)
- [ ] Test alert delivery to all channels (Slack, PagerDuty, email)
- [ ] Document on-call rotation and escalation procedures
- [ ] Train team on dashboard interpretation and runbook usage
- [ ] Set up log aggregation (integrate with ELK/Loki)
- [ ] Configure network policies (firewall rules for services)
- [ ] Set resource limits in docker-compose (memory, CPU)
- [ ] Enable monitoring for monitoring stack itself (meta-monitoring)

## Support

- **Documentation**: [docs/QUIZ_E2E_TESTING_METRICS.md](../docs/QUIZ_E2E_TESTING_METRICS.md)
- **Runbook**: [docs/RUNBOOK_QUIZ_METRICS.md](../docs/RUNBOOK_QUIZ_METRICS.md)
- **Code**: [app/services/quiz_metrics.py](../app/services/quiz_metrics.py)
- **Issues**: https://github.com/your-org/hormonia/issues
- **Slack**: #quiz-system-alerts

## License

Internal use only - Hormonia Healthcare System
