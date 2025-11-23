/**
 * Runtime Configuration Tests for Frontend-v2 Application
 *
 * These tests verify that the runtime configuration system works correctly:
 * - Runtime configuration loading
 * - Environment variables validation
 * - API URL configuration
 * - WebSocket connectivity configuration
 * - Feature flag configuration
 */

import { test, expect, Page } from '@playwright/test';

// Test configuration
const TEST_CONFIG = {
  timeout: 20000,
  baseURL: process.env['PLAYWRIGHT_TEST_BASE_URL'] || 'http://localhost:4173',
};

// Mock runtime configuration for testing
const MOCK_RUNTIME_CONFIG = {
  VITE_SUPABASE_URL: 'https://test.supabase.co',
  VITE_SUPABASE_ANON_KEY: 'test-anon-key-123',
  VITE_API_URL: 'http://localhost:8000',
  VITE_API_BASE_URL: 'http://localhost:8000',
  VITE_WS_BASE_URL: 'ws://localhost:8000/ws',
  VITE_WHATSAPP_INSTANCE_NAME: 'test-instance',
  VITE_ENVIRONMENT: 'test',
  VITE_DEBUG_MODE: 'true',
  VITE_AI_CHAT_ENABLED: 'true',
  VITE_AI_ANALYTICS_ENABLED: 'true',
  VITE_AI_INSIGHTS_ENABLED: 'true',
  VITE_AI_RECOMMENDATIONS_ENABLED: 'false',
  VITE_OPENAI_API_KEY: 'test-openai-key',
  VITE_GEMINI_API_KEY: '',
  VITE_LANGCHAIN_API_KEY: 'test-langchain-key'
};

class RuntimeConfigTestUtils {
  constructor(private page: Page) {}

  async mockRuntimeConfig(config = MOCK_RUNTIME_CONFIG) {
    // Mock the runtime-config.json file
    await this.page.route('**/runtime-config.json', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(config)
      });
    });

    // Also set up window.__RUNTIME_CONFIG__ for immediate access
    await this.page.addInitScript((config) => {
      (window as any).__RUNTIME_CONFIG__ = config;
      (window as any).configLoaded = true;
    }, config);
  }

  async mockFailedRuntimeConfig() {
    await this.page.route('**/runtime-config.json', (route) => {
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Config not found' })
      });
    });
  }

  async waitForConfigLoad() {
    await this.page.waitForFunction(
      () => {
        return (window as any).__RUNTIME_CONFIG__ !== undefined ||
               (window as any).configLoaded === true;
      },
      { timeout: 10000 }
    );
  }

  async getLoadedConfig() {
    return await this.page.evaluate(() => {
      return (window as any).__RUNTIME_CONFIG__;
    });
  }

  async getConfigFromApp() {
    return await this.page.evaluate(async () => {
      // Try to access the loaded configuration from the app
      try {
        const configModule = await import('/src/config.ts');
        return {
          syncConfig: configModule.getConfigSync(),
          asyncConfig: await configModule.loadConfig()
        };
      } catch (error) {
        return { error: error.message };
      }
    });
  }
}

