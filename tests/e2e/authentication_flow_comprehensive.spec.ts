/**
 * Comprehensive Authentication Flow E2E Tests
 * ==========================================
 *
 * This test suite validates the complete authentication flow for the oncology clinic system,
 * including Firebase authentication, admin authentication, role-based access, and session management.
 *
 * Test Coverage:
 * - Firebase authentication integration
 * - Admin vs regular user authentication flows
 * - Role-based access control (RBAC)
 * - Session management and timeouts
 * - Multi-factor authentication scenarios
 * - Security measures and error handling
 */

import { test, expect, Page, BrowserContext } from '@playwright/test'

// Test configuration
const ADMIN_EMAIL = 'admin@hormonia.com'
const ADMIN_PASSWORD = 'TestAdminPassword123!'
const DOCTOR_EMAIL = 'doctor@hormonia.com'
const DOCTOR_PASSWORD = 'TestDoctorPassword123!'
const PATIENT_EMAIL = 'patient@hormonia.com'
const PATIENT_PASSWORD = 'TestPatientPassword123!'
const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:4173'

// Test data
const TEST_USERS = {
  admin: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD, role: 'admin' },
  doctor: { email: DOCTOR_EMAIL, password: DOCTOR_PASSWORD, role: 'doctor' },
  patient: { email: PATIENT_EMAIL, password: PATIENT_PASSWORD, role: 'patient' }
}

class AuthenticationTestHelper {
  constructor(private page: Page) {}

  async navigateToLogin(userType: 'admin' | 'doctor' | 'patient' = 'doctor') {
    const loginPath = userType === 'admin' ? '/admin/login' : '/login'
    await this.page.goto(`${BASE_URL}${loginPath}`)
    await this.page.waitForLoadState('networkidle')
  }

  async fillLoginForm(email: string, password: string) {
    await this.page.getByLabel(/email/i).fill(email)
    await this.page.getByLabel(/password/i).fill(password)
  }

  async submitLogin() {
    await this.page.getByRole('button', { name: /login|entrar/i }).click()
  }

  async verifyDashboardRedirect(userType: 'admin' | 'doctor' | 'patient') {
    const expectedPaths = {
      admin: '/admin/dashboard',
      doctor: '/dashboard',
      patient: '/patient/dashboard'
    }

    await this.page.waitForURL(`${BASE_URL}${expectedPaths[userType]}`)
    await expect(this.page.getByText(/dashboard|painel/i)).toBeVisible()
  }

  async verifyAuthenticationError() {
    await expect(this.page.getByText(/invalid.*credentials|credenciais.*inválidas/i)).toBeVisible()
  }

  async logout() {
    await this.page.getByRole('button', { name: /logout|sair/i }).click()
    await this.page.waitForURL(`${BASE_URL}/login`)
  }

  async verifySessionExpiry() {
    // Wait for session expiry warning
    await expect(this.page.getByText(/session.*expiring|sessão.*expirando/i)).toBeVisible({ timeout: 30000 })
  }

  async extendSession() {
    await this.page.getByRole('button', { name: /extend.*session|estender.*sessão/i }).click()
  }
}

test.describe('Firebase Authentication Integration', () => {
  let authHelper: AuthenticationTestHelper

  test.beforeEach(async ({ page }) => {
    authHelper = new AuthenticationTestHelper(page)
  })

  test('should authenticate with Firebase and redirect to dashboard', async ({ page }) => {
    await authHelper.navigateToLogin('doctor')

    // Fill login form
    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)

    // Monitor network requests for Firebase auth
    const authRequests: any[] = []
    page.on('request', request => {
      if (request.url().includes('identitytoolkit.googleapis.com')) {
        authRequests.push(request)
      }
    })

    await authHelper.submitLogin()

    // Verify Firebase authentication occurred
    expect(authRequests.length).toBeGreaterThan(0)

    // Verify successful redirect
    await authHelper.verifyDashboardRedirect('doctor')

    // Verify authentication state in localStorage/sessionStorage
    const authToken = await page.evaluate(() => localStorage.getItem('firebase-auth-token'))
    expect(authToken).toBeTruthy()
  })

  test('should handle Firebase authentication errors gracefully', async ({ page }) => {
    await authHelper.navigateToLogin('doctor')

    // Use invalid credentials
    await authHelper.fillLoginForm('invalid@email.com', 'wrongpassword')

    await authHelper.submitLogin()

    // Should show Firebase error message
    await authHelper.verifyAuthenticationError()

    // Should not redirect
    await expect(page).toHaveURL(`${BASE_URL}/login`)
  })

  test('should handle network connectivity issues', async ({ page, context }) => {
    await authHelper.navigateToLogin('doctor')

    // Simulate offline mode
    await context.setOffline(true)

    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper.submitLogin()

    // Should show network error
    await expect(page.getByText(/network.*error|erro.*rede/i)).toBeVisible()

    // Restore connectivity
    await context.setOffline(false)

    // Retry should work
    await authHelper.submitLogin()
    await authHelper.verifyDashboardRedirect('doctor')
  })

  test('should persist authentication across browser refresh', async ({ page }) => {
    await authHelper.navigateToLogin('doctor')
    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper.submitLogin()
    await authHelper.verifyDashboardRedirect('doctor')

    // Refresh the page
    await page.reload()

    // Should still be authenticated
    await expect(page.getByText(/dashboard|painel/i)).toBeVisible()
  })
})

