import React, { createContext, useContext, useEffect, useState, ReactNode, useCallback } from 'react'
import { apiClient } from '../lib/api-client'
import { User } from '../hooks/auth/types'
import { isMockAuthEnabled } from '../config/mock.config'
import mockAuthService from '../lib/mock-auth-service'
import { firebaseAuth } from '../lib/firebase-client'
import type { User as FirebaseUser } from 'firebase/auth'
import { wsManager } from '../lib/websocket'

interface AuthContextType {
  user: User | null
  session: { access_token: string } | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  hasPermission: (permission: string) => boolean
  hasRole: (role: string) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

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
  const [session, setSession] = useState<{ access_token: string } | null>(null)
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
    return user['role'] === role
  }, [user])

  // Helper to transform Firebase user to app User
  const transformFirebaseUser = useCallback(async (firebaseUser: FirebaseUser): Promise<User> => {
    const token = await firebaseUser.getIdToken()

    // Try to fetch full user data from backend
    try {
      apiClient.setAuthToken(token)
      const response = await apiClient.auth.me()
      return response.data
    } catch (error) {
      console.warn('[AuthContext] Could not fetch user from backend, using Firebase data:', error)
      // Fallback to Firebase user data
      return {
        id: firebaseUser.uid,
        email: firebaseUser.email || '',
        fullName: firebaseUser.displayName || '',
        firstName: firebaseUser.displayName?.split(' ')[0] || '',
        lastName: firebaseUser.displayName?.split(' ').slice(1).join(' ') || '',
        role: 'user',
        isActive: true,
        permissions: [],
        createdAt: firebaseUser.metadata.creationTime || new Date().toISOString()
      }
    }
  }, [])

  // Initialize from session
  useEffect(() => {
    const init = async () => {
      console.log('[AuthContext] Initializing authentication...')

      if (isMockAuthEnabled()) {
        console.log('[AuthContext] Using mock authentication')
        try {
          const mockUser = mockAuthService.getCurrentUser()
          const mockSession = mockAuthService.getSession()

          if (mockUser && mockSession) {
            console.log('[AuthContext] Mock session found:', mockUser.email)
            setUser(mockUser)
            setSession({ access_token: mockSession.access_token })
            apiClient.setAuthToken(mockSession.access_token)
          } else {
            console.log('[AuthContext] No active mock session')
          }
        } catch (error) {
          console.error('[AuthContext] Mock auth initialization error:', error)
        }
        setIsLoading(false)
      } else {
        console.log('[AuthContext] Using Firebase authentication')

        // Set up Firebase auth state listener
        const unsubscribe = firebaseAuth.onAuthStateChange(async (firebaseUser) => {
          if (firebaseUser) {
            console.log('[AuthContext] Firebase user signed in:', firebaseUser.email)
            try {
              const token = await firebaseUser.getIdToken()
              const appUser = await transformFirebaseUser(firebaseUser)

              setUser(appUser)
              setSession({ access_token: token })
              apiClient.setAuthToken(token)

              // Connect WebSocket with Firebase token
              console.log('[AuthContext] Connecting WebSocket...')
              wsManager.connect(token)
            } catch (error) {
              console.error('[AuthContext] Error transforming Firebase user:', error)
              setUser(null)
              setSession(null)
              apiClient.setAuthToken(null)
              wsManager.disconnect()
            }
          } else {
            console.log('[AuthContext] No Firebase user signed in')
            setUser(null)
            setSession(null)
            apiClient.setAuthToken(null)

            // Disconnect WebSocket when user logs out
            console.log('[AuthContext] Disconnecting WebSocket...')
            wsManager.disconnect()
          }
          setIsLoading(false)
        })

        // Set up Firebase token refresh listener
        const unsubscribeTokenRefresh = firebaseAuth.onIdTokenChanged(async (firebaseUser) => {
          if (firebaseUser) {
            try {
              const newToken = await firebaseUser.getIdToken()
              console.log('[AuthContext] Firebase token refreshed')

              // Update WebSocket with new token
              wsManager.updateToken(newToken)

              // Update API client with new token
              apiClient.setAuthToken(newToken)
              setSession({ access_token: newToken })
            } catch (error) {
              console.error('[AuthContext] Error refreshing token:', error)
            }
          }
        })

        // Cleanup subscription on unmount
        return () => {
          console.log('[AuthContext] Cleaning up Firebase auth listeners')
          unsubscribe()
          unsubscribeTokenRefresh()
          wsManager.disconnect()
        }
      }
    }

    init()
  }, [transformFirebaseUser])

  const login = async (email: string, password: string) => {
    setIsLoading(true)
    try {
      console.log('[AuthContext] Attempting login:', email)

      if (isMockAuthEnabled()) {
        const result = await mockAuthService.signIn(email, password)

        if (!result.success || !result.user || !result.session) {
          throw new Error(result.error || 'Login failed')
        }

        console.log('[AuthContext] Mock login successful:', result.user.email)
        setUser(result.user)
        setSession({ access_token: result.session.access_token })
        apiClient.setAuthToken(result.session.access_token)

        // Connect WebSocket for mock auth
        wsManager.connect(result.session.access_token)
      } else {
        const result = await firebaseAuth.signInWithPassword({ email, password })

        if (result.error || !result.user || !result.session) {
          throw result.error || new Error('Login failed')
        }

        console.log('[AuthContext] Firebase login successful:', result.user.email)

        const appUser = await transformFirebaseUser(result.user)
        setUser(appUser)
        setSession(result.session)
        apiClient.setAuthToken(result.session.access_token)

        // Connect WebSocket with Firebase token
        wsManager.connect(result.session.access_token)
      }
    } catch (error: any) {
      console.error('[AuthContext] Login failed:', error)
      setUser(null)
      setSession(null)
      apiClient.setAuthToken(null)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const logout = useCallback(async () => {
    try {
      console.log('[AuthContext] Logging out...')

      if (isMockAuthEnabled()) {
        await mockAuthService.signOut()
      } else {
        await firebaseAuth.signOut()
      }

      apiClient.setAuthToken(null)
      setUser(null)
      setSession(null)

      // Disconnect WebSocket on logout
      wsManager.disconnect()
      console.log('[AuthContext] Logout complete')
    } catch (error) {
      console.error('[AuthContext] Logout error:', error)
      apiClient.setAuthToken(null)
      setUser(null)
      setSession(null)
    }
  }, [])

  const value: AuthContextType = {
    user,
    session,
    isAuthenticated,
    isLoading,
    login,
    logout,
    hasPermission,
    hasRole
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
