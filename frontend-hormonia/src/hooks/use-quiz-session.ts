/**
 * useQuizSession - React Hook for Quiz Session Management
 *
 * ARCHITECTURE:
 * - Uses useSearchParams for session token from URL
 * - useRef to prevent double execution (React 18 StrictMode)
 * - Integration with QuizApiClient (direct Python backend connection)
 * - Automatic CSRF handshake on mount
 *
 * SECURITY:
 * - Session token from URL query parameter
 * - CSRF token managed by QuizApiClient (RAM only)
 * - HttpOnly cookies for authentication (automatic)
 *
 * RESILIENCE:
 * - Session recovery via cookie on page refresh (F5)
 * - Checks for existing session cookie on mount
 * - Restores quiz state from cookie if available
 * - Seamless user experience across page reloads
 *
 * @module hooks/use-quiz-session
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  quizApiClient,
  QuizSession,
  QuizApiError
} from '../../lib/api-client';
import { createLogger } from '../lib/logger';

const logger = createLogger('useQuizSession');

/**
 * RESILIENCE: Cookie-based session recovery
 * Cookie name for storing session token across page reloads
 */
const SESSION_COOKIE_NAME = 'quiz_session_token';

/**
 * Get session token from cookie
 *
 * RESILIENCE: Enables session recovery on page refresh (F5)
 * Reads session token from HttpOnly-safe cookie
 *
 * @returns Session token from cookie or null
 */
function getSessionTokenFromCookie(): string | null {
  try {
    const cookies = document.cookie.split(';');
    const sessionCookie = cookies.find(c => c.trim().startsWith(`${SESSION_COOKIE_NAME}=`));

    if (sessionCookie) {
      const token = sessionCookie.split('=')[1]?.trim();
      logger.debug('[useQuizSession] Found session token in cookie:', token?.substring(0, 8) + '...');
      return token || null;
    }

    logger.debug('[useQuizSession] No session token found in cookie');
    return null;
  } catch (error) {
    logger.warn('[useQuizSession] Error reading session cookie:', error);
    return null;
  }
}

/**
 * Save session token to cookie
 *
 * RESILIENCE: Persists session token for recovery on page refresh
 *
 * @param token - Session token to save
 * @param expiresAt - ISO timestamp when session expires
 */
function saveSessionTokenToCookie(token: string, expiresAt?: string): void {
  try {
    // Calculate expiration time
    let expires = '';
    if (expiresAt) {
      const expiryDate = new Date(expiresAt);
      expires = `; expires=${expiryDate.toUTCString()}`;
    } else {
      // Default: 24 hours
      const expiryDate = new Date();
      expiryDate.setTime(expiryDate.getTime() + (24 * 60 * 60 * 1000));
      expires = `; expires=${expiryDate.toUTCString()}`;
    }

    // Set cookie with secure flags
    document.cookie = `${SESSION_COOKIE_NAME}=${token}${expires}; path=/; SameSite=Strict`;
    logger.debug('[useQuizSession] Session token saved to cookie');
  } catch (error) {
    logger.warn('[useQuizSession] Error saving session cookie:', error);
  }
}

/**
 * Clear session token from cookie
 */
function clearSessionTokenFromCookie(): void {
  try {
    document.cookie = `${SESSION_COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Strict`;
    logger.debug('[useQuizSession] Session token cleared from cookie');
  } catch (error) {
    logger.warn('[useQuizSession] Error clearing session cookie:', error);
  }
}

/**
 * Hook state interface
 */
export interface UseQuizSessionState {
  // Session data
  session: QuizSession | null;
  sessionToken: string | null;

  // Loading states
  loading: boolean;
  initializing: boolean;
  submitting: boolean;

  // Error state
  error: QuizApiError | null;

  // Session status
  isValid: boolean;
  isExpired: boolean;
  isCompleted: boolean;

  // Actions
  submitResponse: (questionId: string, answer: string | string[]) => Promise<void>;
  completeSession: () => Promise<void>;
  refreshSession: () => Promise<void>;
}

/**
 * Hook options
 */
export interface UseQuizSessionOptions {
  // Auto-fetch session on mount
  autoFetch?: boolean;

  // Polling interval in milliseconds (0 = disabled)
  pollingInterval?: number;

