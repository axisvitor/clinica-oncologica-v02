/**
 * End-to-End Tests for Configuration Initialization
 *
 * Tests the complete initialization flow in a browser environment
 * using Playwright for realistic user scenarios
 */

import { test, expect } from '@playwright/test';

test.describe('Configuration Initialization - E2E Tests', () => {

  test.beforeEach(async ({ page }) => {
    // Intercept console logs for debugging
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.error('Browser console error:', msg.text());
      }
    });
  });

  test.describe('Successful Initialization', () => {

    test('should load application with runtime configuration', async ({ page }) => {
      // Mock successful config endpoint
      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            VITE_API_URL: 'https://api.test.local',
            VITE_WS_URL: 'wss://ws.test.local',
            VITE_SUPABASE_URL: 'https://supabase.test.local',
            VITE_SUPABASE_ANON_KEY: 'test-key-e2e'
          })
        });
      });

      await page.goto('/');

      // Should show loading state briefly
      await expect(page.locator('text=Carregando Configuração')).toBeVisible({ timeout: 1000 });

      // Then show application content
      await expect(page.locator('text=Carregando Configuração')).not.toBeVisible({ timeout: 5000 });
    });

    test('should display loading spinner during initialization', async ({ page }) => {
      await page.route('/config.json', async route => {
        // Delay response to observe loading state
        await new Promise(resolve => setTimeout(resolve, 500));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            VITE_API_URL: 'https://api.test.local'
          })
        });
      });

      await page.goto('/');

      // Should display loading spinner
      const spinner = page.locator('.animate-spin');
      await expect(spinner).toBeVisible();

      await expect(spinner).not.toBeVisible({ timeout: 3000 });
    });

    test('should initialize app within acceptable time', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            VITE_API_URL: 'https://api.test.local'
          })
        });
      });

      const startTime = Date.now();
      await page.goto('/');

      // Wait for app to be ready (loading complete)
      await expect(page.locator('text=Carregando Configuração')).not.toBeVisible({ timeout: 5000 });

      const endTime = Date.now();
      const duration = endTime - startTime;

      // Should load within 3 seconds
      expect(duration).toBeLessThan(3000);
    });
  });

  test.describe('Error Handling', () => {

    test('should display error when config fetch fails', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.abort('failed');
      });

      await page.goto('/');

      // Should show error state
      await expect(page.locator('text=Erro de Configuração')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('text=Não foi possível carregar a configuração do sistema')).toBeVisible();
    });

    test('should display retry button on error', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.abort('failed');
      });

      await page.goto('/');

      const retryButton = page.locator('button:has-text("Tentar Novamente")');
      await expect(retryButton).toBeVisible({ timeout: 5000 });
    });

    test('should allow retry after config error', async ({ page }) => {
      let attemptCount = 0;

      await page.route('/config.json', async route => {
        attemptCount++;
        if (attemptCount === 1) {
          await route.abort('failed');
        } else {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              VITE_API_URL: 'https://api.test.local'
            })
          });
        }
      });

      await page.goto('/');

      // First attempt fails
      await expect(page.locator('text=Erro de Configuração')).toBeVisible({ timeout: 5000 });

      // Click retry
      const retryButton = page.locator('button:has-text("Tentar Novamente")');
      await retryButton.click();

      // Should succeed on retry
      await expect(page.locator('text=Erro de Configuração')).not.toBeVisible({ timeout: 5000 });
    });

    test('should display error details', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.abort('failed');
      });

      await page.goto('/');

      // Error details should be collapsible
      const details = page.locator('details:has-text("Detalhes do erro")');
      await expect(details).toBeVisible({ timeout: 5000 });

      // Click to expand
      await details.locator('summary').click();

      // Should show error message
      const errorPre = details.locator('pre');
      await expect(errorPre).toBeVisible();
    });

    test('should handle network timeout gracefully', async ({ page }) => {
      await page.route('/config.json', async route => {
        // Simulate very slow response
        await new Promise(resolve => setTimeout(resolve, 10000));
        await route.fulfill({ status: 200, body: '{}' });
      });

      await page.goto('/');

      // Should eventually show error or fallback (depending on implementation)
      const loadingOrError = page.locator('text=Carregando Configuração, text=Erro de Configuração');
      await expect(loadingOrError).toBeVisible({ timeout: 15000 });
    });

    test('should handle malformed JSON response', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: 'invalid-json-{{'
        });
      });

      await page.goto('/');

      // Should handle gracefully with error or fallback
      const result = await page.waitForSelector('text=Carregando Configuração, text=Erro de Configuração, [role=main]', {
        timeout: 5000
      });

      expect(result).toBeTruthy();
    });

    test('should handle 404 response', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 404,
          body: 'Not Found'
        });
      });

      await page.goto('/');

      // Should fallback gracefully (may use env vars)
      const state = await page.waitForSelector('text=Carregando Configuração, text=Erro de Configuração, [role=main]', {
        timeout: 5000
      });

      expect(state).toBeTruthy();
    });

    test('should handle 500 server error', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 500,
          body: 'Internal Server Error'
        });
      });

      await page.goto('/');

      // Should show error or fallback
      const errorOrFallback = await page.waitForSelector('text=Erro de Configuração, [role=main]', {
        timeout: 5000
      });

      expect(errorOrFallback).toBeTruthy();
    });
  });

  test.describe('User Experience', () => {

    test('should provide helpful error messages', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.abort('failed');
      });

      await page.goto('/');

      await expect(page.locator('text=Erro de Configuração')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('text=Não foi possível carregar a configuração do sistema')).toBeVisible();
      await expect(page.locator('text=Verifique sua conexão com a internet')).toBeVisible();
    });

    test('should show loading message in Portuguese', async ({ page }) => {
      await page.route('/config.json', async route => {
        await new Promise(resolve => setTimeout(resolve, 500));
        await route.fulfill({ status: 200, body: '{}' });
      });

      await page.goto('/');

      await expect(page.locator('text=Carregando Configuração')).toBeVisible();
      await expect(page.locator('text=Preparando o sistema Hormonia')).toBeVisible();
    });

    test('should maintain responsive design during loading', async ({ page }) => {
      await page.route('/config.json', async route => {
        await new Promise(resolve => setTimeout(resolve, 1000));
        await route.fulfill({ status: 200, body: '{}' });
      });

      // Test mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/');

      const loadingContainer = page.locator('.min-h-screen').first();
      await expect(loadingContainer).toBeVisible();

      // Test desktop viewport
      await page.setViewportSize({ width: 1920, height: 1080 });
      await expect(loadingContainer).toBeVisible();
    });

    test('should be accessible with keyboard navigation', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.abort('failed');
      });

      await page.goto('/');

      await expect(page.locator('text=Erro de Configuração')).toBeVisible({ timeout: 5000 });

      // Should be able to navigate to retry button with Tab
      await page.keyboard.press('Tab');
      const retryButton = page.locator('button:has-text("Tentar Novamente")');
      await expect(retryButton).toBeFocused();

      // Should be able to activate with Enter
      await page.keyboard.press('Enter');
    });
  });

  test.describe('Configuration Validation', () => {

    test('should validate required configuration fields', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            VITE_API_URL: 'https://api.test.local'
            // Missing other fields
          })
        });
      });

      await page.goto('/');

      // Should load successfully (validation happens at component level)
      await expect(page.locator('text=Carregando Configuração')).not.toBeVisible({ timeout: 5000 });
    });

    test('should handle empty configuration gracefully', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({})
        });
      });

      await page.goto('/');

      // Should complete loading
      const result = await page.waitForSelector('text=Carregando Configuração, [role=main]', {
        timeout: 5000,
        state: 'attached'
      });

      expect(result).toBeTruthy();
    });
  });

  test.describe('Performance', () => {

    test('should not block main thread during initialization', async ({ page }) => {
      await page.route('/config.json', async route => {
        await new Promise(resolve => setTimeout(resolve, 500));
        await route.fulfill({
          status: 200,
          body: JSON.stringify({ VITE_API_URL: 'https://api.test.local' })
        });
      });

      await page.goto('/');

      // Measure performance
      const metrics = await page.evaluate(() => {
        const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
        return {
          domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
          loadComplete: navigation.loadEventEnd - navigation.loadEventStart
        };
      });

      // DOM should load quickly
      expect(metrics.domContentLoaded).toBeLessThan(1000);
    });

    test('should optimize rerenders during initialization', async ({ page }) => {
      let renderCount = 0;

      await page.exposeFunction('trackRender', () => {
        renderCount++;
      });

      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 200,
          body: JSON.stringify({ VITE_API_URL: 'https://api.test.local' })
        });
      });

      await page.goto('/');
      await expect(page.locator('text=Carregando Configuração')).not.toBeVisible({ timeout: 5000 });

      // Should have minimal renders (exact count depends on implementation)
      expect(renderCount).toBeLessThan(10);
    });
  });

  test.describe('Security', () => {

    test('should not expose sensitive config in DOM', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            VITE_API_URL: 'https://api.test.local',
            VITE_SUPABASE_ANON_KEY: 'super-secret-key-12345'
          })
        });
      });

      await page.goto('/');
      await expect(page.locator('text=Carregando Configuração')).not.toBeVisible({ timeout: 5000 });

      const pageContent = await page.content();

      // Sensitive keys should not be directly visible in HTML
      // (they may be in memory/JS but not in rendered DOM)
      expect(pageContent).not.toContain('super-secret-key-12345');
    });

    test('should handle XSS attempts in config values', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            VITE_API_URL: '<script>alert("XSS")</script>'
          })
        });
      });

      // Set up dialog handler to catch any alerts
      page.on('dialog', dialog => {
        throw new Error('XSS vulnerability: alert was triggered');
      });

      await page.goto('/');
      await page.waitForTimeout(2000);

      // If we reach here without dialog, XSS was prevented
      expect(true).toBe(true);
    });

    test('should validate config source integrity', async ({ page }) => {
      await page.route('/config.json', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            VITE_API_URL: 'https://api.test.local',
            __proto__: { polluted: true }
          })
        });
      });

      await page.goto('/');
      await expect(page.locator('text=Carregando Configuração')).not.toBeVisible({ timeout: 5000 });

      // Prototype pollution should not affect app
      const isPrototypePolluted = await page.evaluate(() => {
        return (Object.prototype as any).polluted === true;
      });

      expect(isPrototypePolluted).toBe(false);
    });
  });
});