# Evolution API Webhook Integration Fixes

**Date:** 2025-10-11
**Status:** ✅ Completed
**Priority:** P0 (Critical)

## Overview

This document details the critical fixes implemented for the Evolution API webhook integration to ensure reliable, secure, and auditable webhook processing.

## Fixes Implemented

### 1. ✅ Enforce Webhook Security (Priority P0)

**Problem:**
- Webhook signature validation was optional in production
- Security risk: Unauthenticated webhooks could be processed
- File: `app/integrations/evolution.py:672`

**Solution:**
- Made signature validation **mandatory in production**
- Reject webhooks without valid signatures when `ENVIRONMENT=production`
- Allow bypass only in development environment for testing

**Files Modified:**
- `backend-hormonia/app/integrations/evolution.py` (lines 666-677)
- `backend-hormonia/app/api/v1/webhooks.py` (lines 20-62)

**Code Changes:**
```python
# evolution.py
if not validation_secret:
    if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
        logger.error("Webhook signature validation required in production")
        return False  # REJECT in production
    return True  # Allow only in development

# webhooks.py
if not settings.EVOLUTION_WEBHOOK_SECRET:
    if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
        logger.error("Webhook secret required in production environment")
        return False
    return True  # Allow in development
```

**Testing:**
```bash
# Test in development (should pass)
export ENVIRONMENT=development
curl -X POST http://localhost:8000/webhooks/evolution/message -d '{...}'

# Test in production without signature (should fail with 401)
export ENVIRONMENT=production
curl -X POST http://localhost:8000/webhooks/evolution/message -d '{...}'
# Expected: 401 Unauthorized

# Test in production with valid signature (should pass)
export EVOLUTION_WEBHOOK_SECRET=your_secret
curl -X POST http://localhost:8000/webhooks/evolution/message \
  -H "X-Signature: sha256=<valid_signature>" \
  -d '{...}'
```

---

### 2. ✅ Add Webhook Database Persistence (Priority P0)

**Problem:**
- Webhooks were processed but not stored in database
- No audit trail for webhook events
- No way to retry failed webhooks
- File: `app/services/webhook_processor.py`

**Solution:**
- Persist all webhook events to `webhook_events` table
- Store event metadata (type, source, payload, timestamp)
- Generate event hash for idempotency
- Track processing status (processed, retry_count, error_message)
- Link to related message_id and patient_id when available

**Files Modified:**
- `backend-hormonia/app/services/webhook_processor.py` (lines 742-1093)

**Database Schema (Already Exists):**
```sql
-- webhook_events table (17 columns)
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    source VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    error_stack_trace TEXT,
    related_message_id UUID,
    related_patient_id UUID,
    event_hash VARCHAR(64) UNIQUE,  -- For idempotency
    is_duplicate BOOLEAN DEFAULT false,
    original_event_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX ix_webhook_type_processed ON webhook_events(event_type, processed, created_at);
CREATE INDEX ix_webhook_retry_schedule ON webhook_events(processed, next_retry_at);
CREATE INDEX ix_webhook_pending ON webhook_events(processed, retry_count, created_at);
```

**New Methods:**
- `_persist_webhook_event()` - Save webhook to database
- `_mark_webhook_processed()` - Update processing status

**Integration:**
All webhook handlers now persist events:
- `process_message_webhook()` - Stores message.received events
- `process_status_webhook()` - Stores message.status events
- `process_connection_webhook()` - Stores connection.update events
- `process_qrcode_webhook()` - Stores qrcode.updated events

**Testing:**
```sql
-- Check webhook events are being persisted
SELECT event_type, source, processed, retry_count, created_at
FROM webhook_events
ORDER BY created_at DESC
LIMIT 10;

-- Check failed webhooks
SELECT id, event_type, error_message, retry_count, next_retry_at
FROM webhook_events
WHERE processed = false
  AND retry_count < max_retries;

-- Check idempotency (should not have duplicates)
SELECT event_hash, COUNT(*) as count
FROM webhook_events
GROUP BY event_hash
HAVING COUNT(*) > 1;
```

