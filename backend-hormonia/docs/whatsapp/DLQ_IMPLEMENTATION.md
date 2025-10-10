# Dead Letter Queue (DLQ) Implementation

## Overview

The Dead Letter Queue (DLQ) system prevents critical WhatsApp messages from being silently dropped after exhausting retry attempts. Messages that fail delivery after max retries are routed to the DLQ for manual review, analysis, and selective retry.

## Architecture

### Components

1. **FailedMessage Model** (`app/models/failed_message.py`)
   - Stores failed messages with full context
   - Tracks failure reason, retry attempts, and review status
   - Supports workflow: pending_review → under_review → approved_for_retry → requeued

2. **DLQHandler Service** (`app/integrations/whatsapp/queue/dlq.py`)
   - Routes failed messages to DLQ
   - Categorizes failure reasons
   - Manages review workflow
   - Enables manual retry

3. **Admin API** (`app/api/v1/admin/dlq.py`)
   - GET /admin/dlq/pending - List messages awaiting review
   - GET /admin/dlq/critical - Get high-priority failures
   - POST /admin/dlq/{id}/review - Review and approve/reject
   - POST /admin/dlq/{id}/requeue - Retry failed message
   - GET /admin/dlq/metrics/overview - DLQ analytics

4. **Database Table** (`whatsapp_delivery_failures`)
   - Migration: `20251009_230000_add_whatsapp_delivery_failures.py`
   - Indexes for efficient querying
   - Foreign keys to messages, patients, users

### Failure Reasons

Categorized enum for root cause analysis:

- `MAX_RETRIES_EXCEEDED` - Exhausted all retry attempts
- `NETWORK_ERROR` - Network connectivity issues
- `API_ERROR` - WhatsApp API errors (4xx, 5xx)
- `INVALID_PHONE` - Invalid phone number format
- `BLOCKED_NUMBER` - Number blocked by WhatsApp
- `RATE_LIMIT` - API rate limit exceeded (429)
- `TIMEOUT` - Request timeout
- `UNKNOWN` - Unclassified error

### DLQ Statuses

Workflow states for message lifecycle:

- `PENDING_REVIEW` - Awaiting admin review (initial state)
- `UNDER_REVIEW` - Admin is investigating
- `APPROVED_FOR_RETRY` - Admin approved retry
- `REQUEUED` - Message sent back to delivery queue
- `PERMANENTLY_FAILED` - Cannot be retried (e.g., invalid phone)
- `RESOLVED` - Issue resolved (manual intervention)

## Integration with MessageScheduler

### Automatic DLQ Routing

When a message fails permanently (max retries exceeded), `MessageScheduler.on_delivery_failure()` automatically:

1. Categorizes failure reason
2. Routes to DLQ via `DLQHandler.route_to_dlq()`
3. Updates flow state to prevent blocking
4. Logs failure for monitoring

```python
# In message_scheduler.py
async def on_delivery_failure(self, message_id, failure_reason, whatsapp_error):
    if message.retry_count >= max_retries:
        # Route to DLQ
        await self._route_to_dlq_on_max_retries(message, failure_reason, whatsapp_error)
```

### Failure Categorization

The `_categorize_failure_reason()` method analyzes error details:

```python
def _categorize_failure_reason(self, delivery_info):
    error_message = str(delivery_info.get('error', '')).lower()

    if 'timeout' in error_message:
        return FailureReason.TIMEOUT
    elif 'invalid' in error_message and 'phone' in error_message:
        return FailureReason.INVALID_PHONE
    # ... more categorization logic
```

## Usage

### Admin Review Workflow

1. **List Pending Messages**
   ```bash
   GET /admin/dlq/pending?limit=50&offset=0
   ```

2. **Get Critical Failures** (high retry count, recent)
   ```bash
   GET /admin/dlq/critical?hours_back=24&limit=20
   ```

3. **Review Message**
   ```bash
   POST /admin/dlq/{dlq_id}/review
   {
     "approve_retry": true,
     "notes": "Network issue resolved, safe to retry"
   }
   ```

4. **Re-queue for Retry**
   ```bash
   POST /admin/dlq/{dlq_id}/requeue
   {
     "immediate": false  # false = scheduled, true = retry ASAP
   }
   ```

5. **Monitor Metrics**
   ```bash
   GET /admin/dlq/metrics/overview?days_back=7
   ```

### Programmatic Usage

