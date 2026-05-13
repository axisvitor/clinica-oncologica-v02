import { useState, useEffect, useCallback } from 'react'
import type { QuizSession, SingleAnswer, MultipleAnswer, QuizQuestion } from '@/types/quiz'
import { clearQuizProgress } from '@/lib/quiz-progress-storage'
import { api } from '@/lib/api-client'

interface UseQuizStateProps {
  session: QuizSession
  initialToken?: string
  onComplete?: () => void
}

export function useQuizState({ session, onComplete }: UseQuizStateProps) {
  // Initialize with 0 fallback to prevent undefined -> 0 transitions that trigger useEffect
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(
    session.current_question_index ?? 0,
  )
  const [selectedAnswer, setSelectedAnswer] = useState<SingleAnswer | MultipleAnswer | null>(null)
  const [answers, setAnswers] = useState<Map<string, SingleAnswer | MultipleAnswer>>(new Map())
  const [otherTexts, setOtherTexts] = useState<Map<string, string>>(new Map())
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isCompleted, setIsCompleted] = useState(false)
  const [navigationDirection, setNavigationDirection] = useState<'forward' | 'backward'>('forward')

  // Guard: Check for empty or invalid questions array
  const hasValidQuestions = Array.isArray(session.questions) && session.questions.length > 0
  const safeIndex = hasValidQuestions
    ? Math.min(Math.max(0, currentQuestionIndex), session.questions.length - 1)
    : 0

  // Use safe access with fallback
  const fallbackQuestion: QuizQuestion = {
    id: '',
    text: 'Quiz não disponível',
    type: 'text',
    options: [],
  }

  const currentQuestion = hasValidQuestions ? session.questions[safeIndex] : fallbackQuestion
  const totalQuestions = hasValidQuestions ? session.questions.length : 0
  const progress = totalQuestions > 0 ? ((safeIndex + 1) / totalQuestions) * 100 : 0
  const isLastQuestion = hasValidQuestions && safeIndex === totalQuestions - 1

  // Remove any legacy client-side quiz progress on mount/session changes.
  useEffect(() => {
    clearQuizProgress()
  }, [session.quiz_session_id])

  // Reset selected answer when question changes (NOT when answers changes)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const savedAnswer = answers.get(currentQuestion.id)
    setSelectedAnswer(savedAnswer || null)
  }, [currentQuestionIndex, currentQuestion.id]) // Removed 'answers' - it was causing re-renders on every keystroke

  const handleSubmitAnswer = async (
    questionId: string,
    responseValue: string | string[],
    metadata?: Record<string, unknown>,
  ) => {
    setIsSubmitting(true)
    try {
      // Use Unified API Client for submission
      // It handles CSRF, session cookies, and error retry automatically
      const result = await api.submitAnswer(questionId, responseValue, metadata)

      // Handle completion
      if (result.is_last_question) {
        setIsCompleted(true)
        // Clear legacy progress on completion
        clearQuizProgress()
        onComplete?.()
      } else {
        setCurrentQuestionIndex((prev) => (prev || 0) + 1)
        setSelectedAnswer(null)
      }

      return result
    } catch (error) {
      clearQuizProgress()
      throw error
    } finally {
      setIsSubmitting(false)
    }
  }

  // Navigation helpers with direction tracking
  const goToNextQuestion = useCallback(() => {
    setNavigationDirection('forward')
    setCurrentQuestionIndex((prev) => Math.min(prev + 1, totalQuestions - 1))
    setSelectedAnswer(null)
  }, [totalQuestions])

  const goToPreviousQuestion = useCallback(() => {
    setNavigationDirection('backward')
    setCurrentQuestionIndex((prev) => Math.max(prev - 1, 0))
  }, [])

  return {
    currentQuestionIndex,
    selectedAnswer,
    answers,
    otherTexts,
    isSubmitting,
    isCompleted,
    currentQuestion,
    totalQuestions,
    progress,
    isLastQuestion,
    hasValidQuestions,
    navigationDirection,
    setCurrentQuestionIndex,
    setSelectedAnswer,
    setAnswers,
    setOtherTexts,
    setIsSubmitting,
    setIsCompleted,
    handleSubmitAnswer,
    goToNextQuestion,
    goToPreviousQuestion,
  }
}
