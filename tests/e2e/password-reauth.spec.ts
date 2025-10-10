/**
 * E2E Tests for Password Re-authentication Flow
 *
 * Tests the complete password change security flow:
 * 1. User attempts to change password
 * 2. System prompts for current password
 * 3. Current password is validated
 * 4. New password is set
 * 5. All sessions are invalidated
 * 6. User is forced to re-login
 */

import { test, expect } from '@playwright/test'

// Test data
const TEST_USER = {
  email: 'test-password-reauth@example.com',
  current_password: 'TestPassword123!',
  new_password: 'NewPassword456!',
  wrong_password: 'WrongPassword999!',
}

test.describe('Password Re-authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to login page
    await page.goto('/login')

    // Login with test user
    await page.fill('input[name="email"]', TEST_USER.email)
    await page.fill('input[name="password"]', TEST_USER.current_password)
    await page.click('button[type="submit"]')

    // Wait for successful login and navigation
    await expect(page).toHaveURL(/\/dashboard|\//, { timeout: 10000 })

    // Navigate to settings page
    await page.goto('/settings')
    await expect(page.getByText('Configurações')).toBeVisible()

    // Navigate to security tab
    await page.click('text=Segurança')
    await expect(page.getByText('Alterar Senha')).toBeVisible()
  })

  test('should require current password validation', async ({ page }) => {
    // Fill password change form
    await page.fill('input[name="current_password"]', TEST_USER.current_password)
    await page.fill('input[name="new_password"]', TEST_USER.new_password)
    await page.fill('input[name="confirm_password"]', TEST_USER.new_password)

    // Submit form
    await page.click('button:has-text("Alterar senha")')

    // Should show success message
    await expect(page.getByText(/senha alterada com sucesso/i)).toBeVisible({ timeout: 10000 })

    // Should redirect to login after 3 seconds
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 })

    // Should show reason parameter
    await expect(page).toHaveURL(/reason=password-changed/)
  })

  test('should reject wrong current password', async ({ page }) => {
    // Fill password change form with wrong current password
    await page.fill('input[name="current_password"]', TEST_USER.wrong_password)
    await page.fill('input[name="new_password"]', TEST_USER.new_password)
    await page.fill('input[name="confirm_password"]', TEST_USER.new_password)

    // Submit form
    await page.click('button:has-text("Alterar senha")')

    // Should show error message
    await expect(
      page.getByText(/senha atual incorreta/i)
    ).toBeVisible({ timeout: 5000 })

    // Should stay on settings page
    await expect(page).toHaveURL(/\/settings/)
  })

  test('should validate password confirmation match', async ({ page }) => {
    // Fill password change form with mismatched passwords
    await page.fill('input[name="current_password"]', TEST_USER.current_password)
    await page.fill('input[name="new_password"]', TEST_USER.new_password)
    await page.fill('input[name="confirm_password"]', TEST_USER.new_password + 'different')

    // Try to submit form
    await page.click('button:has-text("Alterar senha")')

    // Should show validation error
    await expect(
      page.getByText(/senhas não coincidem/i)
    ).toBeVisible()
  })

  test('should enforce minimum password length', async ({ page }) => {
    // Fill password change form with short password
    await page.fill('input[name="current_password"]', TEST_USER.current_password)
    await page.fill('input[name="new_password"]', '12345')
    await page.fill('input[name="confirm_password"]', '12345')

    // Try to submit form
    await page.click('button:has-text("Alterar senha")')

    // Should show validation error
    await expect(
      page.getByText(/senha deve ter pelo menos 6 caracteres/i)
    ).toBeVisible()
  })

  test('should invalidate all sessions after password change', async ({ page, context }) => {
    // Open second tab with same session
    const secondPage = await context.newPage()
    await secondPage.goto('/dashboard')
    await expect(secondPage.getByText(/dashboard|início/i)).toBeVisible()

    // Change password in first tab
    await page.fill('input[name="current_password"]', TEST_USER.current_password)
    await page.fill('input[name="new_password"]', TEST_USER.new_password)
    await page.fill('input[name="confirm_password"]', TEST_USER.new_password)
    await page.click('button:has-text("Alterar senha")')

    // Wait for password change
    await expect(page.getByText(/senha alterada com sucesso/i)).toBeVisible({ timeout: 10000 })

    // Second tab should be logged out or show session expired
    await secondPage.reload()
    await expect(secondPage).toHaveURL(/\/login/, { timeout: 5000 })
  })

  test('should show loading state during password change', async ({ page }) => {
    // Fill form
    await page.fill('input[name="current_password"]', TEST_USER.current_password)
    await page.fill('input[name="new_password"]', TEST_USER.new_password)
    await page.fill('input[name="confirm_password"]', TEST_USER.new_password)

    // Submit form
    const submitButton = page.locator('button:has-text("Alterar senha")')
    await submitButton.click()

    // Should show loading state
    await expect(submitButton).toBeDisabled()
    await expect(page.locator('svg.animate-spin')).toBeVisible()
  })

  test('should handle network errors gracefully', async ({ page, context }) => {
    // Simulate offline mode
    await context.setOffline(true)

    // Fill form
    await page.fill('input[name="current_password"]', TEST_USER.current_password)
    await page.fill('input[name="new_password"]', TEST_USER.new_password)
    await page.fill('input[name="confirm_password"]', TEST_USER.new_password)

    // Try to submit
    await page.click('button:has-text("Alterar senha")')

    // Should show network error
    await expect(
      page.getByText(/erro de conexão|verifique sua internet/i)
    ).toBeVisible({ timeout: 5000 })

    // Restore connection
    await context.setOffline(false)
  })

  test('should rate limit password change attempts', async ({ page }) => {
    // Attempt multiple password changes rapidly
    for (let i = 0; i < 4; i++) {
      await page.fill('input[name="current_password"]', TEST_USER.wrong_password)
      await page.fill('input[name="new_password"]', TEST_USER.new_password)
      await page.fill('input[name="confirm_password"]', TEST_USER.new_password)
      await page.click('button:has-text("Alterar senha")')
      await page.waitForTimeout(500)
    }

    // Should show rate limit error
    await expect(
      page.getByText(/muitas tentativas|aguarde/i)
    ).toBeVisible({ timeout: 5000 })
  })

  test('should clear form after successful password change', async ({ page }) => {
    // Change password
    await page.fill('input[name="current_password"]', TEST_USER.current_password)
    await page.fill('input[name="new_password"]', TEST_USER.new_password)
    await page.fill('input[name="confirm_password"]', TEST_USER.new_password)
    await page.click('button:has-text("Alterar senha")')

    // Wait for success
    await expect(page.getByText(/senha alterada com sucesso/i)).toBeVisible({ timeout: 10000 })

    // Form should be cleared (check before redirect)
    const currentPasswordInput = page.locator('input[name="current_password"]')
    await expect(currentPasswordInput).toHaveValue('')
  })
})

