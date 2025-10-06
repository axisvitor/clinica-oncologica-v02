/**
 * TypeScript Type Definitions for Wave 2 Backend Endpoints
 *
 * Auto-generated from OpenAPI/Swagger specifications
 * Generated from Pydantic models
 *
 * Version: 1.0.0
 * Date: 2025-10-06
 * Base URL: https://api.hormonia.com/api/v1
 */

// ============================================================================
// Common Types
// ============================================================================

/**
 * Service health status enum
 */
export type ServiceStatus = 'healthy' | 'degraded' | 'down'

/**
 * Risk level enum
 */
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

/**
 * Risk trend enum
 */
export type RiskTrend = 'improving' | 'stable' | 'worsening'

/**
 * Alert severity enum
 */
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical'

/**
 * Activity type enum
 */
export type ActivityType = 'message' | 'alert' | 'quiz_completion' | 'treatment_update'

/**
 * Flow state enum
 */
export type FlowState = 'onboarding' | 'active' | 'paused' | 'completed' | 'inactive'

/**
 * Time period enum for analytics
 */
export type AnalyticsPeriod = '7d' | '30d' | '90d' | 'all'

// ============================================================================
// 1. Admin System Stats Endpoint
// ============================================================================

/**
 * System health metrics
 */
export interface SystemHealthMetrics {
  /** Current CPU usage percentage (0-100) */
  cpu_percent: number
  /** Current memory usage percentage (0-100) */
  memory_percent: number
  /** Current disk usage in gigabytes */
  disk_usage_gb: number
  /** System uptime in hours */
  uptime_hours: number
}

/**
 * Active user metrics by role
 */
export interface ActiveUsersMetrics {
  /** Total number of active users */
  total: number
  /** Number of active doctors */
  doctors: number
  /** Number of active patients */
  patients: number
  /** Number of active admins */
  admins: number
}

/**
 * Database performance metrics
 */
export interface DatabaseMetrics {
  /** Total database size in megabytes */
  total_size_mb: number
  /** Current number of active database connections */
  active_connections: number
  /** Average query execution time in milliseconds */
  query_performance_ms: number
  /** Redis cache hit rate (0.0 to 1.0) */
  cache_hit_rate: number
}

/**
 * Service status for external dependencies
 */
export interface ServiceStatusMetrics {
  /** Redis service status */
  redis: ServiceStatus
  /** Database service status */
  database: ServiceStatus
  /** Evolution API service status */
  evolution_api: ServiceStatus
  /** OpenAI API service status */
  openai_api: ServiceStatus
}

/**
 * Response schema for GET /api/v1/admin/system-stats
 */
export interface SystemStatsResponse {
  /** System health and resource metrics */
  system_health: SystemHealthMetrics
  /** Active user counts by role */
  active_users: ActiveUsersMetrics
  /** Database performance metrics */
  database_metrics: DatabaseMetrics
  /** External service status */
  service_status: ServiceStatusMetrics
  /** Last update timestamp (ISO8601) */
  last_updated: string
}

// ============================================================================
// 2. Analytics Treatment Distribution Endpoint
// ============================================================================

/**
 * Treatment type distribution item
 */
export interface TreatmentDistributionItem {
  /** Treatment type name */
  treatment_type: string
  /** Number of patients with this treatment */
  count: number
  /** Percentage of total patients (0-100) */
  percentage: number
  /** Number of currently active patients */
  active_patients: number
  /** Average number of days in treatment */
  avg_treatment_days: number
  /** Hex color code for chart visualization */
  color: string
}

/**
 * Weekly trend data point
 */
export interface TrendDataPoint {
  /** Week start date (ISO date) */
  week: string
  /** Patient count for that week */
  count: number
}

/**
 * Response schema for GET /api/v1/analytics/treatment-distribution
 */
export interface TreatmentDistributionResponse {
  /** Selected time period (7d, 30d, 90d, all) */
  period: AnalyticsPeriod
  /** Total number of patients in analysis */
  total_patients: number
  /** Distribution data by treatment type */
  distribution: TreatmentDistributionItem[]
  /** Historical trend data (last 12 weeks) */
  trend_data: TrendDataPoint[]
  /** Last update timestamp (ISO8601) */
  last_updated: string
}

// ============================================================================
// 3. Physician Risk Assessments Endpoint
// ============================================================================

/**
 * Recent patient alert
 */
