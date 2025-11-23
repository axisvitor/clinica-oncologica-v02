# E2E Test Setup Instructions
## P1 and P2 API Fix Test Suite

**Last Updated:** 2025-11-16
**Test Framework:** Playwright
**Target:** Hormonia Oncology Clinic API v2

---

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Install Playwright browsers
npx playwright install

# 3. Set up environment
cp .env.example .env.test

# 4. Run tests
npm run test:e2e
```

---

## Detailed Setup

### 1. Prerequisites

#### Required Software

- **Node.js:** >= 18.0.0
- **npm:** >= 9.0.0
- **Backend API:** Running on port 8000 (default)
- **PostgreSQL:** Database with test data

#### Check Versions

```bash
node --version  # Should be >= 18.0.0
npm --version   # Should be >= 9.0.0
```

### 2. Install Dependencies

```bash
# From frontend-hormonia directory
cd frontend-hormonia

# Install all dependencies
npm install

# Install Playwright browsers (Chrome, Firefox, Safari)
npx playwright install

# Verify Playwright installation
npx playwright --version
```

### 3. Environment Configuration

#### Create Test Environment File

```bash
# Copy example environment
cp .env.example .env.test
```

#### Configure Environment Variables

Edit `.env.test`:

```bash
# Backend API URL (required)
VITE_API_URL=http://localhost:8000

# Playwright specific
PLAYWRIGHT_TEST_BASE_URL=http://localhost:4173

# Test authentication (optional - uses defaults)
TEST_AUTH_EMAIL=doctor@example.com
TEST_AUTH_PASSWORD=password123

# Admin credentials
TEST_ADMIN_EMAIL=admin@example.com
TEST_ADMIN_PASSWORD=admin123

# Test database (optional)
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/clinic_test

# Debug mode (optional)
DEBUG=pw:api  # Enable Playwright API debugging
```

### 4. Backend Setup

#### Start Backend API

```bash
# From backend-hormonia directory
cd ../backend-hormonia

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# OR
.\venv\Scripts\activate   # Windows

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Verify Backend is Running

```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

### 5. Test Database Setup

#### Create Test Database

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create test database
CREATE DATABASE clinic_test;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE clinic_test TO your_user;
```

#### Seed Test Data

```bash
# Run seeding scripts
cd backend-hormonia

# Seed users
python scripts/seed_test_users.py

# Seed patients
python scripts/seed_test_patients.py
```

#### Create Test Users

Ensure these users exist in the database:

```sql
-- Doctor user
INSERT INTO users (id, email, full_name, firebase_uid, role, is_active)
VALUES (
  'doctor-uuid-here',
  'doctor@example.com',
  'Dr. Test Doctor',
  'firebase-uid-doctor',
  'doctor',
  true
);

-- Admin user
INSERT INTO users (id, email, full_name, firebase_uid, role, is_active)
VALUES (
  'admin-uuid-here',
  'admin@example.com',
  'Admin User',
  'firebase-uid-admin',
  'admin',
  true
);
```

---

## Running Tests

### Run All Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run with HTML report
npm run test:e2e:report

# Run in UI mode (interactive)
npm run test:e2e:ui

# Run in debug mode
npm run test:e2e:debug
```

### Run Specific Test Suites

```bash
# CSRF migration tests (22 tests)
npx playwright test tests/e2e/csrf-migration.spec.ts

# Appointments API tests (16 tests)
npx playwright test tests/e2e/appointments.spec.ts

# Treatments API tests (15 tests)
npx playwright test tests/e2e/treatments.spec.ts

# Medications API tests (16 tests)
npx playwright test tests/e2e/medications.spec.ts

# Data contracts tests (19 tests)
npx playwright test tests/e2e/data-contracts.spec.ts
```

### Run Tests by Tag

```bash
# Run only security tests
npx playwright test --grep "@security"

# Run only RBAC tests
npx playwright test --grep "@rbac"

# Skip slow tests
npx playwright test --grep-invert "@slow"
```

### Run Tests in Parallel

```bash
# Run with 4 workers
npx playwright test --workers=4

# Run specific suite in parallel
npx playwright test tests/e2e/appointments.spec.ts --workers=2
```

### Run Tests in Different Browsers

```bash
# Run on Chrome only
npx playwright test --project="Desktop Chrome"

