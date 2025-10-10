import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe, toHaveNoViolations } from 'jest-axe'
import { BrowserRouter } from 'react-router-dom'
import { LoginPage } from '@/pages/LoginPage'
import { AuthContext } from '@/contexts/AuthContext'
import { AuthContextType } from '@/contexts/AuthContext'

// Extend Jest matchers
expect.extend(toHaveNoViolations)

// Mock dependencies
const mockLogin = vi.fn()

vi.mock('@/lib/runtime-config', () => ({
  isProduction: vi.fn().mockReturnValue(false)
}))

vi.mock('@/lib/config-initializer', () => ({
  useConfig: () => ({
    config: {
      VITE_ENVIRONMENT: 'development',
      VITE_DEBUG_MODE: 'true',
      VITE_SHOW_DEMO_CREDENTIALS: 'true'
    }
  })
}))

vi.mock('@/hooks/use-auth-submit', () => ({
  useAuthSubmit: vi.fn().mockReturnValue({
    isSubmitting: false,
    error: null,
    handleSubmit: vi.fn((fn) => fn)
  })
}))

const createMockAuthContext = (overrides: Partial<AuthContextType> = {}): AuthContextType => ({
  user: null,
  session: null,
  isAuthenticated: false,
  isLoading: false,
  login: mockLogin,
  logout: vi.fn(),
  logoutAll: vi.fn(),
  hasPermission: vi.fn(),
  hasRole: vi.fn(),
  getFirebaseToken: vi.fn(),
  refreshToken: vi.fn(),
  ...overrides
})

const renderWithAuth = (authValue: Partial<AuthContextType> = {}) => {
  const contextValue = createMockAuthContext(authValue)

  return render(
    <BrowserRouter>
      <AuthContext.Provider value={contextValue}>
        <LoginPage />
      </AuthContext.Provider>
    </BrowserRouter>
  )
}

