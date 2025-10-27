import React, { createContext, useContext, useEffect, useState, ReactNode, useCallback, useMemo } from 'react'
import { apiClient } from '../lib/api-client'
import { User } from '../hooks/auth/types'
import { isMockAuthEnabled } from '../config/mock.config'
import mockAuthService from '../lib/mock-auth-service'
import { firebaseAuthLazy } from '../lib/firebase-lazy'
import type { User as FirebaseUser } from 'firebase/auth'
import { wsManager } from '../lib/websocket'
import { createLogger } from '../lib/logger'
import { toast } from '../hooks/use-toast'
import * as firebaseAuthService from '../services/firebase-auth'

const logger = createLogger('AuthContext')

interface AuthContextType {
  user: User | null
  session: { access_token: string; session_id?: string } | null
  isAuthenticated: boolean
  isLoading: boolean // DEPRECATED: Use isInitializing instead
  isInitializing: boolean // Bootstrap/Firebase initialization
  isAuthenticating: boolean // Active login/logout operation
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>
  logout: () => void
  logoutAll: () => Promise<void>
  hasPermission: (permission: string) => boolean
  hasRole: (role: string) => boolean
  // WebSocket helpers
  getFirebaseToken: () => Promise<string | null>
  refreshToken: () => Promise<void>
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<{ access_token: string; session_id?: string } | null>(null)
  const [isInitializing, setIsInitializing] = useState(true) // Bootstrap phase
  const [isAuthenticating, setIsAuthenticating] = useState(false) // Active login/logout

  const isAuthenticated = !!user
  // DEPRECATED: Keep for backward compatibility, remove in next major version
  const isLoading = isInitializing

  // Permission and role checking functions
  const hasPermission = useCallback((permission: string): boolean => {
    if (isMockAuthEnabled()) {
      return mockAuthService.hasPermission(permission)
    }

    if (!user) {
      return false
    }

    const role = String(user['role'] ?? '').toLowerCase()
    if (role === 'admin') {
      return true
    }

    const rawPermissions = Array.isArray(user['permissions']) ? user['permissions'] : []
    if (rawPermissions.length === 0) {
      return false
    }

    const normalizedPermission = String(permission).toLowerCase()

    return rawPermissions.some(userPermission => {
      if (!userPermission) {
        return false
      }
      const normalizedUserPermission = String(userPermission).toLowerCase()

      if (normalizedUserPermission === normalizedPermission) {
        return true
      }

      if (normalizedUserPermission.endsWith('.*')) {
        const basePermission = normalizedUserPermission.slice(0, -2)
        return (
          normalizedPermission === basePermission ||
          normalizedPermission.startsWith(`${basePermission}.`)
        )
      }

      return false
    })
  }, [user])

  const hasRole = useCallback((role: string): boolean => {
    if (isMockAuthEnabled()) {
      return mockAuthService.hasRole(role)
    }
    if (!user || !user['role']) {
      return false
    }
    // Case-insensitive role comparison to handle ADMIN, admin, Admin, etc.
    const userRole = String(user['role']).toLowerCase()
    const checkRole = String(role).toLowerCase()
    return userRole === checkRole
  }, [user])

  // Helper to transform Firebase user to app User
  const transformFirebaseUser = useCallback(async (firebaseUser: FirebaseUser): Promise<User | null> => {
    try {
      const token = await firebaseUser.getIdToken()

      try {
        // Call /auth/me with auth header
        apiClient.setAuthToken(token)
        const response = await apiClient.auth.me()

        if (!response || !response.data) {
          // No user data returned, force sign out (lazy loaded)
          logger.warn('No user data from /auth/me, signing out')
          await firebaseAuthLazy.signOut()

          toast({
            title: 'Sessão expirada',
            description: 'Sua sessão expirou. Por favor, faça login novamente.',
            variant: 'destructive'
          })

          return null
        }

        return response.data
      } finally {
        // HYBRID AUTH: Keep Firebase token for backward compatibility
        // Both session cookie AND Bearer token available for all endpoints
        logger.log('Keeping Firebase token for hybrid authentication after transformFirebaseUser')
      }

    } catch (error: any) {
      // ANY error from /auth/me = force sign out (lazy loaded)
      logger.error('/auth/me failed, signing out user', { error })

      // Don't use fallback data - always sign out
      await firebaseAuthLazy.signOut()

      // Show error to user
      toast({
        title: 'Sessão expirada',
        description: 'Sua sessão expirou. Por favor, faça login novamente.',
        variant: 'destructive'
      })

      return null
    }
  }, [])

