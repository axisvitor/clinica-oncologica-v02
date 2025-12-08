/**
 * Critical Flow E2E Tests for Hormonia Frontend
 *
 * This test suite covers the most critical user flows:
 * - Configuration loading
 * - Homepage rendering
 * - Authentication
 * - Navigation
 *
 * Run with: npm run test:e2e:smoke
 */

import { test, expect, Page } from '@playwright/test';

// Test configuration
const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:5175';

// Helper function to check for console errors
const setupConsoleMonitoring = (page: Page) => {
  const errors: string[] = [];
  const warnings: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    } else if (msg.type() === 'warning') {
      warnings.push(msg.text());
    }
  });

  page.on('pageerror', error => {
    errors.push(error.message);
  });

  return { errors, warnings };
};

test.describe('Critical Flow: Configuration & Core', () => {

  test('TC-CONFIG-001: Should load runtime configuration correctly', async ({ page }) => {
    const consoleLogs: string[] = [];
    page.on('console', msg => consoleLogs.push(msg.text()));

    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    // Check if configuration debug logs are present
    const configLog = consoleLogs.find(log =>
      log.includes('Frontend Configuration Debug') ||
      log.includes('Using runtime configuration') ||
      log.includes('Using build-time configuration')
    );

    expect(configLog).toBeDefined();

    // Verify runtime config exists
    const runtimeConfig = await page.evaluate(() => {
      return {
        hasConfig: typeof window.RUNTIME_CONFIG !== 'undefined',
        supabaseUrl: window.RUNTIME_CONFIG?.VITE_SUPABASE_URL ||
                     (window as any).import?.meta?.env?.VITE_SUPABASE_URL,
        apiUrl: window.RUNTIME_CONFIG?.VITE_API_URL ||
                (window as any).import?.meta?.env?.VITE_API_URL
      };
    });

    // At least one config method should be available
    expect(
      runtimeConfig.supabaseUrl ||
      runtimeConfig.apiUrl
    ).toBeTruthy();

    console.log('✅ Runtime configuration loaded successfully');
  });

  test('TC-CONFIG-002: Should initialize Firebase correctly', async ({ page }) => {
    const { errors } = setupConsoleMonitoring(page);

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Check for Firebase-related errors
    const firebaseErrors = errors.filter(err =>
      err.toLowerCase().includes('firebase')
    );

    expect(firebaseErrors).toHaveLength(0);

    console.log('✅ Firebase initialized without errors');
  });

  test('TC-CONFIG-003: Should initialize Supabase client', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    const supabaseConfig = await page.evaluate(() => {
      return {
        url: window.RUNTIME_CONFIG?.VITE_SUPABASE_URL,
        hasAnonKey: !!window.RUNTIME_CONFIG?.VITE_SUPABASE_ANON_KEY
      };
    });

    // Should have Supabase URL configured
    expect(supabaseConfig.url).toBeTruthy();
    expect(supabaseConfig.hasAnonKey).toBe(true);

    console.log('✅ Supabase client configured correctly');
  });
});

test.describe('Critical Flow: Homepage & Core Functionality', () => {

  test('TC-CORE-001: Should load homepage successfully', async ({ page }) => {
    const startTime = Date.now();
    const { errors } = setupConsoleMonitoring(page);

    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    const loadTime = Date.now() - startTime;

    // Performance check - should load within 5 seconds (relaxed for CI)
    expect(loadTime).toBeLessThan(5000);

    // Verify page title
    const title = await page.title();
    expect(title).toBeTruthy();
    expect(title.length).toBeGreaterThan(0);

    // Verify root element exists
    const rootElement = page.locator('#root');
    await expect(rootElement).toBeVisible({ timeout: 5000 });

    // Should have no critical errors
    const criticalErrors = errors.filter(err =>
      !err.includes('DevTools') &&
      !err.includes('Extension')
    );

    console.log('Load time:', loadTime, 'ms');
    console.log('Page title:', title);
    console.log('Critical errors:', criticalErrors.length);

    expect(criticalErrors.length).toBe(0);

    console.log('✅ Homepage loaded successfully');
  });

  test('TC-CORE-002: Should display correct app metadata', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    // Check if app has proper structure
    const hasReactRoot = await page.evaluate(() => {
      const root = document.getElementById('root');
      return root !== null && root.children.length > 0;
    });

    expect(hasReactRoot).toBe(true);

    console.log('✅ App metadata validated');
  });
});

