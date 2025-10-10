# Deployment Checklist
**Oncology Clinic Management System - Hormonia**

**Environment:** Production (Railway Platform)
**Deployment Date:** _____________
**Deployment Lead:** _____________

---

## 📋 Pre-Deployment Checklist

### 1. Code Preparation

- [ ] **Git Repository Clean**
  ```bash
  git status
  # Should show: "working tree clean"
  ```

- [ ] **Latest Code Pulled**
  ```bash
  git checkout main
  git pull origin main
  ```

- [ ] **Build Tests Pass**
  ```bash
  # Backend
  cd backend-hormonia
  python -m pytest tests/ -v

  # Frontend
  cd frontend-hormonia
  npm test
  npm run build
  ```

- [ ] **Linting Passes**
  ```bash
  # Backend
  cd backend-hormonia
  ruff check .

  # Frontend
  cd frontend-hormonia
  npm run lint
  ```

---

### 2. Database Preparation

- [ ] **Backup Current Database**
  ```bash
  # Railway dashboard: Create manual backup
  # OR via CLI
  pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql
  ```

- [ ] **Migrations Ready**
  ```bash
  cd backend-hormonia
  alembic current  # Check current version
  alembic history  # Review pending migrations
  ```

- [ ] **Test Migrations in Staging**
  ```bash
  # Run in staging environment first
  alembic upgrade head

  # Verify
  alembic current
  ```

- [ ] **GIN Indexes Applied**
  ```bash
  # Check if indexes exist
  psql $DATABASE_URL -f backend-hormonia/scripts/verify_gin_indexes.sql
  ```

---

### 3. Environment Variables

- [ ] **Backend Environment Variables Set**
  ```bash
  # Railway dashboard: Environment Variables section

  # Required:
  DATABASE_URL=postgresql+psycopg://...
  REDIS_URL=redis://...
  SECRET_KEY=<generate-new>
  CSRF_SECRET_KEY=<generate-new>
  FIREBASE_PROJECT_ID=...
  FIREBASE_PRIVATE_KEY=...
  FIREBASE_CLIENT_EMAIL=...

  # Optional:
  DEBUG=false
  ENVIRONMENT=production
  LOG_LEVEL=INFO
  CORS_ALLOWED_ORIGINS=https://app.hormonia.com
  ```

- [ ] **Frontend Environment Variables Set**
  ```bash
  # Railway dashboard: Environment Variables section

  # Required:
  VITE_API_BASE_URL=https://api.hormonia.com

  # Optional:
  VITE_WS_BASE_URL=wss://api.hormonia.com
  VITE_SENTRY_DSN=...
  VITE_ANALYTICS_TRACKING_ID=...
  ```

- [ ] **Secrets Generated Securely**
  ```bash
  # Generate new SECRET_KEY
  python -c 'import secrets; print(secrets.token_urlsafe(32))'

  # Generate new CSRF_SECRET_KEY
  python -c 'import secrets; print(secrets.token_urlsafe(32))'
  ```

- [ ] **Environment Variables Validated**
  ```bash
  # Backend validation
  cd backend-hormonia
  python -c "from app.config import get_settings; get_settings()"

  # Should pass without errors
  ```

---

### 4. Security Configuration

- [ ] **HTTPS Enforced**
  - Verify `SESSION_COOKIE_SECURE=True` in production
  - Check `CORS_ALLOWED_ORIGINS` uses HTTPS only
  - Confirm no HTTP fallback URLs in frontend config

- [ ] **CORS Configuration Validated**
  ```python
  # backend-hormonia/app/config.py
  CORS_ALLOWED_ORIGINS = [
      "https://app.hormonia.com",
      "https://hormonia.com"
  ]
  # No localhost, no wildcards
  ```

- [ ] **Security Headers Configured**
  - HSTS with 1-year max-age
  - CSP policy restrictive
  - X-Frame-Options: DENY
  - All headers in `app/middleware/security_headers.py`

- [ ] **Rate Limiting Active**
  - Redis-backed (not in-memory fallback)
  - Limits configured per endpoint
  - `/session` endpoint: 10 requests/min

- [ ] **CSRF Protection Enabled**
  - CSRF_SECRET_KEY set with high entropy
  - X-CSRF-Token required on POST/PUT/DELETE
  - Validation active in middleware

---

### 5. Performance Optimization

- [ ] **GIN Indexes Created**
  ```sql
  -- Verify indexes exist
  SELECT indexname FROM pg_indexes
  WHERE tablename IN ('users', 'patients', 'messages')
  AND indexname LIKE '%gin%';
  ```

- [ ] **Eager Loading Configured**
  ```python
  # Verify in repositories:
  # - app/repositories/flow.py
  # - app/repositories/alert.py
  # - app/repositories/quiz.py
  # - app/repositories/report.py
  ```

- [ ] **Cache Configuration Validated**
  ```bash
  # Test Redis connection
  redis-cli -u $REDIS_URL ping
  # Should return: PONG
  ```

