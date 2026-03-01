# Deployment Procedure - P0 Implementations

**Version:** 1.0
**Last Updated:** 2025-11-15
**Deployment Type:** Zero-Downtime Production Deployment

---

## Overview

This document provides step-by-step instructions for deploying P0 implementations to staging and production environments.

**What's Being Deployed:**
- Migration 010: 28 database performance indexes
- Migration 011: HIPAA audit trail enhancement
- Migration 012: Quiz response JSONB migration
- Security fixes: CSRF, SQL injection, rate limiting
- Service refactoring: Patient service modularization

**Expected Duration:**
- Staging: 10-15 minutes
- Production: 15-20 minutes

**Downtime:**
- Expected: **0 minutes** (non-blocking migrations)
- Actual: To be recorded post-deployment

---

## Prerequisites

**Before Starting:**
- [ ] `PRE_DEPLOYMENT_CHECKLIST.md` 100% complete
- [ ] All stakeholders notified
- [ ] On-call team briefed and ready
- [ ] Monitoring dashboards open
- [ ] Database backup completed
- [ ] Rollback procedure reviewed

**Required Access:**
- [ ] Railway production project access
- [ ] Database admin credentials
- [ ] Monitoring dashboard access (Grafana)
- [ ] PagerDuty/Slack access
- [ ] Git repository push access

---

## Deployment Timeline

### Recommended Deployment Window

**Staging:**
- **When:** During business hours
- **Best Time:** Tuesday-Thursday, 10 AM - 4 PM
- **Reason:** Team available for immediate support

**Production:**
- **When:** During low-traffic period
- **Best Time:** Saturday 2 AM - 4 AM (lowest traffic)
- **Reason:** Minimize user impact if issues occur

**Deployment Schedule:**
```
Staging:  Tuesday, 2 PM EST
          ↓ Monitor for 24 hours
Production: Saturday, 2 AM EST
```

---

## Part 1: Pre-Deployment (T-30 minutes)

### Step 1.1: Environment Preparation (5 minutes)

**Set Environment Variables:**
```bash
# Navigate to project directory
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia

# Set target environment
export TARGET_ENV=staging  # or production
export DEPLOYMENT_ID="p0-deploy-$(date +%Y%m%d-%H%M%S)"

# Verify working directory
pwd
git branch --show-current
# Expected: feature/ia-optimization-review or main

# Verify clean state
git status
# Expected: nothing to commit, working tree clean
```

**Validation:**
- [ ] Project directory verified
- [ ] Git branch confirmed
- [ ] No uncommitted changes
- [ ] Environment variable set

### Step 1.2: Database Backup (10 minutes)

**Create Production Backup:**
```bash
# Get database URL from Railway
railway login
railway link

# For staging
railway environment staging
export DB_URL=$(railway variables get DATABASE_URL)

# For production
railway environment production
export DB_URL=$(railway variables get DATABASE_URL)

# Create backup
BACKUP_FILE="backups/p0_backup_${TARGET_ENV}_$(date +%Y%m%d_%H%M%S).sql"
mkdir -p backups

echo "Creating database backup..."
pg_dump "$DB_URL" > "$BACKUP_FILE"

# Verify backup
ls -lh "$BACKUP_FILE"
# Expected: File size >10MB (adjust based on your database)

# Compress backup
gzip "$BACKUP_FILE"
echo "✅ Backup created: ${BACKUP_FILE}.gz"

# Optional: Upload to S3/Cloud Storage for redundancy
# aws s3 cp "${BACKUP_FILE}.gz" s3://your-bucket/backups/
```

**Validation:**
- [ ] Backup file created successfully
- [ ] Backup file size reasonable (>10MB)
- [ ] Backup compressed
- [ ] Backup location recorded
- [ ] Backup uploaded to cloud (if configured)

**Backup Location:**
```
Local:  /mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/backups/
Cloud:  [S3 URL or equivalent]
```

### Step 1.3: Pre-Deployment Health Check (5 minutes)

