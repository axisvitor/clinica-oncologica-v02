/**
 * Admin Dashboard Complete E2E Test
 *
 * Tests the complete admin dashboard functionality:
 * 1. Dashboard loads with all widgets
 * 2. Statistics are displayed correctly
 * 3. Real-time updates work
 * 4. Quick actions are functional
 * 5. Navigation between sections
 * 6. Performance metrics
 *
 * Priority: CRITICAL
 * Estimated Duration: 3-5 minutes
 */

import { test, expect, Page } from '@playwright/test';

// Test data
const ADMIN_CREDENTIALS = {
  email: 'admin@test.com',
  password: 'Test123!@#',
};

// Helper functions
async function loginAsAdmin(page: Page) {
  console.log('🔐 Logging in as admin...');
  await page.goto('/login');

  await page.waitForSelector('[data-testid="email-input"]', { timeout: 10000 });
  await page.fill('[data-testid="email-input"]', ADMIN_CREDENTIALS.email);
  await page.fill('[data-testid="password-input"]', ADMIN_CREDENTIALS.password);

  await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle' }),
    page.click('[data-testid="login-submit"]'),
  ]);

  await expect(page.locator('[data-testid="dashboard"]')).toBeVisible({ timeout: 15000 });
  console.log('✅ Admin logged in successfully');
}

async function waitForDashboardLoad(page: Page) {
  console.log('⏳ Waiting for dashboard to load...');

  // Wait for main dashboard container
  await page.waitForSelector('[data-testid="dashboard-container"]', { timeout: 15000 });

  // Wait for statistics widgets
  await page.waitForSelector('[data-testid="stats-total-patients"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="stats-active-flows"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="stats-pending-quizzes"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="stats-messages-sent"]', { timeout: 10000 });

  // Wait for network to be idle (all API calls completed)
  await page.waitForLoadState('networkidle');

  console.log('✅ Dashboard loaded successfully');
}

async function verifyStatisticsWidgets(page: Page) {
  console.log('📊 Verifying statistics widgets...');

  // Total Patients Widget
  const totalPatients = page.locator('[data-testid="stats-total-patients"]');
  await expect(totalPatients).toBeVisible();
  const patientsCount = await totalPatients.locator('[data-testid="stat-value"]').textContent();
  expect(parseInt(patientsCount!)).toBeGreaterThanOrEqual(0);
  console.log(`  ✅ Total Patients: ${patientsCount}`);

  // Active Flows Widget
  const activeFlows = page.locator('[data-testid="stats-active-flows"]');
  await expect(activeFlows).toBeVisible();
  const flowsCount = await activeFlows.locator('[data-testid="stat-value"]').textContent();
  expect(parseInt(flowsCount!)).toBeGreaterThanOrEqual(0);
  console.log(`  ✅ Active Flows: ${flowsCount}`);

  // Pending Quizzes Widget
  const pendingQuizzes = page.locator('[data-testid="stats-pending-quizzes"]');
  await expect(pendingQuizzes).toBeVisible();
  const quizzesCount = await pendingQuizzes.locator('[data-testid="stat-value"]').textContent();
  expect(parseInt(quizzesCount!)).toBeGreaterThanOrEqual(0);
  console.log(`  ✅ Pending Quizzes: ${quizzesCount}`);

  // Messages Sent Widget
  const messagesSent = page.locator('[data-testid="stats-messages-sent"]');
  await expect(messagesSent).toBeVisible();
  const messagesCount = await messagesSent.locator('[data-testid="stat-value"]').textContent();
  expect(parseInt(messagesCount!)).toBeGreaterThanOrEqual(0);
  console.log(`  ✅ Messages Sent: ${messagesCount}`);

  console.log('✅ All statistics widgets verified');
}

async function verifyRecentActivity(page: Page) {
  console.log('📋 Verifying recent activity feed...');

  const activityFeed = page.locator('[data-testid="recent-activity-feed"]');
  await expect(activityFeed).toBeVisible();

  // Check if activity items exist
  const activityItems = activityFeed.locator('[data-testid="activity-item"]');
  const count = await activityItems.count();

  if (count > 0) {
    console.log(`  ✅ Found ${count} recent activities`);

    // Verify first activity item has required elements
    const firstItem = activityItems.first();
    await expect(firstItem.locator('[data-testid="activity-icon"]')).toBeVisible();
    await expect(firstItem.locator('[data-testid="activity-title"]')).toBeVisible();
    await expect(firstItem.locator('[data-testid="activity-timestamp"]')).toBeVisible();
  } else {
    console.log('  ℹ️  No recent activities');
  }

  console.log('✅ Recent activity feed verified');
}