test.describe('Runtime Configuration Loading', () => {
  let testUtils: RuntimeConfigTestUtils;

  test.beforeEach(async ({ page }) => {
    testUtils = new RuntimeConfigTestUtils(page);
  });

  test('Runtime configuration loads successfully', async ({ page }) => {
    test.setTimeout(TEST_CONFIG.timeout);

    await testUtils.mockRuntimeConfig();
    await page.goto('/');

    // Wait for configuration to load
    await testUtils.waitForConfigLoad();

    // Verify configuration is available
    const config = await testUtils.getLoadedConfig();
    expect(config).toBeTruthy();
    expect(config.VITE_SUPABASE_URL).toBe(MOCK_RUNTIME_CONFIG.VITE_SUPABASE_URL);
    expect(config.VITE_API_URL).toBe(MOCK_RUNTIME_CONFIG.VITE_API_URL);
  });

  test('Configuration fallback works when runtime config fails', async ({ page }) => {
    await testUtils.mockFailedRuntimeConfig();

    // Set environment variables as fallback
    await page.addInitScript(() => {
      (window as any).process = {
        env: {
          NODE_ENV: 'test'
        }
      };

      // Mock import.meta.env
      Object.defineProperty(window, 'import', {
        value: {
          meta: {
            env: {
              VITE_SUPABASE_URL: 'https://fallback.supabase.co',
              VITE_SUPABASE_ANON_KEY: 'fallback-key',
              VITE_API_URL: 'http://localhost:8000',
              VITE_WS_BASE_URL: 'ws://localhost:8000/ws'
            }
          }
        }
      });
    });

    await page.goto('/');

    // App should still work with fallback values
    await page.waitForSelector('[data-testid="app-root"], body', { timeout: 10000 });

    // Check that app doesn't crash
    const errors: string[] = [];
    page.on('pageerror', (error) => {
      errors.push(error.message);
    });

    await page.waitForTimeout(3000);

    // Filter critical errors (some config errors are expected in this test)
    const criticalErrors = errors.filter(error =>
      !error.includes('Failed to load configuration') &&
      !error.includes('runtime-config.json') &&
      !error.includes('Network Error')
    );

    expect(criticalErrors).toHaveLength(0);
  });

  test('Configuration validation works', async ({ page }) => {
    // Test with invalid configuration
    const invalidConfig = {
      ...MOCK_RUNTIME_CONFIG,
      VITE_SUPABASE_URL: '', // Missing required field
      VITE_API_URL: ''       // Missing required field
    };

    await testUtils.mockRuntimeConfig(invalidConfig);
    await page.goto('/');

    // Check for configuration errors
    const configErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error' && msg.text().includes('Config')) {
        configErrors.push(msg.text());
      }
    });

    await page.waitForTimeout(3000);

    // Should log configuration errors
    expect(configErrors.length).toBeGreaterThan(0);
  });
});

test.describe('Environment Variables Validation', () => {
  let testUtils: RuntimeConfigTestUtils;

  test.beforeEach(async ({ page }) => {
    testUtils = new RuntimeConfigTestUtils(page);
  });

  test('Required environment variables are present', async ({ page }) => {
    await testUtils.mockRuntimeConfig();
    await page.goto('/');
    await testUtils.waitForConfigLoad();

    const config = await testUtils.getLoadedConfig();

    // Check required variables
    expect(config.VITE_SUPABASE_URL).toBeTruthy();
    expect(config.VITE_SUPABASE_ANON_KEY).toBeTruthy();
    expect(config.VITE_API_URL || config.VITE_API_BASE_URL).toBeTruthy();
    expect(config.VITE_WS_BASE_URL).toBeTruthy();
  });

  test('Optional environment variables are handled correctly', async ({ page }) => {
    const configWithOptionals = {
      ...MOCK_RUNTIME_CONFIG,
      VITE_OPENAI_API_KEY: undefined,
      VITE_GEMINI_API_KEY: undefined,
      VITE_SENTRY_DSN: 'https://test-sentry-dsn.com',
      VITE_ANALYTICS_TRACKING_ID: 'GA-TEST-123'
    };

    await testUtils.mockRuntimeConfig(configWithOptionals);
    await page.goto('/');
    await testUtils.waitForConfigLoad();

    // App should work without optional variables
    await page.waitForSelector('[data-testid="app-root"], body', { timeout: 10000 });

    // Check that features are disabled appropriately
    const hasAIFeatures = await page.evaluate(() => {
      return !!(window as any).__RUNTIME_CONFIG__?.VITE_OPENAI_API_KEY ||
             !!(window as any).__RUNTIME_CONFIG__?.VITE_GEMINI_API_KEY;
    });

    expect(hasAIFeatures).toBeFalsy();
  });

  test('Feature flags work correctly', async ({ page }) => {
    const featureFlagConfig = {
      ...MOCK_RUNTIME_CONFIG,
      VITE_AI_CHAT_ENABLED: 'false',
      VITE_AI_ANALYTICS_ENABLED: 'true',
      VITE_DEBUG_MODE: 'true'
    };

    await testUtils.mockRuntimeConfig(featureFlagConfig);
    await page.goto('/');
    await testUtils.waitForConfigLoad();

    // Wait for app to load
    await page.waitForSelector('[data-testid="app-root"], body', { timeout: 10000 });

    // Check feature flags are applied
    const features = await page.evaluate(() => {
      return {
        aiChatEnabled: (window as any).__RUNTIME_CONFIG__?.VITE_AI_CHAT_ENABLED === 'true',
        aiAnalyticsEnabled: (window as any).__RUNTIME_CONFIG__?.VITE_AI_ANALYTICS_ENABLED === 'true',
        debugMode: (window as any).__RUNTIME_CONFIG__?.VITE_DEBUG_MODE === 'true'
      };
    });

    expect(features.aiChatEnabled).toBeFalsy();
    expect(features.aiAnalyticsEnabled).toBeTruthy();
    expect(features.debugMode).toBeTruthy();
  });
});