**Check Current System Health:**
```bash
# Health endpoint check
curl https://your-app-${TARGET_ENV}.railway.app/health | jq

# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "redis": "connected",
#   "version": "1.x.x"
# }

# Check database connectivity
railway run --environment ${TARGET_ENV} -- \
  python -c "
from app.db import SessionLocal
db = SessionLocal()
result = db.execute('SELECT version()').fetchone()
print(f'✅ Database connected: {result[0][:50]}...')
db.close()
"

# Check current migration version
railway run --environment ${TARGET_ENV} -- \
  alembic current

# Expected: Current migration before 010
```

**Validation:**
- [ ] Health endpoint returns 200 OK
- [ ] Database connected successfully
- [ ] Redis connected successfully
- [ ] Current migration version documented: __________

### Step 1.4: Notify Stakeholders (5 minutes)

**Send Deployment Start Notification:**
```bash
# Slack notification (if webhook configured)
curl -X POST $SLACK_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "🚀 P0 Deployment Starting",
    "blocks": [
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": "*P0 Deployment Starting*\n• Environment: '"${TARGET_ENV}"'\n• Deployment ID: '"${DEPLOYMENT_ID}"'\n• Expected Duration: 15-20 minutes\n• Downtime: 0 minutes (non-blocking)"
        }
      }
    ]
  }'
```

**Manual Notification:**
```
#p0-deployment channel:
🚀 P0 Deployment Starting
• Environment: [staging/production]
• Deployment ID: p0-deploy-20251115-140000
• Expected Duration: 15-20 minutes
• Downtime: 0 minutes
• Monitoring: [Dashboard URL]
• On-call: @engineer-name
```

**Validation:**
- [ ] Slack notification sent
- [ ] Team acknowledged in #p0-deployment
- [ ] Monitoring dashboards open
- [ ] On-call engineer standing by

### Step 1.5: Enable Read-Only Mode (OPTIONAL)

**Only if you want extra safety during migration:**
```bash
# This is OPTIONAL - migrations are non-blocking
# Only use if you want to prevent writes during migration

railway variables set MAINTENANCE_MODE=true --environment ${TARGET_ENV}

# Trigger application restart
railway up --detach --environment ${TARGET_ENV}

# Wait for restart (30 seconds)
sleep 30

# Verify maintenance mode
curl https://your-app-${TARGET_ENV}.railway.app/health
# Should return 503 Service Unavailable if maintenance mode enabled
```

**Note:** For P0 deployment, this is **NOT REQUIRED** because:
- All index creations use `CONCURRENTLY` (non-blocking)
- Application can run during migration
- Zero downtime guaranteed

---

## Part 2: Staging Deployment (T+0 to T+15)

### Step 2.1: Deploy Code to Staging (5 minutes)

**Push to Staging Branch:**
```bash
# Ensure on correct branch
git checkout main
git pull origin main

# Verify latest commit
git log --oneline -5

# Railway auto-deploys from main branch
# Trigger deployment by pushing to repository
git push origin main

# Monitor deployment in Railway dashboard
railway logs --environment staging --follow

# Wait for deployment to complete
# Expected: "Build successful" in logs
```

**Validation:**
- [ ] Code pushed to main branch
- [ ] Railway deployment triggered
- [ ] Build completed successfully
- [ ] Application started successfully
- [ ] Health check passing

### Step 2.2: Apply Database Migrations (5 minutes)

**Run Migrations on Staging:**
```bash
# Connect to staging environment
railway environment staging

# Check current migration
railway run -- alembic current
# Document current version: __________

# Apply P0 migrations
echo "Applying migrations 010, 011, 012..."
railway run -- alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Running upgrade 009 -> 010
# INFO  [alembic.runtime.migration] Running upgrade 010 -> 011
# INFO  [alembic.runtime.migration] Running upgrade 011 -> 012

# Verify migrations applied
railway run -- alembic current -v
# Expected: 012 (head)
```

