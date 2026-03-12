import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ApiError } from '@/lib/api-client/core'
import { LoginPage } from '@/pages/LoginPage'
import MedicoLogin from '@/pages/medico/MedicoLogin'
import { PasswordResetRequestPage } from '@/pages/auth/PasswordResetRequestPage'
import { PasswordResetConfirmPage } from '@/pages/auth/PasswordResetConfirmPage'
import { publicRoutes } from '@/app/routes/routeDefinitions'
import { ROUTES } from '@/app/routes/routeConfig'
import { AuthContext } from '@/contexts/AuthContext'

const { mockRequestPasswordReset, mockConfirmPasswordReset, mockLogin } = vi.hoisted(() => ({
  mockRequestPasswordReset: vi.fn(),
  mockConfirmPasswordReset: vi.fn(),
  mockLogin: vi.fn(),
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    auth: {
      requestPasswordReset: mockRequestPasswordReset,
      confirmPasswordReset: mockConfirmPasswordReset,
    },
  },
}))

vi.mock('@/lib/runtime-config', () => ({
  isProduction: vi.fn().mockReturnValue(false),
}))

vi.mock('@/lib/config-initializer', () => ({
  useConfig: () => ({
    config: {
      VITE_ENVIRONMENT: 'development',
      VITE_DEBUG_MODE: 'true',
      VITE_SHOW_DEMO_CREDENTIALS: 'false',
    },
  }),
}))

vi.mock('@/hooks/use-auth-submit', () => ({
  useAuthSubmit: vi.fn().mockImplementation(({ onSubmit }) => ({
    isSubmitting: false,
    error: null,
    handleSubmit: async (data: unknown) => onSubmit(data),
  })),
}))

const authValue = {
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
}

function renderWithAuth(ui: React.ReactNode, initialEntries: string[] = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AuthContext.Provider value={authValue as never}>{ui}</AuthContext.Provider>
    </MemoryRouter>
  )
}

describe('recovery and physician route cutover proof', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRequestPasswordReset.mockReset()
    mockConfirmPasswordReset.mockReset()
    mockLogin.mockReset()
  })

  it('requires routed reset-request and reset-confirm pages on the public surface', () => {
    const publicPaths = publicRoutes.map((route) => route.path)

    expect(publicPaths).toContain(ROUTES.AUTH.PASSWORD_RESET_REQUEST)
    expect(publicPaths).toContain(ROUTES.AUTH.PASSWORD_RESET_CONFIRM)
    expect(publicPaths).toContain(ROUTES.AUTH.LEGACY_RESET_PASSWORD)
    expect(publicPaths).toContain(ROUTES.AUTH.FIRST_ACCESS)
    expect(publicPaths).toContain(ROUTES.MEDICO.LOGIN)
  })

  it('replaces the support-email forgot-password placeholder with routed recovery', async () => {
    const user = userEvent.setup()

    renderWithAuth(
      <Routes>
        <Route path={ROUTES.LOGIN} element={<LoginPage />} />
        <Route path={ROUTES.AUTH.PASSWORD_RESET_REQUEST} element={<PasswordResetRequestPage />} />
      </Routes>,
      [ROUTES.LOGIN]
    )

    await user.click(screen.getByRole('button', { name: /solicitar redefinição de senha/i }))

    expect(
      screen.getByRole('heading', { name: /receber um novo link de acesso/i })
    ).toBeInTheDocument()
    expect(screen.queryByText(/suporte@neoplasiaslitoral\.com/i)).not.toBeInTheDocument()
  })

  it('submits the reset-request page through the first-party recovery endpoint with generic success messaging', async () => {
    const user = userEvent.setup()
    mockRequestPasswordReset.mockResolvedValue({
      success: true,
      message: 'If the account exists, a recovery email has been sent.',
    })

    renderWithAuth(<PasswordResetRequestPage />)

    await user.type(screen.getByLabelText(/^email$/i), 'medico@example.com')
    await user.click(screen.getByRole('button', { name: /enviar link de recuperação/i }))

    await waitFor(() => {
      expect(mockRequestPasswordReset).toHaveBeenCalledWith({ email: 'medico@example.com' })
    })

    expect(screen.getAllByText(/se existir uma conta vinculada a este email/i).length).toBeGreaterThan(0)
    expect(screen.queryByText(/medico@example.com/i)).not.toBeInTheDocument()
  })

  it('surfaces actionable delivery diagnostics on reset-request failures', async () => {
    const user = userEvent.setup()
    mockRequestPasswordReset.mockRejectedValue(
      new ApiError(
        503,
        {
          error: 'AUTH_PASSWORD_RESET_DELIVERY_FAILED',
          message: 'Unable to send recovery email at this time.',
          request_id: 'req-reset-503',
        },
        'Unable to send recovery email at this time.',
        'Unable to send recovery email at this time.'
      )
    )

    renderWithAuth(<PasswordResetRequestPage />)

    await user.type(screen.getByLabelText(/^email$/i), 'medico@example.com')
    await user.click(screen.getByRole('button', { name: /enviar link de recuperação/i }))

    await waitFor(() => {
      expect(screen.getAllByText(/não foi possível enviar o email agora/i).length).toBeGreaterThan(0)
    })

    expect(screen.getByText(/AUTH_PASSWORD_RESET_DELIVERY_FAILED/i)).toBeInTheDocument()
    expect(screen.getByText(/req-reset-503/i)).toBeInTheDocument()
  })

  it('shows actionable invalid-token recovery on the reset-confirm page', async () => {
    const user = userEvent.setup()
    mockConfirmPasswordReset.mockRejectedValue(
      new ApiError(
        400,
        {
          error: 'AUTH_RESET_TOKEN_INVALID_OR_EXPIRED',
          message: 'Invalid or expired reset token.',
          request_id: 'req-reset-confirm-1',
        },
        'Invalid or expired reset token.',
        'Invalid or expired reset token.'
      )
    )

    renderWithAuth(
      <Routes>
        <Route path={ROUTES.AUTH.PASSWORD_RESET_CONFIRM} element={<PasswordResetConfirmPage />} />
        <Route path={ROUTES.AUTH.PASSWORD_RESET_REQUEST} element={<PasswordResetRequestPage />} />
      </Routes>,
      [`${ROUTES.AUTH.PASSWORD_RESET_CONFIRM}?token=expired-token`]
    )

    await user.type(screen.getByLabelText(/nova senha/i), 'StrongPass123')
    await user.type(screen.getByLabelText(/confirmar senha/i), 'StrongPass123')
    await user.click(screen.getByRole('button', { name: /salvar nova senha/i }))

    await waitFor(() => {
      expect(screen.getByText(/o link de recuperação expirou/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/AUTH_RESET_TOKEN_INVALID_OR_EXPIRED/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /solicitar novo link/i })).toHaveAttribute(
      'href',
      ROUTES.AUTH.PASSWORD_RESET_REQUEST
    )
  })

  it('treats /medico/login as an email-first compatibility entrypoint instead of a CRM-only form', () => {
    renderWithAuth(<MedicoLogin />)

    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/^crm$/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/portal médico/i)).not.toBeInTheDocument()
    expect(screen.getByText(/acesso médico com email/i)).toBeInTheDocument()
  })
})
