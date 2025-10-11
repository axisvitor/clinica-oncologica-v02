/// <reference types="vite/client" />

import { API_BASE_URL } from '../config'
import { transformPaginationResponse, transformFlowListResponse, transformReportDownload } from './response-transformers'
import { isMockApiEnabled } from '../config/mock.config'
import { mockApiHandler } from './mock-api-handler'
import { createLogger } from './logger'
import { environment } from './environment'
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
  return API_BASE_URL || import.meta.env['VITE_API_URL'] || 'https://clinica-oncologica-v02-production.up.railway.app'
}

export interface ApiResponse<T> {
  data: T
  message?: string
  timestamp: string
}

export { PaginatedResponse }

export class ApiError extends Error {
  public userFriendlyMessage: string
  public retryable: boolean
  public timestamp: string

  constructor(
    public status: number,
    public data: unknown,
    message?: string,
    userFriendlyMessage?: string
  ) {
    super(message || `API Error: ${status}`)
    this.name = 'ApiError'
    this.userFriendlyMessage = userFriendlyMessage || this.getDefaultUserMessage(status)
    this.retryable = this.isRetryableError(status)
    this.timestamp = new Date().toISOString()
  }

  private getDefaultUserMessage(status: number): string {
    switch (status) {
      case 0:
        return 'Não foi possível conectar ao servidor. Verifique sua conexão com a internet.'
      case 400:
        return 'Os dados enviados estão incorretos. Verifique as informações e tente novamente.'
      case 401:
        return 'Sua sessão expirou. Por favor, faça login novamente.'
      case 403:
        return 'Você não tem permissão para realizar esta ação.'
      case 404:
        return 'O recurso solicitado não foi encontrado.'
      case 408:
        return 'A requisição demorou muito para responder. Tente novamente.'
      case 409:
        return 'Conflito nos dados. Verifique se outro usuário não modificou as informações.'
      case 422:
        return 'Os dados fornecidos não puderam ser processados. Verifique os campos obrigatórios.'
      case 429:
        return 'Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente novamente.'
      case 500:
        return 'Erro interno do servidor. Nossa equipe foi notificada.'
      case 502:
      case 503:
      case 504:
        return 'O servidor está temporariamente indisponível. Tente novamente em alguns minutos.'
      default:
        if (status >= 500) {
          return 'Erro no servidor. Nossa equipe foi notificada.'
        }
        if (status >= 400) {
          return 'Erro na requisição. Verifique os dados e tente novamente.'
        }
        return 'Erro inesperado. Tente novamente ou entre em contato com o suporte.'
    }
  }

  private isRetryableError(status: number): boolean {
    // Network errors (0) and server errors (5xx) are retryable
    // Rate limiting (429) and timeouts (408) are retryable
    return status === 0 || status === 408 || status === 429 || (status >= 500 && status <= 599)
  }

  toJSON() {
    return {
      name: this.name,
      message: this.message,
      userFriendlyMessage: this.userFriendlyMessage,
      status: this.status,
      data: this.data,
      retryable: this.retryable,
      timestamp: this.timestamp,
      stack: environment.isDevelopment ? this.stack : undefined
    }
  }
}

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean>
}

class ApiClient {
  private baseURL: string
  private authToken: string | null = null
  private initialized: boolean = false
  private csrfToken: string | null = null
  private csrfTokenPromise: Promise<void> | null = null // Prevent concurrent fetches

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

    // SECURITY: Block HTTP URLs in production to prevent mixed-content errors
    if (url.startsWith('http://') && typeof window !== 'undefined') {
      const isProduction = window.location.protocol === 'https:' ||
                          window.location.hostname !== 'localhost'

      if (isProduction) {
        logger.error('🚨 SECURITY: Blocked HTTP URL in production:', url)
        logger.error('   Using HTTPS instead to prevent mixed-content blocking')

        // Force HTTPS by replacing protocol
        url = url.replace('http://', 'https://')
        logger.log('   Corrected URL:', url)
      }
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
    logger.debug('[ApiClient] Setting auth token:', {
      hasToken: !!token,
      tokenLength: token?.length
    })
    this.authToken = token
  }

