import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { createWrapperWithProviders, mockUser } from '../../test-utils'

// Mock dependencies
const mockFirebaseAuth = {
  onAuthStateChanged: vi.fn(),
  onIdTokenChanged: vi.fn(),
  getCurrentUser: vi.fn(),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  setPersistence: vi.fn(),
  isConfigured: vi.fn().mockReturnValue(true)
}

const mockApiClient = {
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  fetchCsrfToken: vi.fn(),
  auth: {
    me: vi.fn(),
    createSession: vi.fn(),
    checkAuth: vi.fn()
  },
  dashboard: {
    getMain: vi.fn()
  },
  getBaseURL: vi.fn().mockReturnValue('https://api.example.com'),
  getCsrfToken: vi.fn().mockReturnValue('csrf-token')
}

const mockWsManager = {
  connect: vi.fn(),
  disconnect: vi.fn(),
  updateToken: vi.fn()
}

const mockFirebaseAuthService = {
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  logoutAllDevices: vi.fn(),
  setSessionId: vi.fn(),
  clearSessionId: vi.fn()
}

const mockMockAuthService = {
  getCurrentUser: vi.fn(),
  getSession: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
  hasPermission: vi.fn(),
  hasRole: vi.fn()
}

const mockToast = vi.fn()

// Mock modules
vi.mock('@/lib/firebase-lazy', () => ({
  firebaseAuthLazy: mockFirebaseAuth
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient
}))

vi.mock('@/lib/websocket', () => ({
  wsManager: mockWsManager
}))

vi.mock('@/services/firebase-auth', () => mockFirebaseAuthService)

vi.mock('@/lib/mock-auth-service', () => ({
  default: mockMockAuthService
}))

vi.mock('@/hooks/use-toast', () => ({
  toast: mockToast
}))

vi.mock('@/config/mock.config', () => ({
  isMockAuthEnabled: vi.fn().mockReturnValue(false)
}))

const mockFirebaseUser = {
  uid: 'firebase-uid',
  email: 'test@example.com',
  getIdToken: vi.fn().mockResolvedValue('firebase-token')
}

