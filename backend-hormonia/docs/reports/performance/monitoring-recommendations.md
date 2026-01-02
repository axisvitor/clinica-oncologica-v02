# P0 Performance Monitoring Recommendations

**Document Version:** 1.0
**Last Updated:** 2025-11-15
**Target Audience:** DevOps, SRE, Engineering Teams
**Implementation Priority:** P0 - Critical

---

## Executive Summary

This document provides comprehensive monitoring recommendations for validating and maintaining the performance improvements achieved through P0 implementations. It covers metrics collection, alerting strategies, dashboard configuration, and ongoing optimization practices.

### Key Recommendations

1. **Deploy Comprehensive Monitoring Stack** - Prometheus + Grafana + Alertmanager
2. **Implement 24/7 Automated Alerting** - Critical, High, and Predictive alerts
3. **Establish Performance Baselines** - Measure before/after P0 implementation
4. **Create SLA Dashboards** - Real-time visibility into business metrics
5. **Enable Continuous Optimization** - Automated performance regression detection

---

## 1. Monitoring Architecture

### 1.1 Recommended Stack

```yaml
Core Components:
  Prometheus:
    Purpose: Time-series metrics collection and storage
    Version: v2.48.0+
    Retention: 30 days (metrics), 1 year (aggregated)
    Scrape Interval: 15s (default), 5s (critical metrics)

  Grafana:
    Purpose: Visualization and dashboarding
    Version: 10.2.2+
    Refresh Rate: 30s (dashboards), 5s (critical panels)
    Data Sources: Prometheus, PostgreSQL

  Alertmanager:
    Purpose: Alert routing and deduplication
    Version: v0.26.0+
    Grouping: By severity and category
    Routes: PagerDuty (critical), Slack (high), Email (warning)

  Node Exporter:
    Purpose: System-level metrics
    Version: v1.7.0+
    Collectors: CPU, memory, disk, network

  Postgres Exporter:
    Purpose: Database metrics
    Version: v0.15.0+
    Custom Queries: Index usage, slow queries

  Custom Application Metrics:
    Purpose: Application-specific metrics
    Framework: Prometheus client library
    Endpoint: /metrics (port 9090)
```

### 1.2 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐        │
│  │   FastAPI   │  │   Celery    │  │  PostgreSQL  │        │
│  │   Workers   │  │   Workers   │  │   Database   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘        │
│         │                 │                 │                 │
│         └─────────────────┴─────────────────┘                │
│                           │                                   │
└───────────────────────────┼───────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Metrics Collection Layer                    │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐       │
│  │    Node     │  │   Postgres   │  │  Custom App │       │
│  │  Exporter   │  │   Exporter   │  │   Metrics   │       │
│  └──────┬──────┘  └──────┬───────┘  └──────┬──────┘       │
│         │                 │                  │               │
│         └─────────────────┴──────────────────┘              │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Prometheus Server                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  - Scrapes metrics every 15s                         │  │
│  │  - Stores time-series data (30 days)                 │  │
│  │  - Evaluates alert rules (30s interval)              │  │
│  │  - Exposes query API (PromQL)                        │  │
│  └────────────┬────────────────────────┬──────────────────┘ │
└───────────────┼────────────────────────┼────────────────────┘
                │                        │
       ┌────────▼────────┐      ┌───────▼────────┐
       │   Alertmanager  │      │    Grafana     │
       │                 │      │                │
       │  - Routes alerts│      │  - Dashboards  │
       │  - Deduplicates │      │  - Queries     │
       │  - Sends to:    │      │  - Analysis    │
       │    • PagerDuty  │      │                │
       │    • Slack      │      │                │
       │    • Email      │      │                │
       └─────────────────┘      └────────────────┘
