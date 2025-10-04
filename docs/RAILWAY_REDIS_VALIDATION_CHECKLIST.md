# Railway Redis Validation Checklist
**Project:** Backend Hormonia
**Environment:** Production (Railway)
**Date:** 2025-10-04

---

## 🔴 CRITICAL FIXES (DO BEFORE DEPLOY)

### 1. SSL Certificate Validation
**Priority:** CRITICAL
**Time:** 5 minutes

- [ ] Update `.env` production file:
  ```bash
  # Change from:
  REDIS_SSL_CERT_REQS="none"

  # Change to:
  REDIS_SSL_CERT_REQS="required"
  ```

- [ ] Update Railway environment variables:
  - Navigate to: Railway Project → backend-hormonia service → Variables
  - Set: `REDIS_SSL_CERT_REQS=required`

- [ ] Verify Redis Cloud certificate is valid:
  ```bash
  openssl s_client -connect redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149 -tls1_2
  ```

**Expected Result:** Connection succeeds with valid certificate chain

---

### 2. Update redis_manager.py SSL Logic
**Priority:** HIGH
**Time:** 15 minutes

- [ ] Edit `backend-hormonia/app/core/redis_manager.py`
- [ ] Update lines 96-112 (async client creation):
  ```python
  # Read certificate requirements from settings
  cert_reqs_str = getattr(settings, 'REDIS_SSL_CERT_REQS', 'required')
  cert_reqs = ssl.CERT_REQUIRED if cert_reqs_str == 'required' else ssl.CERT_NONE

  connection_kwargs.update({
      'ssl': True,
      'ssl_cert_reqs': cert_reqs,
      'ssl_check_hostname': (cert_reqs == ssl.CERT_REQUIRED)
  })
  ```

- [ ] Update lines 146-162 (sync client creation) with same logic
- [ ] Add logging:
  ```python
  logger.info(f"Redis SSL: cert_reqs={cert_reqs_str}, hostname_check={cert_reqs == ssl.CERT_REQUIRED}")
  ```

- [ ] Commit changes:
  ```bash
  git add backend-hormonia/app/core/redis_manager.py
  git commit -m "fix(redis): respect REDIS_SSL_CERT_REQS setting for security"
  ```

**Expected Result:** Redis connections respect SSL certificate validation setting

---

## 🟡 RECOMMENDED IMPROVEMENTS (POST-DEPLOY)

### 3. Configure Redis Eviction Policy
**Priority:** MEDIUM
**Time:** 10 minutes

- [ ] Log into Redis Cloud dashboard
- [ ] Navigate to: Database → Configuration → Advanced
- [ ] Set eviction policy:
  ```
  maxmemory-policy: allkeys-lru
  maxmemory: 256mb (or based on your plan)
  maxmemory-samples: 5
  ```

- [ ] Save and restart Redis (if required)

**Expected Result:** Redis automatically evicts least recently used keys when memory limit reached

---

### 4. Update config.py Default for Celery Backend
**Priority:** LOW
**Time:** 5 minutes

- [ ] Edit `backend-hormonia/app/config.py`
- [ ] Line 184: Update default DB for consistency:
  ```python
  # Change from:
  CELERY_RESULT_BACKEND: str = Field(default="rediss://localhost:6379/1")

  # Change to (match actual usage):
  CELERY_RESULT_BACKEND: str = Field(default="rediss://localhost:6379/0")
  ```

- [ ] Add comment:
  ```python
  # Both broker and backend use DB 0 (isolated from cache on DB 1)
  ```

**Expected Result:** Default config matches production usage (DB 0 for Celery, DB 1 for cache)

---

### 5. Add Circuit Breaker Pattern
**Priority:** MEDIUM
**Time:** 30 minutes

- [ ] Create `backend-hormonia/app/core/redis_circuit_breaker.py` (see full implementation in main review)
- [ ] Integrate into `redis_manager.py`:
  ```python
  from app.core.redis_circuit_breaker import RedisCircuitBreaker

  class RedisManager:
      def __init__(self, db_number: Optional[int] = None):
          # ... existing code ...
          self.circuit_breaker = RedisCircuitBreaker(
              failure_threshold=5,
              timeout_seconds=60
          )
  ```

- [ ] Wrap client creation:
  ```python
  async def get_async_client(self) -> redis_async.Redis:
      if self._async_client is None:
          await self.circuit_breaker.call_async(self._create_async_client)
      return self._async_client
  ```

**Expected Result:** Redis failures trigger circuit breaker, preventing cascading failures

---

## 🧪 PRE-DEPLOYMENT TESTING

### Local Testing (Before Railway Deploy)

- [ ] **Test 1: Redis Connection with SSL Validation**
  ```bash
  # Start backend locally with updated .env
  cd backend-hormonia
  python -m uvicorn app.main:app --reload

  # Check logs for:
  # ✅ "Async Redis client connected successfully"
  # ✅ "Redis SSL: cert_reqs=required, hostname_check=True"
  ```