  // Initialize from session
  useEffect(() => {
    const init = async (): Promise<void | (() => void)> => {
      logger.log('Initializing authentication...')

      // Fetch CSRF token on app initialization (non-blocking)
      try {
        await apiClient.fetchCsrfToken()
        logger.log('CSRF token initialized successfully')
      } catch (error) {
        // CSRF token fetch failure should NOT block authentication
        logger.warn('Failed to initialize CSRF token (non-critical):', error)
        // Authentication will still work; token fetched lazily if needed
      }

      if (isMockAuthEnabled()) {
        logger.log('Using mock authentication')
        try {
          const mockUser = mockAuthService.getCurrentUser()
          const mockSession = mockAuthService.getSession()

          if (mockUser && mockSession) {
            logger.log('Mock session found:', mockUser.email)
            setUser(mockUser)
            setSession({ access_token: mockSession.access_token })
            apiClient.setAuthToken(mockSession.access_token)
          } else {
            logger.log('No active mock session')
          }
        } catch (error) {
          logger.error('Mock auth initialization error:', error)
        }
        setIsInitializing(false)
        return undefined
      } else {
        logger.log('Using Firebase authentication (lazy loaded)')

        // Check if Firebase is configured before setting up listeners
        if (!firebaseAuthLazy.isConfigured()) {
          logger.warn('Firebase not configured - falling back to unauthenticated state')
          logger.info('Set VITE_USE_MOCK_AUTH=true or configure Firebase credentials')
          setIsInitializing(false)
          return undefined
        }

        // Set up Firebase auth state listener (lazy loaded)
        const unsubscribe = await firebaseAuthLazy.onAuthStateChanged(async (firebaseUser) => {
          if (firebaseUser) {
            logger.log('Firebase user signed in (lazy loaded):', firebaseUser.email)
            try {
              const token = await firebaseUser.getIdToken()
              const appUser = await transformFirebaseUser(firebaseUser)

              // CRITICAL: If backend validation failed, appUser will be null
              if (appUser) {
                setUser(appUser)
                setSession({ access_token: token })

                // Connect WebSocket with Firebase token (non-blocking)
                logger.log('Connecting WebSocket...')
                wsManager.connect(token).catch(error => {
                  logger.warn('WebSocket connection failed during auth state change, continuing without real-time features:', error)
                  // Don't throw - WebSocket failure shouldn't block authentication
                })
              } else {
                // Backend rejected user - already signed out by transformFirebaseUser
                logger.warn('Backend rejected Firebase user - session cleared')
                setUser(null)
                setSession(null)
                apiClient.clearAuthToken()
                wsManager.disconnect()
              }
            } catch (error) {
              logger.error('Error transforming Firebase user:', error)
              setUser(null)
              setSession(null)
              apiClient.clearAuthToken()
              wsManager.disconnect()
            }
          } else {
            logger.log('No Firebase user signed in')
            setUser(null)
            setSession(null)
            apiClient.clearAuthToken()

            // Disconnect WebSocket when user logs out
            logger.log('Disconnecting WebSocket...')
            wsManager.disconnect()
          }
          setIsInitializing(false)
        })

        // Set up Firebase token refresh listener (lazy loaded)
        const unsubscribeTokenRefresh = await firebaseAuthLazy.onIdTokenChanged(async (firebaseUser) => {
          if (firebaseUser) {
            try {
              const newToken = await firebaseUser.getIdToken()
              logger.log('Firebase token refreshed (lazy loaded)')

              // Update WebSocket with new token
              wsManager.updateToken(newToken)

              // SECURITY: keep API client cookie-only; token stored only for WebSocket usage
              setSession({ access_token: newToken })
            } catch (error) {
              logger.error('Error refreshing token:', error)
            }
          }
        })

        // Cleanup subscription on unmount
        return () => {
          logger.log('Cleaning up Firebase auth listeners')
          unsubscribe()
          unsubscribeTokenRefresh()
          wsManager.disconnect()
        }
      }
    }

    init()
  }, [transformFirebaseUser])

