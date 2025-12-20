/**
 * Quiz Session Hook - Stateless Session Management
 *
 * Handles quiz session initialization from URL token.
 * Uses the unified API client for direct Python backend connection.
 *
 * Features:
 * - Extracts token from URL searchParams
 * - Exchanges URL token for secure session (HttpOnly cookie)
 * - Cleans URL after successful authentication (security)
 * - Prevents double execution in React Strict Mode
 */

"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api-client";
import type { QuizSession } from "@/types/quiz";

export interface UseQuizSessionResult {
  /** Current quiz session data */
  session: QuizSession | null;
  /** Loading state during initialization */
  isLoading: boolean;
  /** Error message if initialization failed */
  error: string | null;
  /** Retry function for failed initialization */
  retry: () => void;
  /** Submit answer function */
  submitAnswer: (
    questionId: string,
    value: string | string[],
    metadata?: Record<string, unknown>
  ) => Promise<void>;
  /** Current submission state */
  isSubmitting: boolean;
}

/**
 * Hook for managing quiz session lifecycle
 *
 * @example
 * ```tsx
 * function QuizPage() {
 *   const { session, isLoading, error, submitAnswer } = useQuizSession();
 *
 *   if (isLoading) return <Loading />;
 *   if (error) return <Error message={error} />;
 *   if (!session) return <AccessDenied />;
 *
 *   return <Quiz data={session} onSubmit={submitAnswer} />;
 * }
 * ```
 */
export function useQuizSession(): UseQuizSessionResult {
  const [session, setSession] = useState<QuizSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ref to prevent double execution in React Strict Mode
  const initialized = useRef(false);
  const searchParams = useSearchParams();

  /**
   * Initialize session from URL token
   */
  const initSession = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const urlToken = searchParams.get("token");

      if (urlToken) {
        // 1. Exchange URL token for secure session (HttpOnly cookie)
        const data = await api.accessQuiz(urlToken);
        setSession(data);

        // 2. Clean URL for security (prevents sharing authenticated links)
        if (typeof window !== "undefined") {
          const newUrl = new URL(window.location.href);
          newUrl.searchParams.delete("token");
          window.history.replaceState({}, "", newUrl.toString());
        }

        if (process.env.NODE_ENV === "development") {
          console.log("[Session] Quiz session initialized:", {
            sessionId: data.quiz_session_id,
            totalQuestions: data.questions?.length ?? 0,
          });
        }
      } else {
        // No token in URL - check if existing session is valid
        const existingSession = await api.getSessionStatus();
        if (existingSession) {
          setSession(existingSession);
        } else {
          setError("Token de acesso não encontrado. Use o link enviado.");
        }
      }
    } catch (err) {
      console.error("[Session] Initialization error:", err);

      if (err instanceof ApiError) {
        switch (err.status) {
          case 401:
          case 403:
            setError("Link de acesso inválido ou expirado.");
            break;
          case 404:
            setError("Quiz não encontrado.");
            break;
          case 408:
            setError("Tempo limite excedido. Verifique sua conexão.");
            break;
          case 429:
            setError("Muitas tentativas. Aguarde alguns minutos.");
            break;
          default:
            setError(err.message || "Erro ao acessar o quiz.");
        }
      } else {
        setError("Erro de conexão. Verifique sua internet.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [searchParams]);

  // Initialize on mount (with Strict Mode protection)
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    initSession();
  }, [initSession]);

  /**
   * Retry initialization
   */
  const retry = useCallback(() => {
    initialized.current = false;
    initSession();
  }, [initSession]);

  /**
   * Submit answer to current question
   */
  const submitAnswer = useCallback(
    async (
      questionId: string,
      value: string | string[],
      metadata?: Record<string, unknown>
    ) => {
      setIsSubmitting(true);

      try {
        const response = await api.submitAnswer(questionId, value, metadata);

        // Update session with new state from response
        if (response.next_question) {
          setSession((prev) =>
            prev
              ? {
                  ...prev,
                  current_question: response.next_question,
                  current_question_index: (prev.current_question_index || 0) + 1,
                }
              : null
          );
        } else if (response.is_last_question) {
          // Quiz completed
          setSession((prev) =>
            prev
              ? {
                  ...prev,
                  status: "completed",
                }
              : null
          );
        }

        if (process.env.NODE_ENV === "development") {
          console.log("[Session] Answer submitted:", {
            questionId,
            isComplete: response.is_last_question,
          });
        }
      } catch (err) {
        console.error("[Session] Submit error:", err);
        throw err; // Re-throw to let UI handle the error
      } finally {
        setIsSubmitting(false);
      }
    },
    []
  );

  return {
    session,
    isLoading,
    error,
    retry,
    submitAnswer,
    isSubmitting,
  };
}

export default useQuizSession;
