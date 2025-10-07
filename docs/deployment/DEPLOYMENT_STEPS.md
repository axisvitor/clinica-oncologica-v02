# Deployment Steps - Railway Production

**Date**: 2025-10-07
**Branch**: docs-refactor-py313
**Database Migration**: Required (SENDING status)

---

## 🚀 Pre-Deployment Checklist

### 1. Verify All Fixes Are Committed
```bash
git status
git log --oneline -12
```

**Expected commits**:
- ✅ `9779a54` - Final session summary
- ✅ `1e7fab8` - P1-2 and P1-3 fixes
- ✅ `2d5cc38` - P0 completion summary
- ✅ `49ef5d0` - P0-2 and P0-4 fixes
- ✅ `c94636c` - P0-1 and P0-3 fixes
- ✅ `a6653a4` - Smoke test suite
- ✅ `7e2c730` - Pydantic V2 fixes
- ✅ `903b0a4` - Railway deployment docs
- ✅ `378375b` - Dependencies cleanup
- ✅ `fa1c7ed` - P0 startup fixes
- ✅ `b06503b` - Circular import fix

### 2. Verify Tests Pass Locally (optional)
```bash
cd backend-hormonia

# P0 fixes tests (if env configured)
pytest tests/test_message_scheduler_signature_fix.py -v
pytest tests/test_phone_number_normalization.py -v
pytest tests/test_p0_2_ghost_message_fix.py -v
pytest tests/test_message_duplication_fix.py -v

# P1 fixes tests
pytest tests/unit/utils/test_db_circuit_breaker.py -v
pytest tests/test_message_sender_queue_mode.py -v
```

**Note**: Local tests may fail due to production config validation. This is expected.

---

## 📊 Database Migration (REQUIRED)

### Migration Details
**File**: `backend-hormonia/alembic/versions/20251007_add_message_sending_status.py`
**Purpose**: Add SENDING status to MessageStatus enum
**Required for**: P0-4 fix (message duplication)

### Migration Steps

#### Option 1: Railway CLI (Recommended)
```bash
# Connect to Railway project
railway link

# Run migration on production database
railway run alembic upgrade head

# Verify migration applied
railway run alembic current
```

#### Option 2: Direct PostgreSQL Connection
```bash
# Get Railway database URL
railway variables

# Set DATABASE_URL locally
export DATABASE_URL="postgresql://..."

# Run migration
cd backend-hormonia
alembic upgrade head

# Verify
alembic current
```

#### Option 3: Manual SQL (Last Resort)
```sql
-- Connect to Railway PostgreSQL
-- Run this SQL:

ALTER TYPE messagestatus ADD VALUE IF NOT EXISTS 'sending' AFTER 'scheduled';

-- Verify
SELECT enum_range(NULL::messagestatus);
```

### Verify Migration Success
```sql
-- Should include 'sending' in the list
SELECT unnest(enum_range(NULL::messagestatus)) as status;

-- Expected output:
-- pending
-- scheduled
-- sending  ← NEW
-- sent
-- delivered
-- read
-- failed
-- cancelled
```

---

## 🚢 Railway Deployment

### Auto-Deploy (if configured)
Railway should auto-deploy when you push to the connected branch:

```bash
git push origin docs-refactor-py313
```

Watch Railway dashboard for:
- ✅ Build started
- ✅ Build successful
- ✅ Deploy started
- ✅ Deploy successful
- ✅ Health checks passing

### Manual Deploy (if needed)
```bash
railway up
```

### Deployment Verification Commands
```bash
# Check deployment status
railway status

# View recent logs
railway logs

# Check specific service logs
railway logs --service backend

# Follow logs in real-time
railway logs --follow
```

---

## ✅ Post-Deployment Validation

### 1. Health Check (Immediate)
```bash
# Get Railway URL
RAILWAY_URL=$(railway variables | grep RAILWAY_PUBLIC_URL | cut -d'=' -f2)

# Test health endpoint
curl $RAILWAY_URL/health

# Expected response:
# {
#   "status": "healthy",
#   "database": {"status": "healthy", "pool_size": 40},
#   "redis": {"status": "healthy"}
# }
```

### 2. Smoke Tests (5 minutes)
```bash
cd backend-hormonia

# Update smoke_test.py with Railway URL
# Edit line 13: BASE_URL = "https://YOUR-RAILWAY-URL"

# Run smoke tests
python tests/smoke_test.py

# Expected: 6/6 tests passing
```

### 3. Database Verification (5 minutes)
```sql
-- Connect to Railway PostgreSQL

-- 1. Verify SENDING status exists
SELECT unnest(enum_range(NULL::messagestatus)) as status;

-- 2. Check for duplicate messages (should be 0)
SELECT patient_id, content, COUNT(*) as duplicates
FROM messages
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY patient_id, content
HAVING COUNT(*) > 1;

-- 3. Check orphaned scheduled messages (should be 0)
SELECT COUNT(*)
FROM messages
WHERE status = 'scheduled'
  AND scheduled_for < NOW() - INTERVAL '1 hour';

-- 4. Check phone matching success rate
SELECT
  COUNT(*) FILTER (WHERE patient_id IS NOT NULL) as matched,
  COUNT(*) FILTER (WHERE patient_id IS NULL) as unmatched,
  ROUND(100.0 * COUNT(*) FILTER (WHERE patient_id IS NOT NULL) / COUNT(*), 2) as success_rate
FROM webhook_events
WHERE created_at > NOW() - INTERVAL '1 day';
```

