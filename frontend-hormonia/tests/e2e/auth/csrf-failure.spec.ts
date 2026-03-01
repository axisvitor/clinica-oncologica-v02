import { test, expect } from '@playwright/test'

test.describe('CSRF Failure Handling', () => {
    test('should show warning toast when CSRF initialization fails', async ({ page }) => {
        // Abort CSRF token request to simulate failure
        await page.route('**/auth/csrf-token', route => route.abort('failed'))

        await page.goto('/login')

        // Verify warning toast appears
        // We look for the title "Aviso de Segurança"
        const warningToast = page.getByText('Aviso de Segurança')
        await expect(warningToast).toBeVisible({ timeout: 10000 })

        // Verify descriptive text
        await expect(page.getByText('Algumas funcionalidades podem não funcionar corretamente')).toBeVisible()

        // App should still be usable (Login form visible)
        await expect(page.getByLabel('Email')).toBeVisible()
        await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
    })

    test('should allow login attempt even if CSRF init failed', async ({ page }) => {
        // Abort CSRF init
        await page.route('**/auth/csrf-token', route => route.abort('failed'))

        await page.goto('/login')

        // Wait for toast
        await expect(page.getByText('Aviso de Segurança')).toBeVisible()

        // Try to type in form (smoke test that UI is not blocked)
        await page.getByLabel('Email').fill('test@example.com')
        await expect(page.getByLabel('Email')).toHaveValue('test@example.com')
    })
})