**Monitor During Migration:**
```bash
# In separate terminal, monitor database performance
railway run -- psql $DATABASE_URL -c "
SELECT
    pid,
    state,
    query_start,
    left(query, 60) as query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;
"

# Expected: See CONCURRENTLY index creations
# These do NOT block other operations
```

**Validation:**
- [ ] Migration 010 applied successfully (28 indexes)
- [ ] Migration 011 applied successfully (HIPAA audit)
- [ ] Migration 012 applied successfully (JSONB)
- [ ] No errors in migration logs
- [ ] Application still responsive during migration

### Step 2.3: Verify Indexes Created (3 minutes)

**Run Index Verification Script:**
```bash
# Upload verification script to Railway
railway run --environment staging -- bash -c "
cat > /tmp/verify_indexes.sql << 'EOF'
$(cat scripts/verify_p0_indexes.sql)
EOF

psql \$DATABASE_URL -f /tmp/verify_indexes.sql
"

# Expected output:
# ✅ All 28 P0 indexes present
# ✅ Index sizes reasonable
# ✅ No missing indexes
```

**Manual Verification:**
```bash
railway run --environment staging -- psql $DATABASE_URL -c "
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes
WHERE indexname LIKE 'idx_p0_%'
ORDER BY tablename, indexname;
"

# Expected: 28 rows (all P0 indexes)
```

**Validation:**
- [ ] All 28 indexes present
- [ ] Index names match migration
- [ ] Index sizes reasonable (<100MB each)
- [ ] No errors in index creation

### Step 2.4: Smoke Tests on Staging (5 minutes)

**Run Critical Path Tests:**
```bash
# Test authentication
echo "Testing authentication..."
curl -X POST https://your-app-staging.railway.app/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123"
  }' | jq

# Expected: 200 OK with access token

# Test patient listing (should be FAST with new indexes)
ACCESS_TOKEN="<token from above>"
time curl -X GET https://your-app-staging.railway.app/api/v2/patients \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq

# Expected: Response time <200ms

# Test quiz session creation
curl -X POST https://your-app-staging.railway.app/api/v2/quiz/sessions \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "quiz_template_id": 1
  }' | jq

# Expected: 200 OK with session created

# Test HIPAA audit trail (new feature)
railway run --environment staging -- psql $DATABASE_URL -c "
SELECT COUNT(*) as audit_events
FROM hipaa_audit_trail
WHERE created_at > NOW() - INTERVAL '5 minutes';
"

# Expected: Audit events being logged
```

**Validation:**
- [ ] Authentication working
- [ ] Patient listing <200ms
- [ ] Quiz session creation working
- [ ] HIPAA audit logging working
- [ ] No errors in application logs

### Step 2.5: Performance Validation (5 minutes)

**Run Performance Tests:**
```bash
# Test query performance with new indexes
railway run --environment staging -- bash -c "
cat > /tmp/test_performance.sql << 'EOF'
$(cat scripts/test_query_performance.sql)
EOF

psql \$DATABASE_URL -f /tmp/test_performance.sql
"

# Expected results:
# Doctor Dashboard Query: <10ms ✅
# Patient Messages Query: <5ms ✅
# Quiz Analytics Query: <8ms ✅
# Alert Dashboard Query: <10ms ✅
```

**Monitor Database Performance:**
```bash
railway run --environment staging -- psql $DATABASE_URL -c "
SELECT
    query,
    calls,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
WHERE query LIKE '%patients%' OR query LIKE '%messages%'
ORDER BY mean_exec_time DESC
LIMIT 10;
"

# Expected: Mean execution times <10ms for indexed queries
```

**Validation:**
- [ ] All critical queries <10ms
- [ ] No slow queries (>100ms) detected
- [ ] Database CPU normal (<50%)
- [ ] No connection pool exhaustion

---

## Part 3: Staging Validation (T+15 to T+45)

### Step 3.1: Automated Test Suite (15 minutes)