---

### 3. ✅ Implement Connection Webhook Handler (Priority P0)

**Problem:**
- Connection webhook endpoint existed but handler was incomplete
- No way to track WhatsApp instance connection state
- File: `app/services/webhook_processor.py`

**Solution:**
- Implemented `process_connection_webhook()` method
- Handles connection.update events from Evolution API
- Updates instance status in Redis for real-time monitoring
- Supports connection states: open, close, connecting

**Files Modified:**
- `backend-hormonia/app/services/webhook_processor.py` (lines 870-922)
- `backend-hormonia/app/api/v1/webhooks.py` (already had endpoint at line 125)

**Connection States:**
- `open` - Instance is connected to WhatsApp
- `close` - Instance disconnected
- `connecting` - Instance is connecting

**Code Implementation:**
```python
async def process_connection_webhook(self, event_data: dict[str, Any]) -> bool:
    """Process connection status webhook (connection.update events)."""
    # 1. Persist webhook event
    webhook_id = await self._persist_webhook_event(
        event_type="connection.update",
        source="evolution_api",
        payload=event_data
    )

    # 2. Extract connection data
    instance = event_data.get("instance")
    state = event_data.get("state") or event_data.get("data", {}).get("state")

    # 3. Update connection state in Redis
    await self.connection_state_repo.set_state(instance, state)

    # 4. Mark as processed
    await self._mark_webhook_processed(webhook_id, True)
```

**Testing:**
```bash
# Test connection webhook
curl -X POST http://localhost:8000/webhooks/evolution/connection \
  -H "Content-Type: application/json" \
  -H "X-Signature: sha256=<signature>" \
  -d '{
    "instance": "hormonia",
    "state": "open"
  }'

# Check Redis for connection state
redis-cli GET "connection_state:hormonia"
```

---

### 4. ✅ Add Basic Webhook Retry (Priority P0)

**Problem:**
- Failed webhooks were lost
- No automatic retry mechanism
- Network issues caused permanent data loss

**Solution:**
- Implemented `retry_failed_webhooks()` method
- Simple exponential backoff: 60s → 120s → 240s
- Background worker script for continuous retry
- Leverages existing `retry_count` and `next_retry_at` columns

**Files Modified:**
- `backend-hormonia/app/services/webhook_processor.py` (lines 985-1093)
- `backend-hormonia/scripts/webhook_retry_worker.py` (new file)

**Retry Logic:**
```python
# Exponential backoff formula
next_retry_delay = 60 * (2 ** retry_count)
# Result: 60s, 120s, 240s (for retry_count 0, 1, 2)

# Max retries: 3 (configurable via max_retries column)
```

**Background Worker:**
```bash
# Run webhook retry worker
python scripts/webhook_retry_worker.py

# Configure retry interval (default: 60s)
export WEBHOOK_RETRY_INTERVAL=60
python scripts/webhook_retry_worker.py

# Run as systemd service (recommended for production)
sudo systemctl start webhook-retry
sudo systemctl enable webhook-retry
```

**Systemd Service Example:**
```ini
[Unit]
Description=Webhook Retry Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/app/backend-hormonia
Environment="WEBHOOK_RETRY_INTERVAL=60"
ExecStart=/usr/bin/python3 scripts/webhook_retry_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Testing:**
```bash
# Manually trigger retry
python -c "
from app.database import get_db
from app.services.webhook_processor import WebhookProcessor
import asyncio

async def test_retry():
    db = next(get_db())
    processor = WebhookProcessor(db)
    count = await processor.retry_failed_webhooks()
    print(f'Retried {count} webhooks')
    db.close()

asyncio.run(test_retry())
"

