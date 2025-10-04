/**
 * End-to-End tests for Login Flow
 *
 * Tests complete user authentication journey including state persistence
 */
import { test, expect } from '@playwright/test'

// Configuration
const BASE_URL = process.env.VITE_APP_URL || 'http://localhost:5173'
const TEST_EMAIL = 'test@example.com'
const TEST_PASSWORD = 'Test123!@#'

test.describe('Login Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any existing auth state
    await page.goto(BASE_URL)
    await page.evaluate(() => localStorage.clear())
    await page.evaluate(() => sessionStorage.clear())
  })

  test('should display login form correctly', async ({ page }) => {
    // Navigate to login page
    await page.goto(`${BASE_URL}/login`)

    // Verify form elements are present
    await expect(page.locator('[name="email"]')).toBeVisible()
    await expect(page.locator('[name="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()

    // Verify title/heading
    await expect(page.locator('h1, h2').filter({ hasText: /login|entrar/i })).toBeVisible()
  })

  test('should show validation errors for empty fields', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)

    // Try submitting without filling fields
    await page.click('button[type="submit"]')

    // Should show validation errors (browser or custom)
    const emailInput = page.locator('[name="email"]')
    const passwordInput = page.locator('[name="password"]')

    await expect(emailInput).toHaveAttribute('required', '')
    await expect(passwordInput).toHaveAttribute('required', '')
  })

  test('should show error for invalid email format', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)

    // Enter invalid email
    await page.fill('[name="email"]', 'invalid-email')
    await page.fill('[name="password"]', 'password123')
    await page.click('button[type="submit"]')

    // Should show email validation error (browser native or custom)
    const emailInput = page.locator('[name="email"]')
    const validationMessage = await emailInput.evaluate((el: HTMLInputElement) => el.validationMessage)
    expect(validationMessage).toBeTruthy()
  })

  test('should login successfully with valid credentials', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)

    // Fill login form
    await page.fill('[name="email"]', TEST_EMAIL)
    await page.fill('[name="password"]', TEST_PASSWORD)

    // Submit form
    await page.click('button[type="submit"]')

    // Should redirect to dashboard
    await page.waitForURL('**/dashboard', { timeout: 5000 })

    // Verify authenticated state - user menu or profile element
    const userMenu = page.locator('[data-testid="user-menu"]')
      .or(page.locator('[aria-label*="user" i]'))
      .or(page.locator('text=/perfil|conta/i'))

    await expect(userMenu.first()).toBeVisible({ timeout: 3000 })
  })

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)

    // Enter wrong password
    await page.fill('[name="email"]', TEST_EMAIL)
    await page.fill('[name="password"]', 'wrong-password')
    await page.click('button[type="submit"]')

    // Should show error message
    const errorMessage = page.locator('text=/credenciais inválidas|senha incorreta|erro/i')
    await expect(errorMessage.first()).toBeVisible({ timeout: 5000 })

    // Should remain on login page
    expect(page.url()).toContain('login')
  })

  test('should persist auth state on page reload', async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/login`)
    await page.fill('[name="email"]', TEST_EMAIL)
    await page.fill('[name="password"]', TEST_PASSWORD)
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard')

    // Reload page
    await page.reload()
    await page.waitForLoadState('networkidle')

    // Should still be authenticated
    const userMenu = page.locator('[data-testid="user-menu"]')
      .or(page.locator('[aria-label*="user" i]'))
      .or(page.locator('text=/perfil|conta/i'))

    await expect(userMenu.first()).toBeVisible()
    expect(page.url()).toContain('dashboard')
  })

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/login`)
    await page.fill('[name="email"]', TEST_EMAIL)
    await page.fill('[name="password"]', TEST_PASSWORD)
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard')

    // Find and click logout button
    const logoutButton = page.locator('button:has-text("Sair")')
      .or(page.locator('a:has-text("Sair")'))
      .or(page.locator('[data-testid="logout"]'))

    await logoutButton.first().click()

    // Should redirect to login page
    await page.waitForURL('**/login', { timeout: 5000 })

    // Verify logged out state
    await expect(page.locator('[name="email"]')).toBeVisible()
  })

  test('should redirect to login if accessing protected route while logged out', async ({ page }) => {
    // Try accessing dashboard without logging in
    await page.goto(`${BASE_URL}/dashboard`)

    // Should redirect to login
    await page.waitForURL('**/login', { timeout: 5000 })
    await expect(page.locator('[name="email"]')).toBeVisible()
  })

  test('should handle password reset flow', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)

    // Find password reset link
    const resetLink = page.locator('a:has-text("Esqueceu")')
      .or(page.locator('a:has-text("Recuperar senha")'))
      .or(page.locator('[href*="reset"]'))

    if (await resetLink.count() > 0) {
      await resetLink.first().click()

      // Should navigate to password reset page
      await expect(page.locator('[name="email"]')).toBeVisible()
      await expect(page.locator('button[type="submit"]')).toBeVisible()
    }
  })

  test('should toggle password visibility', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)

    const passwordInput = page.locator('[name="password"]')
    const toggleButton = page.locator('button[aria-label*="show" i]')
      .or(page.locator('button[aria-label*="toggle" i]'))
      .or(page.locator('[data-testid="toggle-password"]'))

    if (await toggleButton.count() > 0) {
      // Initially password type
      await expect(passwordInput).toHaveAttribute('type', 'password')

      // Click toggle
      await toggleButton.first().click()

      // Should change to text
      await expect(passwordInput).toHaveAttribute('type', 'text')

      // Click again
      await toggleButton.first().click()

      // Should change back to password
      await expect(passwordInput).toHaveAttribute('type', 'password')
    }
  })
})

test.describe('Login Security', () => {
  test('should prevent brute force with rate limiting', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)

    // Attempt multiple failed logins
    for (let i = 0; i < 5; i++) {
      await page.fill('[name="email"]', TEST_EMAIL)
      await page.fill('[name="password"]', `wrong-password-${i}`)
      await page.click('button[type="submit"]')
      await page.waitForTimeout(500)
    }

    // After multiple attempts, should show rate limit error or disable form
    const submitButton = page.locator('button[type="submit"]')
    const isDisabled = await submitButton.isDisabled()
    const rateLimitMessage = page.locator('text=/muitas tentativas|rate limit|aguarde/i')

    // Either button is disabled or rate limit message is shown
    expect(isDisabled || await rateLimitMessage.count() > 0).toBeTruthy()
  })

  test('should not expose whether user exists', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)

    // Try with non-existent email
    await page.fill('[name="email"]', 'nonexistent@example.com')
    await page.fill('[name="password"]', 'password123')
    await page.click('button[type="submit"]')

    const errorMessage1 = await page.locator('[role="alert"], .error-message').textContent()

    // Clear and try with wrong password for existing user
    await page.fill('[name="email"]', TEST_EMAIL)
    await page.fill('[name="password"]', 'wrong-password')
    await page.click('button[type="submit"]')

    const errorMessage2 = await page.locator('[role="alert"], .error-message').textContent()

    // Both errors should be generic (not revealing if user exists)
    expect(errorMessage1?.toLowerCase()).toContain('credenciais')
    expect(errorMessage2?.toLowerCase()).toContain('credenciais')
  })
})
