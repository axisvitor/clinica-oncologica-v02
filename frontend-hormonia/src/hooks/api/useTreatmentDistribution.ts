/**
 * Hook for fetching treatment distribution analytics.
 *
 * Provides treatment type distribution data with period filtering,
 * enabling pie charts and trend analysis for patient treatments.
 */
import { useQuery, UseQueryOptions } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { AnalyticsPeriod } from '@/types/api-wave2'
import type { TreatmentDistribution } from '@/lib/api-client/analytics'

/**
 * Time period type for analytics
 */
export type Period = AnalyticsPeriod

interface UseTreatmentDistributionOptions {
  enabled?: boolean
}

/**
 * Fetch treatment distribution analytics with period filtering.
 *
 * @param period - Time period for analysis (7d, 30d, 90d, all). Default: 30d
 * @param options - Query options (enabled, etc.)
 * @returns React Query result with treatment distribution data
 *
 * @example
 * ```tsx
 * // Default 30-day period
 * const { data } = useTreatmentDistribution()
 *
 * // Custom period
 * const { data } = useTreatmentDistribution('7d')
 *
 * // With options
 * const { data } = useTreatmentDistribution('90d', { enabled: isAdmin })
 * ```
 */
export function useTreatmentDistribution(
  period: AnalyticsPeriod = '30d',
  options?: UseTreatmentDistributionOptions
) {
  return useQuery({
    queryKey: ['analytics', 'treatment-distribution', period],
    queryFn: async () => {
      return await apiClient.analytics.treatmentDistribution(period)
    },
    staleTime: 5 * 60 * 1000, // 5 minutes (match backend cache)
    enabled: options?.enabled ?? true,
    retry: 2
  } as UseQueryOptions<TreatmentDistribution>)
}
