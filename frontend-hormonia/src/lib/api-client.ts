/// <reference types="vite/client" />

import { API_BASE_URL } from '../config'
import { transformPaginationResponse, transformFlowListResponse, transformReportDownload } from './response-transformers'
import { isMockApiEnabled } from '../config/mock.config'
import { mockApiHandler } from './mock-api-handler'
import { createLogger } from './logger'
import type {
  PaginatedResponse,
  Patient,
  PatientListResponse,
  TimelineEvent,
  Message,
  MessageListResponse,
  SendMessageRequest,
  SendMessageResponse,
  Flow,
  FlowState,
  FlowTemplate,
  Alert,
  CreateAlertRequest,
  Report,
  GenerateReportRequest,
  QuizTemplate,
  QuizTemplateListResponse,
  QuizSession,
  QuizSessionListResponse,
  MonthlyQuizLink,
  CreateQuizLinkRequest,
  BulkCreateQuizLinkRequest,
  QuizLinkStatus,
  MonthlyQuizStats,
  AdminUser,
  UserActivity,
  CreateUserRequest,
  UpdateUserRequest,
  ResetPasswordResponse,
  AIChatResponse,
  AIInsights,
  AIRecommendations,
  AuthMeResponse,
  LogoutResponse,
  DashboardAnalytics,
  PatientAnalytics,
  EngagementAnalytics,
} from '../types/api-responses'

const logger = createLogger('ApiClient')

// Use a default URL in case config hasn't loaded yet
const getApiUrl = () => {
  return API_BASE_URL || import.meta.env['VITE_API_URL'] || 'http://localhost:8000'
}

export interface ApiResponse<T> {
  data: T
  message?: string
  timestamp: string
}

export { PaginatedResponse }

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown,
    message?: string
  ) {
    super(message || `API Error: ${status}`)
    this.name = 'ApiError'
  }
}

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean>
}

class ApiClient {
  private baseURL: string
  private authToken: string | null = null
  private initialized: boolean = false

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  /**
   * Set base URL for API requests (deferred initialization)
   * @param url - The new base URL
   */
  setBaseURL(url: string) {
    if (!url) {
      logger.warn('Attempted to set empty base URL')
      return
    }
    logger.log('Setting base URL:', url)
    this.baseURL = url
    this.initialized = true
  }

  /**
   * Get current base URL
   */
  getBaseURL(): string {
    return this.baseURL
  }

  /**
   * Check if client is initialized with valid config
   */
  isInitialized(): boolean {
    return this.initialized
  }

  setAuthToken(token: string | null) {
    console.log('[ApiClient] Setting auth token:', {
      hasToken: !!token,
      tokenLength: token?.length,
      tokenPreview: token ? token.substring(0, 20) + '...' : null
    })
    this.authToken = token
  }

  setSupabaseToken(session: any) {
    if (session?.access_token) {
      this.setAuthToken(session.access_token)
    }
  }

