/**
 * Enhanced Analytics API Client
 * Handles AI-powered analytics endpoints
 */

import { createLogger } from '@/utils/logger'
import { apiClient } from './index'

const logger = createLogger('EnhancedAnalytics')
import {
  EnhancedDashboard,
  Prediction,
  TrendData,
  CustomReport,
  DashboardFilters,
  ReportConfig,
  DashboardResponse,
  PredictionsResponse,
  TrendsResponse,
  ReportResponse,
} from '../../types/enhanced-analytics'

type RequestOptions = {
  params?: Record<string, unknown>
  responseType?: 'json' | 'blob'
}

type ApiErrorPayload = { message?: string; error?: string; detail?: string; user_message?: string }

const isCsrfErrorPayload = (payload?: ApiErrorPayload): boolean => {
  const combined = [payload?.error, payload?.detail, payload?.message, payload?.user_message]
    .filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
    .join(' ')
    .toLowerCase()

  return combined.includes('csrf')
}

class ApiClientError extends Error {
  status?: number
  payload?: ApiErrorPayload

  constructor(message: string, status?: number, payload?: ApiErrorPayload) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.payload = payload
  }
}

class HttpClient {
  constructor(
    private readonly baseUrl: string,
    private readonly timeoutMs: number,
    private readonly onUnauthorized: () => void
  ) {}

  async get<T>(path: string, options: RequestOptions = {}): Promise<{ data: T }> {
    return this.request<T>('GET', path, undefined, options)
  }

  async post<T>(path: string, body?: unknown, options: RequestOptions = {}): Promise<{ data: T }> {
    return this.request<T>('POST', path, body, options)
  }

  private async buildHeaders(method: 'GET' | 'POST'): Promise<Record<string, string>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (method === 'POST') {
      if (!apiClient.getCsrfToken()) {
        await apiClient.fetchCsrfToken()
      }

      const csrfToken = apiClient.getCsrfToken()
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken
      }
    }

    return headers
  }

  private async request<T>(
    method: 'GET' | 'POST',
    path: string,
    body?: unknown,
    options: RequestOptions = {},
    retried = false
  ): Promise<{ data: T }> {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), this.timeoutMs)

    try {
      const url = new URL(path.replace(/^\//, ''), this.baseUrl)
      if (options.params) {
        Object.entries(options.params).forEach(([key, value]) => {
          if (value !== undefined && value !== null) {
            url.searchParams.set(key, String(value))
          }
        })
      }

      const response = await fetch(url.toString(), {
        method,
        credentials: 'include',
        headers: await this.buildHeaders(method),
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      })

      if (response.status === 401) {
        this.onUnauthorized()
      }

      if (!response.ok) {
        let payload: ApiErrorPayload | undefined
        try {
          payload = (await response.json()) as ApiErrorPayload
        } catch {
          payload = undefined
        }

        if (response.status === 403 && isCsrfErrorPayload(payload) && !retried && method === 'POST') {
          await apiClient.fetchCsrfToken()
          return this.request<T>(method, path, body, options, true)
        }

        throw new ApiClientError(payload?.message || response.statusText, response.status, payload)
      }

      if (options.responseType === 'blob') {
        return { data: (await response.blob()) as T }
      }

      return { data: (await response.json()) as T }
    } finally {
      window.clearTimeout(timeout)
    }
  }
}

export class EnhancedAnalyticsApi {
  private client: HttpClient
  private baseUrl: string

  constructor(baseUrl?: string) {
    this.baseUrl =
      baseUrl ||
      process.env['REACT_APP_API_URL'] ||
      import.meta.env.VITE_API_BASE_URL ||
      import.meta.env.VITE_API_URL ||
      'http://localhost:8000'
    this.client = new HttpClient(`${this.baseUrl}/api/v2/enhanced-analytics/`, 30000, () => {
      window.location.href = '/login'
    })
  }

