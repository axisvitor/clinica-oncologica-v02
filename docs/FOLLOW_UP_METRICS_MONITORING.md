# Follow-Up System - Métricas e Monitoring

**Versão:** 1.0
**Data:** 2025-12-24
**Objetivo:** Dashboard de métricas e KPIs para o sistema de follow-up

---

## 📊 KPIs Principais

### **1. Follow-Up Action Metrics**

```python
# Implementar em FollowUpSystemService.get_metrics()

{
    "actions": {
        "total_pending": 142,        # Actions waiting execution
        "total_completed": 1829,     # Successfully completed actions
        "total_failed": 23,          # Failed actions
        "completion_rate": 0.987,    # completed / (completed + failed)

        "by_type": {
            "empathetic_response": {
                "pending": 45,
                "completed": 678,
                "failed": 5,
                "avg_execution_time_seconds": 3.2
            },
            "medical_clarification": {
                "pending": 12,
                "completed": 234,
                "failed": 3,
                "avg_execution_time_seconds": 4.1
            },
            "escalation_notification": {
                "pending": 8,
                "completed": 156,
                "failed": 8,
                "avg_execution_time_seconds": 2.8
            },
            "provider_alert": {
                "pending": 3,
                "completed": 89,
                "failed": 4,
                "avg_execution_time_seconds": 5.3
            },
            "conversation_continuation": {
                "pending": 74,
                "completed": 672,
                "failed": 3,
                "avg_execution_time_seconds": 2.1
            }
        },

        "by_priority": {
            "critical": {"pending": 2, "avg_wait_time_minutes": 1.2},
            "high": {"pending": 18, "avg_wait_time_minutes": 5.7},
            "medium": {"pending": 87, "avg_wait_time_minutes": 45.3},
            "low": {"pending": 35, "avg_wait_time_minutes": 180.4}
        },

        "avg_execution_time_seconds": 3.5,
        "p95_execution_time_seconds": 8.2,
        "p99_execution_time_seconds": 15.1
    }
}
```

**Alertas:**
- `total_failed > 50`: 🚨 High failure rate, investigate immediately
- `completion_rate < 0.95`: ⚠️ Completion rate degraded
- `avg_execution_time_seconds > 10`: ⚠️ Slow execution
- `by_priority.critical.pending > 5`: 🚨 Critical actions backing up

---

### **2. Escalation Alert Metrics**

```python
{
    "alerts": {
        "total_active": 18,           # Unresolved alerts
        "total_acknowledged": 12,     # Acknowledged but not resolved
        "total_resolved": 245,        # Successfully resolved
        "resolution_rate": 0.932,     # resolved / (resolved + active)

        "by_level": {
            "critical": {
                "active": 2,
                "acknowledged": 1,
                "resolved": 34,
                "avg_acknowledgment_time_minutes": 8.5,
                "avg_resolution_time_hours": 2.3
            },
            "high": {
                "active": 7,
                "acknowledged": 5,
                "resolved": 89,
                "avg_acknowledgment_time_minutes": 25.2,
                "avg_resolution_time_hours": 6.7
            },
            "medium": {
                "active": 9,
                "acknowledged": 6,
                "resolved": 122,
                "avg_acknowledgment_time_minutes": 45.8,
                "avg_resolution_time_hours": 24.5
            }
        },

        "by_concern_type": {
            "severe_pain": {"active": 3, "resolved": 45},
            "side_effect": {"active": 5, "resolved": 78},
            "mental_health": {"active": 4, "resolved": 56},
            "medication_issue": {"active": 2, "resolved": 34},
            "emergency": {"active": 1, "resolved": 12},
            "general_concern": {"active": 3, "resolved": 20}
        },

        "avg_resolution_time_hours": 12.4,
        "p95_resolution_time_hours": 36.8,
        "p99_resolution_time_hours": 72.1,

        "overdue_alerts": 3,  # active > 48h
        "unacknowledged_alerts": 6  # created > 2h, not acknowledged
    }
}
```

