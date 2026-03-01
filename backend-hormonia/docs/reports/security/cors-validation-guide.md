# CORS Validation Guide

**Version:** 1.0.0
**Last Updated:** 2025-01-16
**Priority:** P0

## Table of Contents

1. [Overview](#overview)
2. [Expected CORS Headers](#expected-cors-headers)
3. [Validation Tools](#validation-tools)
4. [Running Validations](#running-validations)
5. [Troubleshooting](#troubleshooting)
6. [CI/CD Integration](#cicd-integration)
7. [Monitoring](#monitoring)

## Overview

This guide provides comprehensive instructions for validating CORS (Cross-Origin Resource Sharing) configuration across all environments (local, staging, production).

### Why CORS Validation is Critical

- **Security:** Prevents unauthorized cross-origin access
- **Functionality:** Ensures frontend can communicate with API
- **Compliance:** Required for HIPAA audit trail
- **Production Readiness:** Validates deployment configuration

## Expected CORS Headers

### 1. Preflight OPTIONS Response

**Request:**
```http
OPTIONS /api/v2/patients HTTP/1.1
Origin: https://app.example.com
Access-Control-Request-Method: POST
Access-Control-Request-Headers: Content-Type,X-CSRF-Token
```

**Expected Response Headers:**
```http
HTTP/1.1 200 OK
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS
Access-Control-Allow-Headers: Content-Type, X-CSRF-Token, X-Request-ID, Authorization
Access-Control-Max-Age: 3600
Vary: Origin
```

### 2. Actual Request Response

**Request:**
```http
GET /api/v2/patients HTTP/1.1
Origin: https://app.example.com
Cookie: session_token=abc123
```

**Expected Response Headers:**
```http
HTTP/1.1 200 OK
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Credentials: true
Access-Control-Expose-Headers: X-Total-Count, X-Page-Count
Vary: Origin
```

### 3. Header Descriptions

| Header | Purpose | Expected Value |
|--------|---------|----------------|
| `Access-Control-Allow-Origin` | Specifies allowed origin | Exact origin from request (e.g., `https://app.example.com`) |
| `Access-Control-Allow-Credentials` | Allows cookies/auth headers | `true` |
| `Access-Control-Allow-Methods` | Allowed HTTP methods | `GET, POST, PUT, DELETE, PATCH, OPTIONS` |
| `Access-Control-Allow-Headers` | Allowed custom headers | `Content-Type, X-CSRF-Token, X-Request-ID, Authorization` |
| `Access-Control-Max-Age` | Preflight cache duration | `3600` (1 hour) |
| `Access-Control-Expose-Headers` | Headers accessible to JS | `X-Total-Count, X-Page-Count` |
| `Vary` | Cache key variation | `Origin` |

## Validation Tools

### 1. Shell Script (`validate-cors.sh`)

**Purpose:** Quick validation with detailed output

**Features:**
- Color-coded output
- 8 comprehensive tests
- Text report generation
- Exit code for CI/CD

**Location:** `backend-hormonia/scripts/validate-cors.sh`

### 2. Node.js Tool (`validate-cors.js`)

**Purpose:** Programmatic validation with JSON reporting

**Features:**
- Structured JSON output
- Detailed test results
- Pass rate calculation
- Integration-friendly

**Location:** `backend-hormonia/scripts/validate-cors.js`

### 3. Browser DevTools

**Purpose:** Manual validation during development

**Steps:**
1. Open browser DevTools (F12)
2. Go to Network tab
3. Make a request to the API
4. Check response headers
5. Verify CORS headers are present

## Running Validations

### Local Environment

**Prerequisites:**
```bash
# Start API server
cd backend-hormonia
uvicorn app.main:app --reload

# In another terminal, run validation
```

**Shell Script:**
```bash
cd backend-hormonia
chmod +x scripts/validate-cors.sh
./scripts/validate-cors.sh http://localhost:8000 http://localhost:5173
```

**Node.js Tool:**
```bash
cd backend-hormonia
npm install axios  # First time only
node scripts/validate-cors.js
```

**Expected Output:**
```
═══════════════════════════════════════════════════════════════
CORS Configuration Validation
═══════════════════════════════════════════════════════════════

Configuration:
  API URL: http://localhost:8000
  Frontend URL: http://localhost:5173
  Timestamp: 2025-01-16 10:30:45 Sao Paulo

ℹ INFO: API is reachable
✓ PASS: API is reachable

Test 1: Preflight OPTIONS Request
✓ PASS: Header 'Access-Control-Allow-Origin' = 'http://localhost:5173'
✓ PASS: Header 'Access-Control-Allow-Credentials' = 'true'
...

═══════════════════════════════════════════════════════════════
Test Summary
═══════════════════════════════════════════════════════════════

Total Tests: 8
Passed: 8
Failed: 0

✓ All CORS validations passed!
```

### Staging Environment

**Using GitHub Actions:**
```bash
# Trigger manual workflow
gh workflow run cors-validation.yml -f environment=staging
```

**Manual Validation:**
```bash
export API_URL="https://staging-api.example.com"
export FRONTEND_URL="https://staging-app.example.com"

./scripts/validate-cors.sh "$API_URL" "$FRONTEND_URL"
```

### Production Environment

**Using GitHub Actions (Recommended):**
```bash
# Requires 'production' environment approval
gh workflow run cors-validation.yml -f environment=production
```

**Manual Validation (Emergency Only):**
```bash
export API_URL="https://api.example.com"
export FRONTEND_URL="https://app.example.com"

# Use Node.js tool for non-intrusive validation
node scripts/validate-cors.js
```

## Troubleshooting

### Common Issues

#### Issue 1: Missing CORS Headers

**Symptom:**
```
✗ FAIL: Header 'Access-Control-Allow-Origin' not found
```

**Diagnosis:**
```bash
# Check CORS middleware is enabled
grep -r "CORSMiddleware" backend-hormonia/app/main.py

# Check allowed origins configuration
grep -r "CORS_ALLOWED_ORIGINS" backend-hormonia/app/config/
```

**Solution:**
```python
# app/main.py
from app.middleware.cors import setup_cors

app = FastAPI()
setup_cors(app)  # Ensure this is called
```

#### Issue 2: Wrong Origin in Response

**Symptom:**
```
✗ FAIL: Header 'Access-Control-Allow-Origin' = '*' (expected: https://app.example.com)
```

**Diagnosis:**
```bash
# Check CORS configuration
cat backend-hormonia/app/config/settings/security.py | grep CORS
```

**Solution:**
```python
# app/config/settings/security.py
CORS_ALLOWED_ORIGINS = [
    "https://app.example.com",
    "https://staging-app.example.com",
]

# NOT:
# CORS_ALLOWED_ORIGINS = ["*"]  # ❌ WRONG - Too permissive
```

#### Issue 3: Credentials Flag Missing

**Symptom:**
```
✗ FAIL: Header 'Access-Control-Allow-Credentials' = 'false'
```

**Solution:**
```python
# app/middleware/cors.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,  # Must be True
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Issue 4: Preflight Requests Failing

**Symptom:**
```
✗ FAIL: OPTIONS request returns 403 Forbidden
```

**Diagnosis:**
```bash
# Check if OPTIONS method is allowed
curl -X OPTIONS http://localhost:8000/api/v2/patients -v
```

**Solution:**
```python
# Ensure CSRF middleware doesn't block OPTIONS
# app/middleware/csrf.py
if request.method == "OPTIONS":
    return await call_next(request)
```

### Header Comparison Table

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Same-origin request | No CORS headers needed | Headers present | ✓ OK (defensive) |
| Allowed origin | `Access-Control-Allow-Origin: https://app.example.com` | Same | ✓ OK |
| Blocked origin | No CORS headers | No CORS headers | ✓ OK |
| Wildcard origin (`*`) | Never with credentials | `*` | ✗ FAIL |
| Credentials flag | `true` | `false` | ✗ FAIL |

### Debugging Commands

```bash
# Test specific endpoint
curl -v -X OPTIONS http://localhost:8000/api/v2/health \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET"

# Check allowed origins in environment
docker exec backend-hormonia env | grep CORS

# Validate CORS configuration
python -c "
from app.config.settings.security import CORS_ALLOWED_ORIGINS
print('Allowed origins:', CORS_ALLOWED_ORIGINS)
"

# Check middleware order
grep -A 10 "add_middleware" backend-hormonia/app/main.py
```

## CI/CD Integration

### GitHub Actions Workflow

**File:** `.github/workflows/cors-validation.yml`

**Trigger Conditions:**
- Pull requests modifying CORS files
- Push to main/develop branches
- Manual workflow dispatch

**Environments:**
- **Local:** Runs on every PR
- **Staging:** Manual trigger
- **Production:** Manual trigger with approval

### Viewing Results

**In GitHub Actions:**
1. Go to Actions tab
2. Select "CORS Validation" workflow
3. View run details
4. Download artifacts (reports)

**Artifacts:**
- `cors-validation-report.txt` - Human-readable report
- `cors-validation-report.json` - Machine-readable report

### Integration with Pull Requests

**Automatic Comment:**
```markdown
## CORS Validation Results

**Environment:** Local
**Timestamp:** 2025-01-16T10:30:45-03:00

### Summary
- **Total Tests:** 8
- **Passed:** 8 ✅
- **Failed:** 0 ❌
- **Warnings:** 0 ⚠️
- **Pass Rate:** 100%

✅ All CORS validations passed!
```

## Monitoring

### Prometheus Metrics

**File:** `backend-hormonia/monitoring/cors_metrics.yaml`

**Metrics:**
```yaml
# CORS header validation failures
cors_header_validation_failures_total{endpoint, origin}

# CORS preflight requests
cors_preflight_requests_total{endpoint, origin, status}

# Blocked origins
cors_blocked_origins_total{origin}
```

### Alerts

**File:** `backend-hormonia/monitoring/alert_rules.yaml`

**Alert Rules:**
```yaml
groups:
  - name: cors_alerts
    rules:
      - alert: CORSHeaderMissing
        expr: cors_header_validation_failures_total > 0
        for: 5m
        annotations:
          summary: "CORS header validation failing"
          description: "CORS headers missing or incorrect for {{ $labels.endpoint }}"
        labels:
          severity: critical

      - alert: UnauthorizedOriginAttempts
        expr: rate(cors_blocked_origins_total[5m]) > 10
        for: 5m
        annotations:
          summary: "High rate of blocked CORS origins"
          description: "Possible attack from origin {{ $labels.origin }}"
        labels:
          severity: warning
```

### Grafana Dashboard

**Panels:**
1. CORS requests by origin
2. Preflight success rate
3. Blocked origins timeline
4. Header validation failures

## Best Practices

### Development

1. **Always test CORS locally** before pushing
2. **Use exact origin matching** (not wildcards)
3. **Enable credentials flag** for authenticated requests
4. **Set reasonable max-age** for preflight caching (3600s)

### Staging

1. **Run full validation** before promoting to production
2. **Test with actual frontend** URLs
3. **Verify all HTTP methods** work correctly
4. **Check custom headers** are allowed

### Production

1. **Validate before deployment**
2. **Monitor CORS metrics** continuously
3. **Set up alerts** for validation failures
4. **Keep audit trail** of all validations

### Security

1. **Never use wildcard** (`*`) with credentials
2. **Whitelist specific origins** only
3. **Validate origin** on server side
4. **Log blocked attempts** for security monitoring

## References

- [CORS Specification](https://fetch.spec.whatwg.org/#http-cors-protocol)
- [MDN CORS Guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [OWASP CORS Guide](https://cheatsheetseries.owasp.org/cheatsheets/CORS_Cheat_Sheet.html)
- Backend CORS Implementation: `backend-hormonia/app/middleware/cors.py`
- Security Configuration: `backend-hormonia/app/config/settings/security.py`

## Support

For issues or questions:
- **Development:** Check troubleshooting section
- **Staging/Production:** Create incident in GitHub Issues
- **Security Concerns:** Tag as P0 and notify team immediately