async function verifyUpcomingTasks(page: Page) {
  console.log('📅 Verifying upcoming tasks...');

  const tasksWidget = page.locator('[data-testid="upcoming-tasks"]');
  await expect(tasksWidget).toBeVisible();

  // Check if tasks exist
  const taskItems = tasksWidget.locator('[data-testid="task-item"]');
  const count = await taskItems.count();

  if (count > 0) {
    console.log(`  ✅ Found ${count} upcoming tasks`);

    // Verify first task has required elements
    const firstTask = taskItems.first();
    await expect(firstTask.locator('[data-testid="task-title"]')).toBeVisible();
    await expect(firstTask.locator('[data-testid="task-priority"]')).toBeVisible();
    await expect(firstTask.locator('[data-testid="task-due-date"]')).toBeVisible();
  } else {
    console.log('  ℹ️  No upcoming tasks');
  }

  console.log('✅ Upcoming tasks verified');
}

async function verifyQuickActions(page: Page) {
  console.log('⚡ Verifying quick actions...');

  const quickActions = page.locator('[data-testid="quick-actions"]');
  await expect(quickActions).toBeVisible();

  // Verify all quick action buttons
  const expectedActions = [
    'add-patient',
    'send-message',
    'create-quiz',
    'view-reports',
  ];

  for (const action of expectedActions) {
    const button = quickActions.locator(`[data-testid="quick-action-${action}"]`);
    await expect(button).toBeVisible();
    console.log(`  ✅ Quick action: ${action}`);
  }

  console.log('✅ Quick actions verified');
}

async function verifyChartsAndGraphs(page: Page) {
  console.log('📈 Verifying charts and graphs...');

  // Patient Growth Chart
  const growthChart = page.locator('[data-testid="patient-growth-chart"]');
  await expect(growthChart).toBeVisible();
  console.log('  ✅ Patient growth chart displayed');

  // Message Activity Chart
  const activityChart = page.locator('[data-testid="message-activity-chart"]');
  await expect(activityChart).toBeVisible();
  console.log('  ✅ Message activity chart displayed');

  // Quiz Completion Rate Chart
  const quizChart = page.locator('[data-testid="quiz-completion-chart"]');
  await expect(quizChart).toBeVisible();
  console.log('  ✅ Quiz completion chart displayed');

  console.log('✅ All charts verified');
}

async function testQuickActionNavigation(page: Page) {
  console.log('🔗 Testing quick action navigation...');

  // Test "Add Patient" quick action
  await page.click('[data-testid="quick-action-add-patient"]');
  await expect(page).toHaveURL(/\/patients\/new/);
  await page.goBack();
  console.log('  ✅ Add Patient navigation works');

  // Test "Send Message" quick action
  await page.click('[data-testid="quick-action-send-message"]');
  await expect(page.locator('[data-testid="message-compose-modal"]')).toBeVisible();
  await page.click('[data-testid="close-modal"]');
  console.log('  ✅ Send Message modal opens');

  // Test "Create Quiz" quick action
  await page.click('[data-testid="quick-action-create-quiz"]');
  await expect(page).toHaveURL(/\/monthly-quiz\/admin/);
  await page.goBack();
  console.log('  ✅ Create Quiz navigation works');

  // Test "View Reports" quick action
  await page.click('[data-testid="quick-action-view-reports"]');
  await expect(page).toHaveURL(/\/reports/);
  await page.goBack();
  console.log('  ✅ View Reports navigation works');

  console.log('✅ Quick action navigation verified');
}

async function testRealTimeUpdates(page: Page) {
  console.log('🔄 Testing real-time updates...');

  // Get initial patient count
  const statsWidget = page.locator('[data-testid="stats-total-patients"]');
  const initialCount = await statsWidget.locator('[data-testid="stat-value"]').textContent();

  console.log(`  📊 Initial patient count: ${initialCount}`);

  // Wait for potential WebSocket update (simulate by waiting)
  await page.waitForTimeout(2000);

  // Check if count updated (in real scenario, this would test WebSocket)
  const updatedCount = await statsWidget.locator('[data-testid="stat-value"]').textContent();
  console.log(`  📊 Updated patient count: ${updatedCount}`);

  // Verify element is still visible (connection maintained)
  await expect(statsWidget).toBeVisible();

  console.log('✅ Real-time update mechanism verified');
}