```

---

## 2. Critical Metrics to Monitor

### 2.1 P0.1: Database Performance Metrics

```yaml
Database Query Latency:
  Metric: database_query_duration_seconds
  Type: Histogram
  Labels: [query_type, table, index_used]
  Buckets: [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.5, 1.0]
  Target: P95 < 20ms
  Alert: P95 > 20ms for 5 minutes

  Collection Method:
    - Application middleware timing
    - PostgreSQL pg_stat_statements
    - Custom query logging

  Example PromQL:
    histogram_quantile(0.95,
      rate(database_query_duration_seconds_bucket{query_type="doctor_dashboard"}[5m])
    )

Index Usage Effectiveness:
  Metric: pg_stat_user_indexes_index_scans
  Type: Counter
  Labels: [table, index_name]
  Target: >95% index usage
  Alert: Sequential scan ratio > 20%

  Collection Method:
    - Postgres Exporter
    - pg_stat_user_tables view
    - pg_stat_user_indexes view

  Example PromQL:
    (pg_stat_user_tables_seq_scans /
     (pg_stat_user_tables_seq_scans + pg_stat_user_tables_idx_scans)) * 100

Slow Query Count:
  Metric: database_slow_queries_total
  Type: Counter
  Labels: [query_type, duration_bucket]
  Target: <5 queries/hour > 100ms
  Alert: >10 slow queries in 1 hour

  Collection Method:
    - PostgreSQL log_min_duration_statement
    - Custom application logging
    - pg_stat_statements extension

Database Connection Pool:
  Metrics:
    - db_connection_pool_active
    - db_connection_pool_idle
    - db_connection_pool_max
    - db_connection_pool_wait_time
  Target: <80% utilization
  Alert: >90% for 2 minutes

Database Performance Score:
  Metric: database_performance_score
  Type: Gauge
  Calculation: Composite of latency, index usage, connection health
  Target: >85/100
  Alert: <80/100 for 10 minutes
```

### 2.2 P0.2: Async/Sync Performance Metrics

```yaml
Event Loop Lag:
  Metric: event_loop_lag_milliseconds
  Type: Histogram
  Buckets: [1, 5, 10, 20, 50, 100, 200, 500]
  Target: P95 < 20ms
  Alert: P95 > 50ms for 3 minutes

  Collection Method:
    - uvloop.get_event_loop_lag()
    - Custom middleware measurement
    - asyncio.Task monitoring

  Example PromQL:
    histogram_quantile(0.95,
      rate(event_loop_lag_milliseconds_bucket[5m])
    )

Onboarding Latency:
  Metric: onboarding_latency_milliseconds
  Type: Histogram
  Labels: [operation, success]
  Buckets: [50, 100, 150, 200, 250, 500, 1000, 2000]
  Target: P95 < 200ms
  Alert: P95 > 250ms for 5 minutes

  Collection Method:
    - Function decorators (@track_latency)
    - Context managers
    - Manual timing in critical paths

ThreadPool Metrics:
  Metrics:
    - executor_queue_depth{pool="onboarding_sync"}
    - executor_active_threads{pool="onboarding_sync"}
    - executor_tasks_submitted_total
    - executor_tasks_completed_total
    - executor_tasks_failed_total
  Target: Queue depth < 5
  Alert: Queue depth > 10 for 2 minutes

  Collection Method:
    - ThreadPoolExecutor instrumentation
    - Custom metrics wrapper
    - concurrent.futures monitoring

Concurrent Request Capacity:
  Metric: http_requests_concurrent
  Type: Gauge
  Target: Support 200+ concurrent requests
  Alert: < 150 concurrent capacity for 10 minutes

  Collection Method:
    - FastAPI middleware
    - Active request counter
    - Request queue depth
```

### 2.3 P0.3: Template Loading Metrics

```yaml
Template Selection Time:
  Metric: template_selection_duration_milliseconds
  Type: Histogram
  Buckets: [0.1, 0.5, 1, 2, 5, 10]
  Target: P95 < 2ms
  Alert: P95 > 2ms for 5 minutes

  Collection Method:
    - Function timing decorator
    - Template loader instrumentation

