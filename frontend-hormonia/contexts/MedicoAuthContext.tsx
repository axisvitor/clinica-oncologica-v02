import React, { createContext, useContext, useReducer, useEffect, useCallback } from 'react'
import { apiClient } from '../src/lib/api-client'
import { firebaseAuth } from '../src/lib/firebase-client'
import type {
  MedicoAuthState,
  MedicoUser,
  MedicoLoginResponse
} from '../src/types/medico'

interface MedicoAuthContextValue {
  state: MedicoAuthState
  dispatch: React.Dispatch<MedicoAuthAction>
  signIn: (email: string, password: string, rememberMe?: boolean) => Promise<MedicoLoginResponse>
  login: (email: string, password: string, rememberMe?: boolean) => Promise<MedicoLoginResponse>
  signOut: () => Promise<void>
  logout: () => Promise<void>
  refreshToken: () => Promise<void>
  extendSession: () => Promise<void>
  updatePerfil: (updates: Partial<MedicoUser>) => Promise<void>
  getPacientesAtribuidos: () => Promise<string[]>
}

type MedicoAuthAction =
  | { type: 'AUTH_LOADING' }
  | { type: 'AUTH_SUCCESS'; payload: { user: MedicoUser; sessionExpiry: Date; pacientes: string[] } }
  | { type: 'AUTH_ERROR'; payload: string }
  | { type: 'AUTH_LOGOUT' }
  | { type: 'UPDATE_USER'; payload: Partial<MedicoUser> }
  | { type: 'EXTEND_SESSION'; payload: Date }
  | { type: 'UPDATE_PACIENTES'; payload: string[] }

function medicoAuthReducer(state: MedicoAuthState, action: MedicoAuthAction): MedicoAuthState {
  switch (action.type) {
    case 'AUTH_LOADING':
      return { ...state, isLoading: true, error: null }

    case 'AUTH_SUCCESS':
      return {
        ...state,
        user: action.payload.user,
        medico: action.payload.user,
        token: '',
        isAuthenticated: true,
        isLoading: false,
        error: null,
        sessionExpiry: action.payload.sessionExpiry,
        pacientes: action.payload.pacientes
      }

    case 'AUTH_ERROR':
      return {
        ...state,
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: action.payload,
        sessionExpiry: null,
        pacientes: []
      }

    case 'AUTH_LOGOUT':
      return {
        user: null,
        medico: null,
        token: undefined,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        sessionExpiry: null,
        pacientes: []
      }

    case 'UPDATE_USER':
      if (!state.user) return state
      const updatedUser = { ...state.user, ...action.payload }
      return {
        ...state,
        user: updatedUser,
        medico: updatedUser
      }

    case 'EXTEND_SESSION':
      return {
        ...state,
        sessionExpiry: action.payload
      }

    case 'UPDATE_PACIENTES':
      return {
        ...state,
        pacientes: action.payload
      }

    default:
      return state
  }
}

const MedicoAuthContext = createContext<MedicoAuthContextValue | undefined>(undefined)

interface MedicoAuthProviderProps {
  children: React.ReactNode
}

const initialState: MedicoAuthState = {
  user: null,
  medico: null,
  token: undefined,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  sessionExpiry: null,
  pacientes: []
}

