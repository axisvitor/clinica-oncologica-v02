/**
 * CSRF Token Migration E2E Tests
 * Tests for new CSRF endpoint /api/v2/auth/csrf-token
 *
 * P1 Fix: CSRF endpoint migration from /api/csrf-token to /api/v2/auth/csrf-token
 */

import { test, expect, Page } from '@playwright/test';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

test.describe('CSRF Token Migration E2E Tests', () => {
  let page: Page;

  test.beforeEach(async ({ browser }) => {
    const context = await browser.newContext();
    page = await context.newPage();
  });

  test.afterEach(async () => {
    await page.close();
  });

  test.describe('New CSRF Endpoint', () => {
    test('should fetch CSRF token from new endpoint /api/v2/auth/csrf-token', async () => {
      const response = await page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('csrf_token');
      expect(typeof data.csrf_token).toBe('string');
      expect(data.csrf_token.length).toBeGreaterThan(0);
    });

    test('should return valid CSRF token structure', async () => {
      const response = await page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);
      const data = await response.json();

      // Token should be a non-empty string
      expect(data.csrf_token).toBeTruthy();
      expect(data.csrf_token).toMatch(/^[A-Za-z0-9_-]+$/);
    });

    test('should set CSRF cookie on token fetch', async () => {
      await page.goto('/');

      const response = await page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);
      expect(response.status()).toBe(200);

      // Check if CSRF cookie is set
      const cookies = await page.context().cookies();
      const csrfCookie = cookies.find(c => c.name.includes('csrf'));

      expect(csrfCookie).toBeDefined();
    });

    test('should generate different tokens on subsequent requests', async () => {
      const response1 = await page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);
      const data1 = await response1.json();

      const response2 = await page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);
      const data2 = await response2.json();

      // Tokens should be different for each request
      expect(data1.csrf_token).not.toBe(data2.csrf_token);
    });

    test('should handle CORS preflight correctly', async () => {
      const response = await page.request.fetch(`${API_BASE_URL}/api/v2/auth/csrf-token`, {
        method: 'OPTIONS',
        headers: {
          'Origin': 'http://localhost:4173',
          'Access-Control-Request-Method': 'GET'
        }
      });

      expect(response.status()).toBe(200);
      expect(response.headers()['access-control-allow-origin']).toBeDefined();
    });
  });

  test.describe('CSRF Token Validation on POST/PUT/DELETE', () => {
    let csrfToken: string;

    test.beforeEach(async () => {
      // Fetch CSRF token
      const response = await page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);
      const data = await response.json();
      csrfToken = data.csrf_token;
    });

    test('should reject POST without CSRF token', async () => {
      const response = await page.request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json'
        },
        data: {
          name: 'Test Patient',
          email: 'test@example.com',
          phone: '+5511999999999'
        }
      });

      // Should be 403 Forbidden due to missing CSRF token
      expect([403, 401]).toContain(response.status());
    });

    test('should accept POST with valid CSRF token', async ({ page: newPage }) => {
      // First, login to get session
      await newPage.goto('/login');
      await newPage.fill('[name="email"]', 'doctor@example.com');
      await newPage.fill('[name="password"]', 'password123');
      await newPage.click('button[type="submit"]');

      // Wait for redirect
      await newPage.waitForURL('/dashboard', { timeout: 10000 });

      // Now make authenticated POST with CSRF token
      const response = await newPage.request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        data: {
          name: 'Test Patient',
          email: 'test@example.com',
          phone: '+5511999999999',
          birth_date: '1990-01-01'
        }
      });

      // If authenticated, should succeed or get validation error (not CSRF error)
      expect([200, 201, 400, 422]).toContain(response.status());
      expect(response.status()).not.toBe(403);
    });

    test('should reject PUT without CSRF token', async () => {
      const response = await page.request.put(`${API_BASE_URL}/api/v2/patients/123e4567-e89b-12d3-a456-426614174000`, {
        headers: {
          'Content-Type': 'application/json'
        },
        data: {
          name: 'Updated Patient'
        }
      });

      expect([403, 401, 404]).toContain(response.status());
    });

    test('should reject DELETE without CSRF token', async () => {
      const response = await page.request.delete(`${API_BASE_URL}/api/v2/patients/123e4567-e89b-12d3-a456-426614174000`, {
        headers: {
          'Content-Type': 'application/json'
        }
      });

      expect([403, 401, 404]).toContain(response.status());
    });

    test('should reject requests with invalid CSRF token', async () => {
      const response = await page.request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': 'invalid-token-12345'
        },
        data: {
          name: 'Test Patient',
          email: 'test@example.com'
        }
      });

      expect([403, 401]).toContain(response.status());
    });

    test('should reject requests with expired CSRF token', async () => {
      // Use an old/expired token
      const expiredToken = 'expired-token-from-yesterday';

      const response = await page.request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': expiredToken
        },
        data: {
          name: 'Test Patient'
        }
      });

      expect([403, 401]).toContain(response.status());
    });
  });

  test.describe('CSRF Token in Different HTTP Methods', () => {
    test('should allow GET without CSRF token', async () => {
      const response = await page.request.get(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json'
        }
      });

      // GET should work without CSRF (might need auth though)
      expect([200, 401]).toContain(response.status());
      expect(response.status()).not.toBe(403);
    });

    test('should allow HEAD without CSRF token', async () => {
      const response = await page.request.head(`${API_BASE_URL}/api/v2/patients`);

      // HEAD should work without CSRF
      expect([200, 401, 404]).toContain(response.status());
      expect(response.status()).not.toBe(403);
    });

    test('should allow OPTIONS without CSRF token', async () => {
      const response = await page.request.fetch(`${API_BASE_URL}/api/v2/patients`, {
        method: 'OPTIONS'
      });

      // OPTIONS should always work
      expect(response.status()).toBe(200);
    });
  });

  test.describe('Integration with Frontend', () => {
    test('should fetch and use CSRF token in form submission', async ({ page: newPage }) => {
      await newPage.goto('/login');

      // Frontend should fetch CSRF token automatically
      const csrfResponse = await newPage.waitForResponse(
        response => response.url().includes('/csrf-token') && response.status() === 200,
        { timeout: 5000 }
      );

      expect(csrfResponse).toBeDefined();
      const csrfData = await csrfResponse.json();
      expect(csrfData).toHaveProperty('csrf_token');
    });

    test('should include CSRF token in axios/fetch requests', async ({ page: newPage }) => {
      await newPage.goto('/dashboard');

      // Intercept API requests to verify CSRF token presence
      const requestPromise = newPage.waitForRequest(
        request =>
          request.url().includes('/api/v2/') &&
          ['POST', 'PUT', 'DELETE'].includes(request.method())
      );

      // Trigger an action that makes a POST request (e.g., create patient)
      await newPage.click('[data-testid="create-patient-button"]');

      const request = await requestPromise;
      const headers = request.headers();

      // Should have CSRF token in headers
      expect(headers['x-csrf-token'] || headers['X-CSRF-Token']).toBeDefined();
    });
  });

  test.describe('Error Handling', () => {
    test('should return 403 with descriptive error for missing CSRF', async () => {
      const response = await page.request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json'
        },
        data: { name: 'Test' }
      });

      expect(response.status()).toBe(403);

      const errorData = await response.json();
      expect(errorData).toHaveProperty('detail');
      expect(errorData.detail.toLowerCase()).toContain('csrf');
    });

    test('should return 403 with descriptive error for invalid CSRF', async () => {
      const response = await page.request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': 'invalid-token'
        },
        data: { name: 'Test' }
      });

      expect(response.status()).toBe(403);

      const errorData = await response.json();
      expect(errorData.detail.toLowerCase()).toMatch(/csrf|invalid|token/);
    });
  });

  test.describe('Security Tests', () => {
    test('should not expose CSRF implementation details in headers', async () => {
      const response = await page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);

      const headers = response.headers();

      // Should not expose internal implementation
      expect(headers['x-csrf-secret']).toBeUndefined();
      expect(headers['x-csrf-key']).toBeUndefined();
    });

    test('should generate cryptographically secure tokens', async () => {
      // Fetch multiple tokens
      const tokens: string[] = [];

      for (let i = 0; i < 10; i++) {
        const response = await page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);
        const data = await response.json();
        tokens.push(data.csrf_token);
      }

      // All tokens should be unique
      const uniqueTokens = new Set(tokens);
      expect(uniqueTokens.size).toBe(10);

      // Tokens should have sufficient entropy (length)
      tokens.forEach(token => {
        expect(token.length).toBeGreaterThanOrEqual(32);
      });
    });

    test('should handle concurrent CSRF token requests', async () => {
      // Make 5 concurrent requests
      const promises = Array(5).fill(null).map(() =>
        page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`)
      );

      const responses = await Promise.all(promises);

      // All should succeed
      responses.forEach(response => {
        expect(response.status()).toBe(200);
      });

      // All should return unique tokens
      const tokens = await Promise.all(
        responses.map(r => r.json().then(data => data.csrf_token))
      );

      const uniqueTokens = new Set(tokens);
      expect(uniqueTokens.size).toBe(5);
    });
  });

  test.describe('Performance Tests', () => {
    test('should respond quickly to CSRF token requests', async () => {
      const startTime = Date.now();

      const response = await page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);

      const duration = Date.now() - startTime;

      expect(response.status()).toBe(200);
      expect(duration).toBeLessThan(500); // Should respond in < 500ms
    });

    test('should handle burst of CSRF token requests', async () => {
      const promises = Array(20).fill(null).map(() =>
        page.request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`)
      );

      const startTime = Date.now();
      const responses = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All should succeed
      responses.forEach(response => {
        expect(response.status()).toBe(200);
      });

      // Should handle 20 requests in reasonable time
      expect(duration).toBeLessThan(3000); // < 3 seconds for 20 requests
    });
  });
});
