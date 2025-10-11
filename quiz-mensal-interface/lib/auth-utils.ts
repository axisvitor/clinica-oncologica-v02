/**
 * Secure Authentication Utilities for Quiz Interface
 * Implements httpOnly cookie-based authentication with CSRF protection
 */

import { QuizSession } from "@/types/quiz"

/**
 * CSRF Token management
 */
export class CSRFTokenManager {
  private static instance: CSRFTokenManager
  private csrfToken: string | null = null

  private constructor() {}

  static getInstance(): CSRFTokenManager {
    if (!CSRFTokenManager.instance) {
      CSRFTokenManager.instance = new CSRFTokenManager()
    }
    return CSRFTokenManager.instance
  }

  /**
   * Fetch CSRF token from server
   */
  async fetchCSRFToken(): Promise<string> {
    try {
      const response = await fetch('/api/csrf-token', {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch CSRF token')
      }

      const data = await response.json()
      
      if (!data.csrfToken || typeof data.csrfToken !== 'string') {
        throw new Error('CSRF token not received from server')
      }
      
      this.csrfToken = data.csrfToken
      return data.csrfToken
    } catch (error) {
      console.error('Error fetching CSRF token:', error)
      throw new Error('Unable to initialize secure connection')
    }
  }

  /**
   * Get current CSRF token, fetch if not available
   */
  async getCSRFToken(): Promise<string> {
    if (!this.csrfToken) {
      return await this.fetchCSRFToken()
    }
    return this.csrfToken
  }

  /**
   * Clear CSRF token (for logout or session invalidation)
   */
  clearToken(): void {
    this.csrfToken = null
  }
}

/**
 * Secure Cookie Authentication Manager
 */
export class SecureCookieAuth {
  private static instance: SecureCookieAuth
  private csrfManager: CSRFTokenManager

  private constructor() {
    this.csrfManager = CSRFTokenManager.getInstance()
  }

  static getInstance(): SecureCookieAuth {
    if (!SecureCookieAuth.instance) {
      SecureCookieAuth.instance = new SecureCookieAuth()
    }
    return SecureCookieAuth.instance
  }

  /**
   * Initialize authentication session with token
   * Sends token to server to establish httpOnly cookie session
   */
  async initializeSession(token: string): Promise<QuizSession> {
    try {
      // Get CSRF token first
      const csrfToken = await this.csrfManager.getCSRFToken()

      const response = await fetch('/api/quiz/initialize-session', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify({ token })
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to initialize session" }))
        throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`)
      }

      const session = await response.json()
      return session
    } catch (error) {
      console.error('Session initialization error:', error)
      throw error
    }
  }

  /**
   * Submit quiz answer with CSRF protection
   */
  async submitAnswer(
    questionId: string,
    responseValue: string | string[],
    metadata?: Record<string, any>
  ): Promise<any> {
    try {
      // Get CSRF token
      const csrfToken = await this.csrfManager.getCSRFToken()

      // Extract other_text from metadata if present
      const { other_text, ...restMetadata } = metadata || {}

      const submitData = {
        question_id: questionId,
        response_value: responseValue,
        other_text: other_text as string | undefined,
        response_metadata: restMetadata,
      }

      const response = await fetch('/api/quiz/submit-answer', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify(submitData)
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to submit answer" }))
        throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`)
      }

      return await response.json()
    } catch (error) {
      console.error('Answer submission error:', error)
      throw error
    }
  }

  /**
   * Check if user has a valid authentication session
   */
  async checkSession(): Promise<boolean> {
    try {
      const response = await fetch('/api/quiz/session-status', {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      return response.ok
    } catch (error) {
      console.error('Session check error:', error)
      return false
    }
  }

  /**
   * Clear authentication session
   */
  async clearSession(): Promise<void> {
    try {
      await fetch('/api/quiz/logout', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      // Clear CSRF token
      this.csrfManager.clearToken()
    } catch (error) {
      console.error('Session clear error:', error)
      // Clear CSRF token even if logout fails
      this.csrfManager.clearToken()
    }
  }
}

/**
 * Token validation utilities (client-side validation for UX)
 */
export function isTokenExpired(expiresAt: string): boolean {
  return new Date(expiresAt) < new Date()
}

/**
 * Secure token extraction from URL with immediate cleanup
 */
export function extractTokenFromURL(): string | null {
  if (typeof window === 'undefined') return null

  const params = new URLSearchParams(window.location.search)
  const token = params.get('token')

  if (token) {
    // Remove token from URL immediately for security
    const url = new URL(window.location.href)
    url.searchParams.delete('token')
    window.history.replaceState({}, '', url.toString())
  }

  return token
}

/**
 * Export singleton instances for easy use
 */
export const secureCookieAuth = SecureCookieAuth.getInstance()
export const csrfTokenManager = CSRFTokenManager.getInstance()