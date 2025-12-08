/**
 * E2E Test Setup and Utilities
 *
 * This file provides shared setup functions and utilities for E2E tests.
 * It handles authentication, database setup, and common test configurations.
 */

import { test as setup, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

// ES module compatibility
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Authentication storage path
const authFile = path.join(__dirname, '../.auth/user.json');

/**
 * Global setup for authenticated tests
 * This runs once before all tests and sets up authentication state
 */
setup('authenticate', async ({ page }) => {
  // Navigate to login page
  await page.goto('/login');

  // Wait for page to load
  await page.waitForSelector('[data-testid="login-form"], form', { timeout: 10000 });

  // Mock successful authentication response
  await page.route('**/api/v2/auth/login', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'test-access-token',
        token_type: 'bearer',
        expires_in: 3600,
        user: {
          id: '1',
          email: 'test@example.com',
          name: 'Test User',
          role: 'user'
        }
      })
    });
  });

  // Fill login form
  await page.fill('[data-testid="email-input"], input[type="email"]', 'test@example.com');
  await page.fill('[data-testid="password-input"], input[type="password"]', 'testpassword123');

  // Submit form
  await page.click('[data-testid="login-button"], button[type="submit"]');

  // Wait for redirect to dashboard or main app
  await page.waitForURL(/\/(dashboard|$)/, { timeout: 15000 });

  // Verify authentication state
  await expect(page.locator('[data-testid="user-menu"], .user-profile')).toBeVisible({ timeout: 5000 });

  // Save authentication state
  await page.context().storageState({ path: authFile });
});

/**
 * Database setup (if needed)
 * This can be used to set up test data or clean database state
 */
setup('database setup', async ({ request }) => {
  // Example: Clear test data
  try {
    await request.delete('/api/v2/test/cleanup', {
      headers: {
        ['Authorization']: 'Bearer test-token'
      }
    });
  } catch (error) {
    // Ignore if cleanup endpoint doesn't exist
    console.log('Database cleanup skipped:', error.message);
  }

  // Example: Create test data
  try {
    await request.post('/api/v2/test/setup', {
      headers: {
        ['Authorization']: 'Bearer test-token',
        'Content-Type': 'application/json'
      },
      data: {
        patients: [],
        flows: [],
        templates: []
      }
    });
  } catch (error) {
    // Ignore if setup endpoint doesn't exist
    console.log('Database setup skipped:', error.message);
  }
});

/**
 * Common test utilities and helpers
 */