**Alertas:**
- `by_level.critical.active > 3`: 🚨 Multiple critical alerts
- `overdue_alerts > 5`: 🚨 Alerts not being resolved
- `unacknowledged_alerts > 10`: ⚠️ Alerts not being seen
- `avg_resolution_time_hours > 24`: ⚠️ Slow resolution

---

### **3. Storage & Persistence Metrics**

```python
{
    "storage": {
        "redis_healthy": true,
        "redis_latency_ms": 2.3,
        "redis_memory_used_mb": 156.7,
        "redis_keys_count": 1847,

        "fallback_active": false,
        "fallback_entries": 0,

        "sync_stats": {
            "last_rehydration": "2025-12-24T08:00:00Z",
            "rehydrated_actions": 142,
            "rehydrated_alerts": 18,
            "rehydration_errors": 0,

            "last_memory_to_redis_sync": "2025-12-24T08:05:00Z",
            "synced_actions": 0,  # No Redis downtime
            "synced_alerts": 0,
            "sync_errors": 0
        },

        "cache_stats": {
            "conversation_contexts": 234,
            "hit_rate": 0.87,
            "miss_rate": 0.13,
            "avg_context_size_kb": 4.2
        }
    }
}
```

**Alertas:**
- `redis_healthy == false`: 🚨 Redis down, using fallback
- `fallback_active == true`: ⚠️ Fallback mode active
- `redis_latency_ms > 50`: ⚠️ Slow Redis response
- `sync_errors > 5`: 🚨 Sync issues detected

---

### **4. Message Deduplication Metrics**

```python
{
    "deduplication": {
        "total_checks": 5678,
        "duplicates_blocked": 234,
        "duplicates_rate": 0.041,  # 4.1% blocked

        "by_message_type": {
            "flow_message": {
                "checks": 2345,
                "blocked": 89,
                "block_rate": 0.038
            },
            "follow_up": {
                "checks": 1567,
                "blocked": 78,
                "block_rate": 0.050
            },
            "empathetic": {
                "checks": 1234,
                "blocked": 45,
                "block_rate": 0.036
            },
            "escalation": {
                "checks": 532,
                "blocked": 22,
                "block_rate": 0.041
            }
        },

        "cache_efficiency": {
            "avg_window_hours": 2.0,
            "cache_size_keys": 456,
            "avg_ttl_remaining_minutes": 67.3
        },

        "false_positives": 3,  # Legitimate msgs blocked
        "false_negative": 1    # Duplicates not caught
    }
}
```

**Alertas:**
- `duplicates_rate > 0.10`: ⚠️ High duplicate rate (>10%)
- `false_positives > 10`: 🚨 Too many legitimate msgs blocked
- `duplicates_rate < 0.01`: ℹ️ Very low, check if working

---

### **5. Flow Service Integration Metrics**

```python
{
    "flow_integration": {
        "flow_messages_sent": 1234,
        "follow_ups_registered": 1189,  # Should be ~same as sent
        "registration_rate": 0.964,     # 96.4% registered

        "registration_failures": 45,
        "failure_reasons": {
            "follow_up_service_unavailable": 23,
            "redis_error": 12,
            "timeout": 7,
            "other": 3
        },

        "avg_registration_time_ms": 12.3,
        "p95_registration_time_ms": 45.6,

        "response_tracking": {
            "messages_with_expected_response": 1189,
            "patients_responded": 978,
            "response_rate": 0.823,  # 82.3% responded
            "avg_response_time_hours": 8.7,

            "follow_ups_triggered": 211,  # 1189 - 978
            "follow_up_effectiveness": {
                "responded_after_followup": 156,
                "effectiveness_rate": 0.739  # 73.9%
            }
        }
    }
}
```

**Alertas:**
- `registration_rate < 0.90`: 🚨 Many flow messages not registered
- `response_rate < 0.70`: ⚠️ Low patient response rate
- `effectiveness_rate < 0.50`: ⚠️ Follow-ups not effective

---

## 📈 Dashboard Views

### **View 1: Executive Summary (Real-time)**

