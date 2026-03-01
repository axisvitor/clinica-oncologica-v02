import { test, expect, Page } from '@playwright/test';

const MOCK_AUTH_ENABLED = process.env.VITE_USE_MOCK_AUTH === 'true';

const ADMIN_USER = {
  email: 'admin@sistema.com',
  password: 'senha123',
};

const DOCTOR_USER = {
  email: '123456@medico.local',
  password: 'senha123',
};

async function loginAs(page: Page, email: string, password: string) {
  await page.goto('/admin/login');
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.getByRole('button', { name: /entrar/i }).click();
  await page.waitForLoadState('networkidle');
}

test.describe('RBAC admin access', () => {
  test.skip(!MOCK_AUTH_ENABLED, 'Mock auth required for deterministic RBAC roles.');

  test('Doctor cannot access admin users page', async ({ page }) => {
    await loginAs(page, DOCTOR_USER.email, DOCTOR_USER.password);
    await page.goto('/admin/users');

    await expect(page.locator('h1, h2')).toContainText(/insufficient permissions/i);
    await expect(page).toHaveURL(/\/admin\/users/);
  });

  test('Admin can access admin users page', async ({ page }) => {
    await loginAs(page, ADMIN_USER.email, ADMIN_USER.password);
    await page.goto('/admin/users');

    await expect(page.locator('h1')).toContainText(/user management/i);
    await expect(page).toHaveURL(/\/admin\/users/);
  });
});

test.describe('Session ID propagation', () => {
  test('Session ID via cookie works', async ({ page, context }) => {
    const sessionId = 'test-session-cookie';

    await page.goto('/');
    await context.addCookies([
      {
        name: 'session_id',
        value: sessionId,
        url: page.url(),
        httpOnly: true,
      },
    ]);

    let cookieHeader = '';
    await page.route('**/api/v2/health', async (route) => {
      cookieHeader = route.request().headers()['cookie'] || '';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'ok' }),
      });
    });

    await page.evaluate(() => fetch('/api/v2/health', { credentials: 'include' }));

    expect(cookieHeader).toContain(`session_id=${sessionId}`);
  });

  test('WebSocket uses token query param without localStorage session_id', async ({ page }) => {
    test.skip(!MOCK_AUTH_ENABLED, 'Mock auth required to trigger WebSocket login flow.');

    const wsPromise = page.waitForEvent('websocket', { timeout: 10000 });
    await loginAs(page, ADMIN_USER.email, ADMIN_USER.password);

    const ws = await wsPromise;
    expect(ws.url()).toContain('token=');
    expect(ws.url()).not.toContain('session_id=');
  });
});
