import React, { createContext, useContext, useReducer, useEffect, useCallback } from 'react'
import { apiClient } from '../src/lib/api-client'
import { isMockAuthEnabled } from '../src/config/mock.config'
import mockAuthService from '../src/lib/mock-auth-service'
import { firebaseAuth } from '../src/lib/firebase-client'
import type {
  AdminAuthState,
  AdminUser,
  AdminLoginResponse
} from '../src/types/admin'

interface AdminAuthContextValue {
  state: AdminAuthState
  signIn: (email: string, password: string, rememberMe?: boolean) => Promise<AdminLoginResponse>
  login: (email: string, password: string, rememberMe?: boolean) => Promise<AdminLoginResponse>
  signOut: () => Promise<void>
  logout: () => Promise<void>
  refreshToken: () => Promise<void>
  extendSession: () => Promise<void>
  updateUser: (updates: Partial<AdminUser>) => Promise<void>
}

type AdminAuthAction =
  | { type: 'AUTH_LOADING' }
  | { type: 'AUTH_SUCCESS'; payload: { user: AdminUser; sessionExpiry: Date } }
  | { type: 'AUTH_ERROR'; payload: string }
  | { type: 'AUTH_LOGOUT' }
  | { type: 'UPDATE_USER'; payload: Partial<AdminUser> }
  | { type: 'EXTEND_SESSION'; payload: Date }

function adminAuthReducer(state: AdminAuthState, action: AdminAuthAction): AdminAuthState {
  switch (action.type) {
    case 'AUTH_LOADING':
      return { ...state, isLoading: true, error: null }

    case 'AUTH_SUCCESS':
      return {
        ...state,
        user: action.payload.user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        sessionExpiry: action.payload.sessionExpiry
      }

    case 'AUTH_ERROR':
      return {
        ...state,
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: action.payload,
        sessionExpiry: null
      }

    case 'AUTH_LOGOUT':
      return {
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        sessionExpiry: null
      }

    case 'UPDATE_USER':
      if (!state.user) return state
      return {
        ...state,
        user: { ...state.user, ...action.payload }
      }

    case 'EXTEND_SESSION':
      return {
        ...state,
        sessionExpiry: action.payload
      }

    default:
      return state
  }
}

const AdminAuthContext = createContext<AdminAuthContextValue | undefined>(undefined)

interface AdminAuthProviderProps {
  children: React.ReactNode
}

const initialState: AdminAuthState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  sessionExpiry: null
}

