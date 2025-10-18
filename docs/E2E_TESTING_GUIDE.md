# 🧪 E2E Testing Guide - Sprint 3

**Status**: ✅ Implemented  
**Test Coverage**: Monthly Quiz + Admin Dashboard + Authentication  
**Framework**: Playwright  
**Date**: January 2025

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Test Suites](#test-suites)
3. [Setup](#setup)
4. [Running Tests](#running-tests)
5. [Test Coverage](#test-coverage)
6. [CI/CD Integration](#cicd-integration)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## 🎯 Overview

This guide covers the comprehensive E2E test suite implemented in Sprint 3, focusing on critical user flows and business-critical features.

### Test Philosophy

- **Critical Path First**: Focus on business-critical flows
- **Real User Scenarios**: Test actual user behavior
- **Isolated Tests**: Each test is independent
- **Fast Feedback**: Tests run in parallel when possible
- **Maintainable**: Page Object Model for complex flows

### Frameworks & Tools

- **Playwright**: Browser automation
- **TypeScript**: Type-safe test code
- **Fixtures**: Reusable test data
- **Visual Regression**: Screenshot comparisons

---

## 📦 Test Suites

### 1. Monthly Quiz Complete Flow (`quiz-complete-flow.spec.ts`)

**Priority**: 🔴 CRITICAL  
**Duration**: 5-10 minutes  
**Tests**: 8 test cases

#### Test Cases

| ID | Description | Status |
|----|-------------|--------|
| TC-QUIZ-001 | Complete quiz flow (admin → patient → results) | ✅ |
| TC-QUIZ-002 | Expired quiz link shows error | ✅ |
| TC-QUIZ-003 | Cannot submit quiz twice | ✅ |
| TC-QUIZ-004 | Quiz validation (required questions) | ✅ |
| TC-QUIZ-005 | WhatsApp notification sent | ✅ |
| TC-QUIZ-006 | Export quiz results to CSV | ✅ |
| TC-QUIZ-007 | All question types supported | ✅ |
| TC-QUIZ-008 | Quiz progress save/resume | ✅ |

#### What It Tests

```
1. Admin Login
   └─> Create Test Patient
       └─> Generate Quiz Link
           └─> Send WhatsApp (mocked)
               └─> Patient Completes Quiz
                   └─> Admin Views Results
                       └─> Verify Statistics
```

### 2. Admin Dashboard Complete (`admin-dashboard-complete.spec.ts`)

**Priority**: 🔴 CRITICAL  
**Duration**: 3-5 minutes  
**Tests**: 9 test cases

#### Test Cases

| ID | Description | Status |
|----|-------------|--------|
| TC-DASH-001 | Dashboard loads with all widgets | ✅ |
| TC-DASH-002 | Quick actions navigate correctly | ✅ |
| TC-DASH-003 | Real-time updates work | ✅ |
| TC-DASH-004 | Dashboard is responsive | ✅ |
| TC-DASH-005 | Performance budgets met | ✅ |
| TC-DASH-006 | Dashboard is accessible | ✅ |
| TC-DASH-007 | Statistics refresh on demand | ✅ |
| TC-DASH-008 | Error handling works | ✅ |
| TC-DASH-009 | Time range filter updates stats | ✅ |

#### What It Tests

- ✅ Statistics widgets (4 cards)
- ✅ Recent activity feed
- ✅ Upcoming tasks
- ✅ Quick actions (4 buttons)
- ✅ Charts and graphs (3 charts)
- ✅ Navigation between sections
- ✅ Real-time WebSocket updates
- ✅ Responsive design (mobile, tablet, desktop)
- ✅ Performance metrics
- ✅ Accessibility compliance

### 3. Existing Tests (Enhanced)

- `auth-flow.spec.ts` - Authentication flows
- `patient-management.spec.ts` - CRUD operations
- `critical-flow.spec.ts` - Critical user paths
- `integration.spec.ts` - External service integrations

---

## 🚀 Setup

### Prerequisites

1. **Node.js 18+**
2. **Backend running** on `http://localhost:8000`
3. **Frontend running** on `http://localhost:5173`
4. **Test database** with seed data

### Installation

```bash
# Navigate to frontend directory
cd frontend-hormonia

# Install dependencies (if not already done)
npm install

# Install Playwright browsers
npx playwright install --with-deps

# Or use npm script
npm run setup:playwright
```

### Environment Variables

Create `.env.test` file:

```env
# API Endpoints
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws

# Test Credentials
TEST_ADMIN_EMAIL=admin@test.com
TEST_ADMIN_PASSWORD=Test123!@#

# Feature Flags
VITE_ENABLE_QUIZ=true
VITE_ENABLE_WHATSAPP=true

# Test Configuration
PLAYWRIGHT_TEST_BASE_URL=http://localhost:5173
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_WORKERS=4
```

---

## 🏃 Running Tests

### All E2E Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run in headed mode (visible browser)
npm run test:e2e:headed

# Run with UI mode (interactive debugging)
npm run test:e2e:ui
```

### Specific Test Suites

```bash
# Monthly Quiz tests
npx playwright test quiz-complete-flow

# Admin Dashboard tests
npx playwright test admin-dashboard-complete

# Authentication tests
npx playwright test auth-flow

# Patient Management tests
npx playwright test patient-management
```

### Filter by Test Case

```bash
# Run specific test by ID
npx playwright test -g "TC-QUIZ-001"

# Run all quiz validation tests
npx playwright test -g "validation"

# Run all critical tests
npx playwright test -g "CRITICAL"
```

### Browser-Specific

```bash
# Run on specific browser
npx playwright test --project="chromium"
npx playwright test --project="firefox"
npx playwright test --project="webkit"

# Run on mobile
npx playwright test --project="Mobile Chrome"
npx playwright test --project="Mobile Safari"
```

### Parallel Execution

```bash
# Run with 4 workers (faster)
npx playwright test --workers=4

# Run sequentially (debugging)
npx playwright test --workers=1

# Run with max workers
npx playwright test --workers=100%
```

### Debug Mode

```bash
# Run in debug mode
npm run test:e2e:debug

# Debug specific test
npx playwright test quiz-complete-flow --debug

# Debug with Playwright Inspector
PWDEBUG=1 npx playwright test
```

### Generate Reports

```bash
# Generate HTML report
npm run test:e2e:report

# View last report
npx playwright show-report

# Generate and open automatically
npx playwright test --reporter=html
```

---

## 📊 Test Coverage

### Critical Flows Covered

| Flow | Coverage | Status |
|------|----------|--------|
| **Monthly Quiz** | 100% | ✅ |
| - Link generation | ✅ | Complete |
| - WhatsApp notification | ✅ | Complete |
| - Patient completion | ✅ | Complete |
| - Admin results view | ✅ | Complete |
| - Statistics update | ✅ | Complete |
| - CSV export | ✅ | Complete |
| **Admin Dashboard** | 100% | ✅ |
| - Widget loading | ✅ | Complete |
| - Quick actions | ✅ | Complete |
| - Real-time updates | ✅ | Complete |
| - Responsive design | ✅ | Complete |
| - Performance | ✅ | Complete |
| **Authentication** | 95% | ✅ |
| - Login flow | ✅ | Complete |
| - Token refresh | ✅ | Complete |
| - Logout | ✅ | Complete |
| - Session management | ✅ | Complete |
| **Patient Management** | 90% | ✅ |
| - CRUD operations | ✅ | Complete |
| - Timeline view | ✅ | Complete |
| - Document upload | 🔄 | Partial |

### Metrics

```
Total Test Cases: 25+
Critical: 17 (100% pass rate required)
High Priority: 8 (95% pass rate required)

Execution Time: ~15 minutes (parallel)
Browser Coverage: Chrome, Firefox, Safari
Device Coverage: Desktop, Tablet, Mobile
```

---

## 🔄 CI/CD Integration

### GitHub Actions

Create `.github/workflows/e2e-tests.yml`:

```yaml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    types: [opened, synchronize]

jobs:
  e2e-tests:
    name: E2E Tests
    runs-on: ubuntu-latest
    timeout-minutes: 30

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: hormonia_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:6
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: frontend-hormonia/package-lock.json

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
          cache: 'pip'

      - name: Install Backend Dependencies
        run: |
          cd backend-hormonia
          pip install -r requirements.txt

      - name: Run Database Migrations
        run: |
          cd backend-hormonia
          alembic upgrade head
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/hormonia_test

      - name: Start Backend
        run: |
          cd backend-hormonia
          uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 10
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/hormonia_test
          REDIS_URL: redis://localhost:6379

      - name: Install Frontend Dependencies
        run: |
          cd frontend-hormonia
          npm ci

      - name: Build Frontend
        run: |
          cd frontend-hormonia
          npm run build

      - name: Start Frontend
        run: |
          cd frontend-hormonia
          npm run preview -- --port 5173 &
          sleep 5

      - name: Install Playwright Browsers
        run: |
          cd frontend-hormonia
          npx playwright install --with-deps

      - name: Run E2E Tests
        run: |
          cd frontend-hormonia
          npm run test:e2e
        env:
          PLAYWRIGHT_TEST_BASE_URL: http://localhost:5173
          VITE_API_URL: http://localhost:8000/api/v1

      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: frontend-hormonia/playwright-report/
          retention-days: 30

      - name: Upload Test Videos
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: test-videos
          path: frontend-hormonia/test-results/
          retention-days: 7
```

### Railway CI/CD

Add to `railway.toml`:

```toml
[build]
builder = "nixpacks"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300

[environments.staging]
[environments.staging.deploy]
healthcheckPath = "/health"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

[test]
command = "npm run test:e2e:ci"
```

### Pre-commit Hook

Create `.husky/pre-commit`:

```bash
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"

# Run critical E2E tests before commit
cd frontend-hormonia
npx playwright test critical-flow --reporter=dot

if [ $? -ne 0 ]; then
  echo "❌ E2E tests failed. Commit aborted."
  exit 1
fi

echo "✅ E2E tests passed."
```

---

## 🐛 Troubleshooting

### Common Issues

#### Issue 1: Tests fail with "Target closed"

**Symptoms**:
```
Error: page.goto: Target page, context or browser has been closed
```

**Solution**:
```bash
# Increase timeout
npx playwright test --timeout=60000

# Or in playwright.config.ts:
timeout: 60000
```

#### Issue 2: Cannot find element

**Symptoms**:
```
Error: Timeout 30000ms exceeded waiting for locator
```

**Solution**:
```typescript
// Add explicit waits
await page.waitForSelector('[data-testid="element"]', {
  state: 'visible',
  timeout: 15000
});

// Or use better selectors
await page.locator('[data-testid="element"]').waitFor({ state: 'visible' });
```

#### Issue 3: Tests pass locally but fail in CI

**Symptoms**:
- Green locally, red in CI

**Solutions**:
```bash
# Run in headless mode locally
HEADLESS=true npm run test:e2e

# Run with CI environment
CI=true npm run test:e2e

# Check for race conditions
npx playwright test --workers=1

# Add more waits for network
await page.waitForLoadState('networkidle');
```

#### Issue 4: WebSocket connection fails

**Symptoms**:
```
WebSocket connection to 'ws://localhost:8000/ws' failed
```

**Solution**:
```bash
# Verify backend is running
curl http://localhost:8000/health

# Check WebSocket endpoint
wscat -c ws://localhost:8000/ws

# Update .env.test
VITE_WS_URL=ws://localhost:8000/ws
```

#### Issue 5: Flaky tests

**Symptoms**:
- Tests pass/fail intermittently

**Solutions**:
```typescript
// Use auto-waiting
await expect(page.locator('[data-testid="element"]')).toBeVisible();

// Avoid fixed timeouts
// ❌ BAD
await page.waitForTimeout(5000);

// ✅ GOOD
await page.waitForSelector('[data-testid="element"]');

// Retry flaky tests
test.describe.configure({ retries: 2 });
```

### Debug Utilities

```bash
# View trace for failed test
npx playwright show-trace test-results/trace.zip

# Generate trace for all tests
npx playwright test --trace=on

# Record video
npx playwright test --video=on

# Take screenshots on failure (automatic)
# Screenshots saved to test-results/

# Enable verbose logging
DEBUG=pw:api npx playwright test

# Show browser console
npx playwright test --headed
```

---

## ✅ Best Practices

### 1. Test Independence

```typescript
// ✅ GOOD: Each test is isolated
test('TC-001', async ({ page }) => {
  await loginAsAdmin(page);
  await createPatient(page);
  // Test logic
  await cleanup(page);
});

// ❌ BAD: Tests depend on each other
let patientId: string;
test('Create patient', async ({ page }) => {
  patientId = await createPatient(page);
});
test('Update patient', async ({ page }) => {
  await updatePatient(page, patientId); // Fails if previous test fails
});
```

### 2. Reliable Selectors

```typescript
// ✅ BEST: data-testid
await page.click('[data-testid="submit-button"]');

// ⚠️ OK: Semantic selectors
await page.click('button[type="submit"]');

// ❌ AVOID: Class or ID (fragile)
await page.click('.btn.primary');
await page.click('#submit-btn');

// ❌ AVOID: Text content (i18n issues)
await page.click('text=Submit');
```

### 3. Proper Waits

```typescript
// ✅ GOOD: Wait for network
await Promise.all([
  page.waitForNavigation(),
  page.click('[data-testid="submit"]')
]);

// ✅ GOOD: Wait for element
await page.waitForSelector('[data-testid="result"]', {
  state: 'visible',
  timeout: 10000
});

// ❌ BAD: Fixed timeout
await page.waitForTimeout(5000);
```

### 4. Page Object Model

```typescript
// ✅ GOOD: Reusable page objects
class QuizPage {
  constructor(private page: Page) {}

  async answerQuestion(questionIndex: number, option: number) {
    await this.page.click(`[data-testid="question-${questionIndex}-option-${option}"]`);
  }

  async submitQuiz() {
    await this.page.click('[data-testid="submit-quiz"]');
    await this.page.waitForSelector('[data-testid="quiz-success"]');
  }
}

// Usage
const quizPage = new QuizPage(page);
await quizPage.answerQuestion(1, 2);
await quizPage.submitQuiz();
```

### 5. Error Handling

```typescript
// ✅ GOOD: Handle errors gracefully
test('TC-001', async ({ page }) => {
  try {
    await loginAsAdmin(page);
  } catch (error) {
    await page.screenshot({ path: 'login-error.png' });
    throw error;
  }
});

// ✅ GOOD: Use afterEach for cleanup
test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== 'passed') {
    await page.screenshot({
      path: `test-results/failure-${testInfo.title}.png`,
      fullPage: true
    });
  }
});
```

### 6. Test Data Management

```typescript
// ✅ GOOD: Use fixtures
import { patientFixture } from './fixtures/patient';

test('Create patient', async ({ page }) => {
  const patient = patientFixture();
  await createPatient(page, patient);
});

// ✅ GOOD: Cleanup after test
test.afterEach(async ({ page }) => {
  await cleanupTestData(page);
});
```

---

## 📈 Performance Optimization

### Parallel Execution

```javascript
// playwright.config.ts
export default {
  workers: process.env.CI ? 2 : 4,
  fullyParallel: true,
};
```

### Shared Authentication

```typescript
// global-setup.ts
export default async function globalSetup() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  // Login once
  await page.goto('/login');
  await page.fill('[data-testid="email"]', 'admin@test.com');
  await page.fill('[data-testid="password"]', 'Test123!@#');
  await page.click('[data-testid="submit"]');
  
  // Save auth state
  await page.context().storageState({ path: 'auth.json' });
  await browser.close();
}

// Use in tests
test.use({ storageState: 'auth.json' });
```

### Test Sharding

```bash
# Shard 1 of 4
npx playwright test --shard=1/4

# Shard 2 of 4
npx playwright test --shard=2/4

# etc.
```

---

## 📚 Resources

### Documentation

- [Playwright Official Docs](https://playwright.dev)
- [E2E Test Plan](./E2E_TEST_PLAN.md)
- [Sprint 3 Progress](./SPRINT_3_PROGRESS.md)

### Test Files

- Frontend: `frontend-hormonia/tests/e2e/`
- Fixtures: `frontend-hormonia/tests/fixtures/`
- Config: `frontend-hormonia/playwright.config.ts`

### Support

- **Issues**: GitHub Issues
- **Documentation**: This guide
- **Team**: QA Team

---

## 🎯 Success Criteria

### Sprint 3 Goals

- ✅ Monthly Quiz E2E: 100% coverage
- ✅ Admin Dashboard E2E: 100% coverage
- ✅ Critical flows: 100% pass rate
- ✅ Execution time: < 15 minutes
- ✅ CI/CD integrated

### Quality Gates

```
✅ All critical tests pass (100%)
✅ High priority tests pass (95%+)
✅ No flaky tests (3+ retries)
✅ Performance budgets met
✅ Accessibility checks pass
✅ No console errors
```

---

**Last Updated**: January 2025  
**Maintained By**: QA Team  
**Sprint**: 3  
**Status**: ✅ Complete