test.describe('Admin Authentication Flow', () => {
  let authHelper: AuthenticationTestHelper

  test.beforeEach(async ({ page }) => {
    authHelper = new AuthenticationTestHelper(page)
  })

  test('should authenticate admin user and access admin dashboard', async ({ page }) => {
    await authHelper.navigateToLogin('admin')

    await authHelper.fillLoginForm(TEST_USERS.admin.email, TEST_USERS.admin.password)
    await authHelper.submitLogin()

    await authHelper.verifyDashboardRedirect('admin')

    // Verify admin-specific content
    await expect(page.getByText(/user.*management|gerenciar.*usuários/i)).toBeVisible()
    await expect(page.getByText(/system.*stats|estatísticas.*sistema/i)).toBeVisible()
  })

  test('should prevent regular user from accessing admin routes', async ({ page }) => {
    // First login as regular doctor
    await authHelper.navigateToLogin('doctor')
    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper.submitLogin()
    await authHelper.verifyDashboardRedirect('doctor')

    // Try to access admin route
    await page.goto(`${BASE_URL}/admin/users`)

    // Should redirect to unauthorized or login page
    await expect(page).toHaveURL(/\/(login|unauthorized|403)/);
  })

  test('should handle admin session timeout correctly', async ({ page }) => {
    await authHelper.navigateToLogin('admin')
    await authHelper.fillLoginForm(TEST_USERS.admin.email, TEST_USERS.admin.password)
    await authHelper.submitLogin()
    await authHelper.verifyDashboardRedirect('admin')

    // Mock session timeout by clearing tokens
    await page.evaluate(() => {
      localStorage.removeItem('firebase-auth-token')
      sessionStorage.clear()
    })

    // Try to access protected admin route
    await page.goto(`${BASE_URL}/admin/users`)

    // Should redirect to admin login
    await expect(page).toHaveURL(`${BASE_URL}/admin/login`)
  })

  test('should show admin inactivity warning', async ({ page }) => {
    await authHelper.navigateToLogin('admin')
    await authHelper.fillLoginForm(TEST_USERS.admin.email, TEST_USERS.admin.password)
    await authHelper.submitLogin()
    await authHelper.verifyDashboardRedirect('admin')

    // Wait for inactivity warning (this might need to be mocked or have reduced timeouts for testing)
    // In a real test, you might need to mock the inactivity timer
    await page.evaluate(() => {
      // Trigger inactivity warning manually for testing
      const event = new CustomEvent('admin-inactivity-warning')
      window.dispatchEvent(event)
    })

    await expect(page.getByText(/session.*expiring|sessão.*expirando/i)).toBeVisible()

    // Test session extension
    await authHelper.extendSession()
    await expect(page.getByText(/session.*extended|sessão.*estendida/i)).toBeVisible()
  })
})

test.describe('Role-Based Access Control (RBAC)', () => {
  test('should enforce role-based route access', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)

    // Test admin access
    await authHelper.navigateToLogin('admin')
    await authHelper.fillLoginForm(TEST_USERS.admin.email, TEST_USERS.admin.password)
    await authHelper.submitLogin()

    // Admin should access admin routes
    await page.goto(`${BASE_URL}/admin/users`)
    await expect(page.getByText(/user.*list|lista.*usuários/i)).toBeVisible()

    await authHelper.logout()

    // Test doctor access
    await authHelper.navigateToLogin('doctor')
    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper.submitLogin()

    // Doctor should access patient management
    await page.goto(`${BASE_URL}/patients`)
    await expect(page.getByText(/patients|pacientes/i)).toBeVisible()

    // Doctor should NOT access admin routes
    await page.goto(`${BASE_URL}/admin/users`)
    await expect(page).toHaveURL(/\/(login|unauthorized|403)/)
  })

  test('should display appropriate UI elements based on user role', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)

    // Test admin UI elements
    await authHelper.navigateToLogin('admin')
    await authHelper.fillLoginForm(TEST_USERS.admin.email, TEST_USERS.admin.password)
    await authHelper.submitLogin()

    // Admin should see admin navigation items
    await expect(page.getByText(/user.*management|gerenciar.*usuários/i)).toBeVisible()
    await expect(page.getByText(/system.*settings|configurações.*sistema/i)).toBeVisible()

    await authHelper.logout()

    // Test doctor UI elements
    await authHelper.navigateToLogin('doctor')
    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper.submitLogin()

    // Doctor should see patient-related navigation
    await expect(page.getByText(/patients|pacientes/i)).toBeVisible()
    await expect(page.getByText(/appointments|consultas/i)).toBeVisible()

    // Doctor should NOT see admin elements
    await expect(page.getByText(/user.*management|gerenciar.*usuários/i)).not.toBeVisible()
  })
})

