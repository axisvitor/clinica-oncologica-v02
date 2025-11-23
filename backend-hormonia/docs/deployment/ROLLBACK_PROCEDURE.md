# Rollback Procedure - P0 Implementations

**Version:** 1.0
**Last Updated:** 2025-11-15
**Emergency Contact:** [On-Call Engineer]

---

## ⚠️ CRITICAL: When to Use This Procedure

**Use this rollback procedure immediately if:**
- Error rate >5% for 5+ consecutive minutes
- P95 latency >1000ms for 5+ consecutive minutes
- Database CPU >90% for 5+ consecutive minutes
- Critical functionality completely broken
- Data corruption detected
- HIPAA audit logging failure
- Security vulnerability introduced
- Database migration causing production outage

**Do NOT use this procedure for:**
- Minor performance issues (<3% error rate)
- Isolated user complaints
- Non-critical bugs
- Features working but not optimal

**Decision Authority:**
- On-call engineer can initiate rollback for critical issues
- Tech lead approval required for planned rollback
- Automatic rollback triggered by monitoring alerts (if configured)

---

## Rollback Overview

**What Gets Rolled Back:**
- Database migrations (010, 011, 012)
- Application code (revert to previous commit)
- Environment configuration (if changed)

**Expected Rollback Time:**
- Database rollback: 5-8 minutes
- Application rollback: 2-3 minutes
- **Total: <10 minutes**

**Expected Impact:**
- Downtime: 0 minutes (non-blocking operations)
- Performance: Return to pre-P0 levels (slower queries)
- Features: HIPAA audit will stop logging (acceptable for short rollback)

---

## Pre-Rollback Checklist

### Step 0: Assess Situation (2 minutes)

**Verify Rollback is Necessary:**
```bash
# Check error rate
railway run -- psql $DATABASE_URL -c "
SELECT
    COUNT(CASE WHEN status_code >= 500 THEN 1 END) as errors,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(CASE WHEN status_code >= 500 THEN 1 END) / NULLIF(COUNT(*), 0), 2) as error_rate
FROM api_logs
WHERE created_at > NOW() - INTERVAL '5 minutes';
"

# Check P95 latency (from Grafana or logs)
# Check database CPU
railway run -- psql $DATABASE_URL -c "
SELECT
    pid,
    state,
    query_start,
    wait_event_type,
    LEFT(query, 100) as query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start
LIMIT 20;
"
```

**Rollback Decision:**
- [ ] Error rate confirmed >5%: YES / NO
- [ ] P95 latency confirmed >1000ms: YES / NO
- [ ] Database CPU confirmed >90%: YES / NO
- [ ] Critical issue confirmed: YES / NO
- [ ] **Decision: ROLLBACK / WAIT AND MONITOR**

**If ROLLBACK, proceed immediately. Time is critical.**

---

## Step 1: Emergency Notification (1 minute)

**Notify Team Immediately:**
```
#p0-deployment channel:
🚨 EMERGENCY ROLLBACK IN PROGRESS

Deployment ID: p0-deploy-20251115-140000
Issue: [Error rate >5% / Database overload / Critical bug]
Rollback Started: [TIMESTAMP]
Expected Completion: [TIMESTAMP + 10 minutes]
On-Call: @engineer-name

DO NOT make any changes to production during rollback.
Updates will be posted every 2 minutes.
```

**Send PagerDuty Alert (if configured):**
```bash
# Trigger PagerDuty incident
curl -X POST https://api.pagerduty.com/incidents \
  -H "Authorization: Token token=$PAGERDUTY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "incident": {
      "type": "incident",
      "title": "P0 Deployment Rollback in Progress",
      "service": {"id": "$SERVICE_ID", "type": "service_reference"},
      "urgency": "high",
      "body": {
        "type": "incident_body",
        "details": "Rolling back P0 deployment due to critical issues"
      }
    }
  }'
```

**Validation:**
- [ ] Team notified in #p0-deployment
- [ ] PagerDuty incident created (if applicable)
- [ ] Stakeholders aware
- [ ] No other deployments in progress

