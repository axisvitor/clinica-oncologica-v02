# Railway Production Deployment Validation Checklist

**Version**: 2.0
**Last Updated**: 2025-10-06
**Status**: Ready for Production Validation

---

## 📋 Pre-Deployment Checklist

### 1. Firebase Configuration ✅

- [ ] **Firebase Project Created**
  - Firebase Console → Create/Select project
  - Project ID recorded: `_____________________`

- [ ] **Firebase Authentication Enabled**
  - Authentication → Sign-in method → Email/Password → Enabled
  - Test users created (admin, doctor, patient)

- [ ] **Firebase Service Account Created**
  - Project Settings → Service accounts → Generate new private key
  - Downloaded JSON credentials file
  - Private key extracted (PEM format)

- [ ] **Firebase Admin SDK Credentials**
  - `FIREBASE_PROJECT_ID`: ✅ Obtained
  - `FIREBASE_PRIVATE_KEY`: ✅ Obtained (PEM format with `\n` escaped)
  - `FIREBASE_CLIENT_EMAIL`: ✅ Obtained (ends with `.iam.gserviceaccount.com`)

### 2. Railway Backend Environment Variables ✅

Navigate to Railway → Backend Service → Variables:

**Firebase Authentication**:
```bash
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nMII...your-key...\n-----END PRIVATE KEY-----
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com
```

**Backend URLs**:
```bash
API_BASE_URL=https://backend-hormonia-production.up.railway.app
BACKEND_URL=https://backend-hormonia-production.up.railway.app
```

**CORS Configuration**:
```bash
ALLOWED_ORIGINS=["https://clinica-oncologica-v02-production.up.railway.app","https://interface-quiz-production.up.railway.app","http://localhost:5173"]
```

**Database** (PostgreSQL):
```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

**Redis** (if using):
```bash
REDIS_URL=redis://default:password@host:port
```

- [ ] All environment variables set in Railway
- [ ] No typos or extra spaces in variable names
- [ ] Values match Firebase Console
- [ ] CORS origins include production frontend URL

### 3. Railway Frontend Environment Variables ✅

Navigate to Railway → Frontend Service → Variables:

**Firebase Client Configuration**:
```bash
VITE_FIREBASE_API_KEY=AIzaSy...
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project
VITE_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789012
VITE_FIREBASE_APP_ID=1:123456789012:web:abc...
VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX
```

**Backend API URLs**:
```bash
VITE_API_BASE_URL=https://backend-hormonia-production.up.railway.app
VITE_API_URL=https://backend-hormonia-production.up.railway.app/api/v1
VITE_WS_URL=wss://backend-hormonia-production.up.railway.app/ws
```

**Feature Flags**:
```bash
VITE_USE_MOCK_AUTH=false
```

- [ ] All `VITE_FIREBASE_*` variables set (7 total)
- [ ] Backend URLs point to Railway backend service
- [ ] WebSocket URL uses `wss://` protocol
- [ ] Mock auth disabled in production

### 4. Database Setup ✅

- [ ] **PostgreSQL Database Created**
  - Railway → New → Database → PostgreSQL
  - Database provisioned and running

- [ ] **Database Migrations Applied**
  ```bash
  # Connect to Railway PostgreSQL
  psql $DATABASE_URL
  # Run migrations
  \i backend-hormonia/migrations/001_initial_schema.sql
  ```

- [ ] **User Records Created**
  - Execute SQL to insert admin/doctor/patient users
  - Firebase UIDs match Firebase Console

- [ ] **Database Connection Verified**
  ```bash
  curl https://backend-hormonia-production.up.railway.app/api/v1/health/detailed
  # Check database status: "connected": true
  ```

---

## 🚀 Deployment Validation Tests

### Phase 1: Backend Health Checks ✅

**Test 1.1: Basic Health Endpoint**
```bash
curl https://backend-hormonia-production.up.railway.app/test

Expected: {"status": "ok", "message": "Backend is running"}
```
- [ ] Status code: 200
- [ ] Response contains `"status": "ok"`
- [ ] Response time < 1 second

**Test 1.2: Detailed Health Check**
```bash
curl https://backend-hormonia-production.up.railway.app/api/v1/health/detailed

Expected: Detailed system status with database, Firebase, Redis
```
- [ ] Status code: 200
- [ ] Database status: connected
- [ ] Firebase: configured
- [ ] No critical errors in response

