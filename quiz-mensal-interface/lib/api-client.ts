/**
 * Unified API Client - Gold Master Implementation
 *
 * Robust client with Promise Singleton and Auto-Healing capabilities.
 * Prevents race conditions in React 18 Strict Mode and provides automatic
 * token refresh on 403 errors.
 *
 * Security Features:
 * - CSRF: Token kept in RAM only (XSS immune, cleared on tab close)
 * - Session: credentials: 'include' for automatic HttpOnly cookie handling
 * - Timeout: 15s with AbortController for network resilience
 *
 * Reliability Features:
 * - Promise Singleton: Prevents multiple simultaneous CSRF handshakes
 * - Auto-Healing: Automatically refreshes token on 403 and retries
 * - Exponential Backoff: Retry with increasing delays for server errors
 *
 * Architecture:
 * - Frontend is a pure consumer (no security logic)
 * - Backend (Python FastAPI) handles CORS, CSRF, Rate Limiting
 * - Cookies managed by browser (HttpOnly, Secure, SameSite)
 */

import type {
  QuizSession,
  QuizSubmitResponse
} from "@/types/quiz";

// Configuration: Environment-driven with fallback
const API_BASE_URL = (
  process.env.NEXT_PUBLIC_QUIZ_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000/api/v2"
).replace(/\/$/, "");

// Timeout configuration
const DEFAULT_TIMEOUT = 15000; // 15 seconds
const MAX_RETRIES = 2;

/**
 * Custom error class for API operations
 */
export class ApiError extends Error {
  status?: number;
  code?: string;
  retryable: boolean;

  constructor(message: string, status?: number, retryable: boolean = false) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryable = retryable;
  }
}

interface RequestOptions extends RequestInit {
  retries?: number;
}

/**
 * Unified Quiz API Client
 *
 * Implements:
 * - Stateless Client pattern (CSRF in RAM, session in HttpOnly cookies)
 * - Promise Singleton for CSRF handshake (prevents race conditions)
 * - Auto-Healing for 403 errors (automatic token refresh)
 * - Exponential backoff for server errors
 */
class QuizApiClient {
  // CSRF token kept in memory only (XSS immune, cleared on tab close)
  private csrfToken: string | null = null;

  // Promise Singleton: Prevents multiple simultaneous CSRF handshakes
  // If 10 requests call ensureCsrfToken at the same time, only ONE network call is made
  private handshakePromise: Promise<void> | null = null;