---

## Step 2: Capture Evidence (2 minutes)

**Before rolling back, capture evidence for post-mortem:**

```bash
# Create evidence directory
mkdir -p /tmp/rollback_evidence_$(date +%Y%m%d_%H%M%S)
cd /tmp/rollback_evidence_*

# Capture current state
echo "Capturing evidence for rollback..."

# 1. Application logs (last 30 minutes)
railway logs --since 30m > app_logs.txt

# 2. Database error logs
railway run -- psql $DATABASE_URL -c "
SELECT * FROM error_logs
WHERE created_at > NOW() - INTERVAL '30 minutes'
ORDER BY created_at DESC;
" > db_errors.txt

# 3. Current migration version
railway run -- alembic current -v > migration_version.txt

# 4. Database performance stats
railway run -- psql $DATABASE_URL -c "
SELECT * FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 50;
" > slow_queries.txt

# 5. Active database connections
railway run -- psql $DATABASE_URL -c "
SELECT * FROM pg_stat_activity
WHERE state != 'idle';
" > active_connections.txt

# 6. System metrics snapshot
curl -s https://your-app-production.railway.app/health > health_snapshot.json

echo "Evidence captured in $(pwd)"
```

**Validation:**
- [ ] Logs captured
- [ ] Database state documented
- [ ] Evidence directory created: __________________

**IMPORTANT:** This evidence is critical for post-mortem analysis.

---

## Step 3: Database Rollback (5-8 minutes)

### Step 3.1: Backup Current State (2 minutes)

**Create emergency backup before rollback:**
```bash
# Emergency backup (quick, no compression)
BACKUP_FILE="/tmp/emergency_backup_$(date +%Y%m%d_%H%M%S).sql"

echo "Creating emergency backup..."
railway run -- pg_dump $DATABASE_URL > "$BACKUP_FILE"

# Verify backup size
ls -lh "$BACKUP_FILE"

echo "✅ Emergency backup: $BACKUP_FILE"
```

**Validation:**
- [ ] Backup created successfully
- [ ] Backup size reasonable (>10MB)
- [ ] Backup path: __________________

### Step 3.2: Rollback Database Migrations (3-5 minutes)

**Rollback migrations 010, 011, 012:**
```bash
# Check current migration version
railway run -- alembic current
# Expected: 012 (head)

# CRITICAL: Rollback 3 migrations
echo "Rolling back database migrations..."
railway run -- alembic downgrade -3

# This will:
# 1. Rollback migration 012 (JSONB migration)
# 2. Rollback migration 011 (HIPAA audit trail)
# 3. Rollback migration 010 (28 performance indexes)

# Monitor rollback progress
railway logs --follow

# Expected output:
# INFO  [alembic.runtime.migration] Running downgrade 012 -> 011
# INFO  [alembic.runtime.migration] Running downgrade 011 -> 010
# INFO  [alembic.runtime.migration] Running downgrade 010 -> 009

# Verify rollback successful
railway run -- alembic current -v
# Expected: 009 (pre-P0)
```

**Monitor During Rollback:**
```bash
# In separate terminal, watch database activity
railway run -- psql $DATABASE_URL -c "
SELECT
    pid,
    state,
    query_start,
    LEFT(query, 80) as query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;
" --watch 5
```

**Validation:**
- [ ] Migration rollback started
- [ ] No errors during rollback
- [ ] Migration version now 009 (pre-P0)
- [ ] Database still accessible
- [ ] Rollback time: _______ minutes

### Step 3.3: Verify Database State (1 minute)

**Verify migrations rolled back successfully:**
```bash
# Verify P0 indexes removed
railway run -- psql $DATABASE_URL -c "
SELECT COUNT(*) as p0_indexes_remaining
FROM pg_indexes
WHERE indexname LIKE 'idx_p0_%';
"
# Expected: 0 (all P0 indexes dropped)

# Verify HIPAA audit table exists (but not actively used)
railway run -- psql $DATABASE_URL -c "\dt hipaa_audit_trail"
# Table may still exist, but middleware is disabled

# Verify quiz_responses.value type
railway run -- psql $DATABASE_URL -c "
SELECT data_type
FROM information_schema.columns
WHERE table_name = 'quiz_responses'
AND column_name = 'value';
"
# Expected: May vary depending on migration 012 rollback
```

