import React, { createContext, useContext, useReducer, useEffect, useCallback } from 'react'
import { apiClient } from '../src/lib/api-client'
import { firebaseAuth } from '../src/lib/firebase-client'
import type {
  AdminAuthState,
  AdminUser,
  AdminLoginResponse
} from '../src/types/admin'
import { toast } from '../src/hooks/use-toast'

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
    async (email: string, password: string, rememberMe: boolean = false): Promise<AdminLoginResponse> => {
      dispatch({ type: 'AUTH_LOADING' })

      try {
        console.log('[AdminAuth] Attempting sign in for:', email)

        // Firebase authentication implementation for Admin
        console.log('[AdminAuth] Using Firebase authentication')

        // Set persistence BEFORE signIn using the firebaseAuth module's setPersistence wrapper
        try {
          await firebaseAuth.setPersistence(rememberMe)
          console.log(`[AdminAuth] Persistence set to ${rememberMe ? 'LOCAL' : 'SESSION'}`)
        } catch (error) {
          console.error('[AdminAuth] Failed to set persistence, continuing with default:', error)
        }

        const result = await firebaseAuth.signInWithPassword({
          email: email,
          password
        })

        if (result.error || !result.user || !result.session) {
          throw result.error || new Error('Authentication failed')
        }

        // Set Firebase ID token
        const token = result.session.access_token
        console.log('[AdminAuth] Firebase token set successfully')
        apiClient.setAuthToken(token)

        // Fetch user from backend and validate admin role
        console.log('[AdminAuth → Backend] Calling /api/v1/auth/me...')

        try {
          const me = await apiClient.auth.me()

          if (!me || !me.data) {
            console.error('[AdminAuth] No user data from /auth/me, signing out')
            await firebaseAuth.signOut()

            toast({
              title: 'Sessão expirada',
              description: 'Sua sessão expirou. Por favor, faça login novamente.',
              variant: 'destructive'
            })

            const msg = 'No user data returned from backend'
            dispatch({ type: 'AUTH_ERROR', payload: msg })
            return { success: false, error: msg }
          }

          console.log('[AdminAuth ← Backend] Received user data:', {
            userId: me.data.id,
            email: me.data.email,
            role: me.data.role
          })

          const role = (me.data.role || '').toLowerCase()
          console.log('[AdminAuth] Validating role:', {
            role,
            isAdmin: ['admin', 'super_admin'].includes(role)
          })

          if (!['admin', 'super_admin'].includes(role)) {
            console.error('[AdminAuth] Role validation failed - not an admin')
            await firebaseAuth.signOut()

            toast({
              title: 'Acesso negado',
              description: 'Você não tem permissões de administrador.',
              variant: 'destructive'
            })

            const msg = 'Access denied: user is not an admin'
            dispatch({ type: 'AUTH_ERROR', payload: msg })
            return { success: false, error: msg }
          }
          console.log('[AdminAuth] Role validation successful')

          const adminUser: AdminUser = {
            id: me.data.id,
            email: me.data.email,
            full_name: me.data.full_name,
            role: me.data.role as AdminUser['role'],
            is_active: me.data.is_active,
            permissions: me.data.permissions || [],
            created_at: me.data.created_at || new Date().toISOString(),
            updated_at: me.data.updated_at || new Date().toISOString(),
            last_login: me.data.last_login || new Date().toISOString(),
            login_count: 0,
            two_factor_enabled: false,
            failed_login_attempts: 0,
            locked_until: null
          }

          const sessionExpiry = calculateSessionExpiry()
          dispatch({ type: 'AUTH_SUCCESS', payload: { user: adminUser, sessionExpiry } })

          console.log('[AdminAuth] Admin user authenticated via Firebase:', adminUser.email)
          return { success: true, user: adminUser, token }

        } catch (error: any) {
          // ANY error from /auth/me = force sign out
          console.error('[AdminAuth] /auth/me failed, signing out user', { error })

          // Don't use fallback data - always sign out
          await firebaseAuth.signOut()

          // Show error to user
          toast({
            title: 'Sessão expirada',
            description: 'Sua sessão expirou. Por favor, faça login novamente.',
            variant: 'destructive'
          })

          const errorMessage = error instanceof Error ? error.message : 'Backend authentication failed'
          dispatch({ type: 'AUTH_ERROR', payload: errorMessage })
          return { success: false, error: errorMessage }
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

      await firebaseAuth.signOut()

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

      // Firebase token refresh
      console.log('[AdminAuth] Refreshing Firebase token')

      const session = await firebaseAuth.refreshSession()
      if (!session) {
        throw new Error('No session to refresh')
      }

      const token = session.access_token
      apiClient.setAuthToken(token)

      try {
        const me = await apiClient.auth.me()

        if (!me || !me.data) {
          console.error('[AdminAuth] No user data from /auth/me, signing out')
          await firebaseAuth.signOut()

          toast({
            title: 'Sessão expirada',
            description: 'Sua sessão expirou. Por favor, faça login novamente.',
            variant: 'destructive'
          })

          dispatch({ type: 'AUTH_LOGOUT' })
          throw new Error('No user data returned from backend')
        }

        const role = (me.data.role || '').toLowerCase()
        if (!['admin', 'super_admin'].includes(role)) {
          await firebaseAuth.signOut()

          toast({
            title: 'Acesso negado',
            description: 'Você não tem permissões de administrador.',
            variant: 'destructive'
          })

          dispatch({ type: 'AUTH_LOGOUT' })
          throw new Error('User is not an admin')
        }

        const adminUser: AdminUser = {
          id: me.data.id,
          email: me.data.email,
          full_name: me.data.full_name,
          role: me.data.role as AdminUser['role'],
          is_active: me.data.is_active,
          permissions: me.data.permissions || [],
          created_at: me.data.created_at || new Date().toISOString(),
          updated_at: me.data.updated_at || new Date().toISOString(),
          last_login: me.data.last_login || new Date().toISOString(),
          login_count: state.user?.login_count || 0,
          two_factor_enabled: state.user?.two_factor_enabled || false,
          failed_login_attempts: 0,
          locked_until: null
        }

        const sessionExpiry = calculateSessionExpiry()
        dispatch({ type: 'AUTH_SUCCESS', payload: { user: adminUser, sessionExpiry } })

        console.log('[AdminAuth] Firebase token refresh successful')

      } catch (error: any) {
        // ANY error from /auth/me = force sign out
        console.error('[AdminAuth] /auth/me failed during token refresh, signing out', { error })
        await firebaseAuth.signOut()

        toast({
          title: 'Sessão expirada',
          description: 'Sua sessão expirou. Por favor, faça login novamente.',
          variant: 'destructive'
        })

        dispatch({ type: 'AUTH_LOGOUT' })
        throw error
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

        // Firebase authentication initialization
        console.log('[AdminAuth] Initializing Firebase authentication')

        const firebaseUser = await firebaseAuth.getCurrentUser()

        if (firebaseUser) {
          console.log('[AdminAuth] Found existing Firebase session:', firebaseUser.email)
          const token = await firebaseUser.getIdToken()
          console.log('[AdminAuth] Firebase token set successfully on session restore')
          apiClient.setAuthToken(token)

          try {
            console.log('[AdminAuth → Backend] Restoring session - calling /api/v1/auth/me...')
            const me = await apiClient.auth.me()

            if (!me || !me.data) {
              console.error('[AdminAuth] No user data from /auth/me, signing out')
              await firebaseAuth.signOut()

              toast({
                title: 'Sessão expirada',
                description: 'Sua sessão expirou. Por favor, faça login novamente.',
                variant: 'destructive'
              })

              dispatch({ type: 'AUTH_LOGOUT' })
              return
            }

            console.log('[AdminAuth ← Backend] Session restored successfully:', {
              userId: me.data.id,
              role: me.data.role
            })

            const role = (me.data.role || '').toLowerCase()
            if (!['admin', 'super_admin'].includes(role)) {
              console.log('[AdminAuth] User is not admin, signing out')
              await firebaseAuth.signOut()

              toast({
                title: 'Acesso negado',
                description: 'Você não tem permissões de administrador.',
                variant: 'destructive'
              })

              dispatch({ type: 'AUTH_LOGOUT' })
            } else {
              const adminUser: AdminUser = {
                id: me.data.id,
                email: me.data.email,
                full_name: me.data.full_name,
                role: me.data.role as AdminUser['role'],
                is_active: me.data.is_active,
                permissions: me.data.permissions || [],
                created_at: me.data.created_at || new Date().toISOString(),
                updated_at: me.data.updated_at || new Date().toISOString(),
                last_login: me.data.last_login || new Date().toISOString(),
                login_count: 0,
                two_factor_enabled: false,
                failed_login_attempts: 0,
                locked_until: null
              }

              const sessionExpiry = calculateSessionExpiry()
              dispatch({ type: 'AUTH_SUCCESS', payload: { user: adminUser, sessionExpiry } })
            }
          } catch (error: any) {
            // ANY error from /auth/me = force sign out
            console.error('[AdminAuth] /auth/me failed during session restore, signing out', { error })
            await firebaseAuth.signOut()

            toast({
              title: 'Sessão expirada',
              description: 'Sua sessão expirou. Por favor, faça login novamente.',
              variant: 'destructive'
            })

            dispatch({ type: 'AUTH_LOGOUT' })
          }
        } else {
          console.log('[AdminAuth] No existing Firebase session')
          dispatch({ type: 'AUTH_LOGOUT' })
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
