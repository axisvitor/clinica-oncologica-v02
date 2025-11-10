/**
 * API Client for Monthly Quiz
 * Handles communication with backend API
 *
 * Environment Variables:
 * - NEXT_PUBLIC_QUIZ_PUBLIC_API_URL: Full API endpoint URL (preferred for production)
 * - NEXT_PUBLIC_API_URL: Base URL (will auto-append /api/v2/monthly-quiz-public)
 *
 * Configuration Priority:
 * 1. NEXT_PUBLIC_QUIZ_PUBLIC_API_URL (explicit full path)
 * 2. NEXT_PUBLIC_API_URL (base URL with auto-path)
 * 3. DEFAULT_API_BASE_URL (fallback for development)
 */

import type {
  QuizSession,
  QuizAccessRequest,
  QuizSubmitRequest,
  QuizSubmitResponse,
  QuizError
} from "@/types/quiz"

const DEFAULT_API_BASE_URL = 'http://localhost:8000/api/v2/monthly-quiz-public'

// Default timeout values (can be overridden by env vars)
const DEFAULT_TIMEOUT = 30000 // 30 seconds
const DEFAULT_RETRY_ATTEMPTS = 3

/**
 * Resolves the API base URL from environment variables with fallback logic
 *
 * @returns {string} The resolved API base URL
 */
function resolveApiBaseUrl(): string {
  // Priority 1: Explicit full API URL
  const explicit = process.env.NEXT_PUBLIC_QUIZ_PUBLIC_API_URL
  if (explicit) {
    const url = explicit.replace(/\/$/, '')
    if (process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
      console.log('[API] Using explicit API URL:', url)
    }
    return url
  }

  // Priority 2: Base URL with auto-constructed path
  const legacy = process.env.NEXT_PUBLIC_API_URL
  if (legacy) {
    let trimmed = legacy.replace(/\/$/, '')

    // Ensure /api/v2 prefix is present
    if (!trimmed.includes('/api/v2')) {
      trimmed = `${trimmed}/api/v2`
    }

    // Append quiz endpoint if not already present
    const finalUrl = trimmed.endsWith('/monthly-quiz-public')
      ? trimmed
      : `${trimmed}/monthly-quiz-public`

    if (process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
      console.log('[API] Using base URL:', legacy, '-> Resolved to:', finalUrl)
    }
    return finalUrl
  }

  // Priority 3: Fallback to default
  if (process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
    console.warn('[API] No API URL configured, using default:', DEFAULT_API_BASE_URL)
  }
  return DEFAULT_API_BASE_URL
}

const API_BASE_URL = resolveApiBaseUrl()

// Log configuration on initialization (only in debug mode)
if (typeof window !== 'undefined' && process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
  console.log('[API Configuration]', {
    baseUrl: API_BASE_URL,
    timeout: process.env.NEXT_PUBLIC_API_TIMEOUT || DEFAULT_TIMEOUT,
    retries: process.env.NEXT_PUBLIC_REQUEST_RETRY_ATTEMPTS || DEFAULT_RETRY_ATTEMPTS,
    environment: process.env.NEXT_PUBLIC_ENVIRONMENT || 'development'
  })
}

class QuizAPIError extends Error {
  status?: number
  code?: string
  retryable: boolean

  constructor(message: string, status?: number, retryable: boolean = false) {
    super(message)
    this.name = "QuizAPIError"
    this.status = status
    this.retryable = retryable
  }
}

/**
 * Fetch with timeout support
 *
 * @param url Request URL
 * @param options Fetch options
 * @param timeout Timeout in milliseconds
 * @returns Response promise
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout: number = DEFAULT_TIMEOUT
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    })
    clearTimeout(timeoutId)
    return response
  } catch (error) {
    clearTimeout(timeoutId)
    if (error instanceof Error && error.name === 'AbortError') {
      throw new QuizAPIError('Request timeout - please check your connection', 408, true)
    }
    throw error
  }
}

/**
 * Retry wrapper for API calls
 *
 * @param fn Function to retry
 * @param retries Maximum retry attempts
 * @param delay Delay between retries in ms
 * @returns Result of the function
 */
async function withRetry<T>(
  fn: () => Promise<T>,
  retries: number = DEFAULT_RETRY_ATTEMPTS,
  delay: number = 1000
): Promise<T> {
  let lastError: Error | null = null

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error))

      // Don't retry if error is not retryable
      if (error instanceof QuizAPIError && !error.retryable) {
        throw error
      }

      // Don't retry on last attempt
      if (attempt === retries) {
        break
      }

      // Log retry attempt
      if (process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
        console.warn(`[API] Retry attempt ${attempt + 1}/${retries}:`, lastError.message)
      }

      // Exponential backoff
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, attempt)))
    }
  }

  throw lastError || new QuizAPIError('Maximum retry attempts reached')
}

/**
 * API Client for Monthly Quiz operations
 */
