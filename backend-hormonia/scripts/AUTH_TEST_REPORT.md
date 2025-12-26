# Authentication System Test Report

**Date**: 2025-12-23
**Test Subject**: Firebase Authentication System
**Backend URL**: http://localhost:8000
**API Version**: v2
**Test Credentials**: admin@neoplasiaslitoral.com

---

## Executive Summary

✅ **Test Script Created**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/scripts/test_auth.py`
❌ **Server Status**: Backend server is NOT running
⚠️ **Action Required**: Start backend server to execute authentication tests

---

## 1. Authentication Endpoint Analysis

### Primary Authentication Endpoint

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/auth.py`

**Endpoint**: `POST /api/v2/auth/firebase/verify`

**Authentication Flow**:
```
1. Client sends Firebase ID token
2. Backend verifies token with Firebase Admin SDK
3. Firebase returns user data (uid, email, custom claims)
4. Backend syncs user with PostgreSQL database
5. Creates Redis session for fast authentication
6. Returns session cookie + session data to client
```

**Request Format**:
```json
{
  "id_token": "<Firebase JWT token>"
}
```

**Success Response** (200):
```json
{
  "valid": true,
  "session_id": "<UUID>",
  "message": "Login successful",
  "user": {
    "id": "<UUID>",
    "email": "admin@neoplasiaslitoral.com",
    "full_name": "Admin User",
    "role": "admin",
    "permissions": ["admin.read", "admin.write", ...]
  }
}
```

**Response Headers**:
- Sets `session_id` cookie (HttpOnly, Secure in production)
- Sets `X-Session-ID` header (debug mode only)

---

## 2. Firebase Configuration

### Environment Variables (from .env)

```bash
# Firebase Admin SDK
FIREBASE_ADMIN_PROJECT_ID=sistema-oncologico-auth
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-fbsvc@sistema-oncologico-auth.iam.gserviceaccount.com
FIREBASE_ADMIN_PRIVATE_KEY=<Private key configured>

# Security Settings
FIREBASE_ENABLE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ENABLE_AUDIT_LOGGING=true
FIREBASE_ENABLE_BLOCK_PUBLIC_DOMAINS=true
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com"]
FIREBASE_ALLOWED_ROLES=["admin","doctor","medico"]

# Cache Settings
FIREBASE_TOKEN_CACHE_TTL_SECONDS=3600
FIREBASE_USER_CACHE_TTL_SECONDS=7200
FIREBASE_SESSION_TTL_SECONDS=86400
```

### Missing Configuration

⚠️ **FIREBASE_WEB_API_KEY** - Required for test script to authenticate with Firebase REST API

**Where to find**:
1. Firebase Console → Project Settings
2. General tab → Web API Key
3. Add to `.env`: `FIREBASE_WEB_API_KEY=<your-web-api-key>`

---

## 3. Authentication Service Analysis

### Firebase Auth Service

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/firebase_auth_service.py`

**Key Features**:
- ✅ Firebase Admin SDK initialization with timeout protection (10s)
- ✅ Token verification with revocation checking
- ✅ Custom claims extraction (role, permissions)
- ✅ User management (get user, set custom claims, revoke tokens)
- ✅ Thread-safe singleton pattern

**Methods**:
1. `verify_token(token)` - Verify Firebase ID token and extract user data
2. `get_user(uid)` - Get Firebase user data by UID
3. `set_custom_claims(uid, claims)` - Set custom claims for user (roles)
4. `revoke_refresh_tokens(uid)` - Force re-authentication

### Authentication Dependencies

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/dependencies/auth_dependencies.py`

**Dual Authentication System**:

1. **Session-based (RECOMMENDED)**:
   - Endpoint: Uses `get_current_user_from_session`
   - Speed: ~2-5ms (Redis cache)
   - Flow: Cookie/Header → Redis → PostgreSQL (if cache miss)

2. **Token-based (DEPRECATED)**:
   - Endpoint: Uses `get_current_user`
   - Speed: ~5-250ms (depending on cache)
   - Flow: Bearer token → Firebase SDK → PostgreSQL

