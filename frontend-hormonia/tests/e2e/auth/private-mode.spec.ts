import { test, expect } from '@playwright/test'

test.describe('Private Mode Auth Resilience', () => {
    // Simulate private mode by mocking localStorage failure
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            const mockStorage = {
                getItem: () => null, // Reads might work or return null
                setItem: () => {
                    // Private mode typically allows writing but calls might flake or throw
                    // or in some browsers (like legacy Safari or specific settings) it throws
                    // We simulate the worst case: strict blocking
                    throw new DOMException('The quota has been exceeded.', 'QuotaExceededError')
                },
                removeItem: () => {
                    throw new DOMException('The operation is insecure.', 'SecurityError')
                },
                length: 0,
                key: () => null,
                clear: () => { }
            }

            // Override localStorage
            Object.defineProperty(window, 'localStorage', {
                value: mockStorage,
                writable: true,
                configurable: true
            })
        })
    })

    test('should allow login despite localStorage failures', async ({ page }) => {
        await page.goto('/login')

        // Fill login form
        await page.getByLabel('Email').fill('admin@hormonia.com.br')
        await page.getByLabel('Senha').fill('Admin123!') // Assuming default dev credentials
        await page.getByRole('button', { name: 'Entrar' }).click()

        // Should redirect to dashboard
        await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 })

        // Check that we are logged in (user menu visible)
        await expect(page.getByRole('button', { name: /Marta Silva/i })).toBeVisible({ timeout: 10000 })

        // Verify NO error toast about localStorage
        // We expect "Login realizado com sucesso" or no error toast
        const errorToast = page.getByText('Erro ao fazer login')
        await expect(errorToast).not.toBeVisible()
    })

    test('should persist session via cookies on navigation', async ({ page }) => {
        await page.goto('/login')
        await page.getByLabel('Email').fill('admin@hormonia.com.br')
        await page.getByLabel('Senha').fill('Admin123!')
        await page.getByRole('button', { name: 'Entrar' }).click()

        await expect(page).toHaveURL(/\/dashboard/)

        // Navigate to another page
        await page.goto('/dashboard/patients')
        await expect(page).toHaveURL(/\/patients/)

        // Reload page
        await page.reload()

        // Should still be authenticated (cookie-based)
        await expect(page.getByRole('button', { name: /Marta Silva/i })).toBeVisible()
        await expect(page).not.toHaveURL(/\/login/)
    })
})