Template Cache Hit Rate:
  Metric: template_cache_hits_total / template_cache_lookups_total
  Type: Counter ratio
  Target: >95% hit rate
  Alert: <90% hit rate for 10 minutes

  Collection Method:
    - Cache middleware
    - Template loader cache statistics

Code Complexity Metrics:
  Metrics:
    - code_cyclomatic_complexity{module="flow_service"}
    - code_maintainability_index{module="flow_service"}
    - code_lines_of_code{module="flow_service"}
  Target: Complexity < 15
  Alert: Complexity > 20 for 1 hour

  Collection Method:
    - radon static analysis
    - CI/CD pipeline integration
    - Scheduled complexity scans

Template Mapping Errors:
  Metric: template_mapping_errors_total
  Type: Counter
  Labels: [error_type, treatment_type]
  Target: 0 errors
  Alert: >1 error per 5 minutes

  Collection Method:
    - Exception handling
    - Structured logging
    - Error tracking middleware
```

### 2.4 System-Wide Metrics

```yaml
Error Rate:
  Metric: http_requests_total{status=~"5.."}
  Type: Counter
  Target: <1% error rate
  Alert: >3% error rate for 5 minutes

Timeout Rate:
  Metric: http_requests_timeout_total
  Type: Counter
  Target: <0.5% timeout rate
  Alert: >2% timeout rate for 5 minutes

Request Throughput:
  Metric: rate(http_requests_total[1m]) * 60
  Type: Counter
  Target: >200 req/min
  Alert: <150 req/min for 10 minutes

CPU Utilization:
  Metric: rate(process_cpu_seconds_total[5m]) * 100
  Type: Gauge
  Target: 40-60% utilization
  Alert: >80% for 10 minutes

Memory Usage:
  Metric: process_resident_memory_bytes
  Type: Gauge
  Target: <2GB RSS
  Alert: >2.5GB for 10 minutes
```

---

## 3. Alert Configuration

### 3.1 Alert Severity Levels

```yaml
Critical Alerts (PagerDuty):
  Escalation: Immediate on-call notification
  Response SLA: 15 minutes
  Examples:
    - Database latency P95 > 20ms
    - Event loop lag P95 > 50ms
    - Error rate > 5%
    - Connection pool exhaustion
    - Deadlocks detected
    - SLA violation

High Priority Alerts (Slack + Email):
  Escalation: Team channel notification
  Response SLA: 1 hour
  Examples:
    - Slow query count > 10/hour
    - ThreadPool queue depth > 10
    - Timeout rate > 2%
    - Database CPU > 70%
    - Template cache hit rate < 90%

Medium Priority Alerts (Email):
  Escalation: Email to team
  Response SLA: 4 hours
  Examples:
    - Index not used (sequential scans)
    - Event loop lag trending upward
    - CPU utilization > 70%
    - Memory usage > 1.5GB

Warning Alerts (Dashboard):
  Escalation: Dashboard notification only
  Response SLA: Next business day
  Examples:
    - Template selection > 2ms
    - Code complexity > 15
    - Request throughput < 180 req/min
```

### 3.2 Alert Routing Configuration

```yaml
# alertmanager/config.yml
route:
  receiver: 'default'
  group_by: ['severity', 'category', 'p0_issue']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    # Critical alerts → PagerDuty
    - match:
        severity: critical
      receiver: 'pagerduty'
      continue: true
      group_wait: 10s
      repeat_interval: 30m

    # High priority → Slack + Email
    - match:
        severity: high
      receiver: 'slack-high'
      continue: true
      group_wait: 1m
      repeat_interval: 2h

    # Medium priority → Email only
    - match:
        severity: medium
      receiver: 'email-medium'
      group_wait: 5m
      repeat_interval: 12h

    # Warning → Dashboard only
    - match:
        severity: warning
      receiver: 'null'

