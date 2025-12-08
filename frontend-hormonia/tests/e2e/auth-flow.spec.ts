import { test, expect, Page } from '@playwright/test'

// Test data
const testUser = {
  email: 'test@clinica.com',
  password: 'TestPassword123!',
  name: 'Test User'
}

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Start from the login page
    await page.goto('/login')
  })

  test.describe('Login', () => {
    test('should display login form', async ({ page }) => {
      await expect(page).toHaveTitle(/Clínica Oncológica/)
      await expect(page.getByRole('heading', { name: /entrar/i })).toBeVisible()

      await expect(page.getByLabel(/email/i)).toBeVisible()
      await expect(page.getByLabel(/senha/i)).toBeVisible()
      await expect(page.getByRole('button', { name: /entrar/i })).toBeVisible()
    })

    test('should show validation errors for empty fields', async ({ page }) => {
      await page.getByRole('button', { name: /entrar/i }).click()

      await expect(page.getByText(/email é obrigatório/i)).toBeVisible()
      await expect(page.getByText(/senha é obrigatória/i)).toBeVisible()
    })

    test('should show error for invalid email format', async ({ page }) => {
      await page.getByLabel(/email/i).fill('invalid-email')
      await page.getByLabel(/senha/i).fill('password')
      await page.getByRole('button', { name: /entrar/i }).click()

      await expect(page.getByText(/email inválido/i)).toBeVisible()
    })

    test('should show error for invalid credentials', async ({ page }) => {
      await page.getByLabel(/email/i).fill('wrong@example.com')
      await page.getByLabel(/senha/i).fill('wrongpassword')
      await page.getByRole('button', { name: /entrar/i }).click()

      // Wait for error message
      await expect(page.getByText(/credenciais inválidas/i).or(
        page.getByText(/email ou senha incorretos/i)
      )).toBeVisible({ timeout: 5000 })
    })

    test('should login successfully with valid credentials', async ({ page }) => {
      // Fill login form
      await page.getByLabel(/email/i).fill(testUser.email)
      await page.getByLabel(/senha/i).fill(testUser.password)

      // Submit form
      await page.getByRole('button', { name: /entrar/i }).click()

      // Should redirect to dashboard after successful login
      await expect(page).toHaveURL('/dashboard', { timeout: 10000 })
      await expect(page.getByText(/dashboard/i).or(
        page.getByText(/painel/i)
      )).toBeVisible()
    })

    test('should show loading state during login', async ({ page }) => {
      await page.getByLabel(/email/i).fill(testUser.email)
      await page.getByLabel(/senha/i).fill(testUser.password)

      await page.getByRole('button', { name: /entrar/i }).click()

      // Should show loading indicator
      await expect(page.getByTestId('loading-spinner').or(
        page.getByRole('button', { name: /carregando/i })
      )).toBeVisible()
    })

    test('should handle keyboard navigation', async ({ page }) => {
      // Navigate using Tab
      await page.keyboard.press('Tab')
      await expect(page.getByLabel(/email/i)).toBeFocused()

      await page.keyboard.press('Tab')
      await expect(page.getByLabel(/senha/i)).toBeFocused()

      await page.keyboard.press('Tab')
      await expect(page.getByRole('button', { name: /entrar/i })).toBeFocused()

      // Should be able to submit with Enter
      await page.getByLabel(/email/i).fill(testUser.email)
      await page.getByLabel(/senha/i).fill(testUser.password)
      await page.keyboard.press('Enter')

      // Should redirect to dashboard
      await expect(page).toHaveURL('/dashboard', { timeout: 10000 })
    })
  })

  test.describe('Protected Routes', () => {
    test('should redirect to login when accessing protected route while logged out', async ({ page }) => {
      await page.goto('/dashboard')

      // Should redirect to login
      await expect(page).toHaveURL(/.*\/login/, { timeout: 5000 })
      await expect(page.getByRole('heading', { name: /entrar/i })).toBeVisible()
    })

    test('should redirect to login when accessing patients page while logged out', async ({ page }) => {
      await page.goto('/patients')

      // Should redirect to login
      await expect(page).toHaveURL(/.*\/login/, { timeout: 5000 })
    })

    test('should redirect back to intended page after login', async ({ page }) => {
      // Try to access protected route
      await page.goto('/patients')

      // Should redirect to login
      await expect(page).toHaveURL(/.*\/login/, { timeout: 5000 })

      // Login
      await page.getByLabel(/email/i).fill(testUser.email)
      await page.getByLabel(/senha/i).fill(testUser.password)
      await page.getByRole('button', { name: /entrar/i }).click()

      // Should redirect back to intended page
      await expect(page).toHaveURL('/patients', { timeout: 10000 })
    })
  })

  test.describe('Logout', () => {
    test.beforeEach(async ({ page }) => {
      // Login first
      await loginUser(page, testUser.email, testUser.password)
    })

    test('should logout successfully', async ({ page }) => {
      // Look for logout button (could be in header or dropdown)
      const logoutButton = page.getByRole('button', { name: /sair/i }).or(
        page.getByRole('menuitem', { name: /sair/i })
      )

      // If logout is in a dropdown, open it first
      const userMenu = page.getByTestId('user-menu').or(
        page.getByRole('button', { name: testUser.name }).or(
          page.getByText(testUser.email)
        )
      )

      if (await userMenu.count() > 0) {
        await userMenu.click()
      }

      await logoutButton.click()

      // Should redirect to login
      await expect(page).toHaveURL(/.*\/login/, { timeout: 5000 })
      await expect(page.getByRole('heading', { name: /entrar/i })).toBeVisible()
    })

    test('should clear session on logout', async ({ page }) => {
      // Logout
      const userMenu = page.getByTestId('user-menu').or(
        page.getByRole('button', { name: testUser.name }).or(
          page.getByText(testUser.email)
        )
      )

      if (await userMenu.count() > 0) {
        await userMenu.click()
      }

      await page.getByRole('button', { name: /sair/i }).or(
        page.getByRole('menuitem', { name: /sair/i })
      ).click()

      // Try to access protected route
      await page.goto('/dashboard')

      // Should redirect to login (session cleared)
      await expect(page).toHaveURL(/.*\/login/, { timeout: 5000 })
    })
  })

  test.describe('Session Persistence', () => {
    test('should persist session across page reloads', async ({ page }) => {
      // Login
      await loginUser(page, testUser.email, testUser.password)

      // Reload page
      await page.reload()

      // Should still be logged in
      await expect(page).toHaveURL('/dashboard')
      await expect(page.getByText(/dashboard/i).or(
        page.getByText(/painel/i)
      )).toBeVisible()
    })

    test('should persist session across browser tabs', async ({ context, page }) => {
      // Login in first tab
      await loginUser(page, testUser.email, testUser.password)

      // Open new tab
      const newTab = await context.newPage()
      await newTab.goto('/dashboard')

      // Should be logged in in new tab
      await expect(newTab).toHaveURL('/dashboard')
      await expect(newTab.getByText(/dashboard/i).or(
        newTab.getByText(/painel/i)
      )).toBeVisible()

      await newTab.close()
    })
  })

  test.describe('Form Validation', () => {
    test('should validate email format', async ({ page }) => {
      const invalidEmails = ['invalid', '@example.com', 'test@', 'test.com']

      for (const email of invalidEmails) {
        await page.getByLabel(/email/i).fill(email)
        await page.getByLabel(/senha/i).fill('password')
        await page.getByRole('button', { name: /entrar/i }).click()

        await expect(page.getByText(/email inválido/i).or(
          page.getByText(/formato de email inválido/i)
        )).toBeVisible()

        // Clear form for next iteration
        await page.getByLabel(/email/i).clear()
      }
    })

    test('should validate password requirements', async ({ page }) => {
      await page.getByLabel(/email/i).fill(testUser.email)
      await page.getByLabel(/senha/i).fill('123') // Too short
      await page.getByRole('button', { name: /entrar/i }).click()

      await expect(page.getByText(/senha muito curta/i).or(
        page.getByText(/mínimo de/i)
      )).toBeVisible()
    })

    test('should clear validation errors when corrected', async ({ page }) => {
      // Trigger validation error
      await page.getByRole('button', { name: /entrar/i }).click()
      await expect(page.getByText(/email é obrigatório/i)).toBeVisible()

      // Fix error
      await page.getByLabel(/email/i).fill(testUser.email)

      // Error should disappear
      await expect(page.getByText(/email é obrigatório/i)).not.toBeVisible()
    })
  })

  test.describe('Accessibility', () => {
    test('should have proper labels and ARIA attributes', async ({ page }) => {
      // Check form labels
      await expect(page.getByLabel(/email/i)).toHaveAttribute('type', 'email')
      await expect(page.getByLabel(/senha/i)).toHaveAttribute('type', 'password')

      // Check button is properly labeled
      const loginButton = page.getByRole('button', { name: /entrar/i })
      await expect(loginButton).toBeVisible()
      await expect(loginButton).toBeEnabled()
    })

    test('should have proper focus management', async ({ page }) => {
      // First focusable element should be email input
      await page.keyboard.press('Tab')
      await expect(page.getByLabel(/email/i)).toBeFocused()
    })

    test('should announce validation errors to screen readers', async ({ page }) => {
      await page.getByRole('button', { name: /entrar/i }).click()

      // Error messages should be associated with inputs
      const emailInput = page.getByLabel(/email/i)
      const emailError = page.getByText(/email é obrigatório/i)

      await expect(emailError).toHaveAttribute('role', 'alert')
    })
  })
})

// Helper function to login
async function loginUser(page: Page, email: string, password: string) {
  if (page.url().includes('/login')) {
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/senha/i).fill(password)
    await page.getByRole('button', { name: /entrar/i }).click()

    // Wait for redirect to dashboard
    await expect(page).toHaveURL('/dashboard', { timeout: 10000 })
  } else {
    // Already logged in or navigate to login first
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/senha/i).fill(password)
    await page.getByRole('button', { name: /entrar/i }).click()
    await expect(page).toHaveURL('/dashboard', { timeout: 10000 })
  }
}