  /**
   * Get AI-powered dashboard with insights and predictions
   */
  async getDashboard(filters?: DashboardFilters): Promise<EnhancedDashboard> {
    try {
      const response = await this.client.get<DashboardResponse>('dashboard', {
        params: filters as unknown as Record<string, unknown> | undefined,
      })

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to fetch dashboard')
      }

      return response.data.data
    } catch (error) {
      logger.error('Error fetching enhanced dashboard', error instanceof Error ? error : undefined)
      throw this.handleError(error)
    }
  }

  /**
   * Get AI predictions for patients
   */
  async getPredictions(
    patientId?: string,
    predictionType?: string,
    page = 1,
    pageSize = 50
  ): Promise<Prediction[]> {
    try {
      const response = await this.client.get<PredictionsResponse>('predictions', {
        params: {
          patient_id: patientId,
          prediction_type: predictionType,
          page,
          page_size: pageSize,
        },
      })

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to fetch predictions')
      }

      return response.data.data
    } catch (error) {
      logger.error('Error fetching predictions', error instanceof Error ? error : undefined)
      throw this.handleError(error)
    }
  }

  /**
   * Get trend analysis for a specific metric
   */
  async getTrends(metric: string, period: string, filters?: DashboardFilters): Promise<TrendData> {
    try {
      const response = await this.client.get<TrendsResponse>('trends', {
        params: {
          metric,
          period,
          ...filters,
        },
      })

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to fetch trends')
      }

      return response.data.data
    } catch (error) {
      logger.error('Error fetching trends', error instanceof Error ? error : undefined)
      throw this.handleError(error)
    }
  }

  /**
   * Generate custom analytics report
   */
  async generateCustomReport(config: ReportConfig): Promise<CustomReport> {
    try {
      const response = await this.client.post<ReportResponse>('custom-report', config)

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to generate report')
      }

      return response.data.data
    } catch (error) {
      logger.error('Error generating custom report', error instanceof Error ? error : undefined)
      throw this.handleError(error)
    }
  }

  /**
   * Download report file
   */
  async downloadReport(reportId: string, format: 'pdf' | 'csv' | 'json'): Promise<Blob> {
    try {
      const response = await this.client.get<Blob>(`/reports/${reportId}/download`, {
        params: { format },
        responseType: 'blob',
      })

      return response.data
    } catch (error) {
      logger.error('Error downloading report', error instanceof Error ? error : undefined)
      throw this.handleError(error)
    }
  }

  /**
   * Get available metrics for trend analysis
   */
  async getAvailableMetrics(): Promise<string[]> {
    try {
      const response = await this.client.get<{ success: boolean; data: string[] }>('metrics')

      if (!response.data.success) {
        throw new Error('Failed to fetch available metrics')
      }

      return response.data.data
    } catch (error) {
      logger.error('Error fetching available metrics', error instanceof Error ? error : undefined)
      throw this.handleError(error)
    }
  }

  /**
   * Acknowledge an analytics alert
   */
  async acknowledgeAlert(alertId: string): Promise<void> {
    try {
      await this.client.post(`/alerts/${alertId}/acknowledge`)
    } catch (error) {
      logger.error('Error acknowledging alert', error instanceof Error ? error : undefined)
      throw this.handleError(error)
    }
  }

  /**
   * Export dashboard data
   */
  async exportDashboard(filters?: DashboardFilters, format: 'pdf' | 'csv' = 'pdf'): Promise<Blob> {
    try {
      const response = await this.client.post<Blob>(
        'dashboard/export',
        { filters },
        {
          params: { format },
          responseType: 'blob',
        }
      )

      return response.data
    } catch (error) {
      logger.error('Error exporting dashboard', error instanceof Error ? error : undefined)
      throw this.handleError(error)
    }
  }

  /**
   * Refresh predictions for a specific patient
   */
  async refreshPredictions(patientId: string): Promise<Prediction[]> {
    try {
      const response = await this.client.post<PredictionsResponse>(
        `/predictions/${patientId}/refresh`
      )

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to refresh predictions')
      }

      return response.data.data
    } catch (error) {
      logger.error('Error refreshing predictions', error instanceof Error ? error : undefined)
      throw this.handleError(error)
    }
  }

  /**
   * Error handler
   */
  private handleError(error: unknown): Error {
    if (error instanceof ApiClientError) {
      const message = error.payload?.message || error.message
      return new Error(`API Error: ${message}`)
    }
    if (error instanceof Error) {
      return error
    }
    return new Error('An unknown error occurred')
  }
}

// Export singleton instance
export const enhancedAnalyticsApi = new EnhancedAnalyticsApi()
