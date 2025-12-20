/**
 * Quiz API Client - Dedicated Client for Monthly Quiz Module
 *
 * ARCHITECTURE:
 * - Frontend → Python backend DIRECT connection (no Next.js proxy)
 * - CSRF token stored ONLY in RAM (class private field, immune to XSS)
 * - HttpOnly cookies for session authentication (automatic via credentials: 'include')
 * - 15s timeout with AbortController on all requests
 * - Singleton pattern for efficient resource usage
 *
 * SECURITY:
 * - No localStorage/sessionStorage usage (prevents XSS token theft)
 * - CSRF token fetched from /api/v2/auth/csrf-token
 * - Double Submit Cookie pattern (token in header + cookie)
 * - All requests use credentials: 'include' for automatic cookie handling
 *
 * @module lib/api-client
 */

import { createLogger } from '../src/lib/logger';

const logger = createLogger('QuizApiClient');

/**
 * API Error with retry information
 */
export class QuizApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
    public readonly data: unknown,
    public readonly retryable: boolean = false
  ) {
    super(`Quiz API Error ${status}: ${statusText}`);
    this.name = 'QuizApiError';
  }

  toJSON() {
    return {
      name: this.name,
      status: this.status,
      statusText: this.statusText,
      data: this.data,
      retryable: this.retryable,
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * Quiz Session Interface
 */
export interface QuizSession {
  id: string;
  patient_id: string;
  quiz_template_id: string;
  session_token: string;
  status: 'pending' | 'in_progress' | 'completed' | 'expired';
  started_at: string | null;
  completed_at: string | null;
  expires_at: string;
  current_question_index: number;
  total_questions: number;
  responses: QuizResponse[];
}

/**
 * Quiz Response Interface
 */
export interface QuizResponse {
  question_id: string;
  answer: string | string[];
  answered_at: string;
}

/**
 * Quiz Link Interface
 */
export interface QuizLink {
  id: string;
  patient_id: string;
  quiz_template_id: string;
  session_token: string;
  public_url: string;
  expires_at: string;
  is_active: boolean;
  created_at: string;
}

/**
 * Request Options
 */
export interface RequestOptions {
  timeout?: number;
  retries?: number;
}

/**
 * Quiz API Client - Singleton Class
 *
 * Manages direct connection to Python backend with:
 * - CSRF token in RAM only (never persisted to storage)
 * - HttpOnly cookie-based authentication
 * - 15s request timeout
 * - Automatic retry on network errors
 */
export class QuizApiClient {
  private static instance: QuizApiClient | null = null;

  // SECURITY: CSRF token stored ONLY in RAM (immune to XSS)
  private csrfToken: string | null = null;

  // RESILIENCE: Promise Singleton Lock to prevent race conditions
  // Only ONE handshake can be in flight at a time
  private csrfFetchPromise: Promise<void> | null = null;

  // Configuration
  private readonly baseURL: string;
  private readonly defaultTimeout = 15000; // 15 seconds

  private constructor() {
    // Get backend URL from environment
    this.baseURL = this.getBackendURL();
    logger.log('[QuizApiClient] Initialized with backend URL:', this.baseURL);
  }

  /**
   * Get singleton instance
   */
  public static getInstance(): QuizApiClient {
    if (!QuizApiClient.instance) {
      QuizApiClient.instance = new QuizApiClient();
    }
    return QuizApiClient.instance;
  }

  /**
   * Get backend URL from environment variables
   */
  private getBackendURL(): string {
    // Priority: VITE_API_BASE_URL > VITE_API_ENDPOINT_URL > fallback
    const baseUrl = import.meta.env['VITE_API_BASE_URL'];
    const endpointUrl = import.meta.env['VITE_API_ENDPOINT_URL'];

    if (baseUrl) {
      logger.debug('[QuizApiClient] Using VITE_API_BASE_URL:', baseUrl);
      return baseUrl;
    }

    if (endpointUrl) {
      // Extract base URL from endpoint URL (remove /api/v2)
      const cleanUrl = endpointUrl.replace(/\/api\/v2$/, '');
      logger.debug('[QuizApiClient] Using VITE_API_ENDPOINT_URL (cleaned):', cleanUrl);
      return cleanUrl;
    }

    // Fallback for development
    const fallback = 'http://localhost:8000';
    logger.warn('[QuizApiClient] No API URL found, using fallback:', fallback);
    return fallback;
  }

  /**
   * Ensure security handshake is complete
   *
   * RESILIENCE FEATURES:
   * - Promise Singleton Lock: Only ONE handshake can be in flight at a time
   * - Prevents race conditions when multiple requests are made concurrently
   * - Concurrent requests gracefully wait for in-flight handshake to complete
   *
   * Fetches CSRF token from Python backend and stores it in RAM.
   * Non-blocking: returns gracefully on failure to prevent app blocking.
   *
   * SECURITY: Token stored ONLY in private field (never localStorage/sessionStorage)
   */
  public async ensureSecurityHandshake(): Promise<void> {
    // If token already fetched, return immediately
    if (this.csrfToken) {
      logger.debug('[QuizApiClient] CSRF token already available');
      return;
    }

    // RESILIENCE: If fetch is in progress, wait for it (Promise Singleton Lock)
    // This prevents multiple concurrent handshakes from racing
    if (this.csrfFetchPromise) {
      logger.debug('[QuizApiClient] CSRF token fetch in progress, waiting for completion...');
      return this.csrfFetchPromise;
    }

    // Start new fetch with Promise Singleton Lock
    this.csrfFetchPromise = (async () => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5s timeout for CSRF

      try {
        logger.debug('[QuizApiClient] Fetching CSRF token from backend...');

        const response = await fetch(`${this.baseURL}/api/v2/auth/csrf-token`, {
          method: 'GET',
          credentials: 'include', // Include HttpOnly cookies
          signal: controller.signal,
          headers: {
            'Accept': 'application/json'
          }
        });

        if (!response.ok) {
          logger.warn('[QuizApiClient] Failed to fetch CSRF token:', response.status);
          return;
        }

        const data = await response.json();
        let token = data.csrf_token;

        // Handle array format from backend (legacy compatibility)
        if (Array.isArray(token) && token.length >= 2) {
          token = token[1];
          logger.debug('[QuizApiClient] Extracted CSRF token from array format');
        }

        if (typeof token !== 'string' || !token) {
          logger.warn('[QuizApiClient] Invalid CSRF token format:', typeof token);
          return;
        }

        // SECURITY: Store token ONLY in RAM (private field)
        this.csrfToken = token;
        logger.log('[QuizApiClient] CSRF token fetched and stored in RAM');

      } catch (error) {
        // Log but don't throw - CSRF failure should not block app
        if (error instanceof Error && error.name === 'AbortError') {
          logger.warn('[QuizApiClient] CSRF token fetch timed out (5s)');
        } else {
          logger.warn('[QuizApiClient] Error fetching CSRF token (non-critical):', error);
        }
      } finally {
        clearTimeout(timeoutId);
        // Release the lock after completion
        this.csrfFetchPromise = null;
      }
    })();

    return this.csrfFetchPromise;
  }

  /**
   * Make HTTP request with timeout and retry logic
   *
   * RESILIENCE FEATURES:
   * - Auto-Healing: Automatically retries 403 errors with fresh CSRF token
   * - Invalidates stale CSRF token and fetches new one on 403
   * - Prevents CSRF token expiration from breaking user experience
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    requestOptions: RequestOptions = {}
  ): Promise<T> {
    const { timeout = this.defaultTimeout, retries = 0 } = requestOptions;
    const url = `${this.baseURL}${endpoint}`;

    // Prepare headers
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(options.headers as Record<string, string> || {})
    };

    // Add CSRF token for state-changing methods
    const method = (options.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method) && this.csrfToken) {
      headers['X-CSRF-Token'] = this.csrfToken;
    }

    // Create AbortController for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      logger.debug(`[QuizApiClient] ${method} ${endpoint}`);

      const response = await fetch(url, {
        ...options,
        headers,
        credentials: 'include', // CRITICAL: Include HttpOnly cookies
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({
          detail: response.statusText
        }));

        // AUTO-HEALING: On 403 Forbidden, invalidate CSRF token and retry with fresh one
        if (response.status === 403 && retries === 0) {
          logger.warn('[QuizApiClient] 403 Forbidden - CSRF token may be stale, auto-healing...');

          // Invalidate current token
          this.csrfToken = null;

          // Fetch fresh token
          await this.ensureSecurityHandshake();

          // Retry request with fresh token (increment retries to prevent infinite loop)
          logger.debug('[QuizApiClient] Retrying with fresh CSRF token...');
          return this.request(endpoint, options, { timeout, retries: retries + 1 });
        }

        const isRetryable = this.shouldRetry(response.status, retries);

        throw new QuizApiError(
          response.status,
          response.statusText,
          errorData,
          isRetryable
        );
      }

      // Handle empty responses
      if (response.status === 204 || response.status === 205) {
        return undefined as T;
      }

      const contentLength = response.headers.get('content-length');
      if (contentLength === '0') {
        return undefined as T;
      }

      const data = await response.json();
      return data as T;

    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof QuizApiError) {
        // Retry if retryable and retries remaining
        if (error.retryable && retries < 2) {
          const delay = Math.pow(2, retries) * 1000; // Exponential backoff
          logger.debug(`[QuizApiClient] Retrying after ${delay}ms...`);
          await this.sleep(delay);
          return this.request(endpoint, options, { timeout, retries: retries + 1 });
        }
        throw error;
      }

      // Network error
      const networkError = new QuizApiError(
        0,
        'Network Error',
        error instanceof Error ? error.message : 'Unknown error',
        retries < 2 // Retry network errors
      );

      if (networkError.retryable && retries < 2) {
        const delay = Math.pow(2, retries) * 1000;
        logger.debug(`[QuizApiClient] Retrying network error after ${delay}ms...`);
        await this.sleep(delay);
        return this.request(endpoint, options, { timeout, retries: retries + 1 });
      }

      throw networkError;
    }
  }

  /**
   * Check if error should be retried
   */
  private shouldRetry(status: number, currentRetries: number): boolean {
    if (currentRetries >= 2) return false;

    // Don't retry client errors (except timeout and rate limiting)
    if (status >= 400 && status < 500) {
      return status === 408 || status === 429;
    }

    // Retry server errors
    return status >= 500;
  }

  /**
   * Sleep utility for retry backoff
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // =============================================================================
  // Public API Methods
  // =============================================================================

  /**
   * Get quiz session by token
   */
  public async getSession(sessionToken: string): Promise<QuizSession> {
    return this.request<QuizSession>(
      `/api/v2/quiz-extensions/monthly/public/${sessionToken}`
    );
  }

  /**
   * Submit quiz response
   */
  public async submitResponse(
    sessionToken: string,
    questionId: string,
    answer: string | string[]
  ): Promise<QuizSession> {
    return this.request<QuizSession>(
      `/api/v2/quiz-extensions/monthly/public/${sessionToken}/respond`,
      {
        method: 'POST',
        body: JSON.stringify({
          question_id: questionId,
          answer
        })
      }
    );
  }

  /**
   * Complete quiz session
   */
  public async completeSession(sessionToken: string): Promise<QuizSession> {
    return this.request<QuizSession>(
      `/api/v2/quiz-extensions/monthly/public/${sessionToken}/complete`,
      {
        method: 'POST'
      }
    );
  }

  /**
   * Verify session token is valid
   */
  public async verifySession(sessionToken: string): Promise<boolean> {
    try {
      await this.getSession(sessionToken);
      return true;
    } catch (error) {
      if (error instanceof QuizApiError && error.status === 404) {
        return false;
      }
      throw error;
    }
  }

  /**
   * Get quiz link information
   */
  public async getQuizLink(sessionToken: string): Promise<QuizLink> {
    return this.request<QuizLink>(
      `/api/v2/monthly-quiz-public/monthly/public/${sessionToken}`
    );
  }
}

// Export singleton instance
export const quizApiClient = QuizApiClient.getInstance();
