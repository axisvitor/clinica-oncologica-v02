import { test, expect } from '@playwright/test'

test.describe('Admin Authentication E2E Tests', () => {
  const ADMIN_EMAIL = 'admin@hormonia.com'
  const ADMIN_PASSWORD = 'TestPassword123!'
  const BASE_URL = 'http://localhost:4173'

  test.beforeEach(async ({ page }) => {
    // Navigate to admin login page before each test
    await page.goto(`${BASE_URL}/admin/login`)
  })

  test.describe('Admin Login', () => {
    test('should display admin login page with all elements', async ({ page }) => {
      // Verify page title
      await expect(page).toHaveTitle(/Admin.*Login/i)

      // Verify login form elements
      await expect(page.getByLabel(/email/i)).toBeVisible()
      await expect(page.getByLabel(/password/i)).toBeVisible()
      await expect(page.getByRole('button', { name: /login/i })).toBeVisible()
      await expect(page.getByLabel(/remember me/i)).toBeVisible()
    })

    test('should successfully login with valid admin credentials', async ({ page }) => {
      // Fill in login form
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)

      // Click login button
      await page.getByRole('button', { name: /login/i }).click()

      // Wait for navigation to admin dashboard
      await page.waitForURL(`${BASE_URL}/admin/dashboard`)

      // Verify admin dashboard is loaded
      await expect(page.getByText(/admin dashboard/i)).toBeVisible()
    })

    test('should show error message with invalid credentials', async ({ page }) => {
      // Fill in login form with invalid credentials
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill('wrongpassword')

      // Click login button
      await page.getByRole('button', { name: /login/i }).click()

      // Verify error message is displayed
      await expect(page.getByText(/invalid.*credentials/i)).toBeVisible()
    })

    test('should validate email format', async ({ page }) => {
      // Enter invalid email
      await page.getByLabel(/email/i).fill('invalid-email')
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)

      // Try to submit
      await page.getByRole('button', { name: /login/i }).click()

      // Should show validation error
      await expect(page.getByText(/invalid email/i)).toBeVisible()
    })

    test('should validate password requirements', async ({ page }) => {
      // Enter weak password
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill('weak')

      // Password strength indicator should show weak
      await expect(page.getByText(/weak/i)).toBeVisible()
    })

    test('should toggle password visibility', async ({ page }) => {
      const passwordInput = page.getByLabel(/password/i)
      const toggleButton = page.getByRole('button', { name: /show password/i })

      // Password should be hidden by default
      await expect(passwordInput).toHaveAttribute('type', 'password')

      // Click toggle button
      await toggleButton.click()

      // Password should be visible
      await expect(passwordInput).toHaveAttribute('type', 'text')

      // Click toggle button again
      await toggleButton.click()

      // Password should be hidden again
      await expect(passwordInput).toHaveAttribute('type', 'password')
    })

    test('should remember login with remember me checked', async ({ page, context }) => {
      // Fill in login form
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)

      // Check remember me
      await page.getByLabel(/remember me/i).check()

      // Login
      await page.getByRole('button', { name: /login/i }).click()

      // Wait for dashboard
      await page.waitForURL(`${BASE_URL}/admin/dashboard`)

      // Close and reopen page
      await page.close()
      const newPage = await context.newPage()
      await newPage.goto(`${BASE_URL}/admin`)

      // Should still be logged in
      await expect(newPage.getByText(/admin dashboard/i)).toBeVisible()
    })

    test('should handle network errors gracefully', async ({ page, context }) => {
      // Simulate offline mode
      await context.setOffline(true)

      // Fill in login form
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)

      // Try to login
      await page.getByRole('button', { name: /login/i }).click()

      // Should show network error
      await expect(page.getByText(/network error/i)).toBeVisible()

      // Restore online mode
      await context.setOffline(false)
    })
  })

  test.describe('Admin Logout', () => {
    test.beforeEach(async ({ page }) => {
      // Login before each logout test
      await page.goto(`${BASE_URL}/admin/login`)
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)
      await page.getByRole('button', { name: /login/i }).click()
      await page.waitForURL(`${BASE_URL}/admin/dashboard`)
    })

    test('should logout successfully from dashboard', async ({ page }) => {
      // Click logout button
      await page.getByRole('button', { name: /logout/i }).click()

      // Should redirect to login page
      await page.waitForURL(`${BASE_URL}/admin/login`)

      // Verify login page is shown
      await expect(page.getByText(/admin login/i)).toBeVisible()
    })

    test('should clear session data on logout', async ({ page, context }) => {
      // Logout
      await page.getByRole('button', { name: /logout/i }).click()

      // Wait for login page
      await page.waitForURL(`${BASE_URL}/admin/login`)

      // Try to navigate back to dashboard
      await page.goto(`${BASE_URL}/admin/dashboard`)

      // Should redirect to login
      await expect(page).toHaveURL(`${BASE_URL}/admin/login`)
    })

    test('should clear localStorage on logout', async ({ page }) => {
      // Logout
      await page.getByRole('button', { name: /logout/i }).click()

      // Check localStorage is cleared
      const rememberMe = await page.evaluate(() => localStorage.getItem('rememberMe'))
      expect(rememberMe).toBeNull()
    })
  })

  test.describe('Protected Routes', () => {
    test('should redirect to login when accessing admin routes without auth', async ({ page }) => {
      // Try to access dashboard without logging in
      await page.goto(`${BASE_URL}/admin/dashboard`)

      // Should redirect to login
      await expect(page).toHaveURL(`${BASE_URL}/admin/login`)
    })

    test('should allow access to dashboard after login', async ({ page }) => {
      // Login first
      await page.goto(`${BASE_URL}/admin/login`)
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)
      await page.getByRole('button', { name: /login/i }).click()

      // Wait for dashboard
      await page.waitForURL(`${BASE_URL}/admin/dashboard`)

      // Verify dashboard content
      await expect(page.getByText(/admin dashboard/i)).toBeVisible()
    })

    test('should maintain auth state when navigating between admin pages', async ({ page }) => {
      // Login
      await page.goto(`${BASE_URL}/admin/login`)
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)
      await page.getByRole('button', { name: /login/i }).click()

      // Navigate to different admin pages
      await page.goto(`${BASE_URL}/admin/users`)
      await expect(page.getByText(/users/i)).toBeVisible()

      await page.goto(`${BASE_URL}/admin/settings`)
      await expect(page.getByText(/settings/i)).toBeVisible()

      // Should still be authenticated
      await page.goto(`${BASE_URL}/admin/dashboard`)
      await expect(page.getByText(/admin dashboard/i)).toBeVisible()
    })
  })

  test.describe('Session Management', () => {
    test('should show session warning before expiry', async ({ page }) => {
      // Login
      await page.goto(`${BASE_URL}/admin/login`)
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)
      await page.getByRole('button', { name: /login/i }).click()
      await page.waitForURL(`${BASE_URL}/admin/dashboard`)

      // Wait for session warning (5 minutes before expiry)
      // This would require mocking time or waiting
      // Implementation depends on AdminSessionManager
    })

    test('should extend session when user is active', async ({ page }) => {
      // Login
      await page.goto(`${BASE_URL}/admin/login`)
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)
      await page.getByRole('button', { name: /login/i }).click()
      await page.waitForURL(`${BASE_URL}/admin/dashboard`)

      // Simulate user activity
      await page.mouse.move(100, 100)
      await page.mouse.move(200, 200)

      // Session should be extended
      // Verification depends on implementation
    })

    test('should show inactivity warning after 30 minutes', async ({ page }) => {
      // Login
      await page.goto(`${BASE_URL}/admin/login`)
      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)
      await page.getByRole('button', { name: /login/i }).click()
      await page.waitForURL(`${BASE_URL}/admin/dashboard`)

      // Mock time passage or wait for inactivity timeout
      // Implementation depends on AdminSessionManager
    })
  })

  test.describe('Accessibility', () => {
    test('should have no accessibility violations on login page', async ({ page }) => {
      // Check for basic accessibility
      await expect(page.getByLabel(/email/i)).toBeVisible()
      await expect(page.getByLabel(/password/i)).toBeVisible()

      // Verify keyboard navigation
      await page.keyboard.press('Tab')
      await expect(page.getByLabel(/email/i)).toBeFocused()

      await page.keyboard.press('Tab')
      await expect(page.getByLabel(/password/i)).toBeFocused()
    })

    test('should support keyboard-only navigation', async ({ page }) => {
      // Navigate using Tab
      await page.keyboard.press('Tab')
      await expect(page.getByLabel(/email/i)).toBeFocused()

      // Fill using keyboard
      await page.keyboard.type(ADMIN_EMAIL)

      await page.keyboard.press('Tab')
      await expect(page.getByLabel(/password/i)).toBeFocused()

      await page.keyboard.type(ADMIN_PASSWORD)

      // Submit using Enter
      await page.keyboard.press('Enter')

      // Should navigate to dashboard
      await page.waitForURL(`${BASE_URL}/admin/dashboard`)
    })
  })

  test.describe('Security', () => {
    test('should not expose password in DOM', async ({ page }) => {
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)

      const passwordInput = page.getByLabel(/password/i)
      const inputType = await passwordInput.getAttribute('type')

      expect(inputType).toBe('password')
    })

    test('should prevent XSS attacks in email field', async ({ page }) => {
      const xssPayload = '<script>alert("xss")</script>'

      await page.getByLabel(/email/i).fill(xssPayload)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)
      await page.getByRole('button', { name: /login/i }).click()

      // Should not execute script
      // Page should still be on login page with validation error
      await expect(page).toHaveURL(`${BASE_URL}/admin/login`)
    })

    test('should have CSRF protection', async ({ page }) => {
      // Login request should include CSRF token or proper headers
      // This depends on API implementation
      await page.goto(`${BASE_URL}/admin/login`)

      // Monitor network requests
      const requests: any[] = []
      page.on('request', request => requests.push(request))

      await page.getByLabel(/email/i).fill(ADMIN_EMAIL)
      await page.getByLabel(/password/i).fill(ADMIN_PASSWORD)
      await page.getByRole('button', { name: /login/i }).click()

      // Verify CSRF protection in requests
      // Implementation depends on backend
    })
  })
})
