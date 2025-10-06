# Manual Testing Procedures for Railway Production

**Purpose**: Step-by-step manual testing guide for validating Railway deployment
**Audience**: QA Engineers, DevOps, Developers
**Environment**: Production (Railway)
**Estimated Time**: 2-3 hours for complete validation

---

## 🎯 Testing Objectives

1. ✅ Verify all backend services are healthy and operational
2. ✅ Validate HTTPS/WSS security and no mixed content warnings
3. ✅ Confirm Firebase authentication works end-to-end
4. ✅ Ensure CORS configuration allows frontend-backend communication
5. ✅ Test WebSocket real-time features
6. ✅ Validate no 401 race condition errors on dashboard
7. ✅ Verify custom claims authorization works

---

## 📋 Pre-Testing Setup

### Required Tools
- [ ] Modern web browser (Chrome, Firefox, or Edge)
- [ ] Browser DevTools knowledge
- [ ] `curl` command-line tool
- [ ] Text editor for recording results
- [ ] Railway dashboard access
- [ ] Firebase Console access

### Test Environment URLs
```bash
BACKEND_URL=https://backend-hormonia-production.up.railway.app
FRONTEND_URL=https://clinica-oncologica-v02-production.up.railway.app
WS_URL=wss://backend-hormonia-production.up.railway.app/ws
```

### Test Credentials
Prepare test accounts:
- Admin user (email/password)
- Doctor user (email/password)
- Patient user (email/password)

---

## 🧪 Manual Test Suite

### Test Suite 1: Backend Health Validation (15 minutes)

#### Test 1.1: Basic Health Endpoint
**Objective**: Verify backend is running and accessible

**Steps**:
1. Open terminal/command prompt
2. Execute:
   ```bash
   curl https://backend-hormonia-production.up.railway.app/test
   ```
3. Record response

**Expected Result**:
```json
{
  "status": "ok",
  "message": "Backend is running"
}
```

**Pass Criteria**:
- [ ] HTTP status code: 200
- [ ] Response time < 2 seconds
- [ ] JSON response contains `"status": "ok"`

**If Failed**:
- Check Railway backend service status
- Verify deployment completed successfully
- Check Railway logs for errors

---

#### Test 1.2: Detailed Health Check
**Objective**: Verify all backend components are healthy

**Steps**:
1. Execute:
   ```bash
   curl https://backend-hormonia-production.up.railway.app/api/v1/health/detailed
   ```
2. Examine response for:
   - Database status
   - Firebase configuration
   - Redis status (if applicable)

**Expected Result**:
```json
{
  "status": "healthy",
  "components": {
    "database": "connected",
    "firebase": "configured",
    "redis": "connected"
  },
  "timestamp": "2025-10-06T..."
}
```

**Pass Criteria**:
- [ ] HTTP status: 200
- [ ] Database: connected
- [ ] Firebase: configured
- [ ] No error messages

**If Failed**:
- Check DATABASE_URL in Railway
- Verify Firebase env vars set
- Check connection strings

---

### Test Suite 2: HTTPS & Security Validation (20 minutes)

#### Test 2.1: HTTPS Backend Verification
**Objective**: Ensure backend serves only HTTPS

**Steps**:
1. Open browser
2. Navigate to: `https://backend-hormonia-production.up.railway.app/test`
3. Click padlock icon in address bar
4. View certificate details

