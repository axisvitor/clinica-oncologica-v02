import { writeFile } from 'node:fs/promises'
import { test, expect, type Response, type TestInfo } from '@playwright/test'

const seededStaff = {
  email: process.env.E2E_SESSION_FIRST_EMAIL,
  password: process.env.E2E_SESSION_FIRST_PASSWORD,
}

function requiredSeededFixtureNames() {
  const missing: string[] = []
  if (!seededStaff.email) missing.push('E2E_SESSION_FIRST_EMAIL')
  if (!seededStaff.password) missing.push('E2E_SESSION_FIRST_PASSWORD')
  return missing
}

type CapturedRequest = {
  method: string
  url: string
  status: number
  ok: boolean
  responseBody?: Record<string, unknown>
}

type RouteSmokeEvidence = {
  phase: 'running' | 'completed' | 'failed'
  currentRoute: string
  lastSuccessfulRoute: string | null
  loginEntry: {
    attemptedPath: string
    redirectedTo?: string
    headingVisible?: boolean
  }
  admin?: {
    finalUrl?: string
    headingVisible?: boolean
    analyticsOverview?: CapturedRequest
  }
  dashboard?: {
    finalUrl?: string
    headingVisible?: boolean
    onlineBadgeVisible?: boolean
    request?: CapturedRequest
  }
  whatsapp?: {
    finalUrl?: string
    headingVisible?: boolean
    request?: CapturedRequest
  }
  unexpectedFirebaseRequests: string[]
  failure?: string
}

async function persistRouteSmokeEvidence(testInfo: TestInfo, evidence: RouteSmokeEvidence) {
  const evidencePath = testInfo.outputPath('route-smoke-evidence.json')
  await writeFile(evidencePath, JSON.stringify(evidence, null, 2), 'utf-8')
  return evidencePath
}

async function captureRequest(response: Response, includeJsonBody = false): Promise<CapturedRequest> {
  let responseBody: Record<string, unknown> | undefined

  if (includeJsonBody) {
    responseBody = (await response.json().catch(() => undefined)) as Record<string, unknown> | undefined
  }

  return {
    method: response.request().method(),
    url: response.url(),
    status: response.status(),
    ok: response.ok(),
    ...(responseBody ? { responseBody } : {}),
  }
}

