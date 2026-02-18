/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState, ReactNode, useCallback, useMemo } from 'react'
import { apiClient } from '@/lib/api-client'
import { User } from '@/types/api'
import { isMockAuthEnabled } from '@/config/mock.config'
import mockAuthService from '@/lib/mock-auth-service'
import { firebaseAuthLazy } from '@/lib/firebase-lazy'
import type { User as FirebaseUser } from 'firebase/auth'
import { wsManager } from '@/lib/websocket'
import { createLogger } from '@/lib/logger'
import { toast } from '@/hooks/use-toast'
import * as firebaseAuthService from '@/services/firebase-auth'
import { isErrorWithMessage } from '@/lib/type-guards'

const logger = createLogger('AuthContext')
export const AUTH_LOCK_TIMEOUT_MS = 5000

export const safeLocalStorage = {
  setItem: (key: string, value: string): boolean => {
    try {
      localStorage.setItem(key, value)
      logger.log(`localStorage.setItem('${key}') succeeded`)
      return true
    } catch (error) {
      logger.warn(
        `localStorage.setItem('${key}') failed (likely private mode):`,
        error
      )
      return false
    }
  },

  getItem: (key: string): string | null => {
    try {
      return localStorage.getItem(key)
    } catch (error) {
      logger.warn(`localStorage.getItem('${key}') failed:`, error)
      return null
    }
  },

  removeItem: (key: string): boolean => {
    try {
      localStorage.removeItem(key)
      logger.log(`localStorage.removeItem('${key}') succeeded`)
      return true
    } catch (error) {
      logger.warn(`localStorage.removeItem('${key}') failed:`, error)
      return false
    }
  },
}

export type AuthLockState = {
  locked: boolean
  timestamp: number
  operation: 'login' | 'restore' | null
}

type AuthSession = {
  access_token: string
  session_id?: string
  websocketToken?: string
}

export const createAuthLock = (
  authLockRef: React.MutableRefObject<AuthLockState>,
  lockLogger = logger
) => {
  const acquireAuthLock = (operation: 'login' | 'restore') => {
    const now = Date.now()
    const currentLock = authLockRef.current

    if (currentLock.locked && (now - currentLock.timestamp) < AUTH_LOCK_TIMEOUT_MS) {
      lockLogger.warn(
        `Auth lock active (operation=${currentLock.operation ?? 'unknown'}), rejecting ${operation}`
      )
      return false
    }

    authLockRef.current = {
      locked: true,
      timestamp: now,
      operation
    }
    lockLogger.log(`Auth lock acquired for ${operation}`)
    return true
  }

  const releaseAuthLock = () => {
    const previousOperation = authLockRef.current.operation
    authLockRef.current = {
      locked: false,
      timestamp: 0,
      operation: null
    }
    lockLogger.log(`Auth lock released${previousOperation ? ` (${previousOperation})` : ''}`)
  }

  return { acquireAuthLock, releaseAuthLock }
}

interface AuthContextType {
  user: User | null
  session: AuthSession | null
  isAuthenticated: boolean
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
  const [session, setSession] = useState<AuthSession | null>(null)
  const [isInitializing, setIsInitializing] = useState(true) // Bootstrap phase
  const [isAuthenticating, setIsAuthenticating] = useState(false) // Active login/logout
  const authLockRef = React.useRef<AuthLockState>({
    locked: false,
    timestamp: 0,
    operation: null
  })
  const isAuthenticatingRef = React.useRef(false) // Legacy ref for compatibility
  const { acquireAuthLock, releaseAuthLock } = React.useMemo(
    () => createAuthLock(authLockRef, logger),
    []
  )

  // OPTIMIZATION: Access query client for dashboard prefetching
  // This prefetches dashboard data immediately after login for instant loading
  const isAuthenticated = !!user

  // Permission and role checking functions
  const hasPermission = useCallback((permission: string): boolean => {
    if (isMockAuthEnabled()) {
      return mockAuthService.hasPermission(permission)
    }

    if (!user) {
      return false
    }

    const role = String(user.role ?? '').toLowerCase()
    if (role === 'admin') {
      return true
    }

    const rawPermissions = Array.isArray(user.permissions) ? user.permissions : []
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

    if (!user || !user.role) {
      return false
    }

    const userRole = String(user.role).toLowerCase()
    const checkRole = String(role).toLowerCase()
    return userRole === checkRole
  }, [user])

