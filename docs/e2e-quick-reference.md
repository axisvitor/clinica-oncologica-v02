# E2E Testing Quick Reference Card

## 🚀 Quick Commands

### Essential Commands
```bash
# Run all E2E tests
npm run test:e2e

# Run smoke tests (fastest)
npm run test:e2e:smoke

# Run with visible browser
npm run test:e2e:headed

# Run in UI mode (interactive)
npm run test:e2e:ui

# Run specific test file
npx playwright test critical-flow

# Run integration tests
npx playwright test integration
```

### Debugging
```bash
# Debug mode
npm run test:e2e:debug

# View HTML report
npm run test:e2e:report

# Show trace for failed test
npx playwright show-trace test-results/trace.zip

# Run single test with debug
npx playwright test --debug -g "Should load homepage"
```

### Browser-Specific
```bash
# Chrome only
npx playwright test --project="Desktop Chrome"

# Firefox only
npx playwright test --project="Desktop Firefox"

# Mobile Safari
npx playwright test --project="Mobile Safari"

# All browsers
npx playwright test
```

## 📋 Test Categories Quick Access

| Category | Command | Duration |
|----------|---------|----------|
| **Smoke Tests** | `npm run test:e2e:smoke` | ~2 min |
| **Critical Flow** | `npx playwright test critical-flow` | ~5 min |
| **Integration** | `npx playwright test integration` | ~8 min |
| **Full Suite** | `npm run test:e2e` | ~15 min |

## 🎯 Test Coverage

### Critical Tests (MUST PASS)
- ✅ TC-CONFIG-001: Runtime config loading
- ✅ TC-CONFIG-002: Firebase initialization
- ✅ TC-CONFIG-003: Supabase client setup
- ✅ TC-CORE-001: Homepage load
- ✅ TC-AUTH-001: Login page display
- ✅ TC-AUTH-002: Protected route redirect

### High Priority Tests
- ⚡ TC-NAV-001: Navigation menu
- ⚡ TC-PERF-001: Page load performance
- ⚡ TC-A11Y-001: Keyboard navigation
- ⚡ TC-RESP-001: Mobile responsive
- ⚡ TC-INT-001: Firebase auth integration

## 🔧 Prerequisites Checklist

```bash
# 1. Frontend running
npm run dev
# → http://localhost:5175 ✅

# 2. Playwright installed
npm run setup:playwright
# → Browsers installed ✅

# 3. Environment configured
cat .env.local | grep VITE_
# → All VITE_* vars present ✅
```

## 📊 Quick Test Execution Matrix

### Local Development Flow
```bash
# 1. Make changes to code
# 2. Run smoke tests
npm run test:e2e:smoke

# 3. If passed, run critical tests
npx playwright test critical-flow

# 4. If all passed, run full suite
npm run test:e2e
```

### Pre-Commit Flow
```bash
# Run critical tests only
npx playwright test critical-flow --reporter=list
```

### Pre-Deploy Flow
```bash
# Full suite with report
npm run test:e2e
npm run test:e2e:report
```

## 🐛 Troubleshooting Quick Fixes

### Test Fails: "Page closed"
```bash
# Increase timeout
test.setTimeout(60000);
```

### Test Fails: "Element not found"
```typescript
// Add explicit wait
await page.waitForSelector('[data-testid="element"]', {
  state: 'visible',
  timeout: 10000
});
```

### Test Fails: Authentication
```typescript
// Clear auth state
await page.context().clearCookies();
await page.evaluate(() => {
  localStorage.clear();
  sessionStorage.clear();
});
```

### Tests Pass Locally, Fail in CI
```bash
# Run in CI mode locally
CI=true npm run test:e2e
```

### WebSocket Connection Fails
```bash
# Check backend is running
curl http://localhost:8000/health
```

## 📈 Performance Budgets

