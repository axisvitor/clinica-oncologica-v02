import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5175';

test.describe('Smoke Tests - Local Development', () => {
  test('Homepage should load successfully', async ({ page }) => {
    await page.goto(BASE_URL);

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Check title
    await expect(page).toHaveTitle(/Neoplasias Litoral|Hormonia/);

    // Take screenshot
    await page.screenshot({ path: 'test-results/homepage.png', fullPage: true });
  });

  test('Should have proper meta tags', async ({ page }) => {
    await page.goto(BASE_URL);

    // Check viewport meta
    const viewport = await page.locator('meta[name="viewport"]').getAttribute('content');
    expect(viewport).toContain('width=device-width');

    // Check charset
    const charset = await page.locator('meta[charset]').getAttribute('charset');
    expect(charset).toBe('UTF-8');
  });

  test('Should load Vite client and React Refresh', async ({ page }) => {
    await page.goto(BASE_URL);

    // Check if Vite client is loaded
    const scripts = await page.locator('script[type="module"]').count();
    expect(scripts).toBeGreaterThan(0);
  });

  test('Should initialize without errors', async ({ page }) => {
    const errors: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    page.on('pageerror', (error) => {
      errors.push(error.message);
    });

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Allow configuration warnings but fail on other errors
    const criticalErrors = errors.filter(err =>
      !err.includes('configuration') &&
      !err.includes('Supabase') &&
      !err.includes('Firebase')
    );

    expect(criticalErrors).toHaveLength(0);
  });

  test('Should have responsive viewport', async ({ page }) => {
    // Desktop
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(BASE_URL);
    await expect(page).toHaveTitle(/Neoplasias Litoral|Hormonia/);

    // Tablet
    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(page).toHaveTitle(/Neoplasias Litoral|Hormonia/);

    // Mobile
    await page.setViewportSize({ width: 375, height: 667 });
    await expect(page).toHaveTitle(/Neoplasias Litoral|Hormonia/);
  });

  test('Should check Firebase configuration', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Check console for Firebase initialization
    const logs: string[] = [];
    page.on('console', (msg) => {
      logs.push(msg.text());
    });

    await page.reload();
    await page.waitForTimeout(2000);

    // Firebase should be configured (keys are in .env.local)
    const hasFirebaseLog = logs.some(log =>
      log.includes('Firebase') || log.includes('firebase')
    );

    console.log('Firebase-related logs found:', hasFirebaseLog);
  });

  test('Should check Supabase configuration', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    const logs: string[] = [];
    page.on('console', (msg) => {
      logs.push(msg.text());
    });

    await page.reload();
    await page.waitForTimeout(2000);

    // Supabase should be configured (keys are in .env.local without quotes)
    const hasSupabaseLog = logs.some(log =>
      log.includes('Supabase') || log.includes('supabase')
    );

    console.log('Supabase-related logs found:', hasSupabaseLog);
  });

  test('Performance: Page load time should be acceptable', async ({ page }) => {
    const startTime = Date.now();

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;

    console.log(`Page load time: ${loadTime}ms`);

    // Should load in less than 5 seconds
    expect(loadTime).toBeLessThan(5000);
  });

  test('Should check network requests', async ({ page }) => {
    const requests: string[] = [];

    page.on('request', (request) => {
      requests.push(request.url());
    });

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    console.log(`Total requests made: ${requests.length}`);

    // Should make some requests (Vite HMR, fonts, etc.)
    expect(requests.length).toBeGreaterThan(0);

    // Check for Vite client
    const hasViteClient = requests.some(url => url.includes('@vite/client'));
    expect(hasViteClient).toBe(true);
  });

  test('Should capture full page screenshot', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Wait a bit for dynamic content
    await page.waitForTimeout(2000);

    await page.screenshot({
      path: 'test-results/full-page-screenshot.png',
      fullPage: true
    });

    console.log('Full page screenshot saved to test-results/full-page-screenshot.png');
  });
});