  // Helper to transform Firebase user to app User
  const transformFirebaseUser = useCallback(async (_firebaseUser: FirebaseUser): Promise<User | null> => {
    try {
      // IMPORTANT: Do NOT use Firebase JWT as auth token for API calls
      // The backend expects session_id (UUID from Redis), not Firebase JWT
      // auth.me() uses httpOnly cookie automatically via credentials: 'include'

      try {
        // Call /auth/me - relies on session cookie, NOT Authorization header
        // auth.me() in auth.ts uses fetchSession() which explicitly doesn't send Bearer token
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
        // CRITICAL FIX: Clear any auth token to prevent Firebase JWT being used
        // API calls should use session_id (UUID) from login or rely on httpOnly cookie
        logger.log('transformFirebaseUser completed - API uses cookie/session_id, not Firebase JWT')
      }

    } catch (error: unknown) {
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
    let unsubscribeAuth: (() => void) | undefined
    let unsubscribeToken: (() => void) | undefined

    const init = async () => {
      logger.log('Initializing authentication...')

      // Fetch CSRF token on app initialization (non-blocking)
      try {
        await apiClient.fetchCsrfToken()
        logger.log('CSRF token initialized successfully')
      } catch (error) {
        // CSRF token fetch failure should NOT block authentication
        logger.error('CRITICAL: Failed to initialize CSRF token:', error)

        // Show toast warning to user (non-blocking)
        toast({
          title: 'Aviso de Segurança',
          description:
            'Algumas funcionalidades podem não funcionar corretamente. ' +
            'Tente recarregar a página.',
          variant: 'warning',
          duration: 10000, // 10 seconds
        })

        // Authentication will still work; token fetched lazily if needed
      }

      const storedSessionId = safeLocalStorage.getItem('session_id')
      if (storedSessionId) {
        logger.log('Restoring session_id from localStorage for API auth')
        firebaseAuthService.setSessionId(storedSessionId)
      }

      if (isMockAuthEnabled()) {
        logger.log('Using mock authentication')
        try {
          const mockUser = mockAuthService.getCurrentUser()
          const mockSession = mockAuthService.getSession()

          if (mockUser && mockSession) {
            logger.log('Mock session found:', mockUser.email)
            setUser({ ...mockUser, name: mockUser.email })
            setSession({
              access_token: mockSession.access_token,
              websocketToken: mockSession.access_token
            })
            apiClient.setAuthToken(mockSession.access_token)
          } else {
            logger.log('No active mock session')
          }
        } catch (error) {
          logger.error('Mock auth initialization error:', error)
        }
        setIsInitializing(false)
        return
      } else {
        logger.log('Using Firebase authentication (lazy loaded)')

        // Check if Firebase is configured before setting up listeners
        if (!firebaseAuthLazy.isConfigured()) {
          logger.warn('Firebase not configured - attempting server session fallback')

          // FALLBACK: Try to validate existing server session (cookie)
          try {
            const { authenticated, user: sessionUser } = await apiClient.auth.checkAuth()
            if (authenticated && sessionUser) {
              logger.log('Server session valid (fallback mode)', sessionUser.email)
              setUser(sessionUser)
              // No access token in fallback mode, but cookies work
              setSession({ access_token: '' })
            } else {
              logger.warn('No valid server session found in fallback mode')
            }
          } catch (error) {
            logger.error('Server session fallback check failed:', error)
          }

          setIsInitializing(false)
          return
        }

        // PERFORMANCE FIX: Check backend session FIRST before waiting for Firebase
        // This prevents the "logout on refresh" bug caused by Firebase's async state restoration
        // The httpOnly session cookie is sent automatically, providing immediate session validation
        let sessionValidatedFromCookie = false
        try {
          logger.log('Checking server session via httpOnly cookie (fast path)...')
          const { authenticated, user: sessionUser, sessionId } = await apiClient.auth.checkAuth()
          if (authenticated && sessionUser) {
            logger.log('Session restored from httpOnly cookie:', sessionUser.email)
            setUser(sessionUser)

            if (sessionId) {
              logger.log('Session ID restored from cookie validation (Header-Based Auth)')
              apiClient.setAuthToken(sessionId)
              setSession({ access_token: sessionId, session_id: sessionId })
            } else {
              setSession({ access_token: '' }) // Token will be updated when Firebase loads
            }

            sessionValidatedFromCookie = true
            // CRITICAL: Set isInitializing to false immediately so UI can render
            // Firebase will sync in background and update the token
            setIsInitializing(false)
            logger.log('User authenticated via cookie - UI ready, Firebase syncing in background')

            // OPTIMIZATION: Prefetch dashboard data immediately after session restore
            // This ensures dashboard loads instantly when user navigates to it
            try {
              apiClient.dashboard.getMain({ time_range: 'week' })
                .then(() => logger.log('Dashboard data prefetched successfully'))
                .catch(e => logger.debug('Dashboard prefetch failed (non-critical)', e))
            } catch {
              // Non-blocking prefetch
            }
          } else if (storedSessionId) {
            logger.warn('Stored session_id invalid, clearing')
            safeLocalStorage.removeItem('session_id')
            firebaseAuthService.clearSessionId()
          }
        } catch (error) {
          logger.debug('Cookie session check failed (will rely on Firebase):', error)
          // Continue with Firebase authentication - this is expected on first login
        }

        // Set up Firebase auth state listener (lazy loaded)
        unsubscribeAuth = await firebaseAuthLazy.onAuthStateChanged(async (firebaseUser) => {
          const now = Date.now()
          const currentLock = authLockRef.current
          if (currentLock.locked && (now - currentLock.timestamp) < AUTH_LOCK_TIMEOUT_MS) {
            logger.log(
              `Ignoring onAuthStateChanged event due to active auth lock (${currentLock.operation ?? 'unknown'})`
            )
            return
          }

          if (firebaseUser) {
            logger.log('Firebase user signed in (lazy loaded):', firebaseUser.email)
            if (!acquireAuthLock('restore')) {
              logger.warn('Auth lock already active, skipping session restore')
              return
            }

            try {
              const firebaseToken = await firebaseUser.getIdToken()
              const appUser = await transformFirebaseUser(firebaseUser)

              // CRITICAL: If backend validation failed, appUser will be null
              if (appUser) {
                setUser(appUser)
                // CRITICAL FIX: Store session_id from login response, NOT Firebase JWT
                // Firebase token is ONLY used for WebSocket, not API calls
                // session_id (UUID) should be set by login flow or restored from checkAuth()
                // If we don't have a session_id, keep current session or use empty token
                // The httpOnly cookie handles actual API authentication
                setSession(prev => ({
                  access_token: prev?.access_token ?? '',
                  session_id: prev?.session_id,
                  websocketToken: firebaseToken
                }))

                // Connect WebSocket with Firebase token (non-blocking)
                // Note: WebSocket uses Firebase JWT, but API calls use session_id/cookie
                logger.log('Connecting WebSocket with Firebase token...')
                wsManager.connect(firebaseToken).catch(error => {
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
            } finally {
              releaseAuthLock()
            }
          } else {
            // CRITICAL FIX: Only clear session if we didn't validate from cookie
            // Firebase may fire null initially while still loading persisted state
            if (!sessionValidatedFromCookie) {
              logger.log('No Firebase user signed in')
              setUser(null)
              setSession(null)
              apiClient.clearAuthToken()

              // Disconnect WebSocket when user logs out
              logger.log('Disconnecting WebSocket...')
              wsManager.disconnect()
            } else {
              logger.log('Firebase not ready yet, but session validated from cookie - keeping user logged in')
              // Reset flag so future "null" events (actual logout) work correctly
              sessionValidatedFromCookie = false
            }
          }
          setIsInitializing(false)
        })

        // Set up Firebase token refresh listener (lazy loaded)
        unsubscribeToken = await firebaseAuthLazy.onIdTokenChanged(async (firebaseUser) => {
          if (firebaseUser) {
            try {
              const newToken = await firebaseUser.getIdToken()
              logger.log('Firebase token refreshed (lazy loaded)')

              // Update WebSocket with new token
              wsManager.updateToken(newToken)

              // SECURITY: keep API client cookie-only; token stored only for WebSocket usage
              setSession(prev => (prev ? { ...prev, websocketToken: newToken } : prev))
            } catch (error) {
              logger.error('Error refreshing token:', error)
            }
          }
        })
      }
    }

    init()

    // Cleanup subscription on unmount
    return () => {
      logger.log('Cleaning up Firebase auth listeners')
      if (unsubscribeAuth) unsubscribeAuth()
      if (unsubscribeToken) unsubscribeToken()
      wsManager.disconnect()
    }
  }, [transformFirebaseUser, acquireAuthLock, releaseAuthLock])

  const login = useCallback(async (email: string, password: string, rememberMe: boolean = false) => {
    if (!acquireAuthLock('login')) {
      logger.warn('Auth lock already active, rejecting login attempt')
      throw new Error('Operação de autenticação já em andamento')
    }
    setIsAuthenticating(true)
    isAuthenticatingRef.current = true
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
        setUser({ ...result.user, name: result.user.email })
        setSession({
          access_token: result.session.access_token,
          websocketToken: result.session.access_token
        })
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
        const sessionId = loginResponse.session_id ?? ''
        const sessionData: AuthSession = {
          access_token: sessionId,
          session_id: loginResponse.session_id,
          websocketToken: firebaseToken
        }
        setSession(sessionData)

        // Connect WebSocket with Firebase token (non-blocking)
        if (firebaseToken) {
          wsManager.connect(firebaseToken).catch(error => {
            logger.warn('WebSocket connection failed during login, continuing without real-time features:', error)
            // Don't throw - WebSocket failure shouldn't block login
          })
        }

        // Store session_id for WebSocket authentication (with try-catch)
        if (sessionId) {
          const stored = safeLocalStorage.setItem('session_id', sessionId)
          if (!stored) {
            logger.warn(
              'Failed to store session_id in localStorage. ' +
              'WebSocket notifications may not work in private browsing mode.'
            )
            // Don't show toast - this is expected behavior in private mode
            // WebSocket will gracefully degrade without localStorage
          }
        }

        // OPTIMIZATION: Prefetch dashboard data immediately after login
        // This ensures the dashboard loads instantly when user navigates to it
        try {
          apiClient.dashboard.getMain({ time_range: 'week' })
            .then(() => logger.log('Dashboard data prefetched after login'))
            .catch(e => logger.debug('Dashboard prefetch failed (non-critical)', e))
        } catch {
          // Non-blocking prefetch
        }
      }
    } catch (error: unknown) {
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

      if (isErrorWithMessage(error) && error.message.includes('auth/user-not-found')) {
        userMessage = 'Usuário não encontrado. Verifique seu email.'
      } else if (isErrorWithMessage(error) && error.message.includes('auth/wrong-password')) {
        userMessage = 'Senha incorreta. Tente novamente.'
      } else if (isErrorWithMessage(error) && error.message.includes('auth/too-many-requests')) {
        userMessage = 'Muitas tentativas. Aguarde alguns minutos.'
      } else if (isErrorWithMessage(error) && error.message.includes('Network')) {
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
      releaseAuthLock()
      setIsAuthenticating(false)
      isAuthenticatingRef.current = false
    }
  }, [acquireAuthLock, releaseAuthLock])

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
      safeLocalStorage.removeItem('session_id')  // Clear session_id from localStorage
      setUser(null)
      setSession(null)

      // Disconnect WebSocket on logout
      wsManager.disconnect()
      logger.log('Logout complete')
    } catch (error) {
      logger.error('Logout error:', error)

      // Force cleanup even on error (cookie cleared by backend)
      apiClient.clearAuthToken()
      safeLocalStorage.removeItem('session_id')  // Clear session_id from localStorage
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
      safeLocalStorage.removeItem('session_id')
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
      safeLocalStorage.removeItem('session_id')
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
        await currentUser.getIdToken(true) // force refresh
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
