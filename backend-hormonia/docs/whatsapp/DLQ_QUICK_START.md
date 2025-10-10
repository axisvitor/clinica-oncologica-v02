# Dead Letter Queue (DLQ) - Quick Start Guide

## What is the DLQ?

The Dead Letter Queue (DLQ) prevents critical WhatsApp messages from being silently dropped after max retry attempts. Failed messages are routed to DLQ for manual review and selective retry.

## Quick Setup

### 1. Run Migration

```bash
cd backend-hormonia
alembic upgrade head
```

This creates the `whatsapp_delivery_failures` table.

### 2. Configure Environment

Add to `.env`:

```bash
WHATSAPP_MAX_RETRIES=3  # Messages route to DLQ after 3 retries
WHATSAPP_RETRY_DELAY_SECONDS=60  # Initial retry delay
```

### 3. Verify Integration

The DLQ is automatically integrated into `MessageScheduler`. When a message fails permanently:

```python
# Automatically routes to DLQ
await message_scheduler.on_delivery_failure(
    message_id=message.id,
    failure_reason="Network timeout",
    whatsapp_error={"error": "ETIMEDOUT"}
)
```

## Admin Usage

### View Pending Messages

```bash
GET /admin/dlq/pending?limit=50
```

**Response:**
```json
[
  {
    "id": "uuid",
    "patient_id": "uuid",
    "whatsapp_phone": "+5511999999999",
    "content": "Test message",
    "failure_reason": "network_error",
    "retry_count": 3,
    "failed_at": "2025-10-09T23:00:00Z",
    "dlq_status": "pending_review"
  }
]
```

### Get Critical Failures

High-priority failures needing immediate attention:

```bash
GET /admin/dlq/critical?hours_back=24&limit=20
```

### Review Message

Approve or reject retry:

```bash
POST /admin/dlq/{dlq_id}/review
{
  "approve_retry": true,
  "notes": "Network issue resolved, safe to retry"
}
```

### Retry Message

Send back to delivery queue:

```bash
POST /admin/dlq/{dlq_id}/requeue
{
  "immediate": false  # false = scheduled, true = retry ASAP
}
```

### Monitor Metrics

```bash
GET /admin/dlq/metrics/overview?days_back=7
```

**Response:**
```json
{
  "total_failures": 42,
  "failure_by_reason": {
    "network_error": 15,
    "timeout": 12,
    "api_error": 10,
    "rate_limit": 5
  },
  "status_distribution": {
    "pending_review": 20,
    "requeued": 15,
    "permanently_failed": 7
  },
  "avg_retry_count": 3.2,
  "requeue_rate": 45.2,
  "period_days": 7
}
```

## Programmatic Usage

```python
from app.integrations.whatsapp.queue.dlq import DLQHandler
from app.models.failed_message import FailureReason

# Get DLQ handler
dlq = DLQHandler(db)

# Route failed message
await dlq.route_to_dlq(
    message_id=message.id,
    patient_id=patient.id,
    content="Failed message",
    whatsapp_phone="+5511999999999",
    failure_reason=FailureReason.NETWORK_ERROR,
    failure_details={"error": "Timeout"},
    retry_count=3
)

# Get pending messages
pending = await dlq.get_pending_review(limit=50)

# Review message
reviewed = await dlq.review_message(
    dlq_id=entry.id,
    reviewer_id=admin.id,
    approve_retry=True,
    notes="Safe to retry"
)

# Requeue for retry
result = await dlq.requeue_for_retry(
    dlq_id=entry.id,
    immediate=False
)
```

## Failure Reasons

| Reason | Description | Auto-Retry? |
|--------|-------------|-------------|
| `max_retries_exceeded` | Exhausted all retry attempts | No |
| `network_error` | Network connectivity issues | Yes |
| `api_error` | WhatsApp API errors | Yes |
| `invalid_phone` | Invalid phone number | No |
| `blocked_number` | Blocked by WhatsApp | No |
| `rate_limit` | API rate limit (429) | Yes |
| `timeout` | Request timeout | Yes |
| `unknown` | Unclassified error | Manual |

## Workflow States

```
PENDING_REVIEW
    ↓
UNDER_REVIEW (admin investigating)
    ↓
APPROVED_FOR_RETRY (approved by admin)
    ↓
REQUEUED (sent back to delivery queue)
```

Alternative paths:
- `PERMANENTLY_FAILED` - Cannot retry (e.g., invalid phone)
- `RESOLVED` - Issue manually resolved

## Monitoring & Alerts

### Key Metrics to Monitor

1. **DLQ Volume** - Messages entering DLQ per hour
2. **Critical Failures** - Messages with retry_count >= 3
3. **Pending Time** - How long messages wait for review
4. **Requeue Success Rate** - % of requeued messages delivered

### Alert Examples

```python
# Alert on high DLQ volume
critical = await dlq.get_critical_failures(hours_back=1)
if len(critical) > 10:
    send_alert("High DLQ volume", critical)

# Alert on specific failure reasons
pending = await dlq.get_pending_review()
invalid_phones = [m for m in pending if m.failure_reason == FailureReason.INVALID_PHONE]
if len(invalid_phones) > 5:
    send_alert("Multiple invalid phone numbers", invalid_phones)
```

## Testing

Run integration tests:

```bash
pytest tests/integration/whatsapp/test_dlq.py -v
```

Test categories:
- **Routing** - DLQ routing on max retries
- **Review** - Approve/reject workflow
- **Requeue** - Retry scheduling
- **Metrics** - Analytics accuracy

## Common Issues

### Issue: Messages not routing to DLQ

**Check:**
1. `WHATSAPP_MAX_RETRIES` configured in `.env`
2. Migration applied (`alembic upgrade head`)
3. MessageScheduler calling `on_delivery_failure()`

### Issue: Cannot requeue message

**Check:**
1. Message status is `PENDING_REVIEW` or `APPROVED_FOR_RETRY`
2. Admin has reviewed message (if required)
3. Message not already `REQUEUED` or `PERMANENTLY_FAILED`

### Issue: High DLQ volume

**Investigate:**
1. Check `failure_by_reason` in metrics
2. Network connectivity issues?
3. WhatsApp API rate limits?
4. Invalid patient phone numbers?

## Best Practices

1. **Review Daily** - Check pending messages at least once per day
2. **Categorize Failures** - Use failure reasons for root cause analysis
3. **Monitor Metrics** - Set up alerts for critical failures
4. **Document Decisions** - Add review notes when approving/rejecting
5. **Test Retries** - Use `immediate: false` for scheduled retries
6. **Permanent Failures** - Mark invalid phones as permanently failed

## Success Criteria

✅ No messages silently dropped
✅ <5 minute recovery time for critical messages
✅ >90% requeue success rate
✅ <24 hour average pending time
✅ Clear audit trail for all failures

## Next Steps

1. Set up monitoring dashboard
2. Configure alerting rules
3. Train admin team on review workflow
4. Review DLQ metrics weekly
5. Optimize failure categorization

## Support

For detailed documentation, see:
- [DLQ_IMPLEMENTATION.md](DLQ_IMPLEMENTATION.md) - Full implementation details
- [WHATSAPP_INTEGRATION_FLOW.md](../architecture/WHATSAPP_INTEGRATION_FLOW.md) - Overall flow
