# Railway Deployment - Next Steps

## 🎯 Current Status (as of 2025-10-07 21:30 UTC)

**Deployment Phase**: 🟡 Build & Migration In Progress

### ✅ Completed
1. Code changes implemented and tested
2. Dockerfile updated with auto-migration
3. Migration script created (`run_migrations.sh`)
4. Code committed (3 commits total)
5. Code pushed to GitHub
6. Railway deployment triggered
7. Complete documentation created

### ⏳ In Progress
1. Railway Docker build executing
2. Waiting for container deployment
3. Auto-migration will run on startup

### ⏳ Pending
1. Migration execution verification
2. Database enum validation
3. Application health checks
4. 1-hour monitoring period
5. Final results documentation

---

## 📋 Immediate Next Steps (Manual Actions Required)

### Step 1: Monitor Railway Build (NOW)
**Action**: Open Railway Dashboard to watch build progress

**URL**: https://railway.com/project/e3613fd1-1f2c-4495-bbae-52d7f609e3d8/service/d6ecfac8-f9c7-4281-8416-044a43481db2?id=f3d540ef-9397-4074-add6-242d923194f6

**What to Look For**:
```
✅ Building Docker image...
✅ Step 28/30 : COPY run_migrations.sh ./
✅ Step 29/30 : RUN chmod +x run_migrations.sh
✅ Successfully built [image-id]
✅ Successfully tagged railway.app/[...]
✅ Pushing to registry...
```

**Expected Time**: 3-5 minutes from 21:15 UTC start

---

### Step 2: Verify Migration Execution (After Build)
**Action**: Check deployment logs in Railway Dashboard

**Navigate to**: Project → backend service → Deployments → Latest

**Expected Output**:
```bash
Starting Container
🔄 Running database migrations...
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 9a84c2fd1234 -> 20251007_add_message_sending_status, Add SENDING status
✅ Migrations completed successfully

=== STARTUP DEBUG - Verificando Ambiente ===
✓ DATABASE_URL: database-clinica-neoplasias...
✓ REDIS_URL: redis-14149...
...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

**Success Criteria**:
- ✅ Migration runs without errors
- ✅ Application starts successfully
- ✅ No errors in startup logs

---

### Step 3: Validate Database Changes (After Startup)
**Action**: Query PostgreSQL to confirm SENDING status exists

**Option A: Railway Dashboard SQL Console**
1. Navigate to: Project → PostgreSQL database → Query
2. Run query:
```sql
SELECT unnest(enum_range(NULL::messagestatus)) as status;
```

**Expected Output**:
```
pending
scheduled
sending      ← Should appear here
sent
delivered
read
failed
cancelled
```

**Option B: Via Backend API** (if SQL console unavailable)
```bash
curl https://backend-hormonia-production.up.railway.app/api/v1/messages/statuses
```

---

### Step 4: Health Check Validation (After Migration)
**Action**: Verify application health

**Command**:
```bash
curl https://backend-hormonia-production.up.railway.app/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "checks": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

**Additional Checks**:
```bash
# Check API root
curl https://backend-hormonia-production.up.railway.app/

# Check docs
curl https://backend-hormonia-production.up.railway.app/docs

# Check metrics
curl https://backend-hormonia-production.up.railway.app/metrics
```

---

### Step 5: Message Flow Testing (After Health Check)
**Action**: Test complete message lifecycle with new SENDING status

**Test Scenario**:
```bash
# 1. Create test message
MESSAGE_ID=$(curl -X POST https://backend-hormonia-production.up.railway.app/api/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -d '{
    "patient_id": "test-patient-uuid",
    "content": "Test message for SENDING status",
    "direction": "outbound",
    "type": "text"
  }' | jq -r '.id')

# 2. Schedule message
curl -X POST https://backend-hormonia-production.up.railway.app/api/v1/messages/$MESSAGE_ID/schedule \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -d '{
    "send_time": "2025-10-07T21:45:00Z",
    "priority": "high"
  }'

# 3. Wait 2 minutes, then check status
curl https://backend-hormonia-production.up.railway.app/api/v1/messages/$MESSAGE_ID \
  -H "Authorization: Bearer $TEST_TOKEN"
```