export class TestHelpers {
  static async mockApiResponse(page: any, endpoint: string, response: any, options: any = {}) {
    const { status = 200, delay = 0 } = options;

    await page.route(`**${endpoint}**`, async (route: any) => {
      if (delay > 0) {
        await new Promise(resolve => setTimeout(resolve, delay));
      }

      await route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(response)
      });
    });
  }

  static async mockApiError(page: any, endpoint: string, errorCode: number = 500, message: string = 'Internal Server Error') {
    await page.route(`**${endpoint}**`, (route: any) => {
      route.fulfill({
        status: errorCode,
        contentType: 'application/json',
        body: JSON.stringify({
          error: message,
          code: errorCode
        })
      });
    });
  }

  static async waitForToast(page: any, message?: string) {
    const toastSelector = '.toast, [role="alert"], .notification';

    if (message) {
      await expect(page.locator(toastSelector).filter({ hasText: message })).toBeVisible({ timeout: 5000 });
    } else {
      await expect(page.locator(toastSelector).first()).toBeVisible({ timeout: 5000 });
    }
  }

  static async waitForLoadingToComplete(page: any) {
    // Wait for loading indicators to disappear
    const loadingSelectors = [
      '.loading',
      '.spinner',
      '[data-testid="loading"]',
      '.skeleton'
    ];

    for (const selector of loadingSelectors) {
      try {
        await page.waitForSelector(selector, { state: 'detached', timeout: 1000 });
      } catch {
        // Loading element might not exist, continue
      }
    }
  }

  static async fillForm(page: any, formData: Record<string, string>) {
    for (const [field, value] of Object.entries(formData)) {
      const selector = `[name="${field}"], [data-testid="${field}-input"], #${field}`;
      await page.fill(selector, value);
    }
  }

  static async interceptNetworkRequests(page: any, pattern: string) {
    const requests: any[] = [];

    await page.route(pattern, (route: any) => {
      requests.push({
        url: route.request().url(),
        method: route.request().method(),
        headers: route.request().headers(),
        postData: route.request().postData()
      });
      route.continue();
    });

    return requests;
  }

  static async setAuthToken(page: any, token: string) {
    await page.evaluate((token) => {
      localStorage.setItem('supabase.auth.token', JSON.stringify({
        access_token: token,
        token_type: 'bearer',
        user: { id: '1', email: 'test@example.com' }
      }));
    }, token);
  }

  static async clearAuth(page: any) {
    await page.evaluate(() => {
      localStorage.removeItem('supabase.auth.token');
      sessionStorage.clear();
    });
  }

  static async mockRuntimeConfig(page: any, config: Record<string, any> = {}) {
    const defaultConfig = {
      VITE_SUPABASE_URL: 'https://test.supabase.co',
      VITE_SUPABASE_ANON_KEY: 'test-anon-key',
      VITE_API_URL: 'http://localhost:8000',
      VITE_WS_BASE_URL: 'ws://localhost:8000/ws',
      VITE_ENVIRONMENT: 'test',
      VITE_DEBUG_MODE: 'true',
      ...config
    };

    await page.addInitScript((config) => {
      (window as any).__RUNTIME_CONFIG__ = config;
      (window as any).configLoaded = true;
    }, defaultConfig);

    await page.route('**/runtime-config.json', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(defaultConfig)
      });
    });
  }

  static async takeScreenshotOnFailure(page: any, testInfo: any) {
    if (testInfo.status !== 'passed') {
      const screenshot = await page.screenshot();
      await testInfo.attach('screenshot', { body: screenshot, contentType: 'image/png' });
    }
  }

  static async getConsoleErrors(page: any) {
    const errors: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    return errors;
  }

  static async expectNoConsoleErrors(page: any, allowedErrors: string[] = []) {
    const errors = await this.getConsoleErrors(page);
    const criticalErrors = errors.filter(error =>
      !allowedErrors.some(allowed => error.includes(allowed))
    );

    expect(criticalErrors).toHaveLength(0);
  }
}

/**
 * Test data factories for creating consistent test data
 */
export class TestDataFactory {
  static createPatient(overrides: any = {}) {
    return {
      id: '1',
      name: 'Test Patient',
      email: 'patient@example.com',
      phone: '+5511999999999',
      birthDate: '1990-01-01',
      cpf: '12345678901',
      ...overrides
    };
  }

  static createFlow(overrides: any = {}) {
    return {
      id: '1',
      name: 'Test Flow',
      description: 'Test flow description',
      status: 'active',
      steps: [],
      ...overrides
    };
  }

  static createQuizSession(overrides: any = {}) {
    return {
      id: '1',
      patientId: '1',
      quizType: 'monthly',
      status: 'pending',
      responses: [],
      createdAt: new Date().toISOString(),
      ...overrides
    };
  }

  static createAuthUser(overrides: any = {}) {
    return {
      id: '1',
      email: 'test@example.com',
      name: 'Test User',
      role: 'user',
      ...overrides
    };
  }
}

/**
 * Environment configuration for tests
 */
export const TestEnvironment = {
  getBaseUrl() {
    return process.env['PLAYWRIGHT_TEST_BASE_URL'] || 'http://localhost:4173';
  },

  getApiUrl() {
    return process.env['VITE_API_URL'] || 'http://localhost:8000';
  },

  isCI() {
    return !!process.env['CI'];
  },

  isDevelopment() {
    return !this.isCI();
  },

  getTimeout() {
    return this.isCI() ? 30000 : 15000;
  },

  shouldTakeScreenshots() {
    return this.isCI() || process.env['TAKE_SCREENSHOTS'] === 'true';
  },

  shouldRecordVideo() {
    return this.isCI() || process.env['RECORD_VIDEO'] === 'true';
  }
};

export { authFile };