/**
 * Unified API Client - Stateless Security Pattern
 *
 * Direct connection to Python Backend with in-memory CSRF protection.
 * Eliminates "Split-Brain Security" by letting the backend handle all security.
 *
 * Security Features:
 * - CSRF: Token fetched from Python, kept in RAM only (XSS immune)
 * - Session: credentials: 'include' for automatic HttpOnly cookie handling
 * - Timeout: 15s with AbortController for network resilience
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

/**
 * Unified Quiz API Client
 *
 * Implements Stateless Client pattern:
 * - CSRF token in memory (cleared on page close)
 * - Session via HttpOnly cookies (browser-managed)
 * - Direct connection to Python backend
 */
class QuizApiClient {
  // CSRF token kept in memory only (XSS immune, cleared on tab close)
  private csrfToken: string | null = null;

  /**
   * Central request wrapper
   * Handles Headers, CSRF injection, Timeout, and Error handling
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

    // 1. Build headers
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "Accept": "application/json",
      ...(options.headers as Record<string, string>),
    };

    // Inject CSRF only for state-changing methods (POST, PUT, DELETE, PATCH)
    const method = options.method?.toUpperCase() || "GET";
    if (this.csrfToken && ["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
      headers["X-CSRF-Token"] = this.csrfToken;
    }

    // 2. Setup timeout with AbortController
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT);

    try {
      const response = await fetch(url, {
        ...options,
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

      // 3. Error handling
      if (!response.ok) {
        // Clear CSRF token on 403 to force refresh
        if (response.status === 403) {
          this.csrfToken = null;
        }

        const errorData = await response.json().catch(() => ({}));
        const retryable = response.status >= 500 || response.status === 408;

        throw new ApiError(
          errorData.detail || errorData.message || `HTTP Error ${response.status}`,
          response.status,
          retryable
        );
      }

      return await response.json() as T;

    } catch (error: unknown) {
      clearTimeout(timeoutId);

      if (error instanceof ApiError) {
        throw error;
      }

      if (error instanceof Error && error.name === "AbortError") {
        throw new ApiError(
          "Tempo limite excedido. Verifique sua conexão.",
          408,
          true
        );
      }

      throw new ApiError(
        error instanceof Error ? error.message : "Erro de rede",
        undefined,
        true
      );
    }
  }

  /**
   * Security Handshake
   * Fetches CSRF token from Python backend before any POST/PUT/DELETE
   */
  async ensureSecurityHandshake(): Promise<void> {
    if (this.csrfToken) return;

    try {
      // Fetch CSRF token from Python backend
      const data = await this.request<{ csrf_token: string }>(
        "/auth/csrf-token",
        { method: "GET" }
      );
      this.csrfToken = data.csrf_token;

      if (process.env.NODE_ENV === "development") {
        console.log("[Security] CSRF handshake completed");
      }
    } catch (e) {
      console.warn("[Security] CSRF handshake failed:", e);
      // Continue without CSRF - some endpoints may not require it
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
   */
  async accessQuiz(tokenLink: string): Promise<QuizSession> {
    await this.ensureSecurityHandshake();

    return this.request<QuizSession>("/monthly-quiz-public/access", {
      method: "POST",
      body: JSON.stringify({ token: tokenLink }),
    });
  }

  /**
   * Submit answer to a question
   */
  async submitAnswer(
    questionId: string,
    responseValue: string | string[],
    metadata?: Record<string, unknown>
  ): Promise<QuizSubmitResponse> {
    return this.request<QuizSubmitResponse>("/monthly-quiz-public/submit", {
      method: "POST",
      body: JSON.stringify({
        question_id: questionId,
        response_value: responseValue,
        response_metadata: metadata,
      }),
    });
  }

  /**
   * Get current session status
   */
  async getSessionStatus(): Promise<QuizSession | null> {
    try {
      return await this.request<QuizSession>("/monthly-quiz-public/session");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Logout from quiz session
   */
  async logout(): Promise<void> {
    try {
      await this.request<void>("/monthly-quiz-public/logout", {
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
