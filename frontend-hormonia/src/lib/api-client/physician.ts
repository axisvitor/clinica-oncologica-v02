import type { ApiClientCore } from './core'
import type { PhysicianRiskAssessmentsResponse } from './types'

export interface PhysicianApi {
  riskAssessments: (
    patientId?: string,
    daysLookback?: number
  ) => Promise<PhysicianRiskAssessmentsResponse>
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
  }
}
