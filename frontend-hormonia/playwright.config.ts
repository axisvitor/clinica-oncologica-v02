import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Configuration for Frontend-v2 E2E Tests
 *
 * This configuration sets up Playwright for testing the Frontend-v2 application
 * with proper environment handling, API mocking, and comprehensive test coverage.
 */

// Test environment configuration
const isCI = Boolean(process.env['CI']);
const TEST_ENV = {
  // Base URL for the application (Railway deployment or local)
  baseURL: process.env['PLAYWRIGHT_TEST_BASE_URL'] ||
           process.env['BASE_URL'] ||
           'http://localhost:4173',

  // API base URL for backend services
  apiURL: process.env['VITE_API_URL'] ||
          process.env['API_URL'] ||
          'http://localhost:8000',

  // Test database configuration
  testDatabaseURL: process.env['TEST_DATABASE_URL'],

  // Authentication configuration for tests
  testAuthEmail: process.env['TEST_AUTH_EMAIL'] || 'test@example.com',
  testAuthPassword: process.env['TEST_AUTH_PASSWORD'] || 'testpassword123',

  // Feature flags for testing
  enableAIFeatures: process.env['VITE_AI_CHAT_ENABLED'] !== 'false',
  enableWebSocketTests: process.env['VITE_WS_BASE_URL'] !== undefined,
};