### 4. Message Delivery Verification (30 minutes)
```bash
# Monitor Railway logs for message processing
railway logs --follow | grep -E "message|flow|scheduled|sent"

# Look for:
# ✅ "Successfully scheduled message {id}"
# ✅ "Flow message sent successfully"
# ✅ "Patient found with E.164 format"
# ❌ NO "FINAL FAILURE" logs
# ❌ NO "Ghost message" warnings
# ❌ NO "TypeError" in scheduling
```

### 5. Circuit Breaker Verification (optional)
```bash
# Simulate DB error (use staging, not production!)
railway logs --follow | grep -i "circuit"

# Look for:
# ✅ "Circuit breaker opened after 5 failures"
# ✅ "Circuit breaker transitioning to HALF_OPEN"
# ✅ "Circuit breaker closed after successful operation"
```

---

## 📊 Monitoring (24 Hours)

### Metrics to Track

#### Message Delivery
- Flow message delivery rate: Target 100%
- WhatsApp patient matching rate: Target 100%
- Duplicate message count: Target 0
- Orphaned scheduled messages: Target 0

#### Performance
- Message scheduling latency: < 100ms
- Phone lookup attempts: 1-3 avg (was 5-6)
- Database pool utilization: < 80%
- Circuit breaker opening rate: < 1% of requests

#### Errors
- TypeError in scheduling: Target 0
- "FINAL FAILURE" logs: Target 0
- Ghost message warnings: Target 0
- Circular import errors: Target 0

### Monitoring Commands
```bash
# Railway metrics
railway metrics

# Logs analysis
railway logs --since 1h | grep -c "error"
railway logs --since 1h | grep -c "TypeError"
railway logs --since 1h | grep -c "FINAL FAILURE"

# Database query
SELECT
  DATE_TRUNC('hour', created_at) as hour,
  status,
  COUNT(*) as count
FROM messages
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY hour, status
ORDER BY hour DESC;
```

---

## 🔄 Rollback Plan (If Needed)

### Quick Rollback (Revert Commits)
```bash
# Revert P1 fixes (if causing issues)
git revert 1e7fab8
git push origin docs-refactor-py313

# Revert P0 fixes (if critical)
git revert 49ef5d0
git revert c94636c
git push origin docs-refactor-py313

# Railway will auto-deploy the rollback
```

### Database Rollback (Complex - Avoid if Possible)
**Note**: PostgreSQL doesn't support removing enum values easily.

If SENDING status causes issues:
1. Update all SENDING messages to PENDING:
```sql
UPDATE messages SET status = 'pending' WHERE status = 'sending';
```

2. The enum value can stay (harmless), or complex migration needed.

---

## 🎯 Success Criteria

Deployment is successful when:

✅ **Database Migration**
- SENDING status added to enum
- No migration errors in logs

✅ **Message Delivery**
- Flow messages delivering at 100% rate
- No "TypeError" in message_scheduler
- No "FINAL FAILURE" logs

✅ **Patient Matching**
- WhatsApp matching at 100% rate
- "Patient found with E.164 format" in logs
- No unmatched conversations

✅ **Message Duplication**
- Duplicate query returns 0 rows
- One message per conversation in UI
- Status updates sync correctly

✅ **System Health**
- Health endpoint returns 200
- Database pool healthy
- Redis connected
- No errors in logs for 1 hour

✅ **Performance**
- Circuit breaker protecting DB
- Retry policies triggering on failures
- Message queue processing smoothly

---

## 📞 Troubleshooting

### Issue: Migration Fails
**Symptom**: `enum value already exists` error

**Solution**:
```sql
-- Check if SENDING already exists
SELECT unnest(enum_range(NULL::messagestatus));

-- If exists, migration is already applied
-- No action needed
```

### Issue: Health Check Returns 503
**Symptom**: `/health` returns unhealthy

**Solution**:
```bash
# Check Railway logs
railway logs --tail 100

# Common fixes:
# - Database connection timeout: Increase pool size
# - Redis connection failed: Check Redis service status
# - Circular import: Already fixed in commits
```

### Issue: Messages Still Duplicating
**Symptom**: Duplicate messages in database

**Solution**:
```bash
# Verify P0-2 and P0-4 fixes deployed
git log --oneline | grep -E "49ef5d0|ghost|duplication"

# Check Celery is using new code
railway logs --follow | grep "Celery.*message_id"

# Should see: "message_id={uuid}" in logs
```

### Issue: Phone Matching Still Failing
**Symptom**: Patient lookup fails

**Solution**:
```bash
# Verify P0-3 fix deployed
git log --oneline | grep -E "c94636c|phone"

# Check logs for normalization
railway logs --follow | grep "E.164"

# Should see: "E.164 format '+55...'"
```

---

## 📋 Deployment Checklist

- [ ] All commits verified (12 commits)
- [ ] Database migration planned
- [ ] Railway project linked
- [ ] Backup database (optional but recommended)
- [ ] Run migration: `railway run alembic upgrade head`
- [ ] Verify migration: Check SENDING status exists
- [ ] Deploy code: `git push origin docs-refactor-py313`
- [ ] Wait for Railway build/deploy
- [ ] Run health check: `/health` returns 200
- [ ] Run smoke tests: 6/6 passing
- [ ] Verify database: No duplicates, no orphans
- [ ] Monitor logs: No errors for 1 hour
- [ ] Check metrics: Delivery 100%, matching 100%
- [ ] Document any issues
- [ ] Mark deployment successful

---

## 🎉 Deployment Complete

Once all checks pass:

1. Update deployment status in Railway dashboard
2. Notify team of successful deployment
3. Continue monitoring for 24 hours
4. Plan next session for P1-1 and P1-4

**Deployment Status**: ✅ **READY TO DEPLOY**
**Estimated Downtime**: None (zero-downtime deployment)
**Rollback Time**: < 5 minutes

---

**Last Updated**: 2025-10-07
**Next Review**: After 24h monitoring period