**Test 1.3: CORS Configuration Check**
```bash
curl https://backend-hormonia-production.up.railway.app/api/v1/health/cors-test \
  -H "Origin: https://clinica-oncologica-v02-production.up.railway.app"

Expected: CORS headers in response
```
- [ ] `Access-Control-Allow-Origin` header present
- [ ] Origin matches request origin
- [ ] `Access-Control-Allow-Credentials: true`

### Phase 2: CORS Validation ✅

**Test 2.1: Preflight OPTIONS Request**
```bash
curl -X OPTIONS \
  https://backend-hormonia-production.up.railway.app/api/v1/users/me \
  -H "Origin: https://clinica-oncologica-v02-production.up.railway.app" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization" \
  -v
```
- [ ] Status code: 200 or 204
- [ ] `Access-Control-Allow-Origin` header present
- [ ] `Access-Control-Allow-Methods` includes GET
- [ ] `Access-Control-Allow-Headers` includes Authorization
- [ ] No preflight errors

**Test 2.2: Actual CORS GET Request**
```bash
curl https://backend-hormonia-production.up.railway.app/api/v1/health \
  -H "Origin: https://clinica-oncologica-v02-production.up.railway.app"
```
- [ ] Status code: 200
- [ ] `Access-Control-Allow-Origin` header matches origin
- [ ] Response includes expected data

**Test 2.3: Forbidden Origin Rejection**
```bash
curl -X OPTIONS \
  https://backend-hormonia-production.up.railway.app/api/v1/users/me \
  -H "Origin: https://evil-site.com" \
  -H "Access-Control-Request-Method: GET"
```
- [ ] No `Access-Control-Allow-Origin` for disallowed origin
- [ ] Or origin header is `null` or omitted

### Phase 3: HTTPS & Mixed Content ✅

**Test 3.1: Backend Uses HTTPS**
```bash
curl -I https://backend-hormonia-production.up.railway.app/test
```
- [ ] Response from HTTPS (not HTTP)
- [ ] Valid SSL certificate
- [ ] No certificate warnings

**Test 3.2: Frontend Uses HTTPS**
```bash
curl -I https://clinica-oncologica-v02-production.up.railway.app
```
- [ ] Frontend served over HTTPS
- [ ] Valid SSL certificate
- [ ] Railway SSL auto-configured

**Test 3.3: No Mixed Content**
- [ ] Open browser DevTools → Console
- [ ] Navigate to frontend URL
- [ ] No "Mixed Content" warnings
- [ ] All resources loaded via HTTPS
- [ ] API calls use HTTPS backend URL

### Phase 4: Firebase Authentication ✅

**Test 4.1: Protected Endpoint Requires Auth**
```bash
curl https://backend-hormonia-production.up.railway.app/api/v1/users/me

Expected: 401 Unauthorized
```
- [ ] Status code: 401
- [ ] Error message: "Unauthorized" or similar
- [ ] `WWW-Authenticate: Bearer` header present

**Test 4.2: Invalid Token Rejected**
```bash
curl https://backend-hormonia-production.up.railway.app/api/v1/users/me \
  -H "Authorization: Bearer invalid-token"

Expected: 401 Unauthorized
```
- [ ] Status code: 401
- [ ] Clear error message
- [ ] No 500 server errors

**Test 4.3: Firebase Custom Claims (requires valid token)**
```bash
# Get Firebase token via frontend login
# Then:
curl https://backend-hormonia-production.up.railway.app/api/v1/users/me \
  -H "Authorization: Bearer <FIREBASE_TOKEN>"

Expected: 200 with user data including custom claims
```
- [ ] Status code: 200
- [ ] User data returned
- [ ] Custom claims present (role, permissions)
- [ ] No 401 errors with valid token

### Phase 5: WebSocket WSS Connections ✅

**Test 5.1: WebSocket Endpoint Exists**
```bash
# Try to access via HTTP (will fail but should not be 404)
curl https://backend-hormonia-production.up.railway.app/ws/appointments

Expected: 400 or 426 Upgrade Required (not 404)
```
- [ ] Not 404 Not Found
- [ ] Endpoint exists and expects WebSocket upgrade

**Test 5.2: WSS Connection Without Token Rejected**
- [ ] Open browser DevTools → Console
- [ ] Run: `new WebSocket("wss://backend-hormonia-production.up.railway.app/ws/appointments")`
- [ ] Expected: Connection rejected or 401 error
- [ ] Unauthenticated connections not allowed

**Test 5.3: WSS Connection With Token Succeeds**
- [ ] Login to frontend
- [ ] WebSocket automatically connects
- [ ] DevTools → Network → WS tab shows connection
- [ ] Connection uses `wss://` protocol
- [ ] Token included in connection
- [ ] Connection status: 101 Switching Protocols

