import { useQuery, UseQueryOptions } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { MedicoDashboardStatsResponse } from '@/types/api-wave2'

interface UseMedicoDashboardStatsOptions {
  refetchInterval?: number
  enabled?: boolean
}

export function useMedicoDashboardStats(options?: UseMedicoDashboardStatsOptions) {
  return useQuery({
    queryKey: ['medico', 'dashboard-stats'],
    queryFn: async () => {
      return await apiClient.request<MedicoDashboardStatsResponse>('/api/v2/medico/dashboard-stats')
    },
    staleTime: 120000, // 2 minutes (match backend cache)
    refetchInterval: options?.refetchInterval,
    enabled: options?.enabled ?? true,
    retry: 2,
  } as UseQueryOptions<MedicoDashboardStatsResponse>)
}