export default defineConfig({
  // Test directory configuration
  testDir: './tests/e2e',

  // Global test configuration
  timeout: 30 * 1000, // 30 seconds per test
  expect: {
    timeout: 10 * 1000, // 10 seconds for assertions
  },

  // Test execution configuration
  fullyParallel: true, // Run tests in parallel
  forbidOnly: isCI, // Forbid test.only in CI
  retries: isCI ? 2 : 0, // Retry failed tests in CI
  ...(isCI ? { workers: 2 } : {}), // Limit workers in CI

  // Test reporting configuration
  reporter: [
    ['html', {
      outputFolder: 'test-results/e2e-report',
      open: 'never'
    }],
    ['json', {
      outputFile: 'test-results/e2e-results.json'
    }],
    ['junit', {
      outputFile: 'test-results/e2e-junit.xml'
    }],
    // Add list reporter for console output
    ['list']
  ],

  // Output directory for test artifacts
  outputDir: 'test-results/e2e-artifacts',

  // Global test configuration
  use: {
    // Base URL for all tests
    baseURL: TEST_ENV.baseURL,

    // Browser configuration
    headless: isCI ? true : false,
    viewport: { width: 1280, height: 720 },

    // Action timeouts
    actionTimeout: 10 * 1000,
    navigationTimeout: 15 * 1000,

    // Screenshot and video configuration
    screenshot: isCI ? 'only-on-failure' : 'off',
    video: isCI ? 'retain-on-failure' : 'off',
    trace: isCI ? 'retain-on-failure' : 'off',

    // Ignore HTTPS errors in development
    ignoreHTTPSErrors: !isCI,

    // Accept downloads
    acceptDownloads: true,

    // Extra HTTP headers
    extraHTTPHeaders: {
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'gzip, deflate',
    },

    // Geolocation (if needed for tests)
    geolocation: { longitude: -46.6333, latitude: -23.5505 }, // São Paulo
    permissions: ['geolocation'],

    // Color scheme
    colorScheme: 'light',

    // Locale
    locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo',
  },

  // Test project configurations for different environments
  projects: [
    // Setup project for authentication and database
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },

    // Desktop Chrome tests
    {
      name: 'Desktop Chrome',
      use: {
        ...devices['Desktop Chrome'],
        // Override baseURL for specific tests if needed
        baseURL: TEST_ENV.baseURL,
        // Add custom context options
        permissions: ['notifications', 'geolocation'] as const
      },
      dependencies: ['setup'],
      testIgnore: ['**/mobile-only/**'],
    },

    // Desktop Firefox tests
    {
      name: 'Desktop Firefox',
      use: {
        ...devices['Desktop Firefox'],
        baseURL: TEST_ENV.baseURL,
      },
      dependencies: ['setup'],
      testIgnore: ['**/mobile-only/**', '**/chrome-only/**'],
    },

    // Desktop Safari tests (if on macOS)
    ...(process.platform === 'darwin' ? [{
      name: 'Desktop Safari',
      use: {
        ...devices['Desktop Safari'],
        baseURL: TEST_ENV.baseURL,
      },
      dependencies: ['setup'],
      testIgnore: ['**/mobile-only/**', '**/chrome-only/**'],
    }] : []),

    // Mobile Chrome tests
    {
      name: 'Mobile Chrome',
      use: {
        ...devices['Pixel 5'],
        baseURL: TEST_ENV.baseURL,
      },
      dependencies: ['setup'],
      testMatch: ['**/smoke.spec.ts', '**/mobile-*.spec.ts'],
    },

    // Mobile Safari tests
    {
      name: 'Mobile Safari',
      use: {
        ...devices['iPhone 12'],
        baseURL: TEST_ENV.baseURL,
      },
      dependencies: ['setup'],
      testMatch: ['**/smoke.spec.ts', '**/mobile-*.spec.ts'],
    },

    // High DPI / Retina display tests
    {
      name: 'High DPI',
      use: {
        ...devices['Desktop Chrome HiDPI'],
        baseURL: TEST_ENV.baseURL,
      },
      dependencies: ['setup'],
      testMatch: ['**/visual-*.spec.ts', '**/responsive-*.spec.ts'],
    },

    // API testing project
    {
      name: 'API Tests',
      use: {
        baseURL: TEST_ENV.apiURL,
        extraHTTPHeaders: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        }
      },
      testMatch: ['**/api-*.spec.ts'],
    },

    // Performance testing project
    {
      name: 'Performance Tests',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: TEST_ENV.baseURL,
        // Disable screenshots/videos for performance tests
        screenshot: 'off',
        video: 'off',
        trace: 'off',
      },
      testMatch: ['**/performance-*.spec.ts'],
      timeout: 60 * 1000, // Longer timeout for performance tests
    },

    // Accessibility testing project
    {
      name: 'Accessibility Tests',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: TEST_ENV.baseURL,
      },
      testMatch: ['**/accessibility-*.spec.ts', '**/a11y-*.spec.ts'],
      dependencies: ['setup'],
    },
  ],

  // Web server configuration for local development
  ...(isCI ? {} : {
    webServer: {
      command: process.env['PLAYWRIGHT_SKIP_BUILD'] ? 'npm run preview' : 'npm run build && npm run preview',
      url: TEST_ENV.baseURL,
      reuseExistingServer: !isCI,
      timeout: 120 * 1000, // 2 minutes to start the server
      env: {
        NODE_ENV: 'test',
        VITE_ENVIRONMENT: 'test',
        // Pass through test environment variables
        VITE_SUPABASE_URL: process.env['VITE_SUPABASE_URL'] || 'https://test.supabase.co',
        VITE_SUPABASE_ANON_KEY: process.env['VITE_SUPABASE_ANON_KEY'] || 'test-anon-key',
        VITE_API_URL: TEST_ENV.apiURL,
        VITE_WS_BASE_URL: process.env['VITE_WS_BASE_URL'] || `ws://localhost:8000/ws`,
        VITE_DEBUG_MODE: 'true',
        // AI feature flags for testing
        VITE_AI_CHAT_ENABLED: 'true',
        VITE_AI_ANALYTICS_ENABLED: 'true',
        VITE_AI_INSIGHTS_ENABLED: 'true',
        VITE_AI_RECOMMENDATIONS_ENABLED: 'false',
      },
    },
  }),

  // Global test setup and teardown
  globalSetup: './tests/e2e/global-setup.ts',
  globalTeardown: './tests/e2e/global-teardown.ts',

  // Test metadata and annotations
  metadata: {
    'test-environment': process.env['NODE_ENV'] || 'test',
    'base-url': TEST_ENV.baseURL,
    'api-url': TEST_ENV.apiURL,
    'ai-features-enabled': TEST_ENV.enableAIFeatures.toString(),
    'websocket-enabled': TEST_ENV.enableWebSocketTests.toString(),
  },
} as any);
