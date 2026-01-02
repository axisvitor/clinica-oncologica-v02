/**
 * React Query hook for fetching at-risk patients with automatic refetching.
 * Provides real-time risk monitoring for clinical dashboard.
 */
import { useQuery, UseQueryResult, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { apiClient } from '@/lib/api-client'

/**
 * Patient risk assessment structure from /api/v2/analytics/risk-assessment
 */
export interface PatientRisk {
  id: string
  name: string
  riskLevel: 'low' | 'medium' | 'high' | 'critical'
  lastInteraction: string
  sentiment: number
  adherence: number
  alerts: string[]
}

/**
 * Hook options for risk patients query
 */
export interface UseRiskPatientsOptions {
  refetchInterval?: number
  wsData?: { type?: string } // WebSocket data for triggering refetch
}

/**
 * Hook to fetch at-risk patients with automatic refetching.
 * Automatically refetches when WebSocket receives 'risk_alert' event.
 *
 * @param options - Query options including refetchInterval and wsData
 * @returns Query result with risk patients data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data: riskPatients, isLoading, error } = useRiskPatients({
 *   refetchInterval: 60000, // Refresh every 60 seconds
 *   wsData // WebSocket data
 * })
 * ```
 */
export function useRiskPatients(
  options?: UseRiskPatientsOptions
): UseQueryResult<PatientRisk[], Error> {
  const { refetchInterval = 60000, wsData } = options ?? {}
  const queryClient = useQueryClient()

  // Auto-refetch when WebSocket receives 'risk_alert'
  useEffect(() => {
    if (wsData?.type === 'risk_alert') {
      queryClient.invalidateQueries({ queryKey: ['clinical', 'risk-patients'] })
    }
  }, [wsData, queryClient])

  return useQuery<PatientRisk[], Error>({
    queryKey: ['clinical', 'risk-patients'],
    queryFn: async () => {
      const response = await apiClient.analytics.riskAssessment()
      return response.risk_assessments.map((assessment) => ({
        id: assessment.id,
        name: assessment.name ?? 'Paciente sem nome',
        riskLevel: (assessment.risk_level as PatientRisk['riskLevel']) ?? 'low',
        lastInteraction: assessment.last_response ?? '',
        sentiment: 0,
        adherence: 0,
        alerts: assessment.risk_factors ?? []
      }))
    },
    staleTime: 60000, // 60 seconds
    refetchInterval,
    retry: 2
  })
}
