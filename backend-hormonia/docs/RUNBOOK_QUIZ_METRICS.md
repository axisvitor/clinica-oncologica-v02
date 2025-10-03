# Quiz System Operational Runbook

## Overview

This runbook provides step-by-step procedures for investigating and resolving common issues with the quiz system, based on alerts and metrics.

**Systems Covered:**
- Conversational quiz flow (WhatsApp)
- Quiz metrics collection (Redis)
- Message delivery (Evolution API)
- Webhook processing

**On-Call Resources:**
- Grafana Dashboard: https://grafana.example.com/d/quiz-metrics-hormonia
- Alert Manager: https://alertmanager.example.com
- Logs: https://logs.example.com (search: `service:quiz_system`)

---

## Alert Response Procedures

### 🚨 HighQuizAbandonmentRate

**Alert:** `Quiz abandonment rate > 20%`

**Impact:** Patients starting quizzes but not completing them → reduced data quality and patient engagement.

**Investigation Steps:**

1. **Check Dashboard**
   ```
   Navigate to Grafana → Quiz Metrics Dashboard
   Panel: "Quiz Completion Rate by Template"
   Identify which template(s) have high abandonment
   ```

2. **Review Recent Changes**
   ```bash
   # Check recent deployments
   kubectl get deployments -n hormonia --sort-by=.metadata.creationTimestamp

   # Check recent template changes
   psql -c "SELECT id, name, version, updated_at FROM quiz_templates WHERE updated_at > NOW() - INTERVAL '7 days' ORDER BY updated_at DESC;"
   ```

3. **Analyze Question Difficulty**
   ```bash
   # Get clarification rate per question
   redis-cli --scan --pattern "quiz_metrics:clarifications:*" | while read key; do
     count=$(redis-cli get "$key")
     echo "$key: $count"
   done | sort -t: -k4 -rn
   ```

4. **Check Response Latency**
   - High response latency (> 5 min) may indicate confusing questions
   - Review panel: "Response Latency by Question (p95)"

5. **Review Patient Feedback**
   ```sql
   -- Check for patterns in abandoned sessions
   SELECT
     qt.name,
     qs.current_question_index,
     COUNT(*) as abandon_count
   FROM quiz_sessions qs
   JOIN quiz_templates qt ON qs.quiz_template_id = qt.id
   WHERE qs.is_completed = FALSE
     AND qs.started_at > NOW() - INTERVAL '7 days'
   GROUP BY qt.name, qs.current_question_index
   ORDER BY abandon_count DESC
   LIMIT 10;
   ```

**Common Causes & Fixes:**

| Cause | Symptoms | Fix |
|-------|----------|-----|
| Confusing question wording | High clarification rate on specific question | Revise question text, add examples |
| Too many questions | Abandonment increases at later questions | Reduce quiz length or add progress indicators |
| Poor timing | Abandonment during specific hours | Adjust quiz delivery schedule |
| Technical issues | Sudden spike in abandonment | Check Evolution API health, webhook processing |

**Escalation:**
- If abandonment > 40% for > 30 min → Escalate to Product team
- If technical root cause (API down) → Escalate to Platform team

---

### ⚠️ HighQuizSendLatency

**Alert:** `Quiz message send latency p95 > 2s`

**Impact:** Degraded patient experience, delayed quiz responses.

**Investigation Steps:**

1. **Check Evolution API Health**
   ```bash
   # Test Evolution API connectivity
   curl -X GET "https://evolution.example.com/health" \
     -H "apikey: $EVOLUTION_API_KEY"

   # Check circuit breaker status
   redis-cli get "circuit_breaker:evolution_api:status"
   ```

2. **Review Queue Depth**
   ```bash
   # Check message queue backlog
   redis-cli llen "message_queue:outbound"

   # Check processing rate
   redis-cli --stat | grep -E "instantaneous_ops_per_sec"
   ```

3. **Analyze Send Latency by Instance**
   ```bash
   # Group latency by Evolution instance
   redis-cli --scan --pattern "quiz_metrics:send_latency:*" | while read key; do
     p95=$(redis-cli zrange "$key" -100 -1 WITHSCORES | awk '{sum+=$2; count++} END {print sum/count}')
     echo "$key: $p95s"
   done
   ```

4. **Check Network Latency**
   ```bash
   # Test network to Evolution API
   ping -c 10 evolution.example.com
   traceroute evolution.example.com
   ```

5. **Review Recent Load**
   ```bash
   # Check message volume last hour
   redis-cli --scan --pattern "quiz_metrics:completions:*:daily:*" | \
     xargs -I {} redis-cli get {} | paste -sd+ | bc
   ```

