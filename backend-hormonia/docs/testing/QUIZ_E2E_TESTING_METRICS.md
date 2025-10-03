# Quiz E2E Testing & Metrics Implementation

## Summary

Complete implementation of end-to-end testing suite and production-grade metrics for the conversational quiz system.

## What Was Implemented

### 1. E2E Test Suite ([tests/e2e/test_conversational_quiz.py](../tests/e2e/test_conversational_quiz.py))

**Coverage:**
- ✅ Complete quiz flow (start → question → response → advance → completion)
- ✅ Realistic Evolution webhook simulation
- ✅ Idempotency (Redis fast-path + DB fallback)
- ✅ Invalid response handling with clarification messages
- ✅ Concurrent session start protection
- ✅ WebSocket event verification

**Key Tests:**
```python
test_complete_quiz_flow()          # Full happy path
test_quiz_idempotency_redis_path() # Duplicate webhook deduplication
test_quiz_idempotency_db_fallback()# Fallback when Redis unavailable
test_quiz_invalid_response_clarification() # Error handling
test_quiz_session_concurrent_start_protection() # Race conditions
test_quiz_websocket_events_published() # Real-time updates
```

### 2. Multi-Instance Routing Tests ([tests/e2e/test_multi_instance_routing.py](../tests/e2e/test_multi_instance_routing.py))

**Coverage:**
- ✅ Default instance routing
- ✅ Per-message metadata override (`metadata['instance_name']`)
- ✅ Load balancing across 3+ instances
- ✅ Failover scenarios (primary → backup)
- ✅ HYBRID mode routing

**Example Usage:**
```python
# Initialize with default instance
service = UnifiedWhatsAppService(
    db=db_session,
    default_instance_name="inst_primary"
)

# Override per message
message.message_metadata = {
    "instance_name": "inst_backup"  # Route to backup instance
}
```

### 3. Quiz Metrics ([app/services/quiz_metrics.py](../app/services/quiz_metrics.py))

**Metrics Tracked:**

#### Completion Metrics
- `quiz_completion_total{template_id}` - Total completions per template
- `quiz_abandonment_rate{template_id}` - Started but not completed sessions

#### Latency Metrics
- `quiz_send_latency_seconds{template_id, message_type, percentile}`
  - p50, p95, p99 for message delivery time
- `quiz_response_latency_seconds{template_id, question_id, percentile}`
  - p50, p95, p99 for patient response time (question → answer)

#### Quality Metrics
- `quiz_clarification_rate{template_id, question_id}` - Invalid responses requiring re-prompt

**Storage:**
- Redis-backed (TTL: 7-30 days)
- Sorted sets for percentile calculation
- Daily breakdowns for trend analysis

**API:**
```python
from app.services.quiz_metrics import get_quiz_metrics_collector

metrics = await get_quiz_metrics_collector()

# Record completion
await metrics.record_quiz_completion(template_id, session_id)

# Record send latency
await metrics.record_send_latency(template_id, latency_seconds, message_type="question")

# Record response latency
await metrics.record_response_latency(template_id, question_id, session_id, latency_seconds)

# Query metrics
completion_count = await metrics.get_completion_count(template_id)
latency_stats = await metrics.get_send_latency_percentiles(template_id, "question")
# Returns: {"p50": 0.12, "p95": 0.45, "p99": 1.2, "samples": 1000}
```

### 4. Integration Points

**Completion Tracking** ([app/services/quiz.py:703](../app/services/quiz.py)):
```python
async def complete_session(self, session_id: UUID):
    # ... existing logic ...

    # Record completion metric
    metrics = await get_quiz_metrics_collector()
    await metrics.record_quiz_completion(
        template_id=session.quiz_template_id,
        session_id=session.id
    )
```

**Send Latency Tracking** ([app/services/unified_whatsapp_service.py:256](../app/services/unified_whatsapp_service.py)):
```python
async def send_message(self, message: Message, **kwargs):
    send_start = datetime.utcnow()

    # ... send logic ...

    if success and quiz_template_id:
        latency = (datetime.utcnow() - send_start).total_seconds()
        metrics = await get_quiz_metrics_collector()
        await metrics.record_send_latency(template_id, latency, message_type)
```

**Response Latency Tracking** ([app/services/quiz_flow_integration.py:483](../app/services/quiz_flow_integration.py)):
```python
async def process_quiz_response(self, patient_id, response_text, message_metadata):
    # ... validation & save ...

    # Calculate latency from question_sent_at to now
    if message_metadata and 'question_sent_at' in message_metadata:
        response_latency = (datetime.utcnow() - question_sent_at).total_seconds()
        await metrics.record_response_latency(
            template_id, question_id, session_id, response_latency
        )
```

