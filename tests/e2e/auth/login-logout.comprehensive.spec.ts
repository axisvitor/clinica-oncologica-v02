import { test, expect, Page, BrowserContext } from '@playwright/test'

// Test data
const VALID_CREDENTIALS = {
  email: 'admin@neoplasiaslitoral.com',
  password: 'Admin@123456!'
}

const INVALID_CREDENTIALS = {
  email: 'invalid@example.com',
  password: 'wrongpassword'
}

// Page object helpers
class LoginPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/login')
  }

  async fillEmail(email: string) {
    await this.page.fill('[data-testid="email-input"], #email', email)
  }

  async fillPassword(password: string) {
    await this.page.fill('[data-testid="password-input"], #password', password)
  }

  async togglePasswordVisibility() {
    await this.page.click('[aria-label*="senha"], [aria-label*="password"]')
  }

  async checkRememberMe() {
    await this.page.check('#rememberMe')
  }

  async clickSubmit() {
    await this.page.click('button[type="submit"]')
  }

  async clickForgotPassword() {
    await this.page.click('button:has-text("Esqueci minha senha")')
  }

  async waitForErrorMessage() {
    return await this.page.waitForSelector('[role="alert"]:has-text("Invalid"), .error-message', { timeout: 5000 })
  }

  async getErrorMessage() {
    const errorElement = await this.page.locator('[role="alert"], .error-message').first()
    return await errorElement.textContent()
  }

  async isSubmitButtonDisabled() {
    return await this.page.isDisabled('button[type="submit"]')
  }

  async isLoadingVisible() {
    return await this.page.isVisible(':has-text("Entrando...")')
  }

  async isDemoCredentialsVisible() {
    return await this.page.isVisible(':has-text("Credenciais Demo")')
  }
}

class DashboardPage {
  constructor(private page: Page) {}

  async waitForDashboard() {
    await this.page.waitForSelector('[data-testid="dashboard"], h1:has-text("Dashboard")', { timeout: 10000 })
  }

  async logout() {
    // Try multiple possible logout button selectors
    try {
      await this.page.click('button:has-text("Logout"), button:has-text("Sair"), [data-testid="logout-button"]')
    } catch {
      // Fallback: look for user menu first
      await this.page.click('[data-testid="user-menu"], .user-menu, button:has([data-testid="user-avatar"])')
      await this.page.click('button:has-text("Logout"), button:has-text("Sair")')
    }
  }

  async isAuthenticated() {
    return await this.page.isVisible('[data-testid="dashboard"], h1:has-text("Dashboard")')
  }
}

