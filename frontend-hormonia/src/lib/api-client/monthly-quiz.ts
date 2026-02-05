/**
 * Monthly Quiz API Module
 *
 * Handles all monthly quiz-related API calls:
 * - Create and manage quiz links
 * - Bulk operations
 * - Quiz statistics and analytics
 * - Link status management
 * - Resend and cancellation
 */

import type { ApiClientCore, PaginatedResponse } from './core'

export interface QuizLink {
  id: string
  quiz_session_id: string
  patient_id: string
  quiz_template_id: string
  patient_name?: string
  template_name?: string
  template_version?: string
  token: string
  link: string
  link_url?: string
  delivery_method: 'whatsapp' | 'email' | 'sms' | 'manual'
  status: 'pending' | 'sent' | 'accessed' | 'completed' | 'expired' | 'cancelled'
  expires_at: string
  sent_at?: string
  accessed_at?: string
  completed_at?: string
  access_count?: number
  created_at: string
  updated_at: string
}

export interface QuizLinkCreate {
  patient_id: string
  quiz_template_id: string
  delivery_method?: 'whatsapp' | 'email' | 'sms' | 'manual'
  expiry_hours?: number
  custom_message?: string
}

export interface QuizLinkBulkCreate {
  patient_ids: string[]
  quiz_template_id: string
  delivery_method?: 'whatsapp' | 'email' | 'sms' | 'manual'
  expiry_hours?: number
  custom_message?: string
}

// QuizSession is imported from @/types/api

export interface QuizStats {
  // New field names (backend v2)
  total_sent: number
  total_completed: number
  total_expired: number
  total_active: number
  average_score: number

  // Old field names (backward compatibility)
  total_links_created?: number
  completed_quizzes?: number
  expired_links?: number
  active_links?: number

  // Calculated metrics
  completion_rate: number
  expiration_rate: number

  // Breakdown by period
  by_period?: {
    daily?: Array<{ date: string; sent: number; completed: number }>
    weekly?: Array<{ week: string; sent: number; completed: number }>
    monthly?: Array<{ month: string; sent: number; completed: number }>
  }

  // Breakdown by doctor
  by_doctor?: Record<string, {
    sent: number
    completed: number
    completion_rate: number
  }>
}

// Import and re-export types from centralized types
import type {
  QuizLinkStatus as ApiQuizLinkStatus,
  QuizLinkStatusValue,
  QuizTemplate,
  QuizSession
} from '@/types/api'
export type QuizLinkStatus = ApiQuizLinkStatus
export type { QuizLinkStatusValue, QuizTemplate, QuizSession }

export interface QuizHistoryEntry {
  id: string
  patient_id?: string
  patient_name?: string
  quiz_template_name: string
  quiz_template_id?: string
  status: QuizSession['status']
  score?: number
  started_at?: string
  completed_at?: string
  sent_at?: string
  accessed_at?: string
  expires_at?: string
  created_at?: string
  delivery_method?: string
}

export type QuizHistory = QuizHistoryEntry[]

// QuizTemplate is imported from @/types/api

export interface QuizResponse {
  id: string
  quiz_session_id: string
  question_id: string
  question_text: string
  response_value: string | string[]
  other_text?: string
  answered_at: string
}

export interface QuizAnalytics {
  template_id: string
  template_name: string
  total_sessions: number
  completion_rate: number
  average_score: number
  average_duration_minutes: number
  question_analytics: Array<{
    question_id: string
    question_text: string
    response_distribution: Record<string, number>
    skip_rate: number
  }>
}

/**
 * Monthly Quiz API methods
 */
