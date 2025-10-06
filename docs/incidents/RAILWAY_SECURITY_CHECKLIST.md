# Railway Production Security Checklist
## Critical Actions for Production Deployment

**Date**: 2025-10-06
**Environment**: Railway Production
**Related Report**: `RAILWAY_PRODUCTION_SECURITY_AUDIT.md`

---

## ⚠️ CRITICAL ACTIONS (Complete Within 24 Hours)

### 1. Verify CORS Configuration

**Production URLs:**
- Frontend: `https://frontend-production-18bb.up.railway.app`
- Backend: `https://clinica-oncologica-v02-production.up.railway.app`

**Action Steps:**

```bash
# Step 1: Check current CORS configuration
railway variables get ALLOWED_ORIGINS
railway variables get FRONTEND_URL
railway variables get ENVIRONMENT

# Step 2: Set CORS origins (CHOOSE ONE METHOD):

# METHOD A: Use ALLOWED_ORIGINS directly (JSON array) - RECOMMENDED
railway variables set ALLOWED_ORIGINS='["https://frontend-production-18bb.up.railway.app"]'

# METHOD B: Use individual URLs (automatic array construction)
railway variables set FRONTEND_URL="https://frontend-production-18bb.up.railway.app"
railway variables set QUIZ_URL="https://quiz-production-XXXX.up.railway.app"  # If quiz is separate
railway variables set ENVIRONMENT="production"

# Step 3: Verify settings
railway variables | grep -E "ALLOWED_ORIGINS|FRONTEND_URL|ENVIRONMENT"

# Step 4: Restart backend service
railway up --service backend-hormonia

# Step 5: Check logs for CORS initialization
railway logs --service backend-hormonia | grep "CORS"
```

**Expected Log Output:**
```
CORS Production Mode: 1 allowed origins
Allowed origins: ['https://frontend-production-18bb.up.railway.app']
Dynamic CORS middleware configured successfully
```

**Verification Test:**
```bash
# Test CORS preflight from allowed origin
curl -X OPTIONS https://clinica-oncologica-v02-production.up.railway.app/api/v1/health \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Access-Control-Request-Method: GET" \
  -v

# Expected response headers:
# Access-Control-Allow-Origin: https://frontend-production-18bb.up.railway.app
# Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
```

**Status**: [ ] Complete

---

### 2. Verify Firebase Admin SDK Configuration

**Action Steps:**

```bash
# Step 1: Check if Firebase credentials are set
railway variables get FIREBASE_ADMIN_PROJECT_ID
railway variables get FIREBASE_ADMIN_PRIVATE_KEY
railway variables get FIREBASE_ADMIN_CLIENT_EMAIL

# Step 2: If missing, set Firebase credentials
# Get these from Firebase Console → Project Settings → Service Accounts → Generate new private key

railway variables set FIREBASE_ADMIN_PROJECT_ID="your-project-id"
railway variables set FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n"
railway variables set FIREBASE_ADMIN_CLIENT_EMAIL="firebase-adminsdk@your-project.iam.gserviceaccount.com"

# Step 3: Restart backend service
railway up --service backend-hormonia

# Step 4: Check logs for Firebase initialization
railway logs --service backend-hormonia | grep "Firebase"
```

**Expected Log Output:**
```
Firebase Admin SDK initialized successfully for project: your-project-id
Firebase Authentication enabled
```

**Verification Test:**
```bash
# Test authentication endpoint
curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_VALID_FIREBASE_TOKEN" \
  -v

# Expected response:
# HTTP/1.1 200 OK
# {"id": "...", "email": "...", "role": "...", "is_active": true}
```

**Status**: [ ] Complete

---

### 3. Configure Firebase Security Settings

**Action Steps:**

```bash
# Step 1: Set allowed email domains (REPLACE with your actual domains)
railway variables set FIREBASE_ALLOWED_DOMAINS='["yourdomain.com","yourcompany.com"]'

# Step 2: Enable security features
railway variables set FIREBASE_REQUIRE_CUSTOM_CLAIMS="true"
railway variables set FIREBASE_BLOCK_PUBLIC_DOMAINS="true"
railway variables set FIREBASE_ENABLE_AUDIT_LOGGING="true"

# Step 3: Set allowed roles
railway variables set FIREBASE_ALLOWED_ROLES='["admin","super_admin","doctor","medico"]'

# Step 4: Set public domain blocklist (default provided)
railway variables set FIREBASE_PUBLIC_DOMAINS_BLOCKLIST='["gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com"]'

# Step 5: Verify settings
railway variables | grep "FIREBASE"

# Step 6: Restart backend service
railway up --service backend-hormonia
```