export interface RecentAlert {
  /** Alert severity level */
  severity: AlertSeverity
  /** Alert type identifier */
  type: string
  /** Human-readable alert message */
  message: string
  /** Alert creation timestamp (ISO8601) */
  created_at: string
}

/**
 * Individual patient risk assessment
 */
export interface PatientRiskAssessment {
  /** Patient unique identifier (UUID) */
  patient_id: string
  /** Patient full name */
  patient_name: string
  /** Overall risk level classification */
  risk_level: RiskLevel
  /** Calculated risk score (0.0 to 10.0) */
  risk_score: number
  /** Primary risk driver category */
  risk_category: string
  /** Assessment calculation timestamp (ISO8601) */
  assessment_date: string
  /** Recent alerts for this patient (last 7 days) */
  recent_alerts: RecentAlert[]
  /** Risk trend direction */
  trend: RiskTrend
  /** Last patient interaction timestamp (ISO8601) or null */
  last_interaction: string | null
}

/**
 * Risk assessments summary statistics
 */
export interface RiskAssessmentsSummary {
  /** Total number of patients in result set */
  total_patients: number
  /** Patient counts by risk level */
  by_risk_level: {
    critical: number
    high: number
    medium: number
    low: number
  }
  /** Number of patients requiring immediate attention (critical + high) */
  requiring_attention: number
}

/**
 * Response schema for GET /api/v1/physician/risk-assessments
 */
export interface RiskAssessmentsResponse {
  /** Individual patient risk assessments */
  assessments: PatientRiskAssessment[]
  /** Summary statistics */
  summary: RiskAssessmentsSummary
  /** Last update timestamp (ISO8601) */
  last_updated: string
}

// ============================================================================
// 4. Medico Dashboard Stats Endpoint
// ============================================================================

/**
 * Dashboard overview metrics
 */
export interface DashboardOverview {
  /** Total number of patients under care */
  total_patients: number
  /** Number of currently active treatment protocols */
  active_treatments: number
  /** Number of patients requiring review */
  pending_reviews: number
  /** Number of new alerts created today */
  new_alerts_today: number
}

/**
 * Treatment type breakdown item
 */
export interface TreatmentTypeBreakdown {
  /** Treatment type name */
  treatment_type: string
  /** Number of patients with this treatment */
  count: number
}

/**
 * Patient breakdown by various categories
 */
export interface PatientBreakdown {
  /** Patient counts by flow state */
  by_flow_state: Record<FlowState, number>
  /** Patient counts by treatment type */
  by_treatment_type: TreatmentTypeBreakdown[]
}

/**
 * Patient engagement metrics
 */
export interface EngagementMetrics {
  /** Number of messages sent today */
  messages_today: number
  /** 7-day response rate percentage (0-100) */
  response_rate_7d: number
  /** Average response time in hours */
  avg_response_time_hours: number
  /** Number of quizzes completed in last 7 days */
  quizzes_completed_7d: number
}

/**
 * Alerts summary by severity
 */
export interface AlertsSummary {
  /** Total number of unacknowledged alerts */
  unacknowledged: number
  /** Alert counts by severity level */
  by_severity: {
    critical: number
    high: number
    medium: number
    low: number
  }
}

/**
 * Recent activity feed item
 */
export interface RecentActivity {
  /** Activity type */
  type: ActivityType
  /** Patient name associated with activity */
  patient_name: string
  /** Human-readable activity description */
  description: string
  /** Activity timestamp (ISO8601) */
  timestamp: string
}

/**
 * Performance indicators
 */
export interface PerformanceIndicators {
  /** Treatment completion rate percentage (0-100) */
  completion_rate: number
  /** Average patient satisfaction score (0-5) */
  patient_satisfaction_score: number
  /** Treatment adherence rate percentage (0-100) */
  adherence_rate: number
}

/**
 * Response schema for GET /api/v1/medico/dashboard-stats
 */
export interface MedicoDashboardStatsResponse {
  /** Overview metrics */
  overview: DashboardOverview
  /** Patient breakdown by category */
  patient_breakdown: PatientBreakdown
  /** Engagement metrics */
  engagement_metrics: EngagementMetrics
  /** Alerts summary */
  alerts_summary: AlertsSummary
  /** Recent activity feed (last 10 items) */
  recent_activity: RecentActivity[]
  /** Performance indicators */
  performance_indicators: PerformanceIndicators
  /** Last update timestamp (ISO8601) */
  last_updated: string
}

// ============================================================================
// Error Response Types
// ============================================================================