```
┌─────────────────────────────────────────────────────────────────────┐
│                   FOLLOW-UP SYSTEM DASHBOARD                        │
│                   Last Update: 2025-12-24 14:35:22                  │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────┬──────────────────────┬──────────────────────┐
│   PENDING ACTIONS    │   ACTIVE ALERTS      │   SYSTEM HEALTH      │
│                      │                      │                      │
│      142             │        18            │    ✅ HEALTHY        │
│   ⬆️ +12 (1h)        │   ⬇️ -3 (1h)         │   Redis: ✅ 2.3ms    │
│                      │                      │   Fallback: ❌ Off   │
└──────────────────────┴──────────────────────┴──────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   COMPLETION RATE                                                   │
│                                                                     │
│   98.7%  ████████████████████████████████████████████▌             │
│                                                                     │
│   Target: 95%  ✅ Above target                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   CRITICAL ALERTS (Requires Immediate Attention)                   │
│                                                                     │
│   2 Critical Alerts Active                                         │
│   - Severe pain reported by Patient #1234 (2h ago) ⏰ URGENT       │
│   - Emergency escalation for Patient #5678 (45m ago) 🚨 CRITICAL   │
│                                                                     │
│   6 Unacknowledged Alerts (> 2h)                                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   RESPONSE TRACKING (Last 24h)                                     │
│                                                                     │
│   Messages Sent:          1,234                                    │
│   Patients Responded:       978  (82.3%)  ✅                        │
│   Follow-ups Triggered:     211  (17.7%)                           │
│   Responded After FU:       156  (73.9% effectiveness)             │
└─────────────────────────────────────────────────────────────────────┘
```

---

### **View 2: Operations Dashboard**

```
┌─────────────────────────────────────────────────────────────────────┐
│                   FOLLOW-UP OPERATIONS                              │
└─────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────┬────────────────────────────────┐
│   ACTIONS BY TYPE                  │   ACTIONS BY PRIORITY          │
│                                    │                                │
│   Empathetic Response:    45       │   Critical:      2  ⏰         │
│   Medical Clarification:  12       │   High:         18  ⚠️         │
│   Escalation:              8       │   Medium:       87             │
│   Provider Alert:          3       │   Low:          35             │
│   Conversation:           74       │                                │
└────────────────────────────────────┴────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   EXECUTION PERFORMANCE                                             │
│                                                                     │
│   Avg Execution Time:     3.5s  ✅                                  │
│   P95 Execution Time:     8.2s  ✅                                  │
│   P99 Execution Time:    15.1s  ⚠️ (Target: <10s)                  │
│                                                                     │
│   Slowest Actions (Last Hour):                                     │
│   - Medical Clarification #abc123: 24.5s (AI timeout)              │
│   - Provider Alert #def456: 18.7s (notification delay)             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   DEDUPLICATION                                                     │
│                                                                     │
│   Total Checks:        5,678                                       │
│   Duplicates Blocked:    234  (4.1%)                               │
│                                                                     │
│   By Type:                                                         │
│   - Flow Messages:     89 blocked (3.8%)                           │
│   - Follow-ups:        78 blocked (5.0%)  ⚠️ Higher than expected  │
│   - Empathetic:        45 blocked (3.6%)                           │
│   - Escalation:        22 blocked (4.1%)                           │
│                                                                     │
│   False Positives:      3  ⚠️ Review blocked messages              │
└─────────────────────────────────────────────────────────────────────┘
```

---

### **View 3: Alert Management Dashboard**

