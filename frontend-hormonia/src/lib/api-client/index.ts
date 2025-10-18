/**
 * API Client - Main Entry Point
 *
 * This is the refactored API client with modular architecture.
 * Each domain (auth, patients, quiz, etc.) has its own module.
 *
 * Usage:
 * ```typescript
 * import { apiClient } from '@/lib/api-client'
 *
 * // Authentication
 * await apiClient.auth.login({ email, password })
 *
 * // Patients
 * const patients = await apiClient.patients.list()
 *
 * // Monthly Quiz
 * await apiClient.monthlyQuiz.createLink({ patient_id, quiz_template_id })
 * ```
 */

import { ApiClientCore } from './core'
import { createAuthApi } from './auth'
import { createPatientsApi } from './patients'
import { createMonthlyQuizApi } from './monthly-quiz'
import { createAnalyticsApi } from './analytics'
import { createLogger } from '../logger'
import { API_BASE_URL } from '../../config'

const logger = createLogger('ApiClient')

// Re-export core types
export type { ApiResponse, PaginatedResponse, RequestOptions } from './core'
export { ApiError } from './core'

// Re-export domain types
export type * from './auth'
export type * from './patients'
export type * from './monthly-quiz'
export type * from './analytics'

/**
 * Main API Client class
 * Extends core with domain-specific modules
 */
export class ApiClient extends ApiClientCore {
  // Domain modules
  public readonly auth: ReturnType<typeof createAuthApi>
  public readonly patients: ReturnType<typeof createPatientsApi>
  public readonly monthlyQuiz: ReturnType<typeof createMonthlyQuizApi>
  public readonly analytics: ReturnType<typeof createAnalyticsApi>

  // Additional namespaces (lightweight inline implementations)
  public readonly messages: MessagesApi
  public readonly flows: FlowsApi
  public readonly alerts: AlertsApi
  public readonly reports: ReportsApi
  public readonly admin: AdminApi

  constructor(baseURL: string) {
    super(baseURL)

    // Initialize domain modules
    this.auth = createAuthApi(this)
    this.patients = createPatientsApi(this)
    this.monthlyQuiz = createMonthlyQuizApi(this)
    this.analytics = createAnalyticsApi(this)

    // Initialize inline modules (simpler domains)
    this.messages = this.createMessagesApi()
    this.flows = this.createFlowsApi()
    this.alerts = this.createAlertsApi()
    this.reports = this.createReportsApi()
    this.admin = this.createAdminApi()

    logger.log('API Client initialized with modular architecture')
  }

  /**
   * Messages API (inline implementation)
   */
  private createMessagesApi(): MessagesApi {
    return {
      list: (page = 1, size = 20, filters?: any) =>
        this.get('/api/v1/messages', { page, size, ...filters }),

      get: (messageId: string) =>
        this.get(`/api/v1/messages/${messageId}`),

      send: (data: any) =>
        this.post('/api/v1/messages', data),

      markAsRead: (messageId: string) =>
        this.patch(`/api/v1/messages/${messageId}/read`),

      delete: (messageId: string) =>
        this.delete(`/api/v1/messages/${messageId}`),

      getConversation: (patientId: string) =>
        this.get(`/api/v1/messages/conversations/${patientId}`),

      sendBulk: (data: { patient_ids: string[]; content: string }) =>
        this.post('/api/v1/messages/bulk', data)
    }
  }

  /**
   * Flows API (inline implementation)
   */
  private createFlowsApi(): FlowsApi {
    return {
      list: () =>
        this.get('/api/v1/flows'),

      get: (flowId: string) =>
        this.get(`/api/v1/flows/${flowId}`),

      create: (data: any) =>
        this.post('/api/v1/flows', data),

      update: (flowId: string, data: any) =>
        this.put(`/api/v1/flows/${flowId}`, data),

      delete: (flowId: string) =>
        this.delete(`/api/v1/flows/${flowId}`),

      activate: (flowId: string) =>
        this.post(`/api/v1/flows/${flowId}/activate`),

      deactivate: (flowId: string) =>
        this.post(`/api/v1/flows/${flowId}/deactivate`),

      execute: (flowId: string, data?: any) =>
        this.post(`/api/v1/flows/${flowId}/execute`, data),

      getExecutions: (flowId: string) =>
        this.get(`/api/v1/flows/${flowId}/executions`)
    }
  }