- [ ] **Test 2: Rate Limiting Functionality**
  ```bash
  # Test login endpoint (should use Redis)
  for i in {1..6}; do
    curl -X POST http://localhost:8000/api/v1/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email":"test@test.com","password":"wrong"}'
  done

  # Expected: 6th request returns HTTP 429 (rate limited)
  ```

- [ ] **Test 3: Celery Task Execution**
  ```bash
  # Start Celery worker
  celery -A app.celery_app worker --loglevel=info

  # Trigger a task via API or console
  # Verify task executes and result is stored in Redis
  ```

- [ ] **Test 4: Health Check Endpoint**
  ```bash
  curl http://localhost:8000/api/health

  # Expected response includes:
  # {
  #   "redis": {
  #     "status": "healthy",
  #     "async_ping": true,
  #     "sync_ping": true
  #   }
  # }
  ```

---

## 🚀 RAILWAY DEPLOYMENT STEPS

### Step 1: Update Environment Variables

- [ ] Log into Railway dashboard
- [ ] Navigate to: backend-hormonia service → Variables
- [ ] Update/verify variables:
  ```bash
  REDIS_SSL_CERT_REQS=required          # ← CHANGE THIS
  REDIS_SSL=true                         # ← Verify
  REDIS_URL=redis://default:PASSWORD@HOST:PORT  # ← Verify
  REDIS_ENABLE_DB_ISOLATION=true        # ← Verify
  REDIS_CACHE_DB=1                      # ← Verify
  REDIS_BROKER_DB=0                     # ← Verify
  REDIS_MAX_CONNECTIONS=25              # ← Verify
  REDIS_SOCKET_TIMEOUT=10.0             # ← Verify
  ```

- [ ] Save changes (Railway will auto-redeploy)

---

### Step 2: Deploy Code Changes

- [ ] Commit all changes:
  ```bash
  git add .
  git commit -m "fix(redis): implement SSL cert validation and security improvements"
  git push origin main
  ```

- [ ] Railway auto-deploys from main branch
- [ ] Monitor build logs for errors

---

### Step 3: Monitor Deployment

- [ ] Watch Railway deployment logs:
  - Look for: ✅ "Async Redis client connected successfully"
  - Look for: ✅ "Redis SSL: cert_reqs=required"
  - Look for: ❌ NO SSL errors or connection failures

- [ ] Check service health:
  ```bash
  curl https://your-backend.railway.app/api/health
  ```

- [ ] Verify Redis metrics in Railway dashboard:
  - Connected clients: should be 1-5 initially
  - Memory usage: should be <50MB initially
  - Commands/sec: varies based on traffic

---

## 🔍 POST-DEPLOYMENT VALIDATION

### Functional Tests (On Railway Production)

- [ ] **Test 1: Authentication with Rate Limiting**
  ```bash
  # Test login endpoint (should hit Redis for rate limiting)
  curl -X POST https://your-backend.railway.app/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@test.com","password":"yourpassword"}'

  # Expected: HTTP 200 (success) or 401 (invalid creds)
  # NOT 500 (server error) or 503 (Redis unavailable)
  ```

- [ ] **Test 2: Rate Limit Enforcement**
  ```bash
  # Trigger rate limit (6+ failed logins in 1 minute)
  for i in {1..7}; do
    curl -X POST https://your-backend.railway.app/api/v1/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email":"test@test.com","password":"wrong"}'
    sleep 1
  done

  # Expected: 7th request returns HTTP 429 with:
  # {"error":"too_many_requests","message":"Muitas tentativas..."}
  ```

- [ ] **Test 3: Cache Functionality**
  ```bash
  # Login twice with valid credentials
  # First request: slow (DB query)
  # Second request: fast (Redis cache)

  curl -w "\nTime: %{time_total}s\n" \
    -X POST https://your-backend.railway.app/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@test.com","password":"yourpassword"}'

  # Expected: Second request significantly faster (<100ms)
  ```

- [ ] **Test 4: Celery Task Processing**
  ```bash
  # Trigger async task (e.g., send email, process flow)
  # Verify task completes successfully
  # Check Celery logs in Railway
  ```

---

### Performance Validation

- [ ] **Redis Connection Pool**
  - Railway Redis dashboard → Connections
  - Expected: 5-25 concurrent connections (varies by traffic)
  - Alert if: >40 connections (may need to increase pool)

- [ ] **Memory Usage**
  - Railway Redis dashboard → Memory
  - Expected: <100MB for typical usage
  - Alert if: >200MB (may need eviction policy or larger plan)

- [ ] **Cache Hit Rate**
  - Check application logs or monitoring
  - Expected: >50% hit rate for user data
  - Alert if: <30% (cache TTL may be too short)

- [ ] **Response Times**
  - Monitor API endpoint response times
  - Expected: <200ms for cached requests
  - Alert if: >500ms consistently (Redis latency issue)

---

### Security Validation

- [ ] **SSL/TLS Certificate**
  ```bash
  # Verify SSL connection from Railway container
  # (exec into Railway container or check logs)

  # Expected in logs:
  # "Redis SSL: cert_reqs=required, hostname_check=True"
  ```