### Phase 6: 401 Error Resolution ✅

**Test 6.1: No Race Condition 401 Errors**
- [ ] Clear browser cache (Ctrl+Shift+Delete)
- [ ] Open DevTools → Network tab
- [ ] Login to frontend
- [ ] Navigate to /dashboard
- [ ] **Verify**: No 401 errors on:
  - `/api/v1/users/me`
  - `/api/v1/auth/notifications`
  - `/api/v1/analytics/dashboard`
- [ ] All requests include `Authorization: Bearer <token>` header
- [ ] All protected API calls wait for authentication

**Test 6.2: Token Refresh Works**
- [ ] Stay logged in for > 30 minutes
- [ ] Make API call after 30 minutes
- [ ] Token automatically refreshes
- [ ] No 401 errors during refresh
- [ ] No gaps where both old and new tokens are invalid

**Test 6.3: Concurrent Requests No 401s**
- [ ] Load dashboard (triggers multiple API calls)
- [ ] DevTools → Network tab
- [ ] All concurrent requests succeed
- [ ] No intermittent 401 errors
- [ ] Consistent authentication state

---

## 🧪 Automated Test Execution

### Run E2E Test Suite

**Test 6.4: Firebase Custom Claims Tests**
```bash
cd tests
pytest tests/e2e/auth/test_firebase_custom_claims.py -v

Expected: All tests pass or skip (if integration env not set)
```
- [ ] Test suite runs without errors
- [ ] Unit tests pass
- [ ] Integration tests skip gracefully if no live token

**Test 6.5: HTTPS Mixed Content Tests**
```bash
pytest tests/e2e/auth/test_https_mixed_content.py -v

Expected: All HTTPS validation tests pass
```
- [ ] All endpoints use HTTPS
- [ ] No HTTP resources loaded
- [ ] WebSocket uses WSS

**Test 6.6: 401 Error Resolution Tests**
```bash
pytest tests/e2e/auth/test_401_error_resolution.py -v

Expected: Auth flow tests pass
```
- [ ] Protected endpoints reject missing tokens
- [ ] Malformed tokens handled gracefully
- [ ] Concurrent requests are thread-safe

**Test 6.7: WebSocket WSS Tests**
```bash
pytest tests/e2e/websocket/test_wss_authentication.py -v

Expected: WebSocket tests pass or skip
```
- [ ] WSS protocol validation passes
- [ ] Connection tests work (or skip if no token)

**Test 6.8: CORS Smoke Tests**
```bash
pytest tests/backend/test_cors_smoke.py -v --base-url https://backend-hormonia-production.up.railway.app

Expected: CORS configuration validated
```
- [ ] Allowed origins work
- [ ] Forbidden origins blocked
- [ ] Preflight requests succeed
- [ ] Headers/methods configured correctly

---

## 🌐 Manual Frontend Testing

### Test 7.1: Login Flow
- [ ] Navigate to production frontend
- [ ] Enter Firebase credentials
- [ ] Login succeeds
- [ ] Redirected to /dashboard
- [ ] No errors in browser console

### Test 7.2: Dashboard Loading
- [ ] Dashboard loads without errors
- [ ] No 401 errors in Network tab
- [ ] All widgets load data
- [ ] Real-time updates work

### Test 7.3: Protected Routes
- [ ] Try accessing /dashboard without login
- [ ] Should redirect to /login
- [ ] After login, can access /dashboard
- [ ] Logout works correctly

### Test 7.4: Role-Based Access
- [ ] Login as admin
- [ ] Can access admin pages
- [ ] Logout and login as doctor
- [ ] Doctor has appropriate access
- [ ] Patient role has restricted access

### Test 7.5: WebSocket Real-Time Updates
- [ ] Create appointment in one browser tab
- [ ] Another tab receives WebSocket notification
- [ ] Updates appear in real-time
- [ ] No connection drops

---

## 🔍 Production Monitoring

### Test 8.1: Railway Logs Check
- [ ] Railway → Backend Service → Logs
- [ ] No critical errors
- [ ] No unexpected 401 errors
- [ ] Firebase initialization successful
- [ ] Database connections stable

### Test 8.2: Performance Metrics
- [ ] Response times < 1 second
- [ ] WebSocket connections stable
- [ ] No memory leaks
- [ ] CPU usage normal

### Test 8.3: Error Tracking
- [ ] Check Railway metrics
- [ ] Error rate < 1%
- [ ] No 500 errors
- [ ] Only expected 401s (missing/invalid tokens)