**Validation:**
- [ ] P0 indexes removed (0 remaining)
- [ ] Database schema reverted
- [ ] No errors in database logs

---

## Step 4: Application Rollback (2-3 minutes)

### Step 4.1: Revert to Previous Code Version (2 minutes)

**Option A: Railway Auto-Rollback (Recommended):**
```bash
# Find previous successful deployment in Railway dashboard
railway status --json | jq '.deployments | .[] | select(.status=="SUCCESS") | .id' | head -2

# Rollback to previous deployment via Railway UI:
# 1. Go to Railway dashboard
# 2. Select "Deployments" tab
# 3. Find previous successful deployment (before P0)
# 4. Click "Redeploy" on that deployment

# OR via CLI:
PREVIOUS_DEPLOYMENT_ID="<id from above>"
railway redeploy $PREVIOUS_DEPLOYMENT_ID
```

**Option B: Git Revert (If Railway auto-deploy):**
```bash
# Find commit hash before P0 deployment
git log --oneline | grep -B 5 "P0"

# Revert to previous commit
PREVIOUS_COMMIT="<commit-hash>"
git revert --no-commit HEAD
git revert --no-commit <P0-commit-hash>

# Or create revert commit
git revert <P0-commit-hash> -m "Emergency rollback: P0 deployment issues"

# Push revert (will trigger auto-deploy)
git push origin main

# Monitor deployment
railway logs --follow
```

**Validation:**
- [ ] Previous code version deployed
- [ ] Application restarted successfully
- [ ] Health check passing
- [ ] Deployment time: _______ minutes

### Step 4.2: Revert Environment Variables (1 minute)

**Revert any P0-specific environment variables:**
```bash
# Check if these were added in P0 deployment
railway variables list | grep -E "CSRF_SECRET_KEY|HIPAA_AUDIT_ENABLED|WEBHOOK_SECRET_KEY"

# If present and causing issues, revert:
railway variables set HIPAA_AUDIT_ENABLED=false
# Note: Keep CSRF and webhook secrets even in rollback (they don't hurt)

# Restart application if env vars changed
railway restart
```

**Validation:**
- [ ] Environment variables reviewed
- [ ] Problematic variables reverted
- [ ] Application restarted (if needed)

---

## Step 5: Post-Rollback Validation (3 minutes)

### Step 5.1: Immediate Health Check (1 minute)

**Verify system is healthy after rollback:**
```bash
# Health endpoint
curl https://your-app-production.railway.app/health | jq

# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "redis": "connected",
#   "version": "1.x.x"  # Previous version
# }

# Verify migration version (should be 009)
railway run -- alembic current
# Expected: 009 (pre-P0)

# Check error rate (should drop)
railway run -- psql $DATABASE_URL -c "
SELECT
    COUNT(CASE WHEN status_code >= 500 THEN 1 END) as errors,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(CASE WHEN status_code >= 500 THEN 1 END) / NULLIF(COUNT(*), 0), 2) as error_rate
FROM api_logs
WHERE created_at > NOW() - INTERVAL '2 minutes';
"
# Expected: Error rate <2%
```

**Validation:**
- [ ] Health endpoint: 200 OK
- [ ] Database connected
- [ ] Migration version: 009
- [ ] Error rate: <2%

### Step 5.2: Smoke Tests (2 minutes)

**Test critical functionality:**
```bash
# Test authentication
curl -s -X POST https://your-app-production.railway.app/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "secure_password"
  }' | jq

# Expected: 200 OK with token

# Test patient listing
ACCESS_TOKEN="<token from above>"
curl -s -X GET https://your-app-production.railway.app/api/v2/patients \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq

# Expected: 200 OK (may be slower without indexes)

# Test quiz session creation
curl -s -X POST https://your-app-production.railway.app/api/v2/quiz/sessions \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"patient_id": 1, "quiz_template_id": 1}' | jq

# Expected: 200 OK
```

