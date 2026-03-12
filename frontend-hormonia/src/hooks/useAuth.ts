import { useContext } from 'react'
import { AuthContext } from '@/app/providers/AuthContext'
import { apiClient } from '@/lib/api-client'
import { usePermissions } from './auth/usePermissions'
import { useAuthRetry } from './auth/useAuthRetry'

interface UseAuthOptions {
  onAuthEvent?: (event: React.MouseEvent) => void
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
 * for the session-first browser auth flow plus permissions helpers.
 */
export function useAuth(options: UseAuthOptions = {}) {
  const auth = useContext(AuthContext)

  if (!auth) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  const {
    executeWithRetry: _executeWithRetry,
    isRetrying,
    retryCount,
    resetRetryState,
  } = useAuthRetry(options.retryConfig ? { config: options.retryConfig } : {})

  const permissions = usePermissions({ user: auth.user })
  const sessionToken = auth.session?.session_id || auth.session?.access_token || null
  const websocketToken = auth.session?.websocketToken || sessionToken

  return {
    user: auth.user,
    token: sessionToken,
    websocketToken,
    refreshToken: auth.refreshToken,
    isAuthenticated: auth.isAuthenticated,
    isLoading: auth.isInitializing,
    isInitializing: auth.isInitializing,
    isAuthenticating: auth.isAuthenticating,
    error: null,

    sessionData: auth.session,
    isSessionExpiring: false,

    login: async (email: string, password: string, rememberMe = false) => {
      resetRetryState()
      return await auth.login(email, password, rememberMe)
    },
    logout: auth.logout,
    refreshAuth: async () => {
      await auth.refreshToken()
      return null
    },
    signUp: async (_email: string, _password: string) => {
      throw new Error('Sign up must be handled through the backend API')
    },
    resetPassword: async (email: string) => {
      return await apiClient.auth.requestPasswordReset({ email })
    },
    updatePassword: async (_newPassword: string) => {
      throw new Error('Password update requires the routed reset-confirm flow token contract')
    },
    restoreSession: async () => {
      await auth.refreshToken()
      return auth.isAuthenticated
    },

    hasPermission: permissions.hasPermission,
    hasRole: permissions.hasRole,
    hasAnyRole: permissions.hasAnyRole,
    hasAllPermissions: permissions.hasAllPermissions,
    hasAnyPermission: permissions.hasAnyPermission,
    isAdmin: permissions.isAdmin,
    isSuperAdmin: permissions.isSuperAdmin,
    canAccessResource: permissions.canAccessResource,
    getPermissionLevel: permissions.getPermissionLevel,

    permissionConfig: permissions.permissionConfig,
    permissionSummary: permissions.permissionSummary,

    isRetrying,
    retryCount,
    resetRetryState,
  }
}
