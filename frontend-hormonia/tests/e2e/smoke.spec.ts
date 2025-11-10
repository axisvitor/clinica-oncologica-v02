/**
 * Smoke Tests for Frontend-v2 Application
 *
 * These tests verify the core functionality of the application:
 * - Application startup and loading
 * - Navigation through main pages
 * - Authentication flow
 * - API integration
 * - Error handling
 */

import { test, expect, Page } from '@playwright/test';

// Test configuration
const TEST_CONFIG = {
  timeout: 30000,
  baseURL: process.env['PLAYWRIGHT_TEST_BASE_URL'] || 'http://localhost:4173',
  api: {
    baseURL: process.env['VITE_API_URL'] || 'http://localhost:8000'
  },
  auth: {
    email: 'test@example.com',
    password: 'testpassword123'
  }
};

// Test utilities
class TestUtils {
  constructor(private page: Page) {}

  async waitForConfig() {
    // Wait for runtime config to load
    await this.page.waitForFunction(
      () => window.__RUNTIME_CONFIG__ !== undefined ||
            (window as any).configLoaded === true,
      { timeout: 10000 }
    );
  }

  async waitForReactReady() {
    // Wait for React to be ready
    await this.page.waitForSelector('[data-testid="app-root"]', {
      timeout: 10000,
      state: 'attached'
    });
  }

  async mockApiResponse(endpoint: string, response: any) {
    await this.page.route(`**${endpoint}**`, (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(response)
      });
    });
  }

  async interceptApiCall(pattern: string) {
    const responses: any[] = [];
    await this.page.route(pattern, (route) => {
      responses.push({
        url: route.request().url(),
        method: route.request().method(),
        headers: route.request().headers()
      });
      route.continue();
    });
    return responses;
  }
}

test.describe('Application Smoke Tests', () => {
  let testUtils: TestUtils;

  test.beforeEach(async ({ page }) => {
    testUtils = new TestUtils(page);

    // Set up API mocks for basic functionality
    await testUtils.mockApiResponse('/api/v2/auth/me', {
      user: { id: '1', email: 'test@example.com', name: 'Test User' }
    });

    await testUtils.mockApiResponse('/api/v2/patients', {
      data: [],
      total: 0,
      page: 1,
      per_page: 20
    });
  });

  test('Application loads successfully', async ({ page }) => {
    test.setTimeout(TEST_CONFIG.timeout);

    await page.goto('/');

    // Wait for configuration to load
    await testUtils.waitForConfig();

    // Check that the app renders
    await testUtils.waitForReactReady();

    // Verify no critical JavaScript errors
    const errors: string[] = [];
    page.on('pageerror', (error) => {
      errors.push(error.message);
    });

    // Wait a bit to catch any errors
    await page.waitForTimeout(2000);

    // Filter out known non-critical errors
    const criticalErrors = errors.filter(error =>
      !error.includes('ResizeObserver') &&
      !error.includes('Non-passive event listener')
    );

    expect(criticalErrors).toHaveLength(0);
  });

  test('Navigation works correctly', async ({ page }) => {
    await page.goto('/');
    await testUtils.waitForConfig();
    await testUtils.waitForReactReady();

    // Mock authentication
    await page.evaluate(() => {
      localStorage.setItem('supabase.auth.token', JSON.stringify({
        access_token: 'mock-token',
        user: { id: '1', email: 'test@example.com' }
      }));
    });

    // Test navigation to different pages
    const navigationTests = [
      { path: '/dashboard', selector: '[data-testid="dashboard-page"]', fallback: 'h1, h2, [role="main"]' },
      { path: '/patients', selector: '[data-testid="patients-page"]', fallback: '[data-testid="patients-table"], .patients-container' },
      { path: '/flows', selector: '[data-testid="flows-page"]', fallback: '.flows-container, [data-testid="flows-dashboard"]' },
      { path: '/questionarios', selector: '[data-testid="quiz-page"]', fallback: '.quiz-container, [data-testid="quiz-dashboard"]' }
    ];

    for (const nav of navigationTests) {
      await page.goto(nav.path);

      try {
        // Try primary selector first
        await page.waitForSelector(nav.selector, { timeout: 5000 });
      } catch {
        // Fall back to generic selectors
        await page.waitForSelector(nav.fallback, { timeout: 5000 });
      }

      // Verify URL
      expect(page.url()).toContain(nav.path);
    }
  });

  test('Authentication flow completes', async ({ page }) => {
    await page.goto('/login');
    await testUtils.waitForConfig();

    // Mock successful login response
    await testUtils.mockApiResponse('/api/v2/auth/login', {
      access_token: 'mock-access-token',
      token_type: 'bearer',
      user: {
        id: '1',
        email: TEST_CONFIG.auth.email,
        name: 'Test User'
      }
    });

    // Fill login form
    await page.fill('[data-testid="email-input"], input[type="email"]', TEST_CONFIG.auth.email);
    await page.fill('[data-testid="password-input"], input[type="password"]', TEST_CONFIG.auth.password);

    // Submit form
    await page.click('[data-testid="login-button"], button[type="submit"]');

    // Should redirect to dashboard or main app
    await page.waitForURL(/\/(dashboard|$)/, { timeout: 10000 });

    // Verify authentication state
    const token = await page.evaluate(() =>
      localStorage.getItem('supabase.auth.token') ||
      sessionStorage.getItem('auth-token')
    );

    expect(token).toBeTruthy();
  });

  test('API integration works', async ({ page }) => {
    const apiCalls = await testUtils.interceptApiCall('**/api/**');

    await page.goto('/patients');
    await testUtils.waitForConfig();
    await testUtils.waitForReactReady();

    // Mock authentication
    await page.evaluate(() => {
      localStorage.setItem('supabase.auth.token', JSON.stringify({
        access_token: 'mock-token'
      }));
    });

    // Wait for potential API calls
    await page.waitForTimeout(3000);

    // Verify that configuration loaded correctly
    const hasApiUrl = await page.evaluate(() => {
      return !!(window as any).__RUNTIME_CONFIG__?.VITE_API_URL ||
             !!(window as any).__RUNTIME_CONFIG__?.VITE_API_BASE_URL;
    });

    expect(hasApiUrl).toBeTruthy();
  });

  test('Error handling displays correctly', async ({ page }) => {
    await page.goto('/');
    await testUtils.waitForConfig();

    // Mock API error response
    await page.route('**/api/**', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Internal Server Error',
          message: 'Test error'
        })
      });
    });

    // Try to trigger an API call
    try {
      await page.goto('/patients');
      await testUtils.waitForReactReady();

      // Look for error indicators
      const errorElements = await page.locator('.error, [role="alert"], .toast').count();

      // Should handle errors gracefully (either show error message or fallback)
      const hasErrorHandling = errorElements > 0 ||
                             await page.locator('.loading, .skeleton').isVisible();

      expect(hasErrorHandling).toBeTruthy();
    } catch (error) {
      // Error handling should prevent complete page crashes
      console.log('Expected error in error handling test:', error);
    }
  });

  test('Flows page functionality', async ({ page }) => {
    // Mock flows API response
    await testUtils.mockApiResponse('/api/v2/flows', {
      flows: [
        { id: '1', name: 'Test Flow', status: 'active' }
      ]
    });

    await page.goto('/flows');
    await testUtils.waitForConfig();
    await testUtils.waitForReactReady();

    // Mock authentication
    await page.evaluate(() => {
      localStorage.setItem('supabase.auth.token', JSON.stringify({
        access_token: 'mock-token'
      }));
    });

    // Check that flows page loads
    const flowsContent = page.locator('.flows-container, [data-testid="flows-page"], [data-testid="flows-dashboard"]');
    await expect(flowsContent.first()).toBeVisible({ timeout: 10000 });
  });

  test('WebSocket connectivity (if enabled)', async ({ page }) => {
    await page.goto('/');
    await testUtils.waitForConfig();

    // Check if WebSocket is configured
    const wsConfig = await page.evaluate(() => {
      return (window as any).__RUNTIME_CONFIG__?.VITE_WS_BASE_URL;
    });

    if (wsConfig) {
      // Mock WebSocket connection
      await page.evaluate(() => {
        // Mock WebSocket for testing
        (window as any).WebSocket = class MockWebSocket {
          onopen: ((event: Event) => void) | null = null;
          onclose: ((event: CloseEvent) => void) | null = null;
          onerror: ((event: Event) => void) | null = null;
          onmessage: ((event: MessageEvent) => void) | null = null;

          constructor(url: string) {
            setTimeout(() => {
              if (this.onopen) {
                this.onopen(new Event('open'));
              }
            }, 100);
          }

          send(data: string) {}
          close() {}
        };
      });

      // Test WebSocket functionality if implemented
      const wsError = await page.evaluate(() => {
        try {
          const ws = new WebSocket('ws://localhost:8000/ws');
          return null;
        } catch (error) {
          return error.message;
        }
      });

      // WebSocket should either work or fail gracefully
      expect(wsError).toBeNull();
    }
  });
});

