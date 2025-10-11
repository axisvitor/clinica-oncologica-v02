# API Contract Test Execution Guide

## Overview

This guide provides comprehensive instructions for executing API contract tests to validate all backend-frontend integration fixes.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Test Coverage](#test-coverage)
5. [Continuous Integration](#continuous-integration)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

```bash
# Backend dependencies
cd backend-hormonia
pip install -r requirements.txt
pip install pytest pytest-cov pytest-asyncio httpx

# Frontend dependencies
cd ../frontend-hormonia
npm install
```

### Quick Test Run

```bash
# Backend smoke test
cd scripts
./smoke_test_api_fixes.bat

# Backend integration tests
cd ../backend-hormonia
pytest tests/api/test_api_contract_fixes.py -v

# Frontend integration tests
cd ../frontend-hormonia
npm run test:integration
```

---

## Test Structure

### Backend Tests

**Location:** `backend-hormonia/tests/api/test_api_contract_fixes.py`

**Structure:**
```
test_api_contract_fixes.py
├── TestAdminUsersListFix          # Fix #1: Pagination
├── TestUserActivityEndpointFix    # Fix #2: Activity tracking
├── TestNotificationsStructureFix  # Fix #3: Notifications
├── TestDashboardTrendsFix         # Fix #4: Dashboard trends
├── TestTypeScriptInterfaceCompliance  # Fix #5: Type safety
└── TestErrorHandling              # Edge cases
```

### Frontend Tests

**Location:** `frontend-hormonia/tests/integration/api-contracts.test.ts`

**Structure:**
```
api-contracts.test.ts
├── Fix #1: useUserAdmin Hook
├── Fix #2: User Activity Endpoint
├── Fix #3: NotificationCenter Component
├── Fix #4: Dashboard Trends
├── TypeScript Interface Compliance
└── Error Handling
```

---

## Running Tests

### Backend Tests

#### 1. Run All Tests

```bash
cd backend-hormonia
pytest tests/api/test_api_contract_fixes.py -v
```

**Expected Output:**
```
test_api_contract_fixes.py::TestAdminUsersListFix::test_admin_users_list_structure PASSED
test_api_contract_fixes.py::TestAdminUsersListFix::test_admin_users_pagination PASSED
test_api_contract_fixes.py::TestAdminUsersListFix::test_admin_users_item_structure PASSED
...
========================== 25 passed in 12.34s ==========================
```

#### 2. Run Specific Test Class

```bash
# Test only admin users endpoint
pytest tests/api/test_api_contract_fixes.py::TestAdminUsersListFix -v

# Test only notifications endpoint
pytest tests/api/test_api_contract_fixes.py::TestNotificationsStructureFix -v

# Test only dashboard endpoint
pytest tests/api/test_api_contract_fixes.py::TestDashboardTrendsFix -v
```

#### 3. Run Specific Test

```bash
pytest tests/api/test_api_contract_fixes.py::TestAdminUsersListFix::test_admin_users_list_structure -v
```

#### 4. Run with Coverage

```bash
pytest tests/api/test_api_contract_fixes.py --cov=app --cov-report=html --cov-report=term
```

**Coverage Report:**
```
Name                                    Stmts   Miss  Cover
-----------------------------------------------------------
app/api/admin.py                          145     12    92%
app/api/notifications.py                   87      5    94%
app/api/dashboard.py                      123      8    93%
-----------------------------------------------------------
TOTAL                                     355     25    93%
```

View HTML report:
```bash
# Windows
start htmlcov/index.html

# Linux/Mac
open htmlcov/index.html
```

#### 5. Run in Watch Mode

```bash
pytest-watch tests/api/test_api_contract_fixes.py
```

#### 6. Run with Markers

```bash
# Run only integration tests
pytest tests/api/test_api_contract_fixes.py -m integration

# Skip slow tests
pytest tests/api/test_api_contract_fixes.py -m "not slow"
```

### Frontend Tests

#### 1. Run All Tests

```bash
cd frontend-hormonia
npm run test:integration
```

#### 2. Run in Watch Mode

```bash
npm run test:watch
```

#### 3. Run with Coverage

```bash
npm run test:coverage
```

#### 4. Run Specific Test File

```bash
npm test -- tests/integration/api-contracts.test.ts
```

#### 5. Run Specific Test

```bash
npm test -- tests/integration/api-contracts.test.ts -t "should process {items, total} structure"
```

### Smoke Tests

#### Quick Validation

```bash
cd scripts
./smoke_test_api_fixes.bat http://localhost:8000
```

**Output:**
```
============================================================================
API Contract Fixes - Smoke Test
============================================================================
Base URL: http://localhost:8000
Log File: smoke_test_results_20241010_143022.log
============================================================================

[1] Testing: Admin Users List Structure
  ✓ HTTP 200 OK
  ✓ Response structure valid

[2] Testing: User Activity Endpoint
  ✓ HTTP 200 OK
  ✓ Response structure valid

[3] Testing: Notifications Structure
  ✓ HTTP 200 OK
  ✓ Response structure valid

[4] Testing: Dashboard Stats Trends
  ✓ HTTP 200 OK
  ✓ Response structure valid

[5] Testing: Pagination Parameters
  ✓ HTTP 200 OK
  ✓ Response structure valid

============================================================================
Test Summary
============================================================================
Total Tests: 5
Passed: 5
Failed: 0
============================================================================

ALL TESTS PASSED
```

---

## Test Coverage

### Coverage Requirements

- **Minimum Coverage:** 80%
- **Target Coverage:** 90%+
- **Critical Paths:** 100%

### Generate Coverage Report

#### Backend

```bash
cd backend-hormonia
pytest tests/api/test_api_contract_fixes.py \
  --cov=app \
  --cov-report=html \
  --cov-report=term \
  --cov-fail-under=80
```

#### Frontend

```bash
cd frontend-hormonia
npm run test:coverage
```

### Coverage Analysis

**View Coverage by File:**
```bash
# Backend
coverage report -m

# Frontend
cat coverage/coverage-summary.json | jq
```

**Identify Uncovered Lines:**
```bash
# Backend
coverage html
# Open htmlcov/index.html and click on files

# Frontend
# Open coverage/lcov-report/index.html
```

---

## Continuous Integration

### GitHub Actions Workflow

**File:** `.github/workflows/api-contract-tests.yml`

```yaml
name: API Contract Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend-hormonia
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run API contract tests
        run: |
          cd backend-hormonia
          pytest tests/api/test_api_contract_fixes.py \
            --cov=app \
            --cov-report=xml \
            --cov-fail-under=80

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend-hormonia/coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd frontend-hormonia
          npm ci

      - name: Run integration tests
        run: |
          cd frontend-hormonia
          npm run test:integration

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./frontend-hormonia/coverage/coverage-final.json

  smoke-tests:
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]
    steps:
      - uses: actions/checkout@v3

      - name: Start backend
        run: |
          cd backend-hormonia
          pip install -r requirements.txt
          uvicorn app.main:app &
          sleep 5

      - name: Run smoke tests
        run: |
          cd scripts
          ./smoke_test_api_fixes.bat http://localhost:8000
```

### Pre-commit Hooks

**File:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: local
    hooks:
      - id: backend-tests
        name: Backend API Contract Tests
        entry: bash -c 'cd backend-hormonia && pytest tests/api/test_api_contract_fixes.py -v'
        language: system
        pass_filenames: false

      - id: frontend-tests
        name: Frontend Integration Tests
        entry: bash -c 'cd frontend-hormonia && npm run test:integration'
        language: system
        pass_filenames: false
```

---

## Troubleshooting

### Common Issues

#### 1. Tests Fail with Authentication Error

**Error:**
```
AssertionError: assert 401 == 200
```

**Solution:**
```bash
# Ensure test fixtures provide valid tokens
# Check conftest.py for admin_token and regular_token fixtures
```

#### 2. Frontend Tests Timeout

**Error:**
```
Timeout waiting for request to /api/v1/admin/users
```

**Solution:**
```bash
# Increase timeout in test setup
waitFor(() => expect(result.current.isSuccess).toBe(true), { timeout: 5000 });
```

#### 3. Coverage Below Threshold

**Error:**
```
FAILED: coverage must be at least 80%
```

**Solution:**
```bash
# Identify uncovered lines
coverage report -m

# Add tests for uncovered code paths
```

#### 4. MSW Handler Not Found

**Error:**
```
[MSW] Warning: captured a request without a matching request handler
```

**Solution:**
```typescript
// Add missing handler to server.use()
server.use(
  rest.get('/api/v1/missing-endpoint', (req, res, ctx) => {
    return res(ctx.json({ data: 'mock' }));
  })
);
```

#### 5. Database Connection Error

**Error:**
```
sqlalchemy.exc.OperationalError: connection refused
```

**Solution:**
```bash
# Use test database
export DATABASE_URL="postgresql://test:test@localhost/test_db"

# Or use SQLite for tests
export DATABASE_URL="sqlite:///./test.db"
```

### Debug Mode

#### Backend

```bash
# Run with verbose output
pytest tests/api/test_api_contract_fixes.py -v -s

# Run with debugger
pytest tests/api/test_api_contract_fixes.py --pdb

# Show print statements
pytest tests/api/test_api_contract_fixes.py -v -s --capture=no
```

#### Frontend

```bash
# Run with debug output
DEBUG=* npm test

# Run single test with logs
npm test -- -t "specific test" --verbose
```

### Logging

#### Enable Test Logging

**Backend:**
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_something():
    logger.debug("Test starting")
    # test code
```

**Frontend:**
```typescript
console.log('Test data:', data);
screen.debug(); // Print current DOM
```

---

## Best Practices

1. **Run tests before committing**
2. **Maintain 80%+ coverage**
3. **Use descriptive test names**
4. **Mock external dependencies**
5. **Test both success and failure cases**
6. **Keep tests fast (<100ms per test)**
7. **Use fixtures for common setup**
8. **Document complex test scenarios**

---

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [React Testing Library](https://testing-library.com/react)
- [MSW (Mock Service Worker)](https://mswjs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)

---

## Support

For test failures or questions:
1. Check test logs
2. Review error messages
3. Run individual failing tests
4. Check CI/CD pipeline logs
5. Contact QA team
