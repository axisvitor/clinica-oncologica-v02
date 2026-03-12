import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { LoginPage } from '@/pages/LoginPage'
import { AuthContext } from '@/contexts/AuthContext'
import { ROUTES } from '@/app/routes/routeConfig'

const mockLogin = vi.fn()
const mockIsProduction = vi.fn(() => false)
const mockConfig = {
  VITE_ENVIRONMENT: 'development',
  VITE_DEBUG_MODE: 'true',
  VITE_SHOW_DEMO_CREDENTIALS: 'true',
}
const mockAuthSubmitState = {
  isSubmitting: false,
  error: null as string | null,
}

vi.mock('@/lib/runtime-config', () => ({
  isProduction: () => mockIsProduction(),
}))

vi.mock('@/lib/config-initializer', () => ({
  useConfig: () => ({
    config: mockConfig,
  }),
}))

vi.mock('@/hooks/use-auth-submit', () => ({
  useAuthSubmit: vi.fn().mockImplementation(({ onSubmit }) => ({
    isSubmitting: mockAuthSubmitState.isSubmitting,
    error: mockAuthSubmitState.error,
    handleSubmit: async (data: unknown) => onSubmit(data),
  })),
}))

const createAuthValue = (overrides: Record<string, unknown> = {}) => ({
  user: null,
  session: null,
  isAuthenticated: false,
  isInitializing: false,
  isAuthenticating: false,
  login: mockLogin,
  logout: vi.fn(),
  logoutAll: vi.fn(),
  hasPermission: vi.fn(),
  hasRole: vi.fn(),
  getFirebaseToken: vi.fn(),
  refreshToken: vi.fn(),
  ...overrides,
})