**Validation:**
- [ ] Authentication working
- [ ] Patient API working
- [ ] Quiz API working
- [ ] No critical errors

---

## Step 6: Monitoring & Recovery (10-30 minutes)

### Step 6.1: Monitor System Stability (10 minutes)

**Watch metrics for 10 minutes post-rollback:**
```bash
# Monitor error rate every minute
for i in {1..10}; do
  echo "Minute $i:"
  railway run -- psql $DATABASE_URL -c "
  SELECT
    COUNT(CASE WHEN status_code >= 500 THEN 1 END) as errors,
    ROUND(100.0 * COUNT(CASE WHEN status_code >= 500 THEN 1 END) / NULLIF(COUNT(*), 0), 2) as error_rate
  FROM api_logs
  WHERE created_at > NOW() - INTERVAL '1 minute';
  "
  sleep 60
done
```

**Validation Checklist (Every 2 Minutes):**
- [ ] T+2: Error rate: ___% | Status: STABLE / UNSTABLE
- [ ] T+4: Error rate: ___% | Status: STABLE / UNSTABLE
- [ ] T+6: Error rate: ___% | Status: STABLE / UNSTABLE
- [ ] T+8: Error rate: ___% | Status: STABLE / UNSTABLE
- [ ] T+10: Error rate: ___% | Status: STABLE / UNSTABLE

**Expected Results:**
- Error rate stabilizes <2% within 5 minutes
- P95 latency returns to pre-P0 levels (higher but stable)
- Database CPU returns to normal (<60%)
- No new critical errors

### Step 6.2: User Impact Assessment (5 minutes)

**Check if users are affected by rollback:**
```bash
# Check active sessions
railway run -- psql $DATABASE_URL -c "
SELECT COUNT(DISTINCT user_id) as active_users
FROM sessions
WHERE is_active = true
AND last_activity > NOW() - INTERVAL '10 minutes';
"

# Check for user error reports
railway run -- psql $DATABASE_URL -c "
SELECT COUNT(*) as recent_errors
FROM user_error_reports
WHERE created_at > NOW() - INTERVAL '10 minutes';
"

# Monitor support channels
# - Slack #support
# - Email support queue
```

**Validation:**
- [ ] Active users: Normal levels
- [ ] User error reports: <5 in 10 minutes
- [ ] No increase in support tickets
- [ ] Users not significantly impacted

### Step 6.3: Document Rollback (5 minutes)

**Create rollback record for post-mortem:**
```bash
# Create rollback documentation
cat > /tmp/ROLLBACK_RECORD_$(date +%Y%m%d_%H%M%S).md << EOF
# Rollback Record - $(date +%Y-%m-%d %H:%M:%S)

## Incident Summary
**Rollback ID:** rollback-$(date +%Y%m%d-%H%M%S)
**Deployment ID:** p0-deploy-20251115-140000
**Trigger:** [Error rate >5% / Database overload / Critical bug]
**Started:** $(date +%Y-%m-%d\ %H:%M:%S)
**Completed:** [To be filled]
**Total Duration:** [To be calculated]

## Reason for Rollback
[Describe the issue that triggered rollback]

## Rollback Actions Taken
- [x] Database migrations rolled back (012 -> 009)
- [x] Application code reverted to previous version
- [x] Environment variables reviewed/reverted
- [x] System stability verified

## Post-Rollback Status
- Migration version: 009
- Error rate: [Current %]
- System status: STABLE / UNSTABLE
- User impact: MINIMAL / MODERATE / SEVERE

## Evidence Collected
- Evidence directory: $(pwd)/rollback_evidence_*
- Emergency backup: [Path]

## Next Steps
1. Root cause analysis
2. Fix identified issues
3. Re-test in staging
4. Plan re-deployment

**Rollback Executed By:** [Your Name]
**Approved By:** [Tech Lead Name]
EOF
```

**Validation:**
- [ ] Rollback record created
- [ ] Evidence preserved
- [ ] Timeline documented

