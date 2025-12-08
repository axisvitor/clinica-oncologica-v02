import type { AnalyticsPeriod } from '@/types/api-wave2'
import type { ActivityItem, Alert } from '@/types/api'
import { ApiClientCore } from './core'
import { createLogger } from '@/utils/logger'

const logger = createLogger('AnalyticsApi')

export interface DashboardMetrics {
  total_patients: number
  active_patients: number
  total_appointments: number
  completed_appointments: number
  pending_messages: number
  unread_messages: number
  quiz_completion_rate: number
  patient_engagement_rate: number
  period?: {
    start_date?: string | null
    end_date?: string | null
  }
}

export interface DashboardAnalyticsData {
  total_patients: number
  active_patients: number
  active_patients_percentage: number
  patients_change: number
  response_rate: number
  response_rate_change: number
  messages_sent: number
  messages_change: number
  alerts_pending: number
  alerts_change: number
  completed_quizzes: number
  quizzes_change: number
  avg_response_time: number
  engagement_chart: Array<{ date: string; messages_sent: number; responses_received: number; response_rate: number }>
  recent_alerts: Alert[]
  recent_activity: ActivityItem[]
  total_quizzes: number
  active_conversations: number
  high_risk_patients: number
  avg_sentiment: number
  pending_reviews: number
}

export interface EngagementDistributionItem {
  label: string
  value: number
  percentage: number
}

export interface EngagementAnalytics {
  total_active_patients: number
  average_quizzes_per_patient: number
  distribution: EngagementDistributionItem[]
}

export interface PatientsAnalytics {
  total_active_patients: number
  segments: EngagementDistributionItem[]
}

export type PerformanceMetrics = Record<string, never>
export type TimeSeriesData = { timestamp: string; value: number; label?: string }
export type AnalyticsReport = Record<string, unknown>
export type PatientEngagementData = EngagementDistributionItem
export type TreatmentOutcomes = Record<string, unknown>

export interface TreatmentDistributionItem {
  treatment_type: string
  count: number
  percentage: number
  color: string
}

export interface TreatmentDistribution {
  period: AnalyticsPeriod
  total_patients: number
  distribution: TreatmentDistributionItem[]
  trend_data: Array<{ week: string; count: number }>
  last_updated: string
}

export interface PatientRiskAssessment {
  id: string
  patient_id: string
  name?: string | null
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  risk_factors: string[]
  last_response?: string | null
  recommended_actions: string[]
}

export interface RiskAssessmentResponse {
  success: boolean
  risk_level_filter: string
  risk_assessments: PatientRiskAssessment[]
  total_patients: number
  generated_at: string
  lookback_days: number
}

interface AnalyticsOverviewResponse {
  total_patients: number
  total_quizzes: number
  completed_quizzes: number
  completion_rate: number
  active_patients_30d: number
  period: {
    start_date?: string | null
    end_date?: string | null
  }
}

interface QuizStatusResponse {
  distribution: Record<string, number>
  total: number
  filters: Record<string, unknown>
}

interface CompletionTrendPoint {
  year: number
  month: number
  total: number
  completed: number
  completion_rate: number
}

interface CompletionTrendResponse {
  trend: CompletionTrendPoint[]
  period: Record<string, unknown>
}

interface PatientEngagementResponse {
  engagement_levels: {
    no_quizzes: number
    low_engagement: number
    high_engagement: number
  }
  average_quizzes_per_patient: number
  total_active_patients: number
}

interface TreatmentDistributionResponse {
  period: AnalyticsPeriod
  total_patients: number
  distribution: Array<{
    treatment_type: string
    count: number
    percentage: number
    color: string
  }>
  trend_data: Array<{ week: string; count: number }>
  last_updated: string
}

const COLOR_PALETTE = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#0ea5e9']

function getColor(index: number): string {
  const i = Math.abs(index) % COLOR_PALETTE.length
  return COLOR_PALETTE[i] ?? '#2563eb'
}

function normalizeMonthPoint(point: CompletionTrendPoint) {
  const date = new Date(Date.UTC(point.year, point.month - 1, 1))
  return {
    date: date.toISOString(),
    response_rate: point.completion_rate ?? 0,
    total: point.total ?? 0,
    completed: point.completed ?? 0,
  }
}

function buildEngagementDistribution(data: PatientEngagementResponse): EngagementDistributionItem[] {
  const total = data.total_active_patients || 0
  const levels = data.engagement_levels
  const entries: Array<[string, number]> = [
    ['Sem questionarios', levels.no_quizzes],
    ['Engajamento baixo (1-5)', levels.low_engagement],
    ['Engajamento alto (6+)', levels.high_engagement],
  ]

  return entries.map(([label, value], index) => ({
    label,
    value,
    percentage: total > 0 ? (value / total) * 100 : 0,
    color: getColor(index),
  }))
}

