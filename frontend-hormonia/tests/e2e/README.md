# Hormonia E2E Test Suite

Comprehensive end-to-end testing for the Hormonia frontend application using Playwright.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Categories](#test-categories)
- [Writing Tests](#writing-tests)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

## 🚀 Quick Start

### Prerequisites

1. **Frontend running:**
   ```bash
   npm run dev
   # Application should be accessible at http://localhost:5175
   ```

2. **Install Playwright:**
   ```bash
   npm run setup:playwright
   # or
   npx playwright install --with-deps
   ```

3. **Environment Setup:**
   Create or verify `.env.local` file in frontend-hormonia directory:
   ```env
   VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
   VITE_SUPABASE_ANON_KEY=your_anon_key
   VITE_API_URL=http://localhost:8000/api/v2
   VITE_WS_URL=ws://localhost:8000/ws
   ```

### Run Your First Test

```bash
# Run all E2E tests
npm run test:e2e

# Run critical flow tests only
npx playwright test critical-flow

# Run integration tests
npx playwright test integration

# Run in headed mode (visible browser)
npm run test:e2e:headed

# Run with UI mode (interactive)
npm run test:e2e:ui
```

## 📁 Test Structure

```
tests/e2e/
├── README.md                    # This file
├── critical-flow.spec.ts        # Critical user flows
├── integration.spec.ts          # External service integrations
├── smoke.spec.ts               # Quick smoke tests
├── runtime-config.spec.ts      # Configuration tests
├── global-setup.ts             # Test setup
├── global-teardown.ts          # Test cleanup
└── fixtures/                    # Test fixtures and helpers
```

## 🧪 Test Categories

### Critical Flow Tests (`critical-flow.spec.ts`)
Tests the most important user journeys:
- ✅ Configuration loading (Firebase, Supabase)
- ✅ Homepage rendering and core functionality
- ✅ Authentication flows
- ✅ Navigation and routing
- ✅ Performance budgets
- ✅ Accessibility compliance
- ✅ Responsive design

**Run with:**
```bash
npx playwright test critical-flow
```

### Integration Tests (`integration.spec.ts`)
Tests integration with external services:
- 🔌 Firebase Authentication
- 🔌 Supabase Database
- 🔌 WebSocket Connection
- 🔌 API Integration
- 🔌 WhatsApp Service
- 🔌 Real-time Features
- 🔌 Session Management
- 🔌 Error Handling

**Run with:**
```bash
npx playwright test integration
```

### Smoke Tests (`smoke.spec.ts`)
Quick validation tests for rapid feedback:
- ⚡ Homepage loads
- ⚡ Login page accessible
- ⚡ Configuration valid

**Run with:**
```bash
npm run test:e2e:smoke
```

## 🏃 Running Tests

### Local Development

```bash
# Run all tests
npm run test:e2e

# Run specific test file
npx playwright test critical-flow.spec.ts

# Run specific test by name
npx playwright test -g "Should load homepage"

# Run in headed mode (see browser)
npm run test:e2e:headed

# Run in debug mode
npm run test:e2e:debug

# Run on specific browser
npx playwright test --project="Desktop Chrome"
npx playwright test --project="Mobile Safari"

# Run tests in parallel
npx playwright test --workers=4

# Update snapshots
npx playwright test --update-snapshots
```

### Interactive Mode

```bash
# Launch UI mode for interactive testing
npm run test:e2e:ui

# Features:
# - Visual test execution
# - Step-by-step debugging
# - Time travel debugging
# - Pick locator tool
```

### Reports and Debugging

```bash
# Generate and view HTML report
npm run test:e2e:report

# View trace for failed tests
npx playwright show-trace test-results/trace.zip

# Record video of test execution
npx playwright test --video=on
```

## ✍️ Writing Tests

### Test Template

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {

  test('TC-XXX-YYY: Should do something specific', async ({ page }) => {
    // Arrange
    await page.goto('/');

    // Act
    await page.click('button');

    // Assert
    await expect(page.locator('.result')).toBeVisible();
  });

});
```

### Best Practices

1. **Use Descriptive Test Names:**
   ```typescript
   // ✅ Good
   test('TC-AUTH-001: Should redirect to login for protected routes', ...)

   // ❌ Bad
   test('auth test', ...)
   ```

2. **Use Test IDs for Reliable Selectors:**
   ```typescript
   // ✅ Preferred
   await page.click('[data-testid="submit-button"]');

   // ⚠️ Use with caution
   await page.click('.btn.primary');
   ```

3. **Wait for Proper States:**
   ```typescript
   // ✅ Good
   await page.waitForLoadState('networkidle');
   await expect(element).toBeVisible();

   // ❌ Bad
   await page.waitForTimeout(5000);
   ```

4. **Handle Async Operations:**
   ```typescript
   // ✅ Good
   await Promise.all([
     page.waitForNavigation(),
     page.click('a[href="/dashboard"]')
   ]);

   // ❌ Bad
   await page.click('a[href="/dashboard"]');
   // No wait for navigation
   ```

5. **Use Page Object Model for Complex Pages:**
   ```typescript
   class LoginPage {
     constructor(private page: Page) {}

     async login(email: string, password: string) {
       await this.page.fill('[data-testid="email"]', email);
       await this.page.fill('[data-testid="password"]', password);
       await this.page.click('[data-testid="submit"]');
     }
   }
   ```

### Common Patterns

#### Check for Console Errors
```typescript
const errors: string[] = [];
page.on('console', msg => {
  if (msg.type() === 'error') errors.push(msg.text());
});

await page.goto('/');
expect(errors).toHaveLength(0);
```

#### Monitor Network Requests
```typescript
const apiCalls: string[] = [];
page.on('request', req => {
  if (req.url().includes('/api/')) {
    apiCalls.push(req.url());
  }
});

await page.goto('/dashboard');
expect(apiCalls.length).toBeGreaterThan(0);
```

#### Take Screenshot on Failure
```typescript
test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== 'passed') {
    await page.screenshot({
      path: `test-results/failure-${testInfo.title}.png`,
      fullPage: true
    });
  }
});
```

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright
        run: npx playwright install --with-deps

      - name: Run E2E tests
        run: npm run test:e2e
        env:
          PLAYWRIGHT_TEST_BASE_URL: http://localhost:5175
          VITE_SUPABASE_URL: ${{ secrets.VITE_SUPABASE_URL }}
          VITE_SUPABASE_ANON_KEY: ${{ secrets.VITE_SUPABASE_ANON_KEY }}

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: test-results/
```

