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
     */
    getMain: async (params?: {
      start_date?: string
      end_date?: string
      doctor_id?: string
    }): Promise<DashboardMainData> => {
      return client.get<DashboardMainData>('/api/v2/dashboard/main', params)
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
     */
    getRealTimeMetrics: async (): Promise<{
      active_patients: number
      pending_messages: number
      unread_alerts: number
      last_updated: string
    }> => {
      return client.get('/api/v2/dashboard/metrics/realtime')
    }
  }
}

// Export types
export type DashboardApi = ReturnType<typeof createDashboardApi>
