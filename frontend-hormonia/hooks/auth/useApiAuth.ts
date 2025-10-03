import { useState, useCallback } from 'react'
import { apiClient } from '../../lib/api-client'
import { wsManager } from '../../lib/websocket'
import { User, LoginResponse, AuthTokens, AuthError } from './types'
import { useAuthRetry } from './useAuthRetry'

interface LoginCredentials {
  email: string
  password: string
}

interface UseApiAuthOptions {
  autoConnectWebSocket?: boolean
  persistTokens?: boolean
}

export function useApiAuth({
  autoConnectWebSocket = true,
  persistTokens = true
}: UseApiAuthOptions = {}) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<AuthError | null>(null)

  const { executeWithRetry, createAuthError } = useAuthRetry({
    onRetryFailed: (error, attempts) => {
      console.error(`API auth failed after ${attempts} attempts:`, error)
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
    const deprecated = createAuthError('Local API authentication is disabled. Use Supabase Auth.', 'api_auth_deprecated', false)
    setError(deprecated)
    throw deprecated
  }, [createAuthError])

  const refreshAuth = useCallback(async (_refreshTokenOverride?: string): Promise<LoginResponse> => {
    const deprecated = createAuthError('Local API token refresh is disabled. Supabase handles session refresh.', 'api_refresh_deprecated', false)
    setError(deprecated)
    throw deprecated
  }, [createAuthError])

  const loadUser = useCallback(async (): Promise<User> => {
    setLoading(true)
    setError(null)

{{ ... }}

      setLoading(false)
    }
  }, [token, clearTokens, setAuthToken])

  const restoreSession = useCallback(async (): Promise<boolean> => {
    return false
  }, [])

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