---

## Step 7: Success Notification (2 minutes)

**Notify team of successful rollback:**
```
#p0-deployment channel:
✅ ROLLBACK COMPLETED SUCCESSFULLY

Deployment ID: p0-deploy-20251115-140000
Rollback Started: [TIMESTAMP]
Rollback Completed: [TIMESTAMP]
Total Rollback Time: [X] minutes

System Status:
✅ Database migrations rolled back (009)
✅ Application code reverted
✅ Error rate stabilized: <2%
✅ Critical functionality restored
✅ User impact: Minimal

Performance:
⚠️  Query performance returned to pre-P0 levels (slower)
⚠️  HIPAA audit logging temporarily disabled
✅ All critical APIs functional

Next Steps:
1. Post-mortem scheduled for [DATE/TIME]
2. Root cause analysis in progress
3. Re-deployment plan TBD

Thank you for the quick response. System is stable.

[Your Name]
```

**PagerDuty Resolution:**
```bash
# Resolve PagerDuty incident
curl -X PUT https://api.pagerduty.com/incidents/$INCIDENT_ID \
  -H "Authorization: Token token=$PAGERDUTY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "incident": {
      "type": "incident_reference",
      "status": "resolved",
      "resolution": "Rollback completed successfully. System stable."
    }
  }'
```

**Validation:**
- [ ] Team notified of successful rollback
- [ ] PagerDuty incident resolved
- [ ] Stakeholders informed
- [ ] Post-mortem scheduled

---

## Post-Rollback Monitoring (24 Hours)

### Hourly Checks (First 6 Hours)

**Monitor every hour for 6 hours post-rollback:**
- [ ] Hour 1: Error rate: ___% | Status: _______
- [ ] Hour 2: Error rate: ___% | Status: _______
- [ ] Hour 3: Error rate: ___% | Status: _______
- [ ] Hour 4: Error rate: ___% | Status: _______
- [ ] Hour 5: Error rate: ___% | Status: _______
- [ ] Hour 6: Error rate: ___% | Status: _______

**Expected:**
- Error rate stable <2%
- No new incidents
- User activity normal

### 24-Hour Checkpoint

**After 24 hours, verify stability:**
- [ ] System stable for 24 hours
- [ ] No degradation observed
- [ ] User feedback normal
- [ ] Post-mortem completed
- [ ] Re-deployment plan created

---

## Troubleshooting Rollback Issues

### Issue: Migration Rollback Fails

**Symptoms:**
- Alembic downgrade errors
- SQL errors during rollback
- Migrations stuck

**Resolution:**
```bash
# 1. Check alembic_version table
railway run -- psql $DATABASE_URL -c "SELECT * FROM alembic_version;"

# 2. Check migration file exists
ls alembic/versions/010*.py

# 3. Manual rollback if needed
railway run -- psql $DATABASE_URL << EOF
-- Drop P0 indexes manually
DROP INDEX CONCURRENTLY IF EXISTS idx_p0_patients_doctor_id;
-- [Repeat for all 28 indexes - see migration 010 downgrade]

-- Update alembic version
UPDATE alembic_version SET version_num = '009';
EOF

# 4. Verify rollback
railway run -- alembic current
# Expected: 009
```

### Issue: Application Won't Start After Rollback

**Symptoms:**
- Application crashes on startup
- Health check fails
- Database connection errors

**Resolution:**
```bash
# 1. Check application logs
railway logs | tail -100

# 2. Verify environment variables
railway variables list

# 3. Check database connectivity
railway run -- psql $DATABASE_URL -c "SELECT 1;"

# 4. Force restart
railway restart

# 5. If still failing, redeploy known-good version
# Get last known good deployment ID from Railway dashboard
railway redeploy <last-good-deployment-id>
```

### Issue: High Error Rate Persists After Rollback

**Symptoms:**
- Error rate still >3% after rollback
- Users still experiencing issues
- Database still overloaded