- [ ] **Frontend Bundle Optimized**
  ```bash
  cd frontend-hormonia
  npm run build

  # Check dist/ size
  du -sh dist/
  # Should be ~2-3MB total, ~300-400KB main chunk
  ```

---

### 6. Monitoring Setup

- [ ] **Health Endpoints Active**
  ```bash
  curl https://api.hormonia.com/health/live
  # Should return: {"status":"alive"}

  curl https://api.hormonia.com/health/ready
  # Should return: {"status":"ready","dependencies":{...}}
  ```

- [ ] **Structured Logging Configured**
  ```python
  # Verify in app/core/lifespan.py
  from app.utils.structured_logger import configure_logging
  configure_logging(log_level="INFO")
  ```

- [ ] **Performance Metrics Middleware Active**
  ```python
  # Verify in app/core/middleware_setup.py
  from app.middleware.metrics import PerformanceMetricsMiddleware
  app.add_middleware(PerformanceMetricsMiddleware)
  ```

- [ ] **OpenTelemetry Configured (Optional)**
  ```bash
  # If using OTLP exporter
  export OTEL_EXPORTER_OTLP_ENDPOINT=...
  export OTEL_SERVICE_NAME=hormonia-backend
  ```

- [ ] **Sentry Configured (Optional)**
  ```bash
  # Frontend
  export VITE_SENTRY_DSN=...

  # Backend
  export SENTRY_DSN=...
  ```

---

### 7. Load Balancer Configuration (If Applicable)

- [ ] **Health Check Endpoint**
  ```yaml
  endpoint: /health/ready
  interval: 10s
  timeout: 5s
  healthy_threshold: 2
  unhealthy_threshold: 3
  ```

- [ ] **Session Affinity (If Using WebSocket)**
  ```yaml
  # Enable sticky sessions for WebSocket connections
  session_affinity: ip_hash
  ```

- [ ] **SSL/TLS Termination**
  - Certificate installed
  - Redirect HTTP → HTTPS
  - HSTS header set

---

### 8. Kubernetes Configuration (If Applicable)

- [ ] **Deployment YAML Updated**
  ```yaml
  # backend-deployment.yaml
  livenessProbe:
    httpGet:
      path: /health/live
      port: 8000
    initialDelaySeconds: 30
    periodSeconds: 10

  readinessProbe:
    httpGet:
      path: /health/ready
      port: 8000
    initialDelaySeconds: 10
    periodSeconds: 5
  ```

- [ ] **ConfigMaps/Secrets Created**
  ```bash
  kubectl create secret generic hormonia-secrets \
    --from-literal=database-url=$DATABASE_URL \
    --from-literal=secret-key=$SECRET_KEY
  ```

- [ ] **Resource Limits Set**
  ```yaml
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "1Gi"
      cpu: "1000m"
  ```

---

## 🚀 Deployment Steps

### Step 1: Deploy Backend (Railway)

1. **Push to Production Branch**
   ```bash
   git checkout main
   git push origin main
   ```

2. **Railway Auto-Deploy (Or Manual)**
   ```bash
   # Railway dashboard: Deployments section
   # OR via CLI
   railway up
   ```

3. **Wait for Build to Complete**
   - Monitor Railway dashboard
   - Check build logs for errors

4. **Run Database Migrations**
   ```bash
   # Railway dashboard: Run command
   alembic upgrade head

   # OR via CLI
   railway run alembic upgrade head
   ```

5. **Verify Health Endpoint**
   ```bash
   curl https://api.hormonia.com/health/ready

   # Should return:
   {
     "status": "ready",
     "dependencies": {
       "database": "healthy",
       "redis": "healthy",
       "firebase": "healthy"
     }
   }
   ```

### Step 2: Deploy Frontend (Railway)

1. **Push to Production Branch**
   ```bash
   git checkout main
   git push origin main
   ```

2. **Railway Auto-Deploy**
   - Build process runs automatically
   - `vite build --mode production`
   - Runtime config injected via `scripts/post-build-config.js`

3. **Wait for Deployment**
   - Monitor Railway dashboard
   - Check for build errors

4. **Verify Frontend Loads**
   ```bash
   curl https://app.hormonia.com/
   # Should return HTML with status 200
   ```

### Step 3: Smoke Testing

- [ ] **Test Login Flow**
  1. Navigate to https://app.hormonia.com/login
  2. Enter valid credentials
  3. Verify successful login
  4. Check session cookie set

- [ ] **Test Patient Creation**
  1. Navigate to patients page
  2. Create new patient
  3. Verify patient appears in list
  4. Check database entry

- [ ] **Test Message Sending**
  1. Select patient
  2. Send test message
  3. Verify message queued
  4. Check logs for delivery

- [ ] **Test Health Endpoints**
  ```bash
  # Liveness
  curl https://api.hormonia.com/health/live

  # Readiness
  curl https://api.hormonia.com/health/ready

  # Metrics
  curl https://api.hormonia.com/health/metrics

  # Performance
  curl https://api.hormonia.com/health/performance
  ```