- [ ] **No Unencrypted Connections**
  ```bash
  # Check Railway logs for Redis connection strings
  # Ensure no "redis://" without SSL
  grep -i "redis://" /path/to/logs

  # Expected: All connections use SSL
  ```

- [ ] **Rate Limiting Active**
  ```bash
  # Verify rate limiting prevents abuse
  # Already tested in Functional Tests above
  ```

- [ ] **No Credentials in Logs**
  ```bash
  # Search Railway logs for password leakage
  grep -i "password\|secret\|key" /path/to/logs

  # Expected: No plain-text credentials (only masked URLs)
  ```

---

## 📊 MONITORING SETUP

### Add Railway Metrics

- [ ] Create Railway monitoring dashboard with:
  ```
  ┌─ Redis Health ────────────────────────┐
  │ • Connected Clients: 15 / 25 max      │
  │ • Memory Used: 85 MB / 256 MB         │
  │ • Commands/sec: 120                   │
  │ • Evicted Keys: 5 (last 1h)           │
  └───────────────────────────────────────┘

  ┌─ Application Metrics ─────────────────┐
  │ • Cache Hit Rate: 65%                 │
  │ • Rate Limits Hit: 12 (last 1h)       │
  │ • Celery Queue Length: 3 tasks        │
  │ • Redis Errors: 0 (last 24h)          │
  └───────────────────────────────────────┘
  ```

### Set Up Alerts

- [ ] **Redis Connection Failures**
  - Trigger: 5+ connection errors in 5 minutes
  - Action: Alert DevOps team, check Redis Cloud status

- [ ] **Memory Threshold**
  - Trigger: Memory usage >200MB
  - Action: Review cache TTL, consider larger plan

- [ ] **Rate Limit Spike**
  - Trigger: >100 rate limit hits per minute
  - Action: Investigate potential attack, review IP patterns

- [ ] **Celery Queue Backlog**
  - Trigger: Queue length >50 tasks for >5 minutes
  - Action: Scale Celery workers, investigate task failures

---

## 🆘 ROLLBACK PLAN (If Issues Occur)

### Immediate Rollback Steps

1. **Revert Environment Variable:**
   ```bash
   # In Railway dashboard, change back to:
   REDIS_SSL_CERT_REQS=none
   ```

2. **Redeploy Previous Version:**
   ```bash
   # Railway → Deployments → Select previous successful deploy → Redeploy
   ```

3. **Monitor Recovery:**
   ```bash
   # Check health endpoint returns to normal
   curl https://your-backend.railway.app/api/health
   ```

### Troubleshooting Common Issues

**Issue 1: SSL Certificate Validation Fails**
```
Error: [SSL: CERTIFICATE_VERIFY_FAILED]
```
**Solution:**
- Verify Redis Cloud certificate is valid (not self-signed)
- Check Railway can reach Redis Cloud host
- Temporarily set `REDIS_SSL_CERT_REQS=none` to unblock, investigate cert issue

**Issue 2: Connection Timeout**
```
Error: TimeoutError: [Errno 110] Connection timed out
```
**Solution:**
- Check Redis Cloud status page
- Verify REDIS_URL is correct
- Increase REDIS_SOCKET_TIMEOUT to 30.0

**Issue 3: Too Many Connections**
```
Error: ConnectionError: max number of clients reached
```
**Solution:**
- Increase REDIS_MAX_CONNECTIONS to 50
- Check for connection leaks (missing cleanup)
- Upgrade Redis Cloud plan for more connections

---

## ✅ FINAL VALIDATION CHECKLIST

### Before Marking Complete

- [ ] All critical fixes applied
- [ ] Local testing passed (4/4 tests)
- [ ] Railway deployment successful
- [ ] Post-deployment tests passed (4/4 tests)
- [ ] Performance metrics normal
- [ ] Security validation passed
- [ ] Monitoring dashboard configured
- [ ] Alert rules active
- [ ] Documentation updated
- [ ] Team notified of changes

### Sign-Off

- **Deployed By:** _______________
- **Deployment Date:** _______________
- **Railway Deployment ID:** _______________
- **Validation Completed:** _______________
- **Production Ready:** [ ] YES [ ] NO

---

## 📝 NOTES & OBSERVATIONS

**Deployment Notes:**
```
[Record any issues encountered, solutions applied, or observations during deployment]
```

**Performance Baseline:**
```
Before:
- Cache hit rate: ___%
- Avg response time: ___ms
- Redis memory: ___MB

After:
- Cache hit rate: ___%
- Avg response time: ___ms
- Redis memory: ___MB
```

**Next Steps:**
```
1. Monitor for 24 hours
2. Implement circuit breaker (if not done)
3. Configure Redis eviction policy
4. Schedule follow-up review in 1 week
```

---

**Reference Documents:**
- Main Review: `docs/REDIS_CONFIGURATION_REVIEW.md`
- Railway Deployment Guide: `docs/deployment/RAILWAY_DEPLOYMENT_GUIDE.md`
- Rate Limiting Docs: `backend-hormonia/docs/RATE_LIMITING.md`
