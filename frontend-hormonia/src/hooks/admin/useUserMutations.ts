/**
 * User Mutations Hook - Data Modification Operations
 *
 * Handles all user mutation operations:
 * - Create, update, delete users
 * - Bulk operations (activate/deactivate)
 * - Permission updates
 * - Password resets
 *
 * @module hooks/admin/useUserMutations
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { apiClient } from '@/lib/api-client'
import { CreateUserRequest, UpdateUserRequest } from '@/lib/api-client/types'
import { AdminUser } from '@/types/admin'
import { useToast } from '@/components/ui/use-toast'
import { getErrorMessage } from '@/lib/utils/type-guards'
import { generateTemporaryPassword } from '@/lib/utils/security/password-generator'
import { createLogger } from '@/utils/logger'
import type { WebSocketMessage } from './useUserWebSocket'

const logger = createLogger('useUserMutations')

export interface UseUserMutationsOptions {
  /** Enable real-time updates via WebSocket */
  realTimeUpdates?: boolean
  /** Function to send WebSocket messages */
  sendMessage?: (message: WebSocketMessage) => void
  /** Whether WebSocket is connected */
  isConnected?: boolean
}

export interface BulkOperationResult {
  successes: number
  failures: number
  total: number
}

/**
 * Hook for user mutation operations
 *
 * @param options - Configuration options
 * @returns Mutation functions and states
 *
 * @example
 * ```tsx
 * const {
 *   createUser,
 *   updateUser,
 *   deleteUser,
 *   isCreating
 * } = useUserMutations({
 *   realTimeUpdates: true,
 *   sendMessage: ws.sendMessage,
 *   isConnected: ws.isConnected
 * })
 *
 * // Create a user
 * createUser({
 *   email: 'user@example.com',
 *   full_name: 'John Doe',
 *   role: 'admin'
 * })
 * ```
 */