**Expected Status Progression**:
1. Initial: `PENDING`
2. After schedule: `SCHEDULED`
3. During send: `SENDING` ← **NEW - Should appear**
4. After send: `SENT`
5. After delivery: `DELIVERED`

---

### Step 6: Production Monitoring (1 Hour)
**Action**: Monitor Railway logs for any errors or issues

**Command** (Run in terminal, let it stream):
```bash
railway logs --service backend --follow
```

**Or via Dashboard**:
Project → backend service → Logs (enable auto-refresh)

**What to Monitor**:
- ❌ No errors related to MessageStatus
- ❌ No "ghost message" warnings
- ❌ No phone matching failures
- ❌ No scheduling duplication logs
- ❌ No database connection errors
- ✅ Messages transitioning through SENDING
- ✅ All deliveries successful
- ✅ No duplicate message warnings

**Critical Queries to Run**:

**Check for Duplicates**:
```sql
-- No duplicate messages with same content/patient/time
SELECT patient_id, content, scheduled_for, COUNT(*) as count
FROM messages
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY patient_id, content, scheduled_for
HAVING COUNT(*) > 1;
-- Should return 0 rows
```

**Check for Stuck Messages**:
```sql
-- No messages stuck in SCHEDULED status
SELECT COUNT(*)
FROM messages
WHERE status = 'scheduled'
AND scheduled_for < NOW() - INTERVAL '5 minutes';
-- Should return 0
```

**Check SENDING Status Usage**:
```sql
-- Messages using new SENDING status
SELECT COUNT(*)
FROM messages
WHERE status = 'sending';
-- Should show active count (usually 0-5 at any moment)
```

---

### Step 7: Smoke Test Execution (After 1 Hour)
**Action**: Run comprehensive smoke test suite

**Update and Run**:
```bash
# 1. Update smoke test with actual Railway URL
cd backend-hormonia/tests
# Edit smoke_test.py: Change BASE_URL to actual Railway URL

# 2. Run smoke tests
python smoke_test.py
```

**Expected Results**:
```
[PASS] Health Check: OK
[PASS] Database Health: OK
[PASS] Create Patient: OK
[PASS] Create Message: OK
[PASS] Schedule Message: OK
[PASS] Message Status: OK (includes SENDING)
```

---

### Step 8: Document Results (Final)
**Action**: Update deployment logs with final status

**Files to Update**:
1. `docs/deployment/DEPLOYMENT_EXECUTION_LOG.md`
   - Update timeline with actual completion times
   - Add final status (SUCCESS/FAILED)
   - Document any issues encountered

2. `docs/deployment/DEPLOYMENT_SUMMARY_2025-10-07.md`
   - Update "Current Status" section
   - Add final metrics
   - Document lessons learned

3. Create `docs/deployment/DEPLOYMENT_RESULTS.md`
   - Summary of all validations
   - Performance metrics
   - Issues and resolutions
   - Recommendations for future

---

## ⚠️ If Something Goes Wrong

### Issue: Build Fails
**Symptoms**: Docker build errors in Railway dashboard

**Actions**:
1. Check build logs for specific error
2. Verify `run_migrations.sh` file exists in repo
3. Check Dockerfile syntax
4. Try rebuilding: `railway up --service backend`

**Rollback**: Revert commits and redeploy:
```bash
git revert a3cefe7 b4db614 3baa1cb
git push origin docs-refactor-py313
railway up --service backend
```

---

### Issue: Migration Fails
**Symptoms**: Error in migration script during startup

**Actions**:
1. Check migration logs in Railway
2. Verify database permissions
3. Check Alembic version compatibility
4. Try manual migration:
```bash
railway run --service backend python -m alembic upgrade head
```

**Rollback**: Revert Dockerfile, keep enum value:
```bash
git revert a3cefe7 b4db614 3baa1cb
git push origin docs-refactor-py313
# Migration already applied - enum value stays (harmless)
```

---

### Issue: Application Fails to Start
**Symptoms**: Container restarts, health check fails

**Actions**:
1. Check startup logs for error
2. Verify environment variables
3. Test database connection
4. Test Redis connection

**Emergency Rollback**:
```bash
# Immediate: Revert to last working deployment
railway rollback --service backend

# Then: Fix code and redeploy
git revert a3cefe7 b4db614 3baa1cb
git push origin docs-refactor-py313
railway up --service backend
```

