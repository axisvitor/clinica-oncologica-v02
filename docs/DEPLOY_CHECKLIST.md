# Deploy Checklist
## Sistema Hormonia (Clínica Oncológica V02)

**Version**: 1.0  
**Last Updated**: Janeiro 2025  
**Purpose**: Garantir deploys seguros e sem downtime

---

## 📋 Table of Contents

1. [Pre-Deploy Checklist](#pre-deploy-checklist)
2. [Staging Deploy](#staging-deploy)
3. [Production Deploy](#production-deploy)
4. [Post-Deploy Validation](#post-deploy-validation)
5. [Rollback Procedure](#rollback-procedure)
6. [Emergency Contacts](#emergency-contacts)

---

## 🔍 Pre-Deploy Checklist

### Code Quality

- [ ] **All tests passing**
  ```bash
  # Backend
  cd backend-hormonia
  pytest --cov=app --cov-report=term
  
  # Frontend
  cd frontend-hormonia
  npm run test
  
  # E2E
  npm run test:e2e
  ```

- [ ] **No linting errors**
  ```bash
  # Backend
  ruff check app/
  mypy app/
  
  # Frontend
  npm run lint
  npm run type-check
  ```

- [ ] **Coverage meets threshold** (90%+)
  ```bash
  pytest --cov=app --cov-report=html
  # Check htmlcov/index.html
  ```

- [ ] **Build succeeds**
  ```bash
  # Frontend
  npm run build
  # Check dist/ size < 500KB (initial bundle)
  
  # Backend
  docker build -t hormonia-backend:latest .
  ```

### Code Review

- [ ] **At least 2 approvals** on PR
- [ ] **No unresolved comments**
- [ ] **Squash commits** (clean history)
- [ ] **Conventional commit message**
  ```
  feat(api): implement v2 patients endpoint
  
  - Add cursor-based pagination
  - Add field selection
  - Add eager loading for relationships
  
  BREAKING CHANGE: Response format changed
  ```

### Documentation

- [ ] **README.md updated** (se mudou setup)
- [ ] **API docs updated** (OpenAPI/Swagger)
- [ ] **CHANGELOG.md updated**
  ```markdown
  ## [2.0.0] - 2025-01-XX
  
  ### Added
  - API v2 with cursor pagination
  - Field selection support
  
  ### Changed
  - Response format for patient list
  
  ### Deprecated
  - API v1 (shutdown in 6 months)
  ```
- [ ] **Environment variables documented** (`.env.example`)
- [ ] **Migration guide created** (se breaking change)

### Database

- [ ] **Migrations tested locally**
  ```bash
  # Test upgrade
  alembic upgrade head
  
  # Test rollback
  alembic downgrade -1
  alembic upgrade head
  ```

- [ ] **Migrations are idempotent** (safe to re-run)
- [ ] **No data loss** (verified with test data)
- [ ] **Indexes added** for new queries
- [ ] **Backup plan ready** (manual backup before migration)

### Dependencies

- [ ] **No security vulnerabilities**
  ```bash
  # Backend
  pip-audit
  
  # Frontend
  npm audit
  ```

- [ ] **Dependencies up to date** (patch versions)
- [ ] **Lock files committed** (`poetry.lock`, `package-lock.json`)

### Configuration

- [ ] **Environment variables set** in Railway/Vercel
  ```bash
  # Check required vars
  grep -v "^#" .env.example | grep "=" | cut -d "=" -f1
  ```

- [ ] **Secrets rotated** (se necessário)
- [ ] **Feature flags configured** (se gradual rollout)
- [ ] **Rate limits configured**
- [ ] **CORS origins updated** (se mudou domínio)

### Performance

- [ ] **Load testing completed** (Locust)
  ```bash
  locust -f tests/performance/locustfile.py \
    --headless \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --host https://staging.hormonia.com
  ```

- [ ] **p95 latency < 500ms** (target: < 200ms)
- [ ] **No memory leaks** (monitor for 30 min)
- [ ] **Database query performance** validated
  ```sql
  -- Check slow queries
  SELECT * FROM pg_stat_statements 
  ORDER BY mean_exec_time DESC 
  LIMIT 10;
  ```

### Monitoring

- [ ] **Sentry configured** (DSN set)
- [ ] **Alerts configured** (Slack, Email)
- [ ] **Dashboards ready** (Grafana)
- [ ] **Log aggregation working** (CloudWatch, Datadog)

---

## 🧪 Staging Deploy

### 1. Pre-Deploy Communication

- [ ] **Notify team** in #deployments Slack channel
  ```
  🚀 Starting staging deploy
  - Branch: feat/api-v2
  - PR: #123
  - ETA: 15 min
  - Changes: API v2 implementation
  ```

- [ ] **Lock deployments** (prevent concurrent deploys)

### 2. Database Migration (Staging)

- [ ] **Create manual backup**
  ```bash
  # PostgreSQL backup
  pg_dump -h staging-db.example.com \
    -U hormonia \
    -d hormonia_db \
    -F c \
    -f backup_$(date +%Y%m%d_%H%M%S).dump
  
  # Upload to S3
  aws s3 cp backup_*.dump s3://hormonia-backups/staging/
  ```

- [ ] **Run migrations**
  ```bash
  # Via Railway CLI
  railway run alembic upgrade head
  
  # Verify migration
  railway run alembic current
  ```

- [ ] **Validate schema**
  ```bash
  # Check tables exist
  railway run python -c "
  from app.database import engine
  from sqlalchemy import inspect
  inspector = inspect(engine)
  print(inspector.get_table_names())
  "
  ```

### 3. Backend Deploy (Staging)

- [ ] **Deploy via Railway**
  ```bash
  # Push to staging branch
  git push origin main:staging
  
  # Or via Railway CLI
  railway up --environment staging
  ```

- [ ] **Monitor deployment logs**
  ```bash
  railway logs --environment staging
  ```

- [ ] **Wait for health check** (200 OK)
  ```bash
  curl -f https://staging-api.hormonia.com/api/health || exit 1
  ```

### 4. Frontend Deploy (Staging)

- [ ] **Deploy via Vercel**
  ```bash
  # Automatic deploy on push to staging branch
  git push origin main:staging
  
  # Or manual deploy
  vercel --prod --scope hormonia-staging
  ```

- [ ] **Wait for build to complete** (check Vercel dashboard)

- [ ] **Verify deployment**
  ```bash
  curl -I https://staging.hormonia.com
  # Check X-Vercel-Id header
  ```

### 5. Smoke Testing (Staging)

- [ ] **API endpoints responding**
  ```bash
  # Health check
  curl https://staging-api.hormonia.com/api/health
  
  # v2 endpoints
  curl https://staging-api.hormonia.com/api/v2/patients
  ```

- [ ] **Frontend loads**
  ```bash
  # Check homepage
  curl -f https://staging.hormonia.com
  
  # Check Lighthouse score
  lighthouse https://staging.hormonia.com --output=json
  ```

- [ ] **Authentication works** (login/logout)
- [ ] **Database queries work** (list patients)
- [ ] **Redis cache works** (check cached endpoints)
- [ ] **Webhooks working** (send test webhook)
- [ ] **Email sending works** (trigger test email)
- [ ] **File uploads work** (if applicable)

### 6. Staging Validation

- [ ] **Run E2E tests against staging**
  ```bash
  PLAYWRIGHT_BASE_URL=https://staging.hormonia.com \
    npm run test:e2e
  ```

- [ ] **QA team validates** critical flows
  - [ ] Patient registration
  - [ ] Quiz submission
  - [ ] Dashboard analytics
  - [ ] WhatsApp integration

- [ ] **No errors in Sentry** (last 30 min)
- [ ] **No performance degradation** (compare with production)

---

## 🚀 Production Deploy

### Pre-Production Checklist

- [ ] **Staging validated** (all tests pass)
- [ ] **No P0/P1 bugs** in staging
- [ ] **Business approval** (PO sign-off)
- [ ] **Deploy window scheduled** (low-traffic time)
- [ ] **Team on standby** (for rollback if needed)

### 1. Pre-Deploy Communication

- [ ] **Announce deploy** in #general and #deployments
  ```
  🚨 PRODUCTION DEPLOY STARTING
  - Time: 2025-01-15 02:00 UTC (23:00 BRT)
  - Expected duration: 30 min
  - Expected downtime: < 2 min (database migration)
  - Changes: API v2 launch, legacy cleanup
  - Rollback plan: Tag v1.9.0 ready
  ```

- [ ] **Email clients** (se breaking change)
- [ ] **Update status page** (status.hormonia.com)

### 2. Enable Maintenance Mode (Optional)

- [ ] **Show maintenance page** (if downtime expected)
  ```bash
  # Set env var in Railway
  railway variables set MAINTENANCE_MODE=true
  ```

- [ ] **Queue incoming requests** (if possible)

### 3. Database Migration (Production)

- [ ] **Final backup** (critical!)
  ```bash
  # PostgreSQL
  pg_dump -h prod-db.example.com \
    -U hormonia \
    -d hormonia_db \
    -F c \
    -f prod_backup_$(date +%Y%m%d_%H%M%S).dump
  
  # Verify backup integrity
  pg_restore --list prod_backup_*.dump | head -20
  
  # Upload to S3 (multiple regions)
  aws s3 cp prod_backup_*.dump s3://hormonia-backups/production/
  aws s3 cp prod_backup_*.dump s3://hormonia-backups-dr/production/
  ```

- [ ] **Run migrations** (production)
  ```bash
  railway run --environment production alembic upgrade head
  ```

- [ ] **Monitor migration duration** (should be < 2 min)

- [ ] **Validate schema changes**
  ```bash
  # Check migration succeeded
  railway run --environment production alembic current
  
  # Query new tables/columns
  railway run --environment production psql -c "\d patients"
  ```

### 4. Backend Deploy (Production)

- [ ] **Create Git tag**
  ```bash
  git tag -a v2.0.0 -m "Release v2.0.0 - API v2"
  git push origin v2.0.0
  ```

- [ ] **Deploy to production**
  ```bash
  git push origin main:production
  
  # Or via Railway
  railway up --environment production
  ```

- [ ] **Monitor deployment** (Railway logs)
  ```bash
  railway logs --environment production --tail
  ```

- [ ] **Wait for health check**
  ```bash
  while ! curl -f https://api.hormonia.com/api/health; do
    echo "Waiting for API..."
    sleep 5
  done
  echo "✅ API healthy!"
  ```

### 5. Frontend Deploy (Production)

- [ ] **Deploy to Vercel**
  ```bash
  vercel --prod --scope hormonia
  ```

- [ ] **Wait for build** (check Vercel dashboard)

- [ ] **Verify CDN propagation**
  ```bash
  # Check multiple regions
  curl -H "Host: hormonia.com" https://cdn.vercel.com/_next/...
  ```

### 6. Disable Maintenance Mode

- [ ] **Re-enable app**
  ```bash
  railway variables set MAINTENANCE_MODE=false
  ```

- [ ] **Update status page** (All Systems Operational)

---

## ✅ Post-Deploy Validation

### Immediate Checks (0-5 min)

- [ ] **API health check passes**
  ```bash
  curl https://api.hormonia.com/api/health
  # Expected: {"status": "healthy", "version": "2.0.0"}
  ```

- [ ] **Frontend loads**
  ```bash
  curl -I https://hormonia.com
  # Expected: 200 OK
  ```

- [ ] **Critical endpoints work**
  ```bash
  # v2 patients
  curl https://api.hormonia.com/api/v2/patients
  
  # v2 quiz
  curl https://api.hormonia.com/api/v2/quiz/active
  ```

- [ ] **No 5xx errors** in logs (last 5 min)
  ```bash
  railway logs --environment production | grep " 5[0-9][0-9] "
  ```

### Short-term Monitoring (5-30 min)

- [ ] **Error rate < 1%** (Sentry dashboard)
- [ ] **Latency p95 < 500ms** (Grafana dashboard)
- [ ] **No memory leaks** (Railway metrics)
- [ ] **Database connections stable** (< 50 connections)
- [ ] **Redis cache hit rate > 80%**

### Smoke Tests (Production)

⚠️ **Use test accounts only! Never touch real user data.**

- [ ] **User can login** (test@hormonia.com)
- [ ] **Patient list loads** (Dashboard)
- [ ] **Quiz submission works** (test patient)
- [ ] **Analytics dashboard loads**
- [ ] **WhatsApp integration works** (test message)
- [ ] **Email notifications sent** (check inbox)

### Business Metrics (30+ min)

- [ ] **Active users count normal** (compared to yesterday)
- [ ] **Quiz completion rate normal**
- [ ] **API request volume normal**
- [ ] **No customer complaints** (check support inbox)

---

## 🔄 Rollback Procedure

### When to Rollback?

Rollback **immediately** if:
- 🔴 Error rate > 5%
- 🔴 Latency p95 > 2 seconds
- 🔴 Critical feature broken (auth, payments)
- 🔴 Data corruption detected
- 🔴 Security vulnerability introduced

### Quick Rollback (< 5 min)

1. **Rollback backend**
   ```bash
   # Via Railway (redeploy previous version)
   railway rollback --environment production
   
   # Or revert Git
   git revert HEAD
   git push origin main
   ```

2. **Rollback frontend**
   ```bash
   # Via Vercel (instant rollback)
   vercel rollback https://hormonia.com --to <previous-deployment-url>
   ```

3. **Rollback database** (if migration ran)
   ```bash
   # Only if safe (no data loss)
   railway run --environment production alembic downgrade -1
   
   # If unsafe, restore from backup
   pg_restore -h prod-db.example.com \
     -U hormonia \
     -d hormonia_db \
     -c \
     prod_backup_TIMESTAMP.dump
   ```

4. **Verify rollback**
   ```bash
   curl https://api.hormonia.com/api/health
   # Check version is previous (v1.9.0)
   ```

5. **Communicate**
   ```
   🚨 ROLLBACK COMPLETED
   - Reason: High error rate (7%)
   - Previous version restored: v1.9.0
   - Impact: 5 min downtime
   - Next steps: Root cause analysis
   ```

### Post-Rollback

- [ ] **Create incident report** (docs/incidents/YYYY-MM-DD.md)
- [ ] **Root cause analysis** (what went wrong?)
- [ ] **Fix issues** (create hotfix branch)
- [ ] **Re-test** (before next deploy attempt)
- [ ] **Update runbook** (prevent future occurrence)

---

## 📊 Metrics to Monitor

### System Health

```yaml
# SLOs (Service Level Objectives)
availability: 99.9%          # Max 43 min downtime/month
latency_p95: < 500ms
latency_p99: < 1s
error_rate: < 1%
```

### Dashboards

1. **Grafana - System Metrics**
   - CPU, Memory, Disk usage
   - Network I/O
   - Request rate, latency, errors

2. **Grafana - Business Metrics**
   - Active users (DAU, MAU)
   - Quiz submissions
   - WhatsApp messages sent
   - API calls by endpoint

3. **Sentry - Error Tracking**
   - Error rate by endpoint
   - Error types (500, 400, etc.)
   - User impact

4. **Railway/Vercel - Infrastructure**
   - Deployment status
   - Build logs
   - Environment variables

---

## 📞 Emergency Contacts

### On-Call Rotation

| Role | Primary | Secondary |
|------|---------|-----------|
| Backend | @dev1 | @dev2 |
| Frontend | @dev3 | @dev4 |
| DevOps | @dev5 | @dev6 |
| Database | @dba1 | @dba2 |

### Escalation Path

1. **Level 1**: On-call dev (5 min response time)
2. **Level 2**: Tech Lead (15 min response time)
3. **Level 3**: CTO (30 min response time)

### Communication Channels

- **Slack**: #incidents (urgent), #deployments (status)
- **Email**: oncall@hormonia.com
- **Phone**: +55 11 9999-9999 (emergencies only)
- **Status Page**: status.hormonia.com

---

## 📝 Deploy Log Template

```markdown
# Deploy Log - v2.0.0

**Date**: 2025-01-15  
**Time**: 02:00 UTC  
**Deployer**: @dev1  
**Environment**: Production

## Changes
- Implemented API v2
- Removed legacy endpoints
- Expanded test coverage to 90%

## Timeline
- 02:00 - Maintenance mode enabled
- 02:02 - Database migration started
- 02:05 - Database migration completed
- 02:07 - Backend deployed
- 02:10 - Frontend deployed
- 02:12 - Maintenance mode disabled
- 02:15 - Smoke tests passed
- 02:30 - Monitoring green, deploy successful

## Metrics (30 min post-deploy)
- Error rate: 0.3% ✅
- Latency p95: 180ms ✅
- Active users: 1,234 ✅
- No Sentry alerts ✅

## Issues
- None

## Notes
- Deploy went smoothly
- No rollback needed
```

---

## 🎓 Best Practices

### Do's ✅

- ✅ Deploy during low-traffic hours (2-4 AM BRT)
- ✅ Always create backups before migrations
- ✅ Test rollback procedure in staging
- ✅ Monitor for at least 30 min post-deploy
- ✅ Communicate proactively
- ✅ Use feature flags for gradual rollouts
- ✅ Tag releases in Git
- ✅ Document everything

### Don'ts ❌

- ❌ Deploy on Friday (hard to rollback on weekend)
- ❌ Deploy without approval
- ❌ Skip staging validation
- ❌ Deploy multiple features at once
- ❌ Ignore alerts during deploy
- ❌ Deploy without rollback plan
- ❌ Touch production DB manually
- ❌ Deploy when on-call is unavailable

---

**Last Review**: Janeiro 2025  
**Next Review**: Abril 2025  
**Owner**: DevOps Team