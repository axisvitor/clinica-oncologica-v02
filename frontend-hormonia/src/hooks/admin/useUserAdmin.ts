/**
 * User Admin Hook - Composition of User Management Hooks
 *
 * Composes all user admin functionality:
 * - User list queries (useUserList)
 * - User mutations (useUserMutations)
 * - WebSocket real-time updates (useUserWebSocket)
 * - Dashboard statistics (useUserStats)
 * - Filter management (useUserFilters)
 *
 * This hook provides a unified API for user administration while
 * maintaining separation of concerns internally.
 *
 * @module hooks/admin/useUserAdmin
 */

import { useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { useUserList } from './useUserList'
import { useUserMutations } from './useUserMutations'
import { useUserWebSocket } from './useUserWebSocket'
import { useUserStats } from './useUserStats'
import { useUserFilters } from './useUserFilters'
import type { AdminUserActivity } from '@/types/admin'

export interface UseUserAdminOptions {
  /** Enable real-time updates via WebSocket */
  realTimeUpdates?: boolean
  /** Auto-refresh interval in milliseconds */
  refreshInterval?: number
  /** Enable automatic retry on failed requests */
  enableRetry?: boolean
  /** Initial page size for pagination */
  pageSize?: number
}

/**
 * Main hook for user administration
 * Composes all user management functionality into a single API
 *
 * @param options - Configuration options
 * @returns Complete user admin interface
 *
 * @example
 * ```tsx
 * const {
 *   users,
 *   isLoading,
 *   createUser,
 *   updateUser,
 *   filters,
 *   updateFilters,
 *   stats,
 *   isRealTimeConnected
 * } = useUserAdmin({
 *   realTimeUpdates: true,
 *   refreshInterval: 30000,
 *   pageSize: 20
 * })
 * ```
 */
export function useUserAdmin(options: UseUserAdminOptions = {}) {
  const {
    realTimeUpdates = true,
    refreshInterval = 30000,
    enableRetry = true,
    pageSize = 10
  } = options

  const queryClient = useQueryClient()

  // ============================================================================
  // FILTERS
  // ============================================================================
  const {
    filters,
    updateFilters,
    updateFilter,
    setPage,
    setPageSize,
    resetFilters,
    hasActiveFilters,
    activeFilterCount
  } = useUserFilters({ pageSize })

  // ============================================================================
  // USER LIST
  // ============================================================================
  const {
    users,
    total: totalUsers,
    totalPages,
    currentPage,
    pageSize: currentPageSize,
    isLoading: usersLoading,
    error: usersError,
    refetch: refetchUsers,
    hasMore
  } = useUserList({
    filters,
    refetchInterval: realTimeUpdates ? refreshInterval : false,
    enableRetry
  })

  // ============================================================================
  // WEBSOCKET
  // ============================================================================
  const {
    isConnected: isRealTimeConnected,
    sendMessage,
    reconnect: reconnectWebSocket,
    disconnect: disconnectWebSocket
  } = useUserWebSocket({
    enabled: realTimeUpdates,
    maxReconnectAttempts: 10,
    reconnectDelay: 1000
  })

  // ============================================================================
  // MUTATIONS
  // ============================================================================
  const {
    createUser,
    updateUser,
    deleteUser,
    bulkActivate,
    bulkDeactivate,
    updatePermissions,
    resetPassword,
    createUserAsync,
    updateUserAsync,
    deleteUserAsync,
    bulkActivateAsync,
    bulkDeactivateAsync,
    updatePermissionsAsync,
    resetPasswordAsync,
    isCreating,
    isUpdating,
    isDeleting,
    isBulkActivating,
    isBulkDeactivating,
    isUpdatingPermissions,
    isResettingPassword
  } = useUserMutations({
    realTimeUpdates,
    sendMessage,
    isConnected: isRealTimeConnected
  })

  // ============================================================================
  // STATS
  // ============================================================================
  const {
    stats,
    metrics,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats
  } = useUserStats({
    usersData: { items: users, total: totalUsers },
    refetchInterval: realTimeUpdates ? refreshInterval : false,
    enabled: users.length > 0
  })

  // ============================================================================
  // USER ACTIVITY
  // ============================================================================
  /**
   * Fetch activity for a specific user
   * Returns a query hook for user activity
   */
  const useUserActivity = useCallback((userId: string) => {
    return useQuery({
      queryKey: ['admin-user-activity', userId],
      queryFn: () => apiClient.adminUsers.getActivity(userId, { page: 1, size: 50 }),
      enabled: !!userId,
      staleTime: 30000 // 30 seconds
    })
  }, [])

  // ============================================================================
  // UTILITY FUNCTIONS
  // ============================================================================

  /**
   * Refresh all user-related data
   */
  const refreshData = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    queryClient.invalidateQueries({ queryKey: ['admin-stats'] })
  }, [queryClient])

  /**
   * Pagination handlers
   */
  const goToPage = useCallback((page: number) => {
    setPage(page)
  }, [setPage])

  const nextPage = useCallback(() => {
    if (currentPage < totalPages) {
      setPage(currentPage + 1)
    }
  }, [currentPage, totalPages, setPage])

  const previousPage = useCallback(() => {
    if (currentPage > 1) {
      setPage(currentPage - 1)
    }
  }, [currentPage, setPage])

  // ============================================================================
  // RETURN API
  // ============================================================================
  return {
    // Data
    users,
    totalUsers,
    totalPages,
    currentPage,
    pageSize: currentPageSize,
    stats,
    metrics,

    // Loading states
    isLoading: usersLoading || statsLoading,
    usersLoading,
    statsLoading,

    // Error states
    error: usersError || statsError,
    usersError,
    statsError,

    // Filters
    filters,
    updateFilters,
    updateFilter,
    resetFilters,
    hasActiveFilters,
    activeFilterCount,

    // Pagination
    goToPage,
    nextPage,
    previousPage,
    hasMore,
    setPageSize,

    // Mutations
    createUser,
    updateUser,
    deleteUser,
    bulkActivate,
    bulkDeactivate,
    updatePermissions,
    resetPassword,

    // Async mutations
    createUserAsync,
    updateUserAsync,
    deleteUserAsync,
    bulkActivateAsync,
    bulkDeactivateAsync,
    updatePermissionsAsync,
    resetPasswordAsync,

    // Mutation states
    isCreating,
    isUpdating,
    isDeleting,
    isBulkActivating,
    isBulkDeactivating,
    isUpdatingPermissions,
    isResettingPassword,

    // Utility functions
    refetchUsers,
    refetchStats,
    refreshData,
    useUserActivity,

    // WebSocket
    isRealTimeConnected,
    reconnectWebSocket,
    disconnectWebSocket
  }
}
