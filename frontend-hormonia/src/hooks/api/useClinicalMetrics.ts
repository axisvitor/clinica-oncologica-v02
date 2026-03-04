/**
 * React Query hook for fetching clinical metrics with automatic refetching.
 * Provides real-time monitoring data for clinical dashboard.
 *
 * Uses /api/v2/dashboard/main as the backend endpoint (no dedicated /metrics/clinical exists)
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

/**
 * Clinical metrics response structure
 * Mapped from /api/v2/dashboard/main response
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
 * Dashboard main response structure
 * Used internally by the hook for type checking API responses
 */
interface _DashboardMainResponse {
  total_patients: number
  active_patients: number
  active_patients_percentage: number
  response_rate: number
  completed_quizzes: number
  total_quizzes: number
  high_risk_patients: number
  avg_sentiment: number
  active_conversations: number
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
  const { refetchInterval = 30000 } = options ?? {}

  return useQuery<ClinicalMetrics, Error>({
    queryKey: ['clinical', 'metrics'],
    queryFn: async () => {
      // Use existing dashboard/main endpoint
      const response = await apiClient.dashboard.getMain()

      // Transform to ClinicalMetrics format
      return {
        patientEngagement: response.active_patients_percentage ?? 0,
        quizCompletion:
          response.total_quizzes > 0
            ? (response.completed_quizzes / response.total_quizzes) * 100
            : 0,
        messageResponseRate: response.response_rate ?? 0,
        averageSentiment: response.avg_sentiment ?? 0,
        riskPatients: response.high_risk_patients ?? 0,
        totalPatients: response.total_patients ?? 0,
        activeFlows: response.active_conversations ?? 0,
        completedFlows: response.completed_quizzes ?? 0,
      }
    },
    staleTime: 30000, // 30 seconds - real-time monitoring
    refetchInterval,
    retry: 2,
  })
}