---

### Issue: Messages Not Using SENDING Status
**Symptoms**: Messages skip from SCHEDULED to SENT

**Actions**:
1. Verify migration ran successfully
2. Check enum values in database
3. Check Celery task code
4. Review MessageScheduler logs

**Fix**: This indicates code/DB mismatch - rerun migration:
```bash
railway run --service backend python -m alembic upgrade head
```

---

## 📞 Support Contacts

### Railway Issues
- Dashboard: https://railway.app
- Status: https://status.railway.app
- Support: support@railway.app

### Database Issues
- AWS RDS Console (PostgreSQL)
- Connection string in Railway env vars
- Check security groups and VPC settings

### Application Issues
- Review GitHub commits
- Check Railway deployment logs
- Reference P0 fix documentation

---

## 📊 Success Checklist

Use this checklist to track deployment progress:

### Phase 1: Build ⏳
- [ ] Railway build triggered
- [ ] Docker build completes
- [ ] Migration script copied
- [ ] Container built successfully

### Phase 2: Deployment ⏳
- [ ] Container starts
- [ ] Migration executes
- [ ] Application starts
- [ ] Health check passes

### Phase 3: Validation ⏳
- [ ] SENDING enum value exists
- [ ] No migration errors
- [ ] No startup errors
- [ ] All endpoints responding

### Phase 4: Testing ⏳
- [ ] Message flow works
- [ ] Status transitions include SENDING
- [ ] No duplicate messages
- [ ] No stuck messages
- [ ] Delivery rate 100%

### Phase 5: Monitoring ⏳
- [ ] 1 hour with no errors
- [ ] No ghost messages
- [ ] No phone matching issues
- [ ] Smoke tests pass
- [ ] Documentation updated

---

## 🎯 Final Deliverables

Once all steps complete, you should have:

1. ✅ **Working Production System**
   - All P0 fixes deployed
   - SENDING status active
   - 100% message delivery
   - Zero duplicate messages

2. ✅ **Complete Documentation**
   - Deployment summary
   - Execution log
   - Manual steps guide
   - Next steps (this file)
   - Final results report

3. ✅ **Validated System**
   - Database migration confirmed
   - Health checks passing
   - Message flow tested
   - 1-hour stability proven
   - Smoke tests passing

4. ✅ **Audit Trail**
   - All commits documented
   - Timeline recorded
   - Issues and fixes logged
   - Metrics captured

---

## 🚀 After Deployment Success

Once deployment is confirmed successful:

1. **Notify Stakeholders**
   - Email team with deployment summary
   - Share Railway dashboard link
   - Provide metrics report

2. **Update Project Board**
   - Close P0 tickets (all 4)
   - Update P1 ticket status
   - Create tickets for any new issues

3. **Plan Next Steps**
   - Schedule P1-1 implementation (flow engine consolidation)
   - Plan E2E test suite execution
   - Schedule next deployment window

4. **Archive Documentation**
   - Tag release in Git
   - Archive deployment docs
   - Update main README

---

**Created**: 2025-10-07 21:30 UTC
**Build Status**: Check Railway dashboard
**Next Update**: After build completes (ETA 2-3 minutes)
**Monitoring**: Active via Railway logs

---

## 🔗 Quick Reference Links

- **Railway Build**: https://railway.com/project/e3613fd1-1f2c-4495-bbae-52d7f609e3d8/service/d6ecfac8-f9c7-4281-8416-044a43481db2?id=f3d540ef-9397-4074-add6-242d923194f6
- **Deployment Summary**: [DEPLOYMENT_SUMMARY_2025-10-07.md](DEPLOYMENT_SUMMARY_2025-10-07.md)
- **Execution Log**: [DEPLOYMENT_EXECUTION_LOG.md](DEPLOYMENT_EXECUTION_LOG.md)
- **Manual Steps**: [RAILWAY_MANUAL_STEPS.md](RAILWAY_MANUAL_STEPS.md)
- **P0 Fixes**: [P0_COMPLETION_SUMMARY.md](P0_COMPLETION_SUMMARY.md)

**END OF DOCUMENT**