---

## 📊 Post-Deployment Monitoring

### First Hour

- [ ] **Monitor Error Logs**
  ```bash
  # Railway dashboard: Logs section
  # Filter: level=ERROR
  ```

- [ ] **Check Response Times**
  ```bash
  curl -w "@curl-format.txt" https://api.hormonia.com/health/metrics

  # curl-format.txt:
  # time_total: %{time_total}s
  # Should be < 1s
  ```

- [ ] **Verify Cache Hit Rate**
  ```bash
  curl https://api.hormonia.com/health/performance
  # cache_hit_rate should be > 70%
  ```

- [ ] **Monitor Database Connections**
  ```sql
  SELECT count(*) FROM pg_stat_activity
  WHERE datname = 'hormonia';
  # Should be < 50% of pool_size (20)
  ```

### First 24 Hours

- [ ] **Daily Health Check**
  - Review error logs
  - Check performance metrics
  - Verify uptime (target: 99.9%)
  - Monitor memory usage

- [ ] **Performance Baseline**
  - Record P50, P95, P99 response times
  - Document cache hit rates
  - Note query counts per request
  - Baseline for future comparisons

- [ ] **Security Monitoring**
  - Failed authentication attempts
  - CSRF validation failures
  - Rate limiting triggers
  - Unusual traffic patterns

### First Week

- [ ] **Daily Standup Reviews**
  - Discuss any production issues
  - Review monitoring dashboards
  - Plan immediate fixes if needed

- [ ] **User Feedback Collection**
  - Monitor support tickets
  - Track user-reported issues
  - Collect performance feedback

- [ ] **Performance Optimization**
  - Analyze slow queries
  - Review cache effectiveness
  - Identify optimization opportunities

---

## 🛡️ Rollback Procedure

### When to Rollback

**Automatic Triggers:**
- Health check failures (3 consecutive)
- Error rate > 10%
- P95 response time > 5s

**Manual Triggers:**
- Critical security vulnerability
- Data corruption detected
- Performance degradation > 50%

### Rollback Steps

1. **Immediate Rollback (Railway)**
   ```bash
   # Railway dashboard: Revert to previous deployment
   # OR via CLI
   railway rollback
   ```

2. **Database Rollback (If Needed)**
   ```bash
   # Connect to database
   psql $DATABASE_URL

   # Rollback migration
   alembic downgrade -1
   ```

3. **Verify Rollback**
   ```bash
   # Check health
   curl https://api.hormonia.com/health/ready

   # Test critical flows
   # - User login
   # - Patient creation
   ```

4. **Communicate**
   - Notify team in Slack
   - Update status page
   - Document incident

5. **Post-Mortem**
   - Investigate root cause
   - Document lessons learned
   - Plan fix and re-deployment

---

## ✅ Post-Deployment Verification

### Checklist: All Systems Operational

- [ ] **Backend Health**
  - /health/live returns 200
  - /health/ready validates dependencies
  - /health/metrics shows healthy stats

- [ ] **Frontend Health**
  - Application loads without errors
  - Authentication works
  - API calls successful
  - WebSocket connects

- [ ] **Database Health**
  - Connections stable
  - Queries performant
  - No migration errors
  - Backups running

- [ ] **Cache Health**
  - Redis responsive
  - Hit rate > 70%
  - No connection errors

- [ ] **Security Active**
  - HTTPS enforced
  - httpOnly cookies set
  - CSRF protection working
  - Rate limiting functional

- [ ] **Monitoring Active**
  - Logs flowing
  - Metrics collected
  - Alerts configured
  - Dashboards updated

---

## 📞 Emergency Contacts

### Escalation Path

**Level 1: Development Team**
- Check documentation: `docs/`
- Review logs: Railway dashboard
- Consult health endpoints

**Level 2: DevOps Team**
- Infrastructure issues
- Deployment problems
- Database/Redis issues

**Level 3: Architecture Team**
- Critical system failures
- Security incidents
- Data corruption

### Support Resources

- **Documentation:** `docs/integration/`
- **Architecture:** `docs/architecture/`
- **Security:** `docs/security/`
- **Monitoring:** `backend-hormonia/docs/monitoring/`
- **Runbooks:** `docs/devops/`

---

## 🎯 Success Criteria

### Deployment is Successful When:

✅ **All health checks pass**
✅ **Critical flows work** (login, patient management, messaging)
✅ **Performance targets met** (P95 < 1s, error rate < 1%)
✅ **Security validated** (HTTPS, cookies, CSRF)
✅ **Monitoring active** (logs, metrics, alerts)
✅ **No critical errors** in first 24 hours

---

**Deployment Status:** _______________
**Deployed By:** _______________
**Deployment Time:** _______________
**Next Review:** _______________ (2 weeks)

---

*This checklist is part of the deployment process for the Hormonia system. Update as deployment procedures evolve.*