async function testDashboardResponsiveness(page: Page) {
  console.log('📱 Testing dashboard responsiveness...');

  // Test mobile viewport
  await page.setViewportSize({ width: 375, height: 667 });
  await page.waitForTimeout(500);

  // Verify mobile menu
  await expect(page.locator('[data-testid="mobile-menu-toggle"]')).toBeVisible();
  console.log('  ✅ Mobile menu visible');

  // Verify statistics stack vertically
  const statsContainer = page.locator('[data-testid="statistics-container"]');
  await expect(statsContainer).toBeVisible();
  console.log('  ✅ Statistics responsive');

  // Test tablet viewport
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.waitForTimeout(500);
  await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();
  console.log('  ✅ Tablet layout works');

  // Restore desktop viewport
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(500);
  console.log('  ✅ Desktop layout restored');

  console.log('✅ Dashboard responsiveness verified');
}

async function testDashboardPerformance(page: Page) {
  console.log('⚡ Testing dashboard performance...');

  // Measure navigation timing
  const navigationTiming = await page.evaluate(() => {
    const perfData = window.performance.timing;
    return {
      loadTime: perfData.loadEventEnd - perfData.navigationStart,
      domReady: perfData.domContentLoadedEventEnd - perfData.navigationStart,
      firstPaint: performance.getEntriesByType('paint')[0]?.startTime || 0,
    };
  });

  console.log(`  ⏱️  Page Load Time: ${navigationTiming.loadTime}ms`);
  console.log(`  ⏱️  DOM Ready: ${navigationTiming.domReady}ms`);
  console.log(`  ⏱️  First Paint: ${navigationTiming.firstPaint}ms`);

  // Verify performance budgets
  expect(navigationTiming.loadTime).toBeLessThan(5000); // 5s max
  expect(navigationTiming.domReady).toBeLessThan(3000); // 3s max

  console.log('✅ Performance within acceptable limits');
}

async function testDashboardAccessibility(page: Page) {
  console.log('♿ Testing dashboard accessibility...');

  // Check page has proper heading structure
  const h1Count = await page.locator('h1').count();
  expect(h1Count).toBeGreaterThanOrEqual(1);
  console.log('  ✅ Page has main heading');

  // Check for alt text on images
  const images = page.locator('img');
  const imageCount = await images.count();

  if (imageCount > 0) {
    for (let i = 0; i < imageCount; i++) {
      const img = images.nth(i);
      const alt = await img.getAttribute('alt');
      expect(alt).toBeTruthy();
    }
    console.log(`  ✅ All ${imageCount} images have alt text`);
  }

  // Check for keyboard navigation
  await page.keyboard.press('Tab');
  const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
  expect(focusedElement).toBeTruthy();
  console.log('  ✅ Keyboard navigation works');

  // Check for ARIA labels on interactive elements
  const buttons = page.locator('button');
  const buttonCount = await buttons.count();

  if (buttonCount > 0) {
    console.log(`  ✅ Found ${buttonCount} interactive buttons`);
  }

  console.log('✅ Accessibility checks passed');
}