export const AdminAuthProvider: React.FC<AdminAuthProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(adminAuthReducer, initialState)

  const calculateSessionExpiry = useCallback((): Date => {
    return new Date(Date.now() + 3600000)
  }, [])

  const signIn = useCallback(
    async (email: string, password: string, _rememberMe?: boolean): Promise<AdminLoginResponse> => {
      dispatch({ type: 'AUTH_LOADING' })

      try {
        console.log('[AdminAuth] Attempting sign in for:', email)

        if (isMockAuthEnabled()) {
          const result = await mockAuthService.signIn(email, password)

          if (!result.success || !result.user) {
            throw new Error(result.error || 'Authentication failed')
          }

          if (result.user.role !== 'admin') {
            throw new Error('Access denied: user is not an admin')
          }

          const adminUser: AdminUser = {
            id: result.user.id,
            email: result.user.email,
            full_name: result.user.full_name,
            role: result.user.role as AdminUser['role'],
            is_active: result.user.is_active,
            permissions: result.user.permissions,
            created_at: result.user.created_at,
            updated_at: result.user.updated_at || new Date().toISOString(),
            last_login: result.user.last_login || new Date().toISOString(),
            login_count: 0,
            two_factor_enabled: false,
            failed_login_attempts: 0,
            locked_until: null
          }

          const sessionExpiry = calculateSessionExpiry()

          if (result.session) {
            apiClient.setAuthToken(result.session.access_token)
          }

          dispatch({
            type: 'AUTH_SUCCESS',
            payload: {
              user: adminUser,
              sessionExpiry
            }
          })

          console.log('[AdminAuth] Admin user authenticated:', adminUser.email)

          return {
            success: true,
            user: adminUser,
            token: result.session?.access_token || '',
            refreshToken: ''
          }
        } else {
          // Firebase authentication implementation for Admin
          console.log('[AdminAuth] Using Firebase authentication')

          const result = await firebaseAuth.signInWithPassword({
            email: email,
            password
          })

          if (result.error || !result.user || !result.session) {
            throw result.error || new Error('Authentication failed')
          }

          // Set Firebase ID token
          const token = result.session.access_token
          apiClient.setAuthToken(token)

          // Fetch user from backend and validate admin role
          const me = await apiClient.auth.me()
          const role = (me.data.role || '').toLowerCase()
          if (!['admin', 'super_admin'].includes(role)) {
            await firebaseAuth.signOut()
            const msg = 'Access denied: user is not an admin'
            dispatch({ type: 'AUTH_ERROR', payload: msg })
            return { success: false, error: msg }
          }

          const adminUser: AdminUser = {
            id: me.data.id,
            email: me.data.email,
            full_name: me.data.full_name,
            role: me.data.role as AdminUser['role'],
            is_active: me.data.is_active,
            permissions: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            last_login: new Date().toISOString(),
            login_count: 0,
            two_factor_enabled: false,
            failed_login_attempts: 0,
            locked_until: null
          }

          const sessionExpiry = calculateSessionExpiry()
          dispatch({ type: 'AUTH_SUCCESS', payload: { user: adminUser, sessionExpiry } })

          console.log('[AdminAuth] Admin user authenticated via Firebase:', adminUser.email)
          return { success: true, user: adminUser, token }
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Authentication failed'
        console.error('[AdminAuth] Sign in failed:', errorMessage)
        dispatch({ type: 'AUTH_ERROR', payload: errorMessage })

        return {
          success: false,
          error: errorMessage
        }
      }
    },
    [calculateSessionExpiry]
  )

  const signOut = useCallback(async (): Promise<void> => {
    try {
      console.log('[AdminAuth] Signing out')

      if (isMockAuthEnabled()) {
        await mockAuthService.signOut()
      } else {
        await firebaseAuth.signOut()
      }

      apiClient.setAuthToken(null)
      dispatch({ type: 'AUTH_LOGOUT' })
      console.log('[AdminAuth] Sign out successful')
    } catch (error) {
      console.error('[AdminAuth] Sign out error:', error)
      apiClient.setAuthToken(null)
      dispatch({ type: 'AUTH_LOGOUT' })
      throw error
    }
  }, [])

  const refreshToken = useCallback(async (): Promise<void> => {
    try {
      console.log('[AdminAuth] Refreshing token')

      if (isMockAuthEnabled()) {
        const result = await mockAuthService.refreshSession()

        if (!result.success || !result.user) {
          throw new Error('No session to refresh')
        }

        const adminUser: AdminUser = {
          id: result.user.id,
          email: result.user.email,
          full_name: result.user.full_name,
          role: result.user.role as AdminUser['role'],
          is_active: result.user.is_active,
          permissions: result.user.permissions,
          created_at: result.user.created_at,
          updated_at: result.user.updated_at || new Date().toISOString(),
          last_login: result.user.last_login || new Date().toISOString(),
          login_count: state.user?.login_count || 0,
          two_factor_enabled: state.user?.two_factor_enabled || false,
          failed_login_attempts: 0,
          locked_until: null
        }

        const sessionExpiry = calculateSessionExpiry()

        dispatch({
          type: 'AUTH_SUCCESS',
          payload: {
            user: adminUser,
            sessionExpiry
          }
        })

        console.log('[AdminAuth] Token refresh successful')
      } else {
        // Firebase token refresh
        console.log('[AdminAuth] Refreshing Firebase token')

        const session = await firebaseAuth.refreshSession()
        if (!session) {
          throw new Error('No session to refresh')
        }

        const token = session.access_token
        apiClient.setAuthToken(token)

        const me = await apiClient.auth.me()
        const role = (me.data.role || '').toLowerCase()
        if (!['admin', 'super_admin'].includes(role)) {
          throw new Error('User is not an admin')
        }

        const adminUser: AdminUser = {
          id: me.data.id,
          email: me.data.email,
          full_name: me.data.full_name,
          role: me.data.role as AdminUser['role'],
          is_active: me.data.is_active,
          permissions: [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          last_login: new Date().toISOString(),
          login_count: state.user?.login_count || 0,
          two_factor_enabled: state.user?.two_factor_enabled || false,
          failed_login_attempts: 0,
          locked_until: null
        }

        const sessionExpiry = calculateSessionExpiry()
        dispatch({ type: 'AUTH_SUCCESS', payload: { user: adminUser, sessionExpiry } })

        console.log('[AdminAuth] Firebase token refresh successful')
      }
    } catch (error) {
      console.error('[AdminAuth] Token refresh error:', error)
      dispatch({ type: 'AUTH_LOGOUT' })
      throw error
    }
  }, [calculateSessionExpiry, state.user])

  const extendSession = useCallback(async (): Promise<void> => {
    try {
      await refreshToken()
      console.log('[AdminAuth] Session extended successfully')
    } catch (error) {
      console.error('[AdminAuth] Failed to extend session:', error)
      throw error
    }
  }, [refreshToken])

  const updateUser = useCallback(
    async (updates: Partial<AdminUser>): Promise<void> => {
      if (!state.user) {
        throw new Error('No user logged in')
      }

      try {
        console.log('[AdminAuth] Updating user profile:', updates)
        dispatch({ type: 'UPDATE_USER', payload: updates })
        console.log('[AdminAuth] User profile updated successfully')
      } catch (error) {
        console.error('[AdminAuth] Failed to update user:', error)
        throw error
      }
    },
    [state.user]
  )

  useEffect(() => {
    let mounted = true

    const initializeAuth = async () => {
      try {
        console.log('[AdminAuth] Initializing auth...')

        if (isMockAuthEnabled()) {
          const user = mockAuthService.getCurrentUser()
          const session = mockAuthService.getSession()

          if (!mounted) return

          if (user && user.role === 'admin' && session) {
            console.log('[AdminAuth] Found existing admin session:', user.email)

            const adminUser: AdminUser = {
              id: user.id,
              email: user.email,
              full_name: user.full_name,
              role: user.role as AdminUser['role'],
              is_active: user.is_active,
              permissions: user.permissions,
              created_at: user.created_at,
              updated_at: user.updated_at || new Date().toISOString(),
              last_login: user.last_login || new Date().toISOString(),
              login_count: 0,
              two_factor_enabled: false,
              failed_login_attempts: 0,
              locked_until: null
            }

            const sessionExpiry = new Date(session.expires_at)

            apiClient.setAuthToken(session.access_token)

            dispatch({
              type: 'AUTH_SUCCESS',
              payload: {
                user: adminUser,
                sessionExpiry
              }
            })
          } else {
            console.log('[AdminAuth] No existing admin session')
            dispatch({ type: 'AUTH_LOGOUT' })
          }
        } else {
          // Firebase authentication initialization
          console.log('[AdminAuth] Initializing Firebase authentication')

          const firebaseUser = await firebaseAuth.getCurrentUser()

          if (firebaseUser) {
            console.log('[AdminAuth] Found existing Firebase session:', firebaseUser.email)
            const token = await firebaseUser.getIdToken()
            apiClient.setAuthToken(token)

            try {
              const me = await apiClient.auth.me()
              const role = (me.data.role || '').toLowerCase()
              if (!['admin', 'super_admin'].includes(role)) {
                console.log('[AdminAuth] User is not admin, signing out')
                await firebaseAuth.signOut()
                dispatch({ type: 'AUTH_LOGOUT' })
              } else {
                const adminUser: AdminUser = {
                  id: me.data.id,
                  email: me.data.email,
                  full_name: me.data.full_name,
                  role: me.data.role as AdminUser['role'],
                  is_active: me.data.is_active,
                  permissions: [],
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                  last_login: new Date().toISOString(),
                  login_count: 0,
                  two_factor_enabled: false,
                  failed_login_attempts: 0,
                  locked_until: null
                }

                const sessionExpiry = calculateSessionExpiry()
                dispatch({ type: 'AUTH_SUCCESS', payload: { user: adminUser, sessionExpiry } })
              }
            } catch (error) {
              console.error('[AdminAuth] Failed to fetch user from backend:', error)
              dispatch({ type: 'AUTH_LOGOUT' })
            }
          } else {
            console.log('[AdminAuth] No existing Firebase session')
            dispatch({ type: 'AUTH_LOGOUT' })
          }
        }
      } catch (error) {
        console.error('[AdminAuth] Failed to initialize auth:', error)
        if (mounted) {
          dispatch({ type: 'AUTH_LOGOUT' })
        }
      }
    }

    initializeAuth()

    return () => {
      mounted = false
    }
  }, [])

  const value: AdminAuthContextValue = {
    state,
    signIn,
    login: signIn,
    signOut,
    logout: signOut,
    refreshToken,
    extendSession,
    updateUser
  }

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>
}

export const useAdminAuth = (): AdminAuthContextValue => {
  const context = useContext(AdminAuthContext)
  if (!context) {
    throw new Error('useAdminAuth must be used within AdminAuthProvider')
  }
  return context
}

export default AdminAuthContext