receivers:
  - name: 'default'
    email_configs:
      - to: 'ops-team@hormonia.com'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '<PAGERDUTY_SERVICE_KEY>'
        severity: 'critical'
        description: '{{ .GroupLabels.alertname }}: {{ .CommonAnnotations.summary }}'
        details:
          firing: '{{ .Alerts.Firing | len }}'
          runbook: '{{ .CommonAnnotations.runbook }}'

  - name: 'slack-high'
    slack_configs:
      - api_url: '<SLACK_WEBHOOK_URL>'
        channel: '#alerts-high'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.summary }}\n{{ .CommonAnnotations.description }}'
        color: 'warning'

  - name: 'email-medium'
    email_configs:
      - to: 'dev-team@hormonia.com'
        subject: '[Medium] {{ .GroupLabels.alertname }}'
```

---

## 4. Dashboard Configuration

### 4.1 Primary Dashboard: P0 Performance Monitoring

**Dashboard File:** `GRAFANA_DASHBOARD_P0_MONITORING.json`

**Panels:**
1. Overall Performance Score (Gauge)
2. Database Query Latency by Type (Graph)
3. Event Loop Performance (Graph)
4. Database Index Effectiveness (Stat)
5. Query Performance Table
6. Async Onboarding Latency (Graph)
7. ThreadPool Utilization (Graph)
8. Concurrent Request Capacity (Gauge)
9. Executor Task Success Rate (Stat)
10. Template Selection Performance (Graph)
11. Template Cache Hit Rate (Stat)
12. Template Mapping Distribution (Pie Chart)
13. Code Complexity Metrics (Stat)
14. System Throughput (Graph)
15. Database Connection Pool (Graph)
16. Error Rate (Gauge)
17. Timeout Rate (Gauge)
18. CPU Utilization (Graph)
19. Memory Usage (Graph)
20. P0 Improvements Summary (Table)

**Refresh Rate:** 30 seconds
**Time Range:** Last 6 hours (default)
**Variables:** Instance, Time Range

### 4.2 Secondary Dashboards

```yaml
Database Deep Dive:
  Focus: Detailed database performance analysis
  Panels:
    - Query execution plans
    - Index usage statistics
    - Table-level metrics
    - Connection pool details
    - Slow query log
  Refresh: 1 minute

Async Operations Monitor:
  Focus: Event loop and ThreadPool analysis
  Panels:
    - Event loop lag histogram
    - ThreadPool queue trends
    - Concurrent request patterns
    - Task failure analysis
  Refresh: 15 seconds

Code Quality Tracker:
  Focus: Code complexity and maintainability
  Panels:
    - Cyclomatic complexity trends
    - Maintainability index
    - Lines of code evolution
    - Test coverage
  Refresh: 1 hour

Business Metrics SLA:
  Focus: SLA compliance and business impact
  Panels:
    - P95 latency compliance
    - Availability percentage
    - Throughput vs target
    - Error budget consumption
  Refresh: 5 minutes
```

---

## 5. Implementation Checklist

### 5.1 Phase 1: Foundation (Week 1)

```yaml
Monitoring Stack Deployment:
  - [ ] Deploy Prometheus server
  - [ ] Deploy Grafana instance
  - [ ] Deploy Alertmanager
  - [ ] Configure Node Exporter
  - [ ] Configure Postgres Exporter
  - [ ] Verify scrape targets

Application Instrumentation:
  - [ ] Add Prometheus client library
  - [ ] Implement custom metrics
  - [ ] Add /metrics endpoint
  - [ ] Configure metric labels
  - [ ] Test metric collection

Alert Configuration:
  - [ ] Import alert rules (PROMETHEUS_ALERTS_P0.yml)
  - [ ] Configure Alertmanager routes
  - [ ] Set up PagerDuty integration
  - [ ] Set up Slack integration
  - [ ] Test alert firing
