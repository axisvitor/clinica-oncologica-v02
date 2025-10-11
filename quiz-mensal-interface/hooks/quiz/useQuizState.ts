import { useState, useEffect } from "react"
import type { QuizSession, SingleAnswer, MultipleAnswer } from "@/types/quiz"
import { quizAPI } from "@/lib/api"
import { useSecureToken } from "@/lib/secure-token-manager"

interface UseQuizStateProps {
  session: QuizSession
  initialToken?: string
  onComplete?: () => void
}

export function useQuizState({ session, initialToken, onComplete }: UseQuizStateProps) {
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(session.current_question_index)
  const [selectedAnswer, setSelectedAnswer] = useState<SingleAnswer | MultipleAnswer | null>(null)
  const [answers, setAnswers] = useState<Map<string, SingleAnswer | MultipleAnswer>>(new Map())
  const [otherTexts, setOtherTexts] = useState<Map<string, string>>(new Map())
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isCompleted, setIsCompleted] = useState(false)

  // Use secure token management
  const { hasToken, isExpired, getToken, updateToken, clearToken } = useSecureToken(
    initialToken || session.new_token,
    session.expires_at
  )

  const currentQuestion = session.questions[currentQuestionIndex]
  const totalQuestions = session.total_questions
  const progress = ((currentQuestionIndex + 1) / totalQuestions) * 100
  const isLastQuestion = currentQuestionIndex === totalQuestions - 1

  // Reset selected answer when question changes
  useEffect(() => {
    const savedAnswer = answers.get(currentQuestion.id)
    setSelectedAnswer(savedAnswer || null)
  }, [currentQuestionIndex, currentQuestion.id, answers])

  const handleSubmitAnswer = async (
    questionId: string,
    responseValue: string | string[],
    metadata?: Record<string, any>
  ) => {
    const currentToken = getToken()
    
    if (!currentToken) {
      throw new Error("No valid token available for submission")
    }

    if (isExpired) {
      throw new Error("Token has expired. Please refresh the page.")
    }

    setIsSubmitting(true)
    try {
      const response = await quizAPI.submitAnswer(
        currentToken,
        questionId,
        responseValue,
        metadata
      )

      // Handle token rotation securely
      if (response.new_token) {
        updateToken(response.new_token, session.expires_at)
      }

      // Handle completion
      if (response.is_last_question) {
        setIsCompleted(true)
        // Clear token on completion for security
        clearToken()
        onComplete?.()
      } else {
        setCurrentQuestionIndex(prev => prev + 1)
        setSelectedAnswer(null)
      }

      return response
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
    hasToken,
    isExpired,
    setCurrentQuestionIndex,
    setSelectedAnswer,
    setAnswers,
    setOtherTexts,
    setIsSubmitting,
    setIsCompleted,
    updateToken,
    clearToken,
    handleSubmitAnswer,
  }
}