test.describe('Session Management', () => {
  test('should maintain session across multiple tabs', async ({ context }) => {
    const page1 = await context.newPage()
    const page2 = await context.newPage()

    const authHelper1 = new AuthenticationTestHelper(page1)
    const authHelper2 = new AuthenticationTestHelper(page2)

    // Login in first tab
    await authHelper1.navigateToLogin('doctor')
    await authHelper1.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper1.submitLogin()
    await authHelper1.verifyDashboardRedirect('doctor')

    // Navigate to dashboard in second tab
    await page2.goto(`${BASE_URL}/dashboard`)

    // Should be authenticated in second tab
    await expect(page2.getByText(/dashboard|painel/i)).toBeVisible()

    // Logout from first tab
    await authHelper1.logout()

    // Second tab should also be logged out
    await page2.reload()
    await expect(page2).toHaveURL(`${BASE_URL}/login`)
  })

  test('should handle concurrent session management', async ({ context }) => {
    // This test verifies that the system handles multiple concurrent sessions properly
    const page1 = await context.newPage()
    const page2 = await context.newPage()

    const authHelper1 = new AuthenticationTestHelper(page1)
    const authHelper2 = new AuthenticationTestHelper(page2)

    // Login as admin in first tab
    await authHelper1.navigateToLogin('admin')
    await authHelper1.fillLoginForm(TEST_USERS.admin.email, TEST_USERS.admin.password)
    await authHelper1.submitLogin()

    // Login as doctor in second tab
    await authHelper2.navigateToLogin('doctor')
    await authHelper2.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper2.submitLogin()

    // Both should be authenticated with appropriate access
    await page1.goto(`${BASE_URL}/admin/users`)
    await expect(page1.getByText(/user.*list|lista.*usuários/i)).toBeVisible()

    await page2.goto(`${BASE_URL}/patients`)
    await expect(page2.getByText(/patients|pacientes/i)).toBeVisible()
  })

  test('should handle session conflicts gracefully', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)

    // Login normally
    await authHelper.navigateToLogin('doctor')
    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper.submitLogin()

    // Simulate token manipulation/corruption
    await page.evaluate(() => {
      localStorage.setItem('firebase-auth-token', 'invalid-token')
    })

    // Navigate to protected route
    await page.goto(`${BASE_URL}/patients`)

    // Should handle gracefully and redirect to login
    await expect(page).toHaveURL(`${BASE_URL}/login`)
  })
})

test.describe('Security Measures', () => {
  test('should prevent XSS attacks in login form', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)
    await authHelper.navigateToLogin('doctor')

    const xssPayload = '<script>alert("XSS")</script>'

    // Try XSS in email field
    await authHelper.fillLoginForm(xssPayload, 'password123')
    await authHelper.submitLogin()

    // Should not execute script and should show validation error
    await expect(page.getByText(/invalid.*email|email.*inválido/i)).toBeVisible()
  })

  test('should implement proper CSRF protection', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)
    await authHelper.navigateToLogin('doctor')

    // Monitor network requests for CSRF tokens
    const requests: any[] = []
    page.on('request', request => {
      requests.push({
        url: request.url(),
        headers: request.headers()
      })
    })

    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper.submitLogin()

    // Check for CSRF protection headers
    const authRequest = requests.find(req => req.url.includes('/api/'))
    if (authRequest) {
      // Should include CSRF token or other protection
      expect(
        authRequest.headers['x-csrf-token'] ||
        authRequest.headers['x-requested-with'] ||
        authRequest.headers['authorization']
      ).toBeTruthy()
    }
  })

  test('should implement rate limiting on login attempts', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)
    await authHelper.navigateToLogin('doctor')

    // Attempt multiple failed logins
    for (let i = 0; i < 6; i++) {
      await authHelper.fillLoginForm('wrong@email.com', 'wrongpassword')
      await authHelper.submitLogin()

      if (i < 5) {
        await authHelper.verifyAuthenticationError()
      }
    }

    // Should show rate limiting message
    await expect(page.getByText(/too.*many.*attempts|muitas.*tentativas/i)).toBeVisible()
  })

  test('should mask sensitive information in network requests', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)
    await authHelper.navigateToLogin('doctor')

    // Monitor network requests
    const requests: any[] = []
    page.on('request', request => {
      if (request.postData()) {
        requests.push({
          url: request.url(),
          postData: request.postData()
        })
      }
    })

    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper.submitLogin()

    // Check that password is not sent in plain text (should be handled by Firebase)
    const loginRequest = requests.find(req => req.postData?.includes('password'))
    if (loginRequest) {
      // Firebase should handle password encryption
      expect(loginRequest.postData).not.toContain(TEST_USERS.doctor.password)
    }
  })
})