function renderLogin(options?: {
  authOverrides?: Record<string, unknown>
  initialEntries?: Array<string | { pathname: string; state?: unknown }>
}) {
  const authValue = createAuthValue(options?.authOverrides)

  return render(
    <MemoryRouter initialEntries={options?.initialEntries ?? [ROUTES.LOGIN]}>
      <AuthContext.Provider value={authValue as never}>
        <Routes>
          <Route path={ROUTES.LOGIN} element={<LoginPage />} />
          <Route path={ROUTES.DASHBOARD} element={<div>Dashboard Route</div>} />
          <Route
            path={ROUTES.AUTH.PASSWORD_RESET_REQUEST}
            element={<div>Reset Request Route</div>}
          />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

describe('LoginPage - Comprehensive Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsProduction.mockReturnValue(false)
    mockConfig.VITE_ENVIRONMENT = 'development'
    mockConfig.VITE_DEBUG_MODE = 'true'
    mockConfig.VITE_SHOW_DEMO_CREDENTIALS = 'true'
    mockAuthSubmitState.isSubmitting = false
    mockAuthSubmitState.error = null
  })

  it('renders the canonical email-first login form', () => {
    renderLogin()

    expect(screen.getByRole('heading', { name: /entrar na sua conta/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^senha$/i)).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /manter-me conectado/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^entrar$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /esqueci minha senha/i })).toBeInTheDocument()
  })

  it('renders the logo and development demo credentials when enabled', () => {
    renderLogin()

    expect(screen.getByAltText('Neoplasias Litoral - Sistema de Gestão')).toBeInTheDocument()
    expect(screen.getByText('Credenciais Demo')).toBeInTheDocument()
    expect(screen.getByText('admin@neoplasiaslitoral.com')).toBeInTheDocument()
    expect(screen.getByText('🔧 Ambiente de desenvolvimento')).toBeInTheDocument()
  })

  it('hides demo credentials and development badge in production mode', () => {
    mockIsProduction.mockReturnValue(true)
    mockConfig.VITE_ENVIRONMENT = 'production'
    mockConfig.VITE_DEBUG_MODE = 'false'
    mockConfig.VITE_SHOW_DEMO_CREDENTIALS = 'false'

    renderLogin()

    expect(screen.queryByText('Credenciais Demo')).not.toBeInTheDocument()
    expect(screen.queryByText('🔧 Ambiente de desenvolvimento')).not.toBeInTheDocument()
    expect(screen.getByLabelText(/^email$/i)).toHaveAttribute('placeholder', 'seu@email.com')
  })

  it('shows a full-page spinner while auth is initializing', () => {
    renderLogin({ authOverrides: { isInitializing: true } })

    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /entrar na sua conta/i })).not.toBeInTheDocument()
  })

  it('redirects authenticated users to their intended destination', () => {
    renderLogin({
      authOverrides: { isAuthenticated: true },
      initialEntries: [{ pathname: ROUTES.LOGIN, state: { from: { pathname: ROUTES.DASHBOARD } } }],
    })

    expect(screen.getByText('Dashboard Route')).toBeInTheDocument()
  })

  it('updates the email and password fields while typing', async () => {
    const user = userEvent.setup()
    renderLogin()

    const emailInput = screen.getByLabelText(/^email$/i)
    const passwordInput = screen.getByLabelText(/^senha$/i)

    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'StrongPass123')

    expect(emailInput).toHaveValue('test@example.com')
    expect(passwordInput).toHaveValue('StrongPass123')
  })

  it('toggles password visibility', async () => {
    const user = userEvent.setup()
    renderLogin()

    const passwordInput = screen.getByLabelText(/^senha$/i)
    const toggleButton = screen.getByRole('button', { name: /mostrar senha/i })

    expect(passwordInput).toHaveAttribute('type', 'password')

    await user.click(toggleButton)
    expect(passwordInput).toHaveAttribute('type', 'text')

    await user.click(screen.getByRole('button', { name: /ocultar senha/i }))
    expect(passwordInput).toHaveAttribute('type', 'password')
  })

  it('validates email format before submitting', async () => {
    const user = userEvent.setup()
    renderLogin()

    await user.type(screen.getByLabelText(/^email$/i), 'invalid-email')
    await user.type(screen.getByLabelText(/^senha$/i), 'StrongPass123')
    await user.click(screen.getByRole('button', { name: /^entrar$/i }))

    await waitFor(() => {
      expect(screen.getByText('Email inválido')).toBeInTheDocument()
    })
    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('validates password length before submitting', async () => {
    const user = userEvent.setup()
    renderLogin()

    await user.type(screen.getByLabelText(/^email$/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^senha$/i), '123')
    await user.click(screen.getByRole('button', { name: /^entrar$/i }))

    await waitFor(() => {
      expect(screen.getByText('Senha deve ter pelo menos 6 caracteres')).toBeInTheDocument()
    })
    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('submits canonical email, password, and remember-me state', async () => {
    const user = userEvent.setup()
    renderLogin()

    await user.type(screen.getByLabelText(/^email$/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^senha$/i), 'StrongPass123')
    await user.click(screen.getByRole('checkbox', { name: /manter-me conectado/i }))
    await user.click(screen.getByRole('button', { name: /^entrar$/i }))

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'StrongPass123', true)
    })
  })

  it('navigates to the routed reset-request page instead of showing a support placeholder', async () => {
    const user = userEvent.setup()
    renderLogin()

    await user.click(screen.getByRole('button', { name: /solicitar redefinição de senha/i }))

    expect(screen.getByText('Reset Request Route')).toBeInTheDocument()
    expect(screen.queryByText(/suporte@neoplasiaslitoral\.com/i)).not.toBeInTheDocument()
  })

  it('surfaces auth errors in an alert and focuses the alert for assistive tech', async () => {
    const { rerender } = renderLogin()

    mockAuthSubmitState.error = 'Invalid credentials'

    rerender(
      <MemoryRouter initialEntries={[ROUTES.LOGIN]}>
        <AuthContext.Provider value={createAuthValue() as never}>
          <Routes>
            <Route path={ROUTES.LOGIN} element={<LoginPage />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials')
      expect(screen.getByRole('alert')).toHaveFocus()
    })
  })

  it('announces loading state while login submission is in progress', () => {
    mockAuthSubmitState.isSubmitting = true

    renderLogin()

    expect(screen.getByText('Enviando dados de login...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /entrando.../i })).toBeDisabled()
  })

  it('exposes accessible form wiring for validation and autocomplete', async () => {
    const user = userEvent.setup()
    renderLogin()

    const emailInput = screen.getByLabelText(/^email$/i)
    const passwordInput = screen.getByLabelText(/^senha$/i)

    expect(emailInput).toHaveAttribute('autoComplete', 'email')
    expect(passwordInput).toHaveAttribute('autoComplete', 'current-password')
    expect(emailInput).toHaveAttribute('aria-invalid', 'false')
    expect(passwordInput).toHaveAttribute('aria-invalid', 'false')

    await user.type(emailInput, 'invalid-email')
    await user.click(screen.getByRole('button', { name: /^entrar$/i }))

    await waitFor(() => {
      expect(emailInput).toHaveAttribute('aria-invalid', 'true')
      expect(emailInput).toHaveAttribute('aria-describedby', 'email-error')
    })
  })
})