```
┌─────────────────────────────────────────────────────────────────────┐
│                   ESCALATION ALERTS                                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   ALERTS BY SEVERITY                                                │
│                                                                     │
│   Critical:   2 active   (Avg resolution: 2.3h)   🚨               │
│   High:       7 active   (Avg resolution: 6.7h)   ⚠️               │
│   Medium:     9 active   (Avg resolution: 24.5h)                   │
│                                                                     │
│   Overdue (>48h):     3 alerts  ⚠️                                  │
│   Unacknowledged:     6 alerts  ⚠️                                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   ALERTS BY CONCERN TYPE (Last 7 days)                             │
│                                                                     │
│   Severe Pain:        3 active,  45 resolved  ████████             │
│   Side Effects:       5 active,  78 resolved  ████████████         │
│   Mental Health:      4 active,  56 resolved  █████████            │
│   Medication Issue:   2 active,  34 resolved  ██████               │
│   Emergency:          1 active,  12 resolved  ███                  │
│   General Concern:    3 active,  20 resolved  ████                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   TEAM PERFORMANCE                                                  │
│                                                                     │
│   Dr. Silva:      Acknowledged: 45   Resolved: 42   Avg: 5.2h     │
│   Dr. Costa:      Acknowledged: 38   Resolved: 35   Avg: 6.8h     │
│   Nurse Maria:    Acknowledged: 67   Resolved: 64   Avg: 8.1h     │
│   Nurse João:     Acknowledged: 54   Resolved: 51   Avg: 7.3h     │
│                                                                     │
│   Unassigned:     12 alerts  ⚠️                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🚨 Alert Rules (Prometheus/Grafana)

### **Critical Alerts (PagerDuty)**

```yaml
# alerts/follow_up_critical.yml

groups:
  - name: follow_up_critical
    interval: 1m
    rules:
      - alert: CriticalAlertsBackingUp
        expr: follow_up_active_alerts{level="critical"} > 3
        for: 5m
        labels:
          severity: critical
          team: medical
        annotations:
          summary: "Multiple critical patient alerts pending"
          description: "{{ $value }} critical alerts active for >5min"

      - alert: FollowUpServiceDown
        expr: up{job="follow_up_service"} == 0
        for: 2m
        labels:
          severity: critical
          team: engineering
        annotations:
          summary: "Follow-up service is down"

      - alert: RedisDownFollowUpFallback
        expr: follow_up_redis_healthy == 0
        for: 5m
        labels:
          severity: critical
          team: engineering
        annotations:
          summary: "Redis down, using in-memory fallback"
          description: "Data loss risk if service restarts"

      - alert: HighActionFailureRate
        expr: rate(follow_up_actions_failed_total[5m]) > 0.1
        for: 10m
        labels:
          severity: critical
          team: engineering
        annotations:
          summary: "High follow-up action failure rate"
          description: "{{ $value }} actions/min failing"
```

---

### **Warning Alerts (Slack)**

```yaml
# alerts/follow_up_warnings.yml

groups:
  - name: follow_up_warnings
    interval: 5m
    rules:
      - alert: UnacknowledgedAlertsAccumulating
        expr: follow_up_unacknowledged_alerts > 10
        for: 15m
        labels:
          severity: warning
          team: medical
        annotations:
          summary: "Many patient alerts not being acknowledged"

      - alert: SlowFollowUpExecution
        expr: histogram_quantile(0.95, follow_up_execution_time_seconds) > 10
        for: 30m
        labels:
          severity: warning
          team: engineering
        annotations:
          summary: "Slow follow-up action execution"
          description: "P95 execution time: {{ $value }}s"

      - alert: LowPatientResponseRate
        expr: follow_up_patient_response_rate < 0.70
        for: 2h
        labels:
          severity: warning
          team: clinical
        annotations:
          summary: "Patient response rate dropped below 70%"

      - alert: HighDuplicationBlockRate
        expr: follow_up_dedup_block_rate > 0.10
        for: 1h
        labels:
          severity: warning
          team: engineering
        annotations:
          summary: "High message deduplication block rate"
          description: "{{ $value }} messages blocked as duplicates"
