/**
 * Hook for fetching system statistics from the admin stats endpoint.
 * Provides real-time system, user, and database metrics.
 */
import { useQuery, UseQueryOptions } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

/**
 * System statistics response structure from /api/v2/admin/system-stats
 */
export interface SystemStats {
  system: {
    cpu_percent: number
    memory_percent: number
    disk_percent: number
    uptime_seconds: number
  }
  users: {
    total: number
    active_now: number
    by_role: {
      admin?: number
      doctor?: number
      [key: string]: number | undefined
    }
  }
  database: {
    total_records: number
    total_patients: number
    total_users: number
    connections: number
  }
  timestamp: string
}

/**
 * Hook to fetch system statistics with automatic refetching.
 *
 * @param options - React Query options including refetchInterval
 * @returns Query result with stats data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data: stats, isLoading, error, refetch } = useSystemStats({
 *   refetchInterval: 30000 // Refresh every 30 seconds
 * })
 * ```
 */
export function useSystemStats(
  options?: Omit<UseQueryOptions<SystemStats, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<SystemStats, Error>({
    queryKey: ['admin', 'system-stats'],
    queryFn: async () => {
      const response = await apiClient.request<SystemStats>('/api/v2/admin/system-stats')
      return response
    },
    staleTime: 20000, // Consider data stale after 20s
    ...options
  })
}