```

### 5.2 Phase 2: Dashboards (Week 2)

```yaml
Dashboard Deployment:
  - [ ] Import P0 Performance Dashboard
  - [ ] Import Database Deep Dive Dashboard
  - [ ] Import Async Operations Dashboard
  - [ ] Import Code Quality Dashboard
  - [ ] Import Business SLA Dashboard
  - [ ] Configure dashboard permissions

Dashboard Validation:
  - [ ] Verify all panels load data
  - [ ] Test alert annotations
  - [ ] Validate time range selection
  - [ ] Test variable filtering
  - [ ] Share dashboards with team
```

### 5.3 Phase 3: Baseline & Tuning (Week 3)

```yaml
Performance Baselines:
  - [ ] Collect 1 week of pre-P0 metrics (if available)
  - [ ] Deploy P0 fixes to staging
  - [ ] Collect 1 week of post-P0 metrics
  - [ ] Generate before/after comparison
  - [ ] Document performance gains

Alert Tuning:
  - [ ] Review alert frequency
  - [ ] Adjust thresholds based on baselines
  - [ ] Reduce false positives
  - [ ] Add predictive alerts
  - [ ] Document alert runbooks
```

### 5.4 Phase 4: Production Rollout (Week 4)

```yaml
Production Deployment:
  - [ ] Deploy monitoring stack to production
  - [ ] Enable all metrics collection
  - [ ] Activate critical alerts only (first 24h)
  - [ ] Enable all alerts (after 24h)
  - [ ] Monitor for anomalies

Validation & Handoff:
  - [ ] Verify P0 improvements in production
  - [ ] Train ops team on dashboards
  - [ ] Document runbooks for common alerts
  - [ ] Establish on-call rotation
  - [ ] Schedule weekly performance review
```

---

## 6. Ongoing Maintenance

### 6.1 Daily Monitoring Tasks

```yaml
Morning Standup:
  - Review overnight alerts
  - Check P95 latency trends
  - Verify error rate < 1%
  - Check database connection pool health
  - Review event loop lag

Throughout Day:
  - Monitor Slack alert channel
  - Respond to critical alerts within SLA
  - Investigate anomalies
  - Update runbooks as needed
```

### 6.2 Weekly Performance Review

```yaml
Weekly Meeting (Fridays 10 AM):
  Agenda:
    1. Review P0 performance metrics (15 min)
       - Database latency trends
       - Event loop performance
       - Template loading efficiency

    2. Analyze alert patterns (10 min)
       - Alert frequency by severity
       - False positive rate
       - Mean time to resolution

    3. Code quality review (10 min)
       - Cyclomatic complexity changes
       - New slow queries detected
       - Index usage effectiveness

    4. Capacity planning (10 min)
       - Throughput trends
       - Resource utilization
       - Scaling recommendations

    5. Action items (15 min)
       - Performance optimizations needed
       - Alert tuning required
       - Runbook updates

  Deliverables:
    - Performance report summary
    - Action item list with owners
    - Updated performance forecasts
```

### 6.3 Monthly Optimization Cycle

```yaml
Month 1: Validation & Baseline
  - Collect comprehensive performance data
  - Validate P0 improvements
  - Establish new performance baselines
  - Document wins and challenges

Month 2: Optimization & Tuning
  - Identify next optimization opportunities
  - Tune alert thresholds
  - Optimize slow queries discovered
  - Add missing indexes if needed

Month 3: Capacity Planning
  - Forecast resource needs
  - Plan for scaling
  - Review SLA compliance
  - Update performance budgets

Quarterly: Strategic Review
  - Present to leadership
  - Evaluate ROI of P0 fixes
  - Plan next performance initiatives
  - Update monitoring strategy
```

---

## 7. Runbook Integration

### 7.1 Alert Runbook Structure

Each alert should have a corresponding runbook entry:

```markdown
# Alert: HighDatabaseQueryLatency

