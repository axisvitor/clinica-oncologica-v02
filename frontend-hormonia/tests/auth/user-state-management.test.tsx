/**
 * Comprehensive User State Management Tests
 * Coverage target: >85% of user state and session management
 * Tests user data persistence, state updates, and session lifecycle
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from '../../src/contexts/AuthContext'
import { createWrapperWithProviders } from '../test-utils'
import { firebaseAuth } from '../../src/lib/firebase-client'
import { apiClient } from '../../src/lib/api-client'
import { wsManager } from '../../src/lib/websocket'
import * as firebaseAuthService from '../../src/services/firebase-auth'

// Mock dependencies
vi.mock('../../src/services/firebase-auth')
vi.mock('../../src/lib/firebase-client')
vi.mock('../../src/lib/api-client')
vi.mock('../../src/lib/websocket')
vi.mock('../../src/config/mock.config', () => ({
  isMockAuthEnabled: vi.fn(() => false),
}))

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

// Mock sessionStorage
const sessionStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
Object.defineProperty(window, 'sessionStorage', {
  value: sessionStorageMock,
})

describe('User State Management Comprehensive Tests', () => {
  const mockUser = {
    id: 'user-123',
    email: 'test@example.com',
    full_name: 'Test User',
    role: 'user',
    permissions: ['read:basic', 'write:own'],
    is_active: true,
    created_at: '2023-01-01T00:00:00Z',
  }

  const mockFirebaseUser = {
    uid: 'firebase-123',
    email: 'test@example.com',
    getIdToken: vi.fn().mockResolvedValue('firebase-token-123'),
  }

  const mockSession = {
    access_token: 'firebase-token-123',
    session_id: 'session-456',
  }

  let mockUnsubscribe: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.getItem.mockReturnValue(null)
    sessionStorageMock.getItem.mockReturnValue(null)

    mockUnsubscribe = vi.fn()

    // Setup Firebase Auth mocks
    vi.mocked(firebaseAuth.isConfigured).mockReturnValue(true)
    vi.mocked(firebaseAuth.onAuthStateChange).mockReturnValue(mockUnsubscribe)
    vi.mocked(firebaseAuth.onIdTokenChanged).mockReturnValue(mockUnsubscribe)
    vi.mocked(firebaseAuth.getCurrentUser).mockResolvedValue(mockFirebaseUser)
    vi.mocked(firebaseAuth.setPersistence).mockResolvedValue()

    // Setup API client mock
    vi.mocked(apiClient.auth.me).mockResolvedValue({ data: mockUser })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('User State Initialization', () => {
    it('should initialize with empty state', () => {
      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.isLoading).toBe(true)
    })

    it('should initialize from existing Firebase session', async () => {
      let authStateHandler: any
      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Simulate existing Firebase session
      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser)
        expect(result.current.session?.access_token).toBe('firebase-token-123')
        expect(result.current.isAuthenticated).toBe(true)
        expect(result.current.isLoading).toBe(false)
      })
    })

    it('should handle initialization errors gracefully', async () => {
      vi.mocked(apiClient.auth.me).mockRejectedValue(new Error('Network error'))
      vi.mocked(firebaseAuth.signOut).mockResolvedValue()

      let authStateHandler: any
      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.user).toBe(null)
        expect(result.current.session).toBe(null)
        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.isLoading).toBe(false)
      })

      expect(firebaseAuth.signOut).toHaveBeenCalled()
    })
  })

  describe('User Data Persistence', () => {
    it('should persist user data during session', async () => {
      let authStateHandler: any
      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser)
        expect(result.current.session).toEqual({
          access_token: 'firebase-token-123',
        })
      })

      // Verify user data persists across re-renders
      const { result: newResult } = renderHook(() => useAuth(), { wrapper })
      expect(newResult.current.user).toEqual(mockUser)
    })

    it('should clear user data on logout', async () => {
      vi.mocked(firebaseAuthService.logoutUser).mockResolvedValue(undefined)

      const wrapper = createWrapperWithProviders({
        user: mockUser,
        session: mockSession,
        isAuthenticated: true,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logout()
      })

      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
      expect(result.current.isAuthenticated).toBe(false)
    })

    it('should handle session expiration', async () => {
      vi.mocked(apiClient.auth.me).mockRejectedValue(new Error('Session expired'))
      vi.mocked(firebaseAuth.signOut).mockResolvedValue()

      let authStateHandler: any
      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.user).toBe(null)
        expect(result.current.session).toBe(null)
        expect(result.current.isAuthenticated).toBe(false)
      })

      expect(firebaseAuth.signOut).toHaveBeenCalled()
    })
  })

  describe('User State Updates', () => {
    it('should update user state on successful login', async () => {
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

      expect(result.current.user).toEqual(mockUser)
      expect(result.current.session?.session_id).toBe('cookie')
      expect(result.current.isAuthenticated).toBe(true)
    })

    it('should update token on Firebase token refresh', async () => {
      const newToken = 'refreshed-token-789'
      let tokenRefreshHandler: any

      vi.mocked(firebaseAuth.onIdTokenChanged).mockImplementation((handler) => {
        tokenRefreshHandler = handler
        return mockUnsubscribe
      })

      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)

      const wrapper = createWrapperWithProviders({
        user: mockUser,
        session: mockSession,
        isAuthenticated: true,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await tokenRefreshHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.session?.access_token).toBe(newToken)
      })

      expect(apiClient.setAuthToken).toHaveBeenCalledWith(newToken)
      expect(wsManager.updateToken).toHaveBeenCalledWith(newToken)
    })

    it('should handle user profile updates', async () => {
      const updatedUser = {
        ...mockUser,
        full_name: 'Updated Name',
        permissions: [...mockUser.permissions, 'write:advanced'],
      }

      vi.mocked(apiClient.auth.me).mockResolvedValue({ data: updatedUser })

      let authStateHandler: any
      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.user?.full_name).toBe('Updated Name')
        expect(result.current.user?.permissions).toContain('write:advanced')
      })
    })
  })

  describe('Permission and Role State Management', () => {
    it('should update permission checks when user permissions change', async () => {
      const userWithLimitedPermissions = {
        ...mockUser,
        permissions: ['read:basic'],
      }

      vi.mocked(apiClient.auth.me).mockResolvedValue({ data: userWithLimitedPermissions })

      let authStateHandler: any
      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.hasPermission('read:basic')).toBe(true)
        expect(result.current.hasPermission('write:own')).toBe(false)
        expect(result.current.hasPermission('admin:full')).toBe(false)
      })
    })

    it('should update role checks when user role changes', async () => {
      const adminUser = {
        ...mockUser,
        role: 'admin',
        permissions: ['admin:full', 'read:all', 'write:all'],
      }

      vi.mocked(apiClient.auth.me).mockResolvedValue({ data: adminUser })

      let authStateHandler: any
      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.hasRole('admin')).toBe(true)
        expect(result.current.hasRole('user')).toBe(false)
        expect(result.current.hasPermission('admin:full')).toBe(true)
      })
    })

    it('should handle case-insensitive role comparisons', () => {
      const wrapper = createWrapperWithProviders({
        user: { ...mockUser, role: 'ADMIN' },
        isAuthenticated: true,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.hasRole('admin')).toBe(true)
      expect(result.current.hasRole('Admin')).toBe(true)
      expect(result.current.hasRole('ADMIN')).toBe(true)
    })

    it('should return false for permissions when user is null', () => {
      const wrapper = createWrapperWithProviders({
        user: null,
        isAuthenticated: false,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.hasPermission('read:basic')).toBe(false)
      expect(result.current.hasRole('user')).toBe(false)
    })
  })

  describe('Session Lifecycle Management', () => {
    it('should establish session on successful authentication', async () => {
      let authStateHandler: any
      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.session).toEqual({
          access_token: 'firebase-token-123',
        })
      })

      expect(apiClient.setAuthToken).toHaveBeenCalledWith('firebase-token-123')
      expect(wsManager.connect).toHaveBeenCalledWith('firebase-token-123')
    })

    it('should manage token lifecycle correctly', async () => {
      const wrapper = createWrapperWithProviders({
        user: mockUser,
        session: mockSession,
        isAuthenticated: true,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Test getting current token
      const token = await result.current.getFirebaseToken()
      expect(token).toBe('firebase-token-123')

      // Test force refresh
      const newToken = 'force-refreshed-token'
      mockFirebaseUser.getIdToken.mockResolvedValue(newToken)

      await act(async () => {
        await result.current.refreshToken()
      })

      expect(mockFirebaseUser.getIdToken).toHaveBeenCalledWith(true)
      expect(apiClient.setAuthToken).toHaveBeenCalledWith(newToken)
    })

    it('should cleanup session on logout', async () => {
      vi.mocked(firebaseAuthService.logoutUser).mockResolvedValue(undefined)

      const wrapper = createWrapperWithProviders({
        user: mockUser,
        session: mockSession,
        isAuthenticated: true,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logout()
      })

      expect(result.current.session).toBe(null)
      expect(apiClient.setAuthToken).toHaveBeenCalledWith(null)
      expect(wsManager.disconnect).toHaveBeenCalled()
    })

    it('should cleanup all sessions on logout all devices', async () => {
      const logoutAllResponse = { sessions_deleted: 5 }
      vi.mocked(firebaseAuthService.logoutAllDevices).mockResolvedValue(logoutAllResponse)

      const wrapper = createWrapperWithProviders({
        user: mockUser,
        session: mockSession,
        isAuthenticated: true,
      })
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logoutAll()
      })

      expect(result.current.session).toBe(null)
      expect(firebaseAuthService.logoutAllDevices).toHaveBeenCalled()
      expect(wsManager.disconnect).toHaveBeenCalled()
    })
  })

  describe('State Synchronization', () => {
    it('should synchronize state across multiple auth context instances', async () => {
      let authStateHandler: any
      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper1 = createWrapperWithProviders()
      const wrapper2 = createWrapperWithProviders()

      const { result: result1 } = renderHook(() => useAuth(), { wrapper: wrapper1 })
      const { result: result2 } = renderHook(() => useAuth(), { wrapper: wrapper2 })

      // Both should start unauthenticated
      expect(result1.current.isAuthenticated).toBe(false)
      expect(result2.current.isAuthenticated).toBe(false)

      // Authenticate in first instance
      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      // Both should be authenticated (Firebase handles global state)
      await waitFor(() => {
        expect(result1.current.isAuthenticated).toBe(true)
        expect(result2.current.isAuthenticated).toBe(true)
      })
    })

    it('should handle concurrent authentication attempts', async () => {
      vi.mocked(firebaseAuthService.loginUser).mockImplementation(
        () => new Promise(resolve =>
          setTimeout(() => resolve({
            user: mockUser,
            session_id: 'cookie',
          }), 100)
        )
      )

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Start two concurrent login attempts
      const login1 = result.current.login('test@example.com', 'password123')
      const login2 = result.current.login('test@example.com', 'password123')

      await act(async () => {
        await Promise.all([login1, login2])
      })

      // Should handle gracefully without conflicts
      expect(result.current.user).toEqual(mockUser)
      expect(result.current.isAuthenticated).toBe(true)
    })
  })

  describe('Error Recovery', () => {
    it('should recover from transient authentication errors', async () => {
      vi.mocked(apiClient.auth.me)
        .mockRejectedValueOnce(new Error('Network timeout'))
        .mockResolvedValue({ data: mockUser })

      vi.mocked(firebaseAuth.signOut).mockResolvedValue()

      let authStateHandler: any
      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // First attempt fails
      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false)
      })

      // Second attempt succeeds
      vi.mocked(firebaseAuth.signOut).mockClear()
      await act(async () => {
        await authStateHandler(mockFirebaseUser)
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
        expect(result.current.user).toEqual(mockUser)
      })
    })

    it('should maintain state consistency during errors', async () => {
      const loginError = new Error('Invalid credentials')
      vi.mocked(firebaseAuthService.loginUser).mockRejectedValue(loginError)

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      try {
        await act(async () => {
          await result.current.login('test@example.com', 'wrongpassword')
        })
      } catch {
        // Expected error
      }

      // State should remain consistent
      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.isLoading).toBe(false)
    })
  })

  describe('Memory Management', () => {
    it('should cleanup listeners and subscriptions on unmount', () => {
      const wrapper = createWrapperWithProviders()
      const { unmount } = renderHook(() => useAuth(), { wrapper })

      unmount()

      expect(mockUnsubscribe).toHaveBeenCalledTimes(2) // Auth state + token refresh
      expect(wsManager.disconnect).toHaveBeenCalled()
    })

    it('should not cause memory leaks with frequent state updates', async () => {
      let authStateHandler: any
      let tokenRefreshHandler: any

      vi.mocked(firebaseAuth.onAuthStateChange).mockImplementation((handler) => {
        authStateHandler = handler
        return mockUnsubscribe
      })

      vi.mocked(firebaseAuth.onIdTokenChanged).mockImplementation((handler) => {
        tokenRefreshHandler = handler
        return mockUnsubscribe
      })

      const wrapper = createWrapperWithProviders()
      renderHook(() => useAuth(), { wrapper })

      // Simulate frequent state changes
      for (let i = 0; i < 10; i++) {
        await act(async () => {
          await authStateHandler(mockFirebaseUser)
        })

        await act(async () => {
          await tokenRefreshHandler(mockFirebaseUser)
        })
      }

      // Should handle without memory issues
      expect(mockUnsubscribe).toHaveBeenCalledTimes(2)
    })
  })
})