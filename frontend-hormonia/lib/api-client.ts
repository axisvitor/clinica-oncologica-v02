import { API_BASE_URL } from '../config'
import type {
  ApiResponse,
  PaginatedResponse,
  RequestOptions,
  Patient,
  Message,
  Flow,
  Alert,
  Report,
  User,
  AuthTokens,
  PatientQueryParams,
  MessageQueryParams,
  AlertQueryParams,
  ReportQueryParams,
  CreatePatientRequest,
  UpdatePatientRequest,
  SendMessageRequest,
  StartFlowRequest,
  CreateAlertRequest,
  GenerateReportRequest,
  BulkMessageRequest,
  DashboardAnalytics,
  EngagementMetrics,
  FlowMetrics,
  AIInsight,
  SentimentAnalysis,
  SystemHealth,
  PerformanceMetric,
  Notification,
  ActivityItem,
  FlowTemplate,
  CreateFlowTemplateRequest,
  UpdateFlowTemplateRequest,
  ApiClientFlowsExtended,
  ApiClientReportsExtended,
  ApiClientPatientsExtended
} from '../types'

// Import ApiErrorResponse from shared types
import type { ApiErrorResponse } from '../types/shared'
import { isObject } from './utils/type-guards'

// Endpoint type definitions
interface AuthEndpoints {
  login: (credentials: { email: string; password: string }) => Promise<AuthTokens & { user: User }>
  refresh: (refreshToken: string) => Promise<AuthTokens & { user: User }>
  me: () => Promise<User>
  logout: () => Promise<void>
}

interface MessageEndpoints {
  list: (params?: MessageQueryParams) => Promise<PaginatedResponse<Message>>
  send: (message: SendMessageRequest) => Promise<Message>
  sendBulk: (data: BulkMessageRequest) => Promise<{ batch_id: string; message_ids: string[] }>
  retry: (id: string) => Promise<Message>
  cancel: (id: string) => Promise<void>
}

interface AnalyticsEndpoints {
  dashboard: () => Promise<DashboardAnalytics>
  patients: (params?: { start_date?: string; end_date?: string }) => Promise<EngagementMetrics>
  engagement: (params?: { start_date?: string; end_date?: string }) => Promise<EngagementMetrics>
}

interface AlertEndpoints {
  list: (params?: AlertQueryParams) => Promise<PaginatedResponse<Alert>>
  create: (alert: CreateAlertRequest) => Promise<Alert>
  get: (id: string) => Promise<Alert>
  acknowledge: (id: string) => Promise<Alert>
  resolve: (id: string) => Promise<Alert>
  delete: (id: string) => Promise<void>
}

interface SystemEndpoints {
  health: () => Promise<SystemHealth>
  metrics: () => Promise<PerformanceMetric[]>
  notifications: () => Promise<Notification[]>
}

interface AIEndpoints {
  chat: (message: string, context?: Record<string, unknown>) => Promise<{ response: string; confidence: number }>
  analyze: (data: unknown, analysisType: string) => Promise<AIInsight>
  sentiment: (text: string) => Promise<SentimentAnalysis>
  insights: (patientId: string, timeframe?: string) => Promise<AIInsight[]>
  recommendations: (patientId: string) => Promise<AIInsight[]>
}

interface QuizEndpoints {
  templates: () => Promise<{ templates: unknown[] }>
  start: (patientId: string, templateId: string) => Promise<unknown>
  getSession: (sessionId: string) => Promise<unknown>
  submitResponse: (sessionId: string, responses: unknown) => Promise<void>
  sessions: (params?: { patient_id?: string; status?: string }) => Promise<PaginatedResponse<unknown>>
}

// Enhanced API Error class with better type safety
export class ApiError extends Error {
  constructor(
    public status: number,
    public data: ApiErrorResponse,
    message?: string
  ) {
    super(message || data.message || `API Error: ${status}`)
    this.name = 'ApiError'
  }

  get isRetryable(): boolean {
    return this.status >= 500 || this.status === 429
  }

  get isClientError(): boolean {
    return this.status >= 400 && this.status < 500
  }
}