### Environment Variables for CI

Create these secrets in your repository:
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_PROJECT_ID`

## 🐛 Troubleshooting

### Common Issues

#### Issue: Tests fail with "Target closed" error
**Solution:**
```bash
# Increase timeout
npx playwright test --timeout=60000

# Or in test file:
test.setTimeout(60000);
```

#### Issue: Cannot find element
**Solution:**
```typescript
// Add explicit waits
await page.waitForSelector('[data-testid="element"]', {
  state: 'visible',
  timeout: 10000
});
```

#### Issue: Tests pass locally but fail in CI
**Solution:**
```bash
# Run tests in CI mode locally
CI=true npm run test:e2e

# Use headless mode explicitly
npx playwright test --headed=false
```

#### Issue: WebSocket connection fails
**Solution:**
```bash
# Verify backend is running
curl http://localhost:8000/health

# Check WebSocket URL in config
echo $VITE_WS_URL
```

#### Issue: Authentication tests fail
**Solution:**
```bash
# Clear auth state before test
await page.context().clearCookies();
await page.evaluate(() => {
  localStorage.clear();
  sessionStorage.clear();
});
```

### Debug Mode

```bash
# Run specific test in debug mode
npx playwright test --debug critical-flow.spec.ts

# Use Playwright Inspector
PWDEBUG=1 npx playwright test

# Enable verbose logging
DEBUG=pw:api npx playwright test
```

### Trace Viewer

```bash
# Record trace
npx playwright test --trace=on

# View trace
npx playwright show-trace test-results/trace.zip
```

## 📊 Test Metrics

### Success Criteria
- ✅ **Critical tests:** 100% pass rate
- ✅ **High priority:** 95% pass rate
- ✅ **Medium priority:** 90% pass rate
- ✅ **Performance:** < 3s page load

### Coverage Goals
- Configuration: 100%
- Authentication: 100%
- Core features: 95%
- UI components: 90%
- Integrations: 95%

## 📚 Additional Resources

- [Playwright Documentation](https://playwright.dev)
- [Full Test Plan](../../docs/e2e-test-plan-hormonia.md)
- [Test Plan Summary](../../docs/e2e-test-plan-summary.md)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)

## 🤝 Contributing

### Adding New Tests

1. Identify test category (critical, integration, etc.)
2. Write test following naming convention: `TC-CATEGORY-XXX`
3. Add descriptive test name
4. Include arrange-act-assert structure
5. Add console logging for debugging
6. Update this README if adding new category

### Test Naming Convention

```
TC-[CATEGORY]-[NUMBER]: [Description]

Categories:
- CONFIG: Configuration tests
- CORE: Core functionality
- AUTH: Authentication
- NAV: Navigation
- UI: UI components
- PERF: Performance
- A11Y: Accessibility
- RESP: Responsive design
- INT: Integration
- FEAT: Feature-specific
```

### Code Review Checklist

- [ ] Test has unique ID and descriptive name
- [ ] Follows arrange-act-assert pattern
- [ ] Uses reliable selectors (data-testid preferred)
- [ ] Has proper waits (no arbitrary timeouts)
- [ ] Includes console logging
- [ ] Has screenshot on failure
- [ ] Documented in test plan

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/your-repo/issues)
- **Slack:** #hormonia-testing
- **Email:** dev@hormonia.com

---

**Last Updated:** 2025-10-04
**Maintained By:** QA Team
**Status:** ✅ Active