  /**
   * Fetch CSRF token from backend with request deduplication
   * Called on app initialization and after session creation
   *
   * PERFORMANCE: Multiple concurrent calls will share the same Promise
   * to prevent race conditions and duplicate network requests
   */
  async fetchCsrfToken(): Promise<void> {
    // If there's already a fetch in progress, return that Promise
    if (this.csrfTokenPromise) {
      logger.debug('[ApiClient] CSRF token fetch already in progress, waiting...')
      return this.csrfTokenPromise
    }

    // Create new fetch Promise and cache it
    this.csrfTokenPromise = (async () => {
      try {
        logger.debug('[ApiClient] Initiating CSRF token fetch...')
        const response = await fetch(`${this.baseURL}/api/v1/csrf-token`, {
          credentials: 'include' // Include cookies
        })

        if (response.ok) {
          const data = await response.json()
          let csrfToken = data.csrf_token
          
          // FIX: Backend returns CSRF token as array [token_id, signed_token]
          // We need the signed token (second element) for validation
          if (Array.isArray(csrfToken) && csrfToken.length >= 2) {
            csrfToken = csrfToken[1] // Use the signed token
            logger.debug('[ApiClient] CSRF token extracted from array format')
          } else if (typeof csrfToken !== 'string') {
            logger.error('[ApiClient] Unexpected CSRF token format:', typeof csrfToken, csrfToken)
            throw new Error('Invalid CSRF token format received from server')
          }
          
          // Use the token from JSON response (now fixed in backend)
          this.csrfToken = csrfToken
          
          logger.debug('[ApiClient] CSRF token fetched successfully')
        } else {
          logger.warn('[ApiClient] Failed to fetch CSRF token:', response.status)
        }
      } catch (error) {
        logger.error('[ApiClient] Error fetching CSRF token:', error)
        throw error
      } finally {
        // Clear the promise after completion (success or failure)
        // to allow future fetches
        this.csrfTokenPromise = null
      }
    })()

    return this.csrfTokenPromise
  }

  /**
   * Get current CSRF token
   */
  getCsrfToken(): string | null {
    return this.csrfToken
  }

