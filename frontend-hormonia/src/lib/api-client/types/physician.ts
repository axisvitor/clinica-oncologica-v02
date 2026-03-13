export interface RiskAssessmentRequest {
  patient_id?: string
  days_lookback?: number
}

export interface RiskFactor {
  name: string
  value: number
  weight: number
  description?: string
}

export interface RiskAssessment {
  id: string
  patient_id: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  risk_score: number
  factors: RiskFactor[]
  recommendations: string[]
  assessed_at: string
  assessed_by?: string
}

export interface RiskAssessmentsResponse {
  assessments: RiskAssessment[]
}

export interface PhysicianRiskAssessment {
  patient_id: string
  patient_name?: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  risk_factors: string[]
  last_response?: string
  recommended_actions: string[]
}

export interface PhysicianRiskAssessmentsResponse {
  success: boolean
  risk_level_filter: string
  risk_assessments: PhysicianRiskAssessment[]
  total_patients: number
  generated_at: string
  lookback_days: number
}