export function createAnalyticsApi(client: ApiClientCore) {
  const fetchOverview = (params?: Record<string, string | number | boolean>) =>
    client.get<AnalyticsOverviewResponse>('/api/v2/analytics/overview', params)

  const fetchQuizStatus = (params?: Record<string, string | number | boolean>) =>
    client.get<QuizStatusResponse>('/api/v2/analytics/quiz-status', params)

  const fetchTrend = (months = 6) =>
    client.get<CompletionTrendResponse>('/api/v2/analytics/completion-trend', { months })

  const fetchEngagement = () =>
    client.get<PatientEngagementResponse>('/api/v2/analytics/patient-engagement')

  return {
    async dashboard(_params?: Record<string, unknown>): Promise<DashboardAnalyticsData> {
      const [overview, status, trend, engagement] = await Promise.all([
        fetchOverview(),
        fetchQuizStatus(),
        fetchTrend(6),
        fetchEngagement(),
      ])

      const totalQuizzes = overview.total_quizzes ?? 0
      const completedQuizzes = overview.completed_quizzes ?? 0
      const alertsPending = status.distribution?.['cancelled'] ?? 0
      const activePatients = overview.active_patients_30d ?? 0
      const totalPatients = overview.total_patients ?? 0
      const responseRate = overview.completion_rate ?? 0

      const engagementChart = (trend.trend ?? [])
        .map(normalizeMonthPoint)
        .map(point => ({
          date: point.date,
          messages_sent: point.total,
          responses_received: point.completed,
          response_rate: Math.round(point.response_rate),
        }))

      return {
        total_patients: totalPatients,
        active_patients: activePatients,
        active_patients_percentage: totalPatients ? (activePatients / totalPatients) * 100 : 0,
        patients_change: 0,
        response_rate: Math.round(responseRate),
        response_rate_change: 0,
        messages_sent: totalQuizzes,
        messages_change: 0,
        alerts_pending: alertsPending,
        alerts_change: 0,
        completed_quizzes: completedQuizzes,
        quizzes_change: 0,
        avg_response_time: 0,
        engagement_chart: engagementChart,
        recent_alerts: [] as Alert[],
        recent_activity: [] as ActivityItem[],
        total_quizzes: totalQuizzes,
        active_conversations: activePatients,
        high_risk_patients: 0,
        avg_sentiment: 0,
        pending_reviews: 0,
      }
    },

    async engagement(): Promise<EngagementAnalytics> {
      const data = await fetchEngagement()
      return {
        total_active_patients: data.total_active_patients ?? 0,
        average_quizzes_per_patient: data.average_quizzes_per_patient ?? 0,
        distribution: buildEngagementDistribution(data),
      }
    },

    async patients(): Promise<PatientsAnalytics> {
      const data = await fetchEngagement()
      return {
        total_active_patients: data.total_active_patients ?? 0,
        segments: buildEngagementDistribution(data),
      }
    },

    async treatmentDistribution(period: AnalyticsPeriod = '30d'): Promise<TreatmentDistribution> {
      const response = await client.get<TreatmentDistributionResponse>(
        '/api/v2/analytics/treatment-distribution',
        { period }
      )
      // Ensure colors exist
      const distribution = response.distribution.map((item, index) => ({
        ...item,
        color: item.color || getColor(index),
      }))

      return {
        period: response.period,
        total_patients: response.total_patients,
        distribution,
        trend_data: response.trend_data ?? [],
        last_updated: response.last_updated,
      }
    },

    async getDashboardMetrics(params?: {
      start_date?: string
      end_date?: string
      doctor_id?: string
    }): Promise<DashboardMetrics> {
      const overview = await fetchOverview(params)

      return {
        total_patients: overview.total_patients ?? 0,
        active_patients: overview.active_patients_30d ?? 0,
        total_appointments: overview.total_quizzes ?? 0,
        completed_appointments: overview.completed_quizzes ?? 0,
        pending_messages: 0,
        unread_messages: 0,
        quiz_completion_rate: Math.round(overview.completion_rate ?? 0),
        patient_engagement_rate: overview.active_patients_30d ?? 0,
        period: overview.period,
      }
    },

    async riskAssessment(params?: {
      risk_level?: PatientRiskAssessment['risk_level']
      limit?: number
      lookback_days?: number
    }): Promise<RiskAssessmentResponse> {
      const query: Record<string, string | number> = {}
      if (params?.risk_level) query['risk_level'] = params.risk_level
      if (params?.limit) query['limit'] = params.limit
      if (params?.lookback_days) query['lookback_days'] = params.lookback_days
      return client.get<RiskAssessmentResponse>('/api/v2/analytics/risk-assessment', query)
    }
  }
}

export type AnalyticsApi = ReturnType<typeof createAnalyticsApi>

/**
 * Enhanced Analytics Integration
 * Link to AI-powered analytics features
 */
export interface EnhancedInsight {
  category: string
  insights: Array<{
    id: string
    type: 'opportunity' | 'risk' | 'trend' | 'recommendation'
    title: string
    description: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    confidence: number
    data: Record<string, unknown>
  }>
  priority: number
}

export function createEnhancedAnalyticsIntegration(client: ApiClientCore) {
  return {
    /**
     * Get AI-powered insights for standard analytics
     */
    async getEnhancedInsights(): Promise<EnhancedInsight[]> {
      try {
        const response = await client.get<{ success: boolean; data: EnhancedInsight[] }>(
          '/api/v2/enhanced-analytics/insights'
        )
        return response.data
      } catch (error) {
        logger.warn('Enhanced insights not available')
        return []
      }
    },

    /**
     * Check if enhanced analytics features are available
     */
    async isEnhancedAnalyticsAvailable(): Promise<boolean> {
      try {
        await client.get('/api/v2/enhanced-analytics/health')
        return true
      } catch {
        return false
      }
    },

    /**
     * Get enhanced metrics for dashboard
     */
    async getEnhancedMetrics(params?: Record<string, unknown>): Promise<Record<string, unknown>> {
      try {
        const response = await client.get<{ success: boolean; data: Record<string, unknown> }>(
          '/api/v2/enhanced-analytics/metrics',
          params as any
        )
        return response.data
      } catch (error) {
        logger.warn('Enhanced metrics not available', error)
        return { error: true, message: 'Enhanced metrics not available', metrics: {} }
      }
    },
  }
}
