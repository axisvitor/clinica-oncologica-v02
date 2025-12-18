/**
 * LoginPage Unit Tests
 *
 * Comprehensive tests for the login page component including:
 * - Form rendering and validation
 * - User interactions
 * - Error handling
 * - Loading states
 * - Accessibility
 */

import { expect, vi, describe, it, beforeEach, afterEach } from 'vitest'
import * as matchers from '@testing-library/jest-dom/matchers'
expect.extend(matchers)

import React from 'react'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'

// Cleanup after each test
afterEach(() => {
  cleanup()
})

// Mock Firebase auth
vi.mock('firebase/auth', () => ({
  signInWithEmailAndPassword: vi.fn(),
  getAuth: vi.fn(() => ({})),
  onAuthStateChanged: vi.fn(),
}))

// Mock auth context
const mockLogin = vi.fn()
const mockLogout = vi.fn()

vi.mock('@/app/providers/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isAuthenticated: false,
    isInitializing: false,
    isAuthenticating: false,
    login: mockLogin,
    logout: mockLogout,
    hasPermission: () => false,
    hasRole: () => false,
    session: null,
    getFirebaseToken: vi.fn().mockResolvedValue(null),
    refreshToken: vi.fn().mockResolvedValue(undefined),
    logoutAll: vi.fn().mockResolvedValue(undefined),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

// Mock config initializer
vi.mock('@/lib/config-initializer', () => ({
  useConfig: () => ({
    config: { apiUrl: 'http://localhost:8000' },
    isLoading: false,
    error: null,
  }),
}))

// Mock use-auth-submit hook
const mockHandleAuthSubmit = vi.fn()
vi.mock('@/hooks/use-auth-submit', () => ({
  useAuthSubmit: () => ({
    isSubmitting: false,
    error: null,
    handleSubmit: mockHandleAuthSubmit,
  }),
}))

// Mock runtime-config
vi.mock('@/lib/runtime-config', () => ({
  isProduction: () => false,
  getRuntimeConfig: () => ({
    VITE_API_URL: 'http://localhost:8000',
  }),
}))

// Mock navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({ state: null }),
  }
})

// Helper to render with router
const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  )
}

// ============================================================================
// Form Rendering Tests
// ============================================================================

describe('LoginPage - Form Rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render login form with email field', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    // Check for email input by name or placeholder
    const emailInput = screen.getByPlaceholderText(/email/i) ||
                       screen.getByRole('textbox')
    expect(emailInput).toBeInTheDocument()
  })

  it('should render login form with password field', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    // Check for password input (type="password" doesn't have role="textbox")
    const passwordInput = document.querySelector('input[type="password"]')
    expect(passwordInput).toBeInTheDocument()
  })

  it('should render submit button', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    // Check for submit button by type
    const submitButton = document.querySelector('button[type="submit"]')
    expect(submitButton).toBeInTheDocument()
  })

  it('should render logo image', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    const logos = screen.getAllByRole('img')
    expect(logos.length).toBeGreaterThan(0)
  })
})

// ============================================================================
// Form Validation Tests
// ============================================================================

describe('LoginPage - Form Validation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should have email input with correct type', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    const emailInput = document.querySelector('input[type="email"]')
    expect(emailInput).toBeInTheDocument()
  })

  it('should have password input with correct type', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    const passwordInput = document.querySelector('input[type="password"]')
    expect(passwordInput).toBeInTheDocument()
  })
})

// ============================================================================
// User Interaction Tests
// ============================================================================

