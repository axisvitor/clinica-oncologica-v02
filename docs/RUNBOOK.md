# Operational Runbook - Clínica Oncológica V02

**Version:** 2.0.0  
**Last Updated:** 2025-10-17  
**On-Call:** See escalation procedures below

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Incident Response](#incident-response)
3. [Common Issues](#common-issues)
4. [Database Operations](#database-operations)
5. [Monitoring & Alerts](#monitoring--alerts)
6. [Escalation Procedures](#escalation-procedures)

---

## Quick Reference

### Critical Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| Backend Health | `https://your-domain.com/health` | System health check |
| Frontend | `https://your-frontend.com` | User interface |
| Sentry | `https://sentry.io/organizations/YOUR_ORG` | Error tracking |
| Railway Dashboard | `https://railway.app/project/YOUR_PROJECT` | Deployment management |

### Emergency Contacts

| Role | Contact | Availability |
|------|---------|--------------|
| Tech Lead | [Name] - [Email/Phone] | 24/7 |
| DevOps | [Name] - [Email/Phone] | Business hours |
| Database Admin | [Name] - [Email/Phone] | On-call rotation |

### Key Metrics Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Error Rate | >1% | >5% | Investigate immediately |
| Response Time | >500ms | >2s | Check database/Redis |
| DB Pool Utilization | >70% | >90% | Scale pool or investigate leaks |
| CPU Usage | >70% | >90% | Scale horizontally |
| Memory Usage | >80% | >95% | Restart or scale |

---

## Incident Response

### Severity Levels

**P0 - Critical (Immediate Response)**
- Complete service outage
- Data loss or corruption
- Security breach
- Payment processing failure

**P1 - High (Response within 1 hour)**
- Partial service degradation
- Database connection issues
- Webhook failures affecting >50% of messages
- Authentication failures

**P2 - Medium (Response within 4 hours)**
- Performance degradation
- Non-critical feature failures
- Monitoring alerts

**P3 - Low (Response within 24 hours)**
- Minor bugs
- UI issues
- Documentation updates

### Incident Response Workflow

```
1. DETECT → Alert received (Sentry, monitoring, user report)
   ↓
2. ASSESS → Check /health endpoint, Sentry, logs
   ↓
3. TRIAGE → Determine severity (P0-P3)
   ↓
4. MITIGATE → Apply immediate fix or rollback
   ↓
5. RESOLVE → Deploy permanent fix
   ↓
6. DOCUMENT → Post-mortem (for P0/P1)
```

### Initial Assessment Checklist

```bash
# 1. Check system health
curl https://your-domain.com/health | jq

# 2. Check recent errors in Sentry
# Visit: https://sentry.io/organizations/YOUR_ORG/issues/

# 3. Check recent deployments
railway logs --tail 100

# 4. Check database connectivity
psql $DATABASE_URL -c "SELECT 1;"

# 5. Check Redis connectivity
redis-cli -u $REDIS_URL ping

# 6. Check Evolution API status
curl https://evolution-api.com/instance/status \
  -H "apikey: $EVOLUTION_API_KEY"
```

---

## Common Issues

### 1. Database Connection Pool Exhaustion

**Symptoms:**
- `QueuePool limit of size X overflow Y reached`
- Slow response times
- Timeouts on database queries

**Diagnosis:**
```bash
# Check pool status
curl https://your-domain.com/health | jq '.checks.database_pool'

# Expected output:
{
  "status": "critical",
  "pool_size": 10,
  "checked_out": 18,
  "overflow": 10,
  "utilization_percent": 90.0,
  "message": "Pool near exhaustion"
}
```

**Resolution:**
```bash
# Option 1: Increase pool size (temporary)
railway variables set DB_POOL_SIZE=20 DB_MAX_OVERFLOW=20
railway restart

# Option 2: Find connection leaks
# Check for long-running queries
psql $DATABASE_URL -c "
  SELECT pid, now() - query_start as duration, state, query
  FROM pg_stat_activity
  WHERE state != 'idle'
  ORDER BY duration DESC
  LIMIT 10;
"

# Kill long-running queries (if safe)
psql $DATABASE_URL -c "SELECT pg_terminate_backend(PID);"

# Option 3: Restart application
railway restart
```

**Prevention:**
- Monitor pool utilization in Grafana
- Set alerts for >70% utilization
- Review code for missing `db.close()` or context manager usage

---

### 2. Webhook Signature Validation Failures

**Symptoms:**
- `401 Unauthorized` errors on webhook endpoints
- Messages not being processed
- Sentry errors: "Invalid webhook signature"

**Diagnosis:**
```bash
# Check recent webhook errors
railway logs | grep "webhook" | grep "401"

# Verify webhook secret is set
railway variables get EVOLUTION_WEBHOOK_SECRET

# Test webhook signature generation
python scripts/test_webhook_signature.py
```

**Resolution:**
```bash
# Option 1: Verify secret matches Evolution API
# Get secret from Evolution API settings
# Compare with environment variable

# Option 2: Regenerate and update secret
NEW_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
railway variables set EVOLUTION_WEBHOOK_SECRET=$NEW_SECRET

# Update Evolution API webhook configuration
curl -X POST https://evolution-api.com/webhook/set \
  -H "apikey: $EVOLUTION_API_KEY" \
  -d "{\"url\": \"https://your-domain.com/api/v1/webhooks/evolution/message\", \"secret\": \"$NEW_SECRET\"}"

# Option 3: Check timestamp validation
# Ensure server time is synchronized (NTP)
date -u
```

**Prevention:**
- Document webhook secret in secure vault (1Password, AWS Secrets Manager)
- Set up monitoring for webhook failure rate
- Implement webhook retry mechanism

---

### 3. Saga Pattern Failures (Patient Onboarding)

**Symptoms:**
- Patient onboarding incomplete
- Compensation actions triggered
- Sentry errors: "Saga step failed"

**Diagnosis:**
```bash
# Check saga state in database
psql $DATABASE_URL -c "
  SELECT id, patient_id, current_step, status, error_message, created_at
  FROM saga_state
  WHERE status IN ('failed', 'compensating')
  ORDER BY created_at DESC
  LIMIT 10;
"

# Check saga logs
railway logs | grep "saga" | tail -50
```

**Resolution:**
```bash
# Option 1: Retry failed saga
python scripts/retry_saga.py --saga-id <SAGA_ID>

# Option 2: Manual compensation
# 1. Identify failed step
# 2. Manually reverse changes
# 3. Mark saga as compensated

psql $DATABASE_URL -c "
  UPDATE saga_state
  SET status = 'compensated', updated_at = NOW()
  WHERE id = '<SAGA_ID>';
"

# Option 3: Complete saga manually
# If safe to proceed, mark as completed
psql $DATABASE_URL -c "
  UPDATE saga_state
  SET status = 'completed', current_step = 'completed', updated_at = NOW()
  WHERE id = '<SAGA_ID>';
"
```

**Prevention:**
- Monitor saga success rate (should be >99%)
- Set alerts for saga failures >1%
- Implement saga dashboard for visibility

---

### 4. Rate Limiting False Positives

**Symptoms:**
- Legitimate users blocked
- `429 Too Many Requests` errors
- User complaints about access issues

**Diagnosis:**
```bash
# Check rate limit hits in Redis
redis-cli -u $REDIS_URL --scan --pattern "rate_limit:*" | head -20

# Check rate limit logs
railway logs | grep "rate_limit" | tail -50

# Identify blocked IPs
railway logs | grep "429" | awk '{print $1}' | sort | uniq -c | sort -rn
```

**Resolution:**
```bash
# Option 1: Whitelist specific IP
# Add to rate limiter whitelist in code
# Deploy update

# Option 2: Clear rate limit for specific key
redis-cli -u $REDIS_URL DEL "rate_limit:IP_ADDRESS"

# Option 3: Temporarily increase limits
railway variables set RATE_LIMIT_PER_MINUTE=100
railway restart

# Option 4: Disable rate limiting (emergency only)
railway variables set ENABLE_RATE_LIMITING=false
railway restart
```

**Prevention:**
- Implement tiered rate limits (authenticated vs. anonymous)
- Add rate limit headers to responses
- Monitor rate limit hit rate

---

### 5. Evolution API Connection Issues

**Symptoms:**
- Messages not being sent
- Webhook timeouts
- Sentry errors: "Evolution API unreachable"

**Diagnosis:**
```bash
# Check Evolution API status
curl https://evolution-api.com/instance/status \
  -H "apikey: $EVOLUTION_API_KEY"

# Check recent Evolution API errors
railway logs | grep "evolution" | grep -i "error" | tail -50

# Test webhook connectivity
curl -X POST https://your-domain.com/api/v1/webhooks/evolution/message \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: test" \
  -H "X-Webhook-Timestamp: $(date +%s)" \
  -d '{"event": "test"}'
```

**Resolution:**
```bash
# Option 1: Restart Evolution API instance
# Via Evolution API dashboard

# Option 2: Reconnect WhatsApp session
curl -X POST https://evolution-api.com/instance/connect \
  -H "apikey: $EVOLUTION_API_KEY"

# Option 3: Disable Evolution integration temporarily
railway variables set ENABLE_EVOLUTION=false
railway restart

# Option 4: Switch to backup Evolution instance
railway variables set EVOLUTION_API_URL=https://backup-evolution-api.com
railway restart
```

**Prevention:**
- Set up Evolution API health monitoring
- Implement automatic reconnection logic
- Configure backup Evolution API instance

---

## Database Operations

### Backup and Restore

```bash
# Create backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
psql $DATABASE_URL < backup_20251017_120000.sql

# AWS RDS automated backups
aws rds create-db-snapshot \
  --db-instance-identifier clinica-oncologica-prod \
  --db-snapshot-identifier manual-backup-$(date +%Y%m%d)
```

### Migration Management

```bash
# Check current migration
alembic current

# Run pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Create new migration
alembic revision --autogenerate -m "Description"
```

### Performance Tuning

```bash
# Find slow queries
psql $DATABASE_URL -c "
  SELECT query, mean_exec_time, calls
  FROM pg_stat_statements
  ORDER BY mean_exec_time DESC
  LIMIT 10;
"

# Analyze table statistics
psql $DATABASE_URL -c "ANALYZE VERBOSE;"

# Vacuum database
psql $DATABASE_URL -c "VACUUM ANALYZE;"
```

---

## Monitoring & Alerts

### Sentry Alerts

**Critical Errors (Immediate notification):**
- Database connection failures
- Authentication failures
- Payment processing errors
- Data corruption

**Warning Errors (Hourly digest):**
- API timeouts
- Webhook failures
- Rate limit hits

### Prometheus Metrics

```bash
# Access metrics
curl https://your-domain.com/metrics

# Key metrics to monitor:
# - http_requests_total{status="500"}
# - http_request_duration_seconds{quantile="0.95"}
# - db_pool_checked_out / db_pool_size
# - redis_operations_total{status="error"}
```

### Log Aggregation

```bash
# Search logs for errors
railway logs | grep -i "error" | tail -100

# Search logs for specific user
railway logs | grep "user_id:12345" | tail -50

# Search logs for specific time range
railway logs --since 2h | grep "error"
```

---

## Escalation Procedures

### P0 - Critical Incidents

1. **Immediate Actions:**
   - Page on-call engineer
   - Create incident channel (#incident-YYYYMMDD)
   - Notify stakeholders

2. **Response Team:**
   - Incident Commander (Tech Lead)
   - Engineer (On-call)
   - Database Admin (if DB-related)

3. **Communication:**
   - Update status page every 15 minutes
   - Post updates in incident channel
   - Notify users via email/WhatsApp

4. **Post-Incident:**
   - Write post-mortem within 48 hours
   - Identify root cause
   - Create action items to prevent recurrence

### P1 - High Priority

1. **Response Time:** Within 1 hour
2. **Notification:** Slack alert to #engineering
3. **Post-Incident:** Brief summary in #engineering

### P2/P3 - Medium/Low Priority

1. **Response Time:** Within 4-24 hours
2. **Notification:** Create ticket in issue tracker
3. **Post-Incident:** Update ticket with resolution

---

## Additional Resources

- **Deployment Guide:** `docs/DEPLOYMENT.md`
- **Architecture:** `docs/ARCHITECTURE.md`
- **API Documentation:** `docs/API.md`
- **Contributing:** `docs/CONTRIBUTING.md`

For questions, contact the engineering team in #engineering Slack channel.

