/**
 * Shared API client transport barrel.
 *
 * Domain owners live under ./types/* while this file remains the stable
 * import surface for callers using @/lib/api-client/types.
 */

export * from './types/common'
export * from './types/messages'
export * from './types/flows'
export * from './types/alerts'
export * from './types/reports'
export * from './types/admin'
export * from './types/ai'
export * from './types/quiz'
export * from './types/tasks'
export * from './types/notifications'
export type {
  RiskAssessmentRequest,
  RiskFactor,
  RiskAssessment,
  RiskAssessmentsResponse,
  PhysicianRiskAssessment,
  PhysicianRiskAssessmentsResponse,
} from './types/physician'
export * from './types/flow-engine'
