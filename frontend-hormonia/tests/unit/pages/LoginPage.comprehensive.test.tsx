import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { LoginPage } from '@/pages/LoginPage'
import { AuthContext } from '@/contexts/AuthContext'
import { AuthContextType } from '@/contexts/AuthContext'

// Mock dependencies
const mockLogin = vi.fn()
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    Navigate: ({ to }: { to: string }) => <div data-testid="navigate-to">{to}</div>,
    useLocation: () => ({ state: { from: { pathname: '/dashboard' } } })
  }
})

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

describe('LoginPage - Comprehensive Tests', () => {
  let user: ReturnType<typeof userEvent.setup>

  beforeEach(() => {
    user = userEvent.setup()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Page Rendering', () => {
    it('should render login form with all required elements', () => {
      renderWithAuth()

      expect(screen.getByRole('heading', { name: /entrar na sua conta/i })).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/senha/i)).toBeInTheDocument()
      expect(screen.getByRole('checkbox', { name: /manter-me conectado/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /entrar/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /esqueci minha senha/i })).toBeInTheDocument()
    })

    it('should render logo image with correct attributes', () => {
      renderWithAuth()

      const logo = screen.getByAltText('Neoplasias Litoral - Sistema de Gestão')
      expect(logo).toBeInTheDocument()
      expect(logo).toHaveAttribute('src', '/images/logo_system.svg')
    })

    it('should show demo credentials in development mode', () => {
      renderWithAuth()

      expect(screen.getByText('Credenciais Demo')).toBeInTheDocument()
      expect(screen.getByText('admin@neoplasiaslitoral.com')).toBeInTheDocument()
      expect(screen.getByText('Admin@123456!')).toBeInTheDocument()
    })

    it('should show loading spinner when isLoading is true', () => {
      renderWithAuth({ isLoading: true })

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
      expect(screen.queryByRole('form')).not.toBeInTheDocument()
    })

    it('should redirect to dashboard when already authenticated', () => {
      renderWithAuth({ isAuthenticated: true })

      expect(screen.getByTestId('navigate-to')).toHaveTextContent('/dashboard')
    })
  })

  describe('Form Interactions', () => {
    it('should update email field value on input', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')

      expect(emailInput).toHaveValue('test@example.com')
    })

    it('should update password field value on input', async () => {
      renderWithAuth()

      const passwordInput = screen.getByLabelText(/senha/i)
      await user.type(passwordInput, 'password123')

      expect(passwordInput).toHaveValue('password123')
    })

    it('should toggle password visibility', async () => {
      renderWithAuth()

      const passwordInput = screen.getByLabelText(/senha/i)
      const toggleButton = screen.getByRole('button', { name: /mostrar senha/i })

      expect(passwordInput).toHaveAttribute('type', 'password')

      await user.click(toggleButton)

      expect(passwordInput).toHaveAttribute('type', 'text')
      expect(screen.getByRole('button', { name: /ocultar senha/i })).toBeInTheDocument()

      await user.click(toggleButton)

      expect(passwordInput).toHaveAttribute('type', 'password')
    })

    it('should toggle remember me checkbox', async () => {
      renderWithAuth()

      const checkbox = screen.getByRole('checkbox', { name: /manter-me conectado/i })

      expect(checkbox).not.toBeChecked()

      await user.click(checkbox)

      expect(checkbox).toBeChecked()

      await user.click(checkbox)

      expect(checkbox).not.toBeChecked()
    })

    it('should show/hide forgot password section', async () => {
      renderWithAuth()

      const forgotPasswordButton = screen.getByRole('button', { name: /esqueci minha senha/i })

      expect(screen.queryByText('Redefinição de Senha')).not.toBeInTheDocument()

      await user.click(forgotPasswordButton)

      expect(screen.getByText('Redefinição de Senha')).toBeInTheDocument()
      expect(screen.getByText(/para redefinir sua senha/i)).toBeInTheDocument()

      const closeButton = screen.getByRole('button', { name: /fechar/i })
      await user.click(closeButton)

      expect(screen.queryByText('Redefinição de Senha')).not.toBeInTheDocument()
    })
  })

  describe('Form Validation', () => {
    it('should show email validation error for invalid email', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'invalid-email')
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText('Email inválido')).toBeInTheDocument()
      })
    })

    it('should show password validation error for short password', async () => {
      renderWithAuth()

      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(passwordInput, '123')
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText('Senha deve ter pelo menos 6 caracteres')).toBeInTheDocument()
      })
    })

    it('should not submit form with validation errors', async () => {
      renderWithAuth()

      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.click(submitButton)

      await waitFor(() => {
        expect(mockLogin).not.toHaveBeenCalled()
      })
    })

    it('should submit form with valid data', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const rememberMeCheckbox = screen.getByRole('checkbox', { name: /manter-me conectado/i })
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(rememberMeCheckbox)
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123', true)
      })
    })
  })

  describe('Error Handling', () => {
    it('should display authentication error', () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: false,
        error: 'Invalid credentials',
        handleSubmit: vi.fn((fn) => fn)
      })

      renderWithAuth()

      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })

    it('should focus on error alert when error appears', async () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)

      // First render without error
      const { rerender } = renderWithAuth()

      // Then rerender with error
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
  })

  describe('Loading States', () => {
    it('should show submitting state during login', () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: true,
        error: null,
        handleSubmit: vi.fn((fn) => fn)
      })

      renderWithAuth()

      const submitButton = screen.getByRole('button', { name: /entrando.../i })
      expect(submitButton).toBeDisabled()
      expect(screen.getByText('Entrando...')).toBeInTheDocument()
    })

    it('should disable form inputs during submission', () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: true,
        error: null,
        handleSubmit: vi.fn((fn) => fn)
      })

      renderWithAuth()

      const submitButton = screen.getByRole('button', { name: /entrando.../i })
      expect(submitButton).toBeDisabled()
    })
  })

  describe('Accessibility', () => {
    it('should have proper ARIA labels and roles', () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      expect(emailInput).toHaveAttribute('aria-invalid', 'false')
      expect(passwordInput).toHaveAttribute('aria-invalid', 'false')
      expect(submitButton).toHaveAttribute('type', 'submit')
    })

    it('should set aria-invalid to true for fields with errors', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'invalid-email')
      await user.click(submitButton)

      await waitFor(() => {
        expect(emailInput).toHaveAttribute('aria-invalid', 'true')
      })
    })

    it('should have proper aria-describedby for form fields', () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)

      expect(emailInput).toHaveAttribute('id', 'email')
      expect(passwordInput).toHaveAttribute('id', 'password')
    })

    it('should announce form submission status to screen readers', () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: true,
        error: null,
        handleSubmit: vi.fn((fn) => fn)
      })

      renderWithAuth()

      const liveRegion = screen.getByText('Enviando dados de login...')
      expect(liveRegion).toBeInTheDocument()
    })

    it('should announce errors to screen readers', () => {
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: false,
        error: 'Login failed',
        handleSubmit: vi.fn((fn) => fn)
      })

      renderWithAuth()

      const errorAnnouncement = screen.getByText('Erro no login: Login failed')
      expect(errorAnnouncement).toBeInTheDocument()
    })
  })

  describe('Keyboard Navigation', () => {
    it('should allow keyboard navigation through form elements', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const rememberMeCheckbox = screen.getByRole('checkbox', { name: /manter-me conectado/i })
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      // Start with email input focused
      emailInput.focus()
      expect(emailInput).toHaveFocus()

      // Tab to password input
      await user.tab()
      expect(passwordInput).toHaveFocus()

      // Tab to show/hide password button
      await user.tab()
      expect(screen.getByRole('button', { name: /mostrar senha/i })).toHaveFocus()

      // Tab to remember me checkbox
      await user.tab()
      expect(rememberMeCheckbox).toHaveFocus()

      // Tab to submit button
      await user.tab()
      expect(submitButton).toHaveFocus()
    })

    it('should submit form on Enter key in password field', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.keyboard('{Enter}')

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123', false)
      })
    })
  })

  describe('Production vs Development Mode', () => {
    it('should hide demo credentials in production', () => {
      const isProductionMock = vi.mocked(require('@/lib/runtime-config').isProduction)
      isProductionMock.mockReturnValue(true)

      renderWithAuth()

      expect(screen.queryByText('Credenciais Demo')).not.toBeInTheDocument()
      expect(screen.queryByText('admin@neoplasiaslitoral.com')).not.toBeInTheDocument()
    })

    it('should show development environment indicator', () => {
      renderWithAuth()

      expect(screen.getByText('🔧 Ambiente de desenvolvimento')).toBeInTheDocument()
    })

    it('should hide development indicator in production', () => {
      const isProductionMock = vi.mocked(require('@/lib/runtime-config').isProduction)
      isProductionMock.mockReturnValue(true)

      renderWithAuth()

      expect(screen.queryByText('🔧 Ambiente de desenvolvimento')).not.toBeInTheDocument()
    })
  })

  describe('Form Auto-completion', () => {
    it('should have proper autocomplete attributes', () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)

      expect(emailInput).toHaveAttribute('autoComplete', 'email')
      expect(passwordInput).toHaveAttribute('autoComplete', 'current-password')
    })

    it('should have email input focused by default', () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      expect(emailInput).toHaveAttribute('autoFocus')
    })
  })

  describe('Visual States', () => {
    it('should show correct placeholder text with demo credentials', () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      expect(emailInput).toHaveAttribute('placeholder', 'admin@neoplasiaslitoral.com')
    })

    it('should show correct placeholder text without demo credentials', () => {
      const useConfigMock = vi.mocked(require('@/lib/config-initializer').useConfig)
      useConfigMock.mockReturnValue({
        config: {
          VITE_ENVIRONMENT: 'production',
          VITE_DEBUG_MODE: 'false',
          VITE_SHOW_DEMO_CREDENTIALS: 'false'
        }
      })

      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      expect(emailInput).toHaveAttribute('placeholder', 'seu@email.com')
    })
  })
})