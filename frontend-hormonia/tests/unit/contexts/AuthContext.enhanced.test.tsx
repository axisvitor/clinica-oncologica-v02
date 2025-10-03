/**
 * Comprehensive AuthContext Tests
 * Tests authentication, session management, and authorization
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { AuthProvider, useAuth } from '@/src/contexts/AuthContext'
import { createMockSupabaseAuth, mockUser, mockSession, mockSupabaseUser } from '../../test-utils'
import * as supabaseClient from '@/src/lib/supabase-client'
import * as apiClientModule from '@/src/lib/api-client'

// Mock modules
vi.mock('@/src/lib/supabase-client', () => ({
  auth: createMockSupabaseAuth(),
  realtimeManager: {
    unsubscribeAll: vi.fn()
  }
}))

vi.mock('@/src/lib/api-client', () => ({
  apiClient: {
    auth: {
      me: vi.fn(),
      logout: vi.fn()
    },
    setAuthToken: vi.fn(),
    setSupabaseToken: vi.fn()
  }
}))

describe('AuthContext - Comprehensive Tests', () => {
  const mockAuth = supabaseClient.auth as ReturnType<typeof createMockSupabaseAuth>
  const mockApiClient = apiClientModule.apiClient

  beforeEach(() => {
    vi.clearAllMocks()
    // Reset default mock implementations
    mockAuth.getCurrentSession.mockResolvedValue(mockSession)
    mockAuth.getCurrentUser.mockResolvedValue(mockSupabaseUser)
    ;(mockApiClient.auth.me as any).mockResolvedValue({
      data: {
        id: mockUser.id,
        email: mockUser.email,
        fullName: mockUser.full_name,
        role: mockUser.role,
        isActive: mockUser.is_active,
        permissions: mockUser.permissions,
        createdAt: mockUser.created_at
      }
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Hook Usage', () => {
    it('should throw error when used outside AuthProvider', () => {
      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      expect(() => {
        renderHook(() => useAuth())
      }).toThrow('useAuth must be used within an AuthProvider')

      consoleSpy.mockRestore()
    })

    it('should provide auth context when used within AuthProvider', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current).toBeDefined()
        expect(result.current.isLoading).toBe(false)
      })
    })
  })

  describe('Initial Authentication State', () => {
    it('should start with loading state', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      expect(result.current.isLoading).toBe(true)
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBe(null)
    })

    it('should initialize authenticated user from session', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.isAuthenticated).toBe(true)
      expect(result.current.user).toEqual(expect.objectContaining({
        id: mockUser.id,
        email: mockUser.email
      }))
      expect(result.current.session).toBe(mockSession)
    })

    it('should handle no existing session', async () => {
      mockAuth.getCurrentSession.mockResolvedValue(null)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBe(null)
      expect(result.current.session).toBe(null)
    })

    it('should handle initialization timeout gracefully', async () => {
      mockAuth.getCurrentSession.mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 5000))
      )

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      }, { timeout: 4000 })

      expect(result.current.user).toBe(null)
    })
  })

  describe('Login Function', () => {
    it('should login successfully with valid credentials', async () => {
      mockAuth.getCurrentSession.mockResolvedValue(null)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      await act(async () => {
        await result.current.login('test@example.com', 'password123')
      })

      expect(mockAuth.signIn).toHaveBeenCalledWith('test@example.com', 'password123')
      expect(mockApiClient.setSupabaseToken).toHaveBeenCalledWith(mockSession)
      expect(result.current.isAuthenticated).toBe(true)
    })

    it('should handle login failure', async () => {
      mockAuth.getCurrentSession.mockResolvedValue(null)
      mockAuth.signIn.mockRejectedValue(new Error('Invalid credentials'))

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      await expect(async () => {
        await act(async () => {
          await result.current.login('test@example.com', 'wrongpassword')
        })
      }).rejects.toThrow('Invalid credentials')

      expect(result.current.isAuthenticated).toBe(false)
      expect(mockApiClient.setAuthToken).toHaveBeenCalledWith(null)
    })

    it('should handle missing session after login', async () => {
      mockAuth.getCurrentSession.mockResolvedValue(null)
      mockAuth.signIn.mockResolvedValue({ user: mockSupabaseUser, session: null })

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      await expect(async () => {
        await act(async () => {
          await result.current.login('test@example.com', 'password123')
        })
      }).rejects.toThrow('Supabase did not return a session')
    })

    it('should fallback to Supabase user when API me() fails', async () => {
      mockAuth.getCurrentSession.mockResolvedValue(null)
      ;(mockApiClient.auth.me as any).mockRejectedValue(new Error('API error'))

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      await act(async () => {
        await result.current.login('test@example.com', 'password123')
      })

      expect(result.current.user).toEqual(expect.objectContaining({
        id: mockSupabaseUser.id,
        email: mockSupabaseUser.email
      }))
    })
  })

  describe('Logout Function', () => {
    it('should logout successfully', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
      })

      await act(async () => {
        await result.current.logout()
      })

      expect(mockAuth.signOut).toHaveBeenCalled()
      expect(mockApiClient.setAuthToken).toHaveBeenCalledWith(null)
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBe(null)
    })

    it('should clear state even if logout API call fails', async () => {
      ;(mockApiClient.auth.logout as any).mockRejectedValue(new Error('Network error'))

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
      })

      await act(async () => {
        await result.current.logout()
      })

      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBe(null)
    })
  })

  describe('Permission Checking', () => {
    it('should correctly check user permissions', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
      })

      expect(result.current.hasPermission('read:patients')).toBe(true)
      expect(result.current.hasPermission('write:patients')).toBe(true)
      expect(result.current.hasPermission('delete:all')).toBe(false)
    })

    it('should return false when user has no permissions', async () => {
      ;(mockApiClient.auth.me as any).mockResolvedValue({
        data: {
          ...mockUser,
          permissions: []
        }
      })

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
      })

      expect(result.current.hasPermission('read:patients')).toBe(false)
    })

    it('should return false when user is not authenticated', async () => {
      mockAuth.getCurrentSession.mockResolvedValue(null)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.hasPermission('read:patients')).toBe(false)
    })
  })

  describe('Role Checking', () => {
    it('should correctly check user role', async () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
      })

      expect(result.current.hasRole('admin')).toBe(true)
      expect(result.current.hasRole('user')).toBe(false)
      expect(result.current.hasRole('doctor')).toBe(false)
    })

    it('should return false when user has no role', async () => {
      ;(mockApiClient.auth.me as any).mockResolvedValue({
        data: {
          ...mockUser,
          role: null
        }
      })

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
      })

      expect(result.current.hasRole('admin')).toBe(false)
    })

    it('should return false when user is not authenticated', async () => {
      mockAuth.getCurrentSession.mockResolvedValue(null)

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.hasRole('admin')).toBe(false)
    })
  })

  describe('Auth State Change Listener', () => {
    it('should update state when auth state changes', async () => {
      let authStateCallback: Function = () => {}
      mockAuth.onAuthStateChange.mockImplementation((callback: Function) => {
        authStateCallback = callback
        return { data: { subscription: { unsubscribe: vi.fn() } } }
      })

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      const { result } = renderHook(() => useAuth(), { wrapper })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true)
      })

      // Simulate sign out event
      act(() => {
        authStateCallback('SIGNED_OUT', null)
      })

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBe(null)
      })
    })

    it('should update token when session changes', async () => {
      let authStateCallback: Function = () => {}
      mockAuth.onAuthStateChange.mockImplementation((callback: Function) => {
        authStateCallback = callback
        return { data: { subscription: { unsubscribe: vi.fn() } } }
      })

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      )

      renderHook(() => useAuth(), { wrapper })

      const newSession = { ...mockSession, access_token: 'new-token' }

      await act(async () => {
        await authStateCallback('TOKEN_REFRESHED', newSession)
      })

      await waitFor(() => {
        expect(mockApiClient.setSupabaseToken).toHaveBeenCalledWith(newSession)
      })
    })
  })
})