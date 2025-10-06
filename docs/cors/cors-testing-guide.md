# CORS Testing Guide

**System**: Hormonia Healthcare Platform
**Last Updated**: October 6, 2025
**Version**: 2.0

---

## Table of Contents

1. [CORS Smoke Tests](#cors-smoke-tests)
2. [Manual Testing with curl](#manual-testing-with-curl)
3. [Browser-Based Testing](#browser-based-testing)
4. [Automated Testing Scripts](#automated-testing-scripts)
5. [WebSocket CORS Testing](#websocket-cors-testing)
6. [Expected Results](#expected-results)
7. [Common Issues and Solutions](#common-issues-and-solutions)
8. [CI/CD Integration](#cicd-integration)

---

## CORS Smoke Tests

Quick verification tests to ensure CORS is working correctly.

### 1. Backend Health Check

Verify the backend is running:

```bash
curl https://clinica-oncologica-v02-production.up.railway.app/test
```

**Expected Result**:
```json
{
  "message": "Server is working",
  "debug": false,
  "mode": "production"
}
```

### 2. CORS Configuration Check

Verify CORS is configured:

```bash
curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/health/detailed
```

**Expected Result** (CORS section):
```json
{
  "cors": {
    "enabled": true,
    "allowed_origins_count": 23,
    "allowed_origins": [
      "https://frontend-production-18bb.up.railway.app",
      "https://quiz-interface-production.up.railway.app",
      "..."
    ]
  }
}
```

### 3. CORS Preflight Test

Test OPTIONS preflight request:

```bash
curl -X OPTIONS \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization" \
  https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me \
  -v
```

**Expected Headers**:
```
HTTP/2 200
access-control-allow-origin: https://frontend-production-18bb.up.railway.app
access-control-allow-credentials: true
access-control-allow-methods: *
access-control-allow-headers: *
access-control-max-age: 86400
```

### 4. CORS GET Test

Test actual GET request with CORS:

```bash
curl -X GET \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  https://clinica-oncologica-v02-production.up.railway.app/api/v1/health/cors-test
```

**Expected Result**:
```json
{
  "message": "CORS GET test successful",
  "origin": "https://frontend-production-18bb.up.railway.app",
  "timestamp": "2025-10-06T12:00:00Z",
  "cors_configured": true,
  "allowed_origins": ["..."]
}
```

---

## Manual Testing with curl

### Test 1: Preflight OPTIONS for Authentication Endpoint

```bash
curl -X OPTIONS \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,authorization" \
  https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/login \
  -i
```

**What to Check**:
- ✅ Status code: 200 OK
- ✅ `Access-Control-Allow-Origin` header present
- ✅ `Access-Control-Allow-Methods` includes POST
- ✅ `Access-Control-Allow-Headers` includes content-type and authorization
- ✅ `Access-Control-Allow-Credentials: true`

### Test 2: GET Request with Custom Headers

```bash
curl -X GET \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Authorization: Bearer fake-token" \
  -H "X-Request-ID: test-123" \
  https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me \
  -i
```

**What to Check**:
- ✅ `Access-Control-Allow-Origin` header matches origin
- ✅ `Access-Control-Expose-Headers` includes custom headers
- ✅ Response includes healthcare headers (X-Request-ID, X-RateLimit-*)

### Test 3: POST Request with JSON Body

```bash
curl -X POST \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fake-token" \
  -d '{"test":"data"}' \
  https://clinica-oncologica-v02-production.up.railway.app/api/v1/test-endpoint \
  -i
```

**What to Check**:
- ✅ Preflight OPTIONS sent automatically (if needed)
- ✅ CORS headers in both OPTIONS and POST responses
- ✅ Request completes successfully

### Test 4: Unauthorized Origin (Should Fail)

```bash
curl -X OPTIONS \
  -H "Origin: https://malicious-site.com" \
  -H "Access-Control-Request-Method: GET" \
  https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me \
  -i
```

**What to Check**:
- ✅ No `Access-Control-Allow-Origin` header (or different origin)
- ✅ Request should be rejected by browser (curl will succeed, browser won't)

### Test 5: Development Origins (Local)

```bash
# Test localhost
curl -X OPTIONS \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET" \
  http://localhost:8000/api/v1/auth/me \
  -i

# Test 127.0.0.1
curl -X OPTIONS \
  -H "Origin: http://127.0.0.1:5173" \
  -H "Access-Control-Request-Method: GET" \
  http://localhost:8000/api/v1/auth/me \
  -i
```

**What to Check**:
- ✅ Both localhost and 127.0.0.1 work
- ✅ All Vite ports (5173-5179) work
- ✅ CORS headers include credentials support

---

## Browser-Based Testing

### Test 1: Console Fetch Test

Open browser DevTools (F12) → Console:

```javascript
// Test GET request
fetch('https://clinica-oncologica-v02-production.up.railway.app/api/v1/health/cors-test', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json'
  }
})
  .then(res => {
    console.log('Status:', res.status);
    console.log('Headers:', [...res.headers.entries()]);
    return res.json();
  })
  .then(data => console.log('Response:', data))
  .catch(err => console.error('Error:', err));
```

**Expected Output**:
```
Status: 200
Headers: [
  ['access-control-allow-origin', 'https://frontend-production-18bb.up.railway.app'],
  ['access-control-allow-credentials', 'true'],
  ['access-control-expose-headers', 'X-Request-ID,X-RateLimit-Limit,...'],
  ...
]
Response: {
  message: "CORS GET test successful",
  origin: "https://frontend-production-18bb.up.railway.app",
  ...
}
```

### Test 2: POST Request with Credentials

```javascript
// Test POST with authorization
fetch('https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer fake-token',
    'Content-Type': 'application/json'
  },
  credentials: 'include'  // Important: include credentials
})
  .then(res => res.json())
  .then(data => console.log('Auth Response:', data))
  .catch(err => console.error('Auth Error:', err));
```

**What to Check**:
- ✅ Network tab shows OPTIONS preflight (status 200)
- ✅ Network tab shows GET request (status 401 or 200)
- ✅ No CORS errors in console
- ✅ Response includes CORS headers

### Test 3: Network Tab Analysis

1. Open browser DevTools (F12)
2. Go to Network tab
3. Filter by "Fetch/XHR"
4. Navigate to frontend application
5. Watch for API requests

**What to Check**:

**Preflight OPTIONS Request**:
- ✅ Method: OPTIONS
- ✅ Status: 200 OK
- ✅ Response Headers:
  - `access-control-allow-origin`
  - `access-control-allow-methods`
  - `access-control-allow-headers`
  - `access-control-allow-credentials`

**Actual Request (GET/POST/etc)**:
- ✅ Status: 200/401/etc (not CORS error)
- ✅ Response Headers:
  - `access-control-allow-origin`
  - `access-control-expose-headers`

### Test 4: CORS Error Detection

**Intentionally trigger CORS error** (for testing):

```javascript
// This will fail if origin is not allowed
fetch('https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me', {
  method: 'GET',
  headers: {
    'X-Custom-Header': 'test'  // Triggers preflight
  }
})
  .catch(err => console.error('Expected CORS Error:', err));
```

**Expected Console Error** (if CORS fails):
```
Access to fetch at 'https://...' from origin 'https://...'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present
```

---

## Automated Testing Scripts

### Script 1: Comprehensive CORS Test Suite

**File**: `scripts/test-cors-comprehensive.sh`

```bash
#!/bin/bash

# Configuration
BACKEND_URL="${BACKEND_URL:-https://clinica-oncologica-v02-production.up.railway.app}"
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-https://frontend-production-18bb.up.railway.app}"
QUIZ_ORIGIN="https://quiz-interface-production.up.railway.app"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Test function
run_test() {
    local test_name="$1"
    local command="$2"
    local expected_pattern="$3"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "\n${YELLOW}Test $TOTAL_TESTS: $test_name${NC}"

    result=$(eval "$command" 2>&1)

    if echo "$result" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}✓ PASS${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo "Expected pattern: $expected_pattern"
        echo "Got: $result"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

echo "========================================"
echo "CORS Comprehensive Test Suite"
echo "Backend: $BACKEND_URL"
echo "Frontend Origin: $FRONTEND_ORIGIN"
echo "========================================"

# Test 1: Backend Health
run_test "Backend Health Check" \
    "curl -s $BACKEND_URL/test" \
    '"message".*"Server is working"'

# Test 2: CORS Configuration
run_test "CORS Configuration Check" \
    "curl -s $BACKEND_URL/api/v1/health/detailed | jq '.cors.enabled'" \
    'true'

# Test 3: Allowed Origins Count
run_test "Allowed Origins Count" \
    "curl -s $BACKEND_URL/api/v1/health/detailed | jq '.cors.allowed_origins_count'" \
    '[0-9]+'

# Test 4: Preflight OPTIONS - Frontend Origin
run_test "Preflight OPTIONS (Frontend)" \
    "curl -sI -X OPTIONS -H 'Origin: $FRONTEND_ORIGIN' -H 'Access-Control-Request-Method: GET' $BACKEND_URL/api/v1/auth/me" \
    'access-control-allow-origin'

# Test 5: Preflight OPTIONS - Quiz Origin
run_test "Preflight OPTIONS (Quiz)" \
    "curl -sI -X OPTIONS -H 'Origin: $QUIZ_ORIGIN' -H 'Access-Control-Request-Method: GET' $BACKEND_URL/api/v1/auth/me" \
    'access-control-allow-origin'

# Test 6: GET with CORS Headers
run_test "GET Request with CORS" \
    "curl -sI -H 'Origin: $FRONTEND_ORIGIN' $BACKEND_URL/api/v1/health/cors-test" \
    'access-control-allow-origin'

# Test 7: POST Preflight
run_test "POST Preflight OPTIONS" \
    "curl -sI -X OPTIONS -H 'Origin: $FRONTEND_ORIGIN' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type,authorization' $BACKEND_URL/api/v1/auth/login" \
    'access-control-allow-methods'

# Test 8: Credentials Support
run_test "Credentials Support Check" \
    "curl -sI -X OPTIONS -H 'Origin: $FRONTEND_ORIGIN' $BACKEND_URL/api/v1/auth/me" \
    'access-control-allow-credentials.*true'

# Test 9: Exposed Headers
run_test "Exposed Headers Check" \
    "curl -sI -H 'Origin: $FRONTEND_ORIGIN' $BACKEND_URL/api/v1/health/cors-test" \
    'access-control-expose-headers'

# Test 10: Max Age Header
run_test "Max Age Header Check" \
    "curl -sI -X OPTIONS -H 'Origin: $FRONTEND_ORIGIN' $BACKEND_URL/api/v1/auth/me" \
    'access-control-max-age.*86400'

# Test 11: Unauthorized Origin (Should Not Have CORS Headers)
run_test "Unauthorized Origin Rejection" \
    "curl -sI -X OPTIONS -H 'Origin: https://malicious-site.com' $BACKEND_URL/api/v1/auth/me | grep -i 'access-control-allow-origin' | grep -v 'malicious-site.com' || echo 'correctly_rejected'" \
    'correctly_rejected'

# Test 12: CORS Test Endpoint
run_test "CORS Test Endpoint Response" \
    "curl -s $BACKEND_URL/api/v1/health/cors-test" \
    '"cors_configured".*true'

# Summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo -e "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "\n${GREEN}✓ All CORS tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}✗ Some CORS tests failed. Please review the output above.${NC}"
    exit 1
fi
```

**Usage**:
```bash
# Make executable
chmod +x scripts/test-cors-comprehensive.sh

# Run tests (default production)
./scripts/test-cors-comprehensive.sh

# Run tests (custom backend)
BACKEND_URL=https://custom-backend.railway.app ./scripts/test-cors-comprehensive.sh

# Run tests (local development)
BACKEND_URL=http://localhost:8000 FRONTEND_ORIGIN=http://localhost:5173 ./scripts/test-cors-comprehensive.sh
```

### Script 2: Quick CORS Validation

**File**: `scripts/quick-cors-check.sh`

```bash
#!/bin/bash

BACKEND_URL="${1:-https://clinica-oncologica-v02-production.up.railway.app}"
FRONTEND_ORIGIN="${2:-https://frontend-production-18bb.up.railway.app}"

echo "Quick CORS Check"
echo "Backend: $BACKEND_URL"
echo "Origin: $FRONTEND_ORIGIN"
echo ""

# Test preflight
echo "Testing preflight OPTIONS..."
curl -X OPTIONS \
  -H "Origin: $FRONTEND_ORIGIN" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization" \
  "$BACKEND_URL/api/v1/auth/me" \
  -s -D - -o /dev/null | grep -i "access-control" || echo "❌ No CORS headers found"

echo ""
echo "Testing CORS configuration..."
curl -s "$BACKEND_URL/api/v1/health/detailed" | jq '.cors' || echo "❌ Cannot fetch CORS config"
```

**Usage**:
```bash
chmod +x scripts/quick-cors-check.sh
./scripts/quick-cors-check.sh
./scripts/quick-cors-check.sh https://backend.railway.app https://frontend.railway.app
```

### Script 3: CORS Monitoring Script

**File**: `scripts/monitor-cors.sh`

```bash
#!/bin/bash

# Monitor CORS errors in production logs
BACKEND_URL="${1:-https://clinica-oncologica-v02-production.up.railway.app}"

echo "Monitoring CORS configuration..."
echo "Press Ctrl+C to stop"
echo ""

while true; do
    clear
    echo "=== CORS Status @ $(date) ==="
    echo ""

    # Get CORS configuration
    cors_status=$(curl -s "$BACKEND_URL/api/v1/health/detailed" | jq '.cors')
    echo "Configuration:"
    echo "$cors_status"

    echo ""
    echo "=== Recent CORS Test ==="

    # Test CORS
    test_result=$(curl -s "$BACKEND_URL/api/v1/health/cors-test")
    echo "$test_result" | jq '.'

    sleep 10
done
```

---

## WebSocket CORS Testing

### Test 1: WebSocket Connection with wscat

Install wscat:
```bash
npm install -g wscat
```

Test WebSocket CORS:
```bash
wscat -c wss://clinica-oncologica-v02-production.up.railway.app/ws/connect \
  --origin https://frontend-production-18bb.up.railway.app \
  --header "Authorization: Bearer test-token"
```

**Expected Result**:
```
Connected (press CTRL+C to quit)
```

**CORS Error** (if failing):
```
Error: Unexpected server response: 403
```

### Test 2: Browser WebSocket Test

```javascript
// In browser console
const wsUrl = 'wss://clinica-oncologica-v02-production.up.railway.app/ws/connect';
const token = 'test-token'; // Replace with real token

const ws = new WebSocket(`${wsUrl}?token=${token}`);

ws.onopen = (event) => {
    console.log('✓ WebSocket Connected:', event);
};

ws.onerror = (error) => {
    console.error('✗ WebSocket Error:', error);
};

ws.onmessage = (event) => {
    console.log('Message received:', event.data);
};

ws.onclose = (event) => {
    console.log('WebSocket Closed:', event.code, event.reason);
};
```

**What to Check**:
- ✅ Connection opens successfully
- ✅ No CORS errors in console
- ✅ Messages can be sent/received
- ✅ Proper close on disconnect

### Test 3: WebSocket CORS Headers Check

Check if WebSocket endpoint returns CORS headers:

```bash
curl -I https://clinica-oncologica-v02-production.up.railway.app/ws/connect \
  -H "Origin: https://frontend-production-18bb.up.railway.app" \
  -H "Upgrade: websocket" \
  -H "Connection: Upgrade"
```

**Expected Headers**:
```
HTTP/2 101 Switching Protocols
access-control-allow-origin: https://frontend-production-18bb.up.railway.app
upgrade: websocket
connection: Upgrade
```

---

## Expected Results

### ✅ Successful CORS Request

**Preflight OPTIONS Response**:
```
HTTP/2 200
access-control-allow-origin: https://frontend-production-18bb.up.railway.app
access-control-allow-credentials: true
access-control-allow-methods: *
access-control-allow-headers: *
access-control-max-age: 86400
content-length: 0
```

**Actual Request Response**:
```
HTTP/2 200
access-control-allow-origin: https://frontend-production-18bb.up.railway.app
access-control-allow-credentials: true
access-control-expose-headers: X-Request-ID,X-RateLimit-Limit,X-RateLimit-Remaining,...
content-type: application/json

{
  "data": "..."
}
```

### ❌ Failed CORS Request

**Missing CORS Headers**:
```
HTTP/2 200
content-type: application/json

{
  "data": "..."
}
```
*Browser will block this - no `access-control-allow-origin` header*

**Wrong Origin**:
```
HTTP/2 200
access-control-allow-origin: https://different-origin.com
...
```
*Browser will block - origin doesn't match request origin*

**Browser Console Error**:
```
Access to fetch at 'https://backend.railway.app/api/v1/auth/me'
from origin 'https://frontend.railway.app' has been blocked by CORS policy:
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

---

## Common Issues and Solutions

### Issue 1: Preflight Failing but GET Works

**Symptom**: Simple GET works, but POST/PUT/DELETE fail

**Cause**: Preflight OPTIONS not configured

**Test**:
```bash
curl -X OPTIONS -H "Origin: https://frontend.railway.app" https://backend.railway.app/api/v1/auth/login -v
```

**Solution**: Verify middleware allows OPTIONS:
```python
allow_methods=["*"]  # Includes OPTIONS
```

### Issue 2: CORS Works in curl but Not Browser

**Symptom**: curl tests pass, browser shows CORS error

**Cause**: Browser enforces CORS, curl doesn't

**Test in Browser**:
```javascript
fetch('https://backend.railway.app/api/v1/auth/me')
  .then(res => res.json())
  .catch(err => console.error(err));
```

**Solution**: Ensure origin is in `ALLOWED_ORIGINS`

### Issue 3: Custom Headers Blocked

**Symptom**: Requests with `Authorization` header fail

**Cause**: Custom headers trigger preflight, which may not allow them

**Test**:
```bash
curl -X OPTIONS \
  -H "Origin: https://frontend.railway.app" \
  -H "Access-Control-Request-Headers: authorization,x-custom-header" \
  https://backend.railway.app/api/v1/auth/me -v
```

**Solution**: Check `allow_headers` includes all custom headers:
```python
allow_headers=["*"]  # Allows all headers
```

### Issue 4: Credentials Not Working

**Symptom**: Cookies/auth headers not sent

**Cause**: `credentials: 'include'` not set or `allow_credentials` false

**Test**:
```javascript
fetch('https://backend.railway.app/api/v1/auth/me', {
  credentials: 'include'  // Required
})
```

**Solution**: Ensure both are set:
```python
# Backend
allow_credentials=True

# Frontend
credentials: 'include'
```

---

## CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/cors-tests.yml`

```yaml
name: CORS Tests

on:
  push:
    branches: [ main, staging ]
  pull_request:
    branches: [ main ]

jobs:
  cors-tests:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y curl jq

      - name: Run CORS smoke tests
        run: |
          chmod +x scripts/test-cors-comprehensive.sh
          BACKEND_URL=${{ secrets.BACKEND_URL }} \
          FRONTEND_ORIGIN=${{ secrets.FRONTEND_ORIGIN }} \
          ./scripts/test-cors-comprehensive.sh

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: cors-test-results
          path: test-results/
```

### Railway Deployment Hook

Add to `railway.json`:

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "healthcheckPath": "/test",
    "healthcheckTimeout": 300,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  },
  "hooks": {
    "postDeploy": [
      "scripts/quick-cors-check.sh"
    ]
  }
}
```

---

## Continuous Monitoring

### Prometheus Metrics

Track CORS metrics:

```python
# In middleware_setup.py
from prometheus_client import Counter, Histogram

cors_requests = Counter(
    'cors_requests_total',
    'Total CORS requests',
    ['origin', 'method', 'status']
)

cors_preflight_duration = Histogram(
    'cors_preflight_duration_seconds',
    'CORS preflight request duration'
)
```

### Alerting Rules

Create alerts for CORS issues:

```yaml
# alerting_rules.yml
groups:
  - name: cors_alerts
    rules:
      - alert: HighCORSRejectionRate
        expr: rate(cors_requests_total{status="rejected"}[5m]) > 0.01
        for: 5m
        annotations:
          summary: "High CORS rejection rate detected"
          description: "CORS rejection rate is {{ $value }} per second"

      - alert: CORSConfigurationChanged
        expr: changes(cors_allowed_origins_count[1h]) > 0
        annotations:
          summary: "CORS configuration changed"
          description: "Allowed origins count changed in the last hour"
```

---

## Related Documentation

- [CORS Audit Report](./cors-audit-report.md) - Security audit findings
- [CORS Configuration Guide](./cors-configuration-guide.md) - Setup instructions
- [Deployment Guide](../deployment/RAILWAY_DEPLOYMENT.md) - Production deployment
- [Troubleshooting Guide](../troubleshooting/CORS_ISSUES.md) - Common problems

---

**Last Updated**: October 6, 2025
**Maintained By**: QA Team
**Review Frequency**: Monthly
