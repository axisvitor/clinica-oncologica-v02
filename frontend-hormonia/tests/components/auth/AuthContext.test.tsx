import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { safeLocalStorage } from '@/app/providers/AuthContext'
import {
  mockUser,
  mockSession,
  mockFirebaseUser,
  createMockFirebaseAuth
} from '../../test-utils'

const mockFirebaseAuth = createMockFirebaseAuth()
const mockWsManager = {
  connect: vi.fn(),
  disconnect: vi.fn(),
  updateToken: vi.fn()
}
const mockApiClient = {
  auth: {
    me: vi.fn()
  },
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  fetchCsrfToken: vi.fn()
}
const mockLoginUser = vi.fn()
const mockLogoutAllDevices = vi.fn()

vi.mock('../../../lib/firebase-lazy', () => ({
  firebaseAuthLazy: mockFirebaseAuth
}))

vi.mock('../../../lib/websocket', () => ({
  wsManager: mockWsManager
}))

vi.mock('../../../lib/api-client', () => ({
  apiClient: mockApiClient
}))

vi.mock('../../../services/firebase-auth', () => ({
  loginUser: mockLoginUser,
  logoutAllDevices: mockLogoutAllDevices
}))

vi.mock('../../../hooks/use-toast', () => ({
  toast: vi.fn()
}))

describe('AuthContext (Firebase)', () => {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  )

  beforeEach(() => {
    vi.clearAllMocks()

    mockApiClient.auth.me.mockResolvedValue({ data: mockUser })
    mockFirebaseAuth.isConfigured.mockReturnValue(true)
    mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser as any)
      ; (mockFirebaseUser.getIdToken as unknown as ReturnType<typeof vi.fn>).mockResolvedValue('firebase-token')
    mockFirebaseAuth.onAuthStateChanged.mockImplementation(async (handler: (user: any) => void) => {
      await handler(mockFirebaseUser as any)
      return () => { }
    })
    mockFirebaseAuth.onIdTokenChanged.mockResolvedValue(() => { })
    mockFirebaseAuth.signOut.mockResolvedValue({ error: null })
    mockLoginUser.mockResolvedValue({ user: mockUser, session_id: 'session-abc' })
    mockLogoutAllDevices.mockResolvedValue({ sessions_deleted: 1 })
    vi.spyOn(safeLocalStorage, 'setItem')
    vi.spyOn(safeLocalStorage, 'removeItem')
  })

  it('throws when useAuth is called outside provider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { })
    expect(() => renderHook(() => useAuth())).toThrow('useAuth must be used within an AuthProvider')
    consoleSpy.mockRestore()
  })

  it('initializes with authenticated user when Firebase session exists', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user?.id).toBe(mockUser.id)
    expect(mockApiClient.auth.me).toHaveBeenCalled()
  })

  it('performs login using Firebase + backend session', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper })

    await act(async () => {
      await result.current.login('admin@example.com', 'secret123', true)
    })

    expect(mockLoginUser).toHaveBeenCalledWith('admin@example.com', 'secret123')
    expect(mockFirebaseAuth.setPersistence).toHaveBeenCalledWith(true)
    expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
    expect(safeLocalStorage.setItem).toHaveBeenCalledWith('session_id', 'session-abc')
  })

  it('signs out and clears session data', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    await act(async () => {
      await result.current.logout()
    })

    expect(mockFirebaseAuth.signOut).toHaveBeenCalled()
    expect(mockWsManager.disconnect).toHaveBeenCalled()
    expect(mockApiClient.clearAuthToken).toHaveBeenCalledTimes(2)
    expect(safeLocalStorage.removeItem).toHaveBeenCalledWith('session_id')
  })

  it('invalidates all sessions via logoutAll', async () => {
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
