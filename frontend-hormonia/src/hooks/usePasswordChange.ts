import { useState } from 'react'
import { getAuth, reauthenticateWithCredential, EmailAuthProvider } from 'firebase/auth'
import { toast } from '@/hooks/use-toast'
import { apiClient } from '@/lib/api-client'
import { logger } from '@/lib/logger'

export interface PasswordChangeData {
  current_password: string
  new_password: string
  confirm_password?: string
}

export interface UsePasswordChangeReturn {
  changePassword: (data: PasswordChangeData) => Promise<void>
  isChangingPassword: boolean
  error: string | null
  clearError: () => void
}

/**
 * Hook for changing user password with Firebase re-authentication
 *
 * Security flow:
 * 1. Re-authenticate user with current password (Firebase client-side)
 * 2. Send password change request to backend with current password
 * 3. Backend validates current password via Firebase Auth API
 * 4. Backend updates password via Firebase Admin SDK
 * 5. Backend invalidates all sessions (force re-login)
 *
 * This double validation (client + server) provides defense in depth.
 *
 * @returns Password change functions and state
 */
export function usePasswordChange(): UsePasswordChangeReturn {
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const clearError = () => setError(null)

  const changePassword = async (data: PasswordChangeData): Promise<void> => {
    setIsChangingPassword(true)
    setError(null)

    try {
      const auth = getAuth()
      const user = auth.currentUser

      if (!user || !user.email) {
        throw new Error('Usuário não autenticado')
      }

      // Step 1: Re-authenticate with current password (client-side validation)
      const credential = EmailAuthProvider.credential(user.email, data.current_password)

      try {
        await reauthenticateWithCredential(user, credential)
      } catch (reAuthError: unknown) {
        logger.error('Re-authentication failed', reAuthError)

        // User-friendly error messages
        const firebaseError = reAuthError as { code?: string }
        let errorMessage = 'Senha atual incorreta'
        if (firebaseError.code === 'auth/wrong-password') {
          errorMessage = 'Senha atual incorreta. Por favor, verifique e tente novamente.'
        } else if (firebaseError.code === 'auth/too-many-requests') {
          errorMessage = 'Muitas tentativas falhadas. Por favor, aguarde alguns minutos.'
        } else if (firebaseError.code === 'auth/network-request-failed') {
          errorMessage = 'Erro de conexão. Verifique sua internet e tente novamente.'
        }

        setError(errorMessage)
        throw new Error(errorMessage)
      }

      // Step 2: Send password change request to backend (server-side validation + update)
      try {
        const response = await apiClient.put<{ message: string; success?: boolean }>(
          '/auth/password',
          {
            current_password: data.current_password,
            new_password: data.new_password,
          }
        )

        // Handle both direct success and nested data.success responses
        const isSuccess =
          response?.success ||
          (response && typeof response === 'object' && 'success' in response && response.success)

        if (isSuccess) {
          toast({
            title: 'Senha alterada com sucesso',
            description:
              'Por segurança, você será desconectado em breve. Faça login novamente com sua nova senha.',
          })

          // Force logout after 3 seconds
          setTimeout(() => {
            window.location.href = '/login?reason=password-changed'
          }, 3000)
        }
      } catch (apiError: unknown) {
        logger.error('Backend password change failed', apiError)

        const error = apiError as { response?: { data?: { detail?: string } } }
        const errorMessage =
          error.response?.data?.detail || 'Erro ao alterar senha. Por favor, tente novamente.'

        setError(errorMessage)
        toast({
          title: 'Erro ao alterar senha',
          description: errorMessage,
          variant: 'destructive',
        })
        throw new Error(errorMessage)
      }
    } catch (err: unknown) {
      // Error already handled and set above
      logger.error('Password change error', err)
      throw err
    } finally {
      setIsChangingPassword(false)
    }
  }

  return {
    changePassword,
    isChangingPassword,
    error,
    clearError,
  }
}
