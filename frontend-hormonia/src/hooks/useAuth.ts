import { useCallback, useMemo } from 'react'
import { useSupabaseAuth } from './auth/useSupabaseAuth'
import { useApiAuth } from './auth/useApiAuth'
import { useSessionManagement } from './auth/useSessionManagement'
import { usePermissions } from './auth/usePermissions'
import { useAuthRetry } from './auth/useAuthRetry'
import { AuthEventListener, User } from './auth/types'

interface UseAuthOptions {
  preferSupabase?: boolean
  onAuthEvent?: AuthEventListener
  autoConnectWebSocket?: boolean
  persistTokens?: boolean
  retryConfig?: {
    maxRetries?: number
    retryDelay?: number
    exponentialBackoff?: boolean
  }
}

/**
 * Main authentication hook that provides a unified interface
 * combining Supabase auth, API auth, session management, and permissions
 */
export function useAuth({
  preferSupabase = true,
  onAuthEvent,
  autoConnectWebSocket = true,
  persistTokens = true,
  retryConfig
}: UseAuthOptions = {}) {
  // Initialize auth retry with config
  const { executeWithRetry, isRetrying, retryCount, resetRetryState } = useAuthRetry(retryConfig ? { config: retryConfig } : {})

  // Initialize Supabase auth
  const supabaseAuth = useSupabaseAuth()

  // Initialize API auth
  const apiAuth = useApiAuth({
    autoConnectWebSocket,
    persistTokens
  })

  // Determine which user to use based on preference and availability
  const user: User | null = useMemo(() => {
    if (preferSupabase && supabaseAuth.user) {
      return supabaseAuth.convertToAppUser(supabaseAuth.user)
    }
    return apiAuth.user
  }, [preferSupabase, supabaseAuth.user, supabaseAuth.convertToAppUser, apiAuth.user])

  // Determine which token to use
  const token = useMemo(() => {
    if (preferSupabase && supabaseAuth.accessToken) {
      return supabaseAuth.accessToken
    }
    return apiAuth.token
  }, [preferSupabase, supabaseAuth.accessToken, apiAuth.token])

  const refreshToken = useMemo(() => {
    if (preferSupabase && supabaseAuth.refreshToken) {
      return supabaseAuth.refreshToken
    }
    return apiAuth.refreshToken
  }, [preferSupabase, supabaseAuth.refreshToken, apiAuth.refreshToken])

  // Initialize session management
  const sessionManagement = useSessionManagement({
    onRefreshNeeded: useCallback(async () => {
      if (preferSupabase && supabaseAuth.session) {
        await supabaseAuth.refreshSession()
      } else if (apiAuth.refreshToken) {
        await apiAuth.refreshAuth()
      }
    }, [preferSupabase, supabaseAuth.session, supabaseAuth.refreshSession, apiAuth.refreshToken, apiAuth.refreshAuth]),

    onSessionExpired: useCallback(() => {
      if (preferSupabase) {
        supabaseAuth.signOut()
      } else {
        apiAuth.logout()
      }
    }, [preferSupabase, supabaseAuth.signOut, apiAuth.logout]),

    autoRefresh: true
  })

  // Initialize permissions
  const permissions = usePermissions({ user })

  // Unified login method
  const login = useCallback(async (email: string, password: string) => {
    resetRetryState()

    if (preferSupabase) {
      return await supabaseAuth.signIn(email, password)
    } else {
      const result = await apiAuth.login({ email, password })

      // Update session management with token info
      if (result && 'expires_in' in result) {
        sessionManagement.updateSessionFromTokens(result as any)
      }

      return result
    }
  }, [preferSupabase, supabaseAuth.signIn, apiAuth.login, sessionManagement.updateSessionFromTokens, resetRetryState])

  // Unified logout method
  const logout = useCallback(async () => {
    sessionManagement.clearSession()

    if (preferSupabase) {
      await supabaseAuth.signOut()
    } else {
      await apiAuth.logout()
    }
  }, [preferSupabase, supabaseAuth.signOut, apiAuth.logout, sessionManagement.clearSession])

  // Unified refresh method
  const refreshAuth = useCallback(async () => {
    return await executeWithRetry(async () => {
      if (preferSupabase && supabaseAuth.session) {
        const result = await supabaseAuth.refreshSession()
        if (result?.session?.expires_at) {
          const expiresIn = result.session.expires_at - Math.floor(Date.now() / 1000)
          sessionManagement.updateSessionFromTokens({ expires_in: expiresIn } as any)
        }
        return result
      } else if (apiAuth.refreshToken) {
        const result = await apiAuth.refreshAuth()
        if (result && 'expires_in' in result) {
          sessionManagement.updateSessionFromTokens(result)
        }
        return result
      } else {
        throw new Error('No refresh token available')
      }
    }, 'auth refresh')
  }, [preferSupabase, supabaseAuth.session, supabaseAuth.refreshSession, apiAuth.refreshToken, apiAuth.refreshAuth, sessionManagement.updateSessionFromTokens, executeWithRetry])

  // Sign up method (primarily for Supabase)
  const signUp = useCallback(async (email: string, password: string) => {
    if (preferSupabase) {
      await supabaseAuth.signUp(email, password)
    } else {
      throw new Error('Sign up is only available with Supabase authentication')
    }
  }, [preferSupabase, supabaseAuth.signUp])

  // Password reset (primarily for Supabase)
  const resetPassword = useCallback(async (email: string) => {
    if (preferSupabase) {
      return await supabaseAuth.resetPassword(email)
    }
    throw new Error('Password reset is only available with Supabase authentication')
  }, [preferSupabase, supabaseAuth.resetPassword])

  // Update password (primarily for Supabase)
  const updatePassword = useCallback(async (newPassword: string) => {
    if (preferSupabase) {
      return await supabaseAuth.updatePassword(newPassword)
    }
    throw new Error('Password update is only available with Supabase authentication')
  }, [preferSupabase, supabaseAuth.updatePassword])

  // Restore session on app start
  const restoreSession = useCallback(async () => {
    if (preferSupabase) {
      // Supabase handles this automatically
      return supabaseAuth.isAuthenticated
    } else {
      const restored = await apiAuth.restoreSession()
      if (restored && sessionManagement.restoreSessionFromStorage()) {
        return true
      }
      return false
    }
  }, [preferSupabase, supabaseAuth.isAuthenticated, apiAuth.restoreSession, sessionManagement.restoreSessionFromStorage])

  // Compute loading state
  const isLoading = useMemo(() => {
    if (preferSupabase) {
      return supabaseAuth.loading
    }
    return apiAuth.loading
  }, [preferSupabase, supabaseAuth.loading, apiAuth.loading])

  // Compute error state
  const error = useMemo(() => {
    if (preferSupabase) {
      return supabaseAuth.error
    }
    return apiAuth.error
  }, [preferSupabase, supabaseAuth.error, apiAuth.error])

  // Compute authentication state
  const isAuthenticated = useMemo(() => {
    if (preferSupabase) {
      return supabaseAuth.isAuthenticated
    }
    return apiAuth.isAuthenticated
  }, [preferSupabase, supabaseAuth.isAuthenticated, apiAuth.isAuthenticated])

  return {
    // User and auth state
    user,
    token,
    refreshToken,
    isAuthenticated,
    isLoading,
    error,

    // Session data
    sessionData: sessionManagement.sessionData,
    isSessionExpiring: sessionManagement.isSessionExpiring,

    // Auth methods
    login,
    logout,
    refreshAuth,
    signUp,
    resetPassword,
    updatePassword,
    restoreSession,

    // Permission methods
    hasPermission: permissions.hasPermission,
    hasRole: permissions.hasRole,
    hasAnyRole: permissions.hasAnyRole,
    hasAllPermissions: permissions.hasAllPermissions,
    hasAnyPermission: permissions.hasAnyPermission,
    isAdmin: permissions.isAdmin,
    isSuperAdmin: permissions.isSuperAdmin,
    canAccessResource: permissions.canAccessResource,
    getPermissionLevel: permissions.getPermissionLevel,

    // Permission data
    permissionConfig: permissions.permissionConfig,
    permissionSummary: permissions.permissionSummary,

    // Retry state
    isRetrying,
    retryCount,
    resetRetryState,

    // Raw auth providers (for advanced use cases)
    supabaseAuth: supabaseAuth.authData,
    apiAuth: {
      user: apiAuth.user,
      token: apiAuth.token,
      loading: apiAuth.loading,
      error: apiAuth.error
    },

    // Configuration
    preferSupabase
  }
}