**Run Full Test Suite Against Staging:**
```bash
# Set staging environment variables
export TEST_API_URL=https://your-app-staging.railway.app
export TEST_DATABASE_URL=$(railway variables get DATABASE_URL --environment staging)

# Run critical path tests
pytest tests/api/critical/ -v --tb=short

# Run integration tests
pytest tests/integration/ -v --tb=short

# Run security tests
pytest tests/security/ -v

# Expected: All tests passing ✅
```

**Validation:**
- [ ] Critical tests: 100% passing
- [ ] Integration tests: 100% passing
- [ ] Security tests: 100% passing
- [ ] No test failures
- [ ] No flaky tests

### Step 3.2: Manual QA Testing (15 minutes)

**Test Critical User Flows:**

**Flow 1: Doctor Dashboard**
- [ ] Login as doctor
- [ ] View patient list (should load <1 second)
- [ ] Click on patient (should load <1 second)
- [ ] View patient history (should be fast)
- [ ] Create new patient (should work)

**Flow 2: Patient Onboarding**
- [ ] Create new patient via API
- [ ] Verify welcome message sent
- [ ] Verify flow initialized
- [ ] Check HIPAA audit log captured event

**Flow 3: Quiz System**
- [ ] Start quiz session
- [ ] Submit quiz responses
- [ ] Complete quiz
- [ ] View quiz analytics (should be fast)

**Flow 4: Alert System**
- [ ] Trigger test alert
- [ ] View alert dashboard (should load <1 second)
- [ ] Acknowledge alert
- [ ] Verify audit log captured action

**Validation:**
- [ ] All critical flows working
- [ ] UI responsive (<1 second loads)
- [ ] No errors in browser console
- [ ] No errors in application logs

### Step 3.3: Security Validation (10 minutes)

**Test Security Fixes:**

**CSRF Protection (CVE-2025-CLINIC-001):**
```bash
# Test CSRF protection enabled
curl -X POST https://your-app-staging.railway.app/api/v2/patients \
  -H "Content-Type: application/json" \
  -d '{"name":"Test"}' \
  -v

# Expected: 403 Forbidden (missing CSRF token)

# Test with valid CSRF token
CSRF_TOKEN=$(curl -s https://your-app-staging.railway.app/api/v2/auth/csrf-token | jq -r .csrf_token)
curl -X POST https://your-app-staging.railway.app/api/v2/patients \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -d '{"name":"Test"}' \
  -v

# Expected: Request processed (needs auth token, but CSRF validated)
```

**SQL Injection Prevention (CVE-2025-CLINIC-004):**
```bash
# Test SQL injection attempt blocked
curl -X GET "https://your-app-staging.railway.app/api/v2/patients?search='; DROP TABLE patients;--" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -v

# Expected: 200 OK with empty results (injection blocked)
# Verify patients table still exists:
railway run --environment staging -- psql $DATABASE_URL -c "\dt patients"
# Expected: Table exists ✅
```

**Rate Limiting:**
```bash
# Test rate limiting on webhook endpoint
for i in {1..100}; do
  curl -X POST https://your-app-staging.railway.app/api/v2/webhooks/whatsapp \
    -H "Content-Type: application/json" \
    -d '{"test": true}' \
    -w "%{http_code}\n" \
    -s -o /dev/null
done | grep 429 | wc -l

# Expected: Some 429 responses (rate limit triggered)
```

**Validation:**
- [ ] CSRF protection working
- [ ] SQL injection attempts blocked
- [ ] Rate limiting active
- [ ] No security test failures

### Step 3.4: HIPAA Audit Validation (5 minutes)

**Verify Audit Trail Working:**
```bash
railway run --environment staging -- psql $DATABASE_URL -c "
SELECT
    event_type,
    user_id,
    patient_id,
    action,
    created_at
FROM hipaa_audit_trail
ORDER BY created_at DESC
LIMIT 20;
"

# Expected: Recent audit events logged
```

