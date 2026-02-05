import { test, expect, Page } from '@playwright/test'

const ADMIN_CREDENTIALS = {
  email: 'admin@test.com',
  password: 'Test123!@#'
}

const sampleFailures = {
  data: [
    {
      saga_id: '11111111-1111-1111-1111-111111111111',
      patient_id: '22222222-2222-2222-2222-222222222222',
      patient_name: 'Maria Silva',
      timestamp: new Date().toISOString(),
      error_details: 'FK constraint violation',
      failed_steps: [{ step: 1, error: 'FK constraint violation' }],
      status: 'FAILED'
    }
  ],
  total: 1,
  page: 1,
  limit: 20,
  pages: 1
}

async function loginAsAdmin(page: Page) {
  await page.goto('/admin/login')
  await page.fill('#email', ADMIN_CREDENTIALS.email)
  await page.fill('#password', ADMIN_CREDENTIALS.password)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await page.waitForURL('**/admin**')
}

test.describe('Admin Compensation Failures', () => {
  test('compensation failures page loads', async ({ page }) => {
    await page.route('**/api/v2/admin/compensation-failures**', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(sampleFailures)
        })
        return
      }
      await route.fallback()
    })

    await loginAsAdmin(page)
    await page.goto('/admin/system/compensation')

    await expect(page.getByTestId('compensation-failures-table')).toBeVisible()
    await expect(page.getByText('Maria Silva')).toBeVisible()
  })

  test('retry compensation success', async ({ page }) => {
    await page.route('**/api/v2/admin/compensation-failures**', async (route) => {
      const method = route.request().method()
      if (method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(sampleFailures)
        })
        return
      }
      if (method === 'POST' && route.request().url().includes('/retry')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, message: 'Compensation retry completed' })
        })
        return
      }
      await route.fallback()
    })

    await loginAsAdmin(page)
    await page.goto('/admin/system/compensation')

    await page.getByTestId(`retry-compensation-${sampleFailures.data[0].saga_id}`).click()
    await expect(page.getByText('Retry iniciado')).toBeVisible()
  })

  test('cleanup compensation with confirmation', async ({ page }) => {
    await page.route('**/api/v2/admin/compensation-failures**', async (route) => {
      const method = route.request().method()
      if (method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(sampleFailures)
        })
        return
      }
      if (method === 'POST' && route.request().url().includes('/cleanup')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ message: 'Compensation cleanup completed' })
        })
        return
      }
      await route.fallback()
    })

    await loginAsAdmin(page)
    await page.goto('/admin/system/compensation')

    await page.getByTestId(`cleanup-compensation-${sampleFailures.data[0].saga_id}`).click()
    await expect(page.getByText('Confirm cleanup?')).toBeVisible()
    await page.getByRole('button', { name: 'Confirmar' }).click()
    await expect(page.getByText('Cleanup concluido')).toBeVisible()
  })

  test('navigation badge shows count', async ({ page }) => {
    await page.route('**/api/v2/admin/compensation-failures**', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...sampleFailures,
            total: 3
          })
        })
        return
      }
      await route.fallback()
    })

    await loginAsAdmin(page)
    await page.goto('/admin/system/compensation')

    const badge = page.getByTestId('compensation-failures-badge')
    await expect(badge).toBeVisible()
    await expect(badge).toHaveText('3')
  })
})