  const login = async (email: string, password: string, rememberMe: boolean = false) => {
    setIsAuthenticating(true)
    try {
      logger.log('Attempting login:', email)

      // Clear any previous errors
      apiClient.clearAuthToken()

      if (isMockAuthEnabled()) {
        const result = await mockAuthService.signIn(email, password)

        if (!result.success || !result.user || !result.session) {
          throw new Error(result.error || 'Login failed')
        }

        logger.log('Mock login successful:', result.user.email)
        setUser(result.user)
        setSession({ access_token: result.session.access_token })
        apiClient.setAuthToken(result.session.access_token)

        // Connect WebSocket for mock auth (non-blocking)
        wsManager.connect(result.session.access_token).catch(error => {
          logger.warn('WebSocket connection failed during mock login, continuing without real-time features:', error)
          // Don't throw - WebSocket failure shouldn't block login
        })
      } else {
        // Set persistence BEFORE signIn using lazy-loaded Firebase
        try {
          await firebaseAuthLazy.setPersistence(rememberMe)
          logger.log(`Persistence set to ${rememberMe ? 'LOCAL' : 'SESSION'} (lazy loaded)`)
        } catch (error) {
          logger.error('Failed to set persistence, continuing with default:', error)
        }

        // Use new firebase-auth service with session management
        // Note: CSRF token fetch is handled inside loginUser()
        const loginResponse = await firebaseAuthService.loginUser(email, password)

        logger.log('Firebase login successful (session in httpOnly cookie)')

        // SECURITY: session_id is now in httpOnly cookie (not exposed to JavaScript)
        // loginResponse.session_id is just a placeholder ('cookie')
        // Actual session validation happens server-side via cookie

        // Get Firebase token from lazy-loaded Firebase Auth SDK (in-memory)
        const currentFirebaseUser = await firebaseAuthLazy.getCurrentUser()
        const firebaseToken = currentFirebaseUser ? await currentFirebaseUser.getIdToken() : ''

        setUser(loginResponse.user)
        const sessionData: { access_token: string; session_id?: string } = {
          access_token: firebaseToken
        }
        if (loginResponse.session_id) {
          sessionData.session_id = loginResponse.session_id
        }
        setSession(sessionData)

        // Connect WebSocket with Firebase token (non-blocking)
        if (firebaseToken) {
          wsManager.connect(firebaseToken).catch(error => {
            logger.warn('WebSocket connection failed during login, continuing without real-time features:', error)
            // Don't throw - WebSocket failure shouldn't block login
          })
        }
      }
    } catch (error: any) {
      logger.error('Login failed:', error)

      // Comprehensive cleanup on login failure
      setUser(null)
      setSession(null)
      apiClient.clearAuthToken()

      // Disconnect WebSocket on login failure
      wsManager.disconnect()

      // Ensure cleanup on error (cookie cleared by backend)
      // Firebase Auth SDK automatically clears in-memory token

      // Enhanced error handling with user-friendly messages
      let userMessage = 'Erro ao fazer login. Tente novamente.'

      if (error.message?.includes('auth/user-not-found')) {
        userMessage = 'Usuário não encontrado. Verifique seu email.'
      } else if (error.message?.includes('auth/wrong-password')) {
        userMessage = 'Senha incorreta. Tente novamente.'
      } else if (error.message?.includes('auth/too-many-requests')) {
        userMessage = 'Muitas tentativas. Aguarde alguns minutos.'
      } else if (error.message?.includes('Network')) {
        userMessage = 'Erro de conexão. Verifique sua internet.'
      }

      // Show user-friendly error
      toast({
        title: 'Erro no Login',
        description: userMessage,
        variant: 'destructive'
      })

      throw error
    } finally {
      setIsAuthenticating(false)
    }
  }

