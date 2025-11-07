/**
 * React Query hook for fetching clinical metrics with automatic refetching.
 * Provides real-time monitoring data for clinical dashboard.
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

/**
 * Clinical metrics response structure from /api/v2/metrics/clinical
 */
export interface ClinicalMetrics {
  patientEngagement: number
  quizCompletion: number
  messageResponseRate: number
  averageSentiment: number
  riskPatients: number
  totalPatients: number
  activeFlows: number
  completedFlows: number
}

/**
 * API response wrapper
 */
interface ApiResponse<T> {
  data: T
  message?: string
  timestamp?: string
}

/**
 * Hook options for clinical metrics query
 */
export interface UseClinicalMetricsOptions {
  timeRange?: '7d' | '30d' | '90d'
  refetchInterval?: number
}

/**
 * Hook to fetch clinical metrics with automatic refetching.
 *
 * @param options - Query options including timeRange and refetchInterval
 * @returns Query result with clinical metrics data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data: metrics, isLoading, error } = useClinicalMetrics({
 *   timeRange: '30d',
 *   refetchInterval: 30000 // Refresh every 30 seconds
 * })
 * ```
 */
export function useClinicalMetrics(
  options?: UseClinicalMetricsOptions
): UseQueryResult<ClinicalMetrics, Error> {
  const { timeRange = '7d', refetchInterval = 30000 } = options ?? {}

  return useQuery<ClinicalMetrics, Error>({
    queryKey: ['clinical', 'metrics', timeRange],
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<ClinicalMetrics>>(
        '/api/v2/metrics/clinical',
        { timeRange }
      )
      return response.data
    },
    staleTime: 30000, // 30 seconds - real-time monitoring
    refetchInterval,
    retry: 2
  })
}