test.describe('Password Change Accessibility', () => {
  test('should be keyboard navigable', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[name="email"]', TEST_USER.email)
    await page.fill('input[name="password"]', TEST_USER.current_password)
    await page.keyboard.press('Enter')

    await page.goto('/settings')
    await page.click('text=Segurança')

    // Tab through form fields
    await page.keyboard.press('Tab')
    await page.keyboard.type(TEST_USER.current_password)
    await page.keyboard.press('Tab')
    await page.keyboard.type(TEST_USER.new_password)
    await page.keyboard.press('Tab')
    await page.keyboard.type(TEST_USER.new_password)
    await page.keyboard.press('Enter')

    // Should submit successfully
    await expect(page.getByText(/senha alterada com sucesso/i)).toBeVisible({ timeout: 10000 })
  })

  test('should have proper ARIA labels', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[name="email"]', TEST_USER.email)
    await page.fill('input[name="password"]', TEST_USER.current_password)
    await page.click('button[type="submit"]')

    await page.goto('/settings')
    await page.click('text=Segurança')

    // Check for proper labels
    await expect(page.locator('label:has-text("Senha atual")')).toBeVisible()
    await expect(page.locator('label:has-text("Nova senha")')).toBeVisible()
    await expect(page.locator('label:has-text("Confirmar nova senha")')).toBeVisible()
  })
})
