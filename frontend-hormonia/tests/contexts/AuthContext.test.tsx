import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { User } from '@/hooks/auth/types'

// Mock Firebase
vi.mock('@/lib/firebase-lazy', () => ({
  firebaseAuthLazy: {
    signInWithEmailAndPassword: vi.fn(),
    signOut: vi.fn(),
    currentUser: null,
    onAuthStateChanged: vi.fn()
  }
}))

// Mock API Client
vi.mock('@/lib/api-client', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
    setAuthToken: vi.fn(),
    clearAuthToken: vi.fn()
  }
}))

// Mock WebSocket
vi.mock('@/lib/websocket', () => ({
  wsManager: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    setAuthToken: vi.fn()
  }
}))

// Mock Toast
vi.mock('@/hooks/use-toast', () => ({
  toast: vi.fn()
}))

describe('AuthContext', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    })
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  const createWrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  )

  describe('Authentication Flow', () => {
    it('should start with unauthenticated state', () => {
      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      expect(result.current.user).toBeNull()
      expect(result.current.session).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.isLoading).toBe(true) // Initially loading
    })

    it('should authenticate user with Firebase successfully', async () => {
      const mockUser: User = {
        id: 'test-user-id',
        email: 'admin@test.com',
        full_name: 'Test Admin',
        role: 'admin',
        permissions: ['users:read', 'users:write', 'admin:access'],
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }

      const mockFirebaseUser = {
        uid: 'test-user-id',
        email: 'admin@test.com',
        getIdToken: vi.fn().mockResolvedValue('mock-firebase-token')
      }

      const mockSession = {
        access_token: 'mock-access-token',
        session_id: 'mock-session-id'
      }

      // Mock Firebase auth
      const { firebaseAuthLazy } = await import('@/lib/firebase-lazy')
      vi.mocked(firebaseAuthLazy.signInWithEmailAndPassword).mockResolvedValue({
        user: mockFirebaseUser
      } as any)

      // Mock API response
      const { apiClient } = await import('@/lib/api-client')
      vi.mocked(apiClient.post).mockResolvedValue({
        user: mockUser,
        session: mockSession
      })

      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      await act(async () => {
        await result.current.login('admin@test.com', 'password123')
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
      })

      expect(result.current.user).toEqual(mockUser)
      expect(result.current.session).toEqual(mockSession)
      expect(result.current.user?.email).toBe('admin@test.com')
      expect(result.current.user?.role).toBe('admin')
    })

    it('should handle login failure gracefully', async () => {
      const { firebaseAuthLazy } = await import('@/lib/firebase-lazy')
      vi.mocked(firebaseAuthLazy.signInWithEmailAndPassword).mockRejectedValue(
        new Error('Invalid credentials')
      )

      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      await act(async () => {
        try {
          await result.current.login('invalid@test.com', 'wrongpassword')
        } catch (error) {
          expect(error).toBeInstanceOf(Error)
        }
      })

      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBeNull()
    })

    it('should logout user correctly', async () => {
      // First login
      const mockUser: User = {
        id: 'test-user-id',
        email: 'test@test.com',
        full_name: 'Test User',
        role: 'user',
        permissions: ['users:read'],
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }

      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      // Mock successful login
      await act(async () => {
        // Simulate user being set (normally done by Firebase auth state change)
        result.current.user = mockUser
        result.current.session = { access_token: 'token', session_id: 'session' }
      })

      // Mock Firebase signOut
      const { firebaseAuthLazy } = await import('@/lib/firebase-lazy')
      vi.mocked(firebaseAuthLazy.signOut).mockResolvedValue()

      // Logout
      await act(async () => {
        result.current.logout()
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false)
      })

      expect(result.current.user).toBeNull()
      expect(result.current.session).toBeNull()
    })
  })

  describe('Permission System', () => {
    it('should check permissions correctly for admin user', () => {
      const mockAdminUser: User = {
        id: 'admin-id',
        email: 'admin@test.com',
        full_name: 'Admin User',
        role: 'admin',
        permissions: [
          'users:read',
          'users:write',
          'users:delete',
          'admin:access',
          'reports:read',
          'system:manage'
        ],
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }

      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      // Set user directly for testing
      act(() => {
        // @ts-ignore - Setting for test purposes
        result.current.user = mockAdminUser
      })

      // Test various permissions
      expect(result.current.hasPermission('users:read')).toBe(true)
      expect(result.current.hasPermission('users:write')).toBe(true)
      expect(result.current.hasPermission('admin:access')).toBe(true)
      expect(result.current.hasPermission('invalid:permission')).toBe(false)
      expect(result.current.hasPermission('super:admin')).toBe(false)
    })

    it('should check permissions correctly for regular user', () => {
      const mockRegularUser: User = {
        id: 'user-id',
        email: 'user@test.com',
        full_name: 'Regular User',
        role: 'user',
        permissions: ['users:read', 'profile:edit'],
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }

      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      act(() => {
        // @ts-ignore - Setting for test purposes
        result.current.user = mockRegularUser
      })

      expect(result.current.hasPermission('users:read')).toBe(true)
      expect(result.current.hasPermission('profile:edit')).toBe(true)
      expect(result.current.hasPermission('users:write')).toBe(false)
      expect(result.current.hasPermission('admin:access')).toBe(false)
    })

    it('should return false for permissions when user is null', () => {
      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      expect(result.current.hasPermission('users:read')).toBe(false)
      expect(result.current.hasPermission('admin:access')).toBe(false)
    })
  })

  describe('Role System', () => {
    it('should check roles correctly', () => {
      const mockUser: User = {
        id: 'user-id',
        email: 'user@test.com',
        full_name: 'Test User',
        role: 'admin',
        permissions: [],
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }

      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      act(() => {
        // @ts-ignore - Setting for test purposes
        result.current.user = mockUser
      })

      expect(result.current.hasRole('admin')).toBe(true)
      expect(result.current.hasRole('user')).toBe(false)
      expect(result.current.hasRole('medico')).toBe(false)
    })

    it('should return false for roles when user is null', () => {
      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      expect(result.current.hasRole('admin')).toBe(false)
      expect(result.current.hasRole('user')).toBe(false)
    })
  })

  describe('Token Management', () => {
    it('should refresh token successfully', async () => {
      const mockUser: User = {
        id: 'user-id',
        email: 'user@test.com',
        full_name: 'Test User',
        role: 'user',
        permissions: [],
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }

      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      // Mock Firebase getIdToken
      const mockFirebaseUser = {
        getIdToken: vi.fn().mockResolvedValue('new-firebase-token')
      }

      // Mock API response
      const { apiClient } = await import('@/lib/api-client')
      vi.mocked(apiClient.post).mockResolvedValue({
        access_token: 'new-access-token',
        session_id: 'new-session-id'
      })

      act(() => {
        // @ts-ignore - Setting for test purposes
        result.current.user = mockUser
        result.current.session = { access_token: 'old-token', session_id: 'old-session' }
      })

      await act(async () => {
        await result.current.refreshToken()
      })

      // Verify API was called
      expect(apiClient.post).toHaveBeenCalledWith('/auth/refresh', {
        firebase_token: 'new-firebase-token'
      })
    })

    it('should get Firebase token successfully', async () => {
      const mockFirebaseUser = {
        getIdToken: vi.fn().mockResolvedValue('firebase-token')
      }

      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      // Mock Firebase current user
      const { firebaseAuthLazy } = await import('@/lib/firebase-lazy')
      // @ts-ignore
      firebaseAuthLazy.currentUser = mockFirebaseUser

      const token = await result.current.getFirebaseToken()
      expect(token).toBe('firebase-token')
    })

    it('should return null when no Firebase user', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      const token = await result.current.getFirebaseToken()
      expect(token).toBeNull()
    })
  })

  describe('Logout All Sessions', () => {
    it('should logout from all sessions successfully', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      // Mock API response
      const { apiClient } = await import('@/lib/api-client')
      vi.mocked(apiClient.post).mockResolvedValue({ success: true })

      // Mock Firebase signOut
      const { firebaseAuthLazy } = await import('@/lib/firebase-lazy')
      vi.mocked(firebaseAuthLazy.signOut).mockResolvedValue()

      await act(async () => {
        await result.current.logoutAll()
      })

      expect(apiClient.post).toHaveBeenCalledWith('/auth/logout-all')
      expect(firebaseAuthLazy.signOut).toHaveBeenCalled()
    })
  })

  describe('Error Handling', () => {
    it('should handle network errors during login', async () => {
      const { firebaseAuthLazy } = await import('@/lib/firebase-lazy')
      vi.mocked(firebaseAuthLazy.signInWithEmailAndPassword).mockRejectedValue(
        new Error('Network error')
      )

      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      await expect(
        act(async () => {
          await result.current.login('test@test.com', 'password')
        })
      ).rejects.toThrow('Network error')

      expect(result.current.isAuthenticated).toBe(false)
    })

    it('should handle API errors during token refresh', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper: createWrapper })

      // Mock API error
      const { apiClient } = await import('@/lib/api-client')
      vi.mocked(apiClient.post).mockRejectedValue(new Error('API Error'))

      await expect(
        act(async () => {
          await result.current.refreshToken()
        })
      ).rejects.toThrow('API Error')
    })
  })
})