---

## 🔄 Post-Deployment Checklist

### Immediate (First 15 minutes)
- [ ] All health checks passing
- [ ] Frontend accessible
- [ ] Login flow working
- [ ] No critical errors in logs

### Short-term (First Hour)
- [ ] Monitor error rates
- [ ] Check WebSocket stability
- [ ] Verify real-time updates
- [ ] User authentication working

### Long-term (First 24 Hours)
- [ ] No performance degradation
- [ ] Token refresh working
- [ ] No memory leaks
- [ ] All features functional

---

## 🆘 Troubleshooting Guide

### Issue: Firebase Not Configured
**Symptoms**: `"Firebase not configured"` in logs or frontend console

**Solutions**:
1. ✅ Verify all `FIREBASE_*` env vars set in Railway backend
2. ✅ Force redeploy: Railway → Backend → Deploy → Redeploy
3. ✅ Check variable spelling (exact match)
4. ✅ Wait for build to complete (2-3 minutes)

### Issue: 401 Errors on Dashboard
**Symptoms**: 401 errors on `/api/v1/users/me` after login

**Solutions**:
1. ✅ Clear browser cache
2. ✅ Verify latest frontend code deployed (commit bef9a2e)
3. ✅ Check `enabled` prop in useQuery hooks
4. ✅ Verify token is set before API calls

### Issue: CORS Errors
**Symptoms**: CORS policy errors in browser console

**Solutions**:
1. ✅ Verify frontend URL in `ALLOWED_ORIGINS`
2. ✅ Check exact URL match (including protocol)
3. ✅ Test preflight with curl
4. ✅ Verify CORS middleware configured

### Issue: WebSocket Won't Connect
**Symptoms**: WebSocket connection fails or drops

**Solutions**:
1. ✅ Verify WSS protocol (not WS)
2. ✅ Check token is included in connection
3. ✅ Verify Railway WebSocket support enabled
4. ✅ Check firewall/proxy settings

### Issue: Mixed Content Warnings
**Symptoms**: Browser shows mixed content warnings

**Solutions**:
1. ✅ Verify all URLs use HTTPS
2. ✅ Check `VITE_API_BASE_URL` uses HTTPS
3. ✅ Verify `VITE_WS_URL` uses WSS
4. ✅ No hardcoded HTTP URLs in code

---

## 📊 Success Criteria

### ✅ Deployment is Successful When:

1. **Health Checks**: All health endpoints return 200
2. **CORS**: Preflight and actual requests work
3. **HTTPS**: All connections use HTTPS/WSS
4. **Authentication**: Firebase tokens validate correctly
5. **Authorization**: Custom claims work for RBAC
6. **WebSocket**: WSS connections stable
7. **No 401 Errors**: Dashboard loads without auth errors
8. **Performance**: Response times < 1s, no errors
9. **Monitoring**: Logs show no critical errors
10. **Frontend**: Complete user flows work end-to-end

### 🎯 Key Performance Indicators (KPIs):

- **Uptime**: > 99.9%
- **Error Rate**: < 0.1%
- **Response Time**: < 500ms (p95)
- **WebSocket Uptime**: > 99%
- **Authentication Success**: > 99.5%

---

## 📝 Validation Sign-Off

**Backend Validation**:
- [ ] Health checks passing
- [ ] Firebase configured
- [ ] CORS working
- [ ] Database connected

**Frontend Validation**:
- [ ] Login flow works
- [ ] Dashboard loads
- [ ] No 401 errors
- [ ] WebSocket connected

**Security Validation**:
- [ ] HTTPS enforced
- [ ] Tokens validated
- [ ] CORS configured
- [ ] No mixed content

**Performance Validation**:
- [ ] Response times acceptable
- [ ] No memory leaks
- [ ] Logs clean
- [ ] Metrics normal

---

**Validated By**: `________________`
**Date**: `________________`
**Environment**: Production (Railway)
**Version**: Backend `______`, Frontend `______`

**Next Review**: 24 hours after deployment

---

## 📚 Related Documentation

- [Railway Firebase Auth Deployment](./RAILWAY_DEPLOY_FIREBASE_AUTH.md)
- [Frontend 401 Error Fix](./RAILWAY_FRONTEND_401_FIX.md)
- [CORS Final Review](../CORS_FINAL_REVIEW_REPORT.md)
- [E2E Tests](../../tests/e2e/auth/)
- [WebSocket Tests](../../tests/e2e/websocket/)