  const logout = useCallback(async () => {
    try {
      logger.log('Logging out...')

      if (isMockAuthEnabled()) {
        await mockAuthService.signOut()
      } else {
        // Use new firebase-auth service with session cleanup
        await firebaseAuthService.logoutUser()
      }

      apiClient.clearAuthToken()
      setUser(null)
      setSession(null)

      // Disconnect WebSocket on logout
      wsManager.disconnect()
      logger.log('Logout complete')
    } catch (error) {
      logger.error('Logout error:', error)

      // Force cleanup even on error (cookie cleared by backend)
      apiClient.clearAuthToken()
      setUser(null)
      setSession(null)

      wsManager.disconnect()
    }
  }, [])

  const logoutAll = useCallback(async () => {
    try {
      logger.log('Logging out from all devices...')

      if (isMockAuthEnabled()) {
        await mockAuthService.signOut()
      } else {
        // Use new firebase-auth service to logout all sessions
        const result = await firebaseAuthService.logoutAllDevices()
        logger.log(`${result.sessions_deleted} sessions invalidated`)
      }

      apiClient.clearAuthToken()
      setUser(null)
      setSession(null)

      // Disconnect WebSocket
      wsManager.disconnect()
      logger.log('Logout from all devices complete')

      toast({
        title: 'Logout realizado',
        description: 'Você foi desconectado de todos os dispositivos.',
        variant: 'default'
      })
    } catch (error) {
      logger.error('Logout all error:', error)

      // Force cleanup even on error (cookie cleared by backend)
      apiClient.clearAuthToken()
      setUser(null)
      setSession(null)
      // Firebase Auth SDK automatically clears in-memory token
      wsManager.disconnect()

      throw error
    }
  }, [])

  /**
   * Get current Firebase token from Firebase Auth SDK (in-memory)
   * Used by WebSocket connections and direct API calls
   *
   * SECURITY ARCHITECTURE:
   * - Firebase ID tokens: Managed by Firebase SDK in-memory
   * - Backend sessions: Stored in httpOnly cookies (automatic, secure)
   * - httpOnly cookies prevent JavaScript access (OWASP best practice)
   */
  const getFirebaseToken = useCallback(async (): Promise<string | null> => {
    try {
      const currentUser = await firebaseAuthLazy.getCurrentUser()
      if (!currentUser) return null
      return await currentUser.getIdToken()
    } catch (error) {
      logger.error('Failed to get Firebase token:', error)
      return null
    }
  }, [])

  /**
   * Force refresh Firebase token
   * Useful for WebSocket reconnection after token expiry
   */
  const refreshToken = useCallback(async (): Promise<void> => {
    try {
      const currentUser = await firebaseAuthLazy.getCurrentUser()
      if (currentUser) {
        const newToken = await currentUser.getIdToken(true) // force refresh
        // Token automatically updated in lazy-loaded Firebase Auth SDK (in-memory)
        logger.info('Firebase token refreshed successfully (lazy loaded)')
      }
    } catch (error) {
      logger.error('Failed to refresh Firebase token:', error)
      throw error
    }
  }, [])

  const value: AuthContextType = useMemo(() => ({
    user,
    session,
    isAuthenticated,
    isLoading,
    isInitializing,
    isAuthenticating,
    login,
    logout,
    logoutAll,
    hasPermission,
    hasRole,
    getFirebaseToken,
    refreshToken
  }), [
    user,
    session,
    isAuthenticated,
    isLoading,
    isInitializing,
    isAuthenticating,
    login,
    logout,
    logoutAll,
    hasPermission,
    hasRole,
    getFirebaseToken,
    refreshToken
  ])

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