**Security Features**:
- ✅ Firebase UID validation (regex pattern)
- ✅ Email validation (RFC 5322)
- ✅ Injection attack prevention
- ✅ Role-based access control (RBAC)
- ✅ Session expiration handling
- ✅ Multi-layer caching (Redis)

---

## 4. Database Configuration

### PostgreSQL Connection
```
Host: database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com
Database: postgres
SSL: Required
Pool Size: 20 connections
Max Overflow: 10
Timeout: 20 seconds
```

### User Model Fields
- `id` (UUID, primary key)
- `firebase_uid` (unique)
- `email` (unique, validated)
- `full_name`
- `role` (admin, doctor, medico)
- `is_active` (boolean)
- `is_locked` (boolean)
- `failed_login_attempts` (integer)
- `locked_until` (timestamp)
- `created_at`, `updated_at`, `firebase_last_sign_in`

---

## 5. Test Script Features

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/scripts/test_auth.py`

**Test Suite**:
1. ✅ Server health check
2. ✅ Firebase authentication (REST API)
3. ✅ Backend authentication endpoint
4. ✅ Session verification
5. ✅ Protected endpoint access (patient list)

**Features**:
- Colored terminal output
- Detailed error messages
- Request/response logging
- Cookie and header validation
- Comprehensive test summary

**Usage**:
```bash
# Make executable
chmod +x scripts/test_auth.py

# Run tests
python3 scripts/test_auth.py
```

---

## 6. How to Start Backend Server

### Prerequisites
1. Python 3.12.3 installed
2. Virtual environment activated
3. Dependencies installed
4. PostgreSQL database accessible
5. Redis server running (optional, will gracefully degrade)

### Startup Commands

#### Option 1: Using Uvicorn (Development)
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia

# Activate virtual environment (if using venv)
source venv/bin/activate  # Linux/Mac
# OR
.\venv\Scripts\activate  # Windows

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Server will be available at:
# http://localhost:8000
# API docs: http://localhost:8000/docs
```

#### Option 2: Using Python Module
```bash
python3 -m uvicorn app.main:app --reload
```

#### Option 3: Using startup script (if available)
```bash
./scripts/init_system.py
```

### Verify Server is Running
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-23T13:00:00Z"
}
```

---

## 7. Running Authentication Tests

### Step 1: Add Firebase Web API Key
```bash
# Edit .env file
nano .env

# Add this line:
FIREBASE_WEB_API_KEY=<your-firebase-web-api-key>
```

### Step 2: Start Backend Server
```bash
uvicorn app.main:app --reload
```

### Step 3: Run Test Script
```bash
python3 scripts/test_auth.py
```

### Expected Test Output

```
================================================================================
Firebase Authentication System Test
================================================================================

✓ Server is running at http://localhost:8000
✓ Firebase authentication successful
✓ Backend authentication successful!
✓ Session cookie set
✓ Session verification successful!
✓ Protected endpoint access successful!

================================================================================
Test Summary
================================================================================

Total Tests: 5
Passed: 5
Failed: 0

✓ All tests passed! ✓
```

---

## 8. Manual Testing (Alternative to Script)

If you don't have Firebase Web API Key, test manually:

### Using cURL

```bash
# 1. Get Firebase ID token from your frontend application
# Copy the token from browser DevTools → Application → Storage

# 2. Test backend authentication
curl -X POST http://localhost:8000/api/v2/auth/firebase/verify \
  -H "Content-Type: application/json" \
  -d '{
    "id_token": "<paste-your-firebase-token-here>"
  }' \
  -c cookies.txt \
  -v

# 3. Test session verification
curl -X GET http://localhost:8000/api/v2/auth/verify-session \
  -b cookies.txt \
  -v

# 4. Test protected endpoint
curl -X GET "http://localhost:8000/api/v2/patients/?limit=5" \
  -b cookies.txt \
  -v