test.describe('mounted no-firebase runtime smoke', () => {
  test.describe.configure({ mode: 'serial' })

  test.skip(({ browserName }) => browserName !== 'chromium', 'Mounted proof runs once in Chromium')

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

  test('covers /login, /dashboard, /admin, and /whatsapp on the live cookie-only runtime', async (
    { page },
    testInfo
  ) => {
    const missingFixtures = requiredSeededFixtureNames()
    test.skip(
      missingFixtures.length > 0,
      `Seeded auth fixtures missing: ${missingFixtures.join(', ')}`
    )

    const unexpectedFirebaseRequests: string[] = []
    const routeEvidence: RouteSmokeEvidence = {
      phase: 'running',
      currentRoute: '/login',
      lastSuccessfulRoute: null,
      loginEntry: {
        attemptedPath: '/admin',
      },
      unexpectedFirebaseRequests,
    }

    page.on('request', (request) => {
      if (/\/auth\/firebase\/verify|firebase/i.test(request.url())) {
        unexpectedFirebaseRequests.push(`${request.method()} ${request.url()}`)
      }
    })

    try {
      await test.step('route /admin via official /login entrypoint', async () => {
        routeEvidence.currentRoute = '/admin'
        await persistRouteSmokeEvidence(testInfo, routeEvidence)

        await page.goto('/admin')
        await expect(page).toHaveURL(/\/login/, { timeout: 20000 })
        routeEvidence.loginEntry.redirectedTo = page.url()

        await expect(page.getByRole('heading', { name: /entrar na sua conta/i })).toBeVisible({
          timeout: 15000,
        })
        routeEvidence.loginEntry.headingVisible = true
        routeEvidence.currentRoute = '/login'
        await persistRouteSmokeEvidence(testInfo, routeEvidence)

        const adminOverviewResponsePromise = page.waitForResponse(
          (response) =>
            response.url().includes('/api/v2/analytics/overview') &&
            response.request().method() === 'GET'
        )

        await page.getByLabel(/^email$/i).fill(seededStaff.email)
        await page.getByLabel(/^senha$/i).fill(seededStaff.password)
        await page.getByRole('button', { name: /^entrar$/i }).click()

        const adminOverviewResponse = await adminOverviewResponsePromise
        expect(adminOverviewResponse.ok()).toBe(true)
        await expect(page).toHaveURL(/\/admin\/?$/, { timeout: 20000 })
        await expect(page).not.toHaveURL(/\/admin\/login/, { timeout: 5000 })
        await expect(page.getByRole('heading', { name: /admin dashboard/i })).toBeVisible({
          timeout: 15000,
        })

        routeEvidence.admin = {
          finalUrl: page.url(),
          headingVisible: true,
          analyticsOverview: await captureRequest(adminOverviewResponse),
        }
        routeEvidence.lastSuccessfulRoute = '/admin'
        routeEvidence.currentRoute = '/admin'
        await persistRouteSmokeEvidence(testInfo, routeEvidence)
      })

      await test.step('route /dashboard with real /api/v2/dashboard/main fetch', async () => {
        routeEvidence.currentRoute = '/dashboard'
        await persistRouteSmokeEvidence(testInfo, routeEvidence)

        const dashboardResponsePromise = page.waitForResponse(
          (response) =>
            response.url().includes('/api/v2/dashboard/main') &&
            response.request().method() === 'GET'
        )

        await page.goto('/dashboard')

        const dashboardResponse = await dashboardResponsePromise
        expect(dashboardResponse.ok()).toBe(true)
        await expect(page).toHaveURL(/\/dashboard/, { timeout: 20000 })
        await expect(page.getByRole('heading', { name: /^dashboard$/i })).toBeVisible({
          timeout: 15000,
        })
        await expect(page.getByText(/sistema online/i)).toBeVisible({ timeout: 15000 })

        routeEvidence.dashboard = {
          finalUrl: page.url(),
          headingVisible: true,
          onlineBadgeVisible: true,
          request: await captureRequest(dashboardResponse),
        }
        routeEvidence.lastSuccessfulRoute = '/dashboard'
        await persistRouteSmokeEvidence(testInfo, routeEvidence)
      })

      await test.step('route /whatsapp with mocked WuzAPI session success', async () => {
        routeEvidence.currentRoute = '/whatsapp'
        await persistRouteSmokeEvidence(testInfo, routeEvidence)

        const wuzapiStatusResponsePromise = page.waitForResponse(
          (response) =>
            response.url().includes('/api/v2/monitoring/wuzapi/session/status') &&
            response.request().method() === 'GET'
        )

        await page.goto('/whatsapp')

        const wuzapiStatusResponse = await wuzapiStatusResponsePromise
        expect(wuzapiStatusResponse.ok()).toBe(true)
        await expect(page).toHaveURL(/\/whatsapp/, { timeout: 20000 })
        await expect(page.getByRole('heading', { name: /whatsapp integration/i })).toBeVisible({
          timeout: 15000,
        })

        const wuzapiRequest = await captureRequest(wuzapiStatusResponse, true)
        expect(wuzapiRequest.responseBody).toMatchObject({
          connected: true,
          logged_in: true,
          mock: true,
        })

        routeEvidence.whatsapp = {
          finalUrl: page.url(),
          headingVisible: true,
          request: wuzapiRequest,
        }
        routeEvidence.lastSuccessfulRoute = '/whatsapp'
        await persistRouteSmokeEvidence(testInfo, routeEvidence)
      })

      expect(unexpectedFirebaseRequests).toEqual([])
      routeEvidence.phase = 'completed'
    } catch (error) {
      routeEvidence.phase = 'failed'
      routeEvidence.failure = error instanceof Error ? error.message : String(error)
      throw error
    } finally {
      const evidencePath = await persistRouteSmokeEvidence(testInfo, routeEvidence)
      await testInfo.attach('route-smoke-evidence', {
        path: evidencePath,
        contentType: 'application/json',
      })
    }
  })
})