**Test Audit Capture:**
```bash
# Perform PHI access action
curl -X GET https://your-app-staging.railway.app/api/v2/patients/1 \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# Verify audit event captured
railway run --environment staging -- psql $DATABASE_URL -c "
SELECT * FROM hipaa_audit_trail
WHERE action = 'PHI_ACCESS'
AND created_at > NOW() - INTERVAL '1 minute';
"

# Expected: Audit event present
```

**Validation:**
- [ ] Audit events being logged
- [ ] PHI access captured
- [ ] User actions tracked
- [ ] Timestamps accurate

---

## Part 4: Production Deployment (T+24 hours)

**IMPORTANT:** Only proceed to production if staging has been stable for 24+ hours with no issues.

### Step 4.1: Production Pre-Flight (10 minutes)

**Final Checks Before Production:**
```bash
# Verify staging stable for 24 hours
railway logs --environment staging --since 24h | grep -i error | wc -l
# Expected: <10 errors in 24 hours

# Check staging metrics
# - Error rate: <1%
# - P95 latency: <200ms
# - Database CPU: <50%
# - No alerts triggered

# Verify production backup recent
ls -lt backups/p0_backup_production_*.sql.gz | head -1
# Expected: Backup from Step 1.2 (within last hour)
```

**Validation:**
- [ ] Staging stable for 24+ hours
- [ ] No critical errors in staging
- [ ] Performance metrics good
- [ ] Production backup verified
- [ ] Team ready for production deployment

### Step 4.2: Production Deployment Announcement (5 minutes)

**Send Production Deployment Notification:**
```
#p0-deployment channel:
🚀 PRODUCTION DEPLOYMENT STARTING
• Deployment ID: p0-deploy-20251115-140000
• Expected Duration: 15-20 minutes
• Downtime: 0 minutes
• Changes: Database performance (28 indexes), HIPAA audit, Security fixes
• Rollback: Available within 10 minutes if needed
• Monitoring: [Dashboard URL]
• On-call: @engineer-name

Please report any issues immediately in this channel.
```

**Validation:**
- [ ] Notification sent
- [ ] Team acknowledged
- [ ] Monitoring dashboards open
- [ ] On-call ready

### Step 4.3: Deploy to Production (15 minutes)

**Same process as staging, but with production environment:**

**Switch to Production Environment:**
```bash
export TARGET_ENV=production
railway environment production

# Verify production environment
railway status
# Expected: Connected to production project
```

**Apply Migrations:**
```bash
# Check current migration
railway run -- alembic current
# Document: __________

# Apply P0 migrations
echo "⚠️  DEPLOYING TO PRODUCTION - Applying migrations..."
railway run -- alembic upgrade head

# Monitor migration progress
railway logs --follow

# Expected: Migrations complete in 3-5 minutes
```

**Verify Deployment:**
```bash
# Check migration version
railway run -- alembic current -v
# Expected: 012 (head)

# Verify indexes created
railway run -- psql $DATABASE_URL -c "
SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE 'idx_p0_%';
"
# Expected: 28

# Health check
curl https://your-app-production.railway.app/health | jq
# Expected: 200 OK, healthy
```

**Validation:**
- [ ] Migrations applied successfully
- [ ] 28 indexes created
- [ ] Health check passing
- [ ] No errors in logs

---

## Part 5: Production Validation (T+0 to T+30)

### Step 5.1: Immediate Smoke Tests (5 minutes)

**Test Critical Endpoints:**
```bash
# Test authentication
curl https://your-app-production.railway.app/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "production_user@example.com",
    "password": "secure_password"
  }' | jq

# Expected: 200 OK

# Test patient listing (with new indexes)
time curl https://your-app-production.railway.app/api/v2/patients \
  -H "Authorization: Bearer $PROD_TOKEN" | jq

# Expected: <200ms response time

# Test quiz creation
curl https://your-app-production.railway.app/api/v2/quiz/sessions \
  -H "Authorization: Bearer $PROD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"patient_id": 123, "quiz_template_id": 1}' | jq

# Expected: 200 OK
```