test.describe('Error Handling and Recovery', () => {
  test('should handle Firebase service downtime gracefully', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)
    await authHelper.navigateToLogin('doctor')

    // Mock Firebase service error
    await page.route('**/identitytoolkit.googleapis.com/**', route => {
      route.fulfill({
        status: 503,
        body: JSON.stringify({ error: 'Service temporarily unavailable' })
      })
    })

    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper.submitLogin()

    // Should show service unavailable message
    await expect(page.getByText(/service.*unavailable|serviço.*indisponível/i)).toBeVisible()

    // Should provide retry option
    await expect(page.getByRole('button', { name: /retry|tentar.*novamente/i })).toBeVisible()
  })

  test('should recover from token refresh failures', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)

    // Login successfully first
    await authHelper.navigateToLogin('doctor')
    await authHelper.fillLoginForm(TEST_USERS.doctor.email, TEST_USERS.doctor.password)
    await authHelper.submitLogin()
    await authHelper.verifyDashboardRedirect('doctor')

    // Mock token refresh failure
    await page.route('**/securetoken.googleapis.com/**', route => {
      route.fulfill({
        status: 401,
        body: JSON.stringify({ error: 'Token refresh failed' })
      })
    })

    // Trigger token refresh (this might need to be simulated)
    await page.evaluate(() => {
      // Simulate token expiry
      const event = new CustomEvent('token-refresh-failed')
      window.dispatchEvent(event)
    })

    // Should redirect to login
    await expect(page).toHaveURL(`${BASE_URL}/login`)
  })

  test('should handle authentication state synchronization errors', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)

    // Create authentication state mismatch
    await page.goto(`${BASE_URL}/dashboard`)

    // Manually set invalid auth state
    await page.evaluate(() => {
      localStorage.setItem('auth-state', 'authenticated')
      // But don't set proper Firebase token
    })

    await page.reload()

    // Should detect mismatch and redirect to login
    await expect(page).toHaveURL(`${BASE_URL}/login`)
  })
})

test.describe('Accessibility and Usability', () => {
  test('should support keyboard-only authentication flow', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)
    await authHelper.navigateToLogin('doctor')

    // Navigate using only keyboard
    await page.keyboard.press('Tab') // Focus email field
    await page.keyboard.type(TEST_USERS.doctor.email)

    await page.keyboard.press('Tab') // Focus password field
    await page.keyboard.type(TEST_USERS.doctor.password)

    await page.keyboard.press('Tab') // Focus login button
    await page.keyboard.press('Enter') // Submit form

    await authHelper.verifyDashboardRedirect('doctor')
  })

  test('should provide proper ARIA labels and roles', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)
    await authHelper.navigateToLogin('doctor')

    // Check for proper accessibility attributes
    const emailField = page.getByLabel(/email/i)
    const passwordField = page.getByLabel(/password/i)
    const loginButton = page.getByRole('button', { name: /login/i })

    await expect(emailField).toHaveAttribute('type', 'email')
    await expect(passwordField).toHaveAttribute('type', 'password')
    await expect(loginButton).toHaveAttribute('type', 'submit')

    // Check for required field indicators
    await expect(emailField).toHaveAttribute('required')
    await expect(passwordField).toHaveAttribute('required')
  })

  test('should work with screen readers', async ({ page }) => {
    const authHelper = new AuthenticationTestHelper(page)
    await authHelper.navigateToLogin('doctor')

    // Check for screen reader friendly elements
    await expect(page.getByRole('main')).toBeVisible()
    await expect(page.getByRole('form')).toBeVisible()

    // Error messages should be announced
    await authHelper.fillLoginForm('invalid@email.com', 'wrongpassword')
    await authHelper.submitLogin()

    const errorMessage = page.getByRole('alert').or(page.getByText(/error|erro/i))
    await expect(errorMessage).toBeVisible()
  })
})