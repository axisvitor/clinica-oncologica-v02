import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuth } from '@/hooks/useAuth'
import * as AuthContext from '@/contexts/AuthContext'
import { usePermissions } from '@/hooks/auth/usePermissions'
import { useAuthRetry } from '@/hooks/auth/useAuthRetry'

// Mock the dependencies
vi.mock('@/contexts/AuthContext')
vi.mock('@/hooks/auth/usePermissions')
vi.mock('@/hooks/auth/useAuthRetry')

describe('useAuth', () => {
  const mockAuthContext = {
    user: {
      id: '1',
      email: 'test@example.com',
      role: 'user',
      token: 'mock-token'
    },
    session: {
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token'
    },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn()
  }

  const mockPermissions = {
    hasPermission: vi.fn(),
    hasRole: vi.fn(),
    hasAnyRole: vi.fn(),
    hasAllPermissions: vi.fn(),
    hasAnyPermission: vi.fn(),
    isAdmin: vi.fn(),
    isSuperAdmin: vi.fn(),
    canAccessResource: vi.fn(),
    getPermissionLevel: vi.fn(),
    permissionConfig: {},
    permissionSummary: {}
  }

  const mockAuthRetry = {
    executeWithRetry: vi.fn(),
    isRetrying: false,
    retryCount: 0,
    resetRetryState: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()

    // Mock useContext to return our mock auth context
    vi.mocked(AuthContext.useContext).mockReturnValue(mockAuthContext)
    vi.mocked(usePermissions).mockReturnValue(mockPermissions)
    vi.mocked(useAuthRetry).mockReturnValue(mockAuthRetry)
  })

  describe('Initialization', () => {
    it('should throw error when used outside AuthProvider', () => {
      vi.mocked(AuthContext.useContext).mockReturnValue(null)

      expect(() => {
        renderHook(() => useAuth())
      }).toThrow('useAuth must be used within an AuthProvider')
    })

    it('should initialize with default options', () => {
      const { result } = renderHook(() => useAuth())

      expect(result.current.user).toEqual(mockAuthContext.user)
      expect(result.current.isAuthenticated).toBe(true)
      expect(result.current.isLoading).toBe(false)
    })

    it('should initialize with custom options', () => {
      const options = {
        onAuthEvent: vi.fn(),
        autoConnectWebSocket: false,
        persistTokens: false,
        retryConfig: {
          maxRetries: 3,
          retryDelay: 1000,
          exponentialBackoff: true
        }
      }

      renderHook(() => useAuth(options))

      expect(useAuthRetry).toHaveBeenCalledWith({ config: options.retryConfig })
    })
  })

  describe('User and Authentication State', () => {
    it('should return user information from AuthContext', () => {
      const { result } = renderHook(() => useAuth())

      expect(result.current.user).toEqual(mockAuthContext.user)
      expect(result.current.token).toBe('mock-access-token')
      expect(result.current.refreshToken).toBeNull() // Firebase handles refresh internally
      expect(result.current.isAuthenticated).toBe(true)
      expect(result.current.isLoading).toBe(false)
      expect(result.current.error).toBeNull()
    })

    it('should handle null session', () => {
      const contextWithoutSession = {
        ...mockAuthContext,
        session: null
      }
      vi.mocked(AuthContext.useContext).mockReturnValue(contextWithoutSession)

      const { result } = renderHook(() => useAuth())

      expect(result.current.token).toBeNull()
    })

    it('should return session state properties', () => {
      const { result } = renderHook(() => useAuth())

      expect(result.current.sessionData).toBeNull() // Firebase manages session internally
      expect(result.current.isSessionExpiring).toBe(false) // Firebase handles expiration
    })
  })

  describe('Authentication Methods', () => {
    it('should call login with retry state reset', async () => {
      const { result } = renderHook(() => useAuth())

      await act(async () => {
        await result.current.login('test@example.com', 'password')
      })

      expect(mockAuthRetry.resetRetryState).toHaveBeenCalled()
      expect(mockAuthContext.login).toHaveBeenCalledWith('test@example.com', 'password')
    })

    it('should call logout from AuthContext', () => {
      const { result } = renderHook(() => useAuth())

      act(() => {
        result.current.logout()
      })

      expect(mockAuthContext.logout).toHaveBeenCalled()
    })

    it('should handle refreshAuth appropriately for Firebase', async () => {
      const { result } = renderHook(() => useAuth())

      const refreshResult = await act(async () => {
        return await result.current.refreshAuth()
      })

      expect(refreshResult).toBeNull() // Firebase handles refresh automatically
    })

    it('should throw error for unsupported signUp', async () => {
      const { result } = renderHook(() => useAuth())

      await expect(async () => {
        await result.current.signUp('test@example.com', 'password')
      }).rejects.toThrow('Sign up must be handled through the backend API')
    })

    it('should throw error for unsupported resetPassword', async () => {
      const { result } = renderHook(() => useAuth())

      await expect(async () => {
        await result.current.resetPassword('test@example.com')
      }).rejects.toThrow('Password reset must be handled through Firebase directly')
    })

    it('should throw error for unsupported updatePassword', async () => {
      const { result } = renderHook(() => useAuth())

      await expect(async () => {
        await result.current.updatePassword('newpassword')
      }).rejects.toThrow('Password update must be handled through Firebase directly')
    })

    it('should handle session restoration', async () => {
      const { result } = renderHook(() => useAuth())

      const restoreResult = await act(async () => {
        return await result.current.restoreSession()
      })

      expect(restoreResult).toBe(true) // Returns current authentication state
    })
  })

  describe('Permission Methods', () => {
    it('should delegate permission methods to usePermissions', () => {
      const { result } = renderHook(() => useAuth())

      // Test all permission methods are available
      expect(typeof result.current.hasPermission).toBe('function')
      expect(typeof result.current.hasRole).toBe('function')
      expect(typeof result.current.hasAnyRole).toBe('function')
      expect(typeof result.current.hasAllPermissions).toBe('function')
      expect(typeof result.current.hasAnyPermission).toBe('function')
      expect(typeof result.current.isAdmin).toBe('function')
      expect(typeof result.current.isSuperAdmin).toBe('function')
      expect(typeof result.current.canAccessResource).toBe('function')
      expect(typeof result.current.getPermissionLevel).toBe('function')
    })

    it('should return permission data', () => {
      const { result } = renderHook(() => useAuth())

      expect(result.current.permissionConfig).toEqual(mockPermissions.permissionConfig)
      expect(result.current.permissionSummary).toEqual(mockPermissions.permissionSummary)
    })

    it('should call hasPermission with correct arguments', () => {
      const { result } = renderHook(() => useAuth())

      act(() => {
        result.current.hasPermission('read:patients')
      })

      expect(mockPermissions.hasPermission).toHaveBeenCalledWith('read:patients')
    })

    it('should call hasRole with correct arguments', () => {
      const { result } = renderHook(() => useAuth())

      act(() => {
        result.current.hasRole('admin')
      })

      expect(mockPermissions.hasRole).toHaveBeenCalledWith('admin')
    })
  })

  describe('Retry State Management', () => {
    it('should return retry state from useAuthRetry', () => {
      const retryStateWithRetrying = {
        ...mockAuthRetry,
        isRetrying: true,
        retryCount: 2
      }
      vi.mocked(useAuthRetry).mockReturnValue(retryStateWithRetrying)

      const { result } = renderHook(() => useAuth())

      expect(result.current.isRetrying).toBe(true)
      expect(result.current.retryCount).toBe(2)
      expect(typeof result.current.resetRetryState).toBe('function')
    })

    it('should call resetRetryState', () => {
      const { result } = renderHook(() => useAuth())

      act(() => {
        result.current.resetRetryState()
      })

      expect(mockAuthRetry.resetRetryState).toHaveBeenCalled()
    })
  })

  describe('Hook Dependencies', () => {
    it('should initialize usePermissions with current user', () => {
      renderHook(() => useAuth())

      expect(usePermissions).toHaveBeenCalledWith({ user: mockAuthContext.user })
    })

    it('should initialize useAuthRetry with empty config by default', () => {
      renderHook(() => useAuth())

      expect(useAuthRetry).toHaveBeenCalledWith({})
    })

    it('should pass retry config to useAuthRetry when provided', () => {
      const retryConfig = {
        maxRetries: 5,
        retryDelay: 2000,
        exponentialBackoff: false
      }

      renderHook(() => useAuth({ retryConfig }))

      expect(useAuthRetry).toHaveBeenCalledWith({ config: retryConfig })
    })
  })

  describe('Error Handling', () => {
    it('should handle login errors gracefully', async () => {
      const loginError = new Error('Login failed')
      mockAuthContext.login.mockRejectedValue(loginError)

      const { result } = renderHook(() => useAuth())

      await expect(async () => {
        await result.current.login('test@example.com', 'wrongpassword')
      }).rejects.toThrow('Login failed')
    })

    it('should maintain consistent state during errors', () => {
      const contextWithError = {
        ...mockAuthContext,
        isAuthenticated: false,
        user: null,
        isLoading: false
      }
      vi.mocked(AuthContext.useContext).mockReturnValue(contextWithError)

      const { result } = renderHook(() => useAuth())

      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBeNull()
      expect(result.current.isLoading).toBe(false)
    })
  })

  describe('Loading States', () => {
    it('should handle loading state from AuthContext', () => {
      const loadingContext = {
        ...mockAuthContext,
        isLoading: true,
        isAuthenticated: false,
        user: null
      }
      vi.mocked(AuthContext.useContext).mockReturnValue(loadingContext)

      const { result } = renderHook(() => useAuth())

      expect(result.current.isLoading).toBe(true)
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBeNull()
    })
  })

  describe('Integration with Options', () => {
    it('should handle all option parameters without errors', () => {
      const mockOnAuthEvent = vi.fn()
      const options = {
        onAuthEvent: mockOnAuthEvent,
        autoConnectWebSocket: true,
        persistTokens: true,
        retryConfig: {
          maxRetries: 10,
          retryDelay: 5000,
          exponentialBackoff: true
        }
      }

      const { result } = renderHook(() => useAuth(options))

      // Should not throw and should return valid auth object
      expect(result.current).toBeDefined()
      expect(typeof result.current.login).toBe('function')
      expect(typeof result.current.logout).toBe('function')
    })
  })
})