**Validation:**
- [ ] Authentication working
- [ ] Patient API responsive (<200ms)
- [ ] Quiz API working
- [ ] No 500 errors

### Step 5.2: Performance Monitoring (15 minutes)

**Monitor Real-Time Metrics:**

**Grafana Dashboard:**
- [ ] P95 latency: Target <200ms (Current: ____ms)
- [ ] Error rate: Target <1% (Current: ___%)
- [ ] Database CPU: Target <50% (Current: ___%)
- [ ] Request rate: Stable (Current: ___/min)

**Database Performance:**
```bash
railway run -- psql $DATABASE_URL -c "
SELECT
    query,
    calls,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
WHERE query LIKE '%patients%'
ORDER BY mean_exec_time DESC
LIMIT 5;
"

# Expected: Mean exec time <10ms
```

**Application Logs:**
```bash
railway logs --follow | grep -i error

# Expected: No critical errors
# Acceptable: INFO/WARNING level logs only
```

**Validation:**
- [ ] P95 latency within target
- [ ] Error rate within target
- [ ] Database performance improved
- [ ] No critical errors

### Step 5.3: User Impact Assessment (10 minutes)

**Monitor User Activity:**
```bash
# Check active user sessions
railway run -- psql $DATABASE_URL -c "
SELECT COUNT(*) as active_sessions
FROM sessions
WHERE is_active = true
AND last_activity > NOW() - INTERVAL '5 minutes';
"

# Expected: Normal session count (baseline from before deployment)

# Check error reports
railway run -- psql $DATABASE_URL -c "
SELECT COUNT(*) as recent_errors
FROM error_logs
WHERE created_at > NOW() - INTERVAL '15 minutes';
"

# Expected: <10 errors in 15 minutes
```

**User Feedback Monitoring:**
- [ ] No user-reported issues in support channels
- [ ] No spike in error reports
- [ ] User sessions stable
- [ ] No complaints about performance

**Validation:**
- [ ] Active sessions normal
- [ ] Error rate low
- [ ] No user complaints
- [ ] System stable

---

## Part 6: Post-Deployment (T+30 to T+120)

### Step 6.1: Extended Monitoring (60 minutes)

**Monitor for 1 Hour Post-Deployment:**

**Every 15 Minutes, Check:**
```bash
# Health check
curl https://your-app-production.railway.app/health | jq

# Error rate
railway run -- psql $DATABASE_URL -c "
SELECT
    DATE_TRUNC('minute', created_at) as minute,
    COUNT(*) as errors
FROM error_logs
WHERE created_at > NOW() - INTERVAL '15 minutes'
GROUP BY minute
ORDER BY minute;
"

# Performance metrics
# Check Grafana dashboard for:
# - P95 latency trend
# - Error rate trend
# - Database CPU trend
# - Request rate trend
```

**Validation (Ongoing):**
- [ ] T+15: All metrics stable
- [ ] T+30: All metrics stable
- [ ] T+45: All metrics stable
- [ ] T+60: All metrics stable

### Step 6.2: Success Notification (5 minutes)

**Send Deployment Success Notification:**
```
#p0-deployment channel:
✅ PRODUCTION DEPLOYMENT SUCCESSFUL

Deployment ID: p0-deploy-20251115-140000
Duration: 18 minutes
Downtime: 0 minutes

Performance Improvements:
✅ Doctor Dashboard: 1500ms → 8ms (99.5% faster)
✅ Patient Messages: 800ms → 4ms (99.5% faster)
✅ Quiz Analytics: 500ms → 6ms (98.8% faster)
✅ Alert Dashboard: 1200ms → 9ms (99.3% faster)

Security Enhancements:
✅ CSRF protection enabled
✅ SQL injection fixes verified
✅ Rate limiting active

HIPAA Compliance:
✅ Audit trail capturing all PHI access
✅ 7-year retention configured

System Health:
✅ Error rate: <1%
✅ P95 latency: <200ms
✅ Database CPU: 35% (down from 68%)
✅ All health checks passing

Monitoring will continue for 24 hours.
Next checkpoint: [Time]

Thanks to the team for the smooth deployment! 🎉
```