describe('AuthContext - Comprehensive Tests', () => {
  let authStateChangeCallback: any
  let tokenChangeCallback: any

  beforeEach(() => {
    vi.clearAllMocks()

    // Setup Firebase auth state change mock
    mockFirebaseAuth.onAuthStateChanged.mockImplementation((callback) => {
      authStateChangeCallback = callback
      return vi.fn() // unsubscribe function
    })

    // Setup Firebase token change mock
    mockFirebaseAuth.onIdTokenChanged.mockImplementation((callback) => {
      tokenChangeCallback = callback
      return vi.fn() // unsubscribe function
    })

    mockApiClient.fetchCsrfToken.mockResolvedValue(undefined)
    mockApiClient.auth.me.mockResolvedValue({ data: mockUser })
    mockApiClient.auth.checkAuth.mockResolvedValue({ authenticated: false })
    mockApiClient.dashboard.getMain.mockResolvedValue({})
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Context Provider Setup', () => {
    it('should throw error when useAuth is used outside provider', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      expect(() => {
        renderHook(() => useAuth())
      }).toThrow('useAuth must be used within an AuthProvider')

      consoleSpy.mockRestore()
    })

    it('should provide all required context methods', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current).toHaveProperty('user')
      expect(result.current).toHaveProperty('session')
      expect(result.current).toHaveProperty('isAuthenticated')
      expect(result.current).toHaveProperty('isLoading')
      expect(result.current).toHaveProperty('login')
      expect(result.current).toHaveProperty('logout')
      expect(result.current).toHaveProperty('logoutAll')
      expect(result.current).toHaveProperty('hasPermission')
      expect(result.current).toHaveProperty('hasRole')
      expect(result.current).toHaveProperty('getFirebaseToken')
      expect(result.current).toHaveProperty('refreshToken')
    })

    it('should initialize with loading state', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.isLoading).toBe(true)
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
    })
  })

  describe('Firebase Authentication Flow', () => {
    it('should handle successful Firebase sign in', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      // Simulate Firebase auth state change
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
        expect(result.current.isAuthenticated).toBe(true)
        expect(result.current.user).toEqual(mockUser)
        expect(result.current.session?.websocketToken).toBe('firebase-token')
      })

      expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
    })

    it('should handle Firebase sign out', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      // First sign in
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      // Then sign out
      await act(async () => {
        await authStateChangeCallback(null)
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBe(null)
        expect(result.current.session).toBe(null)
      })

      expect(mockApiClient.setAuthToken).toHaveBeenCalledWith(null)
      expect(mockWsManager.disconnect).toHaveBeenCalled()
    })

    it('should handle backend validation failure during sign in', async () => {
      mockApiClient.auth.me.mockRejectedValue(new Error('Backend error'))

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBe(null)
      })

      expect(mockToast).toHaveBeenCalledWith({
        title: 'Sessão expirada',
        description: 'Sua sessão expirou. Por favor, faça login novamente.',
        variant: 'destructive'
      })
    })

    it('should handle token refresh', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      renderHook(() => useAuth(), { wrapper })

      const newToken = 'new-firebase-token'
      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)

      await act(async () => {
        await tokenChangeCallback(mockFirebaseUser)
      })

      expect(mockWsManager.updateToken).toHaveBeenCalledWith(newToken)
    })
  })

  describe('Login Function', () => {
    it('should handle successful login with Firebase', async () => {
      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })

      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.login('test@example.com', 'password', true)
      })

      expect(mockFirebaseAuth.setPersistence).toHaveBeenCalledWith(true)
      expect(mockFirebaseAuthService.loginUser).toHaveBeenCalledWith('test@example.com', 'password')
      expect(mockWsManager.connect).toHaveBeenCalledWith('firebase-token')
    })

    it('should handle login with remember me disabled', async () => {
      mockFirebaseAuthService.loginUser.mockResolvedValue({
        user: mockUser,
        session_id: 'session-123'
      })

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.login('test@example.com', 'password', false)
      })

      expect(mockFirebaseAuth.setPersistence).toHaveBeenCalledWith(false)
    })

    it('should handle login errors', async () => {
      const loginError = new Error('Invalid credentials')
      mockFirebaseAuthService.loginUser.mockRejectedValue(loginError)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await expect(
        act(async () => {
          await result.current.login('test@example.com', 'wrongpassword')
        })
      ).rejects.toThrow('Invalid credentials')

      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
    })

    it('should set loading state during login', async () => {
      let resolveLogin: any
      mockFirebaseAuthService.loginUser.mockReturnValue(
        new Promise(resolve => { resolveLogin = resolve })
      )

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      act(() => {
        result.current.login('test@example.com', 'password')
      })

      expect(result.current.isLoading).toBe(true)

      await act(async () => {
        resolveLogin({ user: mockUser, session_id: 'session-123' })
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })
    })
  })

  describe('Logout Functions', () => {
    it('should handle logout', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      // First sign in
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await act(async () => {
        await result.current.logout()
      })

      expect(mockFirebaseAuthService.logoutUser).toHaveBeenCalled()
      expect(mockWsManager.disconnect).toHaveBeenCalled()
    })

    it('should handle logoutAll', async () => {
      mockFirebaseAuthService.logoutAllDevices.mockResolvedValue({
        sessions_deleted: 3
      })

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logoutAll()
      })

      expect(mockFirebaseAuthService.logoutAllDevices).toHaveBeenCalled()
      expect(mockToast).toHaveBeenCalledWith({
        title: 'Logout realizado',
        description: 'Você foi desconectado de todos os dispositivos.',
        variant: 'default'
      })
    })

    it('should handle logout errors gracefully', async () => {
      mockFirebaseAuthService.logoutUser.mockRejectedValue(new Error('Network error'))

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logout()
      })

      // Should still clear state even if logout fails
      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
      expect(mockWsManager.disconnect).toHaveBeenCalled()
    })
  })

  describe('Permission and Role Management', () => {
    it('should check permissions correctly for authenticated user', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      // Sign in user
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.hasPermission('read:patients')).toBe(true)
        expect(result.current.hasPermission('write:patients')).toBe(true)
        expect(result.current.hasPermission('nonexistent')).toBe(false)
      })
    })

    it('should check roles correctly for authenticated user', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      // Sign in user
      await act(async () => {
        await authStateChangeCallback(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.hasRole('admin')).toBe(true)
        expect(result.current.hasRole('ADMIN')).toBe(true) // Case insensitive
        expect(result.current.hasRole('user')).toBe(false)
      })
    })

    it('should return false for permissions when no user', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.hasPermission('read:patients')).toBe(false)
      expect(result.current.hasRole('admin')).toBe(false)
    })
  })

  describe('Firebase Token Management', () => {
    it('should get Firebase token when user is authenticated', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      const token = await result.current.getFirebaseToken()

      expect(token).toBe('firebase-token')
      expect(mockFirebaseAuth.getCurrentUser).toHaveBeenCalled()
    })

    it('should return null when no user is authenticated', async () => {
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(null)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      const token = await result.current.getFirebaseToken()

      expect(token).toBe(null)
    })

    it('should refresh Firebase token', async () => {
      const newToken = 'refreshed-token'
      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)
      mockFirebaseAuth.getCurrentUser.mockResolvedValue(mockFirebaseUser)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.refreshToken()
      })

      expect(mockFirebaseUser.getIdToken).toHaveBeenCalledWith(true)
    })

    it('should handle token refresh errors', async () => {
      mockFirebaseAuth.getCurrentUser.mockRejectedValue(new Error('Token refresh failed'))

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await expect(
        act(async () => {
          await result.current.refreshToken()
        })
      ).rejects.toThrow('Token refresh failed')
    })
  })

  describe('Mock Authentication Mode', () => {
    beforeEach(() => {
      vi.mocked(require('@/config/mock.config').isMockAuthEnabled).mockReturnValue(true)
    })

    it('should use mock auth service when enabled', async () => {
      mockMockAuthService.getCurrentUser.mockReturnValue(mockUser)
      mockMockAuthService.getSession.mockReturnValue({ access_token: 'mock-token' })

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
        expect(result.current.user).toEqual(mockUser)
        expect(result.current.session?.access_token).toBe('mock-token')
      })
    })

    it('should handle mock login', async () => {
      mockMockAuthService.signIn.mockResolvedValue({
        success: true,
        user: mockUser,
        session: { access_token: 'mock-token' }
      })

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.login('test@example.com', 'password')
      })

      expect(mockMockAuthService.signIn).toHaveBeenCalledWith('test@example.com', 'password')
      expect(mockWsManager.connect).toHaveBeenCalledWith('mock-token')
    })

    it('should handle mock permissions', () => {
      mockMockAuthService.hasPermission.mockReturnValue(true)
      mockMockAuthService.hasRole.mockReturnValue(true)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.hasPermission('test')).toBe(true)
      expect(result.current.hasRole('admin')).toBe(true)
    })
  })

  describe('Firebase Configuration Handling', () => {
    it('should handle unconfigured Firebase gracefully', async () => {
      mockFirebaseAuth.isConfigured.mockReturnValue(false)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
        expect(result.current.isAuthenticated).toBe(false)
      })
    })
  })

  describe('Cleanup and Memory Management', () => {
    it('should cleanup subscriptions on unmount', () => {
      const unsubscribeAuth = vi.fn()
      const unsubscribeToken = vi.fn()

      mockFirebaseAuth.onAuthStateChanged.mockReturnValue(unsubscribeAuth)
      mockFirebaseAuth.onIdTokenChanged.mockReturnValue(unsubscribeToken)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { unmount } = renderHook(() => useAuth(), { wrapper })

      unmount()

      expect(unsubscribeAuth).toHaveBeenCalled()
      expect(unsubscribeToken).toHaveBeenCalled()
      expect(mockWsManager.disconnect).toHaveBeenCalled()
    })
  })
})
