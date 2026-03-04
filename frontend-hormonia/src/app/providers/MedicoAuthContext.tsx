/**
 * Medico auth hook built on top of AuthContext.
 */
import { useAuth } from './AuthContext'
import { getErrorMessage } from '@/lib/utils/type-guards'

export interface MedicoProfile {
  full_name: string
  crm: string
}

export interface MedicoAuthContextValue {
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  medico: MedicoProfile | null
  signIn: (
    identifier: string,
    password: string,
    remember?: boolean
  ) => Promise<{ success: boolean; error?: string }>
  signOut: () => Promise<{ success: boolean }>
}

export function useMedicoAuth(): MedicoAuthContextValue {
  const { user, isInitializing, login, logout } = useAuth()

  const isAuthenticated = !!user
  const error = null as string | null
  const medico = user
    ? {
        full_name:
          (user as { full_name?: string; name?: string }).full_name ||
          (user as { name?: string }).name ||
          '',
        crm: (user as { crm?: string }).crm || '',
      }
    : null

  const signIn = async (identifier: string, password: string, remember = false) => {
    try {
      await login(identifier, password, remember)
      return { success: true }
    } catch (e: unknown) {
      const errorMessage = getErrorMessage(e)
      return { success: false, error: errorMessage }
    }
  }

  const signOut = async () => {
    await logout()
    return { success: true }
  }

  return {
    isAuthenticated,
    isLoading: isInitializing,
    error,
    medico,
    signIn,
    signOut,
  }
}

export default useMedicoAuth