// Enhanced API client with all necessary interfaces
interface IApiClient {
  setAuthToken(token: string | null): void
  setSupabaseToken(session: { access_token?: string } | null): void
  request<T>(endpoint: string, options?: Partial<RequestOptions>): Promise<T>
  auth: AuthEndpoints
  patients: ApiClientPatientsExtended
  messages: MessageEndpoints
  flows: ApiClientFlowsExtended
  analytics: AnalyticsEndpoints
  alerts: AlertEndpoints
  reports: ApiClientReportsExtended
  system: SystemEndpoints
  ai: AIEndpoints
  quiz: QuizEndpoints
  quizzes: QuizEndpoints
}

class ApiClient implements IApiClient {
  private baseURL: string
  private authToken: string | null = null
  private requestCache = new Map<string, { data: unknown; timestamp: number; ttl: number }>()
  private pendingRequests = new Map<string, Promise<unknown>>()

  constructor(baseURL: string) {
    this.baseURL = baseURL
    // Clear cache periodically
    setInterval(() => this.cleanupCache(), 5 * 60 * 1000) // 5 minutes
  }

  setAuthToken(token: string | null) {
    this.authToken = token
  }

  // Set Supabase access token
  setSupabaseToken(session: { access_token?: string } | null) {
    if (session?.access_token) {
      this.setAuthToken(session.access_token)
    } else {
      this.setAuthToken(null)
      // Clear cache when logging out
      this.clearCache()
    }
  }

  private getCacheKey(url: string, method?: string): string {
    return `${method || 'GET'}:${url}`
  }

  private getCacheTTL(url: string): number {
    // Different TTL for different endpoints
    if (url.includes('/analytics') || url.includes('/reports')) {
      return 5 * 60 * 1000 // 5 minutes for analytics
    }
    if (url.includes('/patients')) {
      return 2 * 60 * 1000 // 2 minutes for patient data
    }
    return 60 * 1000 // 1 minute default
  }

  private getFromCache(key: string): unknown | null {
    const cached = this.requestCache.get(key)
    if (cached && Date.now() - cached.timestamp < cached.ttl) {
      return cached.data
    }
    if (cached) {
      this.requestCache.delete(key)
    }
    return null
  }

  private setCache(key: string, data: unknown, ttl: number): void {
    this.requestCache.set(key, {
      data,
      timestamp: Date.now(),
      ttl
    })
  }

  private cleanupCache(): void {
    const now = Date.now()
    for (const [key, value] of this.requestCache.entries()) {
      if (now - value.timestamp > value.ttl) {
        this.requestCache.delete(key)
      }
    }
  }

  private clearCache(): void {
    this.requestCache.clear()
    this.pendingRequests.clear()
  }

