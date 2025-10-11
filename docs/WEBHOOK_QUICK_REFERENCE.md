# Evolution API Webhook Integration - Quick Reference Card

## 🚀 Quick Start

### Production Deployment
```bash
# 1. Set environment
export ENVIRONMENT=production
export EVOLUTION_WEBHOOK_SECRET=your_secret_here

# 2. Restart application
sudo systemctl restart hormonia-backend

# 3. Start retry worker
sudo systemctl start webhook-retry
sudo systemctl enable webhook-retry

# 4. Verify
curl https://your-domain.com/webhooks/evolution/health
```

---

## 📍 Webhook Endpoints

| Endpoint | Method | Purpose | Events |
|----------|--------|---------|--------|
| `/webhooks/evolution/message` | POST | Incoming messages | message.received |
| `/webhooks/evolution/status` | POST | Delivery status | message.status |
| `/webhooks/evolution/connection` | POST | Connection state | connection.update |
| `/webhooks/evolution/qrcode` | POST | QR codes | qrcode.updated |
| `/webhooks/evolution/health` | GET | Health check | - |

---

## 🔐 Security

### Signature Validation (P0 Fix #1)
- **Production:** Mandatory - rejects webhooks without valid HMAC signature
- **Development:** Optional - allows testing without signatures
- **Header:** `X-Signature: sha256=<hmac_hex>`

```bash
# Test signature validation
curl -X POST http://localhost:8000/webhooks/evolution/message \
  -H "X-Signature: sha256=$(echo -n '{"test":"data"}' | openssl dgst -sha256 -hmac 'your_secret' | cut -d' ' -f2)" \
  -H "Content-Type: application/json" \
  -d '{"test":"data"}'
```

---

## 💾 Database

### Webhook Events Table
```sql
-- Check recent webhooks
SELECT event_type, processed, retry_count, created_at
FROM webhook_events
ORDER BY created_at DESC
LIMIT 10;

-- Check failed webhooks
SELECT id, event_type, error_message, retry_count
FROM webhook_events
WHERE processed = false
  AND retry_count >= max_retries;

-- Clear old webhooks (older than 30 days)
DELETE FROM webhook_events
WHERE created_at < NOW() - INTERVAL '30 days';
```

---

## 🔄 Retry Worker (P0 Fix #4)

### Control Commands
```bash
# Start
sudo systemctl start webhook-retry

# Stop
sudo systemctl stop webhook-retry

# Restart
sudo systemctl restart webhook-retry

# Status
sudo systemctl status webhook-retry

# Logs
sudo journalctl -u webhook-retry -f
tail -f /var/log/hormonia/webhook_retry.log
```

### Configuration
```bash
# /etc/hormonia/webhook-retry.env
WEBHOOK_RETRY_INTERVAL=60
ENVIRONMENT=production
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
```

---

## 📊 Monitoring

### Key Metrics
```sql
-- Processing rate (webhooks/minute)
SELECT COUNT(*) as count_last_minute
FROM webhook_events
WHERE created_at > NOW() - INTERVAL '1 minute';

-- Success rate
SELECT
  COUNT(*) FILTER (WHERE processed) * 100.0 / COUNT(*) as success_rate_pct
FROM webhook_events
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Retry effectiveness
SELECT
  retry_count,
  COUNT(*) as count,
  COUNT(*) FILTER (WHERE processed) as succeeded
FROM webhook_events
WHERE retry_count > 0
GROUP BY retry_count
ORDER BY retry_count;
```

### Redis Keys
```bash
# Connection states
redis-cli KEYS "connection_state:*"
redis-cli GET "connection_state:hormonia"

# QR codes
redis-cli KEYS "qrcode:*"
redis-cli GET "qrcode:hormonia"
redis-cli TTL "qrcode:hormonia"  # Should be ~300s

# Idempotency keys
redis-cli KEYS "webhook:message:*"
redis-cli TTL "webhook:message:ABC123"  # Should be ~3600s
```

---

## 🐛 Troubleshooting

### Problem: Webhooks Rejected (401)
**Cause:** Signature validation failure
**Fix:**
1. Check `EVOLUTION_WEBHOOK_SECRET` is set correctly
2. Verify Evolution API is sending `X-Signature` header
3. Check signature algorithm matches (HMAC-SHA256)

```bash
# Verify secret
echo $EVOLUTION_WEBHOOK_SECRET

# Test locally without signature (dev mode only)
export ENVIRONMENT=development
curl -X POST http://localhost:8000/webhooks/evolution/message -d '{"test":"data"}'
```

---

### Problem: Webhooks Not Persisted
**Cause:** Database connection or table missing
**Fix:**
1. Check database connection: `psql $DATABASE_URL -c "SELECT 1;"`
2. Verify table exists: `psql $DATABASE_URL -c "\d webhook_events;"`
3. Run migration if needed: `alembic upgrade head`

