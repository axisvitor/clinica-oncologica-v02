import { useContext } from 'react'
import { AuthContext } from '@/contexts/AuthContext'
import { useSessionManagement } from './auth/useSessionManagement'
import { usePermissions } from './auth/usePermissions'
import { useAuthRetry } from './auth/useAuthRetry'

interface UseAuthOptions {
  onAuthEvent?: (event: any) => void
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
 * combining Firebase auth (via AuthContext), session management, and permissions
 *
 * This hook uses Firebase exclusively for authentication.
 */
export function useAuth(options: UseAuthOptions = {}) {
  // Get Firebase auth from AuthContext
  const auth = useContext(AuthContext)

  if (!auth) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  // Initialize auth retry with config
  const { executeWithRetry, isRetrying, retryCount, resetRetryState } = useAuthRetry(
    options.retryConfig ? { config: options.retryConfig } : {}
  )

  // Initialize permissions based on current user
  const permissions = usePermissions({ user: auth.user })

  // Initialize session management
  const sessionManagement = useSessionManagement({
    onRefreshNeeded: async () => {
      // Firebase handles token refresh automatically
      // This is a no-op as AuthContext already handles refresh
    },
    onSessionExpired: auth.logout,
    autoRefresh: true
  })

  return {
    // User and auth state from AuthContext
    user: auth.user,
    token: auth.session?.access_token || null,
    refreshToken: null, // Firebase handles refresh internally
    isAuthenticated: auth.isAuthenticated,
    isLoading: auth.isLoading,
    error: null,

    // Session data
    sessionData: sessionManagement.sessionData,
    isSessionExpiring: sessionManagement.isSessionExpiring,

    // Auth methods from AuthContext
    login: async (email: string, password: string) => {
      resetRetryState()
      return await auth.login(email, password)
    },
    logout: auth.logout,
    refreshAuth: async () => {
      // Firebase handles refresh automatically via AuthContext
      return null
    },
    signUp: async (_email: string, _password: string) => {
      throw new Error('Sign up must be handled through the backend API')
    },
    resetPassword: async (_email: string) => {
      throw new Error('Password reset must be handled through Firebase directly')
    },
    updatePassword: async (_newPassword: string) => {
      throw new Error('Password update must be handled through Firebase directly')
    },
    restoreSession: async () => {
      // Firebase/AuthContext handles session restoration automatically
      return auth.isAuthenticated
    },

    // Permission methods from usePermissions
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
    resetRetryState
  }
}
