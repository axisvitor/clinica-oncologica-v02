/**
 * React Query hook for fetching treatment adherence data.
 * Provides adherence analytics for clinical monitoring.
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

/**
 * Treatment adherence data point structure from /api/v2/analytics/adherence
 */
export interface TreatmentAdherence {
  day: string
  adherence: number
  responses: number
  sentiment: number
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
 * Hook options for adherence data query
 */
export interface UseAdherenceDataOptions {
  days?: number
}

/**
 * Hook to fetch treatment adherence data.
 *
 * @param options - Query options including number of days to fetch
 * @returns Query result with adherence data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data: adherenceData, isLoading, error } = useAdherenceData({
 *   days: 30 // Last 30 days
 * })
 * ```
 */
export function useAdherenceData(
  options?: UseAdherenceDataOptions
): UseQueryResult<TreatmentAdherence[], Error> {
  const { days = 7 } = options ?? {}

  return useQuery<TreatmentAdherence[], Error>({
    queryKey: ['clinical', 'adherence', days],
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<TreatmentAdherence[]>>(
        '/api/v2/analytics/adherence',
        { days }
      )
      return response.data
    },
    staleTime: 300000, // 5 minutes
    retry: 2
  })
}
