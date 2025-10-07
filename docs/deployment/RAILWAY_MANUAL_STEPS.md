# Railway Manual Deployment Steps

## Current Situation
- **Code pushed**: ✅ Commit `3baa1cb` with Dockerfile changes
- **Railway rebuild**: ⏳ IN PROGRESS
- **Build URL**: https://railway.com/project/e3613fd1-1f2c-4495-bbae-52d7f609e3d8/service/d6ecfac8-f9c7-4281-8416-044a43481db2?id=f3d540ef-9397-4074-add6-242d923194f6

## Railway CLI Limitation
Railway CLI `railway logs` is currently showing "No deployments found". This can occur when:
1. Build is still in progress
2. CLI cache needs refresh
3. Deployment hasn't fully completed yet

## Alternative: Manual Steps via Railway Dashboard

### 1. Monitor Build Progress
**Action**: Open build URL in browser
**URL**: https://railway.com/project/e3613fd1-1f2c-4495-bbae-52d7f609e3d8/service/d6ecfac8-f9c7-4281-8416-044a43481db2?id=f3d540ef-9397-4074-add6-242d923194f6

**What to look for**:
- ✅ Docker build steps executing
- ✅ `COPY run_migrations.sh ./` step
- ✅ `RUN chmod +x run_migrations.sh` step
- ✅ Build completing successfully

### 2. View Deployment Logs
Once build completes, Railway will automatically deploy. Check deployment logs in dashboard:

**Navigate to**: Project → backend service → Deployments → Latest

**Expected log sequence**:
```
Starting Container
🔄 Running database migrations...
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade ... -> 20251007_add_message_sending_status
✅ Migrations completed successfully
INFO     Started server process [X]
INFO     Application startup complete.
INFO     Uvicorn running on http://0.0.0.0:8080
```

### 3. Verify Migration Applied

**Option A: Railway Dashboard SQL Query**
Navigate to: Project → PostgreSQL database → Query

Run:
```sql
SELECT unnest(enum_range(NULL::messagestatus)) as status;
```

Expected output should include:
```
pending
scheduled
sending      <-- NEW VALUE
sent
delivered
read
failed
cancelled
```

**Option B: Backend Health Check**
```bash
curl https://backend-hormonia-production.up.railway.app/health
```

Expected: `{"status": "healthy"}`

### 4. Alternative: Manual Migration (If Auto-Migration Fails)

If the migration script doesn't execute automatically:

**Step 1**: Access Railway shell
```bash
railway run --service backend bash
```

**Step 2**: Run migration manually
```bash
python -m alembic upgrade head
```

**Step 3**: Verify
```bash
python -c "from app.models.message import MessageStatus; print([s.value for s in MessageStatus])"
```

Expected output:
```python
['pending', 'scheduled', 'sending', 'sent', 'delivered', 'read', 'failed', 'cancelled']
```

### 5. Post-Deployment Validation

Once migration is confirmed:

**5.1 Check Application Logs** (Railway Dashboard)
- No errors related to MessageStatus
- No "ghost message" warnings
- No phone matching failures
- No scheduling duplication logs

**5.2 Test Message Flow** (Via Railway CLI or Dashboard)
```bash
# Create test message
curl -X POST https://backend-hormonia-production.up.railway.app/api/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "test-uuid",
    "content": "Test message",
    "direction": "outbound",
    "type": "text"
  }'

# Check status transitions:
# PENDING → SCHEDULED → SENDING → SENT
```

**5.3 Monitor for 1 Hour**
- No duplicate messages
- No stuck SCHEDULED messages
- All messages transitioning through SENDING status
- Delivery rate: 100%

### 6. Success Criteria

✅ **Build Complete**: Docker build finishes without errors
✅ **Migration Applied**: `sending` value exists in messagestatus enum
✅ **Application Healthy**: /health endpoint returns 200
✅ **No Errors**: Clean logs for 1 hour
✅ **Message Flow**: All statuses transitioning correctly

### 7. Rollback (If Needed)

If deployment causes issues:

```bash
# Revert Dockerfile changes
git revert 3baa1cb
git push origin docs-refactor-py313

# Redeploy
railway up --service backend
```

## Current Status
- **Build**: ⏳ IN PROGRESS (monitor via dashboard URL above)
- **Migration**: ⏳ PENDING (will execute on container startup)
- **Validation**: ⏳ PENDING (execute after migration confirms)

## Next Actions
1. **Immediate**: Open Railway dashboard build URL to monitor progress
2. **After build**: Check deployment logs for migration output
3. **After migration**: Execute validation steps (section 5)
4. **Document**: Update results in DEPLOYMENT_EXECUTION_LOG.md

---

**Created**: 2025-10-07 21:23 UTC
**Build URL**: [Click here](https://railway.com/project/e3613fd1-1f2c-4495-bbae-52d7f609e3d8/service/d6ecfac8-f9c7-4281-8416-044a43481db2?id=f3d540ef-9397-4074-add6-242d923194f6)
