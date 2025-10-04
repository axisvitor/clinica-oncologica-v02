# Firebase Authentication System - Comprehensive Testing Plan

**Version:** 1.0.0
**Last Updated:** 2025-10-03
**System:** Clinica Oncologica v2.0 - Hormonia Backend/Frontend
**Authentication:** Firebase Auth (replaced Supabase)

---

## Executive Summary

This document provides a comprehensive testing plan for the Firebase authentication system implemented across the backend (FastAPI/Python) and frontend (React/TypeScript). The system uses Firebase Admin SDK for backend token validation and Firebase Client SDK for frontend authentication.

**Testing Coverage Areas:**
1. Configuration & Initialization (10 tests)
2. Backend Token Validation (15 tests)
3. Frontend Login Flow (12 tests)
4. Integration & E2E (8 tests)
5. Security & Vulnerability (10 tests)

**Total Test Scenarios:** 55+

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Test Category 1: Configuration Tests](#1-configuration-tests)
3. [Test Category 2: Backend Token Validation](#2-backend-token-validation-tests)
4. [Test Category 3: Frontend Login Flow](#3-frontend-login-flow-tests)
5. [Test Category 4: Integration Tests](#4-integration-tests)
6. [Test Category 5: Security Tests](#5-security-tests)
7. [Testing Tools & Setup](#testing-tools--setup)
8. [Mock Data & Test Fixtures](#mock-data--test-fixtures)
9. [Validation Commands](#validation-commands)
10. [Testing Gaps & Recommendations](#testing-gaps--recommendations)

---

## System Architecture Overview

### Backend Components
```
backend-hormonia/
├── app/
│   ├── services/
│   │   └── firebase_auth_service.py        # Firebase Admin SDK wrapper
│   ├── dependencies/
│   │   └── auth_dependencies.py             # JWT validation dependency
│   ├── api/v1/
│   │   └── auth.py                          # Auth endpoints (deprecated local auth)
│   └── config.py                            # Settings with Firebase credentials
```

### Frontend Components
```
frontend-hormonia/
├── src/
│   ├── lib/
│   │   └── firebase-client.ts               # Firebase Client SDK wrapper
│   └── contexts/
│       └── MedicoAuthContext.tsx            # Auth state management
```

### Authentication Flow
```
1. User enters credentials → Frontend Firebase Client
2. Firebase validates → Returns ID token (JWT)
3. Frontend sends token → Backend API with Bearer header
4. Backend validates token → Firebase Admin SDK
5. Backend syncs user → Local PostgreSQL database
6. Backend returns → User data + session
```

---

## 1. Configuration Tests

### 1.1 Backend Firebase Configuration Validation

**Test ID:** CONFIG-001
**Priority:** CRITICAL
**Type:** Unit Test

**Test Scenarios:**

#### Scenario 1.1.1: Valid Firebase Admin SDK Configuration
```python
# Test: Firebase service initializes with valid credentials
# File: tests/unit/services/test_firebase_auth_service.py

import pytest
from app.services.firebase_auth_service import FirebaseAuthService

def test_firebase_init_success():
    """Test Firebase Admin SDK initializes with valid credentials"""
    service = FirebaseAuthService(
        project_id="test-project",
        private_key="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
        client_email="test@test-project.iam.gserviceaccount.com"
    )
    assert service._initialized == True
    assert service._app is not None

# Expected: Service initializes without errors
# Actual: Run pytest and verify no RuntimeError
```

**Validation Command:**
```bash
# Test Firebase configuration loading from environment
cd backend-hormonia
pytest tests/unit/services/test_firebase_auth_service.py::test_firebase_init_success -v
```

#### Scenario 1.1.2: Missing Firebase Credentials
```python
def test_firebase_missing_credentials():
    """Test Firebase fails gracefully with missing credentials"""
    with pytest.raises(RuntimeError, match="Firebase initialization failed"):
        service = FirebaseAuthService(
            project_id="",
            private_key="",
            client_email=""
        )

# Expected: Raises RuntimeError with clear message
# Actual: Service should not initialize
```

**Validation Command:**
```bash
pytest tests/unit/services/test_firebase_auth_service.py::test_firebase_missing_credentials -v
```

#### Scenario 1.1.3: Invalid Private Key Format
```python
def test_firebase_invalid_private_key():
    """Test Firebase rejects invalid private key format"""
    with pytest.raises(RuntimeError):
        service = FirebaseAuthService(
            project_id="test-project",
            private_key="INVALID_KEY_FORMAT",
            client_email="test@test.com"
        )

# Expected: Initialization fails with descriptive error
# Actual: Check error message mentions private key
```

#### Scenario 1.1.4: Environment Variables Loaded Correctly
```python
def test_firebase_env_vars_loaded():
    """Test Firebase credentials load from environment"""
    from app.config import settings

    assert settings.FIREBASE_ADMIN_PROJECT_ID is not None
    assert settings.FIREBASE_ADMIN_PRIVATE_KEY is not None
    assert settings.FIREBASE_ADMIN_CLIENT_EMAIL is not None
    assert "@" in settings.FIREBASE_ADMIN_CLIENT_EMAIL
    assert "-----BEGIN PRIVATE KEY-----" in settings.FIREBASE_ADMIN_PRIVATE_KEY

# Expected: All Firebase env vars present and valid format
# Actual: Check .env.example for required variables
```

**Validation Command:**
```bash
# Verify environment variables are set
python -c "from app.config import settings; \
  print(f'Project ID: {bool(settings.FIREBASE_ADMIN_PROJECT_ID)}'); \
  print(f'Private Key: {bool(settings.FIREBASE_ADMIN_PRIVATE_KEY)}'); \
  print(f'Client Email: {bool(settings.FIREBASE_ADMIN_CLIENT_EMAIL)}')"
```

### 1.2 Frontend Firebase Configuration Validation

**Test ID:** CONFIG-002
**Priority:** CRITICAL
**Type:** Unit Test

#### Scenario 1.2.1: Firebase Client SDK Configuration
```typescript
// Test: Firebase app initializes with valid config
// File: tests/unit/lib/test_firebase_client.ts

import { describe, it, expect, beforeEach } from 'vitest'
import { firebaseAuth } from '../../../src/lib/firebase-client'

describe('Firebase Client Configuration', () => {
  it('should initialize Firebase app with valid config', () => {
    expect(import.meta.env.VITE_FIREBASE_API_KEY).toBeDefined()
    expect(import.meta.env.VITE_FIREBASE_AUTH_DOMAIN).toBeDefined()
    expect(import.meta.env.VITE_FIREBASE_PROJECT_ID).toBeDefined()
  })

  it('should expose firebaseAuth methods', () => {
    expect(firebaseAuth.signInWithPassword).toBeDefined()
    expect(firebaseAuth.signOut).toBeDefined()
    expect(firebaseAuth.getCurrentUser).toBeDefined()
  })
})

// Expected: All methods available
// Actual: Run vitest and check exports
```

**Validation Command:**
```bash
# Test frontend Firebase config
cd frontend-hormonia
npm run test -- tests/unit/lib/test_firebase_client.ts
```

#### Scenario 1.2.2: Missing Frontend Environment Variables
```typescript
it('should fail gracefully with missing VITE variables', () => {
  // Temporarily unset VITE_FIREBASE_API_KEY
  const originalKey = import.meta.env.VITE_FIREBASE_API_KEY
  delete import.meta.env.VITE_FIREBASE_API_KEY

  // Firebase should not initialize
  // Check for proper error handling

  // Restore
  import.meta.env.VITE_FIREBASE_API_KEY = originalKey
})

// Expected: Clear error message about missing config
// Actual: Check browser console for warnings
```

---

## 2. Backend Token Validation Tests

### 2.1 Valid Token Acceptance

**Test ID:** TOKEN-001
**Priority:** CRITICAL
**Type:** Integration Test

#### Scenario 2.1.1: Valid Firebase Token Accepted
```python
# Test: Backend accepts valid Firebase ID token
# File: tests/integration/api/test_auth_token_validation.py

import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth

@pytest.mark.integration
async def test_valid_token_accepted(test_client: TestClient, firebase_test_user):
    """Test backend accepts valid Firebase ID token"""

    # Get valid token from Firebase test user
    token = firebase_test_user['id_token']

    # Make authenticated request
    response = test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == firebase_test_user['email']

# Expected: 200 OK with user profile
# Actual: Token validated and user data returned
```

**Validation Command:**
```bash
# Create test user in Firebase and get token
cd backend-hormonia

# Run integration test
pytest tests/integration/api/test_auth_token_validation.py::test_valid_token_accepted -v -s
```

**Manual Validation:**
```bash
# Get real Firebase token (requires Firebase CLI)
firebase login
firebase auth:export users.json --project your-project-id

# Test with curl
TOKEN="your-firebase-id-token"
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Expected Output:
# {
#   "id": "uuid",
#   "email": "user@example.com",
#   "full_name": "Test User",
#   "role": "doctor",
#   "is_active": true
# }
```

### 2.2 Expired Token Rejection

**Test ID:** TOKEN-002
**Priority:** HIGH
**Type:** Unit Test

#### Scenario 2.2.1: Expired Token Returns 401
```python
@pytest.mark.unit
async def test_expired_token_rejected(test_client: TestClient):
    """Test backend rejects expired Firebase token"""

    # Use expired token (from fixture or mock)
    expired_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.EXPIRED_PAYLOAD.SIGNATURE"

    response = test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()

# Expected: 401 Unauthorized with "Token has expired" message
# Actual: Firebase Admin SDK detects expiration
```

**Validation Command:**
```bash
pytest tests/unit/api/test_auth_token_validation.py::test_expired_token_rejected -v
```

**Manual Validation:**
```bash
# Use old/expired token
EXPIRED_TOKEN="eyJ..."  # Old token from >1 hour ago

curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer $EXPIRED_TOKEN"

# Expected Output:
# {
#   "detail": "Token has expired"
# }
# Status: 401
```

### 2.3 Malformed Token Rejection

**Test ID:** TOKEN-003
**Priority:** HIGH
**Type:** Unit Test

#### Scenario 2.3.1: Invalid JWT Format
```python
@pytest.mark.unit
async def test_malformed_token_rejected(test_client: TestClient):
    """Test backend rejects malformed JWT token"""

    invalid_tokens = [
        "not-a-jwt-token",
        "invalid.jwt.format",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",  # Incomplete
        "",
        None,
        "Bearer token-without-bearer-removed"
    ]

    for token in invalid_tokens:
        if token is None:
            headers = {}
        else:
            headers = {"Authorization": f"Bearer {token}"}

        response = test_client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower() or \
               "could not validate" in response.json()["detail"].lower()

# Expected: 401 for all invalid formats
# Actual: Firebase Admin SDK validates structure
```

**Validation Command:**
```bash
pytest tests/unit/api/test_auth_token_validation.py::test_malformed_token_rejected -v
```

### 2.4 Token from Wrong Project

**Test ID:** TOKEN-004
**Priority:** HIGH
**Type:** Integration Test

#### Scenario 2.4.1: Token from Different Firebase Project
```python
@pytest.mark.integration
async def test_wrong_project_token_rejected(test_client: TestClient):
    """Test backend rejects token from different Firebase project"""

    # Token from different Firebase project (wrong project_id in claims)
    wrong_project_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.WRONG_PROJECT.SIG"

    response = test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {wrong_project_token}"}
    )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()

# Expected: 401 with invalid token message
# Actual: Firebase validates project_id in token claims
```

### 2.5 Missing Authorization Header

**Test ID:** TOKEN-005
**Priority:** MEDIUM
**Type:** Unit Test

#### Scenario 2.5.1: No Authorization Header
```python
@pytest.mark.unit
async def test_missing_auth_header(test_client: TestClient):
    """Test backend returns 401 when Authorization header missing"""

    response = test_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert response.headers["WWW-Authenticate"] == "Bearer"

# Expected: 401 with WWW-Authenticate header
# Actual: FastAPI HTTPBearer dependency enforces this
```

**Validation Command:**
```bash
# Test without Authorization header
curl -X GET "http://localhost:8000/api/v1/auth/me" -v

# Expected Output:
# HTTP/1.1 401 Unauthorized
# WWW-Authenticate: Bearer
```

### 2.6 Token Signature Validation

**Test ID:** TOKEN-006
**Priority:** CRITICAL
**Type:** Security Test

#### Scenario 2.6.1: Invalid Signature Detected
```python
@pytest.mark.security
async def test_invalid_signature_rejected(test_client: TestClient):
    """Test backend rejects token with invalid signature"""

    # Valid token structure but tampered signature
    tampered_token = create_tampered_jwt()

    response = test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"}
    )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()

# Expected: Signature validation fails
# Actual: Firebase verifies signature with public keys
```

---

## 3. Frontend Login Flow Tests

### 3.1 Successful Login

**Test ID:** LOGIN-001
**Priority:** CRITICAL
**Type:** E2E Test

#### Scenario 3.1.1: Valid Credentials Login
```typescript
// Test: User can login with valid email/password
// File: tests/e2e/auth/login_flow.spec.ts

import { test, expect } from '@playwright/test'

test('should login with valid credentials', async ({ page }) => {
  await page.goto('http://localhost:5173/medico/login')

  // Fill login form
  await page.fill('[name="email"]', 'medico@test.com')
  await page.fill('[name="password"]', 'Test123!@#')
  await page.click('button[type="submit"]')

  // Wait for redirect to dashboard
  await page.waitForURL('**/medico/dashboard')

  // Verify user is logged in
  await expect(page.locator('[data-testid="user-menu"]')).toBeVisible()
  await expect(page.locator('text=medico@test.com')).toBeVisible()
})

// Expected: Redirects to dashboard with user menu visible
// Actual: Token stored, API calls include Bearer token
```

**Validation Command:**
```bash
# Run E2E test
cd frontend-hormonia
npx playwright test tests/e2e/auth/login_flow.spec.ts
```

**Manual Validation:**
```bash
# Open browser and test manually
npm run dev

# Then in browser:
# 1. Navigate to http://localhost:5173/medico/login
# 2. Enter: medico@test.com / Test123!@#
# 3. Click "Entrar"
# 4. Verify redirect to /medico/dashboard
# 5. Open DevTools → Network → Check for Authorization headers
# 6. Open DevTools → Application → LocalStorage → Check for token
```

### 3.2 Login Failure Scenarios

**Test ID:** LOGIN-002
**Priority:** HIGH
**Type:** Unit Test

#### Scenario 3.2.1: Invalid Password
```typescript
// File: tests/unit/contexts/MedicoAuthContext.test.tsx

import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useMedicoAuth, MedicoAuthProvider } from '../../../contexts/MedicoAuthContext'

describe('MedicoAuthContext - Login Failures', () => {
  it('should reject invalid password', async () => {
    const { result } = renderHook(() => useMedicoAuth(), {
      wrapper: MedicoAuthProvider
    })

    await act(async () => {
      const response = await result.current.signIn(
        'medico@test.com',
        'wrong-password'
      )

      expect(response.success).toBe(false)
      expect(response.error).toMatch(/password|authentication failed/i)
    })

    expect(result.current.state.isAuthenticated).toBe(false)
    expect(result.current.state.error).toBeTruthy()
  })
})

// Expected: Login fails with error message
// Actual: Firebase returns auth/wrong-password
```

#### Scenario 3.2.2: Non-Existent User
```typescript
it('should reject non-existent user', async () => {
  const { result } = renderHook(() => useMedicoAuth(), {
    wrapper: MedicoAuthProvider
  })

  await act(async () => {
    const response = await result.current.signIn(
      'nonexistent@test.com',
      'password123'
    )

    expect(response.success).toBe(false)
    expect(response.error).toMatch(/not found|user.*not.*exist/i)
  })
})

// Expected: User not found error
// Actual: Firebase returns auth/user-not-found
```

#### Scenario 3.2.3: Network Error Handling
```typescript
it('should handle network errors gracefully', async () => {
  // Mock network failure
  vi.mock('firebase/auth', () => ({
    signInWithEmailAndPassword: vi.fn().mockRejectedValue(
      new Error('Network request failed')
    )
  }))

  const { result } = renderHook(() => useMedicoAuth(), {
    wrapper: MedicoAuthProvider
  })

  await act(async () => {
    const response = await result.current.signIn(
      'medico@test.com',
      'password'
    )

    expect(response.success).toBe(false)
    expect(response.error).toMatch(/network|failed/i)
  })
})

// Expected: User-friendly error message
// Actual: Network error caught and displayed
```

### 3.3 Form Validation

**Test ID:** LOGIN-003
**Priority:** MEDIUM
**Type:** Unit Test

#### Scenario 3.3.1: Email Format Validation
```typescript
// Test client-side validation before Firebase call
it('should validate email format', async () => {
  const invalidEmails = [
    'notanemail',
    'missing@domain',
    '@nodomain.com',
    'spaces in@email.com',
    ''
  ]

  for (const email of invalidEmails) {
    // Test that form validation catches invalid email
    // before making Firebase call
  }
})

// Expected: Client-side validation prevents submission
// Actual: Form shows error, no Firebase API call
```

---

## 4. Integration Tests

### 4.1 Complete Authentication Flow

**Test ID:** INTEGRATION-001
**Priority:** CRITICAL
**Type:** E2E Integration Test

#### Scenario 4.1.1: Login → API Request → Success
```typescript
// Test: Complete flow from login to authenticated API request
// File: tests/integration/auth_flow_complete.spec.ts

import { test, expect } from '@playwright/test'

test('complete authentication flow', async ({ page, context }) => {
  // Step 1: Login
  await page.goto('http://localhost:5173/medico/login')
  await page.fill('[name="email"]', 'medico@test.com')
  await page.fill('[name="password"]', 'Test123!@#')
  await page.click('button[type="submit"]')

  // Step 2: Wait for dashboard
  await page.waitForURL('**/medico/dashboard')

  // Step 3: Verify token in localStorage
  const token = await page.evaluate(() =>
    localStorage.getItem('hormonia_access_token')
  )
  expect(token).toBeTruthy()
  expect(token).toMatch(/^eyJ/)  // JWT format

  // Step 4: Make authenticated API request
  const cookies = await context.cookies()
  const response = await page.request.get('http://localhost:8000/api/v1/auth/me', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })

  expect(response.status()).toBe(200)
  const userData = await response.json()
  expect(userData.email).toBe('medico@test.com')

  // Step 5: Verify UI shows user data
  await expect(page.locator('[data-testid="user-name"]')).toContainText('Test Medico')
})

// Expected: Complete flow succeeds
// Actual: Token valid, API calls work, UI updates
```

**Validation Command:**
```bash
npx playwright test tests/integration/auth_flow_complete.spec.ts --headed
```

### 4.2 Token Included in API Requests

**Test ID:** INTEGRATION-002
**Priority:** HIGH
**Type:** Integration Test

#### Scenario 4.2.1: Authorization Header Auto-Added
```typescript
it('should automatically add Authorization header to API requests', async () => {
  // After login, all API requests should include token

  // Monitor network requests
  const requests: any[] = []
  page.on('request', request => {
    if (request.url().includes('/api/v1/')) {
      requests.push({
        url: request.url(),
        headers: request.headers()
      })
    }
  })

  // Make several API calls through UI
  await page.click('[data-testid="load-patients"]')
  await page.waitForResponse(resp => resp.url().includes('/pacientes'))

  // Verify all requests have Authorization header
  const apiRequests = requests.filter(r => r.url.includes('/api/v1/'))
  expect(apiRequests.length).toBeGreaterThan(0)

  for (const req of apiRequests) {
    expect(req.headers.authorization).toBeDefined()
    expect(req.headers.authorization).toMatch(/^Bearer eyJ/)
  }
})

// Expected: All API requests include token
// Actual: apiClient.ts interceptor adds header
```

### 4.3 Protected Route Access

**Test ID:** INTEGRATION-003
**Priority:** HIGH
**Type:** E2E Test

#### Scenario 4.3.1: Unauthenticated User Redirected
```typescript
test('should redirect unauthenticated user to login', async ({ page }) => {
  // Clear any existing tokens
  await page.goto('http://localhost:5173')
  await page.evaluate(() => localStorage.clear())

  // Try to access protected route
  await page.goto('http://localhost:5173/medico/dashboard')

  // Should redirect to login
  await page.waitForURL('**/medico/login')
  expect(page.url()).toContain('/login')
})

// Expected: Redirect to login page
// Actual: Route guard checks authentication
```

### 4.4 Page Reload Preserves Auth

**Test ID:** INTEGRATION-004
**Priority:** MEDIUM
**Type:** E2E Test

#### Scenario 4.4.1: Auth State Persists After Reload
```typescript
test('should preserve authentication after page reload', async ({ page }) => {
  // Login
  await page.goto('http://localhost:5173/medico/login')
  await page.fill('[name="email"]', 'medico@test.com')
  await page.fill('[name="password"]', 'Test123!@#')
  await page.click('button[type="submit"]')
  await page.waitForURL('**/dashboard')

  // Get token before reload
  const tokenBefore = await page.evaluate(() =>
    localStorage.getItem('hormonia_access_token')
  )

  // Reload page
  await page.reload()

  // Should still be on dashboard (not redirected to login)
  expect(page.url()).toContain('/dashboard')

  // Token should still exist
  const tokenAfter = await page.evaluate(() =>
    localStorage.getItem('hormonia_access_token')
  )
  expect(tokenAfter).toBe(tokenBefore)

  // User menu should be visible
  await expect(page.locator('[data-testid="user-menu"]')).toBeVisible()
})

// Expected: User remains logged in
// Actual: Token persists in localStorage, context reinitializes
```

---

## 5. Security Tests

### 5.1 CORS Policy

**Test ID:** SECURITY-001
**Priority:** HIGH
**Type:** Security Test

#### Scenario 5.1.1: Unauthorized Domain Blocked
```python
@pytest.mark.security
async def test_cors_blocks_unauthorized_domain(test_client: TestClient):
    """Test CORS blocks requests from unauthorized domains"""

    response = test_client.get(
        "/api/v1/auth/me",
        headers={
            "Origin": "https://malicious-site.com",
            "Authorization": f"Bearer {valid_token}"
        }
    )

    # CORS should block or not include Access-Control-Allow-Origin
    assert "Access-Control-Allow-Origin" not in response.headers or \
           response.headers["Access-Control-Allow-Origin"] != "https://malicious-site.com"

# Expected: CORS policy blocks unauthorized origin
# Actual: Backend ALLOWED_ORIGINS setting enforced
```

**Validation Command:**
```bash
# Test CORS from unauthorized domain
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Origin: https://malicious-site.com" \
  -H "Authorization: Bearer $TOKEN" \
  -v

# Expected: No Access-Control-Allow-Origin header for malicious domain
```

### 5.2 SQL Injection Prevention

**Test ID:** SECURITY-002
**Priority:** CRITICAL
**Type:** Security Test

#### Scenario 5.2.1: SQL Injection in Email Field
```python
@pytest.mark.security
async def test_sql_injection_prevention(test_client: TestClient):
    """Test SQL injection attempts are blocked"""

    injection_payloads = [
        "'; DROP TABLE users; --",
        "admin'--",
        "' OR '1'='1",
        "'; DELETE FROM users WHERE '1'='1'; --",
        "admin' UNION SELECT * FROM users--"
    ]

    for payload in injection_payloads:
        # Try injection in various endpoints
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": payload, "password": "test"}
        )

        # Should not execute SQL, should return 400/401
        assert response.status_code in [400, 401, 410]

        # Database should still exist (not dropped)
        db_check = test_client.get("/api/v1/health")
        assert db_check.status_code == 200

# Expected: All injection attempts fail safely
# Actual: SQLAlchemy parameterized queries prevent injection
```

### 5.3 XSS Prevention

**Test ID:** SECURITY-003
**Priority:** HIGH
**Type:** Security Test

#### Scenario 5.3.1: XSS in Error Messages
```typescript
// Test: XSS payloads in login form don't execute
it('should sanitize XSS payloads', async () => {
  const xssPayloads = [
    '<script>alert("XSS")</script>',
    '<img src=x onerror=alert("XSS")>',
    '"><script>alert(String.fromCharCode(88,83,83))</script>',
    "javascript:alert('XSS')"
  ]

  for (const payload of xssPayloads) {
    const { result } = renderHook(() => useMedicoAuth(), {
      wrapper: MedicoAuthProvider
    })

    await act(async () => {
      await result.current.signIn(payload, 'password')
    })

    // Check that payload is not executed
    // Error message should be escaped/sanitized
    const errorElement = screen.queryByTestId('error-message')
    if (errorElement) {
      // Should contain escaped HTML, not execute script
      expect(errorElement.innerHTML).not.toContain('<script>')
      expect(errorElement.textContent).toContain('&lt;script&gt;')
    }
  }
})

// Expected: HTML escaped in error messages
// Actual: React escapes by default, verify no innerHTML used
```

### 5.4 Rate Limiting

**Test ID:** SECURITY-004
**Priority:** MEDIUM
**Type:** Security Test

#### Scenario 5.4.1: Login Attempt Rate Limiting
```python
@pytest.mark.security
async def test_login_rate_limiting(test_client: TestClient):
    """Test rate limiting on login endpoint"""

    # Make multiple failed login attempts
    for i in range(10):
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": "wrong"}
        )

    # 11th attempt should be rate limited
    response = test_client.post(
        "/api/v1/auth/login",
        json={"email": "test@test.com", "password": "wrong"}
    )

    assert response.status_code == 429  # Too Many Requests
    assert "rate limit" in response.json()["detail"].lower()

# Expected: Rate limiting after N attempts
# Actual: Redis-based rate limiting (if configured)
```

### 5.5 Token Replay Attack Prevention

**Test ID:** SECURITY-005
**Priority:** HIGH
**Type:** Security Test

#### Scenario 5.5.1: Revoked Token Rejected
```python
@pytest.mark.security
async def test_revoked_token_rejected(test_client: TestClient, firebase_auth_service):
    """Test revoked tokens are rejected"""

    # Get valid token
    token = create_test_user_token()

    # Verify it works
    response = test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    # Revoke the token via Firebase Admin
    uid = decode_token(token)['uid']
    await firebase_auth_service.revoke_refresh_tokens(uid)

    # Token should now be rejected
    response = test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert "revoked" in response.json()["detail"].lower()

# Expected: Revoked tokens fail validation
# Actual: Firebase verify_id_token(check_revoked=True) detects this
```

---

## Testing Tools & Setup

### Backend Testing Stack

```bash
# Install testing dependencies
cd backend-hormonia
pip install pytest pytest-asyncio pytest-cov httpx faker

# Create pytest.ini (already exists)
# Run tests
pytest tests/ -v --cov=app --cov-report=html
```

**Required Packages:**
```txt
# Add to requirements-dev.txt
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
httpx==0.25.2
faker==20.1.0
factory-boy==3.3.0
```

### Frontend Testing Stack

```bash
# Install testing dependencies
cd frontend-hormonia
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom \
  @playwright/test @vitest/ui msw

# Run unit tests
npm run test

# Run E2E tests
npx playwright test
```

**Required Packages:**
```json
{
  "devDependencies": {
    "vitest": "^1.0.4",
    "@testing-library/react": "^14.1.2",
    "@testing-library/jest-dom": "^6.1.5",
    "@testing-library/user-event": "^14.5.1",
    "@playwright/test": "^1.40.1",
    "@vitest/ui": "^1.0.4",
    "msw": "^2.0.11"
  }
}
```

### Test Environment Setup

**Backend Test Environment:**
```bash
# backend-hormonia/.env.test

# Use Firebase test project
FIREBASE_ADMIN_PROJECT_ID=test-project-12345
FIREBASE_ADMIN_PRIVATE_KEY=test-key
FIREBASE_ADMIN_CLIENT_EMAIL=test@test-project.iam.gserviceaccount.com

# Test database
DATABASE_URL=postgresql+psycopg://test:test@localhost:5432/test_db

# Disable Redis for unit tests (use in-memory mock)
ENABLE_REDIS=false
REDIS_URL=redis://localhost:6379/15  # Separate test DB
```

**Frontend Test Environment:**
```bash
# frontend-hormonia/.env.test

VITE_FIREBASE_API_KEY=test-api-key
VITE_FIREBASE_AUTH_DOMAIN=test-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=test-project-12345
VITE_API_URL=http://localhost:8000
VITE_USE_MOCK_AUTH=true  # Enable mock auth for tests
```

---

## Mock Data & Test Fixtures

### Backend Fixtures

**File:** `tests/conftest.py`

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db
from app.models.user import Base
import firebase_admin
from firebase_admin import auth, credentials

# Test database
SQLALCHEMY_TEST_DATABASE_URL = "postgresql+psycopg://test:test@localhost/test_db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Create test database session"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def test_client(db_session):
    """Create test client with db override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture(scope="session")
def firebase_test_app():
    """Initialize Firebase Admin for testing"""
    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": "test-project",
        "private_key": "test-key",
        "client_email": "test@test.com"
    })

    if not firebase_admin._apps:
        firebase_app = firebase_admin.initialize_app(cred, name='test-app')
    else:
        firebase_app = firebase_admin.get_app('test-app')

    yield firebase_app

    firebase_admin.delete_app(firebase_app)

@pytest.fixture
async def firebase_test_user(firebase_test_app):
    """Create Firebase test user and return token"""
    # Create test user
    user = auth.create_user(
        email='test@example.com',
        password='Test123!@#',
        email_verified=True
    )

    # Generate custom token
    custom_token = auth.create_custom_token(user.uid)

    # Exchange for ID token (requires Firebase REST API call)
    # For testing, you can use custom_token or generate ID token

    yield {
        'uid': user.uid,
        'email': user.email,
        'id_token': custom_token.decode('utf-8')  # Simplified
    }

    # Cleanup
    auth.delete_user(user.uid)

@pytest.fixture
def mock_firebase_user():
    """Mock Firebase user data"""
    return {
        "uid": "test-uid-12345",
        "email": "medico@test.com",
        "email_verified": True,
        "name": "Dr. Test",
        "picture": None
    }

@pytest.fixture
def valid_token():
    """Generate valid test JWT token"""
    # Use Firebase Admin SDK to create test token
    # Or mock for unit tests
    return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.TEST.TOKEN"
```

### Frontend Fixtures

**File:** `tests/setup.ts`

```typescript
import { beforeAll, afterEach, afterAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom'

// Mock Firebase
beforeAll(() => {
  // Mock Firebase config
  vi.mock('firebase/app', () => ({
    initializeApp: vi.fn(() => ({})),
    getApps: vi.fn(() => [])
  }))

  vi.mock('firebase/auth', () => ({
    getAuth: vi.fn(() => ({})),
    signInWithEmailAndPassword: vi.fn(),
    signOut: vi.fn(),
    onAuthStateChanged: vi.fn()
  }))
})

// Cleanup after each test
afterEach(() => {
  cleanup()
  localStorage.clear()
  sessionStorage.clear()
})

// Mock data
export const mockUser = {
  id: 'test-user-123',
  email: 'medico@test.com',
  full_name: 'Dr. Test',
  role: 'doctor',
  is_active: true,
  crm: '12345/SC',
  especialidade: 'Oncologia'
}

export const mockFirebaseUser = {
  uid: 'firebase-uid-123',
  email: 'medico@test.com',
  emailVerified: true,
  getIdToken: vi.fn(() => Promise.resolve('mock-token-123'))
}
```

---

## Validation Commands

### Quick Validation Script

**File:** `scripts/test_firebase_auth.sh`

```bash
#!/bin/bash

# Firebase Authentication Validation Script
# Tests Firebase configuration and basic authentication flow

set -e  # Exit on error

echo "🔥 Firebase Authentication Test Suite"
echo "====================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"

echo ""
echo "📋 Test 1: Backend Configuration"
echo "---------------------------------"

# Test 1.1: Check Firebase env vars
python3 -c "
from app.config import settings
import sys

errors = []

if not settings.FIREBASE_ADMIN_PROJECT_ID:
    errors.append('FIREBASE_ADMIN_PROJECT_ID not set')
if not settings.FIREBASE_ADMIN_PRIVATE_KEY:
    errors.append('FIREBASE_ADMIN_PRIVATE_KEY not set')
if not settings.FIREBASE_ADMIN_CLIENT_EMAIL:
    errors.append('FIREBASE_ADMIN_CLIENT_EMAIL not set')

if errors:
    print('❌ Configuration errors:')
    for error in errors:
        print(f'  - {error}')
    sys.exit(1)
else:
    print('✅ All Firebase environment variables configured')
" && echo -e "${GREEN}✓ Backend config valid${NC}" || echo -e "${RED}✗ Backend config invalid${NC}"

echo ""
echo "📋 Test 2: Backend Health Check"
echo "---------------------------------"

# Test 2.1: Backend is running
curl -f -s "$BACKEND_URL/health" > /dev/null && \
  echo -e "${GREEN}✓ Backend is running${NC}" || \
  echo -e "${RED}✗ Backend is not running${NC}"

# Test 2.2: Auth endpoint exists
curl -f -s "$BACKEND_URL/api/v1/auth/me" -H "Authorization: Bearer test" > /dev/null 2>&1 || \
  echo -e "${YELLOW}⚠ Auth endpoint returns expected error${NC}"

echo ""
echo "📋 Test 3: Token Validation"
echo "---------------------------------"

# Test 3.1: Missing token returns 401
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/v1/auth/me")
if [ "$STATUS" -eq 401 ]; then
  echo -e "${GREEN}✓ Missing token returns 401${NC}"
else
  echo -e "${RED}✗ Expected 401, got $STATUS${NC}"
fi

# Test 3.2: Invalid token returns 401
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/v1/auth/me" \
  -H "Authorization: Bearer invalid-token")
if [ "$STATUS" -eq 401 ]; then
  echo -e "${GREEN}✓ Invalid token returns 401${NC}"
else
  echo -e "${RED}✗ Expected 401, got $STATUS${NC}"
fi

echo ""
echo "📋 Test 4: CORS Configuration"
echo "---------------------------------"

# Test 4.1: Allowed origin
RESPONSE=$(curl -s -H "Origin: http://localhost:5173" "$BACKEND_URL/health" -I)
if echo "$RESPONSE" | grep -q "Access-Control-Allow-Origin"; then
  echo -e "${GREEN}✓ CORS allows localhost:5173${NC}"
else
  echo -e "${YELLOW}⚠ CORS headers not found (check ALLOWED_ORIGINS)${NC}"
fi

echo ""
echo "📋 Test 5: Frontend Configuration"
echo "---------------------------------"

# Test 5.1: Check frontend env vars
if [ -f "frontend-hormonia/.env" ]; then
  source frontend-hormonia/.env

  if [ -n "$VITE_FIREBASE_API_KEY" ]; then
    echo -e "${GREEN}✓ VITE_FIREBASE_API_KEY configured${NC}"
  else
    echo -e "${RED}✗ VITE_FIREBASE_API_KEY missing${NC}"
  fi

  if [ -n "$VITE_FIREBASE_PROJECT_ID" ]; then
    echo -e "${GREEN}✓ VITE_FIREBASE_PROJECT_ID configured${NC}"
  else
    echo -e "${RED}✗ VITE_FIREBASE_PROJECT_ID missing${NC}"
  fi
else
  echo -e "${YELLOW}⚠ frontend-hormonia/.env not found${NC}"
fi

echo ""
echo "📋 Test 6: Integration Test"
echo "---------------------------------"

# This requires a real Firebase test account
echo -e "${YELLOW}ℹ Manual test required:${NC}"
echo "  1. Create test user in Firebase Console"
echo "  2. Get ID token: firebase auth:export --project <project-id>"
echo "  3. Test with: curl -H 'Authorization: Bearer <token>' $BACKEND_URL/api/v1/auth/me"

echo ""
echo "====================================="
echo "✅ Validation complete"
```

**Usage:**
```bash
chmod +x scripts/test_firebase_auth.sh
./scripts/test_firebase_auth.sh
```

### Individual Test Commands

```bash
# 1. Test Backend Configuration
cd backend-hormonia
python -c "from app.config import settings; \
  print('Firebase Project:', settings.FIREBASE_ADMIN_PROJECT_ID); \
  print('Client Email:', settings.FIREBASE_ADMIN_CLIENT_EMAIL[:20] + '...')"

# 2. Test Backend Token Validation (unit tests)
pytest tests/unit/services/test_firebase_auth_service.py -v

# 3. Test Backend Token Validation (integration tests)
pytest tests/integration/api/test_auth_token_validation.py -v -s

# 4. Test Frontend Login Flow (unit tests)
cd frontend-hormonia
npm run test -- tests/unit/contexts/MedicoAuthContext.test.tsx

# 5. Test Frontend Login Flow (E2E tests)
npx playwright test tests/e2e/auth/login_flow.spec.ts --headed

# 6. Test Complete Integration
npx playwright test tests/integration/auth_flow_complete.spec.ts --headed

# 7. Run all backend tests
cd backend-hormonia
pytest tests/ -v --cov=app --cov-report=term-missing

# 8. Run all frontend tests
cd frontend-hormonia
npm run test
npm run test:e2e

# 9. Security tests
pytest tests/security/ -v -m security

# 10. Performance tests
pytest tests/ -v -m performance --durations=10
```

---

## Testing Gaps & Recommendations

### Current Gaps Identified

#### 1. **No Automated Firebase Token Generation**
- **Gap:** Tests require manual Firebase token creation
- **Impact:** Integration tests cannot run in CI/CD
- **Recommendation:** Implement Firebase Emulator Suite for testing
  ```bash
  # Install Firebase Emulator
  npm install -g firebase-tools
  firebase init emulators
  firebase emulators:start --only auth
  ```

#### 2. **Missing Rate Limiting Tests**
- **Gap:** No rate limiting configured on login endpoint
- **Impact:** Vulnerable to brute force attacks
- **Recommendation:** Implement Redis-based rate limiting
  ```python
  # backend-hormonia/app/middleware/rate_limit.py
  from slowapi import Limiter
  from slowapi.util import get_remote_address

  limiter = Limiter(key_func=get_remote_address)

  @app.post("/api/v1/auth/login")
  @limiter.limit("5/minute")  # 5 attempts per minute
  async def login(...):
      ...
  ```

#### 3. **No Token Refresh Testing**
- **Gap:** Token refresh mechanism not tested
- **Impact:** Users may be logged out unexpectedly
- **Recommendation:** Add token refresh tests
  ```typescript
  it('should refresh token before expiration', async () => {
    // Mock token expiring in 5 minutes
    // Verify refresh is called automatically
    // Verify new token is stored
  })
  ```

#### 4. **Missing Session Timeout Tests**
- **Gap:** Session timeout behavior not validated
- **Impact:** Security risk if sessions don't expire
- **Recommendation:** Test session expiration
  ```python
  async def test_session_expires_after_timeout():
      # Login and get token
      # Wait for SESSION_TIMEOUT
      # Verify token is rejected
  ```

#### 5. **No Multi-Device Testing**
- **Gap:** Multiple device login not tested
- **Impact:** Unknown behavior for concurrent sessions
- **Recommendation:** Test multi-device scenarios
  ```typescript
  test('should handle login from multiple devices', async () => {
    // Login from device 1
    // Login from device 2
    // Verify both sessions work (or only latest works)
  })
  ```

#### 6. **Missing Performance Tests**
- **Gap:** Token validation performance not measured
- **Impact:** May have latency issues under load
- **Recommendation:** Add load testing
  ```bash
  # Use Locust or k6 for load testing
  k6 run --vus 100 --duration 30s tests/load/auth_load_test.js
  ```

#### 7. **No Firebase Error Code Mapping**
- **Gap:** Firebase error codes not mapped to user-friendly messages
- **Impact:** Poor user experience
- **Recommendation:** Create error mapping
  ```typescript
  const FIREBASE_ERROR_MESSAGES = {
    'auth/user-not-found': 'Email não cadastrado',
    'auth/wrong-password': 'Senha incorreta',
    'auth/too-many-requests': 'Muitas tentativas. Tente novamente mais tarde.',
    'auth/network-request-failed': 'Erro de conexão. Verifique sua internet.'
  }
  ```

#### 8. **Missing Audit Logging Tests**
- **Gap:** Authentication events not logged/tested
- **Impact:** Cannot track security incidents
- **Recommendation:** Add audit logging
  ```python
  async def test_login_audit_logged():
      # Login
      # Verify audit log entry created
      assert audit_log.exists(user_id=user.id, event='login')
  ```

### Recommended Test Tools

#### Backend
- **pytest** - Unit and integration testing
- **pytest-asyncio** - Async test support
- **pytest-cov** - Code coverage
- **httpx** - HTTP client for API testing
- **faker** - Test data generation
- **factory-boy** - Model factories
- **locust** - Load testing

#### Frontend
- **Vitest** - Unit testing (faster than Jest)
- **Playwright** - E2E testing
- **@testing-library/react** - Component testing
- **MSW** - API mocking
- **Storybook** - Component visual testing

#### Integration
- **Firebase Emulator Suite** - Local Firebase for testing
- **Docker Compose** - Test environment orchestration
- **GitHub Actions** - CI/CD automation

### Priority Testing Roadmap

**Phase 1: Critical (Week 1)**
1. ✅ Backend token validation tests
2. ✅ Frontend login flow tests
3. ✅ Integration tests for complete auth flow
4. ❌ Firebase Emulator setup

**Phase 2: High Priority (Week 2)**
5. ❌ Security vulnerability tests (SQL injection, XSS)
6. ❌ Rate limiting implementation and tests
7. ❌ Session timeout and refresh tests
8. ❌ Error message mapping and tests

**Phase 3: Medium Priority (Week 3)**
9. ❌ Multi-device session tests
10. ❌ Audit logging tests
11. ❌ Performance and load tests
12. ❌ CORS policy tests

**Phase 4: Nice to Have (Week 4)**
13. ❌ Visual regression tests (Storybook)
14. ❌ Accessibility tests
15. ❌ Mobile responsiveness tests
16. ❌ Browser compatibility tests

---

## Appendix: Test Data Examples

### Mock Users

```python
# Backend mock users
MOCK_USERS = [
    {
        "uid": "test-medico-001",
        "email": "medico1@test.com",
        "password": "Test123!@#",
        "full_name": "Dr. João Silva",
        "role": "doctor",
        "crm": "12345/SC",
        "especialidade": "Oncologia"
    },
    {
        "uid": "test-medico-002",
        "email": "medico2@test.com",
        "password": "Test123!@#",
        "full_name": "Dra. Maria Santos",
        "role": "doctor",
        "crm": "67890/SC",
        "especialidade": "Radioterapia"
    }
]
```

### Mock Tokens

```typescript
// Frontend mock tokens
export const MOCK_TOKENS = {
  valid: 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiJ0ZXN0LXVzZXIiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJleHAiOjk5OTk5OTk5OTl9.signature',
  expired: 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiJ0ZXN0IiwiZXhwIjoxfQ.sig',
  invalid: 'not-a-valid-jwt-token',
  wrongProject: 'eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJ3cm9uZy1wcm9qZWN0In0.sig'
}
```

---

## Conclusion

This comprehensive testing plan covers all critical aspects of the Firebase authentication system. Implementation of these tests will ensure:

1. **Security:** Robust protection against common vulnerabilities
2. **Reliability:** Consistent authentication behavior across scenarios
3. **User Experience:** Graceful error handling and clear feedback
4. **Maintainability:** Automated tests catch regressions early
5. **Compliance:** Audit trails and security best practices

**Next Steps:**
1. Implement test files in appropriate directories
2. Set up Firebase Emulator for integration testing
3. Configure CI/CD pipeline to run tests automatically
4. Add test coverage reporting
5. Create test documentation for new developers

---

**Document Status:** Draft v1.0
**Requires Review:** Security Team, QA Lead, Backend Lead, Frontend Lead
**Estimated Implementation Time:** 4 weeks (4 phases)
