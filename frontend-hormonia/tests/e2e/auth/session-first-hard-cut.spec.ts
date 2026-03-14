import { test, expect } from '@playwright/test'

const seededStaff = {
  email: process.env.E2E_SESSION_FIRST_EMAIL,
  password: process.env.E2E_SESSION_FIRST_PASSWORD,
  rotatedPassword: process.env.E2E_SESSION_FIRST_ROTATED_PASSWORD,
  resetToken: process.env.E2E_SESSION_FIRST_RESET_TOKEN,
}

function requiredSeededFixtureNames() {
  const missing: string[] = []
  if (!seededStaff.email) missing.push('E2E_SESSION_FIRST_EMAIL')
  if (!seededStaff.password) missing.push('E2E_SESSION_FIRST_PASSWORD')
  if (!seededStaff.rotatedPassword) missing.push('E2E_SESSION_FIRST_ROTATED_PASSWORD')
  if (!seededStaff.resetToken) missing.push('E2E_SESSION_FIRST_RESET_TOKEN')
  return missing
}

type JsonResponse = {
  status: number
  ok: boolean
  data: Record<string, unknown>
}

async function proxiedJsonRequest(
  page: Parameters<Parameters<typeof test>[1]>[0]['page'],
  path: string,
  init?: RequestInit
): Promise<JsonResponse> {
  return page.evaluate(
    async ({ path, init }) => {
      const response = await fetch(path, {
        credentials: 'include',
        ...init,
        headers: {
          Accept: 'application/json',
          ...(init?.headers ?? {}),
        },
      })

      const data = (await response.json().catch(() => ({}))) as Record<string, unknown>

      return {
        status: response.status,
        ok: response.ok,
        data,
      }
    },
    {
      path,
      init,
    }
  )
}

async function deleteWithCsrf(
  page: Parameters<Parameters<typeof test>[1]>[0]['page'],
  path: string
): Promise<JsonResponse> {
  const csrfResponse = await proxiedJsonRequest(page, '/api/auth/csrf-token')
  expect(csrfResponse.ok).toBe(true)
  const csrfToken = csrfResponse.data['csrf_token']
  expect(typeof csrfToken).toBe('string')

  return proxiedJsonRequest(page, path, {
    method: 'DELETE',
    headers: {
      'X-CSRF-Token': String(csrfToken),
    },
  })
}

test.describe('session-first hard cut acceptance', () => {
  test.describe.configure({ mode: 'serial' })

  test.skip(({ browserName }) => browserName !== 'chromium', 'Local-stack proof runs once in Chromium')

  test.beforeEach(async ({ page }) => {
    expect(process.env.VITE_FIREBASE_API_KEY).toBeFalsy()
    expect(process.env.VITE_FIREBASE_PROJECT_ID).toBeFalsy()
    expect(process.env.VITE_FIREBASE_APP_ID).toBeFalsy()
    expect(process.env.VITE_FIREBASE_AUTH_DOMAIN).toBeFalsy()
    expect(process.env.FIREBASE_ADMIN_PROJECT_ID).toBeFalsy()
    expect(process.env.FIREBASE_ADMIN_CLIENT_EMAIL).toBeFalsy()

    await page.context().clearCookies()
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
  })

  test('covers config truth, login, restore, reset, password rotation, logout, and logout-all on a no-Firebase stack', async ({
    page,
  }) => {
    const missingFixtures = requiredSeededFixtureNames()
    test.skip(
      missingFixtures.length > 0,
      `Seeded auth fixtures missing: ${missingFixtures.join(', ')}`
    )

    const unexpectedFirebaseRequests: string[] = []
    page.on('request', (request) => {
      if (/\/auth\/firebase\/verify|firebase/i.test(request.url())) {
        unexpectedFirebaseRequests.push(`${request.method()} ${request.url()}`)
      }
    })

    const publicConfigResponse = await proxiedJsonRequest(page, '/api/system/config')
    expect(publicConfigResponse.ok).toBe(true)
    expect(JSON.stringify(publicConfigResponse.data).toLowerCase()).not.toContain('firebase')

    await page.getByLabel(/^email$/i).fill(seededStaff.email)
    await page.getByLabel(/^senha$/i).fill(seededStaff.password)
    await page.getByRole('button', { name: /^entrar$/i }).click()

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 20000 })

    await page.reload({ waitUntil: 'networkidle' })
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 20000 })

    await page.goto('/settings/security')
    await expect(page.getByRole('heading', { name: /alterar senha/i })).toBeVisible({
      timeout: 15000,
    })

    await page.goto('/auth/password/reset-request')
    await page.getByLabel(/^email$/i).fill(seededStaff.email)
    await page.getByRole('button', { name: /enviar link de recuperação/i }).click()
    const resetSuccessAlert = page
      .getByRole('alert')
      .filter({ hasText: /confira sua caixa de entrada/i })
    await expect(resetSuccessAlert).toBeVisible({ timeout: 15000 })
    await expect(resetSuccessAlert).toContainText(/se existir uma conta vinculada a este email/i)

    await page.goto(`/auth/password/reset-confirm?token=${seededStaff.resetToken}`)
    await page.getByLabel(/^nova senha$/i).fill(seededStaff.rotatedPassword)
    await page.getByLabel(/^confirmar senha$/i).fill(seededStaff.rotatedPassword)
    await page.getByRole('button', { name: /salvar nova senha/i }).click()
    await expect(page.getByText(/senha atualizada com sucesso/i)).toBeVisible({ timeout: 15000 })

    await page.goto('/login')
    await page.getByLabel(/^email$/i).fill(seededStaff.email)
    await page.getByLabel(/^senha$/i).fill(seededStaff.rotatedPassword)
    await page.getByRole('button', { name: /^entrar$/i }).click()
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 20000 })

    await page.goto('/settings/security')
    const passwordChangeRequest = page.waitForRequest(
      (request) =>
        request.url().includes('/api/v2/auth/password') && request.method() === 'PUT'
    )

    await page.getByLabel(/senha atual/i).fill(seededStaff.rotatedPassword)
    await page.getByLabel(/^nova senha$/i).fill(seededStaff.password)
    await page.getByLabel(/confirmar nova senha/i).fill(seededStaff.password)
    await page.getByRole('button', { name: /alterar senha/i }).click()

    const submittedPasswordChange = await passwordChangeRequest
    expect(submittedPasswordChange.postDataJSON()).toMatchObject({
      current_password: seededStaff.rotatedPassword,
      new_password: seededStaff.password,
    })

    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })

    await page.getByLabel(/^email$/i).fill(seededStaff.email)
    await page.getByLabel(/^senha$/i).fill(seededStaff.password)
    await page.getByRole('button', { name: /^entrar$/i }).click()
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 20000 })

    await page.getByRole('button', { name: /menu do usuario/i }).click()
    await page.getByRole('menuitem', { name: /sair/i }).click()
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })

    await page.getByLabel(/^email$/i).fill(seededStaff.email)
    await page.getByLabel(/^senha$/i).fill(seededStaff.password)
    await page.getByRole('button', { name: /^entrar$/i }).click()
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 20000 })

    const logoutAllResponse = await deleteWithCsrf(page, '/api/auth/logout-all')
    expect(logoutAllResponse.ok).toBe(true)
    expect(logoutAllResponse.data).toMatchObject({
      success: true,
      message: 'Logged out from all devices',
    })
    expect(Number(logoutAllResponse.data['sessions_deleted'] ?? 0)).toBeGreaterThanOrEqual(1)

    await page.reload({ waitUntil: 'networkidle' })
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })

    expect(unexpectedFirebaseRequests).toEqual([])
  })
})