**Validation:**
- [ ] Success notification sent
- [ ] Metrics documented
- [ ] Team acknowledged
- [ ] Celebration! 🎉

### Step 6.3: Documentation Updates (10 minutes)

**Update Deployment Records:**
```bash
# Create deployment record
cat > docs/deployment/DEPLOYMENT_RECORD_$(date +%Y%m%d).md << EOF
# Deployment Record - $(date +%Y-%m-%d)

**Deployment ID:** ${DEPLOYMENT_ID}
**Environment:** Production
**Start Time:** $(date -d '18 minutes ago' +%Y-%m-%d\ %H:%M:%S)
**End Time:** $(date +%Y-%m-%d\ %H:%M:%S)
**Duration:** 18 minutes
**Downtime:** 0 minutes

## Migrations Applied
- 010: Database performance indexes (28 indexes)
- 011: HIPAA audit trail enhancement
- 012: Quiz response JSONB migration

## Performance Metrics
- Doctor Dashboard: 1500ms → 8ms
- Patient Messages: 800ms → 4ms
- Database CPU: 68% → 35%

## Issues Encountered
None

## Rollback Required
No

## Sign-off
- Deployed by: [Your Name]
- Verified by: [QA Name]
- Approved by: [Tech Lead Name]

**Status:** ✅ Success
EOF
```

**Update Runbooks:**
- [ ] Update incident response runbook with P0 context
- [ ] Update monitoring runbook with new dashboards
- [ ] Update rollback procedure with lessons learned
- [ ] Update deployment checklist with improvements

**Validation:**
- [ ] Deployment record created
- [ ] Runbooks updated
- [ ] Lessons learned documented
- [ ] Knowledge base updated

---

## Part 7: 24-Hour Monitoring Period

### Step 7.1: Ongoing Monitoring Checklist

**Monitor These Metrics for 24 Hours:**

**Every Hour:**
- [ ] P95 latency: <200ms
- [ ] Error rate: <1%
- [ ] Database CPU: <50%
- [ ] Active user sessions: Normal
- [ ] HIPAA audit logs: Working

**Every 4 Hours:**
- [ ] Run smoke tests
- [ ] Check for user feedback
- [ ] Review error logs
- [ ] Verify backup schedule

**Daily:**
- [ ] Generate performance report
- [ ] Review audit trail
- [ ] Check security alerts
- [ ] Update stakeholders

### Step 7.2: 24-Hour Checkpoint

**After 24 Hours, Complete Final Validation:**
```bash
# Generate 24-hour report
railway run -- psql $DATABASE_URL -c "
SELECT
    'Total Requests' as metric,
    COUNT(*) as value
FROM api_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
UNION ALL
SELECT
    'Error Rate' as metric,
    ROUND(100.0 * COUNT(CASE WHEN status_code >= 500 THEN 1 END) / COUNT(*), 2) as value
FROM api_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
UNION ALL
SELECT
    'Avg Response Time' as metric,
    AVG(response_time_ms) as value
FROM api_logs
WHERE created_at > NOW() - INTERVAL '24 hours';
"
```

**Final Sign-off:**
- [ ] No critical issues in 24 hours
- [ ] Performance metrics stable
- [ ] User feedback positive
- [ ] Deployment declared successful

**Send Final Update:**
```
#p0-deployment channel:
🎉 P0 DEPLOYMENT - 24 HOUR SUCCESS

All metrics stable for 24 hours:
✅ Uptime: 100%
✅ Error rate: <1%
✅ Performance: 99% improvement maintained
✅ User feedback: Positive
✅ No rollback required

Deployment officially closed.
Monitoring will continue as normal operations.

Thanks everyone! 🚀
```

---

## Troubleshooting

### Issue: Migration Fails

