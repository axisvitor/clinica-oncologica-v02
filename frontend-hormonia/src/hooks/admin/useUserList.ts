/**
 * User List Hook - Data Fetching
 *
 * Handles user list queries with pagination and filtering
 * - Fetches paginated user data
 * - Manages loading and error states
 * - Provides refetch functionality
 *
 * @module hooks/admin/useUserList
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { AdminUser } from '@/types/admin'
// import { PaginatedResponse } from '@/lib/api-client/core' // Unused - using inline types
import { createLogger } from '@/utils/logger'

const logger = createLogger('useUserList')

export interface UserFilters {
  search?: string
  role?: string
  status?: string
  twoFactor?: string
  page?: number
  size?: number
}

export interface UseUserListOptions {
  /** Filters to apply to the query */
  filters?: UserFilters
  /** Auto-refresh interval in milliseconds */
  refetchInterval?: number | false
  /** Enable automatic retry on failed requests */
  enableRetry?: boolean
  /** Enable the query */
  enabled?: boolean
}

export interface UseUserListResult {
  /** User list data */
  users: AdminUser[]
  /** Total number of users */
  total: number
  /** Total number of pages */
  totalPages: number
  /** Current page number */
  currentPage: number
  /** Page size */
  pageSize: number
  /** Whether query is loading */
  isLoading: boolean
  /** Query error if any */
  error: Error | null
  /** Refetch function */
  refetch: () => void
  /** Whether there are more pages */
  hasMore: boolean
}

/**
 * Hook for fetching user list with pagination and filters
 *
 * @param options - Configuration options
 * @returns User list data and query state
 *
 * @example
 * ```tsx
 * const { users, isLoading, total, refetch } = useUserList({
 *   filters: { search: 'john', role: 'admin', page: 1, size: 10 },
 *   refetchInterval: 30000,
 *   enableRetry: true
 * })
 * ```
 */
export function useUserList(options: UseUserListOptions = {}): UseUserListResult {
  const { filters = {}, refetchInterval = false, enableRetry = true, enabled = true } = options

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['admin-users', filters],
    queryFn: async () => {
      logger.debug('Fetching users with filters:', filters)

      // Build query parameters
      const params: Record<string, string | number | boolean> = {
        page: filters.page || 1,
        size: filters.size || 10,
      }

      if (filters.search) {
        params['search'] = filters.search
      }

      if (filters.role) {
        params['role'] = filters.role
      }

      if (filters.status) {
        // Convert status filter to is_active boolean
        if (filters.status === 'active') {
          params['is_active'] = true
        } else if (filters.status === 'inactive') {
          params['is_active'] = false
        }
      }

      if (filters.twoFactor) {
        // Convert 2FA filter to boolean
        if (filters.twoFactor === 'enabled') {
          params['two_factor_enabled'] = true
        } else if (filters.twoFactor === 'disabled') {
          params['two_factor_enabled'] = false
        }
      }

      const response = await apiClient.adminUsers.list(params)

      logger.debug('Users fetched successfully:', {
        total: response.total,
        page: response.page,
        items: response.items?.length,
      })

      return response
    },
    enabled,
    refetchInterval,
    retry: enableRetry ? 3 : false,
    staleTime: 10000, // 10 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes (formerly cacheTime)
  })

  return {
    users: data?.items || [],
    total: data?.total || 0,
    totalPages: data?.pages || 0,
    currentPage: data?.page || filters.page || 1,
    pageSize: data?.size || filters.size || 10,
    isLoading,
    error: error as Error | null,
    refetch: () => {
      refetch()
    },
    hasMore: data?.has_more ?? false,
  }
}
