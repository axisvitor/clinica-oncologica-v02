/**
 * Dashboard API Module
 *
 * Handles all dashboard-related API calls:
 * - Main dashboard analytics
 * - Patient-specific dashboard
 * - Physician dashboard
 * - Real-time metrics
 */

import type { ApiClientCore } from './core'
import type { Alert, ActivityItem } from '@/types/api'

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

export interface DashboardMainData {
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
  engagement_chart: Array<{
    date: string
    messages_sent: number
    responses_received: number
    response_rate: number
  }>
  recent_alerts: Alert[]
  recent_activity: ActivityItem[]
  total_quizzes: number
  active_conversations: number
  high_risk_patients: number
  avg_sentiment: number
  pending_reviews: number
  alert_breakdown: {
    critical: number
    high: number
    medium: number
    low: number
  }
  flow_breakdown: {
    active: number
    paused: number
    completed: number
  }
}

export interface DashboardPatientData {
  patient_id: string
  patient_name: string
  treatment_info: {
    type: string
    start_date: string
    current_phase: string
    day: number
  }
  flow_state: {
    status: string
    current_day: number
    next_message_date?: string
    completion_percentage: number
  }
  engagement: {
    total_messages: number
    response_rate: number
    avg_response_time_hours: number
    last_interaction: string
  }
  quiz_history: Array<{
    id: string
    template_name: string
    completed_at: string
    score?: number
  }>
  recent_messages: Array<{
    id: string
    content: string
    direction: 'incoming' | 'outgoing'
    sent_at: string
    status: string
  }>
  alerts: Alert[]
  ai_insights: {
    sentiment: string
    risk_level: 'low' | 'medium' | 'high'
    recommendations: string[]
  }
}

export interface DashboardPhysicianData {
  overview: {
    total_patients: number
    active_treatments: number
    high_risk_patients: number
    pending_reviews: number
  }
  patient_list: Array<{
    id: string
    name: string
    treatment_type: string
    current_day: number
    risk_level: 'low' | 'medium' | 'high'
    last_interaction: string
    response_rate: number
  }>
  upcoming_interactions: Array<{
    patient_id: string
    patient_name: string
    type: 'message' | 'quiz' | 'appointment'
    scheduled_for: string
  }>
  completion_trend: Array<{
    date: string
    quizzes_sent: number
    quizzes_completed: number
    completion_rate: number
  }>
  risk_distribution: {
    low: number
    medium: number
    high: number
  }
  recent_alerts: Alert[]
}

// ============================================================================
// DASHBOARD API METHODS
// ============================================================================

/**
 * Dashboard API methods
 */