# Check retry worker logs
tail -f logs/webhook_retry.log
```

---

### 5. ✅ Add QR Code Handler (Priority P1)

**Problem:**
- No handler for qrcode.updated events
- QR codes not stored for UI display during WhatsApp instance setup
- File: `app/services/webhook_processor.py`

**Solution:**
- Implemented `process_qrcode_webhook()` method
- Stores QR code data in Redis with 5-minute TTL
- New webhook endpoint `/webhooks/evolution/qrcode`

**Files Modified:**
- `backend-hormonia/app/services/webhook_processor.py` (lines 924-983)
- `backend-hormonia/app/api/v1/webhooks.py` (lines 171-208)

**QR Code Storage:**
```python
# Stored in Redis with metadata
qr_data = {
    "instance": "hormonia",
    "qrcode": "data:image/png;base64,...",  # Base64 encoded QR code
    "timestamp": "2025-10-11T12:00:00Z",
    "status": "pending"
}

# Key format: qrcode:{instance_name}
# TTL: 300 seconds (5 minutes)
```

**Testing:**
```bash
# Test QR code webhook
curl -X POST http://localhost:8000/webhooks/evolution/qrcode \
  -H "Content-Type: application/json" \
  -H "X-Signature: sha256=<signature>" \
  -d '{
    "instance": "hormonia",
    "qrcode": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg..."
  }'

# Retrieve QR code from Redis
redis-cli GET "qrcode:hormonia"

# Check expiration (should be ~300 seconds)
redis-cli TTL "qrcode:hormonia"
```

---

## Summary of Changes

| Fix | Priority | Files Modified | Lines Changed | Status |
|-----|----------|----------------|---------------|--------|
| 1. Webhook Security | P0 | 2 files | ~40 lines | ✅ Complete |
| 2. Database Persistence | P0 | 1 file | ~150 lines | ✅ Complete |
| 3. Connection Handler | P0 | 1 file | ~50 lines | ✅ Complete |
| 4. Webhook Retry | P0 | 2 files | ~150 lines | ✅ Complete |
| 5. QR Code Handler | P1 | 2 files | ~70 lines | ✅ Complete |

**Total:** ~460 lines of functional code added

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Evolution API Webhooks                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│            FastAPI Webhook Endpoints                         │
│  • /webhooks/evolution/message     (POST)                    │
│  • /webhooks/evolution/status      (POST)                    │
│  • /webhooks/evolution/connection  (POST)                    │
│  • /webhooks/evolution/qrcode      (POST)                    │
│                                                               │
│  ✅ Signature Validation (P0 Fix #1)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  WebhookProcessor Service                    │
│                                                               │
│  ✅ Persistence (P0 Fix #2)                                 │
│     • _persist_webhook_event()                               │
│     • _mark_webhook_processed()                              │
│                                                               │
│  ✅ Connection Handler (P0 Fix #3)                          │
│     • process_connection_webhook()                           │
│                                                               │
│  ✅ QR Code Handler (P0 Fix #5)                             │
│     • process_qrcode_webhook()                               │
│                                                               │
│  ✅ Retry Mechanism (P0 Fix #4)                             │
│     • retry_failed_webhooks()                                │
└─────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
    ┌──────────────┐  ┌─────────────────┐  ┌─────────────┐
    │  PostgreSQL  │  │      Redis      │  │  Background │
    │              │  │                 │  │   Worker    │
    │ webhook_     │  │ connection_     │  │             │
    │  events      │  │  state:*        │  │ retry_      │
    │              │  │ qrcode:*        │  │  failed_    │
    │ webhook_     │  │                 │  │  webhooks() │
    │  idempotency │  │                 │  │             │
    └──────────────┘  └─────────────────┘  └─────────────┘
```

---

## Redis Cloud Benefits Leveraged

✅ **High Connection Capacity (1000+ concurrent)**
- No connection pooling optimization needed
- Safe to use 100-200 connections
- Built-in failover and HA