  // Callback on session loaded
  onSessionLoaded?: (session: QuizSession) => void;

  // Callback on error
  onError?: (error: QuizApiError) => void;
}

/**
 * useQuizSession Hook
 *
 * Manages quiz session lifecycle with React state and QuizApiClient.
 *
 * @example
 * ```tsx
 * const { session, loading, submitResponse } = useQuizSession({
 *   autoFetch: true,
 *   onSessionLoaded: (session) => console.log('Session loaded:', session.id)
 * });
 *
 * const handleAnswer = async (questionId: string, answer: string) => {
 *   await submitResponse(questionId, answer);
 * };
 * ```
 */
export function useQuizSession(options: UseQuizSessionOptions = {}): UseQuizSessionState {
  const {
    autoFetch = true,
    pollingInterval = 0,
    onSessionLoaded,
    onError
  } = options;

  // Get session token from URL
  const [searchParams] = useSearchParams();
  const sessionToken = searchParams.get('token');

  // State
  const [session, setSession] = useState<QuizSession | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [initializing, setInitializing] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<QuizApiError | null>(null);

  // useRef to prevent double execution in React 18 StrictMode
  const hasInitialized = useRef<boolean>(false);
  const isMounted = useRef<boolean>(true);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const resolveApiError = useCallback((err: unknown): QuizApiError => (
    err instanceof QuizApiError
      ? err
      : new QuizApiError(0, 'Unknown Error', err)
  ), []);

  const reportMutationError = useCallback((message: string, err: unknown): QuizApiError | null => {
    if (!isMounted.current) return null;

    logger.error(message, err);
    const apiError = resolveApiError(err);
    setError(apiError);
    onError?.(apiError);
    return apiError;
  }, [onError, resolveApiError]);

  const finishSubmitting = useCallback(() => {
    if (isMounted.current) {
      setSubmitting(false);
    }
  }, []);

  /**
   * Fetch session from backend
   *
   * RESILIENCE: Saves session token to cookie for recovery on page refresh
   */
  const fetchSession = useCallback(async (token: string) => {
    if (!token) {
      logger.warn('[useQuizSession] No session token provided');
      setError(new QuizApiError(400, 'Bad Request', 'Session token is required'));
      return;
    }

    try {
      setLoading(true);
      setError(null);

      logger.debug('[useQuizSession] Fetching session for token:', token);

      const sessionData = await quizApiClient.getSession(token);

      if (!isMounted.current) return;

      setSession(sessionData);
      logger.log('[useQuizSession] Session loaded:', sessionData.id);

      // RESILIENCE: Save session token to cookie for recovery on page refresh
      saveSessionTokenToCookie(token, sessionData.expires_at);

      // Call onSessionLoaded callback
      if (onSessionLoaded) {
        onSessionLoaded(sessionData);
      }

    } catch (err) {
      if (!isMounted.current) return;

      logger.error('[useQuizSession] Error fetching session:', err);

      const apiError = err instanceof QuizApiError
        ? err
        : new QuizApiError(0, 'Unknown Error', err);

      setError(apiError);

      // RESILIENCE: Clear cookie on session fetch error
      if (apiError.status === 404 || apiError.status === 401) {
        clearSessionTokenFromCookie();
      }

      // Call onError callback
      if (onError) {
        onError(apiError);
      }
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  }, [onSessionLoaded, onError]);

  /**
   * Initialize session and CSRF handshake
   *
   * RESILIENCE: Implements session recovery via cookie
   * - Checks for existing session token in cookie on mount
   * - Falls back to URL parameter if cookie is not available
   * - Enables seamless user experience across page reloads (F5)
   */
  const initialize = useCallback(async () => {
    // Prevent double execution in React 18 StrictMode
    if (hasInitialized.current) {
      logger.debug('[useQuizSession] Already initialized, skipping');
      return;
    }

    hasInitialized.current = true;
    logger.log('[useQuizSession] Initializing...');

    try {
      // Step 1: Ensure CSRF token is fetched
      await quizApiClient.ensureSecurityHandshake();

      // Step 2: RESILIENCE - Try to recover session from cookie
      let tokenToUse = sessionToken;

      if (!tokenToUse) {
        const cookieToken = getSessionTokenFromCookie();
        if (cookieToken) {
          logger.log('[useQuizSession] Session recovered from cookie (page refresh detected)');
          tokenToUse = cookieToken;
        }
      }

      // Step 3: Fetch session if autoFetch enabled and token exists
      if (autoFetch && tokenToUse) {
        await fetchSession(tokenToUse);
      }

    } catch (err) {
      logger.error('[useQuizSession] Initialization error:', err);
    } finally {
      if (isMounted.current) {
        setInitializing(false);
      }
    }
  }, [autoFetch, sessionToken, fetchSession]);

  /**
   * Submit response to current question
   */
  const submitResponse = useCallback(async (
    questionId: string,
    answer: string | string[]
  ): Promise<void> => {
    if (!sessionToken) {
      throw new QuizApiError(400, 'Bad Request', 'Session token is required');
    }

    if (!session) {
      throw new QuizApiError(400, 'Bad Request', 'Session not loaded');
    }

    try {
      setSubmitting(true);
      setError(null);

      logger.debug('[useQuizSession] Submitting response:', { questionId, answer });

      const updatedSession = await quizApiClient.submitResponse(
        sessionToken,
        questionId,
        answer
      );

      if (!isMounted.current) return;

      setSession(updatedSession);
      logger.log('[useQuizSession] Response submitted successfully');

    } catch (err) {
      const apiError = reportMutationError('[useQuizSession] Error submitting response:', err);
      if (apiError) {
        throw apiError;
      }
    } finally {
      finishSubmitting();
    }
  }, [sessionToken, session, reportMutationError, finishSubmitting]);

  /**
   * Complete quiz session
   *
   * RESILIENCE: Clears session cookie when quiz is completed
   */
  const completeSession = useCallback(async (): Promise<void> => {
    if (!sessionToken) {
      throw new QuizApiError(400, 'Bad Request', 'Session token is required');
    }

    if (!session) {
      throw new QuizApiError(400, 'Bad Request', 'Session not loaded');
    }

    try {
      setSubmitting(true);
      setError(null);

      logger.debug('[useQuizSession] Completing session');

      const completedSession = await quizApiClient.completeSession(sessionToken);

      if (!isMounted.current) return;

      setSession(completedSession);
      logger.log('[useQuizSession] Session completed successfully');

      // RESILIENCE: Clear cookie when session is completed
      clearSessionTokenFromCookie();

    } catch (err) {
      const apiError = reportMutationError('[useQuizSession] Error completing session:', err);
      if (apiError) {
        throw apiError;
      }
    } finally {
      finishSubmitting();
    }
  }, [sessionToken, session, reportMutationError, finishSubmitting]);

  /**
   * Refresh session data
   */
  const refreshSession = useCallback(async (): Promise<void> => {
    if (!sessionToken) {
      logger.warn('[useQuizSession] Cannot refresh: no session token');
      return;
    }

    await fetchSession(sessionToken);
  }, [sessionToken, fetchSession]);

  /**
   * Initialize on mount
   */
  useEffect(() => {
    isMounted.current = true;
    initialize();

    return () => {
      isMounted.current = false;
      hasInitialized.current = false;
    };
  }, [initialize]);

  /**
   * Setup polling if enabled
   */
  useEffect(() => {
    if (!pollingInterval || pollingInterval <= 0 || !sessionToken) {
      return;
    }

    logger.debug(`[useQuizSession] Starting polling every ${pollingInterval}ms`);

    pollingIntervalRef.current = setInterval(() => {
      fetchSession(sessionToken);
    }, pollingInterval);

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
        logger.debug('[useQuizSession] Polling stopped');
      }
    };
  }, [pollingInterval, sessionToken, fetchSession]);

  // Derived state
  const isValid = !!session && session.status !== 'expired';
  const isExpired = session?.status === 'expired';
  const isCompleted = session?.status === 'completed';

  return {
    // Session data
    session,
    sessionToken,

    // Loading states
    loading,
    initializing,
    submitting,

    // Error state
    error,

    // Session status
    isValid,
    isExpired,
    isCompleted,

    // Actions
    submitResponse,
    completeSession,
    refreshSession
  };
}

// Export types
export type { QuizApiError };