/**
 * Standard error response structure
 */
export interface ApiErrorResponse {
  /** Human-readable error message */
  detail: string
  /** Machine-readable error code */
  error_code: string
  /** Error timestamp (ISO8601) */
  timestamp: string
  /** Optional request tracking ID */
  request_id?: string
}

/**
 * Validation error field detail
 */
export interface ValidationErrorField {
  /** Field name that failed validation */
  field: string
  /** Validation error message */
  message: string
  /** Submitted value that failed validation */
  value: any
}

/**
 * Validation error response with field details
 */
export interface ValidationErrorResponse extends ApiErrorResponse {
  /** Array of field-level validation errors */
  errors: ValidationErrorField[]
}

/**
 * Rate limit error response
 */
export interface RateLimitErrorResponse extends ApiErrorResponse {
  /** Seconds to wait before retrying */
  retry_after: number
}

// ============================================================================
// Request Parameter Types
// ============================================================================

/**
 * Query parameters for treatment distribution endpoint
 */
export interface TreatmentDistributionParams {
  /** Time period for analysis (default: 30d) */
  period?: AnalyticsPeriod
  /** Filter by specific doctor (admin only) */
  doctor_id?: string
}

/**
 * Query parameters for risk assessments endpoint
 */
export interface RiskAssessmentsParams {
  /** Filter by specific patient */
  patient_id?: string
  /** Filter by risk level */
  risk_level?: RiskLevel
  /** Maximum number of results (1-100, default: 20) */
  limit?: number
}

// ============================================================================
// API Client Types
// ============================================================================

/**
 * API request configuration
 */
export interface ApiRequestConfig {
  /** Request method */
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  /** Request headers */
  headers?: Record<string, string>
  /** Query parameters */
  params?: Record<string, any>
  /** Request body */
  data?: any
  /** Request timeout in milliseconds */
  timeout?: number
}

/**
 * API response wrapper
 */
export interface ApiResponse<T = any> {
  /** Response data */
  data: T
  /** HTTP status code */
  status: number
  /** Response headers */
  headers: Record<string, string>
  /** Cache status */
  cacheStatus?: 'HIT' | 'MISS' | 'BYPASS' | 'EXPIRED'
}

// ============================================================================
// React Query Types
// ============================================================================

/**
 * React Query options for system stats
 */
export interface SystemStatsQueryOptions {
  /** Refetch interval in milliseconds (default: 30000) */
  refetchInterval?: number
  /** Stale time in milliseconds (default: 25000) */
  staleTime?: number
  /** Enable/disable query (default: true) */
  enabled?: boolean
}

/**
 * React Query options for treatment distribution
 */
export interface TreatmentDistributionQueryOptions {
  /** Time period parameter */
  period?: AnalyticsPeriod
  /** Refetch interval in milliseconds (default: 300000) */
  refetchInterval?: number
  /** Stale time in milliseconds (default: 240000) */
  staleTime?: number
  /** Enable/disable query (default: true) */
  enabled?: boolean
}

/**
 * React Query options for risk assessments
 */
export interface RiskAssessmentsQueryOptions extends RiskAssessmentsParams {
  /** Refetch interval in milliseconds (default: 60000) */
  refetchInterval?: number
  /** Stale time in milliseconds (default: 50000) */
  staleTime?: number
  /** Enable/disable query (default: true) */
  enabled?: boolean
}

/**
 * React Query options for medico dashboard
 */
export interface MedicoDashboardQueryOptions {
  /** Refetch interval in milliseconds (default: 120000) */
  refetchInterval?: number
  /** Stale time in milliseconds (default: 100000) */
  staleTime?: number
  /** Enable/disable query (default: true) */
  enabled?: boolean
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if response is an error
 */
export function isApiError(response: any): response is ApiErrorResponse {
  return (
    typeof response === 'object' &&
    'detail' in response &&
    'error_code' in response &&
    'timestamp' in response
  )
}

/**
 * Type guard to check if error is a validation error
 */
export function isValidationError(error: any): error is ValidationErrorResponse {
  return isApiError(error) && 'errors' in error && Array.isArray(error.errors)
}

/**
 * Type guard to check if error is a rate limit error
 */
export function isRateLimitError(error: any): error is RateLimitErrorResponse {
  return isApiError(error) && 'retry_after' in error && typeof error.retry_after === 'number'
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Partial update type for any Wave 2 response
 */
export type PartialUpdate<T> = {
  [P in keyof T]?: T[P]
}

/**
 * Make all properties optional recursively
 */
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P]
}

