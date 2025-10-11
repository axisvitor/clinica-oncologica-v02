import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { AdminUser, AdminDashboardStats, AdminUserActivity } from '@/types/admin'
import { useToast } from '@/components/ui/use-toast'

interface UseUserAdminOptions {
  /** Enable real-time updates via WebSocket */
  realTimeUpdates?: boolean
  /** Auto-refresh interval in milliseconds */
  refreshInterval?: number
  /** Enable automatic retry on failed requests */
  enableRetry?: boolean
}

interface UserFilters {
  search?: string
  role?: string
  status?: string
  twoFactor?: string
  page?: number
  size?: number
}

export function useUserAdmin(options: UseUserAdminOptions = {}) {
  const {
    realTimeUpdates = true,
    refreshInterval = 30000, // 30 seconds
    enableRetry = true
  } = options

  const { toast } = useToast()
  const queryClient = useQueryClient()

  // WebSocket for real-time updates
  // TODO: Implement WebSocket endpoint /ws/admin/users on backend
  // For now, using polling-based updates via refetchInterval
  const isConnected = false
  const sendMessage = useCallback((_message: any) => {
    // Placeholder until backend WebSocket endpoint is implemented
    // This function accepts a message parameter but does nothing with it
  }, [])

  // State for filters and pagination
  const [filters, setFilters] = useState<UserFilters>({
    page: 1,
    size: 10
  })

  // Fetch users list
  const {
    data: usersResponse,
    isLoading: usersLoading,
    error: usersError,
    refetch: refetchUsers
  } = useQuery({
    queryKey: ['admin-users', filters],
    queryFn: () => apiClient.adminUsers.list(filters),
    refetchInterval: realTimeUpdates ? refreshInterval : false,
    retry: enableRetry ? 3 : false,
    staleTime: 10000 // 10 seconds
  })

  // Fetch dashboard stats
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError
  } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: async () => {
      // Mock implementation - replace with actual API call
      return {
        users: {
          total: usersResponse?.total || 0,
          active: usersResponse?.items?.filter(u => u.is_active).length || 0,
          locked: usersResponse?.items?.filter(u => u.locked_until && new Date(u.locked_until) > new Date()).length || 0,
          new_today: 0
        },
        security: {
          failed_logins: usersResponse?.items?.reduce((sum, u) => sum + u.failed_login_attempts, 0) || 0,
          active_sessions: 0,
          blocked_ips: 0
        },
        system: {
          uptime: 0,
          memory_usage: 0,
          cpu_usage: 0,
          disk_usage: 0
        },
        audit: {
          total_logs: 0,
          critical_events: 0,
          warnings: 0
        }
      } as AdminDashboardStats
    },
    enabled: !!usersResponse,
    refetchInterval: realTimeUpdates ? refreshInterval : false
  })

  // Create user mutation
  const createUserMutation = useMutation({
    mutationFn: (userData: Partial<AdminUser>) => apiClient.adminUsers.create(userData),
    onSuccess: (newUser) => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-stats'] })

      toast({
        title: 'Usuário criado com sucesso',
        description: `${newUser.full_name} foi adicionado ao sistema.`,
      })

      // Notify other clients via WebSocket
      if (realTimeUpdates && isConnected) {
        sendMessage({
          type: 'user_created',
          data: { user: newUser }
        })
      }
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao criar usuário',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  // Update user mutation
  const updateUserMutation = useMutation({
    mutationFn: ({ id, userData }: { id: string; userData: Partial<AdminUser> }) =>
      apiClient.adminUsers.update(id, userData),
    onSuccess: (updatedUser, variables) => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-user', variables.id] })
      queryClient.invalidateQueries({ queryKey: ['admin-stats'] })

      toast({
        title: 'Usuário atualizado com sucesso',
        description: 'As alterações foram salvas.',
      })

      // Notify other clients via WebSocket
      if (realTimeUpdates && isConnected) {
        sendMessage({
          type: 'user_updated',
          data: { user: updatedUser }
        })
      }
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao atualizar usuário',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  // Delete user mutation
  const deleteUserMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.delete(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-stats'] })

      toast({
        title: 'Usuário excluído com sucesso',
        description: 'O usuário foi removido do sistema.',
      })

      // Notify other clients via WebSocket
      if (realTimeUpdates && isConnected) {
        sendMessage({
          type: 'user_deleted',
          data: { userId: id }
        })
      }
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao excluir usuário',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  // Bulk activate users
  const bulkActivateMutation = useMutation({
    mutationFn: async (userIds: string[]) => {
      const results = await Promise.allSettled(
        userIds.map(id => apiClient.adminUsers.activate(id))
      )

      const successes = results.filter(r => r.status === 'fulfilled').length
      const failures = results.filter(r => r.status === 'rejected').length

      return { successes, failures, total: userIds.length }
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-stats'] })

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
    },
    onError: (error: any) => {
      toast({
        title: 'Erro na ativação em lote',
        description: error.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  // Bulk deactivate users
  const bulkDeactivateMutation = useMutation({
    mutationFn: async (userIds: string[]) => {
      const results = await Promise.allSettled(
        userIds.map(id => apiClient.adminUsers.deactivate(id))
      )

      const successes = results.filter(r => r.status === 'fulfilled').length
      const failures = results.filter(r => r.status === 'rejected').length

      return { successes, failures, total: userIds.length }
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-stats'] })

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
    },
    onError: (error: any) => {
      toast({
        title: 'Erro na desativação em lote',
        description: error.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  // Update permissions mutation
  // WARNING: Backend endpoint is currently a placeholder and doesn't persist permissions
  const updatePermissionsMutation = useMutation({
    mutationFn: ({ id, permissions }: { id: string; permissions: string[] }) =>
      apiClient.adminUsers.updatePermissions(id, permissions),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-user', variables.id] })

      toast({
        title: '⚠️ Permissões atualizadas (temporário)',
        description: 'Nota: Backend ainda não persiste permissões. Implementação pendente.',
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao atualizar permissões',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  // Reset password mutation
  const resetPasswordMutation = useMutation({
    mutationFn: async (id: string) => {
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
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao redefinir senha',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  // Generate secure temporary password
  function generateTemporaryPassword(): string {
    const length = 12
    const charset = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%^&*'
    const array = new Uint8Array(length)
    crypto.getRandomValues(array)
    return Array.from(array, (byte) => charset[byte % charset.length]).join('')
  }

  // Helper functions
  const updateFilters = useCallback((newFilters: Partial<UserFilters>) => {
    setFilters(prev => ({ ...prev, ...newFilters, page: 1 })) // Reset to first page when filters change
  }, [])

  const resetFilters = useCallback(() => {
    setFilters({ page: 1, size: 10 })
  }, [])

  const refreshData = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    queryClient.invalidateQueries({ queryKey: ['admin-stats'] })
  }, [queryClient])

  // Fetch user activity for a specific user
  const useUserActivity = (userId: string) => {
    return useQuery({
      queryKey: ['admin-user-activity', userId],
      queryFn: () => apiClient.adminUsers.getActivity(userId, { page: 1, size: 50 }),
      enabled: !!userId,
      staleTime: 30000 // 30 seconds
    })
  }

  return {
    // Data
    users: usersResponse?.items || [],
    totalUsers: usersResponse?.total || 0,
    totalPages: usersResponse?.pages || 0,
    currentPage: usersResponse?.page || 1,
    stats,

    // Loading states
    isLoading: usersLoading || statsLoading,
    usersLoading,
    statsLoading,

    // Error states
    error: usersError || statsError,
    usersError,
    statsError,

    // Filters and pagination
    filters,
    updateFilters,
    resetFilters,

    // Mutations
    createUser: createUserMutation.mutate,
    updateUser: updateUserMutation.mutate,
    deleteUser: deleteUserMutation.mutate,
    bulkActivate: bulkActivateMutation.mutate,
    bulkDeactivate: bulkDeactivateMutation.mutate,
    updatePermissions: updatePermissionsMutation.mutate,
    resetPassword: resetPasswordMutation.mutate,

    // Mutation states
    isCreating: createUserMutation.isPending,
    isUpdating: updateUserMutation.isPending,
    isDeleting: deleteUserMutation.isPending,
    isBulkActivating: bulkActivateMutation.isPending,
    isBulkDeactivating: bulkDeactivateMutation.isPending,
    isUpdatingPermissions: updatePermissionsMutation.isPending,
    isResettingPassword: resetPasswordMutation.isPending,

    // Utility functions
    refetchUsers,
    refreshData,
    useUserActivity,

    // WebSocket connection status
    isRealTimeConnected: isConnected
  }
}