  /**
   * Extract CSRF token from cookie (workaround for backend sync issue)
   */
  private extractCsrfTokenFromCookie(): string | null {
    if (typeof document === 'undefined') return null
    
    try {
      const cookies = document.cookie.split(';')
      const csrfCookie = cookies.find(cookie => 
        cookie.trim().startsWith('fastapi-csrf-token=')
      )
      
      if (!csrfCookie) return null
      
      const cookieValue = csrfCookie.split('=')[1]
      if (!cookieValue) return null
      
      // Decode the cookie value
      const decodedValue = decodeURIComponent(cookieValue)
      
      // Remove quotes if present
      const cleanValue = decodedValue.replace(/^"(.*)"$/, '$1')
      
      // Parse the tuple format: ('token_id', 'signed_token')
      const tupleMatch = cleanValue.match(/\('([^']+)'.*?'([^']+)'\)/)
      if (tupleMatch && tupleMatch[2]) {
        logger.debug('[ApiClient] Extracted CSRF token from cookie')
        return tupleMatch[2] // Return the signed token
      }
      
      return null
    } catch (error) {
      logger.error('[ApiClient] Error extracting CSRF token from cookie:', error)
      return null
    }
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

    // Don't retry on authentication errors
    if (error instanceof ApiError && [401, 403].includes(error.status)) {
      return false
    }

    // Don't retry on client errors (except timeout and rate limit)
    if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
      return [408, 429].includes(error.status)
    }

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
          logger.debug('[ApiClient] Request with auth', {
            endpoint,
            method: fetchOptions.method || 'GET'
          })
        }

        // SECURITY FIX: Session ID now in httpOnly cookie (sent automatically)
        // No need to manually add X-Session-ID header - cookies are automatic

        // Add CSRF token for state-changing requests (POST, PUT, DELETE)
        const method = (fetchOptions.method || 'GET').toUpperCase()
        if (['POST', 'PUT', 'DELETE'].includes(method) && this.csrfToken) {
          headers['X-CSRF-Token'] = this.csrfToken
          logger.debug('[ApiClient] Request with CSRF token', {
            endpoint,
            method
          })
        }

        const controller = new AbortController()
        const timeoutId = setTimeout(() => {
          logger.warn('[ApiClient] Request timeout, aborting...', { endpoint, method })
          controller.abort()
        }, 30000) // 30 second timeout

        const response = await fetch(url, {
          ...fetchOptions,
          headers,
          credentials: 'include',  // CRITICAL: Send cookies with every request
          signal: controller.signal
        })

        clearTimeout(timeoutId)

        if (!response.ok) {
          let errorData: any = {}
          let userFriendlyMessage: string | undefined

          try {
            errorData = await response.json()

            // Extract user-friendly message from backend response
            if (errorData.detail && typeof errorData.detail === 'string') {
              userFriendlyMessage = errorData.detail
            } else if (errorData.message && typeof errorData.message === 'string') {
              userFriendlyMessage = errorData.message
            } else if (errorData.error && typeof errorData.error === 'string') {
              userFriendlyMessage = errorData.error
            }
          } catch {
            errorData = { message: `HTTP ${response.status}: ${response.statusText}` }
          }

          // Handle 401 Unauthorized - session expired
          if (response.status === 401) {
            logger.warn('[ApiClient] Session expired (401), clearing session data')
            userFriendlyMessage = 'Sua sessão expirou. Redirecionando para login...'

            if (typeof window !== 'undefined') {
              // SECURITY: Session managed by httpOnly cookies (automatic)
              // Firebase token managed by Firebase SDK (in-memory)

              // Redirect to login page if not already there
              if (!window.location.pathname.includes('/login')) {
                setTimeout(() => {
                  window.location.href = '/login?session_expired=true'
                }, 1500) // Give time for user to see the message
              }
            }
          }

          // Handle validation errors (422)
          if (response.status === 422 && errorData.detail && Array.isArray(errorData.detail)) {
            const validationErrors = errorData.detail
              .map((err: any) => `${err.loc?.join('.') || 'Campo'}: ${err.msg}`)
              .join('; ')
            userFriendlyMessage = `Erro de validação: ${validationErrors}`
          }

          // Handle rate limiting with retry info
          if (response.status === 429) {
            const retryAfter = response.headers.get('Retry-After')
            if (retryAfter) {
              userFriendlyMessage = `Muitas tentativas. Tente novamente em ${retryAfter} segundos.`
            }
          }

          logger.error('[ApiClient] Request failed:', {
            endpoint,
            status: response.status,
            statusText: response.statusText,
            error: errorData,
            userFriendlyMessage
          })

          throw new ApiError(
            response.status,
            errorData,
            errorData.message || `HTTP ${response.status}: ${response.statusText}`,
            userFriendlyMessage
          )
        }

        logger.debug('[ApiClient] Request successful:', {
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

          // Handle network errors with better messages
          if (error instanceof TypeError && 'message' in error && String(error.message).includes('fetch')) {
            const networkError = new ApiError(
              0,
              { message: 'Network error', originalError: error.message },
              'Network connection failed',
              'Não foi possível conectar ao servidor. Verifique sua conexão com a internet e tente novamente.'
            )
            throw networkError
          }

          // Handle timeout errors
          if (error instanceof DOMException && error.name === 'AbortError') {
            const timeoutError = new ApiError(
              408,
              { message: 'Request timeout', timeout: 30000 },
              'Request timed out',
              'A requisição demorou muito para responder. Verifique sua conexão e tente novamente.'
            )
            throw timeoutError
          }

          // Handle CORS errors (common in development)
          if (error instanceof TypeError && error.message.includes('CORS')) {
            const corsError = new ApiError(
              0,
              { message: 'CORS error', originalError: error.message },
              'CORS policy violation',
              environment.isDevelopment
                ? 'Erro de CORS. Verifique se o backend está rodando na porta correta.'
                : 'Erro de conexão. Nossa equipe foi notificada.'
            )
            throw corsError
          }

          // Handle SSL/certificate errors
          if (error instanceof TypeError && (
            error.message.includes('certificate') ||
            error.message.includes('SSL') ||
            error.message.includes('TLS')
          )) {
            const sslError = new ApiError(
              0,
              { message: 'SSL/Certificate error', originalError: error.message },
              'SSL certificate error',
              'Erro de certificado de segurança. Tente novamente ou entre em contato com o suporte.'
            )
            throw sslError
          }

          // Handle other network/connection errors
          const genericError = new ApiError(
            500,
            { message: 'Unknown network error', originalError: error.message },
            'Unknown error occurred',
            'Erro de conexão inesperado. Verifique sua internet e tente novamente.'
          )
          throw genericError
        }

        // Retry with exponential backoff + jitter
        const delay = baseDelay * Math.pow(2, attempt - 1) + Math.random() * 1000
        logger.log(`Tentativa ${attempt}/${maxAttempts} falhou. Tentando novamente em ${Math.round(delay)}ms...`)
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
      throw new ApiError(410, { message: 'Local authentication is disabled. Use Firebase Auth on the client.' }, 'Local authentication is disabled. Use Firebase Auth on the client.')
    },

    refresh: async (_refreshToken: string) => {
      throw new ApiError(410, { message: 'Local token refresh is disabled. Firebase handles session refresh automatically.' }, 'Local token refresh is disabled. Firebase handles session refresh automatically.')
    },

    /**
     * Create backend session with Firebase token
     * SECURITY: Session ID stored in httpOnly cookie (automatic)
     */
    createSession: async (firebaseToken: string, deviceInfo?: Record<string, any>) => {
      // Use trailing slash to avoid 307 redirect
      const response = await this.request<{
        status: string;
        user: {
          id: string;
          email: string;
          full_name: string;
          role: string;
          is_active: boolean;
          permissions: string[];
          created_at: string;
        };
        session_id?: string; // Optional - may be in cookie only
      }>('/api/v1/session/', {
        method: 'POST',
        credentials: 'include', // CRITICAL: Send/receive cookies
        headers: {
          'Content-Type': 'application/json',
          ...(this.csrfToken ? { 'X-CSRF-Token': this.csrfToken } : {})
        },
        body: JSON.stringify({
          firebase_token: firebaseToken,
          device_info: deviceInfo || {
            user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown',
            timestamp: new Date().toISOString()
          }
        })
      });

      return response;
    },

    me: async () => {
      // SECURITY: Never log auth tokens or bearer credentials
      // Removed: console.log with token information

      // FastAPI returns UserResponse directly (not wrapped)
      const user = await this.request<{
        id: string;
        email: string;
        full_name: string;
        role: string;
        is_active: boolean;
        created_at: string;      // Required field
        permissions: string[];   // Required field
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

      // SECURITY: Never log full user profiles in production
      // Removed: console.log with user details

      // Return backend payload VERBATIM - don't override server data
      return {
        data: {
          id: user['id'],
          email: user['email'],
          full_name: user['full_name'],
          role: user['role'],
          is_active: user.is_active,
          // Required fields with fallbacks for type safety
          permissions: user['permissions'] ?? [],
          created_at: user['created_at'] ?? new Date().toISOString(),
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

    submitResponse: (sessionId: string, question_id: string, answer: string, response_metadata?: any) =>
      this.request<any>(`/api/v1/quiz/sessions/${sessionId}/submit`, {
        method: 'POST',
        params: { question_id, answer, ...(response_metadata ? { response_metadata: JSON.stringify(response_metadata) } : {}) }
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
      this.request<{ items: any[]; unread_count: number }>('/api/v1/auth/notifications')
  }

  // Admin System Stats endpoint
  admin = {
    systemStats: () =>
      this.request<{
        users: {
          total: number
          active: number
          locked: number
          new_today: number
        }
        security: {
          failed_logins: number
          active_sessions: number
          blocked_ips: number
        }
        system: {
          uptime: number
          memory_usage: number
          cpu_usage: number
          disk_usage: number
        }
        audit: {
          total_logs: number
          critical_events: number
          warnings: number
        }
      }>('/api/v1/admin/system-stats')
  }

  // Admin User Management endpoints
  adminUsers = {
    list: (params: { page?: number; size?: number; search?: string; role?: string; is_active?: boolean }) =>
      this.request<{ items: any[]; total: number; page: number; pages: number }>('/api/v1/admin/users', { params }),

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

    resetPassword: (id: string, payload: { new_password: string; force_change: boolean }) =>
      this.request<{ success: boolean; message: string }>(`/api/v1/admin/users/${id}/reset-password`, {
        method: 'POST',
        body: JSON.stringify(payload)
      }),

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

  // Physician-specific endpoints
  physician = {
    // Get aggregated risk assessments (Wave 2 Performance Fix)
    // Replaces N+1 queries (1 patient list + N ai/insights) with 1 aggregated call
    riskAssessments: (patientId?: string, daysLookback?: number) => {
      const params: Record<string, string | number | boolean> = {}
      if (patientId) params['patient_id'] = patientId
      if (daysLookback) params['days_lookback'] = daysLookback

      return this.request<any>('/api/v1/physician/risk-assessments',
        Object.keys(params).length > 0 ? { params } : {}
      )
    }
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