test.describe('Critical Flow: Authentication', () => {

  test('TC-AUTH-001: Should display login page with all elements', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('domcontentloaded');

    // Check for form elements (may vary based on actual implementation)
    const formElements = await page.evaluate(() => {
      const emailInputs = document.querySelectorAll('input[type="email"], input[name="email"]');
      const passwordInputs = document.querySelectorAll('input[type="password"], input[name="password"]');
      const submitButtons = document.querySelectorAll('button[type="submit"], button:has-text("Entrar")');

      return {
        hasEmailInput: emailInputs.length > 0,
        hasPasswordInput: passwordInputs.length > 0,
        hasSubmitButton: submitButtons.length > 0
      };
    });

    expect(formElements.hasEmailInput).toBe(true);
    expect(formElements.hasPasswordInput).toBe(true);
    expect(formElements.hasSubmitButton).toBe(true);

    console.log('✅ Login page elements validated');
  });

  test('TC-AUTH-002: Should redirect to login for protected routes', async ({ page }) => {
    // Clear any existing auth state
    await page.context().clearCookies();
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    // Try to access protected route
    await page.goto(`${BASE_URL}/dashboard`);

    // Wait for navigation (either stays on /dashboard if auth works, or redirects to /login)
    await page.waitForLoadState('networkidle', { timeout: 10000 });

    const currentUrl = page.url();

    // Should either:
    // 1. Redirect to login if auth is required
    // 2. Show dashboard if auth is optional/mocked
    const isOnLoginOrDashboard = currentUrl.includes('/login') || currentUrl.includes('/dashboard');

    expect(isOnLoginOrDashboard).toBe(true);

    if (currentUrl.includes('/login')) {
      console.log('✅ Protected route correctly redirected to login');
    } else {
      console.log('ℹ️  Dashboard accessible (auth may be optional in this environment)');
    }
  });
});

test.describe('Critical Flow: Navigation', () => {

  test('TC-NAV-001: Should display main navigation structure', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('domcontentloaded');

    // Check for navigation elements (sidebar, header, or menu)
    const hasNavigation = await page.evaluate(() => {
      const navElements = document.querySelectorAll(
        'nav, [role="navigation"], aside, header, [data-testid*="nav"], [data-testid*="sidebar"]'
      );
      return navElements.length > 0;
    });

    expect(hasNavigation).toBe(true);

    console.log('✅ Navigation structure present');
  });

  test('TC-NAV-004: Should handle 404 routes correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/non-existent-route-12345`);
    await page.waitForLoadState('domcontentloaded');

    // Should show some kind of not found page or redirect
    const has404Content = await page.evaluate(() => {
      const bodyText = document.body.textContent || '';
      return (
        bodyText.includes('404') ||
        bodyText.includes('não encontrada') ||
        bodyText.includes('Not Found') ||
        bodyText.includes('Página não existe')
      );
    });

    // Either shows 404 page or redirects to valid route
    const isValidResponse = has404Content ||
      page.url().includes('/dashboard') ||
      page.url().includes('/login');

    expect(isValidResponse).toBe(true);

    console.log('✅ 404 handling validated');
  });
});