| Metric | Budget | Test |
|--------|--------|------|
| **Page Load** | < 3s | TC-PERF-001 |
| **FCP** | < 1.5s | TC-PERF-001 |
| **LCP** | < 2.5s | TC-PERF-001 |
| **TTI** | < 3s | TC-PERF-001 |
| **Bundle Size** | < 1MB | TC-PERF-002 |
| **API Response** | < 1s | TC-PERF-003 |

## 🎨 Test Writing Template

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Category', () => {

  test('TC-XXX-YYY: Should perform specific action', async ({ page }) => {
    // Arrange
    await page.goto('/');

    // Act
    await page.click('[data-testid="button"]');

    // Assert
    await expect(page.locator('.result')).toBeVisible();

    console.log('✅ Test completed successfully');
  });

  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== 'passed') {
      await page.screenshot({
        path: `test-results/failure-${testInfo.title}.png`
      });
    }
  });
});
```

## 🔑 Environment Variables

### Required for Tests
```env
PLAYWRIGHT_TEST_BASE_URL=http://localhost:5175
VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

### Optional
```env
VITE_FIREBASE_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
```

## 📱 Browser Support

| Browser | Desktop | Mobile | Command |
|---------|---------|--------|---------|
| **Chrome** | ✅ v90+ | ✅ Latest | `--project="Desktop Chrome"` |
| **Firefox** | ✅ v88+ | ✅ Latest | `--project="Desktop Firefox"` |
| **Safari** | ✅ v14+ | ✅ iOS 14+ | `--project="Desktop Safari"` |
| **Edge** | ✅ v90+ | - | `--project="Desktop Edge"` |

## 🎯 Success Criteria

### Pass Rates
- 🟢 Critical: 100%
- 🟢 High: 95%
- 🟡 Medium: 90%
- 🟡 Low: 85%

### Quality Gates
- ✅ Zero console errors on critical paths
- ✅ WCAG AA accessibility compliance
- ✅ Performance budgets met
- ✅ No memory leaks
- ✅ Responsive on all devices

## 📚 Documentation Links

- [Full Test Plan](./e2e-test-plan-hormonia.md)
- [Test Plan Summary](./e2e-test-plan-summary.md)
- [E2E Tests README](../frontend-hormonia/tests/e2e/README.md)
- [Playwright Docs](https://playwright.dev)

## 🚦 CI/CD Integration

### GitHub Actions
```yaml
- name: Run E2E Tests
  run: npm run test:e2e
  env:
    VITE_SUPABASE_URL: ${{ secrets.VITE_SUPABASE_URL }}
    VITE_SUPABASE_ANON_KEY: ${{ secrets.VITE_SUPABASE_ANON_KEY }}
```

### Required Secrets
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_PROJECT_ID`

## 🔄 Update Frequency

| Test Type | Frequency | Command |
|-----------|-----------|---------|
| **Smoke** | Every commit | `npm run test:e2e:smoke` |
| **Critical** | Before push | `npx playwright test critical-flow` |
| **Full Suite** | Pre-deploy | `npm run test:e2e` |
| **Weekly** | Monday 9am | `npm run test:e2e` + accessibility |

## 💡 Pro Tips

1. **Use UI Mode for Development**
   ```bash
   npm run test:e2e:ui
   ```
   - Visual test runner
   - Time travel debugging
   - Pick locator tool

2. **Debug Specific Test**
   ```bash
   npx playwright test --debug -g "homepage"
   ```

3. **Run Tests in Parallel**
   ```bash
   npx playwright test --workers=4
   ```

4. **Update Screenshots**
   ```bash
   npx playwright test --update-snapshots
   ```

5. **Generate Report Automatically**
   ```bash
   npm run test:e2e && npm run test:e2e:report
   ```

## 📞 Support Contacts

- **Slack:** #hormonia-testing
- **Email:** dev@hormonia.com
- **Issues:** [GitHub Issues](https://github.com/your-repo/issues)
- **Docs:** [Confluence](https://your-org.atlassian.net/wiki)

---

**Last Updated:** 2025-10-04
**Version:** 1.0
**Print this for your desk! 📌**
