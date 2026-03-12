import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ApiClientCore, ApiError } from '@/lib/api-client/core'
import { createAuthApi } from '@/lib/api-client/auth'
import { AuthProvider, useAuth, safeLocalStorage } from '@/app/providers/AuthContext'

const mockFetch = vi.fn()
global.fetch = mockFetch as typeof fetch

const mockFirebaseAuth = vi.hoisted(() => ({
  onAuthStateChanged: vi.fn(),
  onIdTokenChanged: vi.fn(),
  getCurrentUser: vi.fn(),
  signOut: vi.fn(),
  setPersistence: vi.fn(),
  isConfigured: vi.fn().mockReturnValue(true),
}))

const mockApiClient = vi.hoisted(() => ({
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  fetchCsrfToken: vi.fn(),
  auth: {
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
    checkAuth: vi.fn(),
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

const mockFirebaseAuthService = vi.hoisted(() => ({
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  logoutAllDevices: vi.fn(),
  setSessionId: vi.fn(),
  clearSessionId: vi.fn(),
}))

vi.mock('@/lib/firebase-lazy', () => ({
  firebaseAuthLazy: mockFirebaseAuth,
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient,
}))

vi.mock('@/lib/websocket', () => ({
  wsManager: mockWsManager,
}))

vi.mock('@/services/firebase-auth', () => mockFirebaseAuthService)

vi.mock('@/hooks/use-toast', () => ({
  toast: vi.fn(),
}))

vi.mock('@/config/mock.config', () => ({
  isMockAuthEnabled: vi.fn().mockReturnValue(false),
}))

const sessionUser = {
  id: 'user-123',
  email: 'doctor@example.com',
  full_name: 'Dra. Session First',
  role: 'doctor',
  is_active: true,
  permissions: ['patients.read'],
  created_at: '2026-03-12T08:00:00-03:00',
}

const firebaseUser = {
  uid: 'firebase-uid-legacy',
  email: sessionUser.email,
  getIdToken: vi.fn().mockResolvedValue('firebase-jwt-token'),
}

function createMockResponse(data: unknown, status = 200, ok = status >= 200 && status < 300) {
  return {
    ok,
    status,
    headers: {
      get: () => null,
    },
    json: async () => data,
  }
}

function AuthProbe() {
  const auth = useAuth()

  return (
    <div>
      <div data-testid="is-initializing">{String(auth.isInitializing)}</div>
      <div data-testid="user-email">{auth.user?.email ?? 'anonymous'}</div>
      <button
        type="button"
        onClick={() => {
          void auth.login('doctor@example.com', 'SecurePass123!', true)
        }}
      >
        session-login
      </button>
      <button
        type="button"
        onClick={() => {
          void auth.logout()
        }}
      >
        session-logout
      </button>
    </div>
  )
}

describe('session-first auth cutover proof', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockApiClient.fetchCsrfToken.mockResolvedValue(undefined)
    mockApiClient.auth.login.mockResolvedValue({
      valid: true,
      session_id: 'session-cutover-123',
      remember_me: true,
      user: sessionUser,
      user_id: sessionUser.id,
      expires_at: '2026-03-13T08:00:00-03:00',
    })
    mockApiClient.auth.logout.mockResolvedValue({
      success: true,
      sessions_deleted: 1,
      message: 'Logged out',
    })
    mockApiClient.auth.me.mockResolvedValue({ data: sessionUser })
    mockApiClient.auth.checkAuth.mockResolvedValue({ authenticated: false })
    mockApiClient.dashboard.getMain.mockResolvedValue({})

    mockFirebaseAuth.isConfigured.mockReturnValue(true)
    mockFirebaseAuth.setPersistence.mockResolvedValue(undefined)
    mockFirebaseAuth.getCurrentUser.mockResolvedValue(firebaseUser)
    mockFirebaseAuth.signOut.mockResolvedValue(undefined)
    mockFirebaseAuth.onAuthStateChanged.mockImplementation(async (callback) => {
      await callback(null)
      return vi.fn()
    })
    mockFirebaseAuth.onIdTokenChanged.mockImplementation(async () => vi.fn())

    mockFirebaseAuthService.loginUser.mockResolvedValue({
      user: sessionUser,
      session_id: 'session-firebase-bridge-123',
    })
    mockFirebaseAuthService.logoutUser.mockResolvedValue(undefined)
    mockFirebaseAuthService.logoutAllDevices.mockResolvedValue({ sessions_deleted: 1 })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('posts remember_me to /api/v2/auth/login and preserves backend auth diagnostics', async () => {
    const client = new ApiClientCore('http://localhost:8000')
    ;(client as { csrfToken: string | null }).csrfToken = 'csrf-token'
    const authApi = createAuthApi(client)

    mockFetch.mockResolvedValueOnce(
      createMockResponse(
        {
          error: 'AUTH_INVALID_CREDENTIALS',
          message: 'Invalid email or password',
          request_id: 'req-login-401',
        },
        401,
        false
      )
    )

    await expect(
      authApi.login({
        email: 'doctor@example.com',
        password: 'WrongPass123!',
        remember_me: true,
      } as never)
    ).rejects.toMatchObject({
      status: 401,
      data: expect.objectContaining({
        error: 'AUTH_INVALID_CREDENTIALS',
        request_id: 'req-login-401',
      }),
    })

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v2/auth/login',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({
          email: 'doctor@example.com',
          password: 'WrongPass123!',
          remember_me: true,
        }),
      })
    )
    expect(String(mockFetch.mock.calls[0]?.[0] ?? '')).not.toContain('/api/v2/auth/firebase/verify')
  })

  it('restores browser auth from verify-session without Firebase listeners', async () => {
    mockApiClient.auth.checkAuth.mockResolvedValue({
      authenticated: true,
      user: sessionUser,
      sessionId: 'session-restore-123',
    })

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('user-email')).toHaveTextContent(sessionUser.email)
    })

    expect(mockApiClient.auth.checkAuth).toHaveBeenCalledTimes(1)
    expect(mockApiClient.setAuthToken).toHaveBeenCalledWith('session-restore-123')
    expect(mockFirebaseAuth.onAuthStateChanged).not.toHaveBeenCalled()
    expect(mockFirebaseAuth.onIdTokenChanged).not.toHaveBeenCalled()
  })

  it('logs in through apiClient.auth.login and avoids Firebase persistence controls', async () => {
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('is-initializing')).toHaveTextContent('false')
    })

    fireEvent.click(screen.getByRole('button', { name: 'session-login' }))

    await waitFor(() => {
      expect(mockApiClient.auth.login).toHaveBeenCalledWith({
        email: 'doctor@example.com',
        password: 'SecurePass123!',
        remember_me: true,
      })
    })

    expect(mockFirebaseAuthService.loginUser).not.toHaveBeenCalled()
    expect(mockFirebaseAuth.setPersistence).not.toHaveBeenCalled()
  })

  it('logs out through the first-party session endpoint and clears local cleanup surfaces', async () => {
    const removeItemSpy = vi.spyOn(safeLocalStorage, 'removeItem')

    mockApiClient.auth.checkAuth.mockResolvedValue({
      authenticated: true,
      user: sessionUser,
      sessionId: 'session-restore-123',
    })

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('user-email')).toHaveTextContent(sessionUser.email)
    })

    fireEvent.click(screen.getByRole('button', { name: 'session-logout' }))

    await waitFor(() => {
      expect(mockApiClient.auth.logout).toHaveBeenCalledTimes(1)
    })

    expect(removeItemSpy).toHaveBeenCalledWith('session_id')
    expect(mockWsManager.disconnect).toHaveBeenCalled()
    expect(mockFirebaseAuthService.logoutUser).not.toHaveBeenCalled()
  })
})