**Pass Criteria**:
- [ ] URL shows `https://` (not `http://`)
- [ ] Padlock icon is secure (not warning)
- [ ] Certificate is valid (issued by Let's Encrypt/Railway)
- [ ] Certificate not expired
- [ ] No security warnings

**If Failed**:
- Railway should auto-configure SSL
- Check Railway service settings
- Verify custom domain SSL (if applicable)

---

#### Test 2.2: HTTPS Frontend Verification
**Objective**: Ensure frontend serves only HTTPS

**Steps**:
1. Navigate to: `https://clinica-oncologica-v02-production.up.railway.app`
2. Check certificate
3. Open DevTools (F12) → Console

**Pass Criteria**:
- [ ] URL shows `https://`
- [ ] Valid SSL certificate
- [ ] No certificate warnings
- [ ] No "Not Secure" warnings

---

#### Test 2.3: Mixed Content Warnings Check
**Objective**: Verify no HTTP resources loaded on HTTPS page

**Steps**:
1. Stay on frontend page with DevTools open
2. Go to Console tab
3. Look for mixed content warnings (yellow/red)
4. Check Network tab → filter by "http:" (should be empty)

**Expected Result**: No mixed content warnings

**Pass Criteria**:
- [ ] Console: No "Mixed Content" warnings
- [ ] Console: No "blocked loading mixed active content" errors
- [ ] Network tab: All requests use HTTPS or WSS
- [ ] No insecure resources loaded

**Common Mixed Content Issues**:
- ❌ `http://` in `VITE_API_BASE_URL`
- ❌ Hardcoded HTTP URLs in code
- ❌ Third-party HTTP scripts
- ❌ HTTP image sources

---

### Test Suite 3: CORS Validation (25 minutes)

#### Test 3.1: CORS Preflight Request
**Objective**: Verify CORS preflight OPTIONS requests work

**Steps**:
1. Execute in terminal:
   ```bash
   curl -X OPTIONS \
     https://backend-hormonia-production.up.railway.app/api/v1/users/me \
     -H "Origin: https://clinica-oncologica-v02-production.up.railway.app" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: Authorization" \
     -v
   ```
2. Examine response headers

**Expected Headers**:
```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: https://clinica-oncologica-v02-production.up.railway.app
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 600
```

**Pass Criteria**:
- [ ] Status: 200 or 204
- [ ] `Access-Control-Allow-Origin` matches request origin
- [ ] `Access-Control-Allow-Methods` includes GET
- [ ] `Access-Control-Allow-Headers` includes Authorization
- [ ] `Access-Control-Allow-Credentials: true`

**If Failed**:
- Check `ALLOWED_ORIGINS` in backend env vars
- Verify frontend URL exactly matches (including protocol)
- Check CORS middleware configuration

---

#### Test 3.2: CORS Actual Request
**Objective**: Verify actual requests include CORS headers

**Steps**:
1. Execute:
   ```bash
   curl https://backend-hormonia-production.up.railway.app/api/v1/health \
     -H "Origin: https://clinica-oncologica-v02-production.up.railway.app" \
     -v
   ```
2. Check response headers

**Expected Headers**:
```
Access-Control-Allow-Origin: https://clinica-oncologica-v02-production.up.railway.app
Access-Control-Allow-Credentials: true
```

**Pass Criteria**:
- [ ] Status: 200
- [ ] `Access-Control-Allow-Origin` present and correct
- [ ] Response data returned successfully

---

#### Test 3.3: Browser CORS Validation
**Objective**: Verify browser can make CORS requests

**Steps**:
1. Open frontend in browser: `https://clinica-oncologica-v02-production.up.railway.app`
2. Open DevTools (F12) → Console
3. Execute JavaScript:
   ```javascript
   fetch('https://backend-hormonia-production.up.railway.app/api/v1/health')
     .then(r => r.json())
     .then(console.log)
     .catch(console.error)
   ```
4. Observe result

**Expected Result**: Health data logged, no CORS errors

**Pass Criteria**:
- [ ] No CORS policy errors in console
- [ ] Response data logged successfully
- [ ] No "blocked by CORS policy" messages

**If Failed**:
- This is critical - frontend cannot communicate with backend
- Verify CORS configuration immediately
- Check `ALLOWED_ORIGINS` includes frontend URL

---

### Test Suite 4: Firebase Authentication (40 minutes)

#### Test 4.1: Login Flow Validation
**Objective**: Complete login flow works end-to-end

**Steps**:
1. Navigate to frontend: `https://clinica-oncologica-v02-production.up.railway.app/login`
2. Open DevTools → Network tab
3. Enter test user credentials (admin email/password)
4. Click "Login"
5. Observe network requests

**Expected Behavior**:
1. Firebase Auth API call succeeds
2. Token obtained from Firebase
3. Redirect to `/dashboard`
4. Dashboard loads without errors

**Pass Criteria**:
- [ ] Login succeeds (no error messages)
- [ ] Token obtained from Firebase (check Network tab)
- [ ] Redirect to `/dashboard` happens
- [ ] No errors in Console tab
- [ ] No 401 errors in Network tab

**Console Logs to Verify**:
```
[FirebaseClient] Firebase initialized successfully with project: your-project
[AuthContext] Using Firebase authentication
[AuthContext] Firebase user signed in: admin@example.com
[AuthContext] Setting auth token for API client
```

**If Failed**:
- Verify Firebase credentials in Railway frontend vars
- Check Firebase Authentication is enabled
- Verify user exists in Firebase Console
- Check browser console for detailed error

---

#### Test 4.2: Protected Endpoint Access
**Objective**: Authenticated user can access protected API endpoints

**Steps**:
1. Stay logged in from Test 4.1
2. Keep DevTools → Network tab open
3. Navigate to `/dashboard`
4. Look for API call to `/api/v1/users/me`

**Expected Behavior**:
```
GET /api/v1/users/me
Request Headers:
  Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Response: 200 OK
{
  "id": "...",
  "email": "admin@example.com",
  "role": "admin",
  "permissions": [...]
}
```

**Pass Criteria**:
- [ ] Request includes `Authorization: Bearer <token>` header
- [ ] Response status: 200 (not 401)
- [ ] User data returned with role and permissions
- [ ] Custom claims visible in response

**If Failed**:
- Check if token is being set (look for `setAuthToken` call in console)
- Verify backend Firebase Admin SDK configured
- Check FIREBASE_* env vars in backend

---

#### Test 4.3: Token Without Auth Rejected
**Objective**: Requests without token are rejected

**Steps**:
1. Open new incognito/private browser window
2. Open DevTools → Console
3. Execute:
   ```javascript
   fetch('https://backend-hormonia-production.up.railway.app/api/v1/users/me')
     .then(r => r.json())
     .then(console.log)
     .catch(console.error)
   ```

**Expected Result**: 401 Unauthorized error

**Pass Criteria**:
- [ ] Response status: 401
- [ ] Error message: "Unauthorized" or "Missing token"
- [ ] No user data returned
- [ ] Protected endpoint is secure

---

#### Test 4.4: Firebase Custom Claims Validation
**Objective**: Custom claims are present and used for authorization

**Steps**:
1. Login as admin user
2. Open DevTools → Console
3. Check Network tab → Find `/api/v1/users/me` response
4. Examine response JSON

**Expected Response**:
```json
{
  "id": "...",
  "email": "admin@example.com",
  "role": "admin",
  "permissions": ["all"],
  "metadata": {
    "firebase_uid": "...",
    "custom_claims": {
      "role": "admin",
      "department": "administration"
    }
  }
}
```

**Pass Criteria**:
- [ ] `role` field present
- [ ] `permissions` array present
- [ ] `metadata.custom_claims` exists
- [ ] Custom claims match user's role

**If Failed**:
- Run custom claims script: `python backend-hormonia/scripts/fix_firebase_custom_claims.py`
- Verify script execution succeeded
- Check Firebase Console → Users → Custom Claims

---

### Test Suite 5: Dashboard 401 Error Resolution (30 minutes)

#### Test 5.1: No Race Condition 401 Errors
**Objective**: Dashboard loads without premature 401 errors

**Steps**:
1. **IMPORTANT**: Clear browser cache completely:
   - Press Ctrl+Shift+Delete (Windows) or Cmd+Shift+Delete (Mac)
   - Select "All time" / "Everything"
   - Check "Cached images and files"
   - Click "Clear data"
2. Close and reopen browser
3. Open DevTools → Network tab
4. Navigate to: `https://clinica-oncologica-v02-production.up.railway.app/login`
5. Login with credentials
6. Carefully watch Network tab during dashboard load

**Expected Behavior**:
- `/api/v1/users/me` → Status: 200 ✅
- `/api/v1/auth/notifications` → Status: 200 ✅
- `/api/v1/analytics/dashboard` → Status: 200 ✅
- All requests have `Authorization: Bearer ...` header

**Pass Criteria**:
- [ ] NO 401 errors on dashboard load
- [ ] All API requests include Authorization header
- [ ] All API requests return 200 (or 204)
- [ ] Dashboard widgets load data successfully
- [ ] No red errors in Console tab

**If Test Fails (401 errors appear)**:
- ❌ **Critical Bug**: Race condition still exists
- Check frontend code has latest fix (commit bef9a2e)
- Verify `enabled` prop in useQuery hooks
- Check apiClient.setAuthToken() is called before queries

**Success Indicators**:
```
Console logs:
  [AuthContext] User authenticated: admin@example.com
  [AuthContext] Setting auth token for API client  ← This MUST happen first
  [QueryClient] Fetching /api/v1/users/me  ← This happens after token set
```

---

#### Test 5.2: Concurrent API Requests
**Objective**: Multiple simultaneous API calls don't cause race conditions

**Steps**:
1. Stay logged in
2. Keep DevTools → Network tab open
3. Click "Clear" to clear network log
4. Navigate to a complex page (e.g., `/dashboard`)
5. Count how many API requests fire simultaneously
6. Verify all have Authorization header

**Expected Behavior**:
- Multiple API calls fire at once (normal)
- ALL requests include `Authorization: Bearer ...`
- ALL requests return 200 (no 401s)
- No intermittent failures

**Pass Criteria**:
- [ ] 5+ concurrent API requests all succeed
- [ ] All have Authorization header
- [ ] No 401 responses
- [ ] Consistent authentication state

---

#### Test 5.3: Token Refresh Test
**Objective**: Token automatically refreshes without 401 errors

**Steps**:
1. Login to application
2. Stay on dashboard for 35+ minutes (Firebase tokens expire ~1 hour)
3. After 35 minutes, click a link or refresh data
4. Watch Network tab for token refresh

**Expected Behavior**:
- Token automatically refreshes via Firebase
- No 401 errors during refresh
- Seamless user experience (no logout)

**Pass Criteria**:
- [ ] No logout after 35+ minutes
- [ ] API calls continue to work
- [ ] No 401 errors
- [ ] Token refresh is invisible to user

**Note**: This is a long test - can be run during other testing

---

### Test Suite 6: WebSocket WSS Validation (25 minutes)

#### Test 6.1: WebSocket Connection Establishment
**Objective**: WebSocket connects successfully with authentication

**Steps**:
1. Login to frontend
2. Open DevTools → Network tab
3. Click "WS" filter (to show only WebSocket connections)
4. Navigate to a page that uses WebSockets (e.g., real-time appointments)
5. Look for WebSocket connection

**Expected Behavior**:
```
Name: ws/appointments?token=eyJ...
Status: 101 Switching Protocols
Type: websocket
```

**Pass Criteria**:
- [ ] WebSocket connection appears in WS tab
- [ ] URL starts with `wss://` (not `ws://`)
- [ ] Status: 101 Switching Protocols
- [ ] Connection includes `token=` parameter
- [ ] Connection stays open (green indicator)

**If Failed**:
- Check `VITE_WS_URL` uses `wss://` protocol
- Verify WebSocket endpoint exists on backend
- Check Railway supports WebSocket connections

---

#### Test 6.2: WebSocket Message Exchange
**Objective**: Can send/receive messages over WebSocket

**Steps**:
1. Keep WebSocket connection open from Test 6.1
2. Click on WebSocket connection in WS tab
3. Go to "Messages" subtab
4. Observe message traffic

**Expected Behavior**:
- Heartbeat/ping messages every 30s
- Real-time updates when data changes
- Clean message format (JSON)

**Pass Criteria**:
- [ ] Messages visible in Messages tab
- [ ] Bidirectional communication works
- [ ] No connection drops
- [ ] Messages are properly formatted JSON

---

#### Test 6.3: WebSocket Reconnection
**Objective**: WebSocket reconnects automatically if disconnected

**Steps**:
1. With WebSocket connected
2. Open Railway backend service
3. Click "Restart" to restart backend
4. Watch DevTools → WS tab for reconnection

**Expected Behavior**:
- Connection drops when backend restarts
- Frontend automatically reconnects after ~5-10 seconds
- Reconnection succeeds with same token

**Pass Criteria**:
- [ ] Automatic reconnection happens
- [ ] No manual refresh needed
- [ ] Reconnection includes token
- [ ] User sees minimal disruption

---

### Test Suite 7: Role-Based Access Control (20 minutes)

#### Test 7.1: Admin Role Access
**Objective**: Admin users can access all features

**Steps**:
1. Login as admin user
2. Try to access:
   - `/dashboard` - should work
   - `/patients` - should work
   - `/appointments` - should work
   - `/users` - should work (admin only)
   - `/settings` - should work

**Pass Criteria**:
- [ ] Admin can access all routes
- [ ] No "Access Denied" messages
- [ ] All features visible and functional

---

#### Test 7.2: Doctor Role Access
**Objective**: Doctor users have appropriate permissions

**Steps**:
1. Logout admin
2. Login as doctor user
3. Try to access:
   - `/dashboard` - should work
   - `/patients` - should work
   - `/appointments` - should work
   - `/users` - should be restricted (redirect or error)

**Pass Criteria**:
- [ ] Doctor can access medical features
- [ ] Doctor cannot access admin features
- [ ] Appropriate error/redirect for restricted routes

---

#### Test 7.3: Patient Role Access
**Objective**: Patient users have limited access

**Steps**:
1. Logout doctor
2. Login as patient user
3. Verify:
   - Can view own data only
   - Cannot access patient list
   - Cannot access admin features

**Pass Criteria**:
- [ ] Patient sees own dashboard
- [ ] Patient cannot access other patients' data
- [ ] RBAC enforced correctly

---

## 📊 Test Results Summary

### Overall Test Results
Record your results:

| Test Suite | Total Tests | Passed | Failed | Skipped |
|------------|-------------|--------|--------|---------|
| 1. Backend Health | 2 | ___ | ___ | ___ |
| 2. HTTPS Security | 3 | ___ | ___ | ___ |
| 3. CORS | 3 | ___ | ___ | ___ |
| 4. Firebase Auth | 4 | ___ | ___ | ___ |
| 5. 401 Resolution | 3 | ___ | ___ | ___ |
| 6. WebSocket WSS | 3 | ___ | ___ | ___ |
| 7. RBAC | 3 | ___ | ___ | ___ |
| **TOTAL** | **21** | **___** | **___** | **___** |

### Critical Issues Found
List any critical issues:

1. _______________________
2. _______________________
3. _______________________

### Pass Criteria
- **Required for Production**: 100% of tests in suites 1-4 pass
- **Recommended**: 90%+ of all tests pass
- **Critical**: Zero critical issues found

---

## 🔄 Retesting Failed Tests

For any failed tests:
1. Document the failure symptoms
2. Check troubleshooting section in RAILWAY_VALIDATION_CHECKLIST.md
3. Apply fix
4. Retest
5. Verify fix didn't break other tests

---

## ✅ Sign-Off

**Testing Completed By**: `___________________`
**Date**: `___________________`
**Environment**: Production (Railway)
**Overall Result**: PASS ☐ / FAIL ☐

**Approval for Production**:
- [ ] All critical tests passed
- [ ] No blocking issues found
- [ ] Documentation updated
- [ ] Team notified of deployment

**Next Steps**:
- [ ] Monitor for 24 hours
- [ ] Check error rates
- [ ] Verify user feedback
- [ ] Schedule follow-up review

---

## 📚 Related Documents
- [Railway Validation Checklist](./RAILWAY_VALIDATION_CHECKLIST.md)
- [Firebase Auth Deployment](./RAILWAY_DEPLOY_FIREBASE_AUTH.md)
- [Frontend 401 Fix](./RAILWAY_FRONTEND_401_FIX.md)
- [Automated E2E Tests](../../tests/e2e/)
