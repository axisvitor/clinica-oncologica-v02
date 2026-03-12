/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
  useCallback,
  useMemo,
} from 'react'
import { apiClient } from '@/lib/api-client'
import { toUserSafeAuthError } from '@/lib/api-client/auth'
import { User } from '@/types/api'
import { isMockAuthEnabled } from '@/config/mock.config'
import mockAuthService from '@/lib/mock-auth-service'
import { wsManager } from '@/lib/websocket'
import { createLogger } from '@/lib/logger'
import { toast } from '@/hooks/use-toast'

const logger = createLogger('AuthContext')
export const AUTH_LOCK_TIMEOUT_MS = 5000

export const safeLocalStorage = {
  setItem: (key: string, value: string): boolean => {
    try {
      localStorage.setItem(key, value)
      logger.log(`localStorage.setItem('${key}') succeeded`)
      return true
    } catch (error) {
      logger.warn(`localStorage.setItem('${key}') failed (likely private mode):`, error)
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

    if (currentLock.locked && now - currentLock.timestamp < AUTH_LOCK_TIMEOUT_MS) {
      lockLogger.warn(
        `Auth lock active (operation=${currentLock.operation ?? 'unknown'}), rejecting ${operation}`
      )
      return false
    }

    authLockRef.current = {
      locked: true,
      timestamp: now,
      operation,
    }
    lockLogger.log(`Auth lock acquired for ${operation}`)
    return true
  }

  const releaseAuthLock = () => {
    const previousOperation = authLockRef.current.operation
    authLockRef.current = {
      locked: false,
      timestamp: 0,
      operation: null,
    }
    lockLogger.log(`Auth lock released${previousOperation ? ` (${previousOperation})` : ''}`)
  }

  return { acquireAuthLock, releaseAuthLock }
}

interface AuthContextType {
  user: User | null
  session: AuthSession | null
  isAuthenticated: boolean
  isInitializing: boolean
  isAuthenticating: boolean
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>
  logout: () => void
  logoutAll: () => Promise<void>
  hasPermission: (permission: string) => boolean
  hasRole: (role: string) => boolean
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
  const [isInitializing, setIsInitializing] = useState(true)
  const [isAuthenticating, setIsAuthenticating] = useState(false)
  const authLockRef = React.useRef<AuthLockState>({
    locked: false,
    timestamp: 0,
    operation: null,
  })
  const { acquireAuthLock, releaseAuthLock } = React.useMemo(
    () => createAuthLock(authLockRef, logger),
    []
  )

  const isAuthenticated = !!user

  const clearAuthState = useCallback(() => {
    apiClient.clearAuthToken()
    safeLocalStorage.removeItem('session_id')
    setUser(null)
    setSession(null)
    wsManager.disconnect()
  }, [])

  const persistSessionState = useCallback((nextUser: User, sessionId?: string | null) => {
    const normalizedSessionId = sessionId?.trim() ? sessionId : undefined

    setUser(nextUser)
    setSession({
      access_token: normalizedSessionId ?? '',
      session_id: normalizedSessionId,
      websocketToken: normalizedSessionId,
    })

    apiClient.setAuthToken(normalizedSessionId ?? null)

    if (normalizedSessionId) {
      safeLocalStorage.setItem('session_id', normalizedSessionId)
    } else {
      safeLocalStorage.removeItem('session_id')
    }
  }, [])

  const prefetchDashboard = useCallback(() => {
    try {
      apiClient.dashboard
        .getMain({ time_range: 'week' })
        .then(() => logger.log('Dashboard data prefetched successfully'))
        .catch((error) => logger.debug('Dashboard prefetch failed (non-critical)', error))
    } catch {
      // Non-blocking prefetch
    }
  }, [])

  const hasPermission = useCallback(
    (permission: string): boolean => {
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

      return rawPermissions.some((userPermission) => {
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
    },
    [user]
  )

  const hasRole = useCallback(
    (role: string): boolean => {
      if (isMockAuthEnabled()) {
        return mockAuthService.hasRole(role)
      }

      if (!user || !user.role) {
        return false
      }

      const userRole = String(user.role).toLowerCase()
      const checkRole = String(role).toLowerCase()
      return userRole === checkRole
    },
    [user]
  )

  const restoreSession = useCallback(async (): Promise<boolean> => {
    if (!acquireAuthLock('restore')) {
      logger.warn('Auth lock already active, skipping session restore')
      return false
    }

    try {
      const storedSessionId = safeLocalStorage.getItem('session_id')
      if (storedSessionId) {
        logger.log('Restoring session_id from localStorage for API auth')
        apiClient.setAuthToken(storedSessionId)
      } else {
        apiClient.clearAuthToken()
      }

      logger.log('Auth phase=restore via verify-session')
      const { authenticated, user: sessionUser, sessionId } = await apiClient.auth.checkAuth()

      if (!authenticated || !sessionUser) {
        if (storedSessionId) {
          logger.warn('Stored session_id invalid, clearing')
        }
        clearAuthState()
        return false
      }

      persistSessionState(sessionUser, sessionId ?? storedSessionId)
      prefetchDashboard()
      return true
    } catch (error) {
      logger.warn('Session restore failed', error)
      clearAuthState()
      return false
    } finally {
      releaseAuthLock()
    }
  }, [acquireAuthLock, clearAuthState, persistSessionState, prefetchDashboard, releaseAuthLock])

  useEffect(() => {
    let isMounted = true

    const init = async () => {
      logger.log('Initializing authentication...')

      try {
        await apiClient.fetchCsrfToken()
        logger.log('CSRF token initialized successfully')
      } catch (error) {
        logger.error('CRITICAL: Failed to initialize CSRF token:', error)
        toast({
          title: 'Aviso de Segurança',
          description:
            'Algumas funcionalidades podem não funcionar corretamente. Tente recarregar a página.',
          variant: 'warning',
          duration: 10000,
        })
      }

      if (isMockAuthEnabled()) {
        logger.log('Using mock authentication')
        try {
          const mockUser = mockAuthService.getCurrentUser()
          const mockSession = mockAuthService.getSession()

          if (mockUser && mockSession) {
            logger.log('Mock session found:', mockUser.email)
            setUser({ ...mockUser, name: mockUser.full_name ?? mockUser.email })
            setSession({
              access_token: mockSession.access_token,
              session_id: mockSession.access_token,
              websocketToken: mockSession.access_token,
            })
            apiClient.setAuthToken(mockSession.access_token)
          }
        } catch (error) {
          logger.error('Mock auth initialization error:', error)
        } finally {
          if (isMounted) {
            setIsInitializing(false)
          }
        }
        return
      }

      await restoreSession()

      if (isMounted) {
        setIsInitializing(false)
      }
    }

    void init()

    return () => {
      isMounted = false
      logger.log('Cleaning up auth provider')
      wsManager.disconnect()
    }
  }, [restoreSession])

  const login = useCallback(
    async (email: string, password: string, rememberMe: boolean = false) => {
      if (!acquireAuthLock('login')) {
        logger.warn('Auth lock already active, rejecting login attempt')
        throw new Error('Operação de autenticação já em andamento')
      }

      setIsAuthenticating(true)

      try {
        logger.log('Auth phase=login')
        apiClient.clearAuthToken()

        if (isMockAuthEnabled()) {
          const result = await mockAuthService.signIn(email, password)

          if (!result.success || !result.user || !result.session) {
            throw new Error(result.error || 'Login failed')
          }

          const mockUser = { ...result.user, name: result.user.full_name ?? result.user.email }
          setUser(mockUser)
          setSession({
            access_token: result.session.access_token,
            session_id: result.session.access_token,
            websocketToken: result.session.access_token,
          })
          apiClient.setAuthToken(result.session.access_token)
          prefetchDashboard()
          return
        }

        const loginResponse = await apiClient.auth.login({
          email,
          password,
          remember_me: rememberMe,
        })

        persistSessionState(loginResponse.user, loginResponse.session_id)
        prefetchDashboard()
      } catch (error: unknown) {
        const userSafeError = toUserSafeAuthError(error, 'Erro ao fazer login. Tente novamente.')

        logger.error('Login failed', {
          status: userSafeError.status,
          error: userSafeError.error,
          request_id: userSafeError.request_id,
        })

        clearAuthState()

        toast({
          title: 'Erro no Login',
          description: userSafeError.message,
          variant: 'destructive',
        })

        throw userSafeError
      } finally {
        releaseAuthLock()
        setIsAuthenticating(false)
      }
    },
    [acquireAuthLock, clearAuthState, persistSessionState, prefetchDashboard, releaseAuthLock]
  )

  const logout = useCallback(async () => {
    logger.log('Auth phase=logout')

    try {
      if (isMockAuthEnabled()) {
        await mockAuthService.signOut()
      } else {
        await apiClient.auth.logout()
      }
    } catch (error) {
      logger.error('Logout error:', error)
    } finally {
      clearAuthState()
      logger.log('Logout complete')
    }
  }, [clearAuthState])

  const logoutAll = useCallback(async () => {
    logger.log('Auth phase=logout-all')

    try {
      if (isMockAuthEnabled()) {
        await mockAuthService.signOut()
      } else {
        const result = await apiClient.auth.invalidateAllSessions()
        logger.log(`${result.sessions_deleted} sessions invalidated`)
      }
    } catch (error) {
      logger.error('Logout all error:', error)
      throw error
    } finally {
      clearAuthState()
    }

    toast({
      title: 'Logout realizado',
      description: 'Você foi desconectado de todos os dispositivos.',
      variant: 'default',
    })
  }, [clearAuthState])

  const refreshToken = useCallback(async (): Promise<void> => {
    logger.log('Auth phase=refresh-session')
    await restoreSession()
  }, [restoreSession])

  const value: AuthContextType = useMemo(
    () => ({
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
      refreshToken,
    }),
    [
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
      refreshToken,
    ]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
