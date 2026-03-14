/**
 * Core API Client - Base class for HTTP requests
 *
 * This module provides the foundational HTTP client with:
 * - Request/response handling
 * - Error handling with retry logic
 * - CSRF token management
 * - Authentication token management
 * - Rate limiting and timeout handling
 */

import { createLogger } from '../logger'
import { environment } from '../environment'

const logger = createLogger('ApiClient')

/**
 * API Response interface
 */
export interface ApiResponse<T> {
  data: T
  message?: string
  timestamp: string
}

/**
 * Paginated response interface
 */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page?: number
  size?: number
  pages?: number
  has_more?: boolean
  next_cursor?: string | null
  data?: T[]
}

/**
 * API Error class with enhanced user messaging
 */
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
      stack: environment.isDevelopment ? this.stack : undefined,
    }
  }
}

/**
 * Request options interface
 */
export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean>
  retries?: number
  timeout?: number
}

/**
 * Core API Client class
 */
export class ApiClientCore {
  private baseURL: string
  private authToken: string | null = null
  private initialized: boolean = false
  private csrfToken: string | null = null
  private csrfTokenPromise: Promise<void> | null = null

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  /**
   * Set base URL for API requests
   */
  setBaseURL(url: string): void {
    if (!url) {
      logger.warn('Attempted to set empty base URL')
      return
    }

    // Remove trailing slashes for consistency
    url = url.replace(/\/+$/, '')

    // SECURITY: Auto-upgrade HTTP to HTTPS in production to prevent mixed-content errors
    if (url.startsWith('http://') && typeof window !== 'undefined') {
      const isProduction =
        window.location.protocol === 'https:' &&
        window.location.hostname !== 'localhost' &&
        !window.location.hostname.startsWith('127.0.0.1') &&
        !window.location.hostname.startsWith('192.168.')

      if (isProduction) {
        logger.warn('⚠️ SECURITY: Auto-upgrading HTTP to HTTPS in production:', url)
        url = url.replace('http://', 'https://')
        logger.log('✓ Upgraded URL:', url)
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
   * Check if client is initialized
   */
  isInitialized(): boolean {
    return this.initialized
  }

  /**
   * Set compatibility auth token.
   * Shared HTTP requests remain cookie-backed and do not emit this value.
   */
  setAuthToken(token: string | null): void {
    this.authToken = token
    if (token !== null) {
      logger.log('Compatibility auth token cached; shared HTTP requests remain cookie-backed')
    } else {
      logger.log('Compatibility auth token cleared')
    }
  }

  /**
   * Clear authentication token (alias for setAuthToken(null))
   * Used when leaving compatibility flows in favor of cookie-backed session auth.
   */
  clearAuthToken(): void {
    logger.debug('[ApiClient] Clearing compatibility auth token - shared requests stay cookie-only')
    this.setAuthToken(null)
  }

  /**
   * Get current auth token
   */
  getAuthToken(): string | null {
    return this.authToken
  }

  /**
   * Build headers for direct fetch calls.
   * Official first-party requests rely on cookies + CSRF, so no legacy session headers are emitted.
   */
  getSessionHeaders(): Record<string, string> {
    return {}
  }

  /**
   * Fetch CSRF token from backend
   * Non-blocking: returns gracefully on failure to prevent app initialization blocking
   */
  async fetchCsrfToken(): Promise<void> {
    if (this.csrfTokenPromise) {
      logger.debug('[ApiClient] CSRF token fetch already in progress, waiting...')
      return this.csrfTokenPromise
    }

    this.csrfTokenPromise = (async () => {
      // Timeout for CSRF fetch (30s) to handle slow backend startup
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 30000)

      try {
        logger.debug('[ApiClient] Initiating CSRF token fetch...')
        const response = await fetch(`${this.baseURL}/api/v2/auth/csrf-token`, {
          credentials: 'include',
          signal: controller.signal,
        })

        if (response.ok) {
          const data = await response.json()
          let csrfToken = data.csrf_token

          // Handle array format from backend
          if (Array.isArray(csrfToken) && csrfToken.length >= 2) {
            csrfToken = csrfToken[1]
            logger.debug('[ApiClient] CSRF token extracted from array format')
          } else if (typeof csrfToken !== 'string') {
            logger.warn('[ApiClient] Unexpected CSRF token format:', typeof csrfToken)
            // Don't throw - just skip setting token
            return
          }

          this.csrfToken = csrfToken
          logger.debug('[ApiClient] CSRF token fetched successfully')
        } else {
          logger.warn('[ApiClient] Failed to fetch CSRF token:', response.status)
          // Don't throw - CSRF token is optional for GET requests
        }
      } catch (error) {
        // Log but don't throw - CSRF failure should not block app initialization
        if (error instanceof Error && error.name === 'AbortError') {
          logger.warn('[ApiClient] CSRF token fetch timed out (30s)')
        } else {
          logger.warn('[ApiClient] Error fetching CSRF token (non-critical):', error)
        }
      } finally {
        clearTimeout(timeoutId)
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
   * Set session token
   */
  setSessionToken(session: { access_token?: string } | null): void {
    if (session?.access_token) {
      this.setAuthToken(session.access_token)
    } else {
      this.setAuthToken(null)
    }
  }

  /**
   * Build URL with query parameters
   */
  private buildUrl(endpoint: string, params?: Record<string, string | number | boolean>): string {
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

  /**
   * Detect CSRF validation errors in API responses
   */
  private isCsrfError(data: unknown): boolean {
    if (!data || typeof data !== 'object') {
      return false
    }

    const record = data as Record<string, unknown>
    const errorValue = record['error']
    const errorCode = typeof errorValue === 'string' ? errorValue : undefined
    const errorMessage =
      typeof errorValue === 'object' && errorValue !== null && 'message' in errorValue
        ? String((errorValue as { message?: unknown }).message || '')
        : undefined
    const detail = typeof record['detail'] === 'string' ? record['detail'] : undefined
    const message = typeof record['message'] === 'string' ? record['message'] : undefined

    const combined = [errorCode, errorMessage, detail, message]
      .filter((value): value is string => typeof value === 'string' && value.length > 0)
      .join(' ')
      .toLowerCase()

    return combined.includes('csrf')
  }

  /**
   * Check if error should be retried
   */
  private shouldRetry(error: unknown, attempt: number): boolean {
    if (attempt >= 3) return false

    if (error instanceof ApiError && [401, 403].includes(error.status)) {
      return false
    }

    if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
      return [408, 429].includes(error.status)
    }

    if (error instanceof TypeError) return true

    if (error instanceof DOMException && error.name === 'AbortError') return true

    if (error instanceof ApiError) {
      return [408, 429, 500, 502, 503, 504].includes(error.status)
    }

    return false
  }

  /**
   * Sleep for retry backoff
   */
  private async sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  /**
   * Make HTTP request with retry logic
   */
  async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { params, retries = 0, timeout = 60000, ...fetchOptions } = options
    const url = this.buildUrl(endpoint, params)

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    Object.assign(headers, (fetchOptions.headers as Record<string, string>) || {})

    // Add CSRF token for state-changing methods
    const method = (fetchOptions.method || 'GET').toUpperCase()
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
      if (!this.csrfToken) {
        // Lazily fetch CSRF token if missing
        await this.fetchCsrfToken()
      }
      if (this.csrfToken) {
        headers['X-CSRF-Token'] = this.csrfToken
      }
    }

    // Create abort controller for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers,
        credentials: 'include',
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({
          detail: response.statusText,
        }))

        if (response.status === 403 && this.isCsrfError(errorData) && retries < 1) {
          logger.warn(
            '[ApiClient] CSRF validation failed, refreshing token and retrying request...'
          )
          await this.fetchCsrfToken()
          return this.request(endpoint, { ...options, retries: retries + 1 })
        }

        const error = new ApiError(
          response.status,
          errorData,
          errorData.detail ||
            errorData.error?.message ||
            errorData.error?.details ||
            `HTTP ${response.status}`,
          errorData.user_message || errorData.error?.message
        )

        if (this.shouldRetry(error, retries)) {
          await this.sleep(Math.pow(2, retries) * 1000)
          return this.request(endpoint, { ...options, retries: retries + 1 })
        }

        throw error
      }

      // Handle empty responses (204 No Content, 205 Reset Content)
      if (response.status === 204 || response.status === 205) {
        return undefined as T
      }

      // Check if response has content before parsing
      const contentLength = response.headers.get('content-length')
      if (contentLength === '0') {
        return undefined as T
      }

      const data = await response.json()
      return data as T
    } catch (error) {
      clearTimeout(timeoutId)

      if (error instanceof ApiError) {
        throw error
      }

      const apiError = new ApiError(
        0,
        error,
        error instanceof Error ? error.message : 'Network error'
      )

      if (this.shouldRetry(apiError, retries)) {
        await this.sleep(Math.pow(2, retries) * 1000)
        return this.request(endpoint, { ...options, retries: retries + 1 })
      }

      throw apiError
    }
  }

  /**
   * GET request
   */
  async get<T>(endpoint: string, params?: Record<string, string | number | boolean>): Promise<T> {
    const options: RequestOptions = { method: 'GET' }
    if (params) {
      ;(options as RequestOptions & { params: Record<string, string | number | boolean> }).params =
        params
    }
    return this.request<T>(endpoint, options)
  }

  /**
   * POST request
   */
  async post<T, TData = unknown>(
    endpoint: string,
    data?: TData,
    params?: Record<string, string | number | boolean>
  ): Promise<T> {
    const options: RequestOptions = { method: 'POST' }
    if (data !== undefined) {
      ;(options as RequestOptions & { body: string }).body = JSON.stringify(data)
    }
    if (params) {
      ;(options as RequestOptions & { params: Record<string, string | number | boolean> }).params =
        params
    }
    return this.request<T>(endpoint, options)
  }

  /**
   * PUT request
   */
  async put<T, TData = unknown>(
    endpoint: string,
    data?: TData,
    params?: Record<string, string | number | boolean>
  ): Promise<T> {
    const options: RequestOptions = { method: 'PUT' }
    if (data !== undefined) {
      ;(options as RequestOptions & { body: string }).body = JSON.stringify(data)
    }
    if (params) {
      ;(options as RequestOptions & { params: Record<string, string | number | boolean> }).params =
        params
    }
    return this.request<T>(endpoint, options)
  }

  /**
   * DELETE request
   */
  async delete<T>(
    endpoint: string,
    params?: Record<string, string | number | boolean>
  ): Promise<T> {
    const options: RequestOptions = { method: 'DELETE' }
    if (params) {
      ;(options as RequestOptions & { params: Record<string, string | number | boolean> }).params =
        params
    }
    return this.request<T>(endpoint, options)
  }

  /**
   * PATCH request
   */
  async patch<T, TData = unknown>(
    endpoint: string,
    data?: TData,
    params?: Record<string, string | number | boolean>
  ): Promise<T> {
    const options: RequestOptions = { method: 'PATCH' }
    if (data !== undefined) {
      ;(options as RequestOptions & { body: string }).body = JSON.stringify(data)
    }
    if (params) {
      ;(options as RequestOptions & { params: Record<string, string | number | boolean> }).params =
        params
    }
    return this.request<T>(endpoint, options)
  }
}

// Export types
// Types already exported above; avoid duplicate export declarations
// ApiError is already exported as a class above