**Verification:**
```bash
# Check logs for security configuration
railway logs --service backend-hormonia | grep -i "firebase\|security\|domain"
```

**Status**: [ ] Complete

---

### 4. Test End-to-End Authentication Flow

**Test Sequence:**

**Test 1: Frontend Login**
```
1. Open: https://frontend-production-18bb.up.railway.app
2. Login with Firebase-authenticated user
3. Verify no CORS errors in browser console (F12 → Console)
4. Verify dashboard loads successfully
5. Check Network tab for successful API calls (200 OK responses)
```

**Test 2: API Health Check**
```bash
curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/health -v
# Expected: HTTP/1.1 200 OK
```

**Test 3: Protected Endpoint**
```bash
# Get Firebase ID token from frontend (browser console):
# firebase.auth().currentUser.getIdToken().then(token => console.log(token))

curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -v
# Expected: HTTP/1.1 200 OK with user data
```

**Test 4: Invalid Token**
```bash
curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me \
  -H "Authorization: Bearer invalid_token" \
  -v
# Expected: HTTP/1.1 401 Unauthorized
```

**Test 5: WebSocket Connection**
```javascript
// Browser console (with valid Firebase token)
const token = await firebase.auth().currentUser.getIdToken();
const ws = new WebSocket(
  `wss://clinica-oncologica-v02-production.up.railway.app/ws/connect?token=${token}`
);

ws.onopen = () => console.log('✅ WebSocket Connected');
ws.onmessage = (e) => console.log('Message:', JSON.parse(e.data));
ws.onerror = (e) => console.error('❌ WebSocket Error:', e);

// Expected: Connection successful with authenticated status
```

**Status**: [ ] Complete

---

## 📊 MONITORING SETUP (Complete Within 1 Week)

### 5. Set Up Log Monitoring

**Action Steps:**

```bash
# Step 1: Monitor real-time logs
railway logs --service backend-hormonia --follow

# Step 2: Set up log filters for security events
railway logs --service backend-hormonia | grep -i "401\|403\|rejected\|unauthorized"

# Step 3: Monitor CORS events
railway logs --service backend-hormonia | grep -i "cors\|origin"

# Step 4: Monitor Firebase authentication
railway logs --service backend-hormonia | grep -i "firebase\|authentication"

# Step 5: Monitor WebSocket connections
railway logs --service backend-hormonia | grep -i "websocket\|ws"
```

**Status**: [ ] Complete

---

### 6. Configure Security Alerts

**Recommended Monitoring:**

1. **Authentication Failures** (401 responses)
   - Alert if > 10 failures per minute
   - Alert if same IP has > 5 failures in 5 minutes

2. **CORS Violations**
   - Alert on any CORS errors in production
   - Log unauthorized origin attempts

3. **WebSocket Issues**
   - Alert on connection failure rate > 5%
   - Monitor average connection duration

4. **Firebase Errors**
   - Alert on Firebase initialization failures
   - Monitor token verification failures

**Tools to Use:**
- Railway built-in metrics
- Custom application logs
- External monitoring (optional): Sentry, Datadog, etc.

**Status**: [ ] Complete

---

## 🔧 PRODUCTION CONFIGURATION VERIFICATION

### 7. Verify All Security Settings

**Checklist:**

```bash
# Core Settings
[ ] ENVIRONMENT=production
[ ] DEBUG=false
[ ] SECURE_SSL_REDIRECT=true
[ ] SESSION_COOKIE_SECURE=true

# CORS Configuration
[ ] ALLOWED_ORIGINS set with production frontend URL
[ ] OR FRONTEND_URL + QUIZ_URL set correctly
[ ] No wildcard (*) in allowed origins

# Firebase Configuration
[ ] FIREBASE_ADMIN_PROJECT_ID set
[ ] FIREBASE_ADMIN_PRIVATE_KEY set (with proper \n escaping)
[ ] FIREBASE_ADMIN_CLIENT_EMAIL set

# Firebase Security
[ ] FIREBASE_ALLOWED_DOMAINS set with authorized domains
[ ] FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
[ ] FIREBASE_BLOCK_PUBLIC_DOMAINS=true
[ ] FIREBASE_ALLOWED_ROLES set

# Database & Redis
[ ] DATABASE_URL using postgresql+psycopg:// (Python 3.13 compatible)
[ ] REDIS_URL set correctly
[ ] Redis SSL configured if using rediss://