describe('LoginPage - User Interactions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should update email input value on typing', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')
    const user = userEvent.setup()

    renderWithRouter(<LoginPage />)

    const emailInput = document.querySelector('input[type="email"]') as HTMLInputElement

    await user.type(emailInput, 'test@example.com')

    expect(emailInput.value).toBe('test@example.com')
  })

  it('should update password input value on typing', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')
    const user = userEvent.setup()

    renderWithRouter(<LoginPage />)

    const passwordInput = document.querySelector('input[type="password"]') as HTMLInputElement

    await user.type(passwordInput, 'mypassword123')

    expect(passwordInput.value).toBe('mypassword123')
  })

  it('should have password visibility toggle button', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    // Find toggle button by aria-label - use querySelector for precision
    const toggleButton = document.querySelector('button[aria-label*="senha"]')
    expect(toggleButton).toBeInTheDocument()
  })

  it('should toggle password visibility when toggle button clicked', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')
    const user = userEvent.setup()

    renderWithRouter(<LoginPage />)

    const passwordInput = document.querySelector('input[name="password"]') as HTMLInputElement
    const toggleButton = document.querySelector('button[aria-label*="senha"]') as HTMLButtonElement

    // Initially type should be password
    expect(passwordInput).toHaveAttribute('type', 'password')

    // Click toggle
    await user.click(toggleButton)
    expect(passwordInput).toHaveAttribute('type', 'text')

    // Click again to hide - aria-label changes to "Ocultar senha"
    const hideButton = document.querySelector('button[aria-label*="senha"]') as HTMLButtonElement
    await user.click(hideButton)
    expect(passwordInput).toHaveAttribute('type', 'password')
  })
})

// ============================================================================
// Security Tests
// ============================================================================

describe('LoginPage - Security', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should have password input type as password by default', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    const passwordInput = document.querySelector('input[name="password"]')
    expect(passwordInput).toHaveAttribute('type', 'password')
  })

  it('should have autocomplete attribute on email', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    const emailInput = document.querySelector('input[type="email"]')
    expect(emailInput).toHaveAttribute('autocomplete', 'email')
  })

  it('should not expose password in DOM', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')
    const user = userEvent.setup()

    renderWithRouter(<LoginPage />)

    const passwordInput = document.querySelector('input[type="password"]') as HTMLInputElement

    await user.type(passwordInput, 'SecretPassword123!')

    // Password value should be in input but not visible in innerHTML
    expect(passwordInput.value).toBe('SecretPassword123!')
    // The password should not appear as text content in the DOM
    const html = document.body.innerHTML
    expect(html).not.toContain('>SecretPassword123!<')
  })
})

// ============================================================================
// Remember Me Tests
// ============================================================================

describe('LoginPage - Remember Me', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should have remember me checkbox', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    const checkbox = document.querySelector('input[type="checkbox"]')
    expect(checkbox).toBeInTheDocument()
  })

  it('should be able to toggle remember me checkbox', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')
    const user = userEvent.setup()

    renderWithRouter(<LoginPage />)

    const checkbox = document.querySelector('input[type="checkbox"]') as HTMLInputElement

    expect(checkbox.checked).toBe(false)

    await user.click(checkbox)
    expect(checkbox.checked).toBe(true)

    await user.click(checkbox)
    expect(checkbox.checked).toBe(false)
  })
})

// ============================================================================
// Forgot Password Tests
// ============================================================================

describe('LoginPage - Forgot Password', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should have forgot password button', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    // Find forgot password button by aria-label
    const forgotButton = document.querySelector('button[aria-label*="redefinição"]')
    expect(forgotButton).toBeInTheDocument()
  })
})

// ============================================================================
// Accessibility Tests
// ============================================================================

describe('LoginPage - Accessibility', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should have proper labels for form fields', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    // Email input should have an associated label
    const emailInput = document.querySelector('input[type="email"]')
    expect(emailInput).toHaveAttribute('id')

    const emailLabel = document.querySelector(`label[for="${emailInput?.getAttribute('id')}"]`)
    expect(emailLabel).toBeInTheDocument()
  })

  it('should be keyboard navigable', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')
    const user = userEvent.setup()

    renderWithRouter(<LoginPage />)

    // Tab through form elements
    await user.tab()

    // First focusable element should be an input or button
    const focusedElement = document.activeElement
    expect(focusedElement?.tagName).toMatch(/INPUT|BUTTON|A/)
  })

  it('should have alt text on logo image', async () => {
    const { LoginPage } = await import('@/pages/LoginPage')

    renderWithRouter(<LoginPage />)

    const logos = screen.getAllByRole('img')
    // At least one image should have alt text
    const hasAltText = logos.some(img => img.getAttribute('alt')?.length)
    expect(hasAltText).toBe(true)
  })
})