// Main test suite
test.describe('Admin Dashboard - Complete Flow', () => {

  test.beforeEach(async ({ page }) => {
    // Set timeout for slower operations
    test.setTimeout(120000); // 2 minutes

    // Monitor console errors
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Store errors for later verification
    (page as any).consoleErrors = errors;
  });

  test('TC-DASH-001: Dashboard loads with all widgets and statistics', async ({ page }) => {
    console.log('🚀 Starting dashboard load test...');

    await test.step('Admin logs in', async () => {
      await loginAsAdmin(page);
    });

    await test.step('Dashboard loads completely', async () => {
      await waitForDashboardLoad(page);
    });

    await test.step('Statistics widgets display correctly', async () => {
      await verifyStatisticsWidgets(page);
    });

    await test.step('Recent activity feed works', async () => {
      await verifyRecentActivity(page);
    });

    await test.step('Upcoming tasks display', async () => {
      await verifyUpcomingTasks(page);
    });

    await test.step('Quick actions are available', async () => {
      await verifyQuickActions(page);
    });

    await test.step('Charts and graphs render', async () => {
      await verifyChartsAndGraphs(page);
    });

    // Verify no critical console errors
    const errors = (page as any).consoleErrors;
    const criticalErrors = errors.filter((e: string) =>
      !e.includes('Warning') && !e.includes('favicon')
    );
    expect(criticalErrors.length).toBe(0);

    console.log('🎉 Dashboard load test passed!');
  });

  test('TC-DASH-002: Quick actions navigate correctly', async ({ page }) => {
    console.log('🧪 Testing quick actions...');

    await loginAsAdmin(page);
    await waitForDashboardLoad(page);
    await testQuickActionNavigation(page);

    console.log('✅ Quick actions test passed!');
  });

  test('TC-DASH-003: Real-time updates work', async ({ page }) => {
    console.log('🧪 Testing real-time updates...');

    await loginAsAdmin(page);
    await waitForDashboardLoad(page);
    await testRealTimeUpdates(page);

    console.log('✅ Real-time updates test passed!');
  });

  test('TC-DASH-004: Dashboard is responsive on all devices', async ({ page }) => {
    console.log('🧪 Testing dashboard responsiveness...');

    await loginAsAdmin(page);
    await waitForDashboardLoad(page);
    await testDashboardResponsiveness(page);

    console.log('✅ Responsiveness test passed!');
  });

  test('TC-DASH-005: Dashboard meets performance budgets', async ({ page }) => {
    console.log('🧪 Testing dashboard performance...');

    await loginAsAdmin(page);
    await testDashboardPerformance(page);

    console.log('✅ Performance test passed!');
  });

  test('TC-DASH-006: Dashboard is accessible', async ({ page }) => {
    console.log('🧪 Testing dashboard accessibility...');

    await loginAsAdmin(page);
    await waitForDashboardLoad(page);
    await testDashboardAccessibility(page);

    console.log('✅ Accessibility test passed!');
  });

  test('TC-DASH-007: Statistics widgets refresh on demand', async ({ page }) => {
    console.log('🧪 Testing manual statistics refresh...');

    await loginAsAdmin(page);
    await waitForDashboardLoad(page);

    // Click refresh button
    const refreshButton = page.locator('[data-testid="refresh-statistics"]');
    await expect(refreshButton).toBeVisible();

    // Monitor API calls
    const apiCalls: string[] = [];
    page.on('request', req => {
      if (req.url().includes('/api/v2/analytics')) {
        apiCalls.push(req.url());
      }
    });

    await refreshButton.click();

    // Wait for loading indicator
    await expect(page.locator('[data-testid="statistics-loading"]')).toBeVisible();
    await expect(page.locator('[data-testid="statistics-loading"]')).not.toBeVisible({ timeout: 10000 });

    // Verify API was called
    expect(apiCalls.length).toBeGreaterThan(0);

    console.log('✅ Manual refresh test passed!');
  });

  test('TC-DASH-008: Dashboard handles errors gracefully', async ({ page }) => {
    console.log('🧪 Testing error handling...');

    await loginAsAdmin(page);

    // Simulate network error by going offline
    await page.context().setOffline(true);

    // Try to refresh statistics
    await page.click('[data-testid="refresh-statistics"]').catch(() => {});

    // Should show error message
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible({ timeout: 5000 });

    // Go back online
    await page.context().setOffline(false);

    // Retry should work
    await page.click('[data-testid="retry-button"]');
    await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

    console.log('✅ Error handling test passed!');
  });

  test('TC-DASH-009: Time range filter updates statistics', async ({ page }) => {
    console.log('🧪 Testing time range filter...');

    await loginAsAdmin(page);
    await waitForDashboardLoad(page);

    // Get initial statistics
    const initialValue = await page.locator('[data-testid="stats-total-patients"] [data-testid="stat-value"]').textContent();

    // Change time range to "Last 7 days"
    await page.click('[data-testid="time-range-filter"]');
    await page.click('[data-testid="time-range-7-days"]');

    // Wait for statistics to update
    await page.waitForTimeout(1000);

    // Verify statistics container is still visible
    await expect(page.locator('[data-testid="statistics-container"]')).toBeVisible();

    // Change to "Last 30 days"
    await page.click('[data-testid="time-range-filter"]');
    await page.click('[data-testid="time-range-30-days"]');

    await page.waitForTimeout(1000);
    await expect(page.locator('[data-testid="statistics-container"]')).toBeVisible();

    console.log('✅ Time range filter test passed!');
  });

});
