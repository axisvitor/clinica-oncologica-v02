/**
 * usePhysicianPatients — Patient list with flow data for physician dashboard
 *
 * Consumes GET /api/v2/physicians/patients with server-side filtering,
 * debounced search, and pagination.
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { useDebounce } from '@/hooks/useDebounce'
import type {
  PhysicianPatientListResponse,
  PhysicianPatientListParams,
} from '@/lib/api-client/physician'

interface UsePhysicianPatientsOptions {
  search?: string
  flow_phase?: string
  flow_status?: string
  page?: number
  size?: number
  enabled?: boolean
}

export function usePhysicianPatients(options?: UsePhysicianPatientsOptions) {
  const {
    search = '',
    flow_phase,
    flow_status,
    page = 1,
    size = 20,
    enabled = true,
  } = options ?? {}

  const debouncedSearch = useDebounce(search, 300)

  const params: PhysicianPatientListParams = {
    page,
    size,
  }
  if (debouncedSearch) params.search = debouncedSearch
  if (flow_phase && flow_phase !== 'all') params.flow_phase = flow_phase
  if (flow_status && flow_status !== 'all') params.flow_status = flow_status

  return useQuery<PhysicianPatientListResponse>({
    queryKey: ['physician', 'patients', { ...params }],
    queryFn: () => apiClient.physician.patients(params),
    staleTime: 60000,
    refetchOnWindowFocus: false,
    enabled,
    retry: 2,
  })
}
