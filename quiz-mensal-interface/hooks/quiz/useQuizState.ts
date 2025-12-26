import { useState, useEffect, useCallback } from "react"
import type { QuizSession, SingleAnswer, MultipleAnswer } from "@/types/quiz"
import { saveQuizProgress, loadQuizProgress, clearQuizProgress, type QuizProgress } from "@/lib/quiz-progress-storage"

interface UseQuizStateProps {
  session: QuizSession
  initialToken?: string
  onComplete?: () => void
  resumeFromSaved?: boolean
}

export function useQuizState({ session, initialToken, onComplete, resumeFromSaved = false }: UseQuizStateProps) {
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(session.current_question_index)
  const [selectedAnswer, setSelectedAnswer] = useState<SingleAnswer | MultipleAnswer | null>(null)
  const [answers, setAnswers] = useState<Map<string, SingleAnswer | MultipleAnswer>>(new Map())
  const [otherTexts, setOtherTexts] = useState<Map<string, string>>(new Map())
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isCompleted, setIsCompleted] = useState(false)

  const currentQuestion = session.questions[currentQuestionIndex || 0]
  const totalQuestions = session.questions.length
  const progress = (((currentQuestionIndex || 0) + 1) / totalQuestions) * 100
  const isLastQuestion = (currentQuestionIndex || 0) === totalQuestions - 1

  // Load saved progress on mount if resuming
  useEffect(() => {
    if (resumeFromSaved) {
      const savedProgress = loadQuizProgress(session.quiz_session_id)
      if (savedProgress) {
        // Restore answers
        const restoredAnswers = new Map(Object.entries(savedProgress.answers))
        setAnswers(restoredAnswers)

        // Restore other texts
        const restoredOtherTexts = new Map(Object.entries(savedProgress.otherTexts || {}))
        setOtherTexts(restoredOtherTexts)

        // Restore question index
        setCurrentQuestionIndex(savedProgress.currentQuestionIndex)

        console.log(`Resumed quiz from question ${savedProgress.currentQuestionIndex + 1}`)
      }
    }
  }, [resumeFromSaved, session.quiz_session_id])

  // Save progress to localStorage whenever state changes
  const saveProgress = useCallback(() => {
    const progressData: QuizProgress = {
      sessionId: session.quiz_session_id,
      currentQuestionIndex: currentQuestionIndex || 0,
      answers: Object.fromEntries(answers),
      otherTexts: Object.fromEntries(otherTexts),
      lastSaved: Date.now(),
      patientName: session.patient_name,
      templateName: session.template_name,
      totalQuestions: session.questions.length
    }
    saveQuizProgress(progressData)
  }, [session, currentQuestionIndex, answers, otherTexts])

  // Auto-save on state changes (debounced)
  useEffect(() => {
    if (answers.size > 0 && !isCompleted) {
      const timeoutId = setTimeout(() => {
        saveProgress()
      }, 500) // Debounce 500ms

      return () => clearTimeout(timeoutId)
    }
  }, [answers, currentQuestionIndex, saveProgress, isCompleted])

  // Reset selected answer when question changes
  useEffect(() => {
    const savedAnswer = answers.get(currentQuestion.id)
    setSelectedAnswer(savedAnswer || null)
  }, [currentQuestionIndex, currentQuestion.id, answers])

  const handleSubmitAnswer = async (
    questionId: string,
    responseValue: string | string[],
    metadata?: Record<string, unknown>
  ) => {
    setIsSubmitting(true)
    try {
      // SECURITY FIX: Use API route with httpOnly cookie authentication
      // Get CSRF token
      const csrfResponse = await fetch('/api/csrf-token')
      const { csrfToken } = await csrfResponse.json()

      // Submit answer via API route (cookie sent automatically)
      const response = await fetch('/api/quiz/submit-answer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify({
          question_id: questionId,
          response_value: responseValue,
          response_metadata: metadata
        }),
        credentials: 'include' // Important: include cookies
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to submit answer')
      }

      const result = await response.json()

      // Handle completion
      if (result.is_last_question) {
        setIsCompleted(true)
        // Clear progress on completion
        clearQuizProgress(session.quiz_session_id)
        onComplete?.()
      } else {
        setCurrentQuestionIndex(prev => (prev || 0) + 1)
        setSelectedAnswer(null)
      }

      return result
    } catch (error) {
      console.error('Error submitting answer:', error)
      throw error
    } finally {
      setIsSubmitting(false)
    }
  }

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
    setCurrentQuestionIndex,
    setSelectedAnswer,
    setAnswers,
    setOtherTexts,
    setIsSubmitting,
    setIsCompleted,
    handleSubmitAnswer,
    saveProgress,
  }
}
