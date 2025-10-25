import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright Configuration for Local Development Testing
 * Use this config when dev server is already running on localhost:5175
 */
const isCI = Boolean(process.env['CI'])

export default defineConfig({
  testDir: './tests/e2e',
  outputDir: './test-results/e2e-artifacts',

  // Run tests in files in parallel
  fullyParallel: true,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: isCI,

  // Retry on CI only
  retries: isCI ? 2 : 0,

  // Opt out of parallel tests on CI
  workers: isCI ? 1 : 4,

  // Reporter to use
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
    ['json', { outputFile: 'test-results/results.json' }]
  ],

  // Shared settings for all the projects below
  use: {
    // Base URL for tests (dev server already running)
    baseURL: 'http://localhost:5175',

    // Collect trace when retrying the failed test
    trace: 'on-first-retry',

    // Take screenshot on failure
    screenshot: 'only-on-failure',

    // Record video only when retrying a test
    video: 'retain-on-failure',

    // Maximum time each action can take
    actionTimeout: 10000,

    // Navigation timeout
    navigationTimeout: 30000,
  },

  // Configure projects for major browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // NO webServer - use the already running dev server
  // Dev server should be running on http://localhost:5175
});