# Run on Firefox only
npx playwright test --project="Desktop Firefox"

# Run on Safari only (macOS only)
npx playwright test --project="Desktop Safari"

# Run on all browsers
npx playwright test --project="Desktop Chrome" --project="Desktop Firefox"
```

---

## Test Configuration

### Playwright Config (`playwright.config.ts`)

Located at: `frontend-hormonia/playwright.config.ts`

Key settings:
- **Timeout:** 30s per test
- **Retries:** 2 in CI, 0 locally
- **Workers:** 2 in CI, unlimited locally
- **Screenshots:** Only on failure in CI
- **Video:** Only on failure in CI
- **Trace:** Only on failure in CI

### Modify Configuration

```typescript
// playwright.config.ts
export default defineConfig({
  timeout: 60000, // Increase timeout to 60s
  retries: 3, // Increase retries
  workers: 1, // Run tests sequentially
  use: {
    headless: false, // Run in headed mode
    screenshot: 'on', // Always take screenshots
    video: 'on', // Always record video
    trace: 'on', // Always record trace
  }
});
```

---

## Debugging Tests

### Visual Debugging

```bash
# Run with browser visible
npx playwright test --headed

# Run in debug mode (step through tests)
npx playwright test --debug

# Run UI mode (interactive)
npx playwright test --ui
```

### Trace Viewer

```bash
# Run with trace
npx playwright test --trace on

# View trace
npx playwright show-trace trace.zip
```

### Console Logging

```bash
# Enable Playwright API logs
DEBUG=pw:api npx playwright test

# Enable all Playwright logs
DEBUG=pw:* npx playwright test

# Enable browser console logs
npx playwright test --debug
```

### Inspect Element

```bash
# Pause test and inspect
await page.pause();
```

### Take Screenshots

```typescript
// In test file
await page.screenshot({ path: 'debug-screenshot.png' });
```

---

## Common Issues & Solutions

### Issue: Tests Fail with "Connection Refused"

**Cause:** Backend API is not running

**Solution:**
```bash
# Start backend
cd backend-hormonia
uvicorn app.main:app --port 8000
```

### Issue: Tests Fail with "401 Unauthorized"

**Cause:** Test users don't exist in database

**Solution:**
```bash
# Seed test users
python scripts/seed_test_users.py
```

### Issue: Tests Fail with "CSRF token missing"

**Cause:** CSRF endpoint not accessible

**Solution:**
```bash
# Verify CSRF endpoint
curl http://localhost:8000/api/v2/auth/csrf-token
# Should return: {"csrf_token": "..."}
```

### Issue: Tests Timeout

**Cause:** Backend is slow or database is large

**Solution:**
```typescript
// Increase timeout in playwright.config.ts
timeout: 60000, // 60 seconds

// Or in specific test
test.setTimeout(60000);
```

### Issue: "Browser not installed"

**Cause:** Playwright browsers not installed

**Solution:**
```bash
npx playwright install
```

### Issue: Tests Pass Locally but Fail in CI

**Cause:** Different environment configuration

**Solution:**
1. Check CI environment variables
2. Verify database state
3. Check for timing issues (add waits)
4. Review CI logs for specific errors

---

## Test Data Management

### Clean Test Data

```bash
# Clean all test data
npm run test:clean

# Or manually
cd backend-hormonia
python scripts/clean_test_data.py
```

### Reset Test Database

```bash
# Drop and recreate test database
dropdb clinic_test
createdb clinic_test

# Run migrations
alembic upgrade head

# Reseed data
python scripts/seed_test_users.py
python scripts/seed_test_patients.py
```

### Create Test Fixtures

```typescript
// In test file
test.beforeAll(async ({ request }) => {
  // Create test patient
  const patient = await createPatient(request, doctorAuth, {
    name: 'Test Patient',
    email: 'test@example.com',
    phone: '+5511999999999',
    birth_date: '1990-01-01'
  });
});

test.afterAll(async ({ request }) => {
  // Clean up test data
  await deleteResource(request, adminAuth, '/api/v2/patients', patientId);
});
```

---

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/e2e-tests.yml`:

```yaml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd frontend-hormonia
          npm ci

      - name: Install Playwright
        run: |
          cd frontend-hormonia
          npx playwright install --with-deps

      - name: Start Backend
        run: |
          cd backend-hormonia
          pip install -r requirements.txt
          uvicorn app.main:app --port 8000 &

      - name: Run E2E Tests
        run: |
          cd frontend-hormonia
          npm run test:e2e

      - name: Upload Test Results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: frontend-hormonia/test-results/
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
e2e-tests:
  stage: test
  image: mcr.microsoft.com/playwright:v1.40.0
  services:
    - postgres:14
  variables:
    POSTGRES_DB: clinic_test
    POSTGRES_PASSWORD: postgres
  script:
    - cd frontend-hormonia
    - npm ci
    - npx playwright install
    - cd ../backend-hormonia
    - pip install -r requirements.txt
    - uvicorn app.main:app --port 8000 &
    - cd ../frontend-hormonia
    - npm run test:e2e
  artifacts:
    when: always
    paths:
      - frontend-hormonia/test-results/
    reports:
      junit: frontend-hormonia/test-results/junit.xml
```

---

## Performance Optimization

### Reduce Test Time

```typescript
// Run tests in parallel
npx playwright test --workers=4

// Skip slow tests in dev
npx playwright test --grep-invert "@slow"

// Use faster assertions
expect(data.id).toBeDefined(); // Faster
expect(data).toHaveProperty('id'); // Slower
```

### Cache Test Data

```typescript
// Cache login credentials
let globalAuth: LoginResult;

test.beforeAll(async ({ request }) => {
  if (!globalAuth) {
    globalAuth = await loginUser(request, 'doctor@example.com', 'password123');
  }
});
```

### Skip Unnecessary Tests

```typescript
// Skip test
test.skip('flaky test', async () => {
  // ...
});

// Conditional skip
test.skip(process.env.CI === 'true', 'slow test', async () => {
  // ...
});
```

---

## Reporting

### Generate HTML Report

```bash
# Run tests with HTML report
npx playwright test --reporter=html

# View report
npx playwright show-report
```

### Generate JSON Report

```bash
# Run tests with JSON report
npx playwright test --reporter=json --reporter-json-output-file=report.json
```

### Generate JUnit Report (for CI)

```bash
# Run tests with JUnit report
npx playwright test --reporter=junit --reporter-junit-output-file=junit.xml
```

### Custom Reporting

```bash
# Multiple reporters
npx playwright test --reporter=list --reporter=html --reporter=junit
```

---

## Best Practices

### Test Organization

1. **Group related tests** in describe blocks
2. **Use descriptive test names** (should + verb + expected result)
3. **Keep tests independent** (no dependencies between tests)
4. **Clean up after tests** (delete created resources)

### Test Data

1. **Use unique data** for each test (avoid conflicts)
2. **Generate random data** with helper functions
3. **Create fixtures** for common test data
4. **Clean up test data** after test suite

### Assertions

1. **Use specific assertions** (toBe, toEqual, toContain)
2. **Assert expected structure** with toHaveProperty
3. **Validate data types** with typeof
4. **Check array lengths** before accessing elements

### Error Handling

1. **Expect errors** when testing error cases
2. **Validate error messages** for clarity
3. **Check error status codes** (400, 401, 403, 404, 422)
4. **Log failures** for debugging

---

## Support & Resources

### Documentation

- **Playwright Docs:** https://playwright.dev
- **Testing Best Practices:** https://playwright.dev/docs/best-practices
- **API Testing Guide:** https://playwright.dev/docs/api-testing

### Community

- **Playwright Discord:** https://discord.com/invite/playwright
- **Stack Overflow:** `[playwright]` tag
- **GitHub Issues:** https://github.com/microsoft/playwright/issues

### Internal Resources

- **Test Report:** `tests/e2e/TEST_REPORT.md`
- **Test Helpers:** `tests/e2e/fixtures/test-helpers.ts`
- **API Documentation:** `/docs/api/README.md`

---

## Next Steps

After setup:

1. ✅ Run all tests to verify setup
2. ✅ Review test failures and fix issues
3. ✅ Add tests for new features
4. ✅ Integrate with CI/CD pipeline
5. ✅ Monitor test results and maintain tests

---

**Setup Status:** Complete
**Total Tests:** 63+ E2E tests
**Coverage:** P1 and P2 API fixes
**Last Updated:** 2025-11-16
