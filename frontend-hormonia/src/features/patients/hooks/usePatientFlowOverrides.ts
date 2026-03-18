/**
 * React Query hook for patient flow day overrides.
 *
 * Provides typed data access for the merged day list (GET) and
 * bulk override upsert (PUT) endpoints.
 *
 * Query key: ['patient-flow-overrides', patientId]
 * Visible in React Query DevTools for cache inspection.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

// ── Response types (from GET /api/v2/patients/{id}/flow-overrides) ───

export interface MergedDayItem {
  day_number: number
  content: string
  message_type: string
  expects_response: boolean
  skip: boolean
  /** Whether this day comes from the global template or a patient override */
  source: 'global' | 'override'
  /** Whether the physician can still edit this day (false for past days) */
  editable: boolean
}

export interface MergedDayListResponse {
  patient_id: string
  flow_state_id: string
  current_flow_day: number
  days: MergedDayItem[]
}

// ── Request types (for PUT /api/v2/patients/{id}/flow-overrides) ─────

export interface OverrideDayInput {
  day_number: number
  content: string
  message_type: string
  expects_response: boolean
  skip: boolean
}

export interface OverrideDayUpdateRequest {
  days: OverrideDayInput[]
}

// ── Hook ─────────────────────────────────────────────────────────────

const QUERY_KEY_PREFIX = 'patient-flow-overrides' as const

export function usePatientFlowOverrides(patientId: string) {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: [QUERY_KEY_PREFIX, patientId],
    queryFn: () =>
      apiClient.get<MergedDayListResponse>(
        `/api/v2/patients/${patientId}/flow-overrides`
      ),
    enabled: !!patientId,
    staleTime: 60_000,
  })

  const mutation = useMutation({
    mutationFn: (payload: OverrideDayUpdateRequest) =>
      apiClient.put<MergedDayListResponse, OverrideDayUpdateRequest>(
        `/api/v2/patients/${patientId}/flow-overrides`,
        payload
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [QUERY_KEY_PREFIX, patientId],
      })
    },
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    saveOverrides: mutation.mutateAsync,
    isSaving: mutation.isPending,
  }
}