export function createDashboardApi(client: ApiClientCore) {
  return {
    /**
     * Get main dashboard data
     * Transforms backend response to frontend-expected format
     */
    getMain: async (params?: {
      start_date?: string
      end_date?: string
      doctor_id?: string
      time_range?: 'today' | 'week' | 'month' | 'quarter' | 'year'
    }): Promise<DashboardMainData> => {
      // Build query params
      const queryParams: Record<string, string | number | boolean> = {}
      if (params?.time_range) queryParams['time_range'] = params.time_range
      if (params?.start_date) queryParams['custom_start'] = params.start_date
      if (params?.end_date) queryParams['custom_end'] = params.end_date

      // Fetch from dedicated dashboard endpoint (single API call, cached on backend)
      const response = await client.get<{
        user_role: string
        time_range: string
        start_date: string
        end_date: string
        patient_metrics: {
          total_patients: number
          active_patients: number
          inactive_patients: number
          new_patients: number
          high_risk_patients: number
        }
        message_metrics: {
          total_messages: number
          sent_count: number
          delivered_count: number
          failed_count: number
          response_count: number
          response_rate: number
        }
        alert_metrics: {
          total_alerts: number
          pending_alerts: number
          acknowledged_alerts: number
          critical_alerts: number
          high_alerts: number
          medium_alerts: number
          low_alerts: number
        }
        flow_metrics: {
          total_flows: number
          active_flows: number
          completed_flows: number
          paused_flows: number
          completion_rate: number
          avg_completion_days: number
        }
        recent_activity: Array<{
          id: string
          type: string
          description: string
          entity_name?: string
          timestamp: string
          icon?: string
          link?: string
        }>
        generated_at: string
      }>('/api/v2/dashboard/main', queryParams)

      // Transform to frontend-expected flat format
      const pm = response.patient_metrics || {}
      const mm = response.message_metrics || {}
      const am = response.alert_metrics || {}
      const fm = response.flow_metrics || {}

      // Calculate percentage
      const totalPatients = pm.total_patients || 0
      const activePatients = pm.active_patients || 0
      const activePercentage = totalPatients > 0 ? (activePatients / totalPatients) * 100 : 0

      return {
        total_patients: totalPatients,
        active_patients: activePatients,
        active_patients_percentage: Math.round(activePercentage * 10) / 10,
        patients_change: pm.new_patients || 0,
        response_rate: Math.round(mm.response_rate || 0),
        response_rate_change: 0, // Not available in current response
        messages_sent: mm.total_messages || 0,
        messages_change: 0, // Not available in current response
        alerts_pending: am.pending_alerts || 0,
        alerts_change: am.critical_alerts || 0,
        completed_quizzes: fm.completed_flows || 0,
        quizzes_change: 0, // Not available in current response
        avg_response_time: Math.round(fm.avg_completion_days || 0),
        engagement_chart: [], // Will be populated from another endpoint if needed
        recent_alerts: [], // Convert from recent_activity if type is alert
        recent_activity: (response.recent_activity || []).map(activity => ({
          id: activity.id,
          type: activity.type as 'message' | 'quiz' | 'flow' | 'alert' | 'system',
          description: activity.description,
          entity_name: activity.entity_name,
          timestamp: activity.timestamp,
          icon: activity.icon,
          link: activity.link,
        })),
        total_quizzes: fm.total_flows || 0,
        active_conversations: mm.response_count || 0,
        high_risk_patients: pm.high_risk_patients || 0,
        avg_sentiment: 0, // Not available in current response
        pending_reviews: am.pending_alerts || 0,
        // Detailed breakdowns
        alert_breakdown: {
          critical: am.critical_alerts || 0,
          high: am.high_alerts || 0,
          medium: am.medium_alerts || 0,
          low: am.low_alerts || 0
        },
        flow_breakdown: {
          active: fm.active_flows || 0,
          paused: fm.paused_flows || 0,
          completed: fm.completed_flows || 0
        }
      }
    },

    /**
     * Get patient-specific dashboard
     */
    getPatient: async (patientId: string): Promise<DashboardPatientData> => {
      return client.get<DashboardPatientData>(`/api/v2/dashboard/patient/${patientId}`)
    },

    /**
     * Get physician dashboard
     */
    getPhysician: async (params?: {
      start_date?: string
      end_date?: string
    }): Promise<DashboardPhysicianData> => {
      return client.get<DashboardPhysicianData>('/api/v2/dashboard/physician', params)
    },

    /**
     * Get real-time metrics (for live updates)
     * Uses enhanced-analytics/realtime-stream endpoint
     */
    getRealTimeMetrics: async (): Promise<{
      active_patients: number
      pending_messages: number
      unread_alerts: number
      last_updated: string
    }> => {
      try {
        // Use existing enhanced-analytics endpoint
        const response = await client.get<{
          timestamp: string
          active_sessions: number
          recent_activity_1h: number
          system_health: { status: string; response_time_ms: number; error_rate: number }
          metrics: { patients_active: number; quizzes_today: number }
        }>('/api/v2/enhanced-analytics/realtime-stream')

        // Transform to expected format
        return {
          active_patients: response.metrics?.patients_active ?? response.active_sessions ?? 0,
          pending_messages: response.recent_activity_1h ?? 0,
          unread_alerts: 0, // Not available in this endpoint
          last_updated: response.timestamp ?? new Date().toISOString()
        }
      } catch {
        // Fallback to dashboard/main if enhanced-analytics not available
        const mainData = await client.get<DashboardMainData>('/api/v2/dashboard/main')
        return {
          active_patients: mainData.active_patients ?? 0,
          pending_messages: mainData.messages_sent ?? 0,
          unread_alerts: mainData.alerts_pending ?? 0,
          last_updated: new Date().toISOString()
        }
      }
    }
  }
}

// Export types
export type DashboardApi = ReturnType<typeof createDashboardApi>