**Common Causes & Fixes:**

| Cause | Symptoms | Fix |
|-------|----------|-----|
| Evolution API rate limiting | 429 responses in logs | Increase rate limit or implement backpressure |
| High queue depth | Queue length > 1000 | Scale worker pods, optimize processing |
| Network issues | High ping latency | Contact networking team, check firewall rules |
| Circuit breaker open | Status = "open" in Redis | Wait for cooldown, investigate underlying issue |

**Immediate Mitigation:**
```bash
# Switch to LEGACY mode (bypass queue)
kubectl set env deployment/hormonia-backend MESSAGING_MODE=LEGACY -n hormonia

# Or scale up workers
kubectl scale deployment/hormonia-workers --replicas=5 -n hormonia
```

**Escalation:**
- If p95 > 5s for > 10 min → Page on-call engineer
- If Evolution API unavailable → Escalate to Evolution support

---

### 📊 HighClarificationRate

**Alert:** `Clarification rate > 15% for a specific question`

**Impact:** Poor user experience, data quality issues.

**Investigation Steps:**

1. **Identify Problematic Question**
   ```bash
   # Get clarification counts per question
   redis-cli --scan --pattern "quiz_metrics:clarifications:*" | while read key; do
     template_id=$(echo "$key" | cut -d: -f3)
     question_id=$(echo "$key" | cut -d: -f4)
     count=$(redis-cli get "$key")
     echo "Template: $template_id, Question: $question_id, Clarifications: $count"
   done | sort -t: -k3 -rn | head -20
   ```

2. **Review Question Design**
   ```sql
   -- Get full question details
   SELECT
     qt.name,
     qt.questions->>question_index AS question
   FROM quiz_templates qt
   WHERE qt.id = '<template_id>';
   ```

3. **Analyze Invalid Responses**
   ```sql
   -- Get sample invalid responses
   SELECT
     qr.response_metadata->>'original_text' as patient_response,
     COUNT(*) as occurrences
   FROM quiz_responses qr
   WHERE qr.quiz_template_id = '<template_id>'
     AND qr.question_id = '<question_id>'
     AND qr.response_metadata ? 'validation_error'
   GROUP BY qr.response_metadata->>'original_text'
   ORDER BY occurrences DESC
   LIMIT 20;
   ```

4. **Check Validation Rules**
   - Review question type (yes/no, single_choice, multi_choice, scale)
   - Verify options are clear and mutually exclusive
   - Test validation logic with sample inputs

**Common Causes & Fixes:**

| Cause | Symptoms | Fix |
|-------|----------|-----|
| Ambiguous options | Multiple similar answers | Clarify option wording, add examples |
| Strict validation | Many near-valid responses | Relax validation, add fuzzy matching |
| Yes/No confusion | "yes" vs "sim" vs "s" | Add response normalization for locale |
| Missing "other" option | Unexpected responses | Add "Outra" option with free text |

**Quick Fix Template:**
```python
# Add fuzzy matching for yes/no in Portuguese
AFFIRMATIVE_RESPONSES = ["sim", "s", "yes", "y", "1", "ok", "pode", "claro"]
NEGATIVE_RESPONSES = ["não", "nao", "n", "no", "0", "nunca"]
```

**Escalation:**
- If > 30% clarification rate → Immediate question revision required
- Coordinate with Content team for rewording

---

### 🔄 HighWebhookDuplicationRate

**Alert:** `Duplicate webhooks > 10/min`

**Impact:** Increased Redis load, potential processing delays.

**Investigation Steps:**

1. **Check Idempotency Cache**
   ```bash
   # Sample duplicate webhook IDs
   redis-cli --scan --pattern "webhook:message:*" --count 100 | head -20

   # Check TTL distribution
   redis-cli --scan --pattern "webhook:message:*" | while read key; do
     ttl=$(redis-cli ttl "$key")
     echo "$ttl"
   done | sort -n | uniq -c
   ```

2. **Review Evolution Webhook Config**
   ```bash
   # Get webhook configuration
   curl -X GET "https://evolution.example.com/webhook/config" \
     -H "apikey: $EVOLUTION_API_KEY"
   ```

3. **Check Webhook Endpoint Health**
   ```bash
   # Test webhook endpoint
   curl -X POST "https://api.hormonia.com/api/v1/webhooks/evolution/message" \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Signature: test" \
     -d '{"event": "test"}'

   # Check response time
   time curl -X POST "https://api.hormonia.com/api/v1/webhooks/evolution/message" \
     -H "Content-Type: application/json" \
     -d @sample_webhook.json
   ```