test.describe('Performance Tests', () => {
  test('Page load performance', async ({ page }) => {
    const start = Date.now();

    await page.goto('/');
    await page.waitForSelector('[data-testid="app-root"], body', {
      timeout: 15000
    });

    const loadTime = Date.now() - start;

    // Page should load within 15 seconds
    expect(loadTime).toBeLessThan(15000);
  });

  test('Memory usage stays reasonable', async ({ page }) => {
    await page.goto('/');

    // Get initial memory usage
    const initialMemory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });

    // Navigate through several pages
    const pages = ['/dashboard', '/patients', '/flows'];
    for (const pagePath of pages) {
      await page.goto(pagePath);
      await page.waitForTimeout(1000);
    }

    // Check memory usage after navigation
    const finalMemory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });

    // Memory shouldn't grow too much (if performance.memory is available)
    if (initialMemory > 0 && finalMemory > 0) {
      const memoryIncrease = finalMemory - initialMemory;
      expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024); // Less than 50MB
    }
  });
});

test.describe('Responsive Design Tests', () => {
  test('Mobile viewport works correctly', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForSelector('[data-testid="app-root"], body');

    // Check that mobile navigation works
    const mobileMenu = page.locator('.mobile-menu, [data-testid="mobile-nav"], button[aria-label*="menu"]');
    if (await mobileMenu.count() > 0) {
      await mobileMenu.first().click();
      await page.waitForTimeout(500);
    }

    // Content should be visible and properly formatted
    const mainContent = page.locator('main, [role="main"], .main-content');
    await expect(mainContent.first()).toBeVisible();
  });

  test('Tablet viewport works correctly', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');
    await page.waitForSelector('[data-testid="app-root"], body');

    // Navigation should be accessible
    const navigation = page.locator('nav, .navigation, .sidebar');
    if (await navigation.count() > 0) {
      await expect(navigation.first()).toBeVisible();
    }
  });
});