**Resolution:**
```bash
# 1. The issue may not be related to P0 deployment
# Check for other problems:

# Recent deployments
railway deployments

# Database issues
railway run -- psql $DATABASE_URL -c "
SELECT
    pid,
    state,
    wait_event_type,
    query
FROM pg_stat_activity
WHERE state != 'idle'
AND query_start < NOW() - INTERVAL '5 minutes';
"
# Look for long-running queries

# 2. Consider emergency maintenance mode
railway variables set MAINTENANCE_MODE=true
railway restart

# 3. Escalate to infrastructure team
# The problem may be infrastructure-related, not code
```

---

## Rollback Decision Matrix

| Metric | Normal | Warning | Critical (Rollback) |
|--------|--------|---------|---------------------|
| Error Rate | <1% | 1-3% | >5% for 5+ min |
| P95 Latency | <200ms | 200-500ms | >1000ms for 5+ min |
| Database CPU | <50% | 50-80% | >90% for 5+ min |
| Uptime | 100% | 99.9% | <99% |
| User Impact | None | Minor | Widespread |

**Rollback if 2 or more critical conditions met for 5+ minutes.**

---

## Recovery and Re-Deployment

### Post-Mortem Required

**Conduct post-mortem within 24 hours:**
- [ ] Timeline of events documented
- [ ] Root cause identified
- [ ] Contributing factors analyzed
- [ ] Evidence reviewed
- [ ] Action items created

**Post-Mortem Template:**
```markdown
# Post-Mortem: P0 Deployment Rollback

## Summary
[Brief description of incident]

## Timeline
- T-0: Deployment started
- T+X: Issue detected
- T+Y: Rollback initiated
- T+Z: System restored

## Root Cause
[Detailed analysis of what went wrong]

## Contributing Factors
1. [Factor 1]
2. [Factor 2]

## What Went Well
1. Rollback procedure worked
2. Team responded quickly
3. Minimal user impact

## What Went Wrong
1. [Issue 1]
2. [Issue 2]

## Action Items
1. [ ] Fix root cause
2. [ ] Improve testing
3. [ ] Update procedures
4. [ ] Re-deploy safely

## Lessons Learned
[Key takeaways]
```

### Re-Deployment Checklist

**Before re-attempting P0 deployment:**
- [ ] Root cause fixed
- [ ] Fix tested in local environment
- [ ] Fix tested in staging for 48+ hours
- [ ] Additional safeguards added
- [ ] Rollback procedure updated
- [ ] Team briefed on lessons learned
- [ ] Stakeholders approve re-deployment

---

## Emergency Contacts

**Critical Escalation (24/7):**
- On-Call Engineer: _______________
- Tech Lead: _______________
- Database Team Lead: _______________
- CTO/VP Engineering: _______________

**Communication Channels:**
- Emergency: #p0-deployment
- PagerDuty: [Service Name]
- Phone: [On-call number]

**External Vendors:**
- Railway Support: support@railway.app
- Database Vendor: [Contact]
- Monitoring Vendor: [Contact]

---

## Rollback Procedure Summary

**Quick Reference (Print and Keep Handy):**

1. **Assess** (2 min): Verify rollback needed
2. **Notify** (1 min): Alert team immediately
3. **Capture Evidence** (2 min): Save logs and state
4. **Backup** (2 min): Emergency database backup
5. **Rollback DB** (5 min): `alembic downgrade -3`
6. **Rollback App** (2 min): Redeploy previous version
7. **Validate** (3 min): Smoke tests and health check
8. **Monitor** (10 min): Watch error rate stabilize
9. **Document** (5 min): Create rollback record
10. **Notify Success** (2 min): Inform team

**Total Time: ~10 minutes**

---

**Document Version:** 1.0
**Last Updated:** 2025-11-15

**Related Documents:**
- `PRE_DEPLOYMENT_CHECKLIST.md`
- `DEPLOYMENT_PROCEDURE.md`
- `POST_DEPLOYMENT_CHECKLIST.md`

**Emergency Hotline:** [Your Phone Number]

---

**IMPORTANT: Print this procedure and keep it accessible. In an emergency, you may not have time to search for it.**
