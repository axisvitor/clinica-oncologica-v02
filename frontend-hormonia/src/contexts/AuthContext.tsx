import React, { createContext, useContext, useEffect, useState, ReactNode, useCallback } from 'react'
import { apiClient } from '../lib/api-client'
import { User } from '../hooks/auth/types'
import { isMockAuthEnabled } from '../config/mock.config'
import mockAuthService from '../lib/mock-auth-service'
import { firebaseAuth } from '../lib/firebase-client'
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
  isLoading: boolean
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>
  logout: () => void
  logoutAll: () => Promise<void>
  hasPermission: (permission: string) => boolean
  hasRole: (role: string) => boolean
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
  const [isLoading, setIsLoading] = useState(true)

  const isAuthenticated = !!user

  // Permission and role checking functions
  const hasPermission = useCallback((permission: string): boolean => {
    if (isMockAuthEnabled()) {
      return mockAuthService.hasPermission(permission)
    }
    if (!user || !user['permissions'] || !Array.isArray(user['permissions'])) {
      return false
    }
    return user['permissions'].includes(permission)
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

      // Call /auth/me with auth header
      apiClient.setAuthToken(token)
      const response = await apiClient.auth.me()

      if (!response || !response.data) {
        // No user data returned, force sign out
        logger.warn('No user data from /auth/me, signing out')
        await firebaseAuth.signOut()

        toast({
          title: 'Sessão expirada',
          description: 'Sua sessão expirou. Por favor, faça login novamente.',
          variant: 'destructive'
        })

        return null
      }

      return response.data

    } catch (error: any) {
      // ANY error from /auth/me = force sign out
      logger.error('/auth/me failed, signing out user', { error })

      // Don't use fallback data - always sign out
      await firebaseAuth.signOut()

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
        setIsLoading(false)
        return undefined
      } else {
        logger.log('Using Firebase authentication')

        // Check if Firebase is configured before setting up listeners
        if (!firebaseAuth.isConfigured()) {
          logger.warn('Firebase not configured - falling back to unauthenticated state')
          logger.info('Set VITE_USE_MOCK_AUTH=true or configure Firebase credentials')
          setIsLoading(false)
          return undefined
        }

        // Set up Firebase auth state listener
        const unsubscribe = firebaseAuth.onAuthStateChange(async (firebaseUser) => {
          if (firebaseUser) {
            logger.log('Firebase user signed in:', firebaseUser.email)
            try {
              const token = await firebaseUser.getIdToken()
              const appUser = await transformFirebaseUser(firebaseUser)

              // CRITICAL: If backend validation failed, appUser will be null
              if (appUser) {
                setUser(appUser)
                setSession({ access_token: token })
                apiClient.setAuthToken(token)

                // Connect WebSocket with Firebase token
                logger.log('Connecting WebSocket...')
                wsManager.connect(token)
              } else {
                // Backend rejected user - already signed out by transformFirebaseUser
                logger.warn('Backend rejected Firebase user - session cleared')
                setUser(null)
                setSession(null)
                apiClient.setAuthToken(null)
                wsManager.disconnect()
              }
            } catch (error) {
              logger.error('Error transforming Firebase user:', error)
              setUser(null)
              setSession(null)
              apiClient.setAuthToken(null)
              wsManager.disconnect()
            }
          } else {
            logger.log('No Firebase user signed in')
            setUser(null)
            setSession(null)
            apiClient.setAuthToken(null)

            // Disconnect WebSocket when user logs out
            logger.log('Disconnecting WebSocket...')
            wsManager.disconnect()
          }
          setIsLoading(false)
        })

        // Set up Firebase token refresh listener
        const unsubscribeTokenRefresh = firebaseAuth.onIdTokenChanged(async (firebaseUser) => {
          if (firebaseUser) {
            try {
              const newToken = await firebaseUser.getIdToken()
              logger.log('Firebase token refreshed')

              // Update WebSocket with new token
              wsManager.updateToken(newToken)

              // Update API client with new token
              apiClient.setAuthToken(newToken)
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
    setIsLoading(true)
    try {
      logger.log('Attempting login:', email)

      if (isMockAuthEnabled()) {
        const result = await mockAuthService.signIn(email, password)

        if (!result.success || !result.user || !result.session) {
          throw new Error(result.error || 'Login failed')
        }

        logger.log('Mock login successful:', result.user.email)
        setUser(result.user)
        setSession({ access_token: result.session.access_token })
        apiClient.setAuthToken(result.session.access_token)

        // Connect WebSocket for mock auth
        wsManager.connect(result.session.access_token)
      } else {
        // Set persistence BEFORE signIn using the firebaseAuth module's setPersistence wrapper
        try {
          await firebaseAuth.setPersistence(rememberMe)
          logger.log(`Persistence set to ${rememberMe ? 'LOCAL' : 'SESSION'}`)
        } catch (error) {
          logger.error('Failed to set persistence, continuing with default:', error)
        }

        // Use new firebase-auth service with session management
        const loginResponse = await firebaseAuthService.loginUser(email, password)

        logger.log('Firebase login successful with session:', loginResponse.session_id.substring(0, 8))

        // Validate that we received a real session_id
        if (!loginResponse.session_id || loginResponse.session_id.length < 32) {
          throw new Error('Invalid session_id received from backend')
        }

        setUser(loginResponse.user)
        setSession({
          access_token: localStorage.getItem('firebase_token') || '',
          session_id: loginResponse.session_id
        })

        // Connect WebSocket with Firebase token
        const firebaseToken = localStorage.getItem('firebase_token')
        if (firebaseToken) {
          wsManager.connect(firebaseToken)
        }
      }
    } catch (error: any) {
      logger.error('Login failed:', error)
      setUser(null)
      setSession(null)
      apiClient.setAuthToken(null)

      // Ensure cleanup on error (cookie cleared by backend)
      localStorage.removeItem('firebase_token')

      throw error
    } finally {
      setIsLoading(false)
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

      apiClient.setAuthToken(null)
      setUser(null)
      setSession(null)

      // Disconnect WebSocket on logout
      wsManager.disconnect()
      logger.log('Logout complete')
    } catch (error) {
      logger.error('Logout error:', error)

      // Force cleanup even on error (cookie cleared by backend)
      apiClient.setAuthToken(null)
      setUser(null)
      setSession(null)
      localStorage.removeItem('firebase_token')
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

      apiClient.setAuthToken(null)
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
      apiClient.setAuthToken(null)
      setUser(null)
      setSession(null)
      localStorage.removeItem('firebase_token')
      wsManager.disconnect()

      throw error
    }
  }, [])

  const value: AuthContextType = {
    user,
    session,
    isAuthenticated,
    isLoading,
    login,
    logout,
    logoutAll,
    hasPermission,
    hasRole
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