  /**
   * Ensure CSRF token is available (Promise Singleton pattern)
   *
   * This prevents race conditions in React 18 Strict Mode where
   * multiple effects might try to fetch the CSRF token simultaneously.
   *
   * @param force - Force token refresh even if one exists
   */
  private async ensureCsrfToken(force = false): Promise<void> {
    // Fast path: Token already exists
    if (this.csrfToken && !force) return;

    // Singleton: If handshake is in progress, wait for it
    if (this.handshakePromise && !force) {
      return this.handshakePromise;
    }

    // Start new handshake
    this.handshakePromise = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/csrf-token`, {
          method: "GET",
          credentials: "include",
        });

        if (!response.ok) {
          throw new Error("Falha na conexão segura.");
        }

        const data = await response.json();
        this.csrfToken = data.csrf_token;

        if (process.env.NODE_ENV === "development") {
          console.log("[Security] CSRF handshake completed");
        }
      } catch (e) {
        console.error("[API] Erro Handshake:", e);
        this.csrfToken = null;
      } finally {
        // Clear promise after completion (allows future handshakes)
        this.handshakePromise = null;
      }
    })();

    return this.handshakePromise;
  }

  /**
   * Central request wrapper with Auto-Healing and Retry logic
   *
   * Features:
   * - Automatic CSRF token injection for state-changing methods
   * - Auto-Healing: Refreshes token on 403 and retries once
   * - Exponential backoff for server errors (5xx)
   * - Network error retry with increasing delays
   */
  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const { retries = MAX_RETRIES, ...fetchOptions } = options;
    const method = options.method?.toUpperCase() || "GET";
    const isWriteMethod = ["POST", "PUT", "DELETE", "PATCH"].includes(method);

    // Ensure CSRF token before state-changing requests
    if (isWriteMethod) {
      await this.ensureCsrfToken();
    }

    // Build headers
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "Accept": "application/json",
      ...(options.headers as Record<string, string>),
    };

    // Inject CSRF token for state-changing methods
    if (this.csrfToken && isWriteMethod) {
      headers["X-CSRF-Token"] = this.csrfToken;
    }

    // Setup timeout with AbortController
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT);

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers,
        signal: controller.signal,
        credentials: "include", // CRITICAL: Enables HttpOnly cookie handling
      });

      clearTimeout(timeoutId);

      // Capture CSRF token rotation (if backend sends new token in header)
      const newCsrf = response.headers.get("X-CSRF-Token");
      if (newCsrf) {
        this.csrfToken = newCsrf;
      }

      // Handle errors
      if (!response.ok) {
        // AUTO-HEALING: If 403 (CSRF expired), refresh token and retry once
        if (response.status === 403 && retries > 0) {
          console.warn("🔄 Token expirado. Renovando...");
          this.csrfToken = null; // Clear expired token
          await this.ensureCsrfToken(true); // Force refresh
          return this.request<T>(endpoint, { ...options, retries: retries - 1 });
        }

        // Server errors (5xx): Exponential backoff retry
        if (response.status >= 500 && retries > 0) {
          const delay = 1000 * (MAX_RETRIES - retries + 1); // 1s, 2s, 3s...
          await new Promise(r => setTimeout(r, delay));
          return this.request<T>(endpoint, { ...options, retries: retries - 1 });
        }

        const errorData = await response.json().catch(() => ({}));
        const retryable = response.status >= 500 || response.status === 408;

        throw new ApiError(
          errorData.detail || errorData.message || `HTTP Error ${response.status}`,
          response.status,
          retryable
        );
      }

      // Handle 204 No Content
      if (response.status === 204) {
        return {} as T;
      }

      return await response.json() as T;

    } catch (error: unknown) {
      clearTimeout(timeoutId);

      if (error instanceof ApiError) {
        throw error;
      }

      // Timeout error
      if (error instanceof Error && error.name === "AbortError") {
        throw new ApiError(
          "Tempo limite excedido. Verifique sua conexão.",
          408,
          true
        );
      }

      // Network errors: Retry with backoff (except timeout)
      if (retries > 0 && !(error instanceof Error && error.name === "AbortError")) {
        const delay = 500 * (MAX_RETRIES - retries + 1); // 500ms, 1s, 1.5s...
        await new Promise(r => setTimeout(r, delay));
        return this.request<T>(endpoint, { ...options, retries: retries - 1 });
      }

      throw new ApiError(
        error instanceof Error ? error.message : "Erro de rede",
        undefined,
        true
      );
    }
  }

  /**
   * Clear security state (logout)
   */
  clearSecurityState(): void {
    this.csrfToken = null;
  }

  // ============================================================
  // Business Methods
  // ============================================================

  /**
   * Access quiz using URL token
   * Exchanges URL token for secure session (HttpOnly cookie)
   * 
   * OPTIMIZATION: Pre-starts CSRF handshake before preparing request body
   * This reduces latency by running CSRF fetch and body prep in parallel.
   */
  async accessQuiz(tokenLink: string): Promise<QuizSession> {
    // Start CSRF handshake early (non-blocking)
    // This runs in parallel while we prepare the request
    const csrfPromise = this.ensureCsrfToken();

    // Prepare request body (can happen while CSRF is fetching)
    const body = JSON.stringify({ token: tokenLink });

    // Wait for CSRF to complete before making the POST
    await csrfPromise;

    // Note: API_BASE_URL already includes /monthly-quiz-public prefix
    return this.request<QuizSession>("/access", {
      method: "POST",
      body,
    });
  }

  /**
   * Recover active session via HttpOnly cookie (for F5/Refresh)
   * No token needed - session is authenticated via cookie
   */
  async recoverSession(): Promise<QuizSession | null> {
    try {
      // Note: API_BASE_URL already includes /monthly-quiz-public prefix
      return await this.request<QuizSession>("/session/active", {
        method: "GET",
      });
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 404)) {
        return null; // No active session
      }
      throw error;
    }
  }

  /**
   * Get current session status (legacy method for compatibility)
   */
  async getSessionStatus(): Promise<QuizSession | null> {
    return this.recoverSession();
  }

  /**
   * Submit answer to a question
   */
  async submitAnswer(
    questionId: string,
    responseValue: string | string[],
    metadata?: Record<string, unknown>
  ): Promise<QuizSubmitResponse> {
    // Note: API_BASE_URL already includes /monthly-quiz-public prefix
    return this.request<QuizSubmitResponse>("/submit", {
      method: "POST",
      body: JSON.stringify({
        question_id: questionId,
        response_value: responseValue,
        response_metadata: metadata,
      }),
    });
  }

  /**
   * Logout from quiz session
   */
  async logout(): Promise<void> {
    try {
      // Note: API_BASE_URL already includes /monthly-quiz-public prefix
      await this.request<void>("/logout", {
        method: "POST",
      });
    } finally {
      this.clearSecurityState();
    }
  }

  /**
   * Health check
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.request<{ status: string }>("/health");
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get current API base URL (for debugging)
   */
  getBaseURL(): string {
    return API_BASE_URL;
  }
}

// Singleton: Single instance for the entire application
export const api = new QuizApiClient();

// Re-export types for convenience
export type { QuizSession, QuizSubmitResponse };