  private buildUrl(endpoint: string, params?: Record<string, string | number | boolean>): string {
    // Normalize base URL: ensure it includes /api/v1 if not already present
    let normalizedBase = this.baseURL
    if (!normalizedBase.includes('/api/v1')) {
      normalizedBase = normalizedBase.replace(/\/$/, '') + '/api/v1'
    }

    const url = new URL(`${normalizedBase}${endpoint}`)

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value))
        }
      })
    }
    
    return url.toString()
  }

  async request<T>(
    endpoint: string,
    options: Partial<RequestOptions> = {}
  ): Promise<T> {
    const { params, ...fetchOptions } = options
    const url = this.buildUrl(endpoint, params)
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> | undefined)
    }
    
    // Allow overriding Content-Type if specified in options
    if (options.headers && isObject(options.headers) && 'Content-Type' in options.headers) {
      const contentType = (options.headers as Record<string, unknown>)['Content-Type']
      if (typeof contentType === 'string') {
        headers['Content-Type'] = contentType
      }
    }

    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`
    }

    // Check cache for GET requests
    const cacheKey = this.getCacheKey(url, fetchOptions.method)
    if (fetchOptions.method === 'GET' || !fetchOptions.method) {
      const cached = this.getFromCache(cacheKey)
      if (cached) {
        return cached as T
      }

      // Check for pending request
      const pending = this.pendingRequests.get(cacheKey)
      if (pending) {
        return pending as Promise<T>
      }
    }

    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 15000) // Reduced to 15 seconds

      const requestPromise = fetch(url, {
        ...fetchOptions,
        headers,
        signal: controller.signal,
        cache: 'no-cache' as RequestCache
      })

      // Store pending request
      if (fetchOptions.method === 'GET' || !fetchOptions.method) {
        this.pendingRequests.set(cacheKey, requestPromise)
      }

      const response = await requestPromise

      clearTimeout(timeoutId)

      // Remove from pending requests
      this.pendingRequests.delete(cacheKey)

      if (!response.ok) {
        let errorData: ApiErrorResponse
        try {
          const data = await response.json()
          errorData = {
            error: data.error || 'Unknown error',
            message: data.message || `HTTP ${response.status}: ${response.statusText}`,
            details: data.details,
            timestamp: data.timestamp || new Date().toISOString(),
            status_code: response.status,
            request_id: data.request_id,
            trace_id: data.trace_id
          }
        } catch {
          errorData = {
            error: 'network_error',
            message: `HTTP ${response.status}: ${response.statusText}`,
            timestamp: new Date().toISOString(),
            status_code: response.status
          }
        }
        throw new ApiError(response.status, errorData)
      }

      const contentType = response.headers.get('content-type')
      let result: T

      if (contentType && contentType.includes('application/json')) {
        result = await response.json()
      } else if (contentType && contentType.includes('text/plain')) {
        const textContent = await response.text()
        result = textContent as unknown as T
      } else if (contentType && (contentType.includes('application/octet-stream') || contentType.includes('application/pdf'))) {
        const blobContent = await response.blob()
        result = blobContent as unknown as T
      } else {
        const textContent = await response.text()
        result = textContent as unknown as T
      }

      // Cache GET requests
      if ((fetchOptions.method === 'GET' || !fetchOptions.method) && response.ok) {
        this.setCache(cacheKey, result, this.getCacheTTL(url))
      }

      return result
    } catch (error) {
      // Clean up pending request
      this.pendingRequests.delete(cacheKey)

      if (error instanceof ApiError) {
        throw error
      }

      // Handle network errors with proper typing
      if (error instanceof TypeError && error.message && String(error.message).includes('fetch')) {
        const networkError: ApiErrorResponse = {
          error: 'network_error',
          message: 'Não foi possível conectar ao servidor. Verifique sua conexão com a internet.',
          timestamp: new Date().toISOString(),
          status_code: 0
        }
        throw new ApiError(0, networkError)
      }

      // Handle timeout errors
      if (error instanceof DOMException && error.name === 'AbortError') {
        const timeoutError: ApiErrorResponse = {
          error: 'timeout_error',
          message: 'A requisição demorou muito para responder. Tente novamente.',
          timestamp: new Date().toISOString(),
          status_code: 408
        }
        throw new ApiError(408, timeoutError)
      }

      // Handle other errors
      const genericError: ApiErrorResponse = {
        error: 'unknown_error',
        message: 'Erro de conexão. Verifique sua internet e tente novamente.',
        timestamp: new Date().toISOString(),
        status_code: 500
      }
      throw new ApiError(500, genericError)
    }
  }

  // Auth endpoints with enhanced type safety
  auth = {
    login: (credentials: { email: string; password: string }) => {
      const formData = new URLSearchParams()
      formData.append('username', credentials.email)
      formData.append('password', credentials.password)

      return this.request<AuthTokens & { user: User }>('/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: formData.toString()
      })
    },

    refresh: (refreshToken: string) =>
      this.request<AuthTokens & { user: User }>('/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refreshToken })
      }),

    me: () =>
      this.request<User>('/auth/me'),

    logout: () =>
      this.request<void>('/auth/logout', { method: 'POST' })
  } as const

  // Patients endpoints with proper typing
  patients = {
    list: (params?: PatientQueryParams) =>
      this.request<PaginatedResponse<Patient>>('/patients', { params: params as Record<string, string | number | boolean> }),

    get: (id: string) =>
      this.request<Patient>(`/patients/${id}`),

    create: (patient: CreatePatientRequest) =>
      this.request<Patient>('/patients', {
        method: 'POST',
        body: JSON.stringify(patient)
      }),

    update: (id: string, patient: UpdatePatientRequest) =>
      this.request<Patient>(`/patients/${id}`, {
        method: 'PUT',
        body: JSON.stringify(patient)
      }),

    delete: (id: string) =>
      this.request<void>(`/patients/${id}`, { method: 'DELETE' }),

    // Deprecated alias for backward compatibility
    deletePatient: (id: string) =>
      this.request<void>(`/patients/${id}`, { method: 'DELETE' }),

    timeline: (id: string) =>
      this.request<ActivityItem[]>(`/patients/${id}/timeline`),

    activate: (id: string) =>
      this.request<void>(`/patients/${id}/activate`, { method: 'POST' }),

    deactivate: (id: string) =>
      this.request<void>(`/patients/${id}/deactivate`, { method: 'POST' })
  } as const

  // Messages endpoints with proper typing
  messages = {
    list: (params?: MessageQueryParams) =>
      this.request<PaginatedResponse<Message>>('/messages', { params: params as Record<string, string | number | boolean> }),

    send: (message: SendMessageRequest) =>
      this.request<Message>('/messages/send', {
        method: 'POST',
        body: JSON.stringify(message)
      }),

    sendBulk: (data: BulkMessageRequest) =>
      this.request<{ batch_id: string; message_ids: string[] }>('/messages/bulk', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    retry: (id: string) =>
      this.request<Message>(`/messages/${id}/retry`, { method: 'POST' }),

    cancel: (id: string) =>
      this.request<void>(`/messages/${id}/cancel`, { method: 'POST' })
  } as const

  // Flow endpoints with proper typing
  flows = {
    list: (params?: { patient_id?: string; status?: string }) =>
      this.request<PaginatedResponse<Flow>>('/flows', params ? { params } : {}),

    start: (data: StartFlowRequest) =>
      this.request<Flow>('/flows/start', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    getState: (patientId: string) =>
      this.request<Flow>(`/flows/${patientId}/state`),

    advance: (patientId: string, forceDay?: number) =>
      this.request<Flow>(`/flows/${patientId}/advance`, {
        method: 'POST',
        body: JSON.stringify(forceDay !== undefined ? { force_day: forceDay } : {})
      }),

    pause: (patientId: string) =>
      this.request<Flow>(`/flows/${patientId}/pause`, { method: 'POST' }),

    resume: (patientId: string) =>
      this.request<Flow>(`/flows/${patientId}/resume`, { method: 'POST' }),

    processResponse: (patientId: string, message: Message) =>
      this.request<void>(`/flows/${patientId}/response`, {
        method: 'POST',
        body: JSON.stringify(message)
      }),

    getAnalytics: () =>
      this.request<FlowMetrics>('/flows/analytics'),

    // Template management methods
    getTemplates: () =>
      this.request<PaginatedResponse<FlowTemplate>>('/flows/templates'),

    createTemplate: (template: CreateFlowTemplateRequest) =>
      this.request<FlowTemplate>('/flows/templates', {
        method: 'POST',
        body: JSON.stringify(template)
      }),

    updateTemplate: (id: string, template: UpdateFlowTemplateRequest) =>
      this.request<FlowTemplate>(`/flows/templates/${id}`, {
        method: 'PUT',
        body: JSON.stringify(template)
      }),

    deleteTemplate: (id: string) =>
      this.request<void>(`/flows/templates/${id}`, { method: 'DELETE' }),

    cloneTemplate: (id: string, name?: string) =>
      this.request<FlowTemplate>(`/flows/templates/${id}/clone`, {
        method: 'POST',
        body: JSON.stringify(name ? { name } : {})
      })
  } as const

  // Analytics endpoints with proper typing
  analytics = {
    dashboard: () =>
      this.request<DashboardAnalytics>('/analytics/dashboard'),

    patients: (params?: { start_date?: string; end_date?: string }) =>
      this.request<EngagementMetrics>('/analytics/patients', params ? { params } : {}),

    engagement: (params?: { start_date?: string; end_date?: string }) =>
      this.request<EngagementMetrics>('/analytics/engagement', params ? { params } : {})
  } as const

  // Alerts endpoints with proper typing
  alerts = {
    list: (params?: AlertQueryParams) =>
      this.request<PaginatedResponse<Alert>>('/alerts', { params: params as Record<string, string | number | boolean> }),

    create: (alert: CreateAlertRequest) =>
      this.request<Alert>('/alerts', {
        method: 'POST',
        body: JSON.stringify(alert)
      }),

    get: (id: string) =>
      this.request<Alert>(`/alerts/${id}`),

    acknowledge: (id: string) =>
      this.request<Alert>(`/alerts/${id}/acknowledge`, { method: 'POST' }),

    resolve: (id: string) =>
      this.request<Alert>(`/alerts/${id}/resolve`, { method: 'POST' }),

    delete: (id: string) =>
      this.request<void>(`/alerts/${id}`, { method: 'DELETE' })
  } as const

  // Reports endpoints with proper typing
  reports = {
    list: (params?: ReportQueryParams) =>
      this.request<PaginatedResponse<Report>>('/reports', { params: params as Record<string, string | number | boolean> }),

    generate: (data: GenerateReportRequest) =>
      this.request<Report>('/reports/generate', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    get: (id: string) =>
      this.request<Report>(`/reports/${id}`),

    download: (id: string) =>
      this.request<{ content: string; contentType: string; filename: string }>(`/reports/${id}/download`),

    delete: (id: string) =>
      this.request<void>(`/reports/${id}`, { method: 'DELETE' }),

    preview: (data: GenerateReportRequest) =>
      this.request<{ preview: string; estimated_size: number }>('/reports/preview', {
        method: 'POST',
        body: JSON.stringify(data)
      })
  } as const

  // Legacy quiz endpoints - maintained for backward compatibility
  // Note: Quiz types are defined in the API types module
  quiz = {
    templates: () =>
      this.request<{ templates: unknown[] }>('/quiz/templates'),

    start: (patientId: string, templateId: string) =>
      this.request<unknown>('/quiz/sessions', {
        method: 'POST',
        body: JSON.stringify({ patient_id: patientId, template_id: templateId })
      }),

    getSession: (sessionId: string) =>
      this.request<unknown>(`/quiz/sessions/${sessionId}`),

    submitResponse: (sessionId: string, responses: unknown) =>
      this.request<void>(`/quiz/sessions/${sessionId}/submit`, {
        method: 'POST',
        body: JSON.stringify({ responses })
      }),

    sessions: (params?: { patient_id?: string; status?: string }) =>
      this.request<PaginatedResponse<unknown>>('/quiz/sessions', params ? { params } : {})
  } as const

  // Legacy alias for backward compatibility
  quizzes = this.quiz
  
  // System endpoints with proper typing
  system = {
    health: () =>
      this.request<SystemHealth>('/system/health'),

    metrics: () =>
      this.request<PerformanceMetric[]>('/system/metrics'),

    notifications: () =>
      this.request<Notification[]>('/notifications')
  } as const

  // AI endpoints with proper typing
  ai = {
    chat: (message: string, context?: Record<string, unknown>) =>
      this.request<{ response: string; confidence: number }>('/ai/chat', {
        method: 'POST',
        body: JSON.stringify({ message, context })
      }),

    analyze: (data: unknown, analysisType: string) =>
      this.request<AIInsight>('/ai/analyze', {
        method: 'POST',
        body: JSON.stringify({ data, analysis_type: analysisType })
      }),

    sentiment: (text: string) =>
      this.request<SentimentAnalysis>('/ai/sentiment', {
        method: 'POST',
        body: JSON.stringify({ text })
      }),

    insights: (patientId: string, timeframe?: string) =>
      this.request<AIInsight[]>(`/ai/insights/${patientId}`, timeframe ? {
        params: { timeframe }
      } : {}),

    recommendations: (patientId: string) =>
      this.request<AIInsight[]>(`/ai/recommendations/${patientId}`)
  } as const
}

export const apiClient = new ApiClient(API_BASE_URL)