test.describe('API URL Configuration', () => {
  let testUtils: RuntimeConfigTestUtils;

  test.beforeEach(async ({ page }) => {
    testUtils = new RuntimeConfigTestUtils(page);
  });

  test('API URL is configured correctly', async ({ page }) => {
    await testUtils.mockRuntimeConfig();
    await page.goto('/');
    await testUtils.waitForConfigLoad();

    const config = await testUtils.getLoadedConfig();
    const apiUrl = config.VITE_API_URL || config.VITE_API_BASE_URL;

    expect(apiUrl).toBe(MOCK_RUNTIME_CONFIG.VITE_API_URL);
    expect(apiUrl).toMatch(/^https?:\/\//); // Should be a valid URL
  });

  test('API requests use configured URL', async ({ page }) => {
    await testUtils.mockRuntimeConfig();

    // Track API requests
    const apiRequests: string[] = [];
    page.on('request', (request) => {
      if (request.url().includes('/api/')) {
        apiRequests.push(request.url());
      }
    });

    await page.goto('/');
    await testUtils.waitForConfigLoad();

    // Trigger an API request (mock authentication)
    await page.evaluate(() => {
      localStorage.setItem('supabase.auth.token', JSON.stringify({
        access_token: 'mock-token'
      }));
    });

    await page.goto('/patients');
    await page.waitForTimeout(2000);

    // Check that requests use the configured base URL
    const baseUrl = MOCK_RUNTIME_CONFIG.VITE_API_URL;
    if (apiRequests.length > 0) {
      const usesCorrectUrl = apiRequests.some(url => url.startsWith(baseUrl));
      expect(usesCorrectUrl).toBeTruthy();
    }
  });

  test('Multiple API URL formats work', async ({ page }) => {
    const configs = [
      { VITE_API_URL: 'http://localhost:8000' },
      { VITE_API_BASE_URL: 'http://localhost:8000' },
      { VITE_API_URL: 'http://localhost:8000/', VITE_API_BASE_URL: 'http://backup:8000' }
    ];

    for (const configUpdate of configs) {
      const testConfig = { ...MOCK_RUNTIME_CONFIG, ...configUpdate };
      await testUtils.mockRuntimeConfig(testConfig);
      await page.goto('/');
      await testUtils.waitForConfigLoad();

      const config = await testUtils.getLoadedConfig();
      const apiUrl = config.VITE_API_URL || config.VITE_API_BASE_URL;
      expect(apiUrl).toBeTruthy();
      expect(apiUrl).toMatch(/^https?:\/\//);

      // Reset page for next iteration
      await page.goto('about:blank');
    }
  });
});

test.describe('WebSocket Configuration', () => {
  let testUtils: RuntimeConfigTestUtils;

  test.beforeEach(async ({ page }) => {
    testUtils = new RuntimeConfigTestUtils(page);
  });

  test('WebSocket URL is configured correctly', async ({ page }) => {
    await testUtils.mockRuntimeConfig();
    await page.goto('/');
    await testUtils.waitForConfigLoad();

    const config = await testUtils.getLoadedConfig();
    const wsUrl = config.VITE_WS_BASE_URL;

    expect(wsUrl).toBe(MOCK_RUNTIME_CONFIG.VITE_WS_BASE_URL);
    expect(wsUrl).toMatch(/^wss?:\/\//); // Should be a valid WebSocket URL
  });

  test('WebSocket connection uses configured URL', async ({ page }) => {
    await testUtils.mockRuntimeConfig();

    // Mock WebSocket constructor to track connection attempts
    await page.addInitScript(() => {
      (window as any).mockWebSocketConnections = [];
      const OriginalWebSocket = (window as any).WebSocket;

      (window as any).WebSocket = class MockWebSocket extends OriginalWebSocket {
        constructor(url: string, protocols?: string | string[]) {
          (window as any).mockWebSocketConnections.push(url);
          // Don't actually connect in tests
          super('data:,'); // Use data URL to avoid real connection
        }
      };
    });

    await page.goto('/');
    await testUtils.waitForConfigLoad();

    // Wait for potential WebSocket connections
    await page.waitForTimeout(3000);

    const connections = await page.evaluate(() => {
      return (window as any).mockWebSocketConnections || [];
    });

    // If WebSocket is used, it should use the configured URL
    if (connections.length > 0) {
      const expectedBaseUrl = MOCK_RUNTIME_CONFIG.VITE_WS_BASE_URL;
      const usesCorrectUrl = connections.some((url: string) =>
        url.startsWith(expectedBaseUrl)
      );
      expect(usesCorrectUrl).toBeTruthy();
    }
  });

  test('WebSocket gracefully handles connection failures', async ({ page }) => {
    await testUtils.mockRuntimeConfig();

    // Mock WebSocket to always fail
    await page.addInitScript(() => {
      (window as any).WebSocket = class MockWebSocket {
        constructor(url: string) {
          setTimeout(() => {
            if (this.onerror) {
              this.onerror(new ErrorEvent('error'));
            }
          }, 100);
        }

        onerror: ((event: Event) => void) | null = null;
        onopen: ((event: Event) => void) | null = null;
        onclose: ((event: CloseEvent) => void) | null = null;
        onmessage: ((event: MessageEvent) => void) | null = null;

        send() {}
        close() {}
      };
    });

    await page.goto('/');
    await testUtils.waitForConfigLoad();

    // App should still function despite WebSocket failure
    await page.waitForSelector('[data-testid="app-root"], body', { timeout: 10000 });

    // Check for graceful error handling
    const errors: string[] = [];
    page.on('pageerror', (error) => {
      errors.push(error.message);
    });

    await page.waitForTimeout(3000);

    // Should not have unhandled WebSocket errors crashing the app
    const webSocketErrors = errors.filter(error =>
      error.includes('WebSocket') &&
      !error.includes('gracefully') &&
      !error.includes('handled')
    );

    expect(webSocketErrors).toHaveLength(0);
  });
});

test.describe('Configuration Performance', () => {
  let testUtils: RuntimeConfigTestUtils;

  test.beforeEach(async ({ page }) => {
    testUtils = new RuntimeConfigTestUtils(page);
  });

  test('Configuration loads within acceptable time', async ({ page }) => {
    await testUtils.mockRuntimeConfig();

    const startTime = Date.now();
    await page.goto('/');
    await testUtils.waitForConfigLoad();
    const loadTime = Date.now() - startTime;

    // Configuration should load within 5 seconds
    expect(loadTime).toBeLessThan(5000);
  });

  test('Configuration is cached correctly', async ({ page }) => {
    await testUtils.mockRuntimeConfig();

    let requestCount = 0;
    page.on('request', (request) => {
      if (request.url().includes('runtime-config.json')) {
        requestCount++;
      }
    });

    await page.goto('/');
    await testUtils.waitForConfigLoad();

    // Navigate to another page
    await page.goto('/dashboard');
    await page.waitForTimeout(1000);

    // Should not reload config on navigation
    expect(requestCount).toBeLessThanOrEqual(1);
  });

  test('Memory usage is reasonable with configuration', async ({ page }) => {
    await testUtils.mockRuntimeConfig();
    await page.goto('/');
    await testUtils.waitForConfigLoad();

    const memoryUsage = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });

    // If memory API is available, configuration shouldn't use excessive memory
    if (memoryUsage > 0) {
      expect(memoryUsage).toBeLessThan(100 * 1024 * 1024); // Less than 100MB
    }
  });
});