# Secrets
[ ] SECRET_KEY is strong and unique (not default/placeholder)
[ ] MONTHLY_QUIZ_TOKEN_SECRET is different from SECRET_KEY
[ ] All API keys are set (GEMINI_API_KEY, etc.)
```

**Verification Command:**
```bash
# Get all environment variables and verify
railway variables > railway-vars.txt
cat railway-vars.txt

# Check for placeholder values
grep -i "REPLACE_WITH\|CHANGE_THIS\|YOUR_" railway-vars.txt
# Expected: No matches (all placeholders replaced)

# Clean up
rm railway-vars.txt
```

**Status**: [ ] Complete

---

## 🚨 INCIDENT RESPONSE

### Known Issues & Solutions

#### Issue: 401 Unauthorized Errors

**Symptoms:**
- Dashboard fails to load after login
- API calls return 401 responses
- Frontend shows authentication errors

**Diagnosis:**
```bash
# Check logs for authentication errors
railway logs --service backend-hormonia | grep "401"

# Check Firebase initialization
railway logs --service backend-hormonia | grep "Firebase"

# Verify token in frontend console
firebase.auth().currentUser.getIdToken().then(t => console.log(t))
```

**Solution:**
1. Verify Firebase credentials are set in Railway
2. Check token is being sent in Authorization header
3. Verify frontend is using correct backend URL
4. Check for token expiration (token refresh needed)

---

#### Issue: CORS Errors in Browser

**Symptoms:**
- Browser console shows CORS policy errors
- Preflight OPTIONS requests failing
- API calls blocked by browser

**Diagnosis:**
```bash
# Check CORS configuration in logs
railway logs --service backend-hormonia | grep "CORS"

# Test CORS manually
curl -X OPTIONS https://clinica-oncologica-v02-production.up.railway.app/api/v1/health \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

**Solution:**
1. Verify ALLOWED_ORIGINS includes frontend URL
2. Ensure ENVIRONMENT=production in Railway
3. Check frontend is using correct backend URL
4. Verify no trailing slashes in origin URLs

---

#### Issue: Firebase Not Configured

**Symptoms:**
- 503 Service Unavailable on auth endpoints
- Log message: "Firebase authentication is not configured"

**Diagnosis:**
```bash
# Check Firebase environment variables
railway variables | grep "FIREBASE"
```

**Solution:**
1. Set all three Firebase credentials (PROJECT_ID, PRIVATE_KEY, CLIENT_EMAIL)
2. Ensure private key has proper \n escaping
3. Restart backend service
4. Verify initialization in logs

---

## 📝 DOCUMENTATION CHECKLIST

- [x] Security audit report created: `RAILWAY_PRODUCTION_SECURITY_AUDIT.md`
- [x] Action checklist created: `RAILWAY_SECURITY_CHECKLIST.md`
- [ ] Update team on critical actions required
- [ ] Schedule security review meeting
- [ ] Document any configuration changes made
- [ ] Update runbook with new procedures

---

## 🎯 SUCCESS CRITERIA

**Deployment is production-ready when:**

1. ✅ All critical actions completed (sections 1-4)
2. ✅ CORS allows frontend origin only (no wildcards)
3. ✅ Firebase authentication working end-to-end
4. ✅ No 401/403 errors on legitimate requests
5. ✅ WebSocket connections stable
6. ✅ All security settings verified
7. ✅ Monitoring and alerting configured
8. ✅ Incident response procedures documented
9. ✅ Team trained on security procedures
10. ✅ Regular security audits scheduled

---

## 📞 SUPPORT & ESCALATION

**If you encounter issues:**

1. Check the comprehensive audit report: `RAILWAY_PRODUCTION_SECURITY_AUDIT.md`
2. Review Railway logs: `railway logs --service backend-hormonia --follow`
3. Check recent commits for fixes: `git log --oneline -20`
4. Review related documentation:
   - `docs/deployment/RAILWAY_DEPLOYMENT.md`
   - `docs/COMPREHENSIVE_SECURITY_REVIEW.md`

**Recent Fixes Applied:**
- `bef9a2e` - Fixed race condition causing 401 errors on dashboard
- `0fcf76f` - Improved WebSocket error handling for closed connections
- `7ea5b62` - Added Firebase custom claims validation
- `1f00be1` - Implemented dual-mode JWT authentication (Firebase + Internal)

---

**Last Updated**: 2025-10-06
**Next Review**: 2025-10-13 (1 week)
