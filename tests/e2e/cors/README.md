# CORS End-to-End Test Suite

Comprehensive CORS testing suite for the Clínica Oncológica application.

## Overview

This test suite validates CORS (Cross-Origin Resource Sharing) configuration using both Playwright (browser-based E2E tests) and pytest (backend unit tests).

## Test Structure

```
tests/
├── e2e/
│   └── cors/
│       ├── conftest.py                          # Pytest fixtures and configuration
│       ├── pytest.ini                           # Pytest settings
│       ├── test_cors_preflight.py              # Preflight (OPTIONS) request tests
│       ├── test_cors_actual_requests.py        # Actual GET/POST/PUT/DELETE tests
│       ├── test_cors_disallowed_origins.py     # Disallowed origin tests
│       └── test_cors_invalid_combinations.py   # Invalid CORS configuration tests
└── backend/
    └── cors/
        └── test_cors_middleware.py              # FastAPI middleware unit tests
```

## Test Categories

### 1. Preflight Tests (`test_cors_preflight.py`)

Tests preflight OPTIONS requests:
- ✅ Allowed origins (localhost:3000, localhost:5173, production)
- ✅ Access-Control-Allow-Origin header validation
- ✅ Access-Control-Allow-Credentials: true
- ✅ Access-Control-Allow-Methods validation
- ✅ Access-Control-Allow-Headers validation
- ✅ Vary header presence
- ✅ Max-Age configuration
- ✅ Complex header combinations

### 2. Actual Request Tests (`test_cors_actual_requests.py`)

Tests actual HTTP requests:
- ✅ GET requests with CORS headers
- ✅ POST requests with credentials
- ✅ PUT/DELETE/PATCH requests
- ✅ Access-Control-Expose-Headers
- ✅ Cookie handling with credentials
- ✅ CORS headers on error responses (404, 500)
- ✅ Multiple sequential requests

### 3. Disallowed Origin Tests (`test_cors_disallowed_origins.py`)

Tests security against unauthorized origins:
- ✅ Requests from evil.com rejected
- ✅ Malicious site requests blocked
- ✅ Non-whitelisted localhost ports blocked
- ✅ IP address origins rejected
- ✅ Subdomain validation
- ✅ Null origin handling
- ✅ Case-sensitive origin validation

### 4. Invalid Combination Tests (`test_cors_invalid_combinations.py`)

Tests CORS security constraints:
- ✅ **CRITICAL**: No wildcard (*) with credentials: true
- ✅ Credentials require specific origin
- ✅ No multiple comma-separated origins
- ✅ HTTP/HTTPS scheme matching
- ✅ Port number specificity
- ✅ Trailing slash handling
- ✅ Credentials value validation

### 5. Backend Unit Tests (`test_cors_middleware.py`)

Tests FastAPI middleware directly:
- ✅ Middleware configuration validation
- ✅ All allowed origins tested
- ✅ Method allowances (GET, POST, PUT, DELETE, PATCH)
- ✅ Header allowances
- ✅ Max-Age configuration
- ✅ Vary header
- ✅ Error response CORS headers

## Running Tests

### Prerequisites

```bash
# Install dependencies
pip install pytest pytest-asyncio playwright fastapi

# Install Playwright browsers
playwright install chromium
```

### Run All CORS Tests

```bash
# E2E tests
pytest tests/e2e/cors/ -v

# Backend unit tests
pytest tests/backend/cors/ -v

# All CORS tests
pytest tests/ -m cors -v
```

### Run Specific Test Categories

```bash
# Only preflight tests
pytest tests/e2e/cors/test_cors_preflight.py -v

# Only security tests
pytest tests/e2e/cors/test_cors_disallowed_origins.py -v

# Only invalid combination tests
pytest tests/e2e/cors/test_cors_invalid_combinations.py -v

# Smoke tests only
pytest tests/ -m smoke -v
```

### Run with Different Environments

```bash
# Test against local backend
BACKEND_URL=http://localhost:8000 pytest tests/e2e/cors/ -v

# Test against staging
BACKEND_URL=https://staging.example.com pytest tests/e2e/cors/ -v

# Test against production
BACKEND_URL=https://clinica-oncologica-production.up.railway.app pytest tests/e2e/cors/ -v
```

### Parallel Execution

```bash
# Run tests in parallel (requires pytest-xdist)
pip install pytest-xdist
pytest tests/e2e/cors/ -n auto -v
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://localhost:8000` | Backend API URL |
| `FRONTEND_URL` | `http://localhost:3000` | Frontend URL |

## Expected Allowed Origins

The tests validate these allowed origins:
- `http://localhost:3000` - React dev server
- `http://localhost:5173` - Vite dev server
- `https://clinica-oncologica-production.up.railway.app` - Production

## CORS Configuration Requirements

### ✅ Valid Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://clinica-oncologica-production.up.railway.app"
    ],
    allow_credentials=True,  # ✅ OK with specific origins
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600
)
```

### ❌ Invalid Configuration

```python
# WRONG: Wildcard with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ❌ CANNOT use with credentials
    allow_credentials=True,  # ❌ Cannot be true with wildcard
    ...
)
```

## Test Markers

Tests are marked for selective execution:
- `@pytest.mark.cors` - All CORS tests
- `@pytest.mark.preflight` - Preflight-specific tests
- `@pytest.mark.security` - Security-related tests
- `@pytest.mark.smoke` - Quick smoke tests

## Continuous Integration

Add to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Run CORS Tests
  run: |
    pytest tests/e2e/cors/ -v --tb=short
    pytest tests/backend/cors/ -v --tb=short
```

## Debugging Failed Tests

### Check CORS Headers

```bash
# Manual curl test
curl -X OPTIONS http://localhost:8000/api/patients \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -v

# Check actual request
curl http://localhost:8000/api/health \
  -H "Origin: http://localhost:3000" \
  -v
```

### View Playwright Traces

```bash
# Run with trace
pytest tests/e2e/cors/ --tracing on

# View trace
playwright show-trace trace.zip
```

## Common Issues

### Issue: Tests fail with "Origin not allowed"

**Solution**: Check that backend CORS middleware includes the test origin.

### Issue: Credentials error in browser

**Solution**: Verify no wildcard (*) is used with `credentials: true`.

### Issue: Preflight fails

**Solution**: Ensure OPTIONS method is allowed in middleware.

## Security Checklist

- [ ] No wildcard origin with credentials
- [ ] All production origins whitelisted
- [ ] Development origins only in dev environment
- [ ] HTTPS enforced for production origins
- [ ] Null origin rejected
- [ ] Subdomain attacks prevented
- [ ] Case-sensitive origin matching
- [ ] Port-specific origin validation

## Coordination Hooks

These tests integrate with Claude Flow coordination:

```bash
# Before tests
npx claude-flow@alpha hooks pre-task --description "CORS test suite"

# After edits
npx claude-flow@alpha hooks post-edit --file "test_cors_preflight.py" --memory-key "hive-mind/tests/cors-suite"

# After completion
npx claude-flow@alpha hooks post-task --task-id "cors-test-creation"
```

## Contributing

When adding new CORS tests:
1. Follow existing test structure
2. Use descriptive test names
3. Add appropriate markers
4. Update this README
5. Run full suite before committing

## Resources

- [CORS Spec](https://fetch.spec.whatwg.org/#http-cors-protocol)
- [MDN CORS Guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [FastAPI CORS Middleware](https://fastapi.tiangolo.com/tutorial/cors/)
- [Playwright Docs](https://playwright.dev/python/)