export function createMonthlyQuizApi(client: ApiClientCore) {
  return {
    /**
     * Create quiz link for a single patient
     */
    createLink: async (data: QuizLinkCreate): Promise<QuizLink> => {
      return client.post<QuizLink>('/api/v2/monthly-quiz/links/', data)
    },

    /**
     * Create quiz links for multiple patients (bulk)
     */
    bulkCreate: async (data: QuizLinkBulkCreate): Promise<{
      success: number
      failed: number
      links: QuizLink[]
      errors?: Array<{ patient_id: string; error: string }>
    }> => {
      return client.post('/api/v2/monthly-quiz/links/bulk/', data)
    },

    /**
     * Get quiz link status for a specific session
     */
    getStatus: async (sessionId: string): Promise<QuizLinkStatus> => {
      return client.get<QuizLinkStatus>(`/api/v2/monthly-quiz/links/${sessionId}/status`)
    },

    /**
     * Get quiz link status for a patient
     */
    getPatientStatus: async (patientId: string): Promise<QuizLinkStatus[]> => {
      return client.get<QuizLinkStatus[]>(`/api/v2/monthly-quiz/patients/${patientId}/status`)
    },

    /**
     * Get quiz link history for a patient
     */
    getHistory: async (patientId: string): Promise<QuizHistory> => {
      return client.get<QuizHistory>(`/api/v2/monthly-quiz/patients/${patientId}/history`)
    },

    /**
     * Get quiz statistics (dashboard)
     */
    getStats: async (params?: {
      start_date?: string
      end_date?: string
      doctor_id?: string
      template_id?: string
    }): Promise<QuizStats> => {
      return client.get<QuizStats>('/api/v2/monthly-quiz/stats/dashboard/', params)
    },

    /**
     * Get active quiz links
     */
    getActiveLinks: async (filters?: {
      patient_id?: string
      doctor_id?: string
      template_id?: string
    }): Promise<QuizLink[]> => {
      return client.get<QuizLink[]>('/api/v2/monthly-quiz/links/active/', filters)
    },

    /**
     * Get all quiz links with pagination
     */
    listLinks: async (
      page: number = 1,
      size: number = 20,
      filters?: {
        status?: QuizLink['status']
        patient_id?: string
        doctor_id?: string
        template_id?: string
        created_after?: string
        created_before?: string
      }
    ): Promise<PaginatedResponse<QuizLink>> => {
      return client.get<PaginatedResponse<QuizLink>>('/api/v2/monthly-quiz/links/', {
        page,
        size,
        ...filters
      })
    },

    /**
     * Resend quiz link
     */
    resend: async (
      sessionId: string,
      method?: 'whatsapp' | 'email' | 'sms'
    ): Promise<{ message: string; sent_at: string }> => {
      return client.post(`/api/v2/monthly-quiz/links/${sessionId}/resend`, {
        delivery_method: method
      })
    },

    /**
     * Cancel quiz link
     */
    cancel: async (sessionId: string): Promise<{ message: string }> => {
      return client.post<{ message: string }>(
        `/api/v2/monthly-quiz/links/${sessionId}/cancel`
      )
    },

    /**
     * Get quiz session details
     */
    getSession: async (sessionId: string): Promise<QuizSession> => {
      return client.get<QuizSession>(`/api/v2/monthly-quiz/sessions/${sessionId}`)
    },

    /**
     * Get quiz responses for a session
     */
    getSessionResponses: async (sessionId: string): Promise<QuizResponse[]> => {
      return client.get<QuizResponse[]>(`/api/v2/monthly-quiz/sessions/${sessionId}/responses`)
    },

    /**
     * List available quiz templates
     */
    listTemplates: async (activeOnly: boolean = true): Promise<QuizTemplate[]> => {
      return client.get<QuizTemplate[]>('/api/v2/monthly-quiz/templates/', {
        active_only: activeOnly
      })
    },

    /**
     * Get quiz template by ID
     */
    getTemplate: async (templateId: string): Promise<QuizTemplate> => {
      return client.get<QuizTemplate>(`/api/v2/monthly-quiz/templates/${templateId}`)
    },

    /**
     * Get quiz analytics for a template
     */
    getTemplateAnalytics: async (
      templateId: string,
      params?: {
        start_date?: string
        end_date?: string
        doctor_id?: string
      }
    ): Promise<QuizAnalytics> => {
      return client.get<QuizAnalytics>(
        `/api/v2/monthly-quiz/templates/${templateId}/analytics`,
        params
      )
    },

    /**
     * Get completion trend data
     */
    getCompletionTrend: async (params?: {
      period: 'daily' | 'weekly' | 'monthly'
      start_date?: string
      end_date?: string
      doctor_id?: string
    }): Promise<Array<{
      date: string
      sent: number
      completed: number
      completion_rate: number
    }>> => {
      return client.get('/api/v2/monthly-quiz/stats/completion-trend/', params)
    },

    /**
     * Get patient engagement metrics
     */
    getEngagementMetrics: async (params?: {
      doctor_id?: string
      start_date?: string
      end_date?: string
    }): Promise<{
      total_patients: number
      engaged_patients: number
      engagement_rate: number
      average_response_time_hours: number
      by_delivery_method: Record<string, {
        sent: number
        completed: number
        completion_rate: number
      }>
    }> => {
      return client.get('/api/v2/monthly-quiz/stats/engagement/', params)
    },

    /**
     * Export quiz data to CSV
     */
    exportToCsv: async (params?: {
      start_date?: string
      end_date?: string
      doctor_id?: string
      template_id?: string
      status?: QuizLink['status']
    }): Promise<Blob> => {
      const queryParams = new URLSearchParams()
      if (params) {
        Object.entries(params).forEach(([key, value]) => {
          if (value !== undefined) {
            queryParams.set(key, String(value))
          }
        })
      }
      const response = await fetch(
        `${client.getBaseURL()}/api/v2/monthly-quiz/export?${queryParams}`,
        {
          method: 'GET',
          headers: {
            ...client.getSessionHeaders(),
          },
          credentials: 'include'
        }
      )

      if (!response.ok) {
        throw new Error('Failed to export quiz data')
      }

      return response.blob()
    },

    /**
     * Generate quiz report (PDF)
     */
    generateReport: async (
      sessionId: string,
      format: 'pdf' | 'html' = 'pdf'
    ): Promise<Blob> => {
      const response = await fetch(
        `${client.getBaseURL()}/api/v2/monthly-quiz/sessions/${sessionId}/report?format=${format}`,
        {
          method: 'GET',
          headers: {
            ...client.getSessionHeaders(),
          },
          credentials: 'include'
        }
      )

      if (!response.ok) {
        throw new Error('Failed to generate report')
      }

      return response.blob()
    },

    /**
     * Schedule automated quiz sending
     */
    scheduleAutomated: async (data: {
      template_id: string
      patient_ids?: string[]
      doctor_id?: string
      schedule_type: 'once' | 'daily' | 'weekly' | 'monthly'
      schedule_time: string
      delivery_method?: 'whatsapp' | 'email' | 'sms'
      expiry_hours?: number
    }): Promise<{ schedule_id: string; message: string }> => {
      return client.post('/api/v2/monthly-quiz/schedules/', data)
    },

    /**
     * Get scheduled quiz jobs
     */
    getScheduledJobs: async (): Promise<Array<{
      id: string
      template_id: string
      template_name: string
      schedule_type: string
      schedule_time: string
      next_run: string
      is_active: boolean
      created_at: string
    }>> => {
      return client.get('/api/v2/monthly-quiz/schedules/')
    },

    /**
     * Cancel scheduled quiz job
     */
    cancelScheduledJob: async (scheduleId: string): Promise<{ message: string }> => {
      return client.delete<{ message: string }>(
        `/api/v2/monthly-quiz/schedules/${scheduleId}`
      )
    }
  }
}

// Export types
export type MonthlyQuizApi = ReturnType<typeof createMonthlyQuizApi>
