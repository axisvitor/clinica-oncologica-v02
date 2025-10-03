import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from '../../../contexts/AuthContext'
import { createWrapperWithProviders, mockUser, mockSupabaseUser, mockSession } from '../../test-utils'

// Mock the Supabase client
const mockAuth = {
  onAuthStateChange: vi.fn(),
  getCurrentSession: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
}

const mockRealtimeManager = {
  unsubscribeAll: vi.fn(),
}

const mockApiClient = {
  setAuthToken: vi.fn(),
  setSupabaseToken: vi.fn(),
}

vi.mock('../../../lib/supabase-client', () => ({
  auth: mockAuth,
  realtimeManager: mockRealtimeManager,
}))

vi.mock('../../../lib/api-client', () => ({
  apiClient: mockApiClient,
}))

describe('AuthContext', () => {
  let mockSubscription: any

  beforeEach(() => {
    vi.clearAllMocks()

    // Mock subscription object
    mockSubscription = {
      unsubscribe: vi.fn(),
    }

    mockAuth.onAuthStateChange.mockReturnValue({
      data: { subscription: mockSubscription }
    })

    mockAuth.getCurrentSession.mockResolvedValue(mockSession)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('useAuth hook', () => {
    it('should throw error when used outside provider', () => {
      // Suppress console error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      expect(() => {
        renderHook(() => useAuth())
      }).toThrow('useAuth must be used within an AuthProvider')

      consoleSpy.mockRestore()
    })

    it('should return auth context when used within provider', () => {
      const wrapper = createWrapperWithProviders()

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current).toBeDefined()
      expect(typeof result.current.login).toBe('function')
      expect(typeof result.current.logout).toBe('function')
      expect(typeof result.current.hasPermission).toBe('function')
      expect(typeof result.current.hasRole).toBe('function')
    })
  })

  describe('AuthProvider initialization', () => {
    it('should initialize with loading state', () => {
      const wrapper = createWrapperWithProviders()

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.isLoading).toBe(true)
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBe(null)
    })

    it('should set up auth state change listener on mount', () => {
      const wrapper = createWrapperWithProviders()

      renderHook(() => useAuth(), { wrapper })

      expect(mockAuth.onAuthStateChange).toHaveBeenCalledWith(expect.any(Function))
    })

    it('should get current session on mount', async () => {
      const wrapper = createWrapperWithProviders()

      renderHook(() => useAuth(), { wrapper })

      expect(mockAuth.getCurrentSession).toHaveBeenCalled()
    })

    it('should clean up subscription on unmount', () => {
      const wrapper = createWrapperWithProviders()

      const { unmount } = renderHook(() => useAuth(), { wrapper })

      unmount()

      expect(mockSubscription.unsubscribe).toHaveBeenCalled()
    })
  })

  describe('authentication state management', () => {
    it('should handle SIGNED_IN event', async () => {
      let authStateHandler: any
      mockAuth.onAuthStateChange.mockImplementation((handler) => {
        authStateHandler = handler
        return { data: { subscription: mockSubscription } }
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler('SIGNED_IN', mockSession)
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
        expect(result.current.user).toEqual(mockUser)
        expect(result.current.session).toEqual(mockSession)
        expect(result.current.isLoading).toBe(false)
      })

      expect(mockApiClient.setSupabaseToken).toHaveBeenCalledWith(mockSession)
    })

    it('should handle SIGNED_OUT event', async () => {
      let authStateHandler: any
      mockAuth.onAuthStateChange.mockImplementation((handler) => {
        authStateHandler = handler
        return { data: { subscription: mockSubscription } }
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // First sign in
      await act(async () => {
        await authStateHandler('SIGNED_IN', mockSession)
      })

      // Then sign out
      await act(async () => {
        await authStateHandler('SIGNED_OUT', null)
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBe(null)
        expect(result.current.session).toBe(null)
      })

      expect(mockApiClient.setAuthToken).toHaveBeenCalledWith(null)
      expect(mockRealtimeManager.unsubscribeAll).toHaveBeenCalled()
    })
  })

  describe('login function', () => {
    it('should call supabase signIn', async () => {
      mockAuth.signIn.mockResolvedValue({ user: mockSupabaseUser, error: null })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.login('test@example.com', 'password')
      })

      expect(mockAuth.signIn).toHaveBeenCalledWith('test@example.com', 'password')
    })

    it('should handle login errors', async () => {
      const error = new Error('Invalid credentials')
      mockAuth.signIn.mockRejectedValue(error)

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await expect(
        act(async () => {
          await result.current.login('test@example.com', 'wrongpassword')
        })
      ).rejects.toThrow('Invalid credentials')
    })

    it('should set loading state during login', async () => {
      let resolveLogin: any
      mockAuth.signIn.mockReturnValue(
        new Promise(resolve => { resolveLogin = resolve })
      )

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      act(() => {
        result.current.login('test@example.com', 'password')
      })

      expect(result.current.isLoading).toBe(true)

      await act(async () => {
        resolveLogin({ user: mockSupabaseUser })
      })

      expect(result.current.isLoading).toBe(false)
    })
  })

  describe('logout function', () => {
    it('should call supabase signOut', async () => {
      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logout()
      })

      expect(mockAuth.signOut).toHaveBeenCalled()
    })

    it('should clear state on logout', async () => {
      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logout()
      })

      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
      expect(result.current.isAuthenticated).toBe(false)
      expect(mockApiClient.setAuthToken).toHaveBeenCalledWith(null)
      expect(mockRealtimeManager.unsubscribeAll).toHaveBeenCalled()
    })

    it('should handle logout errors gracefully', async () => {
      const error = new Error('Network error')
      mockAuth.signOut.mockRejectedValue(error)

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await result.current.logout()
      })

      // Should still clear state even if signOut fails
      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
      expect(result.current.isAuthenticated).toBe(false)
    })
  })

  describe('permission and role checking', () => {
    it('should check permissions correctly', () => {
      const wrapper = createWrapperWithProviders({
        user: mockUser,
        isAuthenticated: true
      })

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.hasPermission('read:patients')).toBe(true)
      expect(result.current.hasPermission('write:patients')).toBe(true)
      expect(result.current.hasPermission('nonexistent:permission')).toBe(false)
    })

    it('should check roles correctly', () => {
      const wrapper = createWrapperWithProviders({
        user: mockUser,
        isAuthenticated: true
      })

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.hasRole('admin')).toBe(true)
      expect(result.current.hasRole('user')).toBe(false)
    })

    it('should return false for permissions when no user', () => {
      const wrapper = createWrapperWithProviders({
        user: null,
        isAuthenticated: false
      })

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.hasPermission('read:patients')).toBe(false)
      expect(result.current.hasRole('admin')).toBe(false)
    })
  })

  describe('user conversion', () => {
    it('should convert supabase user to app user format', async () => {
      let authStateHandler: any
      mockAuth.onAuthStateChange.mockImplementation((handler) => {
        authStateHandler = handler
        return { data: { subscription: mockSubscription } }
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler('SIGNED_IN', mockSession)
      })

      await waitFor(() => {
        expect(result.current.user).toEqual({
          id: mockSupabaseUser.id,
          email: mockSupabaseUser.email,
          full_name: mockSupabaseUser.user_metadata['full_name'],
          role: mockSupabaseUser.user_metadata['role'],
          is_active: true,
          permissions: mockSupabaseUser.user_metadata['permissions'],
          created_at: mockSupabaseUser.created_at
        })
      })
    })

    it('should handle missing user metadata', async () => {
      const userWithoutMetadata = {
        ...mockSupabaseUser,
        user_metadata: {}
      }

      const sessionWithoutMetadata = {
        ...mockSession,
        user: userWithoutMetadata
      }

      let authStateHandler: any
      mockAuth.onAuthStateChange.mockImplementation((handler) => {
        authStateHandler = handler
        return { data: { subscription: mockSubscription } }
      })

      const wrapper = createWrapperWithProviders()
      const { result } = renderHook(() => useAuth(), { wrapper })

      await act(async () => {
        await authStateHandler('SIGNED_IN', sessionWithoutMetadata)
      })

      await waitFor(() => {
        expect(result.current.user).toEqual({
          id: userWithoutMetadata['id'],
          email: userWithoutMetadata['email'],
          full_name: userWithoutMetadata['email'],
          role: 'user',
          is_active: true,
          permissions: [],
          created_at: userWithoutMetadata.created_at
        })
      })
    })
  })
})