```

---

## 📊 Grafana Dashboard JSON

```json
{
  "dashboard": {
    "title": "Follow-Up System Monitoring",
    "panels": [
      {
        "title": "Pending Actions",
        "targets": [{
          "expr": "follow_up_pending_actions_total"
        }],
        "type": "graph"
      },
      {
        "title": "Active Alerts by Severity",
        "targets": [{
          "expr": "follow_up_active_alerts{level=~\"critical|high|medium\"}"
        }],
        "type": "bargauge"
      },
      {
        "title": "Completion Rate",
        "targets": [{
          "expr": "follow_up_actions_completed_total / (follow_up_actions_completed_total + follow_up_actions_failed_total)"
        }],
        "type": "stat"
      },
      {
        "title": "Execution Time (P95)",
        "targets": [{
          "expr": "histogram_quantile(0.95, follow_up_execution_time_seconds)"
        }],
        "type": "graph"
      },
      {
        "title": "Patient Response Rate",
        "targets": [{
          "expr": "follow_up_patient_responses_total / follow_up_messages_sent_total"
        }],
        "type": "graph"
      }
    ]
  }
}
```

---

## 🔍 Logging Strategy

### **Log Levels**

```python
# CRITICAL - System failures
logger.critical("Redis down and fallback failed - DATA LOSS IMMINENT")

# ERROR - Action failures, important errors
logger.error(f"Failed to execute follow-up action {action_id}: {error}")

# WARNING - Degraded performance, potential issues
logger.warning(f"Slow execution time: {execution_time}s > 10s threshold")

# INFO - Important events
logger.info(f"Follow-up action {action_id} completed successfully")

# DEBUG - Detailed troubleshooting
logger.debug(f"Deduplication check for patient {patient_id}: {result}")
```

---

### **Structured Logging (JSON)**

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "follow_up_action_completed",
    action_id=str(action.action_id),
    patient_id=str(action.patient_id),
    action_type=action.follow_up_type.value,
    execution_time_seconds=3.2,
    status="success"
)

# Output:
# {
#   "event": "follow_up_action_completed",
#   "action_id": "abc-123",
#   "patient_id": "xyz-789",
#   "action_type": "empathetic_response",
#   "execution_time_seconds": 3.2,
#   "status": "success",
#   "timestamp": "2025-12-24T14:35:22Z"
# }
```

---

## 🎯 SLOs (Service Level Objectives)

| Metric | Target | Measurement | Alert Threshold |
|--------|--------|-------------|-----------------|
| **Action Completion Rate** | ≥ 95% | completed / (completed + failed) | < 90% |
| **Critical Alert Response** | < 15 min | time_to_acknowledgment | > 30 min |
| **Critical Alert Resolution** | < 4 hours | time_to_resolution | > 8 hours |
| **System Availability** | ≥ 99.5% | uptime / total_time | < 99% |
| **P95 Execution Time** | < 10 seconds | histogram_quantile(0.95) | > 15 seconds |
| **Patient Response Rate** | ≥ 75% | responses / messages_sent | < 70% |
| **Redis Availability** | ≥ 99.9% | redis_uptime / total_time | < 99% |

---

## 📞 On-Call Runbook

### **Scenario 1: High Action Failure Rate**

**Alert:** `HighActionFailureRate > 10%`

**Steps:**
1. Check Celery worker status: `celery inspect active`
2. Review error logs: `grep "Failed to execute" /var/log/follow_up.log`
3. Check Redis connectivity: `redis-cli ping`
4. Verify WhatsApp service: `curl http://whatsapp-api/health`
5. Restart workers if needed: `systemctl restart celery-worker`

---

### **Scenario 2: Redis Down**

**Alert:** `RedisDownFollowUpFallback`

**Steps:**
1. Check Redis status: `systemctl status redis`
2. Review Redis logs: `tail -f /var/log/redis/redis.log`
3. Attempt restart: `systemctl restart redis`
4. Monitor fallback metrics
5. When Redis recovers: Monitor sync_memory_to_redis() execution
6. Verify no data loss: Check action counts before/after

---

### **Scenario 3: Critical Alerts Backing Up**

**Alert:** `CriticalAlertsBackingUp > 3`

**Steps:**
1. Check staff availability
2. Review alert details in dashboard
3. Manually assign to available staff if needed
4. Escalate to on-call physician if > 5 alerts
5. Document reason for backup

---

**Última Atualização:** 2025-12-24
**Versão:** 1.0
**Status:** ✅ Ready for Implementation
