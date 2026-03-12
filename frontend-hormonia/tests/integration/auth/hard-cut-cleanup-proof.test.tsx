import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiClientCore } from '@/lib/api-client/core'
import { createAuthApi } from '@/lib/api-client/auth'
import { AuthProvider, useAuth } from '@/app/providers/AuthContext'
import { SecuritySettings } from '@/features/settings/sections/SecuritySettings'

const mockApiClient = vi.hoisted(() => ({
  request: vi.fn(),
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  fetchCsrfToken: vi.fn(),
  auth: {
    checkAuth: vi.fn(),
    logout: vi.fn(),
    invalidateAllSessions: vi.fn(),
    login: vi.fn(),
  },
  dashboard: {
    getMain: vi.fn().mockResolvedValue({}),
  },
}))

const mockWsManager = vi.hoisted(() => ({
  disconnect: vi.fn(),
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient,
}))

vi.mock('@/lib/websocket', () => ({
  wsManager: mockWsManager,
}))

vi.mock('@/hooks/use-toast', () => ({
  toast: vi.fn(),
}))

vi.mock('@/config/mock.config', () => ({
  isMockAuthEnabled: vi.fn().mockReturnValue(false),
}))

function AuthContractProbe() {
  const auth = useAuth()
  return (
    <div>
      <div data-testid="auth-ready">{String(!auth.isInitializing)}</div>
      <div data-testid="auth-contract-keys">{Object.keys(auth).sort().join(',')}</div>
    </div>
  )
}

function renderSecuritySettings() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <SecuritySettings />
    </QueryClientProvider>
  )
}

describe('hard cut cleanup proof', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApiClient.fetchCsrfToken.mockResolvedValue(undefined)
    mockApiClient.auth.checkAuth.mockResolvedValue({ authenticated: false })
    mockApiClient.auth.logout.mockResolvedValue({ success: true, message: 'Logged out successfully' })
    mockApiClient.auth.invalidateAllSessions.mockResolvedValue({
      success: true,
      sessions_deleted: 1,
      message: 'Logged out from all devices',
    })
    mockApiClient.auth.login.mockResolvedValue({
      valid: true,
      session_id: 'session-hard-cut-proof',
      remember_me: false,
      user_id: 'user-hard-cut-proof',
      expires_at: '2026-03-12T10:00:00-03:00',
      user: {
        id: 'user-hard-cut-proof',
        email: 'doctor@example.com',
        full_name: 'Dra. Hard Cut',
        role: 'doctor',
        is_active: true,
      },
    })
    mockApiClient.request.mockResolvedValue({
      success: true,
      message: 'Password changed successfully',
    })
  })

  it('removes the firebase session bridge from the public auth API contract', () => {
    const authApi = createAuthApi(new ApiClientCore('http://localhost:8000')) as Record<string, unknown>

    expect(authApi).not.toHaveProperty('createSession')
  })

  it('removes firebase-token naming from the public AuthProvider contract', async () => {
    render(
      <AuthProvider>
        <AuthContractProbe />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('auth-ready')).toHaveTextContent('true')
    })

    expect(screen.getByTestId('auth-contract-keys')).not.toHaveTextContent('getFirebaseToken')
  })

  it('submits settings password changes through the first-party endpoint contract', async () => {
    const user = userEvent.setup()
    renderSecuritySettings()

    await user.type(screen.getByLabelText(/senha atual/i), 'CurrentPass123!')
    await user.type(screen.getByLabelText(/^nova senha$/i), 'NextPass123!')
    await user.type(screen.getByLabelText(/confirmar nova senha/i), 'NextPass123!')
    await user.click(screen.getByRole('button', { name: /alterar senha/i }))

    await waitFor(() => {
      expect(mockApiClient.request).toHaveBeenCalledWith('/api/v2/auth/password', {
        method: 'PUT',
        body: JSON.stringify({
          current_password: 'CurrentPass123!',
          new_password: 'NextPass123!',
        }),
      })
    })
  })
})
