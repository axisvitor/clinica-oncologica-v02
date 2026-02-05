/**
 * Comprehensive Firebase Authentication Tests
 * Coverage target: >85% of Firebase authentication functionality
 * Tests Firebase integration, token management, and session handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, renderHook, act, waitFor } from '@testing-library/react'
import { useAuth } from '@/contexts/AuthContext'
import { createWrapperWithProviders, mockUser } from '../test-utils'
import * as firebaseAuthService from '@/services/firebase-auth'
import { firebaseAuthLazy } from '@/lib/firebase-lazy'
import { apiClient } from '@/lib/api-client'
import { wsManager } from '@/lib/websocket'

// Mock Firebase Auth Service
vi.mock('@/services/firebase-auth', () => ({
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  logoutAllDevices: vi.fn(),
}))

// Mock Firebase client
vi.mock('@/lib/firebase-lazy', () => ({
  firebaseAuthLazy: {
    isConfigured: vi.fn(() => true),
    onAuthStateChanged: vi.fn(),
    onIdTokenChanged: vi.fn(),
    getCurrentUser: vi.fn(),
    signOut: vi.fn(),
    setPersistence: vi.fn(),
  },
}))

// Mock WebSocket manager
vi.mock('@/lib/websocket', () => ({
  wsManager: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    updateToken: vi.fn(),
  },
}))

// Mock API client
vi.mock('@/lib/api-client', () => ({
  apiClient: {
    setAuthToken: vi.fn((token) => console.log('setAuthToken called with:', token)),
    clearAuthToken: vi.fn(),
    fetchCsrfToken: vi.fn(),
    auth: {
      me: vi.fn(),
      checkAuth: vi.fn(),
    },
    dashboard: {
      getMain: vi.fn(),
    },
  },
}))

// Mock config
vi.mock('@/config/mock.config', () => ({
  isMockAuthEnabled: vi.fn(() => false),
}))

describe('Firebase Authentication Comprehensive Tests', () => {
  let mockFirebaseUser: any
  let mockUnsubscribe: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()

    // Setup mock Firebase user
    mockFirebaseUser = {
      uid: 'firebase-user-123',
      email: 'test@example.com',
      getIdToken: vi.fn().mockResolvedValue('firebase-token-123'),
    }

    mockUnsubscribe = vi.fn()

    // Setup Firebase Auth mocks
    vi.mocked(firebaseAuthLazy.onAuthStateChanged).mockReturnValue(mockUnsubscribe)
    vi.mocked(firebaseAuthLazy.onIdTokenChanged).mockReturnValue(mockUnsubscribe)
    vi.mocked(firebaseAuthLazy.getCurrentUser).mockResolvedValue(mockFirebaseUser)
    vi.mocked(firebaseAuthLazy.setPersistence).mockResolvedValue()

    // Setup API client mock
    vi.mocked(apiClient.auth.me).mockResolvedValue({ data: mockUser })
    vi.mocked(apiClient.auth.checkAuth).mockResolvedValue({ authenticated: false })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
  })

  describe('Firebase Authentication Flow', () => {
    it('should handle Firebase authentication state changes', async () => {
      let authStateHandler: any
      vi.mocked(firebaseAuthLazy.onAuthStateChanged).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.isLoading).toBe(true)

      // Simulate Firebase auth state change
      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
        expect(result.current.isAuthenticated).toBe(true)
        expect(result.current.user).toEqual(mockUser)
        expect(result.current.session?.websocketToken).toBe('firebase-token-123')
      })

      expect(wsManager.connect).toHaveBeenCalledWith('firebase-token-123')
    })

    it('should handle Firebase token refresh', async () => {
      let tokenRefreshHandler: any
      let authStateHandler: any
      vi.mocked(firebaseAuthLazy.onAuthStateChanged).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      vi.mocked(firebaseAuthLazy.onIdTokenChanged).mockImplementation((handler) => {
        tokenRefreshHandler = handler
        return mockUnsubscribe
      })

      const newToken = 'refreshed-firebase-token-456'
      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Simulate token refresh
      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await act(async () => {
        await tokenRefreshHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.session?.websocketToken).toBe(newToken)
      })

      expect(wsManager.updateToken).toHaveBeenCalledWith(newToken)
    })

    it('should handle Firebase sign out', async () => {
      let authStateHandler: any
      vi.mocked(firebaseAuthLazy.onAuthStateChanged).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // First sign in
      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      // Then sign out
      await act(async () => {
        await authStateHandler(null)
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBe(null)
        expect(result.current.session).toBe(null)
      })

      expect(apiClient.setAuthToken).toHaveBeenCalledWith(null)
      expect(wsManager.disconnect).toHaveBeenCalled()
    })
  })

  describe('Login with Firebase Integration', () => {
    it('should login successfully with Firebase auth service', async () => {
      const loginResponse = {
        user: mockUser,
        session_id: 'cookie',
      }

      vi.mocked(firebaseAuthService.loginUser).mockResolvedValue(loginResponse)

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.login('test@example.com', 'password123')
      })

      expect(firebaseAuthService.loginUser).toHaveBeenCalledWith('test@example.com', 'password123')
      expect(result.current.user).toEqual(mockUser)
      expect(result.current.session?.session_id).toBe('cookie')
      expect(wsManager.connect).toHaveBeenCalledWith('firebase-token-123')
    })

    it('should set persistence correctly for remember me', async () => {
      vi.mocked(firebaseAuthService.loginUser).mockResolvedValue({
        user: mockUser,
        session_id: 'cookie',
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.login('test@example.com', 'password123', true)
      })

      expect(firebaseAuthLazy.setPersistence).toHaveBeenCalledWith(true)
    })

    it('should handle Firebase authentication errors', async () => {
      const authError = new Error('Firebase: Invalid credentials')
      vi.mocked(firebaseAuthService.loginUser).mockRejectedValue(authError)

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await expect(
        act(async () => {
          await result.current.login('test@example.com', 'wrongpassword')
        })
      ).rejects.toThrow('Firebase: Invalid credentials')

      await waitFor(() => {
        expect(result.current.user).toBe(null)
        expect(result.current.session).toBe(null)
        expect(apiClient.setAuthToken).toHaveBeenCalledWith(null)
      })
    })

    it('should handle persistence setting errors gracefully', async () => {
      const persistenceError = new Error('Persistence setting failed')
      vi.mocked(firebaseAuthLazy.setPersistence).mockRejectedValue(persistenceError)
      vi.mocked(firebaseAuthService.loginUser).mockResolvedValue({
        user: mockUser,
        session_id: 'cookie',
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Should not throw error, should continue with login
      await act(async () => {
        await result.current.login('test@example.com', 'password123', true)
      })

      expect(result.current.user).toEqual(mockUser)
    })
  })

  describe('Logout with Firebase Integration', () => {
    it('should logout successfully with Firebase auth service', async () => {
      vi.mocked(firebaseAuthService.logoutUser).mockResolvedValue(undefined)

      const wrapper = createWrapperWithProviders({
        user: mockUser,
        isAuthenticated: true,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logout()
      })

      expect(firebaseAuthService.logoutUser).toHaveBeenCalled()
      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
      expect(apiClient.setAuthToken).toHaveBeenCalledWith(null)
      expect(wsManager.disconnect).toHaveBeenCalled()
    })

    it('should logout from all devices', async () => {
      const logoutAllResponse = { sessions_deleted: 3 }
      vi.mocked(firebaseAuthService.logoutAllDevices).mockResolvedValue(logoutAllResponse)

      const wrapper = createWrapperWithProviders({
        user: mockUser,
        isAuthenticated: true,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logoutAll()
      })

      expect(firebaseAuthService.logoutAllDevices).toHaveBeenCalled()
      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
      expect(wsManager.disconnect).toHaveBeenCalled()
    })

    it('should handle logout errors gracefully', async () => {
      const logoutError = new Error('Logout failed')
      vi.mocked(firebaseAuthService.logoutUser).mockRejectedValue(logoutError)

      const wrapper = createWrapperWithProviders({
        user: mockUser,
        isAuthenticated: true,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logout()
      })

      // Should still clear state even on error
      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
      expect(apiClient.setAuthToken).toHaveBeenCalledWith(null)
      expect(wsManager.disconnect).toHaveBeenCalled()
    })
  })

  describe('Token Management', () => {
    it('should get Firebase token successfully', async () => {
      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      const token = await result.current.getFirebaseToken()

      expect(token).toBe('firebase-token-123')
      expect(firebaseAuthLazy.getCurrentUser).toHaveBeenCalled()
    })

    it('should return null when no Firebase user', async () => {
      vi.mocked(firebaseAuthLazy.getCurrentUser).mockResolvedValue(null)

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      const token = await result.current.getFirebaseToken()

      expect(token).toBe(null)
    })

    it('should refresh Firebase token successfully', async () => {
      const newToken = 'force-refreshed-token-789'
      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.refreshToken()
      })

      expect(mockFirebaseUser.getIdToken).toHaveBeenCalledWith(true)
    })

    it('should handle token refresh errors', async () => {
      const refreshError = new Error('Token refresh failed')
      mockFirebaseUser.getIdToken.mockRejectedValue(refreshError)

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await expect(
        act(async () => {
          await result.current.refreshToken()
        })
      ).rejects.toThrow('Token refresh failed')
    })
  })

  describe('Backend User Validation', () => {
    it('should handle backend user validation failure', async () => {
      // Backend rejects user
      vi.mocked(apiClient.auth.me).mockRejectedValue(new Error('Unauthorized'))
      vi.mocked(firebaseAuthLazy.signOut).mockResolvedValue({ error: null })

      let authStateHandler: any
      vi.mocked(firebaseAuthLazy.onAuthStateChanged).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBe(null)
      })

      expect(firebaseAuthLazy.signOut).toHaveBeenCalled()
      expect(wsManager.disconnect).toHaveBeenCalled()
    })

    it('should handle missing user data from backend', async () => {
      // Backend returns empty response
      vi.mocked(apiClient.auth.me).mockResolvedValue({ data: null })
      vi.mocked(firebaseAuthLazy.signOut).mockResolvedValue({ error: null })

      let authStateHandler: any
      vi.mocked(firebaseAuthLazy.onAuthStateChanged).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBe(null)
      })

      expect(firebaseAuthLazy.signOut).toHaveBeenCalled()
    })
  })

  describe('Firebase Configuration', () => {
    it('should handle Firebase not configured', async () => {
      vi.mocked(firebaseAuthLazy.isConfigured).mockReturnValue(false)

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
        expect(result.current.isAuthenticated).toBe(false)
      })

      expect(firebaseAuthLazy.onAuthStateChanged).not.toHaveBeenCalled()
    })

    it('should cleanup Firebase listeners on unmount', () => {
      const { unmount } = render(<AuthProvider><div></div></AuthProvider>)

      unmount()

      expect(mockUnsubscribe).toHaveBeenCalledTimes(2) // Both auth state and token refresh
      expect(wsManager.disconnect).toHaveBeenCalled()
    })
  })

  describe('WebSocket Integration', () => {
    it('should connect WebSocket on authentication', async () => {
      let authStateHandler: any
      vi.mocked(firebaseAuthLazy.onAuthStateChanged).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      expect(wsManager.connect).toHaveBeenCalledWith('firebase-token-123')
    })

    it('should disconnect WebSocket on logout', async () => {
      let authStateHandler: any
      vi.mocked(firebaseAuthLazy.onAuthStateChanged).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(null)
      })

      expect(wsManager.disconnect).toHaveBeenCalled()
    })

    it('should update WebSocket token on refresh', async () => {
      const newToken = 'updated-ws-token-456'
      let tokenRefreshHandler: any
      vi.mocked(firebaseAuthLazy.onIdTokenChanged).mockImplementation((handler) => {
        tokenRefreshHandler = handler
        return mockUnsubscribe
      })

      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)

      const wrapper = createWrapperWithProviders()
      renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await tokenRefreshHandler(mockFirebaseUser)
      })

      expect(wsManager.updateToken).toHaveBeenCalledWith(newToken)
    })
  })

  describe('Error Handling and Recovery', () => {
    it('should handle Firebase user transformation errors', async () => {
      mockFirebaseUser.getIdToken.mockRejectedValue(new Error('Token generation failed'))

      let authStateHandler: any
      vi.mocked(firebaseAuthLazy.onAuthStateChanged).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBe(null)
      })

      expect(apiClient.setAuthToken).toHaveBeenCalledWith(null)
      expect(wsManager.disconnect).toHaveBeenCalled()
    })

    it('should handle token refresh errors gracefully', async () => {
      const refreshError = new Error('Token refresh failed')
      let tokenRefreshHandler: any
      vi.mocked(firebaseAuthLazy.onIdTokenChanged).mockImplementation((handler) => {
        tokenRefreshHandler = handler
        return mockUnsubscribe
      })

      mockFirebaseUser.getIdToken.mockRejectedValue(refreshError)

      const wrapper = createWrapperWithProviders()
      renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await tokenRefreshHandler(mockFirebaseUser)
      })

      // Should not crash the application
      expect(wsManager.updateToken).not.toHaveBeenCalled()
    })

    it('should handle logout all devices errors', async () => {
      const logoutAllError = new Error('Logout all failed')
      vi.mocked(firebaseAuthService.logoutAllDevices).mockRejectedValue(logoutAllError)

      const wrapper = createWrapperWithProviders({
        user: mockUser,
        isAuthenticated: true,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      await expect(
        act(async () => {
          await result.current.logoutAll()
        })
      ).rejects.toThrow('Logout all failed')

      // Should still clear state even on error
      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
      expect(wsManager.disconnect).toHaveBeenCalled()
    })
  })

  describe('Loading States', () => {
    it('should show loading during login process', async () => {
      let resolveLogin: any
      vi.mocked(firebaseAuthService.loginUser).mockReturnValue(
        new Promise(resolve => { resolveLogin = resolve })
      )

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      act(() => {
        result.current.login('test@example.com', 'password123')
      })

      expect(result.current.isLoading).toBe(true)

      await act(async () => {
        resolveLogin({ user: mockUser, session_id: 'cookie' })
      })

      expect(result.current.isLoading).toBe(false)
    })

    it('should reset loading state on login error', async () => {
      vi.mocked(firebaseAuthService.loginUser).mockRejectedValue(new Error('Login failed'))

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      try {
        await act(async () => {
          await result.current.login('test@example.com', 'wrongpassword')
        })
      } catch {
        // Expected error
      }

      expect(result.current.isLoading).toBe(false)
    })
  })
})
