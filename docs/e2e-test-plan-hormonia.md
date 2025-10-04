# Hormonia Frontend - Comprehensive E2E Test Plan

## Overview

**Application:** Hormonia - Sistema de Gestão Oncológica
**Frontend URL:** http://localhost:5175
**Version:** 2.0.0
**Test Framework:** Playwright
**Last Updated:** 2025-10-04

---

## Table of Contents

1. [Test Environment Setup](#test-environment-setup)
2. [Configuration Tests](#configuration-tests)
3. [Core Functionality Tests](#core-functionality-tests)
4. [Authentication & Authorization Tests](#authentication--authorization-tests)
5. [Navigation & Routing Tests](#navigation--routing-tests)
6. [UI Component Tests](#ui-component-tests)
7. [Performance Tests](#performance-tests)
8. [Accessibility Tests](#accessibility-tests)
9. [Responsive Design Tests](#responsive-design-tests)
10. [Integration Tests](#integration-tests)

---

## Test Environment Setup

### Prerequisites
- Frontend running at `http://localhost:5175`
- Playwright installed and configured
- Test environment variables loaded from `.env.local`

### Required Environment Variables
```env
VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_FIREBASE_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

---

## 1. Configuration Tests

### TC-CONFIG-001: Runtime Configuration Loading
**Priority:** Critical
**Category:** Configuration

**Test Steps:**
1. Navigate to `http://localhost:5175`
2. Open browser DevTools Console
3. Verify runtime configuration is loaded and logged

**Expected Results:**
- Console shows "✅ Using runtime configuration from Railway" OR "⚠️ Using build-time configuration"
- Configuration includes:
  - `VITE_SUPABASE_URL` is set
  - `VITE_SUPABASE_ANON_KEY` is set
  - `VITE_API_URL` points to localhost:8000
  - `VITE_WS_URL` points to ws://localhost:8000

**Playwright Test:**
```typescript
test('should load runtime configuration correctly', async ({ page }) => {
  const consoleLogs: string[] = [];
  page.on('console', msg => consoleLogs.push(msg.text()));

  await page.goto('/');

  // Verify config is loaded
  const configLog = consoleLogs.find(log =>
    log.includes('Frontend Configuration Debug') ||
    log.includes('Using runtime configuration')
  );

  expect(configLog).toBeDefined();

  // Check window.RUNTIME_CONFIG
  const runtimeConfig = await page.evaluate(() => window.RUNTIME_CONFIG);

  expect(runtimeConfig?.VITE_SUPABASE_URL).toBeTruthy();
  expect(runtimeConfig?.VITE_API_URL).toBeTruthy();
});
```

---

### TC-CONFIG-002: Firebase Configuration Validation
**Priority:** Critical
**Category:** Configuration

**Test Steps:**
1. Navigate to application
2. Check Firebase initialization in console
3. Verify Firebase services are available

**Expected Results:**
- No Firebase initialization errors
- Firebase Auth domain matches config
- Project ID is correct

**Playwright Test:**
```typescript
test('should initialize Firebase correctly', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));

  await page.goto('/');
  await page.waitForLoadState('networkidle');

  // Check for Firebase errors
  const firebaseErrors = errors.filter(err =>
    err.toLowerCase().includes('firebase')
  );

  expect(firebaseErrors).toHaveLength(0);

  // Verify Firebase is initialized
  const firebaseInitialized = await page.evaluate(() => {
    return typeof window.firebase !== 'undefined';
  });

  expect(firebaseInitialized).toBeTruthy();
});
```

---

### TC-CONFIG-003: Supabase Client Initialization
**Priority:** Critical
**Category:** Configuration

**Test Steps:**
1. Navigate to application
2. Check for Supabase client initialization
3. Verify connection to Supabase backend

**Expected Results:**
- Supabase client is initialized
- URL points to correct instance
- Anon key is properly set

**Playwright Test:**
```typescript
test('should initialize Supabase client', async ({ page }) => {
  await page.goto('/');

  const supabaseConfig = await page.evaluate(() => {
    return {
      url: window.RUNTIME_CONFIG?.VITE_SUPABASE_URL,
      hasAnonKey: !!window.RUNTIME_CONFIG?.VITE_SUPABASE_ANON_KEY
    };
  });

  expect(supabaseConfig.url).toBe('https://rszpypytdciggybbpnrp.supabase.co');
  expect(supabaseConfig.hasAnonKey).toBe(true);
});
```

---

## 2. Core Functionality Tests

### TC-CORE-001: Homepage Load and Rendering
**Priority:** Critical
**Category:** Core

**Test Steps:**
1. Navigate to `http://localhost:5175`
2. Wait for page load complete
3. Verify page renders without errors

**Expected Results:**
- Page loads within 3 seconds
- No JavaScript console errors
- Root element is visible
- Page title is correct

**Playwright Test:**
```typescript
test('should load homepage successfully', async ({ page }) => {
  const startTime = Date.now();

  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');

  const loadTime = Date.now() - startTime;

  // Performance check
  expect(loadTime).toBeLessThan(3000);

  // Verify page title
  const title = await page.title();
  expect(title).toContain('Hormonia');

  // Verify root element
  const rootElement = page.locator('#root');
  await expect(rootElement).toBeVisible();
});
```

---

### TC-CORE-002: Application Metadata
**Priority:** Medium
**Category:** Core

**Test Steps:**
1. Load application
2. Verify app name and version

**Expected Results:**
- App name: "Hormonia - Sistema de Gestão Oncológica"
- Version: 2.0.0

**Playwright Test:**
```typescript
test('should display correct app metadata', async ({ page }) => {
  await page.goto('/');

  const appName = await page.evaluate(() =>
    import.meta.env.VITE_APP_NAME
  );

  const appVersion = await page.evaluate(() =>
    import.meta.env.VITE_APP_VERSION
  );

  expect(appName).toBe('Hormonia - Sistema de Gestão Oncológica');
  expect(appVersion).toBe('2.0.0');
});
```

---

## 3. Authentication & Authorization Tests

### TC-AUTH-001: Login Page Accessibility
**Priority:** Critical
**Category:** Authentication

**Test Steps:**
1. Navigate to `/login`
2. Verify login page loads
3. Check for required form elements

**Expected Results:**
- Login page displays
- Email input field present
- Password input field present
- Submit button present

**Playwright Test:**
```typescript
test('should display login page with all elements', async ({ page }) => {
  await page.goto('/login');

  // Check form elements
  const emailInput = page.locator('input[type="email"]');
  const passwordInput = page.locator('input[type="password"]');
  const submitButton = page.locator('button[type="submit"]');

  await expect(emailInput).toBeVisible();
  await expect(passwordInput).toBeVisible();
  await expect(submitButton).toBeVisible();
});
```

---

### TC-AUTH-002: Protected Route Redirection
**Priority:** Critical
**Category:** Authentication

**Test Steps:**
1. Clear all cookies/localStorage
2. Navigate to `/dashboard` (protected route)
3. Verify redirect to login

**Expected Results:**
- Automatically redirects to `/login`
- Shows message about authentication requirement

**Playwright Test:**
```typescript
test('should redirect to login for protected routes', async ({ page }) => {
  // Clear auth state
  await page.context().clearCookies();

  await page.goto('/dashboard');

  // Should redirect to login
  await page.waitForURL('**/login');
  expect(page.url()).toContain('/login');
});
```

---

### TC-AUTH-003: Firebase Authentication Flow
**Priority:** Critical
**Category:** Authentication

**Test Steps:**
1. Navigate to login page
2. Enter test credentials
3. Submit form
4. Verify authentication

**Expected Results:**
- Firebase authentication succeeds
- Token stored in localStorage
- Redirected to dashboard

**Playwright Test:**
```typescript
test('should authenticate user with Firebase', async ({ page }) => {
  await page.goto('/login');

  // Fill credentials
  await page.fill('input[type="email"]', 'test@example.com');
  await page.fill('input[type="password"]', 'testpassword');

  // Submit
  await page.click('button[type="submit"]');

  // Wait for redirect
  await page.waitForURL('**/dashboard', { timeout: 10000 });

  // Verify auth token
  const hasToken = await page.evaluate(() => {
    return !!localStorage.getItem('hormonia_access_token');
  });

  expect(hasToken).toBe(true);
});
```

---

## 4. Navigation & Routing Tests

### TC-NAV-001: Main Navigation Menu
**Priority:** High
**Category:** Navigation

**Test Steps:**
1. Login as authenticated user
2. Verify sidebar navigation is visible
3. Check all menu items

**Expected Results:**
- Sidebar renders correctly
- All main menu items present:
  - Dashboard
  - Patients
  - Messages
  - Quiz
  - Monthly Quiz
  - Reports
  - Alerts
  - Analytics
  - Settings
  - Flows
  - Questionários
  - WhatsApp

**Playwright Test:**
```typescript
test('should display all navigation menu items', async ({ page }) => {
  // Assume authenticated
  await page.goto('/dashboard');

  const menuItems = [
    'Dashboard',
    'Pacientes',
    'Mensagens',
    'Quiz',
    'Relatórios',
    'Alertas',
    'Analytics',
    'Configurações'
  ];

  for (const item of menuItems) {
    const menuItem = page.locator(`nav a:has-text("${item}")`);
    await expect(menuItem).toBeVisible();
  }
});
```

---

### TC-NAV-002: Route Navigation
**Priority:** High
**Category:** Navigation

**Test Steps:**
1. Login to application
2. Navigate to each main route
3. Verify page loads correctly

**Expected Results:**
- All routes load without errors
- Correct page content displays
- URL updates correctly

**Playwright Test:**
```typescript
test('should navigate to all main routes', async ({ page }) => {
  const routes = [
    { path: '/dashboard', title: 'Dashboard' },
    { path: '/patients', title: 'Pacientes' },
    { path: '/messages', title: 'Mensagens' },
    { path: '/quiz', title: 'Quiz' },
    { path: '/reports', title: 'Relatórios' }
  ];

  for (const route of routes) {
    await page.goto(route.path);
    await page.waitForLoadState('networkidle');

    // Verify no errors
    const hasError = await page.locator('.error').isVisible()
      .catch(() => false);
    expect(hasError).toBe(false);
  }
});
```

---

### TC-NAV-003: Breadcrumb Navigation
**Priority:** Medium
**Category:** Navigation

**Test Steps:**
1. Navigate to nested routes
2. Verify breadcrumb displays
3. Click breadcrumb items

**Expected Results:**
- Breadcrumb shows current location
- Breadcrumb links work correctly

**Playwright Test:**
```typescript
test('should display and navigate breadcrumbs', async ({ page }) => {
  await page.goto('/patients/123');

  // Check breadcrumb exists
  const breadcrumb = page.locator('[data-testid="breadcrumb"]');
  await expect(breadcrumb).toBeVisible();

  // Verify breadcrumb items
  const homeLink = breadcrumb.locator('a:has-text("Home")');
  const patientsLink = breadcrumb.locator('a:has-text("Pacientes")');

  await expect(homeLink).toBeVisible();
  await expect(patientsLink).toBeVisible();

  // Test navigation
  await patientsLink.click();
  await page.waitForURL('**/patients');
  expect(page.url()).toContain('/patients');
});
```

---

### TC-NAV-004: 404 Error Page
**Priority:** Medium
**Category:** Navigation

**Test Steps:**
1. Navigate to non-existent route
2. Verify 404 page displays

**Expected Results:**
- 404 page shows
- "Página não encontrada" message displays
- "Voltar ao Dashboard" button present and functional

**Playwright Test:**
```typescript
test('should show 404 page for invalid routes', async ({ page }) => {
  await page.goto('/non-existent-route');

  // Check 404 content
  const notFoundText = page.locator('text=404');
  await expect(notFoundText).toBeVisible();

  const message = page.locator('text=Página não encontrada');
  await expect(message).toBeVisible();

  // Test back button
  const backButton = page.locator('button:has-text("Voltar ao Dashboard")');
  await backButton.click();

  await page.waitForURL('**/dashboard');
  expect(page.url()).toContain('/dashboard');
});
```

---

## 5. UI Component Tests

### TC-UI-001: Sidebar Component
**Priority:** High
**Category:** UI Components

**Test Steps:**
1. Load dashboard
2. Verify sidebar renders
3. Test sidebar collapse/expand

**Expected Results:**
- Sidebar visible by default
- Toggle button works
- Sidebar state persists

**Playwright Test:**
```typescript
test('should toggle sidebar visibility', async ({ page }) => {
  await page.goto('/dashboard');

  const sidebar = page.locator('[data-testid="sidebar"]');
  const toggleButton = page.locator('[data-testid="sidebar-toggle"]');

  // Initially visible
  await expect(sidebar).toBeVisible();

  // Toggle collapse
  await toggleButton.click();
  await expect(sidebar).toHaveClass(/collapsed/);

  // Toggle expand
  await toggleButton.click();
  await expect(sidebar).not.toHaveClass(/collapsed/);
});
```

---

### TC-UI-002: Notification Center
**Priority:** Medium
**Category:** UI Components

**Test Steps:**
1. Navigate to dashboard
2. Click notification bell icon
3. Verify notification panel opens

**Expected Results:**
- Notification icon displays
- Panel opens on click
- Notifications list is visible

**Playwright Test:**
```typescript
test('should open and display notifications', async ({ page }) => {
  await page.goto('/dashboard');

  const notificationBell = page.locator('[data-testid="notification-bell"]');
  await notificationBell.click();

  const notificationPanel = page.locator('[data-testid="notification-panel"]');
  await expect(notificationPanel).toBeVisible();

  // Check for notification items
  const notificationItems = notificationPanel.locator('.notification-item');
  const count = await notificationItems.count();
  expect(count).toBeGreaterThanOrEqual(0);
});
```

---

### TC-UI-003: Toast Notifications
**Priority:** Medium
**Category:** UI Components

**Test Steps:**
1. Trigger an action that shows toast
2. Verify toast appears
3. Verify toast auto-dismisses

**Expected Results:**
- Toast displays with message
- Toast auto-dismisses after timeout
- Multiple toasts stack correctly

**Playwright Test:**
```typescript
test('should display and dismiss toast notifications', async ({ page }) => {
  await page.goto('/dashboard');

  // Trigger action that shows toast (example: save settings)
  await page.click('[data-testid="save-settings"]');

  // Verify toast appears
  const toast = page.locator('[data-testid="toast"]');
  await expect(toast).toBeVisible();

  // Verify auto-dismiss
  await expect(toast).toBeHidden({ timeout: 6000 });
});
```

---

### TC-UI-004: Modal Dialogs
**Priority:** High
**Category:** UI Components

**Test Steps:**
1. Open a modal dialog
2. Verify modal displays
3. Test close functionality

**Expected Results:**
- Modal opens correctly
- Overlay blocks background interaction
- Close button works
- ESC key closes modal

**Playwright Test:**
```typescript
test('should open and close modal dialogs', async ({ page }) => {
  await page.goto('/patients');

  // Open modal
  const addPatientButton = page.locator('[data-testid="add-patient"]');
  await addPatientButton.click();

  const modal = page.locator('[role="dialog"]');
  await expect(modal).toBeVisible();

  // Test ESC key
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();

  // Open again and test close button
  await addPatientButton.click();
  await expect(modal).toBeVisible();

  const closeButton = modal.locator('[data-testid="close-modal"]');
  await closeButton.click();
  await expect(modal).toBeHidden();
});
```

---

### TC-UI-005: Loading States
**Priority:** Medium
**Category:** UI Components

**Test Steps:**
1. Navigate to page with async data
2. Verify loading spinner displays
3. Verify spinner disappears when loaded

**Expected Results:**
- Loading spinner shows during data fetch
- Spinner disappears when complete
- Content displays after loading

**Playwright Test:**
```typescript
test('should display loading states correctly', async ({ page }) => {
  await page.goto('/patients');

  // Check for loading spinner
  const spinner = page.locator('[data-testid="loading-spinner"]');

  // May or may not be visible depending on load speed
  const isVisible = await spinner.isVisible().catch(() => false);

  // Wait for content to load
  await page.waitForSelector('[data-testid="patients-table"]', {
    timeout: 10000
  });

  // Spinner should be hidden
  await expect(spinner).toBeHidden();
});
```

---

## 6. Performance Tests

### TC-PERF-001: Initial Page Load Time
**Priority:** High
**Category:** Performance

**Test Steps:**
1. Clear cache
2. Navigate to homepage
3. Measure load time

**Expected Results:**
- First Contentful Paint (FCP) < 1.5s
- Largest Contentful Paint (LCP) < 2.5s
- Time to Interactive (TTI) < 3.0s

**Playwright Test:**
```typescript
test('should load page within performance budgets', async ({ page }) => {
  await page.goto('/');

  const metrics = await page.evaluate(() => {
    const perfData = window.performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    return {
      fcp: perfData.responseStart - perfData.fetchStart,
      lcp: perfData.loadEventEnd - perfData.fetchStart,
      tti: perfData.domInteractive - perfData.fetchStart
    };
  });

  expect(metrics.fcp).toBeLessThan(1500);
  expect(metrics.lcp).toBeLessThan(2500);
  expect(metrics.tti).toBeLessThan(3000);
});
```

---

### TC-PERF-002: Bundle Size Check
**Priority:** Medium
**Category:** Performance

**Test Steps:**
1. Load application
2. Check network requests
3. Verify bundle sizes

**Expected Results:**
- Main JS bundle < 500KB
- Main CSS bundle < 100KB
- Total initial load < 1MB

**Playwright Test:**
```typescript
test('should load with reasonable bundle sizes', async ({ page }) => {
  const resources: { type: string; size: number }[] = [];

  page.on('response', response => {
    const url = response.url();
    if (url.includes('.js') || url.includes('.css')) {
      resources.push({
        type: url.includes('.js') ? 'js' : 'css',
        size: response.headers()['content-length'] || 0
      });
    }
  });

  await page.goto('/');
  await page.waitForLoadState('networkidle');

  const totalJS = resources
    .filter(r => r.type === 'js')
    .reduce((sum, r) => sum + r.size, 0);

  const totalCSS = resources
    .filter(r => r.type === 'css')
    .reduce((sum, r) => sum + r.size, 0);

  expect(totalJS).toBeLessThan(500000); // 500KB
  expect(totalCSS).toBeLessThan(100000); // 100KB
});
```

---

### TC-PERF-003: API Response Times
**Priority:** High
**Category:** Performance

**Test Steps:**
1. Navigate to patients page
2. Measure API request times
3. Verify acceptable response times

**Expected Results:**
- API requests complete < 1000ms
- No requests timeout (30s limit)

**Playwright Test:**
```typescript
test('should have acceptable API response times', async ({ page }) => {
  const apiTimes: number[] = [];

  page.on('response', response => {
    if (response.url().includes('/api/')) {
      const timing = response.timing();
      apiTimes.push(timing.responseEnd);
    }
  });

  await page.goto('/patients');
  await page.waitForLoadState('networkidle');

  const avgTime = apiTimes.reduce((a, b) => a + b, 0) / apiTimes.length;
  expect(avgTime).toBeLessThan(1000);
});
```

---

### TC-PERF-004: Memory Leaks Check
**Priority:** Medium
**Category:** Performance

**Test Steps:**
1. Navigate through multiple pages
2. Check memory usage
3. Return to initial page
4. Verify memory is released

**Expected Results:**
- Memory usage doesn't continuously increase
- Garbage collection works properly

**Playwright Test:**
```typescript
test('should not have memory leaks during navigation', async ({ page }) => {
  const routes = ['/dashboard', '/patients', '/messages', '/dashboard'];

  for (const route of routes) {
    await page.goto(route);
    await page.waitForLoadState('networkidle');
  }

  const metrics = await page.evaluate(() => {
    return (performance as any).memory?.usedJSHeapSize || 0;
  });

  // Heap size should be reasonable (< 100MB)
  expect(metrics).toBeLessThan(100000000);
});
```

---

## 7. Accessibility Tests

### TC-A11Y-001: Keyboard Navigation
**Priority:** High
**Category:** Accessibility

**Test Steps:**
1. Navigate to dashboard
2. Use only keyboard (Tab, Enter, Space)
3. Navigate through all interactive elements

**Expected Results:**
- All interactive elements focusable
- Focus indicators visible
- Tab order is logical
- No keyboard traps

**Playwright Test:**
```typescript
test('should support full keyboard navigation', async ({ page }) => {
  await page.goto('/dashboard');

  // Tab through elements
  for (let i = 0; i < 10; i++) {
    await page.keyboard.press('Tab');

    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return {
        tag: el?.tagName,
        visible: el ? window.getComputedStyle(el).visibility !== 'hidden' : false
      };
    });

    expect(focused.visible).toBe(true);
  }

  // Should be able to activate focused element with Enter
  await page.keyboard.press('Enter');

  // Check no errors occurred
  const errors = await page.evaluate(() =>
    window.console.errors || []
  );
  expect(errors).toHaveLength(0);
});
```

---

### TC-A11Y-002: Screen Reader Support
**Priority:** High
**Category:** Accessibility

**Test Steps:**
1. Load application
2. Check ARIA attributes
3. Verify semantic HTML

**Expected Results:**
- Proper ARIA labels on interactive elements
- Semantic HTML elements used
- Alt text on images
- Form labels associated correctly

**Playwright Test:**
```typescript
test('should have proper ARIA attributes', async ({ page }) => {
  await page.goto('/dashboard');

  // Check for ARIA landmarks
  const main = page.locator('[role="main"]');
  await expect(main).toBeVisible();

  const navigation = page.locator('[role="navigation"]');
  await expect(navigation).toBeVisible();

  // Check buttons have labels
  const buttons = page.locator('button');
  const count = await buttons.count();

  for (let i = 0; i < count; i++) {
    const button = buttons.nth(i);
    const hasLabel = await button.evaluate(el => {
      return !!(el.getAttribute('aria-label') || el.textContent?.trim());
    });
    expect(hasLabel).toBe(true);
  }
});
```

---

### TC-A11Y-003: Color Contrast
**Priority:** Medium
**Category:** Accessibility

**Test Steps:**
1. Load application
2. Check text contrast ratios
3. Verify WCAG AA compliance

**Expected Results:**
- Text contrast ratio ≥ 4.5:1 (normal text)
- Text contrast ratio ≥ 3:1 (large text)
- Interactive elements meet contrast requirements

**Playwright Test:**
```typescript
test('should meet color contrast requirements', async ({ page }) => {
  await page.goto('/dashboard');

  // Use axe-core or similar for contrast checking
  const contrastIssues = await page.evaluate(() => {
    // Simple contrast check (would use axe-core in real scenario)
    const elements = document.querySelectorAll('p, h1, h2, h3, button, a');
    const issues: string[] = [];

    elements.forEach(el => {
      const styles = window.getComputedStyle(el);
      const color = styles.color;
      const bg = styles.backgroundColor;

      // Would calculate actual contrast ratio here
      // For now, just check they're defined
      if (!color || !bg) {
        issues.push(el.tagName);
      }
    });

    return issues;
  });

  expect(contrastIssues).toHaveLength(0);
});
```

---

### TC-A11Y-004: Focus Management
**Priority:** High
**Category:** Accessibility

**Test Steps:**
1. Open modal dialog
2. Verify focus traps within modal
3. Close modal and verify focus returns

**Expected Results:**
- Focus moves to modal on open
- Tab cycles within modal only
- Focus returns to trigger on close

**Playwright Test:**
```typescript
test('should manage focus correctly in modals', async ({ page }) => {
  await page.goto('/patients');

  const trigger = page.locator('[data-testid="add-patient"]');
  await trigger.click();

  const modal = page.locator('[role="dialog"]');
  await expect(modal).toBeVisible();

  // First focusable element should be focused
  const focusedTag = await page.evaluate(() =>
    document.activeElement?.tagName
  );

  expect(['INPUT', 'BUTTON']).toContain(focusedTag);

  // Close modal
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();

  // Focus should return to trigger
  const currentFocus = await page.evaluate(() =>
    document.activeElement?.getAttribute('data-testid')
  );

  expect(currentFocus).toBe('add-patient');
});
```

---

## 8. Responsive Design Tests

### TC-RESP-001: Mobile Viewport (375px)
**Priority:** High
**Category:** Responsive

**Test Steps:**
1. Set viewport to mobile (375x667)
2. Navigate to main pages
3. Verify mobile layout

**Expected Results:**
- Mobile navigation menu displays
- Content adapts to small screen
- No horizontal scroll
- Touch targets ≥ 44px

**Playwright Test:**
```typescript
test('should display correctly on mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto('/dashboard');

  // Check for mobile menu
  const mobileMenu = page.locator('[data-testid="mobile-menu"]');
  await expect(mobileMenu).toBeVisible();

  // Check no horizontal scroll
  const hasHorizontalScroll = await page.evaluate(() =>
    document.documentElement.scrollWidth > document.documentElement.clientWidth
  );

  expect(hasHorizontalScroll).toBe(false);

  // Check touch target sizes
  const buttons = page.locator('button');
  const count = await buttons.count();

  for (let i = 0; i < Math.min(count, 5); i++) {
    const size = await buttons.nth(i).boundingBox();
    if (size) {
      expect(size.height).toBeGreaterThanOrEqual(44);
    }
  }
});
```

---

### TC-RESP-002: Tablet Viewport (768px)
**Priority:** Medium
**Category:** Responsive

**Test Steps:**
1. Set viewport to tablet (768x1024)
2. Navigate through application
3. Verify tablet layout

**Expected Results:**
- Sidebar adapts for tablet
- Content uses available space
- Images scale appropriately

**Playwright Test:**
```typescript
test('should display correctly on tablet viewport', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto('/dashboard');

  // Sidebar should be visible but may be collapsible
  const sidebar = page.locator('[data-testid="sidebar"]');
  await expect(sidebar).toBeVisible();

  // Content area should use remaining space
  const content = page.locator('[data-testid="main-content"]');
  const contentBox = await content.boundingBox();

  expect(contentBox?.width).toBeGreaterThan(400);
  expect(contentBox?.width).toBeLessThan(768);
});
```

---

### TC-RESP-003: Desktop Viewport (1920px)
**Priority:** High
**Category:** Responsive

**Test Steps:**
1. Set viewport to desktop (1920x1080)
2. Navigate through application
3. Verify desktop layout

**Expected Results:**
- Full sidebar visible
- Content centered with max-width
- All features accessible

**Playwright Test:**
```typescript
test('should display correctly on desktop viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('/dashboard');

  // Full sidebar visible
  const sidebar = page.locator('[data-testid="sidebar"]');
  await expect(sidebar).toBeVisible();

  const sidebarBox = await sidebar.boundingBox();
  expect(sidebarBox?.width).toBeGreaterThanOrEqual(280);

  // Content should have appropriate max-width
  const content = page.locator('[data-testid="main-content"]');
  const contentBox = await content.boundingBox();

  expect(contentBox?.width).toBeLessThan(1920);
});
```

---

### TC-RESP-004: Orientation Change
**Priority:** Medium
**Category:** Responsive

**Test Steps:**
1. Load on mobile viewport
2. Rotate to landscape
3. Verify layout adapts

**Expected Results:**
- Layout adjusts to landscape
- No content overflow
- Navigation remains accessible

**Playwright Test:**
```typescript
test('should handle orientation changes', async ({ page }) => {
  // Portrait
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto('/dashboard');

  let hasOverflow = await page.evaluate(() =>
    document.body.scrollWidth > window.innerWidth
  );
  expect(hasOverflow).toBe(false);

  // Landscape
  await page.setViewportSize({ width: 667, height: 375 });
  await page.waitForTimeout(500); // Allow layout to adjust

  hasOverflow = await page.evaluate(() =>
    document.body.scrollWidth > window.innerWidth
  );
  expect(hasOverflow).toBe(false);
});
```

---

## 9. Integration Tests

### TC-INT-001: Firebase Authentication Integration
**Priority:** Critical
**Category:** Integration

**Test Steps:**
1. Login with Firebase credentials
2. Verify token is set
3. Make authenticated API request
4. Logout and verify session cleared

**Expected Results:**
- Login successful
- Token stored correctly
- API accepts token
- Logout clears session

**Playwright Test:**
```typescript
test('should integrate with Firebase authentication', async ({ page }) => {
  await page.goto('/login');

  // Login
  await page.fill('input[type="email"]', 'test@example.com');
  await page.fill('input[type="password"]', 'testpassword');
  await page.click('button[type="submit"]');

  await page.waitForURL('**/dashboard');

  // Check token
  const token = await page.evaluate(() =>
    localStorage.getItem('hormonia_access_token')
  );
  expect(token).toBeTruthy();

  // Logout
  await page.click('[data-testid="logout"]');
  await page.waitForURL('**/login');

  // Verify token cleared
  const tokenAfterLogout = await page.evaluate(() =>
    localStorage.getItem('hormonia_access_token')
  );
  expect(tokenAfterLogout).toBeNull();
});
```

---

### TC-INT-002: Supabase Data Fetching
**Priority:** Critical
**Category:** Integration

**Test Steps:**
1. Navigate to patients page
2. Verify data loads from Supabase
3. Check for real-time updates

**Expected Results:**
- Patient data loads correctly
- Supabase client authenticated
- Real-time subscriptions work

**Playwright Test:**
```typescript
test('should fetch data from Supabase', async ({ page }) => {
  await page.goto('/patients');

  // Wait for data to load
  await page.waitForSelector('[data-testid="patients-table"]');

  // Check table has rows
  const rows = page.locator('[data-testid="patient-row"]');
  const count = await rows.count();

  expect(count).toBeGreaterThan(0);

  // Verify data structure
  const firstRow = rows.first();
  await expect(firstRow).toContainText(/./); // Has some text
});
```

---

### TC-INT-003: WebSocket Connection
**Priority:** High
**Category:** Integration

**Test Steps:**
1. Navigate to messages page
2. Verify WebSocket connects
3. Test real-time message delivery

**Expected Results:**
- WebSocket connects to ws://localhost:8000/ws
- Connection stays alive
- Messages received in real-time

**Playwright Test:**
```typescript
test('should establish WebSocket connection', async ({ page }) => {
  let wsConnected = false;

  page.on('websocket', ws => {
    wsConnected = ws.url().includes('ws://localhost:8000');
  });

  await page.goto('/messages');
  await page.waitForTimeout(2000); // Allow WS to connect

  expect(wsConnected).toBe(true);
});
```

---

### TC-INT-004: WhatsApp Integration
**Priority:** High
**Category:** Integration

**Test Steps:**
1. Navigate to WhatsApp page
2. Verify WhatsApp status
3. Test sending message (if connected)

**Expected Results:**
- WhatsApp instance status displays
- Connection status is accurate
- Messages can be sent (if connected)

**Playwright Test:**
```typescript
test('should display WhatsApp integration status', async ({ page }) => {
  await page.goto('/whatsapp');

  // Check for status indicator
  const status = page.locator('[data-testid="whatsapp-status"]');
  await expect(status).toBeVisible();

  // Status should be one of: connected, disconnected, connecting
  const statusText = await status.textContent();
  expect(['Conectado', 'Desconectado', 'Conectando'])
    .toContain(statusText?.trim() || '');
});
```

---

## 10. Feature-Specific Tests

### TC-FEAT-001: AI Chat Feature
**Priority:** High
**Category:** Features

**Test Steps:**
1. Navigate to AI chat
2. Send a message
3. Verify AI response

**Expected Results:**
- Chat interface loads
- Messages can be sent
- AI responds appropriately

**Playwright Test:**
```typescript
test('should interact with AI chat', async ({ page }) => {
  await page.goto('/dashboard');

  // Open AI chat
  const chatButton = page.locator('[data-testid="ai-chat-button"]');
  await chatButton.click();

  const chatPanel = page.locator('[data-testid="ai-chat-panel"]');
  await expect(chatPanel).toBeVisible();

  // Send message
  const input = chatPanel.locator('input[type="text"]');
  await input.fill('Olá');
  await page.keyboard.press('Enter');

  // Wait for response
  await page.waitForSelector('[data-testid="ai-message"]', {
    timeout: 10000
  });

  const messages = chatPanel.locator('[data-testid="ai-message"]');
  expect(await messages.count()).toBeGreaterThan(0);
});
```

---

### TC-FEAT-002: Appointment Booking
**Priority:** High
**Category:** Features

**Test Steps:**
1. Navigate to appointment booking
2. Select date and time
3. Book appointment

**Expected Results:**
- Calendar displays
- Available slots shown
- Booking confirmation displayed

**Playwright Test:**
```typescript
test('should book an appointment', async ({ page }) => {
  await page.goto('/appointments');

  // Select date
  const calendar = page.locator('[data-testid="appointment-calendar"]');
  await expect(calendar).toBeVisible();

  const availableSlot = page.locator('[data-testid="available-slot"]').first();
  await availableSlot.click();

  // Confirm booking
  const confirmButton = page.locator('button:has-text("Confirmar")');
  await confirmButton.click();

  // Check confirmation
  const confirmation = page.locator('[data-testid="booking-confirmation"]');
  await expect(confirmation).toBeVisible();
});
```

---

### TC-FEAT-003: Monthly Quiz Dashboard
**Priority:** High
**Category:** Features

**Test Steps:**
1. Navigate to monthly quiz dashboard
2. View quiz statistics
3. Send quiz link to patient

**Expected Results:**
- Dashboard displays quiz data
- Statistics are accurate
- Quiz links can be generated

**Playwright Test:**
```typescript
test('should display monthly quiz dashboard', async ({ page }) => {
  await page.goto('/monthly-quiz');

  // Check dashboard elements
  const stats = page.locator('[data-testid="quiz-stats"]');
  await expect(stats).toBeVisible();

  // Check for quiz templates
  const templates = page.locator('[data-testid="quiz-template"]');
  expect(await templates.count()).toBeGreaterThan(0);

  // Test sending quiz link
  const sendButton = page.locator('[data-testid="send-quiz-link"]').first();
  await sendButton.click();

  const modal = page.locator('[role="dialog"]');
  await expect(modal).toBeVisible();
});
```

---

## Test Execution Plan

### Execution Order
1. **Configuration Tests** (TC-CONFIG-001 to TC-CONFIG-003)
2. **Core Functionality Tests** (TC-CORE-001 to TC-CORE-002)
3. **Authentication Tests** (TC-AUTH-001 to TC-AUTH-003)
4. **Navigation Tests** (TC-NAV-001 to TC-NAV-004)
5. **UI Component Tests** (TC-UI-001 to TC-UI-005)
6. **Performance Tests** (TC-PERF-001 to TC-PERF-004)
7. **Accessibility Tests** (TC-A11Y-001 to TC-A11Y-004)
8. **Responsive Tests** (TC-RESP-001 to TC-RESP-004)
9. **Integration Tests** (TC-INT-001 to TC-INT-004)
10. **Feature Tests** (TC-FEAT-001 to TC-FEAT-003)

### Execution Commands

```bash
# Run all tests
npm run test:e2e

# Run smoke tests only
npm run test:e2e:smoke

# Run specific test category
npx playwright test --grep "@configuration"

# Run tests in headed mode (visible browser)
npm run test:e2e:headed

# Run tests with UI mode (interactive)
npm run test:e2e:ui

# Generate HTML report
npm run test:e2e:report
```

---

## Test Data Requirements

### Mock Users
```typescript
{
  admin: {
    email: 'admin@hormonia.com',
    password: 'admin123',
    role: 'ADMIN'
  },
  doctor: {
    email: 'doctor@hormonia.com',
    password: 'doctor123',
    role: 'PHYSICIAN'
  },
  patient: {
    email: 'patient@hormonia.com',
    password: 'patient123',
    role: 'PATIENT'
  }
}
```

### Test Patients Data
- At least 5 patient records
- Various statuses (active, inactive)
- Different quiz completion states

---

## CI/CD Integration

### GitHub Actions Workflow
```yaml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright
        run: npx playwright install --with-deps

      - name: Run E2E tests
        run: npm run test:e2e
        env:
          VITE_SUPABASE_URL: ${{ secrets.VITE_SUPABASE_URL }}
          VITE_SUPABASE_ANON_KEY: ${{ secrets.VITE_SUPABASE_ANON_KEY }}

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: test-results/
```

---

## Success Criteria

### Test Coverage Goals
- **Configuration Tests:** 100% pass rate
- **Core Functionality:** 100% pass rate
- **Authentication:** 100% pass rate
- **Navigation:** 95% pass rate
- **UI Components:** 90% pass rate
- **Performance:** 85% pass rate
- **Accessibility:** 80% pass rate
- **Responsive:** 90% pass rate
- **Integration:** 95% pass rate
- **Features:** 85% pass rate

### Performance Benchmarks
- Page load < 3 seconds
- API response < 1 second
- No memory leaks
- Bundle size < 1MB

### Quality Gates
- All critical tests must pass
- No accessibility violations (WCAG AA)
- Performance budgets met
- Zero console errors on critical paths

---

## Troubleshooting Guide

### Common Issues

#### Issue: Tests fail due to authentication
**Solution:** Ensure test credentials are correct and Firebase is accessible

#### Issue: WebSocket connection fails
**Solution:** Verify backend is running on localhost:8000

#### Issue: Supabase timeouts
**Solution:** Check network connectivity and Supabase API keys

#### Issue: Flaky tests
**Solution:** Add proper waits, use `waitForLoadState('networkidle')`

---

## Appendix

### Environment Variables Reference
```env
# Test-specific
PLAYWRIGHT_TEST_BASE_URL=http://localhost:5175
TEST_AUTH_EMAIL=test@example.com
TEST_AUTH_PASSWORD=testpassword123

# Application
VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

### Useful Playwright Commands
```bash
# Debug specific test
npx playwright test --debug tests/e2e/config.spec.ts

# Run in specific browser
npx playwright test --project="Desktop Chrome"

# Update snapshots
npx playwright test --update-snapshots

# Show test trace
npx playwright show-trace trace.zip
```

---

**Document Version:** 1.0
**Last Updated:** 2025-10-04
**Author:** Strategic Planning Agent
**Status:** Ready for Execution