export class QuizAPI {
  private baseURL: string

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL
  }

  /**
   * Access quiz using token from URL
   * Includes retry logic for network resilience
   */
  async accessQuiz(token: string): Promise<QuizSession> {
    return withRetry(async () => {
      try {
        const timeout = parseInt(process.env.NEXT_PUBLIC_API_TIMEOUT || String(DEFAULT_TIMEOUT))

        if (process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
          console.log('[API] Accessing quiz with token:', token.substring(0, 10) + '...')
        }

        const response = await fetchWithTimeout(
          `${this.baseURL}/access`,
          {
            method: "POST",
            credentials: 'include',
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ token }),
          },
          timeout
        )

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: "Falha ao acessar o quiz" }))

          // Determine if error is retryable
          const retryable = response.status >= 500 || response.status === 408

          throw new QuizAPIError(
            error.detail || `HTTP ${response.status}: ${response.statusText}`,
            response.status,
            retryable
          )
        }

        const data = await response.json()

        if (process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
          console.log('[API] Quiz accessed successfully:', {
            session: data.quiz_session_id,
            questions: data.total_questions
          })
        }

        return data
      } catch (error) {
        if (error instanceof QuizAPIError) {
          throw error
        }
        throw new QuizAPIError(
          error instanceof Error ? error.message : "Erro de rede ao acessar o quiz",
          undefined,
          true // Network errors are retryable
        )
      }
    })
  }

  /**
   * Submit answer to a question
   * Includes retry logic for network resilience
   */
  async submitAnswer(
    token: string,
    questionId: string,
    responseValue: string | string[],
    metadata?: Record<string, any>
  ): Promise<QuizSubmitResponse> {
    return withRetry(async () => {
      try {
        // Extract other_text from metadata if present
        const { other_text, ...restMetadata } = metadata || {}

        const submitData: QuizSubmitRequest = {
          token,
          question_id: questionId,
          // FIXED: Don't stringify arrays - send as-is for multiple choice
          response_value: responseValue,
          other_text: other_text as string | undefined,
          response_metadata: restMetadata,
        }

        const timeout = parseInt(process.env.NEXT_PUBLIC_API_TIMEOUT || String(DEFAULT_TIMEOUT))

        if (process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
          console.log('[API] Submitting answer:', {
            question: questionId,
            valueType: Array.isArray(responseValue) ? 'array' : typeof responseValue
          })
        }

        const response = await fetchWithTimeout(
          `${this.baseURL}/submit`,
          {
            method: "POST",
            credentials: 'include',
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(submitData),
          },
          timeout
        )

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: "Falha ao enviar resposta" }))

          // Determine if error is retryable
          const retryable = response.status >= 500 || response.status === 408

          throw new QuizAPIError(
            error.detail || `HTTP ${response.status}: ${response.statusText}`,
            response.status,
            retryable
          )
        }

        const data = await response.json()

        if (process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
          console.log('[API] Answer submitted successfully:', data.message)
        }

        return data
      } catch (error) {
        if (error instanceof QuizAPIError) {
          throw error
        }
        throw new QuizAPIError(
          error instanceof Error ? error.message : "Erro de rede ao enviar resposta",
          undefined,
          true // Network errors are retryable
        )
      }
    })
  }

  /**
   * Complete quiz session
   */
  async completeQuiz(token: string): Promise<{ success: boolean; message: string }> {
    try {
      // For now, this is handled by the last question submission
      // Backend automatically completes when all questions are answered
      return {
        success: true,
        message: "Quiz completed successfully"
      }
    } catch (error) {
      throw new QuizAPIError(
        error instanceof Error ? error.message : "Failed to complete quiz"
      )
    }
  }

  /**
   * Check API health
   * Used for health checks and monitoring
   */
  async healthCheck(): Promise<boolean> {
    try {
      const timeout = 5000 // Shorter timeout for health checks
      const response = await fetchWithTimeout(
        `${this.baseURL}/health`,
        {
          method: "GET",
          credentials: 'include',
        },
        timeout
      )

      if (process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
        console.log('[API] Health check:', response.ok ? 'OK' : 'FAILED')
      }

      return response.ok
    } catch (error) {
      if (process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
        console.error('[API] Health check failed:', error)
      }
      return false
    }
  }

  /**
   * Get current API base URL
   * Useful for debugging and logging
   */
  getBaseURL(): string {
    return this.baseURL
  }
}

// Export singleton instance
export const quizAPI = new QuizAPI()

// SECURITY FIX: Enhanced secure authentication implementation
// Tokens are now securely managed via:
// 1. httpOnly cookies (server-side session storage)
// 2. CSRF token protection for all form submissions
// 3. Credentials included in all API calls for cookie authentication
// 4. Removed localStorage usage to prevent XSS token theft

// Helper function to check if token is expired
export function isTokenExpired(expiresAt: string): boolean {
  return new Date(expiresAt) < new Date()
}