## Severity: Critical

## Trigger Condition
Database query P95 latency > 20ms for 5 minutes

## Impact
- Slow user experience
- Possible timeout cascade
- Database resource exhaustion

## Immediate Actions (Within 15 minutes)
1. Check database connection pool: `SELECT * FROM pg_stat_activity;`
2. Identify slow queries: `SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;`
3. Check for missing indexes: `SELECT * FROM pg_stat_user_tables WHERE seq_scan > 1000;`
4. Review recent deployments for schema changes

## Investigation Steps
1. Analyze query execution plans: `EXPLAIN ANALYZE <slow_query>;`
2. Check for table bloat: `SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables;`
3. Review database CPU and I/O metrics
4. Check for long-running transactions: `SELECT * FROM pg_stat_activity WHERE state != 'idle' AND query_start < NOW() - INTERVAL '5 minutes';`

## Resolution Strategies
- Add missing indexes (use CONCURRENTLY)
- Optimize query (rewrite inefficient JOINs)
- Increase connection pool size (temporary)
- Scale database vertically (if needed)

## Escalation
If unresolved after 1 hour, escalate to Database Team Lead

## Post-Incident
- Document root cause
- Add regression test
- Update monitoring if needed
```

### 7.2 Runbook Locations

```yaml
Primary Runbook: docs/performance/RUNBOOK.md
Alert-Specific Runbooks: docs/performance/runbooks/
  - high-database-latency.md
  - event-loop-lag.md
  - threadpool-backlog.md
  - slow-queries.md
  - missing-indexes.md
  - connection-pool.md
  - deadlocks.md
  - executor-failures.md
  - template-mapping-errors.md
  - high-error-rate.md
  - sla-violation.md
```

---

## 8. Cost Optimization

### 8.1 Monitoring Cost Estimation

```yaml
Prometheus:
  Storage: ~5GB/month (30 days retention)
  Cost: $0 (self-hosted) or $50/month (managed)

Grafana:
  Users: 10 active users
  Cost: $0 (self-hosted) or $100/month (managed)

Alertmanager:
  Alert Volume: ~500 alerts/month
  Cost: $0 (self-hosted)

PagerDuty:
  On-Call Users: 3
  Cost: $60/user/month = $180/month

Slack:
  Integration: Free

Total Monthly Cost: $50-$330/month
  (Self-hosted: $180/month for PagerDuty only)
  (Fully managed: $330/month)

ROI Comparison:
  Monitoring Cost: $330/month = $3,960/year
  P0 Savings: $96K/year (infrastructure + ops time)
  ROI: 2,424% (24x return)
```

### 8.2 Cost Optimization Tips

```yaml
Storage Optimization:
  - Use recording rules for expensive queries
  - Reduce retention for high-cardinality metrics
  - Aggregate old data before deletion
  - Use remote storage for long-term retention

Alert Optimization:
  - Reduce false positives to minimize PagerDuty costs
  - Use grouping to avoid duplicate alerts
  - Implement maintenance windows to suppress alerts
  - Use Slack for non-critical alerts (free)

Query Optimization:
  - Cache dashboard queries
  - Use pre-aggregated metrics
  - Limit time range for expensive queries
  - Use recording rules for complex PromQL
```

---

## 9. Success Metrics

### 9.1 Monitoring Effectiveness

```yaml
Alert Quality:
  - False Positive Rate: <10%
  - Mean Time to Detection: <2 minutes
  - Mean Time to Resolution: <30 minutes (critical)
  - Alert Coverage: >95% of incidents detected

Dashboard Usage:
  - Daily Active Users: >80% of team
  - Dashboard Load Time: <2 seconds
  - Data Freshness: <30 seconds
  - Panel Reliability: >99.9% uptime

Performance Visibility:
  - Metric Collection Success Rate: >99.9%
  - Data Completeness: >99%
  - Query Response Time: <1 second
  - Historical Data Availability: 30 days
