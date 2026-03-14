import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ApiClientCore } from '@/lib/api-client/core'
import { createAuthApi } from '@/lib/api-client/auth'
import { AuthProvider, useAuth, safeLocalStorage } from '@/app/providers/AuthContext'

const mockFetch = vi.fn()
global.fetch = mockFetch as typeof fetch

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

const staffCredentials = {
  email: 'doctor@example.com',
  password: 'StrongSessionFirstPass123!',
}

const sessionUser = {
  id: 'user-123',
  email: staffCredentials.email,
  full_name: 'Dra. Session First',
  role: 'doctor',
  is_active: true,
  permissions: ['patients.read'],
  created_at: '2026-03-12T08:00:00-03:00',
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
          void auth.login(staffCredentials.email, staffCredentials.password, true)
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
    window.localStorage.clear()

    mockFetch.mockReset()
    mockApiClient.fetchCsrfToken.mockResolvedValue(undefined)
    mockApiClient.auth.login.mockResolvedValue({
      valid: true,
      session_id: 'legacy-session-login',
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
        email: staffCredentials.email,
        password: staffCredentials.password,
        remember_me: true,
      })
    ).rejects.toMatchObject({
      status: 401,
      data: expect.objectContaining({
        error: 'AUTH_INVALID_CREDENTIALS',
        request_id: 'req-login-401',
      }),
    })

    const [requestUrl, requestInit] = mockFetch.mock.calls[0] as [string, RequestInit]
    const requestBody = JSON.parse(String(requestInit.body ?? '{}')) as Record<string, unknown>

    expect(requestUrl).toBe('http://localhost:8000/api/v2/auth/login')
    expect(requestInit).toEqual(
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
      })
    )
    expect(requestBody).toMatchObject({
      email: staffCredentials.email,
      remember_me: true,
    })
    expect(requestBody.password).toEqual(expect.any(String))
    expect(requestUrl).not.toContain('/api/v2/auth/firebase/verify')
  })

  it('restores cookie-backed session state without rehydrating localStorage.session_id', async () => {
    const getItemSpy = vi.spyOn(safeLocalStorage, 'getItem')
    const setItemSpy = vi.spyOn(safeLocalStorage, 'setItem')

    mockApiClient.auth.checkAuth.mockResolvedValue({
      authenticated: true,
      user: sessionUser,
      sessionId: 'legacy-session-restore',
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
    expect(mockApiClient.setAuthToken).not.toHaveBeenCalled()
    expect(getItemSpy).not.toHaveBeenCalledWith('session_id')
    expect(setItemSpy).not.toHaveBeenCalledWith('session_id', expect.any(String))
  })

  it('logs in through AuthProvider without persisting localStorage.session_id', async () => {
    const getItemSpy = vi.spyOn(safeLocalStorage, 'getItem')
    const setItemSpy = vi.spyOn(safeLocalStorage, 'setItem')

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('is-initializing')).toHaveTextContent('false')
    })

    getItemSpy.mockClear()
    setItemSpy.mockClear()
    mockApiClient.setAuthToken.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'session-login' }))

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
      expect(screen.getByTestId('user-email')).toHaveTextContent(sessionUser.email)
    })

    expect(mockApiClient.setAuthToken).not.toHaveBeenCalled()
    expect(getItemSpy).not.toHaveBeenCalledWith('session_id')
    expect(setItemSpy).not.toHaveBeenCalledWith('session_id', expect.any(String))
  })

  it('logs out through the first-party session endpoint without rehydrating legacy session storage', async () => {
    const getItemSpy = vi.spyOn(safeLocalStorage, 'getItem')
    const setItemSpy = vi.spyOn(safeLocalStorage, 'setItem')
    const removeItemSpy = vi.spyOn(safeLocalStorage, 'removeItem')

    mockApiClient.auth.checkAuth.mockResolvedValue({
      authenticated: true,
      user: sessionUser,
      sessionId: 'legacy-session-restore',
    })

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('user-email')).toHaveTextContent(sessionUser.email)
    })

    getItemSpy.mockClear()
    setItemSpy.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'session-logout' }))

    await waitFor(() => {
      expect(mockApiClient.auth.logout).toHaveBeenCalledTimes(1)
    })

    await waitFor(() => {
      expect(screen.getByTestId('user-email')).toHaveTextContent('anonymous')
    })

    expect(getItemSpy).not.toHaveBeenCalledWith('session_id')
    expect(setItemSpy).not.toHaveBeenCalledWith('session_id', expect.any(String))
    expect(removeItemSpy).toHaveBeenCalledWith('session_id')
    expect(mockWsManager.disconnect).toHaveBeenCalled()
  })
})
