import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { AuthProvider, useAuth } from '@/app/providers/AuthContext'
import AdminRoutes from '@/app/routes/AdminRoutes'
import { ROUTES } from '@/app/routes/routeConfig'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'

const mockApiClient = vi.hoisted(() => ({
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  fetchCsrfToken: vi.fn(),
  auth: {
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
    checkAuth: vi.fn(),
    invalidateAllSessions: vi.fn(),
  },
  dashboard: {
    getMain: vi.fn().mockResolvedValue({}),
  },
}))

const mockWsManager = vi.hoisted(() => ({
  connect: vi.fn().mockResolvedValue(undefined),
  disconnect: vi.fn(),
  updateToken: vi.fn(),
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient,
}))

vi.mock('@/lib/websocket', () => ({
  wsManager: mockWsManager,
}))

vi.mock('@/config/mock.config', () => ({
  isMockAuthEnabled: vi.fn().mockReturnValue(false),
}))

vi.mock('@/hooks/use-toast', () => ({
  toast: vi.fn(),
}))

vi.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
    toasts: [],
  }),
}))

vi.mock('@/lib/logger', () => {
  const mockLogger = {
    log: vi.fn(),
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    group: vi.fn(),
    groupEnd: vi.fn(),
    time: vi.fn(),
    timeEnd: vi.fn(),
  }

  return {
    logger: mockLogger,
    default: mockLogger,
    createLogger: () => mockLogger,
  }
})

vi.mock('@/features/admin/AdminDashboard', () => ({
  default: () =>
    React.createElement(
      React.Fragment,
      null,
      React.createElement('div', null, 'Admin dashboard mock'),
      React.createElement(Outlet, null)
    ),
}))

vi.mock('@/features/admin/CompensationFailures', () => ({
  default: () => React.createElement('div', null, 'Compensation failures mock'),
}))

vi.mock('@/features/templates/TemplateManagementPage', () => ({
  default: () => React.createElement('div', null, 'Template management mock'),
}))

vi.mock('@/features/admin/AdminUserActivityMonitor', () => ({
  AdminUserActivityMonitor: () => React.createElement('div', null, 'Activity monitor mock'),
}))

const adminUser = {
  id: 'admin-123',
  email: 'admin@hormonia.com',
  full_name: 'Admin User',
  name: 'Admin User',
  role: 'admin',
  is_active: true,
  permissions: ['admin.read'],
  created_at: '2026-03-12T08:00:00-03:00',
}

const staffCredentials = {
  email: adminUser.email,
  password: 'StrongAdminRoutePass123!',
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location-path">{location.pathname}</div>
}

function MockCanonicalLogin() {
  const { login } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [email, setEmail] = React.useState(staffCredentials.email)
  const [password, setPassword] = React.useState(staffCredentials.password)
  const [rememberMe, setRememberMe] = React.useState(true)

  return (
    <form
      aria-label="canonical-login"
      onSubmit={async (event) => {
        event.preventDefault()
        await login(email, password, rememberMe)

        const redirectTarget =
          (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? '/dashboard'

        navigate(redirectTarget, { replace: true })
      }}
    >
      <h1>Canonical Login</h1>
      <label htmlFor="login-email">Email</label>
      <input id="login-email" value={email} onChange={(event) => setEmail(event.target.value)} />
      <label htmlFor="login-password">Senha</label>
      <input
        id="login-password"
        type="password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <label htmlFor="login-remember">Manter-me conectado</label>
      <input
        id="login-remember"
        type="checkbox"
        checked={rememberMe}
        onChange={(event) => setRememberMe(event.target.checked)}
      />
      <button type="submit">Entrar</button>
    </form>
  )
}

function renderOfficialRouter(initialRoute: string) {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <AuthProvider>
        <LocationProbe />
        <Routes>
          <Route path="/login" element={<MockCanonicalLogin />} />
          <Route
            path={ROUTES.ADMIN.ROOT}
            element={
              <ProtectedRoute requiredPermission="canAccessAdmin">
                <AdminRoutes />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('Admin Authentication Flow - routed session-first integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()

    mockApiClient.fetchCsrfToken.mockResolvedValue(undefined)
    mockApiClient.auth.checkAuth.mockResolvedValue({ authenticated: false })
    mockApiClient.auth.login.mockResolvedValue({
      valid: true,
      session_id: 'legacy-admin-session',
      remember_me: true,
      user: adminUser,
      user_id: adminUser.id,
      expires_at: '2026-03-13T08:00:00-03:00',
    })
    mockApiClient.auth.logout.mockResolvedValue({
      success: true,
      sessions_deleted: 1,
      message: 'Logged out',
    })
    mockApiClient.dashboard.getMain.mockResolvedValue({})
  })

  it('treats /admin/login as a protected routed path and redirects to canonical /login', async () => {
    renderOfficialRouter('/admin/login')

    await waitFor(() => {
      expect(screen.getByTestId('location-path')).toHaveTextContent(/^\/login$/)
    })

    expect(screen.getByRole('heading', { name: /canonical login/i })).toBeInTheDocument()
    expect(mockApiClient.auth.checkAuth).toHaveBeenCalledTimes(1)
  })

  it('routes protected /admin/* access through canonical /login and back into the shipped admin tree', async () => {
    const user = userEvent.setup()

    renderOfficialRouter('/admin/system/compensation')

    await waitFor(() => {
      expect(screen.getByTestId('location-path')).toHaveTextContent(/^\/login$/)
    })

    await user.clear(screen.getByLabelText(/^email$/i))
    await user.type(screen.getByLabelText(/^email$/i), staffCredentials.email)
    await user.clear(screen.getByLabelText(/^senha$/i))
    await user.type(screen.getByLabelText(/^senha$/i), staffCredentials.password)
    await user.click(screen.getByRole('button', { name: /^entrar$/i }))

    await waitFor(() => {
      expect(mockApiClient.auth.login).toHaveBeenCalledWith(
        expect.objectContaining({
          email: staffCredentials.email,
          remember_me: true,
          password: expect.any(String),
        })
      )
    })

    await waitFor(() => {
      expect(screen.getByTestId('location-path')).toHaveTextContent('/admin/system/compensation')
    })

    expect(await screen.findByText('Compensation failures mock')).toBeInTheDocument()
  })

  it('restores an authenticated admin session directly into the shipped /admin/* route tree', async () => {
    mockApiClient.auth.checkAuth.mockResolvedValueOnce({
      authenticated: true,
      user: adminUser,
      sessionId: 'legacy-restored-admin-session',
    })

    renderOfficialRouter('/admin/templates')

    await waitFor(() => {
      expect(screen.getByTestId('location-path')).toHaveTextContent('/admin/templates')
    })

    expect(await screen.findByText('Template management mock', {}, { timeout: 5000 })).toBeInTheDocument()
  })
})