**Symptoms:**
- Migration script errors out
- Indexes not created
- Application crashes

**Resolution:**
```bash
# 1. Check migration error
railway logs | grep -i error

# 2. Rollback migration
railway run -- alembic downgrade -1

# 3. Fix issue (e.g., disk space, permissions)

# 4. Retry migration
railway run -- alembic upgrade head
```

**If Still Failing:**
- Execute `ROLLBACK_PROCEDURE.md`
- Contact database team
- Review migration script for syntax errors

### Issue: High Error Rate Post-Deployment

**Symptoms:**
- Error rate >5%
- 500 errors in logs
- Users reporting errors

**Resolution:**
```bash
# 1. Check error logs
railway logs | grep -i "500\|error" | tail -50

# 2. Identify error pattern
# Common issues:
# - Missing index causing timeout (unlikely with CONCURRENTLY)
# - Configuration error
# - Database connection pool exhaustion

# 3. Quick fixes:
# - Increase database connection pool
railway variables set DATABASE_POOL_SIZE=50
# - Restart application
railway restart

# 4. If errors persist >5 minutes:
# Execute ROLLBACK_PROCEDURE.md
```

### Issue: Slow Performance

**Symptoms:**
- P95 latency >500ms
- Database CPU >80%
- Queries timing out

**Resolution:**
```bash
# 1. Check slow queries
railway run -- psql $DATABASE_URL -c "
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
"

# 2. Verify indexes created
railway run -- psql $DATABASE_URL -c "
SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE 'idx_p0_%';
"
# Expected: 28

# 3. Check index usage
railway run -- psql $DATABASE_URL -c "
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE indexname LIKE 'idx_p0_%'
ORDER BY idx_scan DESC;
"

# 4. If indexes not being used:
# - ANALYZE tables to update statistics
railway run -- psql $DATABASE_URL -c "
ANALYZE patients;
ANALYZE messages;
ANALYZE quiz_sessions;
"
```

### Issue: HIPAA Audit Not Logging

**Symptoms:**
- No audit events in hipaa_audit_trail table
- Audit middleware errors

**Resolution:**
```bash
# 1. Check audit table exists
railway run -- psql $DATABASE_URL -c "\d+ hipaa_audit_trail"

# 2. Check audit logging enabled
railway variables get FIREBASE_ENABLE_AUDIT_LOGGING
# Expected: true

# 3. Check recent logs for audit errors
railway logs | grep -i "audit"

# 4. Test audit logging
curl -X GET https://your-app.railway.app/api/v2/patients/1 \
  -H "Authorization: Bearer $TOKEN"

# Verify event logged
railway run -- psql $DATABASE_URL -c "
SELECT * FROM hipaa_audit_trail
ORDER BY created_at DESC
LIMIT 5;
"
```

---

## Rollback Criteria

**Trigger Rollback If:**
- Error rate >5% for 5+ minutes
- P95 latency >1000ms for 5+ minutes
- Database CPU >90% for 5+ minutes
- Critical functionality broken
- Data corruption detected
- HIPAA audit logging failing

**How to Rollback:**
See `ROLLBACK_PROCEDURE.md` for detailed steps.

**Quick Rollback:**
```bash
railway run -- alembic downgrade -3  # Rollback migrations 010, 011, 012
railway restart  # Restart application
```

---

## Post-Deployment Checklist

After completing deployment, verify:
- [ ] See `POST_DEPLOYMENT_CHECKLIST.md`

---

## Contact Information

**On-Call Team:**
- Primary: _______________
- Secondary: _______________
- Escalation: _______________

**Communication Channels:**
- Slack: #p0-deployment
- PagerDuty: [Service]
- Email: engineering-team@company.com

---

**Document Version:** 1.0
**Last Updated:** 2025-11-15

**Related Documents:**
- `PRE_DEPLOYMENT_CHECKLIST.md`
- `POST_DEPLOYMENT_CHECKLIST.md`
- `ROLLBACK_PROCEDURE.md`
