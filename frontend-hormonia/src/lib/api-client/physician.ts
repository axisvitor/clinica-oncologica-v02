import type { ApiClientCore } from './core'
import type { PhysicianRiskAssessmentsResponse } from './types'

// --- Physician Patient List types ---

export interface PhysicianPatient {
  id: string
  name: string
  flow_phase: string | null
  flow_current_day: number
  flow_status: string | null
  last_interaction: string | null
  unacknowledged_alerts_count: number
  treatment_type: string | null
}

export interface PhysicianPatientListResponse {
  items: PhysicianPatient[]
  total: number
  page: number
  size: number
}

export interface PhysicianPatientListParams {
  search?: string
  flow_phase?: string
  flow_status?: string
  page?: number
  size?: number
}

// --- API interface ---

export interface PhysicianApi {
  riskAssessments: (
    patientId?: string,
    daysLookback?: number
  ) => Promise<PhysicianRiskAssessmentsResponse>
  patients: (params?: PhysicianPatientListParams) => Promise<PhysicianPatientListResponse>
}

export function createPhysicianApi(client: ApiClientCore): PhysicianApi {
  return {
    riskAssessments: (patientId?: string, daysLookback?: number) => {
      const params: Record<string, string | number> = {}
      if (patientId) {
        params['patient_id'] = patientId
      }
      if (daysLookback) {
        params['days_lookback'] = daysLookback
      }
      return client.get<PhysicianRiskAssessmentsResponse>(
        '/api/v2/physician/risk-assessments',
        params
      )
    },

    patients: (listParams?: PhysicianPatientListParams) => {
      const params: Record<string, string | number> = {}
      if (listParams?.search) params['search'] = listParams.search
      if (listParams?.flow_phase) params['flow_phase'] = listParams.flow_phase
      if (listParams?.flow_status) params['flow_status'] = listParams.flow_status
      if (listParams?.page) params['page'] = listParams.page
      if (listParams?.size) params['size'] = listParams.size
      return client.get<PhysicianPatientListResponse>(
        '/api/v2/physicians/patients',
        params
      )
    },
  }
}