/**
 * Extract array element type
 */
export type ArrayElement<ArrayType extends readonly unknown[]> =
  ArrayType extends readonly (infer ElementType)[] ? ElementType : never

/**
 * Make specific properties required
 */
export type WithRequired<T, K extends keyof T> = T & { [P in K]-?: T[P] }

// ============================================================================
// Constants
// ============================================================================

/**
 * Valid analytics periods
 */
export const ANALYTICS_PERIODS = ['7d', '30d', '90d', 'all'] as const

/**
 * Valid risk levels
 */
export const RISK_LEVELS = ['low', 'medium', 'high', 'critical'] as const

/**
 * Valid service statuses
 */
export const SERVICE_STATUSES = ['healthy', 'degraded', 'down'] as const

/**
 * Valid flow states
 */
export const FLOW_STATES = ['onboarding', 'active', 'paused', 'completed', 'inactive'] as const

/**
 * Default cache TTLs (in seconds)
 */
export const CACHE_TTL = {
  SYSTEM_STATS: 30,
  TREATMENT_DISTRIBUTION: 300,
  RISK_ASSESSMENTS: 60,
  MEDICO_DASHBOARD: 120,
} as const

/**
 * API endpoint paths
 */
export const ENDPOINTS = {
  SYSTEM_STATS: '/api/v1/admin/system-stats',
  TREATMENT_DISTRIBUTION: '/api/v1/analytics/treatment-distribution',
  RISK_ASSESSMENTS: '/api/v1/physician/risk-assessments',
  MEDICO_DASHBOARD: '/api/v1/medico/dashboard-stats',
} as const

// ============================================================================
// Example Usage
// ============================================================================

/**
 * Example usage of types with fetch function
 *
 * @example
 * ```typescript
 * import { SystemStatsResponse, ENDPOINTS } from './typescript-types-wave2'
 *
 * async function fetchSystemStats(): Promise<SystemStatsResponse> {
 *   const response = await fetch(ENDPOINTS.SYSTEM_STATS, {
 *     headers: {
 *       'Authorization': `Bearer ${token}`
 *     }
 *   })
 *
 *   if (!response.ok) {
 *     const error = await response.json()
 *     if (isApiError(error)) {
 *       console.error('API Error:', error.error_code, error.detail)
 *     }
 *     throw error
 *   }
 *
 *   return response.json()
 * }
 * ```
 */

/**
 * Example usage with React Query
 *
 * @example
 * ```typescript
 * import { useQuery } from '@tanstack/react-query'
 * import {
 *   RiskAssessmentsResponse,
 *   RiskAssessmentsParams,
 *   ENDPOINTS
 * } from './typescript-types-wave2'
 *
 * function useRiskAssessments(params: RiskAssessmentsParams) {
 *   return useQuery<RiskAssessmentsResponse>({
 *     queryKey: ['risk-assessments', params],
 *     queryFn: async () => {
 *       const url = new URL(ENDPOINTS.RISK_ASSESSMENTS, window.location.origin)
 *       if (params.patient_id) url.searchParams.set('patient_id', params.patient_id)
 *       if (params.risk_level) url.searchParams.set('risk_level', params.risk_level)
 *       if (params.limit) url.searchParams.set('limit', params.limit.toString())
 *
 *       const response = await fetch(url.toString(), {
 *         headers: {
 *           'Authorization': `Bearer ${getToken()}`
 *         }
 *       })
 *
 *       if (!response.ok) throw new Error('Failed to fetch risk assessments')
 *       return response.json()
 *     },
 *     refetchInterval: 60000,
 *     staleTime: 50000
 *   })
 * }
 * ```
 */

/**
 * Export everything for easy importing
 */
export default {
  // Response types
  SystemStatsResponse,
  TreatmentDistributionResponse,
  RiskAssessmentsResponse,
  MedicoDashboardStatsResponse,

  // Request parameter types
  TreatmentDistributionParams,
  RiskAssessmentsParams,

  // Error types
  ApiErrorResponse,
  ValidationErrorResponse,
  RateLimitErrorResponse,

  // Type guards
  isApiError,
  isValidationError,
  isRateLimitError,

  // Constants
  ANALYTICS_PERIODS,
  RISK_LEVELS,
  SERVICE_STATUSES,
  FLOW_STATES,
  CACHE_TTL,
  ENDPOINTS,
}