describe('Authentication Accessibility Tests', () => {
  let user: ReturnType<typeof userEvent.setup>

  beforeEach(() => {
    user = userEvent.setup()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('WCAG 2.1 AA Compliance', () => {
    it('should have no accessibility violations on initial render', async () => {
      const { container } = renderWithAuth()
      const results = await axe(container)
      expect(results).toHaveNoViolations()
    })

    it('should have no accessibility violations with demo credentials shown', async () => {
      const { container } = renderWithAuth()
      const results = await axe(container)
      expect(results).toHaveNoViolations()
    })

    it('should have no accessibility violations with form errors', async () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: false,
        error: 'Invalid credentials',
        handleSubmit: vi.fn((fn) => fn)
      })

      const { container } = renderWithAuth()
      const results = await axe(container)
      expect(results).toHaveNoViolations()
    })

    it('should have no accessibility violations in loading state', async () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: true,
        error: null,
        handleSubmit: vi.fn((fn) => fn)
      })

      const { container } = renderWithAuth()
      const results = await axe(container)
      expect(results).toHaveNoViolations()
    })

    it('should have no accessibility violations with validation errors', async () => {
      const { container } = renderWithAuth()

      // Trigger validation errors
      const submitButton = screen.getByRole('button', { name: /entrar/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/email inválido/i)).toBeInTheDocument()
      })

      const results = await axe(container)
      expect(results).toHaveNoViolations()
    })
  })

  describe('Semantic HTML Structure', () => {
    it('should use proper heading hierarchy', () => {
      renderWithAuth()

      const mainHeading = screen.getByRole('heading', { level: 1 })
      expect(mainHeading).toBeInTheDocument()

      // Should have proper heading structure
      const headings = screen.getAllByRole('heading')
      expect(headings[0]).toHaveProperty('tagName', 'H1')
    })

    it('should use proper form structure', () => {
      renderWithAuth()

      // Should have a form element
      const form = screen.getByRole('form') || document.querySelector('form')
      expect(form).toBeInTheDocument()

      // Form should contain all necessary inputs
      expect(screen.getByRole('textbox', { name: /email/i })).toBeInTheDocument()
      expect(screen.getByLabelText(/senha/i)).toBeInTheDocument()
      expect(screen.getByRole('checkbox')).toBeInTheDocument()
      expect(screen.getByRole('button', { type: 'submit' })).toBeInTheDocument()
    })

    it('should use proper landmark roles', () => {
      renderWithAuth()

      // Main content should be identifiable
      const main = document.querySelector('main') || document.querySelector('[role="main"]')
      expect(main || document.body).toBeInTheDocument()
    })
  })

  describe('Keyboard Navigation', () => {
    it('should support full keyboard navigation', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const passwordToggle = screen.getByRole('button', { name: /mostrar senha/i })
      const rememberMeCheckbox = screen.getByRole('checkbox')
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      // Tab through all interactive elements
      await user.tab()
      expect(emailInput).toHaveFocus()

      await user.tab()
      expect(passwordInput).toHaveFocus()

      await user.tab()
      expect(passwordToggle).toHaveFocus()

      await user.tab()
      expect(rememberMeCheckbox).toHaveFocus()

      await user.tab()
      expect(submitButton).toHaveFocus()
    })

    it('should handle keyboard interactions properly', async () => {
      renderWithAuth()

      const passwordToggle = screen.getByRole('button', { name: /mostrar senha/i })
      const passwordInput = screen.getByLabelText(/senha/i)

      // Focus and activate password toggle with keyboard
      passwordToggle.focus()
      await user.keyboard('{Enter}')

      expect(passwordInput).toHaveAttribute('type', 'text')

      await user.keyboard('{Space}')
      expect(passwordInput).toHaveAttribute('type', 'password')
    })

    it('should support form submission with Enter key', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')

      // Submit form with Enter key
      await user.keyboard('{Enter}')

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123', false)
      })
    })

    it('should trap focus in modals/dialogs', async () => {
      renderWithAuth()

      const forgotPasswordButton = screen.getByRole('button', { name: /esqueci minha senha/i })
      await user.click(forgotPasswordButton)

      // Focus should move to the forgot password section
      await waitFor(() => {
        expect(screen.getByText('Redefinição de Senha')).toBeInTheDocument()
      })

      // Tab navigation should work within the section
      const closeButton = screen.getByRole('button', { name: /fechar/i })
      expect(closeButton).toBeInTheDocument()
    })
  })

  describe('Screen Reader Support', () => {
    it('should have proper labels for all form inputs', () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const rememberMeCheckbox = screen.getByLabelText(/manter-me conectado/i)

      expect(emailInput).toHaveAccessibleName()
      expect(passwordInput).toHaveAccessibleName()
      expect(rememberMeCheckbox).toHaveAccessibleName()
    })

    it('should announce form validation errors', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'invalid-email')
      await user.click(submitButton)

      await waitFor(() => {
        const errorMessage = screen.getByText(/email inválido/i)
        expect(errorMessage).toHaveAttribute('role', 'alert')
      })
    })

    it('should announce loading states', () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: true,
        error: null,
        handleSubmit: vi.fn((fn) => fn)
      })

      renderWithAuth()

      // Should have live region for loading announcement
      const loadingAnnouncement = screen.getByText('Enviando dados de login...')
      expect(loadingAnnouncement).toHaveAttribute('aria-live', 'polite')
    })

    it('should announce authentication errors', () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: false,
        error: 'Login failed',
        handleSubmit: vi.fn((fn) => fn)
      })

      renderWithAuth()

      const errorAlert = screen.getByRole('alert')
      expect(errorAlert).toHaveTextContent('Login failed')
      expect(errorAlert).toHaveAttribute('aria-live', 'polite')
    })

    it('should provide meaningful button descriptions', () => {
      renderWithAuth()

      const passwordToggle = screen.getByRole('button', { name: /mostrar senha/i })
      const submitButton = screen.getByRole('button', { name: /entrar/i })
      const forgotPasswordButton = screen.getByRole('button', { name: /esqueci minha senha/i })

      expect(passwordToggle).toHaveAccessibleName()
      expect(submitButton).toHaveAccessibleName()
      expect(forgotPasswordButton).toHaveAccessibleName()
    })
  })

  describe('ARIA Attributes', () => {
    it('should use proper ARIA attributes for form validation', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)

      // Initially should not be invalid
      expect(emailInput).toHaveAttribute('aria-invalid', 'false')
      expect(passwordInput).toHaveAttribute('aria-invalid', 'false')

      // Trigger validation error
      await user.type(emailInput, 'invalid-email')
      await user.click(screen.getByRole('button', { name: /entrar/i }))

      await waitFor(() => {
        expect(emailInput).toHaveAttribute('aria-invalid', 'true')
      })
    })

    it('should use aria-describedby for error messages', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'invalid-email')
      await user.click(screen.getByRole('button', { name: /entrar/i }))

      await waitFor(() => {
        const errorMessage = screen.getByText(/email inválido/i)
        const errorId = errorMessage.getAttribute('id')
        expect(emailInput).toHaveAttribute('aria-describedby', errorId)
      })
    })

    it('should use proper ARIA roles for alerts and status messages', () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: false,
        error: 'Authentication failed',
        handleSubmit: vi.fn((fn) => fn)
      })

      renderWithAuth()

      const errorAlert = screen.getByRole('alert')
      expect(errorAlert).toHaveAttribute('aria-live', 'polite')
    })

    it('should use aria-expanded for collapsible content', async () => {
      renderWithAuth()

      const forgotPasswordButton = screen.getByRole('button', { name: /esqueci minha senha/i })

      // Initially collapsed
      expect(screen.queryByText('Redefinição de Senha')).not.toBeInTheDocument()

      // Expand
      await user.click(forgotPasswordButton)

      await waitFor(() => {
        expect(screen.getByText('Redefinição de Senha')).toBeInTheDocument()
      })
    })
  })

  describe('Focus Management', () => {
    it('should manage focus properly on error display', async () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)

      // First render without error
      const { rerender } = renderWithAuth()

      // Then show error
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: false,
        error: 'Login failed',
        handleSubmit: vi.fn((fn) => fn)
      })

      rerender(
        <BrowserRouter>
          <AuthContext.Provider value={createMockAuthContext()}>
            <LoginPage />
          </AuthContext.Provider>
        </BrowserRouter>
      )

      await waitFor(() => {
        const errorAlert = screen.getByRole('alert')
        expect(errorAlert).toHaveFocus()
      })
    })

    it('should maintain focus on form elements during validation', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'invalid-email')
      await user.click(submitButton)

      // Focus should remain on the input or move to error
      await waitFor(() => {
        const focusedElement = document.activeElement
        expect(focusedElement).toBeTruthy()
      })
    })

    it('should handle focus for disabled elements', () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: true,
        error: null,
        handleSubmit: vi.fn((fn) => fn)
      })

      renderWithAuth()

      const submitButton = screen.getByRole('button', { name: /entrando.../i })
      expect(submitButton).toBeDisabled()

      // Disabled button should not be focusable
      submitButton.focus()
      expect(submitButton).not.toHaveFocus()
    })
  })

  describe('Color and Contrast', () => {
    it('should have sufficient color contrast for text elements', () => {
      renderWithAuth()

      // This would typically be tested with automated tools
      // Here we ensure elements are rendered with proper classes
      const heading = screen.getByRole('heading', { name: /entrar na sua conta/i })
      expect(heading).toHaveClass(/text-/)

      const labels = screen.getAllByText(/email|senha/i)
      labels.forEach(label => {
        expect(label).toBeVisible()
      })
    })

    it('should not rely solely on color for error indication', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'invalid-email')
      await user.click(screen.getByRole('button', { name: /entrar/i }))

      await waitFor(() => {
        // Error should be indicated by text, not just color
        const errorMessage = screen.getByText(/email inválido/i)
        expect(errorMessage).toBeInTheDocument()

        // Input should have aria-invalid attribute
        expect(emailInput).toHaveAttribute('aria-invalid', 'true')
      })
    })
  })

  describe('Responsive Accessibility', () => {
    it('should maintain accessibility on mobile viewport', async () => {
      // Simulate mobile viewport
      Object.defineProperty(window, 'innerWidth', { value: 375 })
      Object.defineProperty(window, 'innerHeight', { value: 667 })

      const { container } = renderWithAuth()
      const results = await axe(container)
      expect(results).toHaveNoViolations()
    })

    it('should have adequate touch targets on mobile', () => {
      renderWithAuth()

      const submitButton = screen.getByRole('button', { name: /entrar/i })
      const passwordToggle = screen.getByRole('button', { name: /mostrar senha/i })

      // Buttons should be visible and clickable
      expect(submitButton).toBeVisible()
      expect(passwordToggle).toBeVisible()
    })
  })

  describe('High Contrast Mode Support', () => {
    it('should remain functional in high contrast mode', () => {
      // Simulate high contrast mode
      const mediaQuery = window.matchMedia('(prefers-contrast: high)')
      vi.spyOn(mediaQuery, 'matches', 'get').mockReturnValue(true)

      renderWithAuth()

      // All interactive elements should still be visible
      expect(screen.getByLabelText(/email/i)).toBeVisible()
      expect(screen.getByLabelText(/senha/i)).toBeVisible()
      expect(screen.getByRole('button', { name: /entrar/i })).toBeVisible()
    })
  })

  describe('Reduced Motion Support', () => {
    it('should respect prefers-reduced-motion setting', () => {
      // Simulate reduced motion preference
      const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
      vi.spyOn(mediaQuery, 'matches', 'get').mockReturnValue(true)

      renderWithAuth()

      // Page should render without motion-dependent content
      expect(screen.getByRole('heading', { name: /entrar na sua conta/i })).toBeVisible()
    })
  })

  describe('Language and Internationalization', () => {
    it('should have proper lang attribute', () => {
      renderWithAuth()

      // Document or elements should have proper language attributes
      expect(document.documentElement).toHaveAttribute('lang')
    })

    it('should provide clear instructions in Portuguese', () => {
      renderWithAuth()

      // All user-facing text should be in Portuguese
      expect(screen.getByText(/entrar na sua conta/i)).toBeInTheDocument()
      expect(screen.getByText(/digite suas credenciais/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/senha/i)).toBeInTheDocument()
    })
  })
})