import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import MedicoLogin from '../MedicoLogin'
import { AuthContext } from '@/contexts/AuthContext'
import { ROUTES } from '@/app/routes/routeConfig'

const mockLogin = vi.fn()

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

function renderMedicoLogin(authOverrides: Record<string, unknown> = {}) {
  return render(
    <MemoryRouter initialEntries={[ROUTES.MEDICO.LOGIN]}>
      <AuthContext.Provider value={createAuthValue(authOverrides) as never}>
        <Routes>
          <Route path={ROUTES.MEDICO.LOGIN} element={<MedicoLogin />} />
          <Route path={ROUTES.PHYSICIAN.DASHBOARD} element={<div>Physician Dashboard</div>} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

describe('MedicoLogin', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the canonical email-first physician compatibility entrypoint', () => {
    renderMedicoLogin()

    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^senha$/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/^crm$/i)).not.toBeInTheDocument()
    expect(screen.getByText(/acesso médico com email/i)).toBeInTheDocument()
  })

  it('submits email and password through the shared login surface', async () => {
    const user = userEvent.setup()
    renderMedicoLogin()

    await user.type(screen.getByLabelText(/^email$/i), 'medico@example.com')
    await user.type(screen.getByLabelText(/^senha$/i), 'StrongPass123')
    await user.click(screen.getByRole('button', { name: /^entrar$/i }))

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('medico@example.com', 'StrongPass123', false)
    })
  })

  it('redirects authenticated physicians to the canonical physician dashboard', () => {
    renderMedicoLogin({ isAuthenticated: true })

    expect(screen.getByText('Physician Dashboard')).toBeInTheDocument()
  })
})
