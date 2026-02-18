import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { safeLocalStorage } from '@/app/providers/AuthContext'

const {
  mockFirebaseAuth,
  mockWsManager,
  mockApiClient,
  mockLoginUser,
  mockLogoutUser,
  mockLogoutAllDevices,
} = vi.hoisted(() => ({
  mockFirebaseAuth: {
    isConfigured: vi.fn(),
    getCurrentUser: vi.fn(),
    onAuthStateChanged: vi.fn(),
    onIdTokenChanged: vi.fn(),
    setPersistence: vi.fn(),
    signOut: vi.fn(),
  },
  mockWsManager: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    updateToken: vi.fn(),
  },
  mockApiClient: {
    auth: {
      me: vi.fn(),
      checkAuth: vi.fn(),
    },
    dashboard: {
      getMain: vi.fn(),
    },
    setAuthToken: vi.fn(),
    clearAuthToken: vi.fn(),
    fetchCsrfToken: vi.fn(),
  },
  mockLoginUser: vi.fn(),
  mockLogoutUser: vi.fn(),
  mockLogoutAllDevices: vi.fn(),
}))

vi.mock('@/lib/firebase-lazy', () => ({
  firebaseAuthLazy: mockFirebaseAuth,
}))

vi.mock('@/lib/websocket', () => ({
  wsManager: mockWsManager,
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient,
}))

vi.mock('@/services/firebase-auth', () => ({
  loginUser: mockLoginUser,
  logoutUser: mockLogoutUser,
  logoutAllDevices: mockLogoutAllDevices,
  setSessionId: vi.fn(),
  clearSessionId: vi.fn(),
}))

vi.mock('@/hooks/use-toast', () => ({
  toast: vi.fn(),
}))

vi.mock('@/config/mock.config', () => ({
  isMockAuthEnabled: () => false,
}))

vi.mock('@/lib/mock-auth-service', () => ({
  default: {
    hasPermission: vi.fn(),
    hasRole: vi.fn(),
    getCurrentUser: vi.fn(),
    getSession: vi.fn(),
    signIn: vi.fn(),
    signOut: vi.fn(),
  },
}))

describe('AuthContext (canonical)', () => {
  const mockUser = {
    id: 'user-1',
    email: 'admin@example.com',
    full_name: 'Admin',
    role: 'admin',
    permissions: ['users:read'],
    is_active: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  )

  beforeEach(() => {
    vi.clearAllMocks()

    mockApiClient.fetchCsrfToken.mockResolvedValue(undefined)
    mockApiClient.dashboard.getMain.mockResolvedValue(undefined)
    mockApiClient.auth.me.mockResolvedValue({ data: mockUser })
    mockApiClient.auth.checkAuth.mockResolvedValue({ authenticated: false, user: null })
    mockWsManager.connect.mockResolvedValue(undefined)
    mockWsManager.disconnect.mockResolvedValue(undefined)

    mockFirebaseAuth.isConfigured.mockReturnValue(true)
    mockFirebaseAuth.getCurrentUser.mockResolvedValue({
      getIdToken: vi.fn().mockResolvedValue('firebase-token'),
    })
    mockFirebaseAuth.onAuthStateChanged.mockImplementation(async (handler: (user: unknown) => void) => {
      await handler(null)
      return () => {}
    })
    mockFirebaseAuth.onIdTokenChanged.mockResolvedValue(() => {})
    mockFirebaseAuth.setPersistence.mockResolvedValue(undefined)
    mockFirebaseAuth.signOut.mockResolvedValue(undefined)

    mockLoginUser.mockResolvedValue({ user: mockUser, session_id: 'session-abc' })
    mockLogoutUser.mockResolvedValue(undefined)
    mockLogoutAllDevices.mockResolvedValue({ sessions_deleted: 1 })

    vi.spyOn(safeLocalStorage, 'setItem')
    vi.spyOn(safeLocalStorage, 'removeItem')
  })

  it('throws when useAuth is called outside provider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => renderHook(() => useAuth())).toThrow('useAuth must be used within an AuthProvider')
    consoleSpy.mockRestore()
  })

  it('restores authenticated state from backend session check', async () => {
    mockApiClient.auth.checkAuth.mockResolvedValue({
      authenticated: true,
      user: mockUser,
      sessionId: 'session-restored',
    })

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isInitializing).toBe(false)
      expect(result.current.isAuthenticated).toBe(true)
    })

    expect(result.current.user?.id).toBe(mockUser.id)
    expect(mockApiClient.auth.checkAuth).toHaveBeenCalled()
    expect(mockApiClient.setAuthToken).toHaveBeenCalledWith('session-restored')
  })

  it('performs login using firebase-auth service and persists session id', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isInitializing).toBe(false)
    })

    await act(async () => {
      await result.current.login('admin@example.com', 'secret123', true)
    })

    expect(mockLoginUser).toHaveBeenCalledWith('admin@example.com', 'secret123')
    expect(mockFirebaseAuth.setPersistence).toHaveBeenCalledWith(true)
    expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
    expect(safeLocalStorage.setItem).toHaveBeenCalledWith('session_id', 'session-abc')
  })

  it('keeps user unauthenticated when login fails', async () => {
    mockLoginUser.mockRejectedValueOnce(new Error('Invalid credentials'))

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isInitializing).toBe(false)
    })

    let thrownError: unknown
    await act(async () => {
      try {
        await result.current.login('admin@example.com', 'wrong-password')
      } catch (error) {
        thrownError = error
      }
    })

    expect(thrownError).toBeInstanceOf(Error)
    expect((thrownError as Error).message).toBe('Invalid credentials')
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
  })

  it('performs logout and clears local session data', async () => {
    mockApiClient.auth.checkAuth.mockResolvedValue({
      authenticated: true,
      user: mockUser,
      sessionId: 'session-logout',
    })

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    await act(async () => {
      result.current.logout()
    })

    await waitFor(() => {
      expect(mockLogoutUser).toHaveBeenCalled()
    })

    expect(mockWsManager.disconnect).toHaveBeenCalled()
    expect(safeLocalStorage.removeItem).toHaveBeenCalledWith('session_id')
  })

  it('invalidates all sessions via logoutAll and clears local session data', async () => {
    mockApiClient.auth.checkAuth.mockResolvedValue({
      authenticated: true,
      user: mockUser,
      sessionId: 'session-xyz',
    })

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    await act(async () => {
      await result.current.logoutAll()
    })

    expect(mockLogoutAllDevices).toHaveBeenCalled()
    expect(mockWsManager.disconnect).toHaveBeenCalled()
    expect(safeLocalStorage.removeItem).toHaveBeenCalledWith('session_id')
  })
})
