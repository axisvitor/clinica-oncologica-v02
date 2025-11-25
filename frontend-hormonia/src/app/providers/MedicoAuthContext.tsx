/**
 * Medico Auth Context - Legacy compatibility adapter over AuthContext
 * Exposes individual properties and legacy { state, signIn, signOut } API for backward compatibility
 */
import { useAuth } from './AuthContext'
import { getErrorMessage } from '@/lib/utils/type-guards'

export interface MedicoAuthState {
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  medico: {
    full_name: string
    crm: string
  } | null
}

export interface MedicoAuthContextValue extends MedicoAuthState {
  signIn: (identifier: string, password: string, remember?: boolean) => Promise<{ success: boolean; error?: string }>
  signOut: () => Promise<{ success: boolean }>
  // Legacy state property for backward compatibility
  state: MedicoAuthState
}

export function useMedicoAuth(): MedicoAuthContextValue {
  const { user, isLoading, login, logout } = useAuth()

  const isAuthenticated = !!user
  const error = null as string | null
  const medico = user
    ? {
        full_name: (user as any).full_name || (user as any).name || '',
        crm: (user as any).crm || '',
      }
    : null

  const state: MedicoAuthState = {
    isAuthenticated,
    isLoading,
    error,
    medico,
  }

  const signIn = async (identifier: string, password: string, remember = false) => {
    try {
      await login(identifier, password, remember)
      return { success: true }
    } catch (e: unknown) {
      const errorMessage = getErrorMessage(e);
      return { success: false, error: errorMessage }
    }
  }

  const signOut = async () => {
    await logout()
    return { success: true }
  }

  return {
    // Individual properties (new API)
    isAuthenticated,
    isLoading,
    error,
    medico,
    signIn,
    signOut,
    // Legacy state object for backward compatibility
    state,
  }
}

export default useMedicoAuth
