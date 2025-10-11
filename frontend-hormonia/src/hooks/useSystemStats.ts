import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { AdminDashboardStats } from '@/types/admin'
import { mapSystemStats, isSystemStatsResponse } from '@/lib/mappers/systemStatsMapper'

interface UseSystemStatsOptions {
  /** Enable real-time updates via polling */
  realTimeUpdates?: boolean
  /** Auto-refresh interval in milliseconds */
  refreshInterval?: number
}

/**
 * Hook to fetch admin system statistics from /api/v1/admin/system-stats
 * Maps backend SystemStatsResponse to frontend AdminDashboardStats format
 */
export function useSystemStats(options: UseSystemStatsOptions = {}) {
  const {
    realTimeUpdates = true,
    refreshInterval = 30000 // 30 seconds default
  } = options

  const {
    data: stats,
    isLoading,
    error,
    refetch
  } = useQuery<AdminDashboardStats>({
    queryKey: ['admin-system-stats'],
    queryFn: async () => {
      // Fetch from live backend API
      const backendResponse = await apiClient.request<any>('/api/v1/admin/system-stats')

      // Validate and map backend response to frontend format
      if (isSystemStatsResponse(backendResponse)) {
        return mapSystemStats(backendResponse)
      }

      // Fallback to returning as-is if structure doesn't match
      // (handles case where backend returns AdminDashboardStats directly)
      return backendResponse as AdminDashboardStats
    },
    refetchInterval: realTimeUpdates ? refreshInterval : false,
    staleTime: 10000, // 10 seconds
    retry: 3
  })

  return {
    stats,
    isLoading,
    error,
    refetch
  }
}
