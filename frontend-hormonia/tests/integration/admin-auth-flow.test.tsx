import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import AdminApp from '@/AdminApp'
import { AuthProvider, useAuth } from '@/app/providers/AuthContext'

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
  default: () => React.createElement('div', null, 'Admin dashboard mock'),
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

function AuthProbe() {
  const { user } = useAuth()

  return <div data-testid="auth-user">{user?.email ?? 'anonymous'}</div>
}

function renderAdminApp(initialRoute: string) {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <AuthProvider>
        <AuthProbe />
        <Routes>
          <Route path="/admin/*" element={<AdminApp />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('Admin Authentication Flow - session-first integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    if (typeof window.localStorage?.removeItem === 'function') {
      window.localStorage.removeItem('session_id')
    }

    mockApiClient.fetchCsrfToken.mockResolvedValue(undefined)
    mockApiClient.auth.checkAuth.mockResolvedValue({ authenticated: false })
    mockApiClient.auth.login.mockResolvedValue({
      valid: true,
      session_id: 'admin-session-123',
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

  it('redirects unauthenticated /admin access to the admin login screen', async () => {
    renderAdminApp('/admin')

    await waitFor(() => {
      expect(screen.getByText(/Portal Administrativo/i)).toBeInTheDocument()
    })

    expect(mockApiClient.auth.checkAuth).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('auth-user')).toHaveTextContent('anonymous')
  })

  it('submits the admin login form through apiClient.auth.login with remember_me', async () => {
    const user = userEvent.setup()
    renderAdminApp('/admin/login')

    await waitFor(() => {
      expect(screen.getByText(/Portal Administrativo/i)).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText(/Endereço de Email/i), 'admin@hormonia.com')
    await user.type(screen.getByLabelText(/^Senha$/i), 'SecurePass123!')
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: /Entrar/i }))

    await waitFor(() => {
      expect(mockApiClient.auth.login).toHaveBeenCalledWith({
        email: 'admin@hormonia.com',
        password: 'SecurePass123!',
        remember_me: true,
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('auth-user')).toHaveTextContent('admin@hormonia.com')
    })

    expect(mockApiClient.setAuthToken).toHaveBeenCalledWith('admin-session-123')
  })

  it('restores an authenticated admin session into the protected dashboard route', async () => {
    mockApiClient.auth.checkAuth.mockResolvedValueOnce({
      authenticated: true,
      user: adminUser,
      sessionId: 'restored-admin-session',
    })

    renderAdminApp('/admin')

    await waitFor(() => {
      expect(screen.getByText('Admin dashboard mock')).toBeInTheDocument()
    })

    expect(screen.getByTestId('auth-user')).toHaveTextContent('admin@hormonia.com')
    expect(mockApiClient.setAuthToken).toHaveBeenCalledWith('restored-admin-session')
  })

  it('shows insufficient permissions when the restored user lacks admin.read', async () => {
    mockApiClient.auth.checkAuth.mockResolvedValueOnce({
      authenticated: true,
      user: {
        ...adminUser,
        role: 'doctor',
        permissions: [],
      },
      sessionId: 'restored-admin-session',
    })

    renderAdminApp('/admin')

    await waitFor(() => {
      expect(screen.getByText(/Insufficient Permissions/i)).toBeInTheDocument()
    })
  })
})