4. **Analyze Duplicate Patterns**
   ```sql
   -- Check duplicate message IDs in DB
   SELECT
     whatsapp_id,
     COUNT(*) as duplicate_count
   FROM messages
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY whatsapp_id
   HAVING COUNT(*) > 1
   ORDER BY duplicate_count DESC
   LIMIT 20;
   ```

**Common Causes & Fixes:**

| Cause | Symptoms | Fix |
|-------|----------|-----|
| Webhook endpoint timeout | Duplicates after 30s | Optimize webhook processing, return 200 faster |
| Evolution retry policy | Duplicates immediately | Adjust Evolution retry config |
| Network instability | Random duplicate spikes | Check network, add upstream caching |
| Database slowness | Slow idempotency check | Optimize DB query, increase Redis cache TTL |

**Immediate Mitigation:**
```bash
# Increase idempotency cache TTL
redis-cli config set "webhook:message:ttl" 7200  # 2 hours

# Scale webhook processing
kubectl scale deployment/hormonia-backend --replicas=10 -n hormonia
```

**Escalation:**
- If > 100 duplicates/min → Page on-call engineer
- If caused by Evolution API → Escalate to Evolution support

---

### 🔴 ZeroCompletionsIn24Hours

**Alert:** `No quiz completions in last 24 hours for a template`

**Impact:** Data collection stopped, potential system outage.

**Investigation Steps:**

1. **Check Quiz Triggers**
   ```sql
   -- Verify flow triggers are active
   SELECT
     ft.name,
     ft.trigger_config,
     ft.is_active
   FROM flow_templates ft
   WHERE ft.name LIKE '%quiz%'
     AND ft.is_active = TRUE;
   ```

2. **Review Flow Engine Status**
   ```bash
   # Check flow engine health
   curl -X GET "https://api.hormonia.com/health/flow-engine"

   # Check active flows
   curl -X GET "https://api.hormonia.com/api/v1/flows/active" \
     -H "Authorization: Bearer $API_TOKEN"
   ```

3. **Check Patient Eligibility**
   ```sql
   -- Count eligible patients for quiz
   SELECT
     COUNT(DISTINCT p.id) as eligible_patients
   FROM patients p
   LEFT JOIN quiz_sessions qs ON p.id = qs.patient_id
       AND qs.quiz_template_id = '<template_id>'
       AND qs.started_at > NOW() - INTERVAL '30 days'
   WHERE p.is_active = TRUE
     AND qs.id IS NULL;
   ```

4. **Review Recent Errors**
   ```bash
   # Check logs for quiz errors
   kubectl logs -l app=hormonia-backend -n hormonia --since=24h | \
     grep -E "(quiz|QuizSession|QuizResponse)" | \
     grep -i error
   ```

5. **Test Manual Quiz Trigger**
   ```bash
   # Trigger test quiz for a patient
   curl -X POST "https://api.hormonia.com/api/v1/quiz/sessions" \
     -H "Authorization: Bearer $API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "patient_id": "<test_patient_id>",
       "quiz_template_id": "<template_id>"
     }'
   ```

**Common Causes & Fixes:**

| Cause | Symptoms | Fix |
|-------|----------|-----|
| Flow disabled | Flow `is_active = FALSE` | Re-enable flow in admin panel |
| All patients completed | No eligible patients | Review eligibility criteria, adjust frequency |
| Scheduler stopped | No flow triggers firing | Restart Celery beat scheduler |
| Template deactivated | Template `is_active = FALSE` | Re-activate template |

**Immediate Mitigation:**
```bash
# Restart flow engine
kubectl rollout restart deployment/hormonia-backend -n hormonia

# Restart Celery beat (scheduler)
kubectl rollout restart deployment/hormonia-celery-beat -n hormonia
```

**Escalation:**
- If no root cause found in 30 min → Escalate to Engineering lead
- If affecting multiple templates → Declare incident

---

## Metrics Reference

### Completion Metrics

**Key:** `quiz_metrics:completions:{template_id}`
**Type:** Counter
**Retention:** 30 days

**Interpretation:**
- Total completions since metric creation
- Daily breakdowns: `quiz_metrics:completions:{template_id}:daily:{YYYYMMDD}`

**Healthy Range:** > 10 completions/day per active template

---

### Send Latency Metrics

**Key:** `quiz_metrics:send_latency:{template_id}:{message_type}`
**Type:** Sorted Set (scores = latency in seconds)
**Retention:** 7 days, max 1000 samples

**Interpretation:**
- p50: Median send time (typical)
- p95: 95th percentile (most users experience this or better)
- p99: 99th percentile (worst-case for most users)

**Healthy Range:**
- p50: < 0.5s
- p95: < 1.5s
- p99: < 3.0s