export function useUserMutations(options: UseUserMutationsOptions = {}) {
  const {
    realTimeUpdates = false,
    sendMessage,
    isConnected = false
  } = options

  const { toast } = useToast()
  const queryClient = useQueryClient()

  /**
   * Invalidate user-related queries
   */
  const invalidateQueries = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    queryClient.invalidateQueries({ queryKey: ['admin-stats'] })
  }, [queryClient])

  /**
   * Send WebSocket notification
   */
  const notifyWebSocket = useCallback((type: WebSocketMessage['type'], data: Record<string, unknown>) => {
    if (realTimeUpdates && isConnected && sendMessage) {
      sendMessage({ type, data })
    }
  }, [realTimeUpdates, isConnected, sendMessage])

  // ============================================================================
  // CREATE USER
  // ============================================================================
  const createUserMutation = useMutation({
    mutationFn: (userData: Partial<AdminUser>) => {
      logger.debug('Creating user:', userData.email)
      return apiClient.adminUsers.create(userData as CreateUserRequest)
    },
    onSuccess: (newUser) => {
      invalidateQueries()

      toast({
        title: 'Usuário criado com sucesso',
        description: `${newUser.full_name} foi adicionado ao sistema.`,
      })

      notifyWebSocket('user_created', { user: newUser })

      logger.info('User created:', newUser.id)
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao criar usuário',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })

      logger.error('Failed to create user:', error)
    }
  })

  // ============================================================================
  // UPDATE USER
  // ============================================================================
  const updateUserMutation = useMutation({
    mutationFn: ({ id, userData }: { id: string; userData: Partial<AdminUser> }) => {
      logger.debug('Updating user:', id)
      return apiClient.adminUsers.update(id, userData as UpdateUserRequest)
    },
    onSuccess: (updatedUser, variables) => {
      invalidateQueries()
      queryClient.invalidateQueries({ queryKey: ['admin-user', variables.id] })

      toast({
        title: 'Usuário atualizado com sucesso',
        description: 'As alterações foram salvas.',
      })

      notifyWebSocket('user_updated', { user: updatedUser })

      logger.info('User updated:', variables.id)
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao atualizar usuário',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })

      logger.error('Failed to update user:', error)
    }
  })

  // ============================================================================
  // DELETE USER
  // ============================================================================
  const deleteUserMutation = useMutation({
    mutationFn: (id: string) => {
      logger.debug('Deleting user:', id)
      return apiClient.adminUsers.delete(id)
    },
    onSuccess: (_, id) => {
      invalidateQueries()

      toast({
        title: 'Usuário excluído com sucesso',
        description: 'O usuário foi removido do sistema.',
      })

      notifyWebSocket('user_deleted', { userId: id })

      logger.info('User deleted:', id)
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao excluir usuário',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })

      logger.error('Failed to delete user:', error)
    }
  })

  // ============================================================================
  // BULK ACTIVATE
  // ============================================================================
  const bulkActivateMutation = useMutation({
    mutationFn: async (userIds: string[]): Promise<BulkOperationResult> => {
      logger.debug('Bulk activating users:', userIds.length)

      const results = await Promise.allSettled(
        userIds.map(id => apiClient.adminUsers.activate(id))
      )

      const successes = results.filter(r => r.status === 'fulfilled').length
      const failures = results.filter(r => r.status === 'rejected').length

      return { successes, failures, total: userIds.length }
    },
    onSuccess: (result) => {
      invalidateQueries()

      if (result.failures > 0) {
        toast({
          title: 'Ativação parcialmente concluída',
          description: `${result.successes} usuário(s) ativado(s), ${result.failures} falharam.`,
          variant: 'destructive'
        })
      } else {
        toast({
          title: 'Usuários ativados com sucesso',
          description: `${result.successes} usuário(s) foram ativados.`,
        })
      }

      logger.info('Bulk activate result:', result)
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro na ativação em lote',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })

      logger.error('Bulk activate failed:', error)
    }
  })

  // ============================================================================
  // BULK DEACTIVATE
  // ============================================================================
  const bulkDeactivateMutation = useMutation({
    mutationFn: async (userIds: string[]): Promise<BulkOperationResult> => {
      logger.debug('Bulk deactivating users:', userIds.length)

      const results = await Promise.allSettled(
        userIds.map(id => apiClient.adminUsers.deactivate(id))
      )

      const successes = results.filter(r => r.status === 'fulfilled').length
      const failures = results.filter(r => r.status === 'rejected').length

      return { successes, failures, total: userIds.length }
    },
    onSuccess: (result) => {
      invalidateQueries()

      if (result.failures > 0) {
        toast({
          title: 'Desativação parcialmente concluída',
          description: `${result.successes} usuário(s) desativado(s), ${result.failures} falharam.`,
          variant: 'destructive'
        })
      } else {
        toast({
          title: 'Usuários desativados com sucesso',
          description: `${result.successes} usuário(s) foram desativados.`,
        })
      }

      logger.info('Bulk deactivate result:', result)
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro na desativação em lote',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })

      logger.error('Bulk deactivate failed:', error)
    }
  })

  // ============================================================================
  // UPDATE PERMISSIONS
  // ============================================================================
  const updatePermissionsMutation = useMutation({
    mutationFn: ({ id, permissions }: { id: string; permissions: string[] }) => {
      logger.debug('Updating permissions for user:', id)
      return apiClient.adminUsers.updatePermissions(id, permissions)
    },
    onSuccess: (_, variables) => {
      invalidateQueries()
      queryClient.invalidateQueries({ queryKey: ['admin-user', variables.id] })

      toast({
        title: 'Permissões atualizadas',
        description: 'As permissões do usuário foram atualizadas com sucesso.',
      })

      logger.info('Permissions updated for user:', variables.id)
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao atualizar permissões',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })

      logger.error('Failed to update permissions:', error)
    }
  })

  // ============================================================================
  // RESET PASSWORD
  // ============================================================================
  const resetPasswordMutation = useMutation({
    mutationFn: async (id: string) => {
      logger.debug('Resetting password for user:', id)

      // Generate secure temporary password client-side
      const tempPassword = generateTemporaryPassword()

      // Send password to backend for user update
      await apiClient.adminUsers.resetPassword(id, {
        new_password: tempPassword,
        force_change: true
      })

      // Return generated password for display
      return { temporary_password: tempPassword }
    },
    onSuccess: (response) => {
      toast({
        title: 'Senha redefinida com sucesso',
        description: `Nova senha temporária: ${response.temporary_password}`,
      })

      logger.info('Password reset successful')
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao redefinir senha',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })

      logger.error('Failed to reset password:', error)
    }
  })

  return {
    // Mutation functions
    createUser: createUserMutation.mutate,
    updateUser: updateUserMutation.mutate,
    deleteUser: deleteUserMutation.mutate,
    bulkActivate: bulkActivateMutation.mutate,
    bulkDeactivate: bulkDeactivateMutation.mutate,
    updatePermissions: updatePermissionsMutation.mutate,
    resetPassword: resetPasswordMutation.mutate,

    // Async mutation functions
    createUserAsync: createUserMutation.mutateAsync,
    updateUserAsync: updateUserMutation.mutateAsync,
    deleteUserAsync: deleteUserMutation.mutateAsync,
    bulkActivateAsync: bulkActivateMutation.mutateAsync,
    bulkDeactivateAsync: bulkDeactivateMutation.mutateAsync,
    updatePermissionsAsync: updatePermissionsMutation.mutateAsync,
    resetPasswordAsync: resetPasswordMutation.mutateAsync,

    // Loading states
    isCreating: createUserMutation.isPending,
    isUpdating: updateUserMutation.isPending,
    isDeleting: deleteUserMutation.isPending,
    isBulkActivating: bulkActivateMutation.isPending,
    isBulkDeactivating: bulkDeactivateMutation.isPending,
    isUpdatingPermissions: updatePermissionsMutation.isPending,
    isResettingPassword: resetPasswordMutation.isPending,

    // Reset mutation states
    resetCreateUser: createUserMutation.reset,
    resetUpdateUser: updateUserMutation.reset,
    resetDeleteUser: deleteUserMutation.reset
  }
}
