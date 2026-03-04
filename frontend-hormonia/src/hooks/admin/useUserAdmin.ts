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

/**
 * Hook to fetch user activity data
 * This is a standalone hook that follows React's rules of hooks
 *
 * @param userId - The user ID to fetch activity for
 * @param options - Optional configuration
 * @returns Query result with user activity data
 *
 * @example
 * ```tsx
 * const { data: activity, isLoading } = useUserActivity('user-123')
 * ```
 */
export function useUserActivity(
  userId: string | null | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: ['admin-user-activity', userId],
    queryFn: () => apiClient.adminUsers.getActivity(userId!, { page: 1, size: 50 }),
    enabled: !!userId && options?.enabled !== false,
    staleTime: 30000, // 30 seconds
  })
}

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
    pageSize = 10,
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
    activeFilterCount,
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
    hasMore,
  } = useUserList({
    filters,
    refetchInterval: realTimeUpdates ? refreshInterval : false,
    enableRetry,
  })

  // ============================================================================
  // WEBSOCKET
  // ============================================================================
  const {
    isConnected: isRealTimeConnected,
    sendMessage,
    reconnect: reconnectWebSocket,
    disconnect: disconnectWebSocket,
  } = useUserWebSocket({
    enabled: realTimeUpdates,
    maxReconnectAttempts: 10,
    reconnectDelay: 1000,
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
    isResettingPassword,
  } = useUserMutations({
    realTimeUpdates,
    sendMessage,
    isConnected: isRealTimeConnected,
  })

  // ============================================================================
  // STATS
  // ============================================================================
  const {
    stats,
    metrics,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useUserStats({
    usersData: { items: users, total: totalUsers },
    refetchInterval: realTimeUpdates ? refreshInterval : false,
    enabled: users.length > 0,
  })

  // ============================================================================
  // USER ACTIVITY
  // ============================================================================
  // Note: useUserActivity is now a standalone hook exported from this module.
  // Use it directly: const { data } = useUserActivity(userId)
  // This follows React's rules of hooks - hooks cannot be called inside callbacks.

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
  const goToPage = useCallback(
    (page: number) => {
      setPage(page)
    },
    [setPage]
  )

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

    // WebSocket
    isRealTimeConnected,
    reconnectWebSocket,
    disconnectWebSocket,
  }
}
