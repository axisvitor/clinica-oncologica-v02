# Production Deployment Checklist

**Quick Reference Guide**
**Status:** 🟡 2 CRITICAL ISSUES - Fix Before Deploy

---

## ❌ CRITICAL - Must Fix Now

### 1. Redis SSL Configuration
**File:** `backend-hormonia/.env`

**Current:**
```bash
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none
```

**Required:**
```bash
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
```

**Impact:** Unencrypted Redis traffic exposes session tokens, cache data, and Celery tasks

---

### 2. Firebase Public Domain Blocking
**File:** `backend-hormonia/.env`

**Current:**
```bash
FIREBASE_BLOCK_PUBLIC_DOMAINS=false
```

**Required:**
```bash
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
```

**Impact:** Anyone with gmail.com/yahoo.com can register as a user

---

## ⚠️ WARNINGS - Recommended Fixes

### 3. Monitoring Placeholders
**Files:** `frontend-hormonia/.env`, `quiz-mensal-interface/.env`, `backend-hormonia/.env`

**Action:** Replace or remove these placeholders:
- `{{YOUR_SENTRY_DSN}}`
- `{{YOUR_ANALYTICS_ID}}`

---

### 4. WebSocket Endpoint Paths
**Frontend:** `/ws/connect`
**Nginx:** `/ws`

**Action:** Verify backend supports both paths or standardize

---

### 5. Health Endpoint Testing
**Action:** Run these tests before deploying:

```bash
# Backend
curl https://clinica-oncologica-v02-production.up.railway.app/health

# Frontend
curl https://frontend-production-18bb.up.railway.app/health

# Quiz
curl https://quiz-interface-production.up.railway.app/api/health
```

---

## ✅ Configuration Status

### Frontend Hormonia
- [x] Production API URL configured
- [x] Debug mode disabled
- [x] HTTPS enforced
- [x] Firebase configured
- [ ] Monitoring configured (optional)

### Quiz Interface
- [x] Production API URL configured
- [x] NODE_ENV=production
- [x] Telemetry disabled

### Backend Hormonia
- [x] ENVIRONMENT=production
- [x] DEBUG=false
- [x] Strong secret keys
- [x] Database configured
- [ ] **Redis SSL enabled** ⚠️
- [ ] **Public domains blocked** ⚠️
- [x] CORS configured
- [x] Quiz URL configured

---

## 🧪 Quick Test Commands

### After Fixing Issues, Run:

```bash
# 1. Verify Redis SSL
cd backend-hormonia
python -c "from app.config import settings; print(f'Redis SSL: {settings.REDIS_SSL}')"

# 2. Verify domain blocking
python -c "from app.config import settings; print(f'Block public domains: {settings.FIREBASE_BLOCK_PUBLIC_DOMAINS}')"

# 3. Test health endpoints
curl -s https://clinica-oncologica-v02-production.up.railway.app/health | jq .

# 4. Test CORS
curl -I -H "Origin: https://frontend-production-18bb.up.railway.app" \
  https://clinica-oncologica-v02-production.up.railway.app/api/v1/health

# 5. Test WebSocket
wscat -c wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```

---

## 📋 Deployment Sequence

1. **Fix Critical Issues** (Redis SSL + Domain Blocking)
2. **Commit Changes**
3. **Deploy Backend** (Railway auto-deploy)
4. **Test Health Endpoints**
5. **Deploy Frontend** (Railway auto-deploy)
6. **Deploy Quiz Interface** (Railway auto-deploy)
7. **Run Integration Tests**
8. **Monitor Logs** (first 30 minutes)

---

## 🚨 Emergency Rollback Plan

If issues occur:

1. **Check Railway logs:**
   ```bash
   railway logs --service backend-hormonia
   railway logs --service frontend-hormonia
   railway logs --service quiz-mensal-interface
   ```

2. **Rollback via Railway dashboard:**
   - Go to service → Deployments
   - Click previous working deployment
   - Click "Redeploy"

3. **Verify rollback:**
   ```bash
   curl https://clinica-oncologica-v02-production.up.railway.app/health
   ```

---

## 📊 Production Readiness Score

**Current:** 86% (68/79 checks passed)

**After Fixes:** 97% (76/79 checks passed)

**Remaining warnings:** Monitoring (optional)

---

**For full details, see:** `PRODUCTION_VALIDATION_REPORT.md`