---

### Response Latency Metrics

**Key:** `quiz_metrics:response_latency:{template_id}:{question_id}`
**Type:** Sorted Set (scores = latency in seconds)
**Retention:** 7 days, max 500 samples per question

**Interpretation:**
- Time from question sent to patient response received
- High latency may indicate confusing questions

**Healthy Range:**
- p50: < 2 min (120s)
- p95: < 10 min (600s)
- p99: < 30 min (1800s)

---

### Abandonment Metrics

**Key:** `quiz_metrics:abandonment:{template_id}`
**Type:** Counter
**Retention:** 30 days

**Interpretation:**
- Sessions started but not completed
- Calculate rate: `abandonment / (completions + abandonment)`

**Healthy Range:** < 20% abandonment rate

---

## Common Troubleshooting Commands

### Redis Metrics Inspection

```bash
# List all quiz metrics
redis-cli --scan --pattern "quiz_metrics:*"

# Get completion count for template
redis-cli get "quiz_metrics:completions:<template_id>"

# Get send latency samples (last 100)
redis-cli zrange "quiz_metrics:send_latency:<template_id>:question" -100 -1 WITHSCORES

# Calculate p95 manually
redis-cli zrange "quiz_metrics:send_latency:<template_id>:question" -100 -1 WITHSCORES | \
  awk '{if(NR%2==0) print $1}' | sort -n | awk '{a[NR]=$1} END {print a[int(NR*0.95)]}'

# Clear metrics for testing
redis-cli --scan --pattern "quiz_metrics:*" | xargs redis-cli del
```

### Database Queries

```sql
-- Active quiz sessions
SELECT
  p.name as patient_name,
  qt.name as quiz_name,
  qs.current_question_index,
  qs.started_at,
  NOW() - qs.started_at as duration
FROM quiz_sessions qs
JOIN patients p ON qs.patient_id = p.id
JOIN quiz_templates qt ON qs.quiz_template_id = qt.id
WHERE qs.is_completed = FALSE
ORDER BY qs.started_at DESC;

-- Recent completions
SELECT
  qt.name,
  COUNT(*) as completions,
  AVG(EXTRACT(EPOCH FROM (qs.completed_at - qs.started_at))) as avg_duration_seconds
FROM quiz_sessions qs
JOIN quiz_templates qt ON qs.quiz_template_id = qt.id
WHERE qs.is_completed = TRUE
  AND qs.completed_at > NOW() - INTERVAL '24 hours'
GROUP BY qt.name;

-- Question with most clarifications
SELECT
  qt.name,
  qr.question_id,
  COUNT(*) as clarification_count
FROM quiz_responses qr
JOIN quiz_templates qt ON qr.quiz_template_id = qt.id
WHERE qr.response_metadata ? 'validation_error'
  AND qr.responded_at > NOW() - INTERVAL '7 days'
GROUP BY qt.name, qr.question_id
ORDER BY clarification_count DESC
LIMIT 10;
```

### Webhook Testing

```bash
# Test webhook signature validation
./scripts/test_webhook_signature.sh

# Replay webhook from logs
curl -X POST "https://api.hormonia.com/api/v1/webhooks/evolution/message" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: $(./scripts/generate_webhook_sig.sh payload.json)" \
  -d @payload.json

# Check webhook processing latency
kubectl logs -l app=hormonia-backend -n hormonia --tail=100 | \
  grep "Processed inbound message" | \
  awk -F'in ' '{print $2}' | \
  sort -n
```

---

## Escalation Matrix

| Severity | Response Time | Escalation Path |
|----------|---------------|-----------------|
| **Critical** (p95 latency > 5s, abandonment > 40%) | 15 min | On-call engineer → Engineering lead → CTO |
| **Warning** (p95 latency > 2s, abandonment > 20%) | 1 hour | On-call engineer → Team lead |
| **Info** (trends, minor issues) | 24 hours | Team Slack channel → Weekly review |

**Contact Info:**
- On-call Engineer: PagerDuty rotation
- Engineering Lead: Slack @eng-lead
- Platform Team: Slack #platform-support
- Evolution API Support: support@evolution.com

---

## Useful Links

- [Grafana Dashboard](https://grafana.example.com/d/quiz-metrics-hormonia)
- [E2E Test Documentation](../docs/QUIZ_E2E_TESTING_METRICS.md)
- [Quiz Service Code](../app/services/quiz.py)
- [Webhook Processor Code](../app/services/webhook_processor.py)
- [Metrics Collector Code](../app/services/quiz_metrics.py)
- [Alert Definitions](../monitoring/prometheus/rules/quiz_alerts.yml)