## Running Tests

### Prerequisites
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Ensure Redis is running (for idempotency tests)
docker run -d -p 6379:6379 redis:7-alpine

# Set test environment variables
export DATABASE_URL="postgresql://..."
export REDIS_URL="redis://localhost:6379/0"
```

### Execute Tests
```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run specific test file
pytest tests/e2e/test_conversational_quiz.py -v

# Run with coverage
pytest tests/e2e/ --cov=app.services.quiz --cov-report=term-missing

# Run only quiz tests (marker)
pytest -m "e2e and whatsapp" -v

# Run with real-time output
pytest tests/e2e/ -v -s
```

## Grafana Dashboard Queries

### Completion Rate by Template
```promql
# Total completions
sum by (template_id) (redis_get{key=~"quiz_metrics:completions:.*"})

# Abandonment rate
sum by (template_id) (redis_get{key=~"quiz_metrics:abandonment:.*"})
/ (sum by (template_id) (redis_get{key=~"quiz_metrics:completions:.*"})
   + sum by (template_id) (redis_get{key=~"quiz_metrics:abandonment:.*"}))
```

### Send Latency Distribution
```promql
# p95 send latency for quiz questions
histogram_quantile(0.95,
  sum by (template_id, le) (
    rate(quiz_send_latency_seconds_bucket{message_type="question"}[5m])
  )
)
```

### Response Latency by Question
```promql
# p50 response time for specific question
histogram_quantile(0.50,
  sum by (template_id, question_id, le) (
    rate(quiz_response_latency_seconds_bucket[5m])
  )
)
```

### Daily Completion Trend
```promql
# Completions per day (last 30 days)
sum by (template_id, day) (
  redis_get{key=~"quiz_metrics:completions:.*:daily:.*"}
)
```

## Production Checklist

- [x] E2E tests covering happy path and error cases
- [x] Idempotency tests (Redis + DB fallback)
- [x] Multi-instance routing tests
- [x] Metrics instrumentation (completion, send latency, response latency)
- [x] Redis-backed metrics storage with TTL
- [x] Percentile calculation for latency analysis
- [ ] Grafana dashboards configured
- [ ] Alerting rules defined (e.g., p95 latency > 2s, abandonment rate > 20%)
- [ ] Load testing (500+ concurrent quiz sessions)
- [ ] Monitoring integration (DataDog/Prometheus)

## Next Steps

1. **Grafana Setup**
   - Import dashboard JSON
   - Configure data source (Redis exporter / Prometheus)
   - Set up alert channels (Slack, PagerDuty)

2. **Alerting Rules**
   ```yaml
   - alert: HighQuizAbandonmentRate
     expr: quiz_abandonment_rate > 0.20
     for: 10m
     annotations:
       summary: "Quiz {{ $labels.template_id }} has high abandonment"

   - alert: HighSendLatency
     expr: quiz_send_latency_p95 > 2.0
     for: 5m
     annotations:
       summary: "Quiz send p95 latency > 2s"
   ```

3. **Load Testing**
   ```bash
   # Use locust or k6 to simulate 500 concurrent quiz sessions
   k6 run --vus 500 --duration 10m quiz_load_test.js
   ```

4. **Documentation**
   - Update runbook with metric meanings
   - Add troubleshooting guide for common issues
   - Document baseline performance targets

## Architecture Improvements Applied

### Before
- ❌ No end-to-end validation
- ❌ Manual testing required for webhook flows
- ❌ No visibility into completion rates or latency
- ❌ Single instance Evolution (no HA)
- ❌ Duplicate webhook processing possible

### After
- ✅ Automated E2E test suite
- ✅ Realistic webhook simulation
- ✅ Production-grade metrics with percentiles
- ✅ Multi-instance routing with load balancing
- ✅ Redis + DB idempotency guarantee

## References

- [E2E Test Suite](../tests/e2e/test_conversational_quiz.py)
- [Multi-Instance Tests](../tests/e2e/test_multi_instance_routing.py)
- [Quiz Metrics Service](../app/services/quiz_metrics.py)
- [Unified WhatsApp Service](../app/services/unified_whatsapp_service.py)
- [Quiz Flow Integration](../app/services/quiz_flow_integration.py)
- [Webhook Processor (Idempotency)](../app/services/webhook_processor.py)