```

### Using Postman

1. **POST** `/api/v2/auth/firebase/verify`
   - Body: `{"id_token": "<firebase-token>"}`
   - Headers: `Content-Type: application/json`
   - **Check**: Response should set `session_id` cookie

2. **GET** `/api/v2/auth/verify-session`
   - No body
   - **Check**: Automatically uses cookie from previous request

3. **GET** `/api/v2/patients/?limit=5`
   - No body
   - **Check**: Returns patient list (if authorized)

---

## 9. Common Issues and Solutions

### Issue 1: Server Not Running
**Error**: `Cannot connect to server at http://localhost:8000`

**Solution**:
```bash
cd backend-hormonia
uvicorn app.main:app --reload
```

### Issue 2: Firebase Web API Key Missing
**Error**: `FIREBASE_WEB_API_KEY not found in environment`

**Solution**:
1. Go to Firebase Console
2. Project Settings → General → Web API Key
3. Add to `.env`: `FIREBASE_WEB_API_KEY=<key>`

### Issue 3: Invalid Credentials
**Error**: `Firebase authentication failed: INVALID_EMAIL or INVALID_PASSWORD`

**Solution**:
1. Verify email: `admin@neoplasiaslitoral.com`
2. Verify password: `Admin@123456!`
3. Check user exists in Firebase Console → Authentication → Users

### Issue 4: Database Connection Failed
**Error**: `Could not connect to database`

**Solution**:
1. Check PostgreSQL is accessible
2. Verify `.env` DATABASE_URL
3. Check security groups/firewall rules

### Issue 5: Redis Connection Failed
**Warning**: `Redis connection failed, using fallback`

**Impact**: Performance degraded but authentication still works

**Solution** (optional):
```bash
# Install Redis
sudo apt-get install redis-server

# Start Redis
redis-server
```

### Issue 6: Forbidden - Domain Not Allowed
**Error**: `User domain not allowed`

**Solution**:
Check `FIREBASE_ALLOWED_DOMAINS` in `.env`:
```bash
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com"]
```

---

## 10. Security Considerations

### Current Security Measures
- ✅ Firebase UID validation (regex pattern, 20-128 chars)
- ✅ Email validation (RFC 5322)
- ✅ Injection attack prevention
- ✅ Domain whitelist (`neoplasiaslitoral.com`)
- ✅ Role-based access control
- ✅ Custom claims validation
- ✅ HttpOnly session cookies
- ✅ Secure cookies (production)
- ✅ Token revocation checking
- ✅ Session expiration (5 days default)
- ✅ Account locking (failed attempts)
- ✅ Audit logging

### Recommendations
1. ✅ Keep FIREBASE_WEB_API_KEY secret (don't commit to git)
2. ✅ Use HTTPS in production
3. ✅ Enable CSRF protection for state-changing operations
4. ✅ Monitor failed login attempts
5. ✅ Regularly rotate Firebase service account keys
6. ✅ Review and update ALLOWED_DOMAINS/ROLES periodically

---

## 11. Next Steps

### Immediate Actions
1. **Start backend server**:
   ```bash
   cd backend-hormonia
   uvicorn app.main:app --reload
   ```

2. **Add Firebase Web API Key** (optional, for automated tests):
   ```bash
   echo 'FIREBASE_WEB_API_KEY=<your-key>' >> .env
   ```

3. **Run test script**:
   ```bash
   python3 scripts/test_auth.py
   ```

### Long-term Improvements
1. Add integration tests for authentication flow
2. Implement rate limiting on login endpoint
3. Add monitoring/alerting for failed authentications
4. Create admin panel for user management
5. Implement password reset flow
6. Add 2FA/MFA support

---

## 12. Files Created

| File | Purpose | Location |
|------|---------|----------|
| `test_auth.py` | Authentication test script | `/scripts/test_auth.py` |
| `AUTH_TEST_REPORT.md` | This documentation | `/scripts/AUTH_TEST_REPORT.md` |

---

## Contact & Support

For issues or questions about the authentication system:
1. Review this documentation
2. Check server logs: `tail -f logs/app.log`
3. Check Firebase Console for authentication errors
4. Review database logs for connection issues

---

**Report Generated**: 2025-12-23T13:10:00Z
**Test Status**: ⚠️ Pending (Server not running)
**Next Action**: Start backend server and re-run tests