```python
from app.integrations.whatsapp.queue.dlq import DLQHandler

# Route failed message to DLQ
dlq_handler = DLQHandler(db)
await dlq_handler.route_to_dlq(
    message_id=message.id,
    patient_id=patient.id,
    content="Test message",
    whatsapp_phone="+5511999999999",
    failure_reason=FailureReason.NETWORK_ERROR,
    failure_details={"error": "Timeout"},
    retry_count=3
)

# Get pending messages
pending = await dlq_handler.get_pending_review(limit=50)

# Review and approve
reviewed = await dlq_handler.review_message(
    dlq_id=dlq_entry.id,
    reviewer_id=admin.id,
    approve_retry=True,
    notes="Network resolved"
)

# Re-queue for retry
result = await dlq_handler.requeue_for_retry(
    dlq_id=dlq_entry.id,
    immediate=False
)
```

## Monitoring & Alerting

### Key Metrics

DLQ metrics endpoint provides:

- **Total failures** in period
- **Failure breakdown by reason** (network, API, timeout, etc.)
- **Status distribution** (pending, requeued, permanently failed)
- **Average retry count** before DLQ routing
- **Requeue success rate**

### Alerting Triggers

Set up alerts for:

1. **Critical Failures** - Messages with retry_count >= 3
2. **High DLQ Volume** - More than X messages per hour
3. **Specific Failure Reasons** - All `INVALID_PHONE` or `BLOCKED_NUMBER`
4. **Long Pending Time** - Messages pending review > 24 hours

### Example Alert Query

```python
# Get critical failures from last hour
critical = await dlq_handler.get_critical_failures(hours_back=1, limit=100)

if len(critical) > 10:
    send_alert("High number of critical DLQ failures", critical)
```

## Database Schema

```sql
CREATE TABLE whatsapp_delivery_failures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    whatsapp_phone VARCHAR(20) NOT NULL,
    failure_reason failure_reason NOT NULL,  -- Enum
    failure_details JSONB DEFAULT '{}',
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dlq_status dlq_status NOT NULL DEFAULT 'pending_review',  -- Enum
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    requeue_count INTEGER NOT NULL DEFAULT 0,
    last_requeue_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX ix_whatsapp_delivery_failures_patient_id ON whatsapp_delivery_failures(patient_id);
CREATE INDEX ix_whatsapp_delivery_failures_dlq_status ON whatsapp_delivery_failures(dlq_status);
CREATE INDEX ix_whatsapp_delivery_failures_failure_reason ON whatsapp_delivery_failures(failure_reason);
CREATE INDEX ix_whatsapp_delivery_failures_status_failed_at ON whatsapp_delivery_failures(dlq_status, failed_at);
CREATE INDEX ix_whatsapp_delivery_failures_retry_status ON whatsapp_delivery_failures(retry_count, dlq_status, failed_at);
```

## Testing

Comprehensive integration tests in `tests/integration/whatsapp/test_dlq.py`:

- **Routing Tests** - Verify DLQ routing on max retries
- **Review Tests** - Test approve/reject workflow
- **Requeue Tests** - Verify retry scheduling
- **Metrics Tests** - Analytics accuracy
- **Integration Tests** - End-to-end MessageScheduler → DLQ flow

Run tests:
```bash
pytest tests/integration/whatsapp/test_dlq.py -v
```

## Success Criteria

✅ **No Silent Failures** - All failed messages captured in DLQ
✅ **Manual Review** - Admin can review and decide on retry
✅ **Selective Retry** - Only approved messages re-queued
✅ **Fast Recovery** - <5 minute requeue time for urgent messages
✅ **Monitoring** - Real-time metrics and alerting
✅ **Audit Trail** - Full history of failures, reviews, retries

## Configuration

Add to `.env`:

```bash
# WhatsApp DLQ Configuration
WHATSAPP_MAX_RETRIES=3  # Messages route to DLQ after 3 retries
WHATSAPP_RETRY_DELAY_SECONDS=60  # Initial retry delay
```

## Migration

Run migration to create DLQ table:

```bash
cd backend-hormonia
alembic upgrade head
```

## Related Documentation

- [RATE_LIMITING.md](../RATE_LIMITING.md) - Rate limiting for WhatsApp API
- [WHATSAPP_INTEGRATION_FLOW.md](../architecture/WHATSAPP_INTEGRATION_FLOW.md) - Overall WhatsApp integration
- [Message Scheduler](../services/message_scheduler.py) - Message scheduling service

## Support

For issues or questions:
1. Check DLQ metrics for patterns
2. Review failed_message records in database
3. Analyze failure_details JSONB for error context
4. Consult MessageScheduler logs for retry history