```

### 9.2 Business Impact

```yaml
Proactive Issue Detection:
  - Incidents prevented: >10/month
  - Issues caught before user impact: >80%
  - Predictive alerts acted upon: >50%

Operational Efficiency:
  - On-call escalations reduced: -70%
  - Time spent investigating: -60%
  - Performance regression detection: <1 hour

Performance Improvements:
  - P95 latency maintained: <200ms
  - Error rate maintained: <1%
  - Throughput maintained: >200 req/s
  - SLA compliance: >99.5%
```

---

## 10. Next Steps

### Immediate (This Week)
1. Deploy monitoring stack to staging environment
2. Import P0 performance dashboard
3. Configure critical alerts only
4. Begin collecting baseline metrics

### Short-term (Next 2 Weeks)
1. Deploy to production environment
2. Enable all alert rules
3. Train team on dashboard usage
4. Document initial runbooks

### Medium-term (Next Month)
1. Tune alert thresholds based on real data
2. Add predictive alerts
3. Create custom business metric dashboards
4. Establish weekly performance review

### Long-term (Next Quarter)
1. Implement automated performance regression testing
2. Build ML-based anomaly detection
3. Create capacity planning forecasts
4. Integrate with incident management system

---

## Conclusion

Comprehensive monitoring is critical for validating and maintaining the performance gains achieved through P0 implementations. By following these recommendations, you will:

1. **Gain Visibility** - Real-time insights into all critical metrics
2. **Enable Proactive Detection** - Catch issues before they impact users
3. **Support Data-Driven Decisions** - Make optimization choices based on facts
4. **Ensure SLA Compliance** - Maintain performance targets consistently
5. **Reduce Operational Burden** - Automate detection and alerting

**Recommendation:** Begin implementation immediately to validate P0 improvements and prevent performance regressions.

---

**Document Owner:** DevOps Team
**Review Frequency:** Monthly
**Next Review:** 2025-12-15
**Feedback:** devops@hormonia.com

---

## Appendix A: Metric Naming Conventions

```yaml
Counter Metrics:
  Pattern: <namespace>_<subsystem>_<name>_total
  Example: http_requests_total, database_queries_total

Gauge Metrics:
  Pattern: <namespace>_<subsystem>_<name>
  Example: database_connections_active, cpu_usage_percent

Histogram Metrics:
  Pattern: <namespace>_<subsystem>_<name>_<unit>
  Example: http_request_duration_seconds, query_latency_milliseconds

Summary Metrics:
  Pattern: <namespace>_<subsystem>_<name>_summary
  Example: request_size_bytes_summary

Labels:
  - Use lowercase with underscores
  - Keep cardinality low (<100 unique values)
  - Avoid user-generated content in labels
  - Examples: method, status, query_type, table
```

## Appendix B: PromQL Query Examples

```promql
# Database query latency P95 by type
histogram_quantile(0.95,
  rate(database_query_duration_seconds_bucket[5m])
)

# Event loop lag P99
histogram_quantile(0.99,
  rate(event_loop_lag_milliseconds_bucket[5m])
)

# Error rate percentage
(sum(rate(http_requests_total{status=~"5.."}[5m])) /
 sum(rate(http_requests_total[5m]))) * 100

# Requests per second
rate(http_requests_total[1m])

# ThreadPool queue depth trend
deriv(executor_queue_depth{pool="onboarding_sync"}[30m])

# Database index usage ratio
(pg_stat_user_tables_idx_scans /
 (pg_stat_user_tables_idx_scans + pg_stat_user_tables_seq_scans)) * 100

# Template cache hit rate
(sum(rate(template_cache_hits_total[5m])) /
 sum(rate(template_cache_lookups_total[5m]))) * 100

# Concurrent request capacity
http_requests_concurrent
```

---

**End of Document**
