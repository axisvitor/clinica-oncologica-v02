import { useState, useCallback } from 'react'
import { apiClient } from '../../lib/api-client'
import { wsManager } from '../../lib/websocket'
import { User, LoginResponse, AuthTokens, AuthError } from './types'
import { useAuthRetry } from './useAuthRetry'
import { createLogger } from '../../lib/logger'

const logger = createLogger('useApiAuth')

interface LoginCredentials {
  email: string
  password: string
}

interface UseApiAuthOptions {
  autoConnectWebSocket?: boolean
  persistTokens?: boolean
}

/**
 * @deprecated Use useMedicoAuth from contexts/MedicoAuthContext instead
 * This hook is kept for backward compatibility only with legacy code.
 *
 * Firebase Authentication is now the primary authentication method for medicos.
 * API-based authentication has been deprecated in favor of Supabase/Firebase.
 *
 * Migration Guide:
 * - Replace `useApiAuth()` with `useMedicoAuth()` from MedicoAuthContext
 * - Use `signIn(email, password)` instead of `login(credentials)`
 * - Use `signOut()` instead of `logout()`
 * - Token management is now handled automatically by Firebase
 */
export function useApiAuth({
  autoConnectWebSocket = true,
  persistTokens = true
}: UseApiAuthOptions = {}) {
  logger.warn('DEPRECATED: This hook is deprecated. Use useMedicoAuth from MedicoAuthContext instead.')
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<AuthError | null>(null)

  const { executeWithRetry, createAuthError } = useAuthRetry({
    onRetryFailed: (error, attempts) => {
      logger.error(`API auth failed after ${attempts} attempts:`, error)
      // Emit a custom event for auth failures if needed
    }
  })

  const storeTokens = useCallback((tokens: AuthTokens) => {
    if (persistTokens) {
      localStorage.setItem('access_token', tokens.access_token)
      if (tokens.refresh_token) {
        localStorage.setItem('refresh_token', tokens.refresh_token)
      }
    }
  }, [persistTokens])

  const clearTokens = useCallback(() => {
    if (persistTokens) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('session_expiry')
    }
  }, [persistTokens])
  const setAuthToken = useCallback((authToken: string | null) => {
    setToken(authToken)
    apiClient.setAuthToken(authToken)
  }, [])

  const login = useCallback(async (_credentials: LoginCredentials): Promise<LoginResponse> => {
    // Supabase-only mode: API-based login is deprecated
    const deprecated = createAuthError('Local API authentication is disabled. Use Supabase Auth.', 'api_auth_deprecated', false)
    setError(deprecated)
    throw deprecated
  }, [createAuthError])

  const refreshAuth = useCallback(async (_refreshTokenOverride?: string): Promise<LoginResponse> => {
    // Supabase handles refresh automatically on the client
    const deprecated = createAuthError('Local API token refresh is disabled. Supabase handles session refresh.', 'api_refresh_deprecated', false)
    setError(deprecated)
    throw deprecated
  }, [createAuthError])

  const loadUser = useCallback(async (): Promise<User> => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiClient.auth.me()
      if (!result || !result.data) {
        throw createAuthError('Failed to load user data', 'load_user_failed')
      }
      const u: User = {
        id: result.data['id'],
        email: result.data['email'],
        full_name: result.data['full_name'],
        role: result.data['role'],
        is_active: result.data['is_active'],
        permissions: result.data['permissions'] || [],
        created_at: result.data.created_at
      }
      setUser(u)
      return u
    } catch (err) {
      const authError = err as AuthError
      setError(authError)
      throw authError
    } finally {
      setLoading(false)
    }
  }, [createAuthError])

  const logout = useCallback(async () => {
    setLoading(true)
    try {
      if (token) {
        try {
          await apiClient.auth.logout()
        } catch {
          // ignore server errors
        }
      }
    } finally {
      clearTokens()
      setAuthToken(null)
      setRefreshToken(null)
      setUser(null)
      setError(null)
      setLoading(false)
    }
  }, [token, clearTokens, setAuthToken])

  const restoreSession = useCallback(async (): Promise<boolean> => {
    // API-based session restore disabled in Supabase-only mode
    return false
  }, [])

  return {
    // State
    user,
    token,
    refreshToken,
    loading,
    error,
    isAuthenticated: !!user && !!token,

    // Actions
    login,
    logout,
    refreshAuth,
    loadUser,
    restoreSession,

    // Utilities
    setAuthToken,
    clearTokens,
    storeTokens
  }
}