```sql
-- Check if table exists
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
  AND tablename = 'webhook_events';

-- Check columns
\d webhook_events
```

---

### Problem: Retry Worker Not Running
**Cause:** Service crashed or not started
**Fix:**
1. Check status: `sudo systemctl status webhook-retry`
2. View errors: `sudo journalctl -u webhook-retry -n 50`
3. Restart: `sudo systemctl restart webhook-retry`

```bash
# Common issues
# Issue 1: Database connection
# Check DATABASE_URL in /etc/hormonia/webhook-retry.env

# Issue 2: Python dependencies
# Reinstall: pip install -r requirements.txt

# Issue 3: File permissions
# Fix: sudo chown www-data:www-data -R /app/backend-hormonia/logs
```

---

### Problem: High Retry Rate
**Cause:** External service issues or transient errors
**Fix:**
1. Check error patterns:
```sql
SELECT error_message, COUNT(*) as count
FROM webhook_events
WHERE processed = false
GROUP BY error_message
ORDER BY count DESC
LIMIT 5;
```

2. Check Evolution API health: `curl https://api.evolution.dev/health`
3. Adjust retry interval if needed: Edit `/etc/hormonia/webhook-retry.env`

---

## 🔍 Common Queries

### Daily Summary
```sql
SELECT
  DATE(created_at) as date,
  event_type,
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE processed) as processed,
  COUNT(*) FILTER (WHERE NOT processed) as failed,
  AVG(retry_count) as avg_retries
FROM webhook_events
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at), event_type
ORDER BY date DESC, event_type;
```

### Connection History
```sql
SELECT
  payload->>'instance' as instance,
  payload->>'state' as state,
  created_at
FROM webhook_events
WHERE event_type = 'connection.update'
ORDER BY created_at DESC
LIMIT 20;
```

### Message Processing Latency
```sql
SELECT
  event_type,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processed_at - created_at))) as p50_seconds,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processed_at - created_at))) as p95_seconds,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processed_at - created_at))) as p99_seconds
FROM webhook_events
WHERE processed = true
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY event_type;
```

---

## 📞 Alerts Setup

### Alert Thresholds
```sql
-- Critical: Too many failed webhooks
SELECT COUNT(*)
FROM webhook_events
WHERE processed = false
  AND retry_count >= max_retries
  AND created_at > NOW() - INTERVAL '1 hour'
HAVING COUNT(*) > 50;

-- Warning: High retry rate
SELECT COUNT(*)
FROM webhook_events
WHERE retry_count > 0
  AND created_at > NOW() - INTERVAL '1 hour'
HAVING COUNT(*) > 100;

-- Critical: Retry worker not running
-- Check last processed webhook with retry
SELECT MAX(processed_at)
FROM webhook_events
WHERE retry_count > 0
  AND processed = true
HAVING MAX(processed_at) < NOW() - INTERVAL '10 minutes';
```

### Monitoring Script
```bash
#!/bin/bash
# monitor_webhooks.sh

# Check failed webhooks
FAILED=$(psql $DATABASE_URL -t -c "SELECT COUNT(*) FROM webhook_events WHERE processed = false AND retry_count >= max_retries AND created_at > NOW() - INTERVAL '1 hour';")

if [ "$FAILED" -gt 50 ]; then
  echo "CRITICAL: $FAILED failed webhooks in last hour"
  # Send alert
fi

# Check retry worker
if ! systemctl is-active --quiet webhook-retry; then
  echo "CRITICAL: Webhook retry worker is not running"
  # Send alert
fi
```

---

## 📚 Additional Resources

**Full Documentation:**
- Implementation Guide: `docs/EVOLUTION_API_WEBHOOK_FIXES.md`
- Deployment Summary: `docs/WEBHOOK_FIXES_SUMMARY.md`

**Code:**
- Webhook Processor: `app/services/webhook_processor.py`
- Retry Worker: `scripts/webhook_retry_worker.py`
- Tests: `tests/test_webhook_fixes.py`

**External:**
- Evolution API Docs: https://doc.evolution-api.com/v2/pt/webhooks
- Webhook Security: https://webhooks.fyi/security/hmac

---

## ✅ Post-Deployment Checklist

- [ ] `ENVIRONMENT=production` set
- [ ] `EVOLUTION_WEBHOOK_SECRET` configured
- [ ] Signature validation working (test with invalid signature)
- [ ] Webhooks persisting to database
- [ ] Connection webhooks updating Redis
- [ ] QR codes storing in Redis
- [ ] Retry worker running and enabled
- [ ] Monitoring and alerts configured
- [ ] Logs being collected
- [ ] Team trained on troubleshooting

---

**Last Updated:** October 11, 2025
**Version:** 1.0
**Status:** Production Ready ✅