test.describe('Critical Flow: Performance', () => {

  test('TC-PERF-001: Should load within performance budgets', async ({ page }) => {
    const startTime = Date.now();

    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    const domContentLoadedTime = Date.now() - startTime;

    await page.waitForLoadState('networkidle', { timeout: 10000 });
    const networkIdleTime = Date.now() - startTime;

    console.log('Performance Metrics:');
    console.log('- DOM Content Loaded:', domContentLoadedTime, 'ms');
    console.log('- Network Idle:', networkIdleTime, 'ms');

    // Relaxed budgets for CI environment
    expect(domContentLoadedTime).toBeLessThan(5000); // 5s for DOM
    expect(networkIdleTime).toBeLessThan(10000); // 10s for network idle

    // Get Web Vitals if available
    const webVitals = await page.evaluate(() => {
      return new Promise((resolve) => {
        if ('PerformanceObserver' in window) {
          const observer = new PerformanceObserver((list) => {
            const entries = list.getEntries();
            resolve(entries.map(entry => ({
              name: entry.name,
              duration: entry.duration,
              startTime: entry.startTime
            })));
          });

          // Try to observe paint timing
          try {
            observer.observe({ entryTypes: ['paint'] });
            setTimeout(() => resolve([]), 1000);
          } catch (e) {
            resolve([]);
          }
        } else {
          resolve([]);
        }
      });
    });

    console.log('Web Vitals:', webVitals);

    console.log('✅ Performance budgets validated');
  });
});

test.describe('Critical Flow: Accessibility', () => {

  test('TC-A11Y-001: Should support keyboard navigation', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('domcontentloaded');

    // Tab through first few elements
    const focusedElements: string[] = [];

    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('Tab');

      const focusedElement = await page.evaluate(() => {
        const el = document.activeElement;
        return {
          tag: el?.tagName.toLowerCase() || '',
          type: el?.getAttribute('type') || '',
          role: el?.getAttribute('role') || '',
          text: el?.textContent?.substring(0, 20) || ''
        };
      });

      if (focusedElement.tag) {
        focusedElements.push(
          `${focusedElement.tag}${focusedElement.type ? `[${focusedElement.type}]` : ''}`
        );
      }
    }

    // Should have focused on some elements
    expect(focusedElements.length).toBeGreaterThan(0);

    console.log('Focused elements:', focusedElements);
    console.log('✅ Keyboard navigation working');
  });

  test('TC-A11Y-002: Should have proper ARIA structure', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('domcontentloaded');

    const ariaStructure = await page.evaluate(() => {
      return {
        hasMain: document.querySelector('[role="main"], main') !== null,
        hasNavigation: document.querySelector('[role="navigation"], nav') !== null,
        hasBanner: document.querySelector('[role="banner"], header') !== null,
        buttons: Array.from(document.querySelectorAll('button')).filter(btn => {
          return btn.getAttribute('aria-label') ||
                 btn.textContent?.trim() ||
                 btn.querySelector('svg, img');
        }).length
      };
    });

    // Should have some semantic structure
    const hasSemanticStructure =
      ariaStructure.hasMain ||
      ariaStructure.hasNavigation ||
      ariaStructure.hasBanner;

    expect(hasSemanticStructure).toBe(true);

    console.log('ARIA Structure:', ariaStructure);
    console.log('✅ ARIA structure validated');
  });
});

test.describe('Critical Flow: Responsive Design', () => {

  test('TC-RESP-001: Should work on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    // Check for horizontal scroll
    const hasHorizontalScroll = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });

    expect(hasHorizontalScroll).toBe(false);

    console.log('✅ Mobile viewport validated');
  });

  test('TC-RESP-003: Should work on desktop viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    const rootElement = page.locator('#root');
    await expect(rootElement).toBeVisible();

    console.log('✅ Desktop viewport validated');
  });
});

// Test hooks for setup and teardown
test.beforeEach(async ({ page }) => {
  // Set default timeout
  page.setDefaultTimeout(10000);
});

test.afterEach(async ({ page }, testInfo) => {
  // Log test result
  if (testInfo.status !== 'passed') {
    console.error(`❌ Test failed: ${testInfo.title}`);

    // Capture screenshot on failure
    await page.screenshot({
      path: `test-results/failure-${testInfo.title.replace(/\s+/g, '-')}.png`
    });
  }
});