✅ **Fast In-Memory Operations**
- QR code storage with TTL
- Connection state caching
- Idempotency key lookup (fast path)

✅ **Low Latency**
- Sub-millisecond response times
- Perfect for real-time webhook processing

---

## Environment Variables

```bash
# Required for production
ENVIRONMENT=production
EVOLUTION_WEBHOOK_SECRET=your_webhook_secret_here
EVOLUTION_API_KEY=your_api_key_here

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://user:pass@redis-cloud-host:6379

# Webhook retry worker
WEBHOOK_RETRY_INTERVAL=60  # seconds between retry cycles
```

---

## Monitoring & Metrics

### Database Queries

```sql
-- Webhook processing stats
SELECT
    event_type,
    COUNT(*) as total,
    SUM(CASE WHEN processed THEN 1 ELSE 0 END) as processed,
    SUM(CASE WHEN NOT processed THEN 1 ELSE 0 END) as pending,
    AVG(retry_count) as avg_retries
FROM webhook_events
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY event_type;

-- Failed webhooks requiring attention
SELECT id, event_type, error_message, retry_count, next_retry_at
FROM webhook_events
WHERE processed = false
  AND retry_count >= max_retries
ORDER BY created_at DESC;

-- Webhook processing latency
SELECT
    event_type,
    AVG(EXTRACT(EPOCH FROM (processed_at - created_at))) as avg_latency_seconds
FROM webhook_events
WHERE processed = true
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY event_type;
```

### Redis Keys

```bash
# Check connection states
redis-cli KEYS "connection_state:*"

# Check QR codes
redis-cli KEYS "qrcode:*"

# Check idempotency keys
redis-cli KEYS "webhook:message:*"
```

---

## Error Handling

### Webhook Persistence Failure
- Logs error and continues processing
- Webhook not stored but still processed
- Idempotency via Redis remains active

### Connection Update Failure
- Logs error, marks webhook as failed
- Scheduled for retry via retry worker
- Connection state remains stale until success

### QR Code Storage Failure
- Logs error, marks webhook as failed
- QR code not displayed to user
- Retry will attempt to re-store

### Retry Worker Crash
- Systemd restarts service automatically
- Unprocessed webhooks remain in database
- Will be picked up on next cycle

---

## Production Deployment Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Configure `EVOLUTION_WEBHOOK_SECRET`
- [ ] Ensure Redis Cloud is accessible
- [ ] Database has `webhook_events` table
- [ ] Deploy webhook retry worker as systemd service
- [ ] Configure monitoring alerts for failed webhooks
- [ ] Test signature validation (should reject unsigned requests)
- [ ] Verify QR code display in UI
- [ ] Monitor retry worker logs
- [ ] Set up alerting for `retry_count >= max_retries`

---

## Future Enhancements (Out of Scope)

1. **Webhook Analytics Dashboard**
   - Real-time processing metrics
   - Failure rate graphs
   - Retry success rates

2. **Advanced Retry Strategies**
   - Priority-based retry queues
   - Custom retry intervals per event type
   - Circuit breaker for failing endpoints

3. **Webhook Replay API**
   - Manual replay of failed webhooks
   - Bulk replay operations
   - Admin UI for webhook management

4. **Distributed Retry Workers**
   - Multiple worker instances
   - Redis-based job queue
   - Load balancing across workers

---

## References

- Evolution API Documentation: https://doc.evolution-api.com/v2/pt/webhooks
- Webhook Security Best Practices: https://webhooks.fyi/security/hmac
- PostgreSQL JSONB Performance: https://www.postgresql.org/docs/current/datatype-json.html
- Redis Cloud Documentation: https://redis.io/docs/latest/operate/rc/

---

**Implementation Date:** October 11, 2025
**Author:** Claude (AI Code Implementation Agent)
**Review Status:** ✅ Ready for Testing
**Deployment Status:** 🚀 Ready for Production