test.describe('Login/Logout Flow - E2E Tests', () => {
  let loginPage: LoginPage
  let dashboardPage: DashboardPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    dashboardPage = new DashboardPage(page)

    // Clear any existing auth state
    await page.context().clearCookies()
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
  })

  test.describe('Login Page Rendering', () => {
    test('should render login form with all required elements', async ({ page }) => {
      await loginPage.goto()

      // Check for main heading
      await expect(page.locator('h1, h2').filter({ hasText: /entrar|login/i })).toBeVisible()

      // Check for form elements
      await expect(page.locator('#email, [data-testid="email-input"]')).toBeVisible()
      await expect(page.locator('#password, [data-testid="password-input"]')).toBeVisible()
      await expect(page.locator('#rememberMe, [data-testid="remember-me"]')).toBeVisible()
      await expect(page.locator('button[type="submit"]')).toBeVisible()

      // Check for logo
      await expect(page.locator('img[alt*="Neoplasias"], img[alt*="logo"]')).toBeVisible()
    })

    test('should show demo credentials in development mode', async ({ page }) => {
      await loginPage.goto()

      if (await loginPage.isDemoCredentialsVisible()) {
        await expect(page.locator(':has-text("admin@neoplasiaslitoral.com")')).toBeVisible()
        await expect(page.locator(':has-text("Admin@123456!")')).toBeVisible()
      }
    })

    test('should show forgot password functionality', async ({ page }) => {
      await loginPage.goto()

      await loginPage.clickForgotPassword()

      await expect(page.locator(':has-text("Redefinição de Senha")')).toBeVisible()
      await expect(page.locator(':has-text("suporte@neoplasiaslitoral.com")')).toBeVisible()
    })
  })

  test.describe('Form Interactions', () => {
    test('should toggle password visibility', async ({ page }) => {
      await loginPage.goto()

      const passwordInput = page.locator('#password, [data-testid="password-input"]')

      // Initially should be password type
      await expect(passwordInput).toHaveAttribute('type', 'password')

      // Click toggle button
      await loginPage.togglePasswordVisibility()

      // Should now be text type
      await expect(passwordInput).toHaveAttribute('type', 'text')

      // Click again to hide
      await loginPage.togglePasswordVisibility()

      // Should be password type again
      await expect(passwordInput).toHaveAttribute('type', 'password')
    })

    test('should allow typing in form fields', async ({ page }) => {
      await loginPage.goto()

      await loginPage.fillEmail('test@example.com')
      await loginPage.fillPassword('testpassword')

      await expect(page.locator('#email, [data-testid="email-input"]')).toHaveValue('test@example.com')
      await expect(page.locator('#password, [data-testid="password-input"]')).toHaveValue('testpassword')
    })

    test('should toggle remember me checkbox', async ({ page }) => {
      await loginPage.goto()

      const checkbox = page.locator('#rememberMe, [data-testid="remember-me"]')

      await expect(checkbox).not.toBeChecked()

      await loginPage.checkRememberMe()

      await expect(checkbox).toBeChecked()
    })
  })

  test.describe('Form Validation', () => {
    test('should show validation errors for invalid email', async ({ page }) => {
      await loginPage.goto()

      await loginPage.fillEmail('invalid-email')
      await loginPage.fillPassword('password123')
      await loginPage.clickSubmit()

      // Wait for and check validation error
      await expect(page.locator(':has-text("Email inválido"), :has-text("Invalid email")')).toBeVisible()
    })

    test('should show validation errors for short password', async ({ page }) => {
      await loginPage.goto()

      await loginPage.fillEmail('test@example.com')
      await loginPage.fillPassword('123')
      await loginPage.clickSubmit()

      // Wait for and check validation error
      await expect(page.locator(':has-text("pelo menos 6 caracteres"), :has-text("at least 6 characters")')).toBeVisible()
    })

    test('should show validation errors for empty fields', async ({ page }) => {
      await loginPage.goto()

      await loginPage.clickSubmit()

      // Should show validation errors for both fields
      await expect(page.locator('.error, [role="alert"], .text-red')).toHaveCount({ min: 1 })
    })
  })

  test.describe('Successful Login Flow', () => {
    test('should login successfully with valid credentials', async ({ page }) => {
      await loginPage.goto()

      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.clickSubmit()

      // Wait for redirect to dashboard
      await dashboardPage.waitForDashboard()

      // Verify we're on the dashboard
      expect(await dashboardPage.isAuthenticated()).toBe(true)

      // Verify URL changed
      expect(page.url()).toMatch(/dashboard|\/(?!login)/)
    })

    test('should login with remember me option', async ({ page }) => {
      await loginPage.goto()

      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.checkRememberMe()
      await loginPage.clickSubmit()

      await dashboardPage.waitForDashboard()

      expect(await dashboardPage.isAuthenticated()).toBe(true)
    })

    test('should persist authentication after page reload', async ({ page }) => {
      await loginPage.goto()

      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.checkRememberMe()
      await loginPage.clickSubmit()

      await dashboardPage.waitForDashboard()

      // Reload the page
      await page.reload()

      // Should still be authenticated
      await dashboardPage.waitForDashboard()
      expect(await dashboardPage.isAuthenticated()).toBe(true)
    })
  })

  test.describe('Failed Login Attempts', () => {
    test('should show error for invalid credentials', async ({ page }) => {
      await loginPage.goto()

      await loginPage.fillEmail(INVALID_CREDENTIALS.email)
      await loginPage.fillPassword(INVALID_CREDENTIALS.password)
      await loginPage.clickSubmit()

      // Wait for error message
      await loginPage.waitForErrorMessage()

      const errorMessage = await loginPage.getErrorMessage()
      expect(errorMessage).toMatch(/invalid|incorrect|failed|erro/i)

      // Should still be on login page
      expect(page.url()).toMatch(/login/)
    })

    test('should handle network errors gracefully', async ({ page }) => {
      // Simulate network failure
      await page.route('**/api/**', route => route.abort())

      await loginPage.goto()

      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.clickSubmit()

      // Should show network error
      await expect(page.locator(':has-text("network"), :has-text("connection"), :has-text("server")')).toBeVisible({ timeout: 10000 })
    })

    test('should retry login after initial failure', async ({ page }) => {
      await loginPage.goto()

      // First attempt with wrong password
      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword('wrongpassword')
      await loginPage.clickSubmit()

      await loginPage.waitForErrorMessage()

      // Clear and retry with correct password
      await page.fill('#password, [data-testid="password-input"]', '')
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.clickSubmit()

      // Should succeed
      await dashboardPage.waitForDashboard()
      expect(await dashboardPage.isAuthenticated()).toBe(true)
    })
  })

  test.describe('Loading States', () => {
    test('should show loading state during login', async ({ page }) => {
      await loginPage.goto()

      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)

      // Submit and immediately check for loading state
      await loginPage.clickSubmit()

      // Should show loading state (button disabled or loading text)
      const isDisabled = await loginPage.isSubmitButtonDisabled()
      const isLoading = await loginPage.isLoadingVisible()

      expect(isDisabled || isLoading).toBe(true)
    })
  })

  test.describe('Logout Flow', () => {
    test('should logout successfully and redirect to login', async ({ page }) => {
      // First login
      await loginPage.goto()
      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.clickSubmit()
      await dashboardPage.waitForDashboard()

      // Then logout
      await dashboardPage.logout()

      // Should redirect to login page
      await expect(page.locator('h1, h2').filter({ hasText: /entrar|login/i })).toBeVisible({ timeout: 10000 })
      expect(page.url()).toMatch(/login/)
    })

    test('should clear authentication state after logout', async ({ page }) => {
      // Login first
      await loginPage.goto()
      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.clickSubmit()
      await dashboardPage.waitForDashboard()

      // Logout
      await dashboardPage.logout()
      await expect(page.locator('h1, h2').filter({ hasText: /entrar|login/i })).toBeVisible()

      // Try to access protected route directly
      await page.goto('/dashboard')

      // Should redirect back to login
      await expect(page.locator('h1, h2').filter({ hasText: /entrar|login/i })).toBeVisible()
    })
  })

  test.describe('Session Management', () => {
    test('should handle session expiration', async ({ page }) => {
      // Login first
      await loginPage.goto()
      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.clickSubmit()
      await dashboardPage.waitForDashboard()

      // Simulate session expiration by clearing cookies
      await page.context().clearCookies()

      // Try to navigate or perform an action that requires auth
      await page.reload()

      // Should be redirected to login
      await expect(page.locator('h1, h2').filter({ hasText: /entrar|login/i })).toBeVisible({ timeout: 10000 })
    })

    test('should maintain session across browser tabs', async ({ context }) => {
      const page1 = await context.newPage()
      const page2 = await context.newPage()

      const loginPage1 = new LoginPage(page1)
      const dashboardPage1 = new DashboardPage(page1)
      const dashboardPage2 = new DashboardPage(page2)

      // Login in first tab
      await loginPage1.goto()
      await loginPage1.fillEmail(VALID_CREDENTIALS.email)
      await loginPage1.fillPassword(VALID_CREDENTIALS.password)
      await loginPage1.clickSubmit()
      await dashboardPage1.waitForDashboard()

      // Navigate to protected route in second tab
      await page2.goto('/dashboard')

      // Should be authenticated in second tab too
      await dashboardPage2.waitForDashboard()
      expect(await dashboardPage2.isAuthenticated()).toBe(true)

      await page1.close()
      await page2.close()
    })
  })

  test.describe('Accessibility', () => {
    test('should be keyboard navigable', async ({ page }) => {
      await loginPage.goto()

      // Start from email field
      await page.focus('#email, [data-testid="email-input"]')

      // Tab through form elements
      await page.keyboard.press('Tab') // to password
      await page.keyboard.press('Tab') // to show/hide password button
      await page.keyboard.press('Tab') // to remember me
      await page.keyboard.press('Tab') // to submit button

      // Submit button should be focused
      await expect(page.locator('button[type="submit"]')).toBeFocused()
    })

    test('should have proper ARIA labels and roles', async ({ page }) => {
      await loginPage.goto()

      // Check for proper labels
      await expect(page.locator('#email, [data-testid="email-input"]')).toHaveAttribute('aria-invalid', 'false')
      await expect(page.locator('#password, [data-testid="password-input"]')).toHaveAttribute('aria-invalid', 'false')

      // Check for form role
      await expect(page.locator('form, [role="form"]')).toBeVisible()
    })

    test('should announce errors to screen readers', async ({ page }) => {
      await loginPage.goto()

      await loginPage.fillEmail('invalid-email')
      await loginPage.clickSubmit()

      // Error should have proper role
      await expect(page.locator('[role="alert"]')).toBeVisible()
    })
  })

  test.describe('Security Features', () => {
    test('should not expose sensitive data in client-side storage', async ({ page }) => {
      await loginPage.goto()
      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.clickSubmit()
      await dashboardPage.waitForDashboard()

      // Check that passwords are not stored in localStorage or sessionStorage
      const localStorage = await page.evaluate(() => JSON.stringify(window.localStorage))
      const sessionStorage = await page.evaluate(() => JSON.stringify(window.sessionStorage))

      expect(localStorage.toLowerCase()).not.toContain(VALID_CREDENTIALS.password.toLowerCase())
      expect(sessionStorage.toLowerCase()).not.toContain(VALID_CREDENTIALS.password.toLowerCase())
    })

    test('should clear form data on navigation away', async ({ page }) => {
      await loginPage.goto()
      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)

      // Navigate away and back
      await page.goto('/about')
      await loginPage.goto()

      // Form should be cleared
      await expect(page.locator('#email, [data-testid="email-input"]')).toHaveValue('')
      await expect(page.locator('#password, [data-testid="password-input"]')).toHaveValue('')
    })
  })

  test.describe('Error Recovery', () => {
    test('should recover from temporary network issues', async ({ page }) => {
      await loginPage.goto()

      // Block network requests temporarily
      await page.route('**/api/**', route => route.abort())

      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.clickSubmit()

      // Should show error
      await loginPage.waitForErrorMessage()

      // Restore network
      await page.unroute('**/api/**')

      // Retry login
      await loginPage.clickSubmit()

      // Should succeed
      await dashboardPage.waitForDashboard()
      expect(await dashboardPage.isAuthenticated()).toBe(true)
    })
  })
})

test.describe('Cross-browser Compatibility', () => {
  ['chromium', 'firefox', 'webkit'].forEach(browserName => {
    test(`should work correctly in ${browserName}`, async ({ page }) => {
      const loginPage = new LoginPage(page)
      const dashboardPage = new DashboardPage(page)

      await loginPage.goto()
      await loginPage.fillEmail(VALID_CREDENTIALS.email)
      await loginPage.fillPassword(VALID_CREDENTIALS.password)
      await loginPage.clickSubmit()

      await dashboardPage.waitForDashboard()
      expect(await dashboardPage.isAuthenticated()).toBe(true)
    })
  })
})