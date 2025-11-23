/**
 * E2E-007: Admin Workflow
 * Tests: login → dashboard → patient management
 */
import { test, expect, Page } from '@playwright/test';

test.describe('E2E-007: Admin Workflow', () => {
  let page: Page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();

    // Login as admin
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'admin@test.com');
    await page.fill('input[name="password"]', 'Test@1234');
    await page.click('button[type="submit"]');

    // Wait for dashboard
    await page.waitForURL('**/admin/dashboard');
  });

  test.afterEach(async () => {
    await page.close();
  });

  test('should complete admin workflow: login → dashboard → patient list', async () => {
    // Step 1: Verify dashboard loaded
    await expect(page.locator('h1')).toContainText('Dashboard');

    // Check key metrics visible
    await expect(page.locator('[data-testid="total-patients"]')).toBeVisible();
    await expect(page.locator('[data-testid="active-patients"]')).toBeVisible();
    await expect(page.locator('[data-testid="pending-quizzes"]')).toBeVisible();

    // Step 2: Navigate to patients
    await page.click('a[href="/admin/patients"]');
    await page.waitForURL('**/admin/patients');

    // Step 3: Verify patient list loaded
    await expect(page.locator('table')).toBeVisible();
    await expect(page.locator('tbody tr')).toHaveCount.greaterThan(0);

    // Step 4: Search for patient
    await page.fill('input[placeholder*="Buscar"]', 'Maria');
    await page.waitForTimeout(500); // Debounce

    // Verify filtered results
    const rows = page.locator('tbody tr');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    // Step 5: View patient details
    await rows.first().click();
    await expect(page.locator('[data-testid="patient-details"]')).toBeVisible();

    // Step 6: Return to dashboard
    await page.click('a[href="/admin/dashboard"]');
    await page.waitForURL('**/admin/dashboard');
    await expect(page.locator('h1')).toContainText('Dashboard');
  });

  test('should handle admin permissions correctly', async () => {
    // Navigate to admin-only section
    await page.goto('/admin/users');

    // Should have access
    await expect(page.locator('h1')).toContainText('Usuários');

    // Verify user management features visible
    await expect(page.locator('button:has-text("Novo Usuário")')).toBeVisible();
  });

  test('should logout successfully', async () => {
    // Click logout button
    await page.click('[data-testid="user-menu"]');
    await page.click('button:has-text("Sair")');

    // Should redirect to login
    await page.waitForURL('**/admin/login');
    await expect(page.locator('h1')).toContainText('Login');

    // Verify cannot access protected route
    await page.goto('/admin/dashboard');
    await page.waitForURL('**/admin/login'); // Redirected back
  });

  test('should display real-time notifications', async () => {
    // Wait for notification bell
    const notificationBell = page.locator('[data-testid="notification-bell"]');
    await expect(notificationBell).toBeVisible();

    // Check badge count (if any)
    const badge = page.locator('[data-testid="notification-badge"]');
    if (await badge.isVisible()) {
      const count = await badge.textContent();
      expect(parseInt(count || '0')).toBeGreaterThanOrEqual(0);
    }

    // Open notifications
    await notificationBell.click();
    await expect(page.locator('[data-testid="notification-dropdown"]')).toBeVisible();
  });
});
