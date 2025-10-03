import React, { createContext, useContext, useReducer, useEffect, useCallback } from 'react'
import { apiClient } from '../src/lib/api-client'
import { isMockAuthEnabled } from '../src/config/mock.config'
import mockAuthService from '../src/lib/mock-auth-service'
import { getMockPatientsByMedico } from '../src/mocks/patients.mock'
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

  const fetchPacientesAtribuidos = useCallback(async (medicoId: string): Promise<string[]> => {
    try {
      if (isMockAuthEnabled()) {
        const patients = getMockPatientsByMedico(medicoId)
        return patients.map(p => p.id)
      }
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

        if (isMockAuthEnabled()) {
          const result = await mockAuthService.signIn(email, password)

          if (!result.success || !result.user) {
            throw new Error(result.error || 'Authentication failed')
          }

          if (result.user.role !== 'medico') {
            throw new Error('Acesso negado: usuário não é médico')
          }

          const medicoUser: MedicoUser = {
            id: result.user.id,
            email: result.user.email,
            full_name: result.user.full_name,
            role: 'doctor',
            is_active: result.user.is_active,
            permissions: result.user.permissions,
            created_at: result.user.created_at,
            updated_at: result.user.updated_at || new Date().toISOString(),
            last_login: result.user.last_login || new Date().toISOString(),
            login_count: 0,
            two_factor_enabled: false,
            failed_login_attempts: 0,
            locked_until: null,
            crm: result.user.crm || '',
            especialidade: result.user.especialidade || 'Oncologia',
            conselho_regional: result.user.conselho_regional || 'CRM-SC',
            pacientes_atribuidos: result.user.pacientes_atribuidos || []
          }

          const sessionExpiry = calculateSessionExpiry()
          const pacientes = await fetchPacientesAtribuidos(medicoUser.id)

          if (result.session) {
            apiClient.setAuthToken(result.session.access_token)
          }

          dispatch({
            type: 'AUTH_SUCCESS',
            payload: {
              user: medicoUser,
              sessionExpiry,
              pacientes
            }
          })

          console.log('[MedicoAuth] Medico user authenticated:', medicoUser.email)

          return {
            success: true,
            user: medicoUser,
            token: result.session?.access_token || '',
            refreshToken: result.session?.refresh_token || '',
            redirectTo: '/medico/dashboard'
          }
        } else {
          throw new Error('Firebase authentication not implemented yet')
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Authentication failed'
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

      if (isMockAuthEnabled()) {
        await mockAuthService.signOut()
      }

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

      if (isMockAuthEnabled()) {
        const result = await mockAuthService.refreshSession()

        if (!result.success || !result.user) {
          throw new Error('No session to refresh')
        }

        const medicoUser: MedicoUser = {
          id: result.user.id,
          email: result.user.email,
          full_name: result.user.full_name,
          role: 'doctor',
          is_active: result.user.is_active,
          permissions: result.user.permissions,
          created_at: result.user.created_at,
          updated_at: result.user.updated_at || new Date().toISOString(),
          last_login: result.user.last_login || new Date().toISOString(),
          login_count: state.user?.login_count || 0,
          two_factor_enabled: state.user?.two_factor_enabled || false,
          failed_login_attempts: 0,
          locked_until: null,
          crm: result.user.crm || state.user?.crm || '',
          especialidade: result.user.especialidade || state.user?.especialidade || 'Oncologia',
          conselho_regional: result.user.conselho_regional || state.user?.conselho_regional || 'CRM-SC',
          pacientes_atribuidos: result.user.pacientes_atribuidos || state.user?.pacientes_atribuidos || []
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

        console.log('[MedicoAuth] Token refresh successful')
      } else {
        throw new Error('Firebase authentication not implemented yet')
      }
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

        if (isMockAuthEnabled()) {
          const user = mockAuthService.getCurrentUser()
          const session = mockAuthService.getSession()

          if (!mounted) return

          if (user && user.role === 'medico' && session) {
            console.log('[MedicoAuth] Found existing medico session:', user.email)

            const medicoUser: MedicoUser = {
              id: user.id,
              email: user.email,
              full_name: user.full_name,
              role: 'doctor',
              is_active: user.is_active,
              permissions: user.permissions,
              created_at: user.created_at,
              updated_at: user.updated_at || new Date().toISOString(),
              last_login: user.last_login || new Date().toISOString(),
              login_count: 0,
              two_factor_enabled: false,
              failed_login_attempts: 0,
              locked_until: null,
              crm: user.crm || '',
              especialidade: user.especialidade || 'Oncologia',
              conselho_regional: user.conselho_regional || 'CRM-SC',
              pacientes_atribuidos: user.pacientes_atribuidos || []
            }

            const sessionExpiry = new Date(session.expires_at)
            const pacientes = await fetchPacientesAtribuidos(medicoUser.id)

            apiClient.setAuthToken(session.access_token)

            dispatch({
              type: 'AUTH_SUCCESS',
              payload: {
                user: medicoUser,
                sessionExpiry,
                pacientes
              }
            })
          } else {
            console.log('[MedicoAuth] No existing medico session')
            dispatch({ type: 'AUTH_LOGOUT' })
          }
        } else {
          console.log('[MedicoAuth] Firebase auth will be implemented later')
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
  }, [fetchPacientesAtribuidos])

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