  /**
   * Alerts API (inline implementation)
   */
  private createAlertsApi(): AlertsApi {
    return {
      list: (page = 1, size = 20, filters?: any) =>
        this.get('/api/v1/alerts', { page, size, ...filters }),

      get: (alertId: string) =>
        this.get(`/api/v1/alerts/${alertId}`),

      create: (data: any) =>
        this.post('/api/v1/alerts', data),

      update: (alertId: string, data: any) =>
        this.put(`/api/v1/alerts/${alertId}`, data),

      delete: (alertId: string) =>
        this.delete(`/api/v1/alerts/${alertId}`),

      markAsRead: (alertId: string) =>
        this.patch(`/api/v1/alerts/${alertId}/read`),

      markAllAsRead: () =>
        this.post('/api/v1/alerts/read-all'),

      getUnreadCount: () =>
        this.get('/api/v1/alerts/unread-count')
    }
  }

  /**
   * Reports API (inline implementation)
   */
  private createReportsApi(): ReportsApi {
    return {
      list: () =>
        this.get('/api/v1/reports'),

      generate: (type: string, params?: any) =>
        this.post(`/api/v1/reports/generate/${type}`, params),

      download: async (reportId: string, format: 'pdf' | 'excel' | 'csv' = 'pdf') => {
        const response = await fetch(
          `${this.getBaseURL()}/api/v1/reports/${reportId}/download?format=${format}`,
          {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${this.getAuthToken()}`
            },
            credentials: 'include'
          }
        )

        if (!response.ok) {
          throw new Error('Failed to download report')
        }

        return response.blob()
      },

      delete: (reportId: string) =>
        this.delete(`/api/v1/reports/${reportId}`),

      schedule: (data: {
        report_type: string
        frequency: 'daily' | 'weekly' | 'monthly'
        recipients: string[]
        parameters?: any
      }) =>
        this.post('/api/v1/reports/schedule', data),

      getScheduled: () =>
        this.get('/api/v1/reports/scheduled')
    }
  }

  /**
   * Admin API (inline implementation)
   */
  private createAdminApi(): AdminApi {
    return {
      users: {
        list: (page = 1, size = 20) =>
          this.get('/api/v1/admin/users', { page, size }),

        get: (userId: string) =>
          this.get(`/api/v1/admin/users/${userId}`),

        create: (data: any) =>
          this.post('/api/v1/admin/users', data),

        update: (userId: string, data: any) =>
          this.put(`/api/v1/admin/users/${userId}`, data),

        delete: (userId: string) =>
          this.delete(`/api/v1/admin/users/${userId}`),

        resetPassword: (userId: string) =>
          this.post(`/api/v1/admin/users/${userId}/reset-password`),

        toggleStatus: (userId: string) =>
          this.patch(`/api/v1/admin/users/${userId}/toggle-status`)
      },

      roles: {
        list: () =>
          this.get('/api/v1/admin/roles'),

        create: (data: any) =>
          this.post('/api/v1/admin/roles', data),

        update: (roleId: string, data: any) =>
          this.put(`/api/v1/admin/roles/${roleId}`, data),

        delete: (roleId: string) =>
          this.delete(`/api/v1/admin/roles/${roleId}`)
      },

      audit: {
        list: (page = 1, size = 20, filters?: any) =>
          this.get('/api/v1/admin/audit', { page, size, ...filters }),

        get: (auditId: string) =>
          this.get(`/api/v1/admin/audit/${auditId}`),

        export: async (filters?: any) => {
          const queryParams = new URLSearchParams(filters as any)
          const response = await fetch(
            `${this.getBaseURL()}/api/v1/admin/audit/export?${queryParams}`,
            {
              method: 'GET',
              headers: {
                'Authorization': `Bearer ${this.getAuthToken()}`
              },
              credentials: 'include'
            }
          )

          if (!response.ok) {
            throw new Error('Failed to export audit logs')
          }

          return response.blob()
        }
      },

      settings: {
        get: () =>
          this.get('/api/v1/admin/settings'),

        update: (data: any) =>
          this.put('/api/v1/admin/settings', data),

        reset: () =>
          this.post('/api/v1/admin/settings/reset')
      },

      system: {
        getHealth: () =>
          this.get('/api/v1/admin/system/health'),

        getMetrics: () =>
          this.get('/api/v1/admin/system/metrics'),

        clearCache: () =>
          this.post('/api/v1/admin/system/clear-cache'),

        runMaintenance: () =>
          this.post('/api/v1/admin/system/maintenance')
      }
    }
  }

  /**
   * Clear all cached data
   */
  clearCache(): void {
    // Override if needed in the future for client-side caching
    logger.log('Cache cleared')
  }
}

// Type definitions for inline APIs
interface MessagesApi {
  list: (page?: number, size?: number, filters?: any) => Promise<any>
  get: (messageId: string) => Promise<any>
  send: (data: any) => Promise<any>
  markAsRead: (messageId: string) => Promise<any>
  delete: (messageId: string) => Promise<any>
  getConversation: (patientId: string) => Promise<any>
  sendBulk: (data: { patient_ids: string[]; content: string }) => Promise<any>
}

interface FlowsApi {
  list: () => Promise<any>
  get: (flowId: string) => Promise<any>
  create: (data: any) => Promise<any>
  update: (flowId: string, data: any) => Promise<any>
  delete: (flowId: string) => Promise<any>
  activate: (flowId: string) => Promise<any>
  deactivate: (flowId: string) => Promise<any>
  execute: (flowId: string, data?: any) => Promise<any>
  getExecutions: (flowId: string) => Promise<any>
}

interface AlertsApi {
  list: (page?: number, size?: number, filters?: any) => Promise<any>
  get: (alertId: string) => Promise<any>
  create: (data: any) => Promise<any>
  update: (alertId: string, data: any) => Promise<any>
  delete: (alertId: string) => Promise<any>
  markAsRead: (alertId: string) => Promise<any>
  markAllAsRead: () => Promise<any>
  getUnreadCount: () => Promise<any>
}

interface ReportsApi {
  list: () => Promise<any>
  generate: (type: string, params?: any) => Promise<any>
  download: (reportId: string, format?: 'pdf' | 'excel' | 'csv') => Promise<Blob>
  delete: (reportId: string) => Promise<any>
  schedule: (data: {
    report_type: string
    frequency: 'daily' | 'weekly' | 'monthly'
    recipients: string[]
    parameters?: any
  }) => Promise<any>
  getScheduled: () => Promise<any>
}

interface AdminApi {
  users: {
    list: (page?: number, size?: number) => Promise<any>
    get: (userId: string) => Promise<any>
    create: (data: any) => Promise<any>
    update: (userId: string, data: any) => Promise<any>
    delete: (userId: string) => Promise<any>
    resetPassword: (userId: string) => Promise<any>
    toggleStatus: (userId: string) => Promise<any>
  }
  roles: {
    list: () => Promise<any>
    create: (data: any) => Promise<any>
    update: (roleId: string, data: any) => Promise<any>
    delete: (roleId: string) => Promise<any>
  }
  audit: {
    list: (page?: number, size?: number, filters?: any) => Promise<any>
    get: (auditId: string) => Promise<any>
    export: (filters?: any) => Promise<Blob>
  }
  settings: {
    get: () => Promise<any>
    update: (data: any) => Promise<any>
    reset: () => Promise<any>
  }
  system: {
    getHealth: () => Promise<any>
    getMetrics: () => Promise<any>
    clearCache: () => Promise<any>
    runMaintenance: () => Promise<any>
  }
}

// Create singleton instance
const getApiUrl = () => {
  return API_BASE_URL || import.meta.env['VITE_API_URL'] || 'https://clinica-oncologica-v02-production.up.railway.app'
}

export const apiClient = new ApiClient(getApiUrl())

// Export for testing or custom instances
export { ApiClient }

// Default export
export default apiClient