export const MedicoAuthProvider: React.FC<MedicoAuthProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(medicoAuthReducer, initialState)

  const calculateSessionExpiry = useCallback((): Date => {
    return new Date(Date.now() + 3600000)
  }, [])

  const fetchPacientesAtribuidos = useCallback(async (_medicoId: string): Promise<string[]> => {
    try {
      // TODO: Implement backend API call to fetch assigned patients
      return []
    } catch (error) {
      console.error('[MedicoAuth] Failed to fetch pacientes:', error)
      return []
    }
  }, [])

  const signIn = useCallback(
    async (email: string, password: string, _rememberMe?: boolean): Promise<MedicoLoginResponse> => {
      dispatch({ type: 'AUTH_LOADING' })

      try {
        console.log('[MedicoAuth] Attempting sign in for:', email)

        {
          // Firebase authentication implementation for Medico
          console.log('[MedicoAuth] Using Firebase authentication')

          // Convert CRM to email format if needed (e.g., "12345" -> "12345@medico.neoplasiaslitoral.com.br")
          const loginEmail = email.includes('@') ? email : `${email}@medico.neoplasiaslitoral.com.br`

          const result = await firebaseAuth.signInWithPassword({
            email: loginEmail,
            password
          })

          if (result.error || !result.user || !result.session) {
            throw result.error || new Error('Login falhou')
          }

          console.log('[MedicoAuth] Firebase login successful:', result.user.email)

          // Set Firebase ID token
          const token = result.session.access_token
          console.log('[MedicoAuth → Backend] Setting Firebase token:', {
            tokenLength: token.length,
            tokenPreview: token.substring(0, 20) + '...'
          })
          apiClient.setAuthToken(token)

          // Fetch user from backend and validate doctor role
          console.log('[MedicoAuth → Backend] Calling /api/v1/auth/me...')
          const me = await apiClient.auth.me()
          console.log('[MedicoAuth ← Backend] Received user data:', {
            userId: me.data.id,
            email: me.data.email,
            role: me.data.role
          })
          const role = (me.data.role || '').toLowerCase()
          console.log('[MedicoAuth] Validating role:', {
            role,
            isDoctor: ['medico', 'doctor'].includes(role)
          })
          if (!['medico', 'doctor'].includes(role)) {
            console.error('[MedicoAuth] Role validation failed - not a doctor')
            await firebaseAuth.signOut()
            const msg = 'Acesso negado: usuário não é médico'
            dispatch({ type: 'AUTH_ERROR', payload: msg })
            return { success: false, error: msg }
          }
          console.log('[MedicoAuth] Role validation successful')

          // Extract CRM from email if available
          const crmMatch = me.data.email.match(/^([^@]+)@/)
          const crm = me.data['crm'] || crmMatch?.[1] || ''

          const medicoUser: MedicoUser = {
            id: me.data.id,
            email: me.data.email,
            full_name: me.data.full_name || me.data['nome'] || '',
            role: 'doctor',
            is_active: me.data.is_active,
            permissions: me.data.permissions || [],
            created_at: me.data.created_at,
            updated_at: me.data['updated_at'] || new Date().toISOString(),
            last_login: new Date().toISOString(),
            login_count: me.data['login_count'] || 0,
            two_factor_enabled: me.data['two_factor_enabled'] || false,
            failed_login_attempts: 0,
            locked_until: null,
            crm: crm,
            especialidade: me.data['especialidade'] || 'Oncologia',
            conselho_regional: me.data['conselho_regional'] || 'CRM-SC',
            pacientes_atribuidos: me.data['pacientes_atribuidos'] || []
          }

          const sessionExpiry = calculateSessionExpiry()
          const pacientes = await fetchPacientesAtribuidos(medicoUser.id)

          dispatch({
            type: 'AUTH_SUCCESS',
            payload: {
              user: medicoUser,
              sessionExpiry,
              pacientes
            }
          })

          console.log('[MedicoAuth] Medico user authenticated via Firebase:', medicoUser.email)

          return {
            success: true,
            user: medicoUser,
            token: token,
            refreshToken: '',
            redirectTo: '/medico/dashboard'
          }
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Falha na autenticação'
        console.error('[MedicoAuth] Sign in failed:', errorMessage)
        dispatch({ type: 'AUTH_ERROR', payload: errorMessage })

        return {
          success: false,
          error: errorMessage
        }
      }
    },
    [calculateSessionExpiry, fetchPacientesAtribuidos]
  )

  const signOut = useCallback(async (): Promise<void> => {
    try {
      console.log('[MedicoAuth] Signing out')

      await firebaseAuth.signOut()

      apiClient.setAuthToken(null)
      dispatch({ type: 'AUTH_LOGOUT' })
      console.log('[MedicoAuth] Sign out successful')
    } catch (error) {
      console.error('[MedicoAuth] Sign out error:', error)
      apiClient.setAuthToken(null)
      dispatch({ type: 'AUTH_LOGOUT' })
      throw error
    }
  }, [])

  const refreshToken = useCallback(async (): Promise<void> => {
    try {
      console.log('[MedicoAuth] Refreshing token')

      // Firebase token refresh
      console.log('[MedicoAuth] Refreshing Firebase token')

      const session = await firebaseAuth.refreshSession()
      if (!session) {
        throw new Error('No session to refresh')
      }

      const token = session.access_token
      apiClient.setAuthToken(token)

      const me = await apiClient.auth.me()
      const role = (me.data.role || '').toLowerCase()
      if (!['medico', 'doctor'].includes(role)) {
        throw new Error('User is not a medico')
      }

      // Extract CRM from email if available
      const crmMatch = me.data.email.match(/^([^@]+)@/)
      const crm = me.data['crm'] || crmMatch?.[1] || ''

      const medicoUser: MedicoUser = {
        id: me.data.id,
        email: me.data.email,
        full_name: me.data.full_name || me.data['nome'] || '',
        role: 'doctor',
        is_active: me.data.is_active,
        permissions: me.data.permissions || [],
        created_at: me.data.created_at,
        updated_at: me.data['updated_at'] || new Date().toISOString(),
        last_login: new Date().toISOString(),
        login_count: me.data['login_count'] || state.user?.login_count || 0,
        two_factor_enabled: me.data['two_factor_enabled'] || state.user?.two_factor_enabled || false,
        failed_login_attempts: 0,
        locked_until: null,
        crm: crm,
        especialidade: me.data['especialidade'] || 'Oncologia',
        conselho_regional: me.data['conselho_regional'] || 'CRM-SC',
        pacientes_atribuidos: me.data['pacientes_atribuidos'] || []
      }

      const sessionExpiry = calculateSessionExpiry()
      const pacientes = await fetchPacientesAtribuidos(medicoUser.id)

      dispatch({
        type: 'AUTH_SUCCESS',
        payload: {
          user: medicoUser,
          sessionExpiry,
          pacientes
        }
      })

      console.log('[MedicoAuth] Firebase token refresh successful')
    } catch (error) {
      console.error('[MedicoAuth] Token refresh error:', error)
      dispatch({ type: 'AUTH_LOGOUT' })
      throw error
    }
  }, [calculateSessionExpiry, fetchPacientesAtribuidos, state.user])

  const extendSession = useCallback(async (): Promise<void> => {
    try {
      await refreshToken()
      console.log('[MedicoAuth] Session extended successfully')
    } catch (error) {
      console.error('[MedicoAuth] Failed to extend session:', error)
      throw error
    }
  }, [refreshToken])

  const updatePerfil = useCallback(
    async (updates: Partial<MedicoUser>): Promise<void> => {
      if (!state.user) {
        throw new Error('No user logged in')
      }

      try {
        console.log('[MedicoAuth] Updating medico profile:', updates)
        dispatch({ type: 'UPDATE_USER', payload: updates })
        console.log('[MedicoAuth] Medico profile updated successfully')
      } catch (error) {
        console.error('[MedicoAuth] Failed to update medico profile:', error)
        throw error
      }
    },
    [state.user]
  )

  const getPacientesAtribuidos = useCallback(async (): Promise<string[]> => {
    if (!state.user) {
      throw new Error('No medico logged in')
    }

    try {
      const pacientes = await fetchPacientesAtribuidos(state.user.id)
      dispatch({ type: 'UPDATE_PACIENTES', payload: pacientes })
      return pacientes
    } catch (error) {
      console.error('[MedicoAuth] Failed to get pacientes atribuidos:', error)
      throw error
    }
  }, [state.user, fetchPacientesAtribuidos])

  useEffect(() => {
    let mounted = true

    const initializeAuth = async () => {
      try {
        console.log('[MedicoAuth] Initializing auth...')

        // Firebase authentication initialization
        console.log('[MedicoAuth] Initializing Firebase authentication')

        const firebaseUser = await firebaseAuth.getCurrentUser()

        if (firebaseUser) {
          console.log('[MedicoAuth] Found existing Firebase session:', firebaseUser.email)
          const token = await firebaseUser.getIdToken()
          console.log('[MedicoAuth → Backend] Setting Firebase token on session restore')
          apiClient.setAuthToken(token)

          try {
            console.log('[MedicoAuth → Backend] Restoring session - calling /api/v1/auth/me...')
            const me = await apiClient.auth.me()
            console.log('[MedicoAuth ← Backend] Session restored successfully:', {
              userId: me.data.id,
              role: me.data.role
            })
            const role = (me.data.role || '').toLowerCase()
            if (!['medico', 'doctor'].includes(role)) {
              console.log('[MedicoAuth] User is not medico, signing out')
              await firebaseAuth.signOut()
              dispatch({ type: 'AUTH_LOGOUT' })
            } else {
              // Extract CRM from email if available
              const crmMatch = me.data.email.match(/^([^@]+)@/)
              const crm = me.data['crm'] || crmMatch?.[1] || ''

              const medicoUser: MedicoUser = {
                id: me.data.id,
                email: me.data.email,
                full_name: me.data.full_name || me.data['nome'] || '',
                role: 'doctor',
                is_active: me.data.is_active,
                permissions: me.data.permissions || [],
                created_at: me.data.created_at,
                updated_at: me.data['updated_at'] || new Date().toISOString(),
                last_login: new Date().toISOString(),
                login_count: me.data['login_count'] || 0,
                two_factor_enabled: me.data['two_factor_enabled'] || false,
                failed_login_attempts: 0,
                locked_until: null,
                crm: crm,
                especialidade: me.data['especialidade'] || 'Oncologia',
                conselho_regional: me.data['conselho_regional'] || 'CRM-SC',
                pacientes_atribuidos: me.data['pacientes_atribuidos'] || []
              }

              const sessionExpiry = calculateSessionExpiry()
              const pacientes = await fetchPacientesAtribuidos(medicoUser.id)

              dispatch({
                type: 'AUTH_SUCCESS',
                payload: {
                  user: medicoUser,
                  sessionExpiry,
                  pacientes
                }
              })
            }
          } catch (error) {
            console.error('[MedicoAuth] Failed to fetch user from backend:', error)
            dispatch({ type: 'AUTH_LOGOUT' })
          }
        } else {
          console.log('[MedicoAuth] No existing Firebase session')
          dispatch({ type: 'AUTH_LOGOUT' })
        }
      } catch (error) {
        console.error('[MedicoAuth] Failed to initialize auth:', error)
        if (mounted) {
          dispatch({ type: 'AUTH_LOGOUT' })
        }
      }
    }

    initializeAuth()

    return () => {
      mounted = false
    }
  }, [calculateSessionExpiry, fetchPacientesAtribuidos])

  const value: MedicoAuthContextValue = {
    state,
    dispatch,
    signIn,
    login: signIn,
    signOut,
    logout: signOut,
    refreshToken,
    extendSession,
    updatePerfil,
    getPacientesAtribuidos
  }

  return <MedicoAuthContext.Provider value={value}>{children}</MedicoAuthContext.Provider>
}

export const useMedicoAuth = (): MedicoAuthContextValue => {
  const context = useContext(MedicoAuthContext)
  if (!context) {
    throw new Error('useMedicoAuth must be used within MedicoAuthProvider')
  }
  return context
}

export default MedicoAuthContext