  private buildUrl(endpoint: string, params?: Record<string, string | number | boolean>): string {
    // Warn if using uninitialized client
    if (!this.initialized) {
      logger.warn('Making request before initialization. Using fallback URL:', this.baseURL)
    }
    const url = new URL(`${this.baseURL}${endpoint}`)

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value))
        }
      })
    }

    return url.toString()
  }

  private _shouldRetry(error: any, attempt: number): boolean {
    // Don't retry on last attempt
    if (attempt >= 3) return false

    // Retry on network errors
    if (error instanceof TypeError) return true

    // Retry on timeout
    if (error instanceof DOMException && error.name === 'AbortError') return true

    // Retry on server errors and rate limits
    if (error instanceof ApiError) {
      return [408, 429, 500, 502, 503, 504].includes(error.status)
    }

    return false
  }

  private async _sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    // Use mock API if enabled
    if (isMockApiEnabled()) {
      logger.log('Using mock API for:', endpoint)
      const { params, ...fetchOptions } = options
      const url = this.buildUrl(endpoint, params)
      return mockApiHandler.handleRequest<T>(url, fetchOptions)
    }

    const maxAttempts = 3
    const baseDelay = 1000 // 1 second

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        const { params, ...fetchOptions } = options
        const url = this.buildUrl(endpoint, params)

        // Check if body is FormData to avoid setting Content-Type header
        const isFormData = fetchOptions.body instanceof FormData

        const headers: Record<string, string> = {
          ...(options.headers as Record<string, string> | undefined)
        }

        // Only set Content-Type if not FormData (browser will set correct multipart boundary)
        if (!isFormData) {
          headers['Content-Type'] = 'application/json'
        }

        // Allow overriding Content-Type if specified in options (and not FormData)
        if (!isFormData && options.headers && 'Content-Type' in options.headers) {
          headers['Content-Type'] = (options.headers as any)['Content-Type']
        }

        if (this.authToken) {
          headers['Authorization'] = `Bearer ${this.authToken}`
          console.log('[ApiClient] Adding Authorization header to request:', {
            endpoint,
            method: fetchOptions.method || 'GET',
            hasToken: !!this.authToken
          })
        } else {
          console.log('[ApiClient] No auth token available for request:', {
            endpoint,
            method: fetchOptions.method || 'GET'
          })
        }

        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 second timeout

        const response = await fetch(url, {
          ...fetchOptions,
          headers,
          signal: controller.signal
        })

        clearTimeout(timeoutId)

        if (!response.ok) {
          let errorData: any = {}
          try {
            errorData = await response.json()
          } catch {
            errorData = { message: `HTTP ${response.status}: ${response.statusText}` }
          }
          console.error('[ApiClient] Request failed:', {
            endpoint,
            status: response.status,
            statusText: response.statusText,
            error: errorData
          })
          throw new ApiError(response.status, errorData, errorData.message)
        }

        console.log('[ApiClient] Request successful:', {
          endpoint,
          status: response.status,
          contentType: response.headers.get('content-type')
        })

        const contentType = response.headers.get('content-type')
        const contentLength = response.headers.get('content-length')

        if (response.status === 204 || response.status === 205 || response.status === 304 || (!contentType && (!contentLength || contentLength === '0'))) {
          return undefined as T
        }

        if (contentType && contentType.includes('application/json')) {
          return await response.json()
        }

        if (contentType && contentType.includes('text/plain')) {
          return (await response.text()) as unknown as T
        }

        return response as unknown as T

      } catch (error) {
        // If this is not retryable or last attempt, throw immediately
        if (!this._shouldRetry(error, attempt)) {
          if (error instanceof ApiError) {
            throw error
          }

          // Handle network errors
          if (error instanceof TypeError && 'message' in error && String(error.message).includes('fetch')) {
            throw new ApiError(0, { message: 'Falha ao conectar ao servidor' }, 'Não foi possível conectar ao servidor. Verifique sua conexão com a internet.')
          }

          // Handle timeout errors
          if (error instanceof DOMException && error.name === 'AbortError') {
            throw new ApiError(408, { message: 'Timeout' }, 'A requisição demorou muito para responder. Tente novamente.')
          }

          // Handle other errors
          throw new ApiError(500, { message: 'Erro de rede' }, 'Erro de conexão. Verifique sua internet e tente novamente.')
        }

        // Retry with exponential backoff
        const delay = baseDelay * Math.pow(2, attempt - 1)
        logger.log(`Tentativa ${attempt}/${maxAttempts} falhou. Tentando novamente em ${delay}ms...`)
        await this._sleep(delay)
      }
    }

    // This should never be reached but TypeScript requires it
    throw new ApiError(500, { message: 'Erro de rede' }, 'Erro após múltiplas tentativas.')
  }

  // Convenience methods that wrap the request() method
  async get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  async post<T>(endpoint: string, body?: any, options?: RequestOptions): Promise<T> {
    const requestOptions: RequestOptions = {
      method: 'POST',
      ...options
    }
    if (body !== undefined) {
      // Don't stringify FormData
      requestOptions.body = body instanceof FormData ? body : JSON.stringify(body)
    }
    return this.request<T>(endpoint, requestOptions);
  }

  async put<T>(endpoint: string, body?: any, options?: RequestOptions): Promise<T> {
    const requestOptions: RequestOptions = {
      method: 'PUT',
      ...options
    }
    if (body !== undefined) {
      // Don't stringify FormData
      requestOptions.body = body instanceof FormData ? body : JSON.stringify(body)
    }
    return this.request<T>(endpoint, requestOptions);
  }

  async delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }

  // Auth endpoints
  auth = {
    login: async (_credentials: { email: string; password: string }) => {
      throw new ApiError(410, { message: 'Local authentication is disabled. Use Supabase Auth on the client.' }, 'Local authentication is disabled. Use Supabase Auth on the client.')
    },

    refresh: async (_refreshToken: string) => {
      throw new ApiError(410, { message: 'Local token refresh is disabled. Supabase handles session refresh automatically.' }, 'Local token refresh is disabled. Supabase handles session refresh automatically.')
    },

    me: async () => {
      console.log('[ApiClient] Calling /api/v1/auth/me with token:', {
        hasToken: !!this.authToken,
        baseURL: this.baseURL
      })

      // FastAPI returns UserResponse directly (not wrapped)
      const user = await this.request<{
        id: string;
        email: string;
        full_name: string;
        role: string;
        is_active: boolean;
        // Optional medico-specific fields
        crm?: string;
        nome?: string;
        updated_at?: string;
        last_login?: string;
        login_count?: number;
        two_factor_enabled?: boolean;
        especialidade?: string;
        conselho_regional?: string;
        pacientes_atribuidos?: any[];
      }>('/api/v1/auth/me');

      console.log('[ApiClient] Received user from /api/v1/auth/me:', {
        id: user.id,
        email: user.email,
        role: user.role,
        is_active: user.is_active
      })

      // Return in snake_case format to match User type
      return {
        data: {
          id: user['id'],
          email: user['email'],
          full_name: user['full_name'],
          role: user['role'],
          is_active: user.is_active,
          permissions: [],
          created_at: new Date().toISOString(),
          // Include optional medico-specific fields if present
          crm: user['crm'],
          nome: user['nome'],
          updated_at: user['updated_at'],
          last_login: user['last_login'],
          login_count: user['login_count'],
          two_factor_enabled: user['two_factor_enabled'],
          especialidade: user['especialidade'],
          conselho_regional: user['conselho_regional'],
          pacientes_atribuidos: user['pacientes_atribuidos']
        }
      };
    },

    logout: async () => {
      // FastAPI returns: { "message": "Successfully logged out" }
      const response = await this.request<{ message: string }>('/api/v1/auth/logout', { method: 'POST' });

      // Transform to match frontend expectations
      return {
        message: response.message
      };
    }
  }

  // Patients endpoints
  patients = {
    list: async (params: { page?: number; size?: number; search?: string; status?: string; treatment_type?: string }) => {
      const response = await this.request<PatientListResponse>('/api/v1/patients', { params });
      return transformPaginationResponse<Patient>(response, 'patients');
    },

    get: (id: string) =>
      this.request<Patient>(`/api/v1/patients/${id}`),

    create: (patient: Partial<Patient>) =>
      this.request<Patient>('/api/v1/patients', {
        method: 'POST',
        body: JSON.stringify(patient)
      }),

    update: (id: string, patient: Partial<Patient>) =>
      this.request<Patient>(`/api/v1/patients/${id}`, {
        method: 'PUT',
        body: JSON.stringify(patient)
      }),

    deletePatient: (id: string) =>
      this.request<void>(`/api/v1/patients/${id}`, { method: 'DELETE' }),

    timeline: (id: string) =>
      this.request<{ events: TimelineEvent[]; total?: number }>(`/api/v1/patients/${id}/timeline`),

    activate: (id: string) =>
      this.request<void>(`/api/v1/patients/${id}/activate`, { method: 'POST' }),

    deactivate: (id: string) =>
      this.request<void>(`/api/v1/patients/${id}/deactivate`, { method: 'POST' })
  }

  // Messages endpoints
  messages = {
    list: async (params: { patient_id?: string; page?: number; size?: number }) => {
      const response = await this.request<MessageListResponse>('/api/v1/messages', { params });
      return transformPaginationResponse<Message>(response, 'messages');
    },

    send: (message: SendMessageRequest) =>
      this.request<SendMessageResponse>('/api/v1/messages/send', {
        method: 'POST',
        body: JSON.stringify(message)
      }),

    retry: (id: string) =>
      this.request<Message>(`/api/v1/messages/${id}/retry`, { method: 'POST' })
  }

  // Flow endpoints
  flows = {
    list: async (params: { patient_id?: string; status?: string }) => {
      const response = await this.request<any[]>('/api/v1/flows', { params });
      return transformFlowListResponse(response);
    },

    start: (patientId: string, flowType: string) =>
      this.request<any>('/api/v1/flows/start', {
        method: 'POST',
        body: JSON.stringify({ patient_id: patientId, flow_type: flowType })
      }),

    getState: (patientId: string) =>
      this.request<any>(`/api/v1/flows/${patientId}/state`),

    advance: (patientId: string, forceDay?: number) =>
      this.request<any>(`/api/v1/flows/${patientId}/advance`, {
        method: 'POST',
        body: JSON.stringify({ force_day: forceDay })
      }),

    pause: (patientId: string) =>
      this.request<any>(`/api/v1/flows/${patientId}/pause`, { method: 'POST' }),

    resume: (patientId: string) =>
      this.request<any>(`/api/v1/flows/${patientId}/resume`, { method: 'POST' }),

    processResponse: (patientId: string, responseText: string, responseMetadata?: any) =>
      this.request<any>(`/api/v1/flows/${patientId}/response`, {
        method: 'POST',
        body: JSON.stringify({
          response_text: responseText,
          response_metadata: responseMetadata
        })
      }),

    // Template management
    getTemplates: () =>
      this.request<any[]>('/api/v1/flows/templates'),

    createTemplate: (template: any) =>
      this.request<any>('/api/v1/flows/templates', {
        method: 'POST',
        body: JSON.stringify(template)
      }),

    updateTemplate: (templateId: string, template: any) =>
      this.request<any>(`/api/v1/flows/templates/${templateId}`, {
        method: 'PUT',
        body: JSON.stringify(template)
      }),

    deleteTemplate: (templateId: string) =>
      this.request<void>(`/api/v1/flows/templates/${templateId}`, { method: 'DELETE' }),

    getAnalytics: () =>
      this.request<any>('/api/v1/flows/analytics/flow-performance')
  }

  // Analytics endpoints
  analytics = {
    dashboard: () =>
      this.request<any>('/api/v1/analytics/dashboard'),

    patients: (params: { start_date?: string; end_date?: string }) =>
      this.request<any>('/api/v1/analytics/patients', { params }),

    engagement: (params: { start_date?: string; end_date?: string }) =>
      this.request<any>('/api/v1/analytics/engagement', { params })
  }

  // Alerts endpoints
  alerts = {
    list: (params: { page?: number; size?: number; severity?: string; acknowledged?: boolean }) =>
      this.request<PaginatedResponse<any>>('/api/v1/alerts', { params }),

    create: (alert: { patient_id?: string; type: string; severity: string; title: string; message: string; metadata?: any }) =>
      this.request<any>('/api/v1/alerts', {
        method: 'POST',
        body: JSON.stringify(alert)
      }),

    acknowledge: (id: string) =>
      this.request<void>(`/api/v1/alerts/${id}/acknowledge`, { method: 'POST' }),

    resolve: (id: string) =>
      this.request<void>(`/api/v1/alerts/${id}/resolve`, { method: 'POST' })
  }

  // Reports endpoints
  reports = {
    list: (params: { page?: number; size?: number }) =>
      this.request<PaginatedResponse<any>>('/api/v1/reports', { params }),

    generate: (patientId: string, type: string, config: any) =>
      this.request<any>('/api/v1/reports/generate', {
        method: 'POST',
        body: JSON.stringify({ patient_id: patientId, type, config })
      }),

    get: (id: string) =>
      this.request<any>(`/api/v1/reports/${id}`),

    preview: (id: string) =>
      this.request<any>(`/api/v1/reports/${id}/preview`),

    download: async (id: string) => {
      const url = `${this.baseURL}/api/v1/reports/${id}/download`;
      const response = await fetch(url, {
        headers: {
          ...this.authToken ? { 'Authorization': `Bearer ${this.authToken}` } : {}
        }
      });

      if (!response.ok) {
        throw new ApiError(response.status, await response.json());
      }

      return transformReportDownload(response);
    }
  }

  // Quiz endpoints
  quiz = {
    templates: () =>
      this.request<{ items: any[]; total: number; page: number; size: number }>('/api/v1/quiz/templates'),

    start: (patientId: string, quizTemplateId: string) =>
      this.request<any>('/api/v1/quiz/sessions', {
        method: 'POST',
        body: JSON.stringify({ patient_id: patientId, quiz_template_id: quizTemplateId })
      }),

    getSession: (sessionId: string) =>
      this.request<any>(`/api/v1/quiz/sessions/${sessionId}`),

    submitResponse: (sessionId: string, responses: any) =>
      this.request<void>(`/api/v1/quiz/sessions/${sessionId}/submit`, {
        method: 'POST',
        body: JSON.stringify({ responses })
      }),

    sessions: (params: { patient_id?: string; status?: string }) =>
      this.request<{ items: any[]; total: number; page: number; size: number }>('/api/v1/quiz/sessions', { params })
  }

  // Quizzes endpoints (alias for quiz for backward compatibility)
  // All methods delegate to the quiz namespace to avoid duplication
  get quizzes() {
    return {
      // Template management - delegates to avoid duplication
      list: () => this.quiz.templates(),
      listTemplates: () => this.quiz.templates(),
      create: (quiz: any) => this.request<any>('/api/v1/quiz/templates', {
        method: 'POST',
        body: JSON.stringify(quiz)
      }),
      createTemplate: (template: any) => this.request<any>('/api/v1/quiz/templates', {
        method: 'POST',
        body: JSON.stringify(template)
      }),
      update: (id: string, quiz: any) => this.request<any>(`/api/v1/quiz/templates/${id}`, {
        method: 'PUT',
        body: JSON.stringify(quiz)
      }),
      delete: (id: string) => this.request<void>(`/api/v1/quiz/templates/${id}`, { method: 'DELETE' }),
      deleteTemplate: (id: string) => this.request<void>(`/api/v1/quiz/templates/${id}`, { method: 'DELETE' }),
      getTemplateAnalytics: (templateId: string) => this.request<any>(`/api/v1/quiz/templates/${templateId}/analytics`),

      // Session management - delegates to quiz namespace
      start: this.quiz.start.bind(this.quiz),
      getSession: this.quiz.getSession.bind(this.quiz),
      submitResponse: this.quiz.submitResponse.bind(this.quiz),
      sessions: this.quiz.sessions.bind(this.quiz),
      templates: this.quiz.templates.bind(this.quiz)
    }
  }
  
  // Notifications endpoints (available under auth route)
  notifications = {
    list: () =>
      this.request<any>('/api/v1/auth/notifications')
  }

  // Admin User Management endpoints
  adminUsers = {
    list: (params: { page?: number; size?: number; search?: string; role?: string; is_active?: boolean }) =>
      this.request<PaginatedResponse<any>>('/api/v1/admin/users', { params }),

    get: (id: string) =>
      this.request<any>(`/api/v1/admin/users/${id}`),

    create: (user: any) =>
      this.request<any>('/api/v1/admin/users', {
        method: 'POST',
        body: JSON.stringify(user)
      }),

    update: (id: string, user: any) =>
      this.request<any>(`/api/v1/admin/users/${id}`, {
        method: 'PUT',
        body: JSON.stringify(user)
      }),

    delete: (id: string) =>
      this.request<void>(`/api/v1/admin/users/${id}`, { method: 'DELETE' }),

    activate: (id: string) =>
      this.request<void>(`/api/v1/admin/users/${id}/activate`, { method: 'POST' }),

    deactivate: (id: string) =>
      this.request<void>(`/api/v1/admin/users/${id}/deactivate`, { method: 'POST' }),

    updatePermissions: (id: string, permissions: string[]) =>
      this.request<void>(`/api/v1/admin/users/${id}/permissions`, {
        method: 'PUT',
        body: JSON.stringify({ permissions })
      }),

    updateRole: (id: string, role: string) =>
      this.request<void>(`/api/v1/admin/users/${id}/role`, {
        method: 'PUT',
        body: JSON.stringify({ role })
      }),

    getActivity: (id: string, params?: { page?: number; size?: number }) =>
      this.request<PaginatedResponse<any>>(`/api/v1/admin/users/${id}/activity`, params ? { params } : {}),

    resetPassword: (id: string) =>
      this.request<{ temporary_password: string }>(`/api/v1/admin/users/${id}/reset-password`, { method: 'POST' }),

    unlock: (id: string) =>
      this.request<void>(`/api/v1/admin/users/${id}/unlock`, { method: 'POST' }),

    enable2FA: (id: string) =>
      this.request<void>(`/api/v1/admin/users/${id}/2fa/enable`, { method: 'POST' }),

    disable2FA: (id: string) =>
      this.request<void>(`/api/v1/admin/users/${id}/2fa/disable`, { method: 'POST' })
  }

  // AI endpoints
  ai = {
    chat: (message: string, context?: any) =>
      this.request<any>('/api/v1/ai/chat', {
        method: 'POST',
        body: JSON.stringify({ message, context })
      }),

    analyze: (data: any, analysisType: string) =>
      this.request<any>('/api/v1/ai/analyze', {
        method: 'POST',
        body: JSON.stringify({ data, analysis_type: analysisType })
      }),

    generateResponse: (patientId: string, messageHistory: any[], intent?: string) =>
      this.request<any>('/api/v1/ai/generate-response', {
        method: 'POST',
        body: JSON.stringify({ patient_id: patientId, message_history: messageHistory, intent })
      }),

    sentiment: (text: string) =>
      this.request<any>('/api/v1/ai/sentiment', {
        method: 'POST',
        body: JSON.stringify({ text })
      }),

    insights: (patientId: string, timeframe?: string) =>
      this.request<any>(`/api/v1/ai/insights/${patientId}`, timeframe ? {
        params: { timeframe }
      } : {}),

    recommendations: (patientId: string) =>
      this.request<any>(`/api/v1/ai/recommendations/${patientId}`)
  }

  // Monthly Quiz Management endpoints
  monthlyQuiz = {
    // Create quiz link for a single patient
    createLink: (data: {
      patient_id: string
      quiz_template_id: string
      delivery_method?: string
      expiry_hours?: number
      custom_message?: string
    }) =>
      this.request<any>('/api/v1/monthly-quiz/links', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    // Create quiz links for multiple patients (bulk)
    bulkCreate: (data: {
      patient_ids: string[]
      quiz_template_id: string
      delivery_method?: string
      expiry_hours?: number
      custom_message?: string
    }) =>
      this.request<any>('/api/v1/monthly-quiz/links/bulk', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    // Get quiz link status for a specific session
    getStatus: (sessionId: string) =>
      this.request<any>(`/api/v1/monthly-quiz/links/${sessionId}/status`),

    // Get quiz link status for a patient
    getPatientStatus: (patientId: string) =>
      this.request<any>(`/api/v1/monthly-quiz/patients/${patientId}/status`),

    // Get quiz link history for a patient
    getHistory: (patientId: string) =>
      this.request<any>(`/api/v1/monthly-quiz/patients/${patientId}/history`),

    // Get quiz statistics (dashboard)
    getStats: (params?: { start_date?: string; end_date?: string }) =>
      this.request<{
        // New field names
        total_sent: number
        total_completed: number
        total_expired: number
        total_active: number
        average_score: number
        // Old field names (backward compatibility)
        total_links_created: number
        completed_quizzes: number
        expired_links: number
        active_links: number
        // Calculated metrics
        completion_rate: number
        expiration_rate: number
      }>('/api/v1/monthly-quiz/stats/dashboard', params ? { params } : {}),

    // Get active quiz links
    getActiveLinks: () =>
      this.request<any[]>('/api/v1/monthly-quiz/links/active'),

    // Resend quiz link
    resend: (sessionId: string, method: 'whatsapp' | 'email' | 'sms' = 'whatsapp') =>
      this.request<any>(`/api/v1/monthly-quiz/links/${sessionId}/resend`, {
        method: 'POST',
        params: { delivery_method: method }
      }),

    // Cancel quiz link
    cancel: (sessionId: string) =>
      this.request<any>(`/api/v1/monthly-quiz/links/${sessionId}/cancel`, {
        method: 'POST'
      })
  }
}

export const apiClient = new ApiClient(getApiUrl())
