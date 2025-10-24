import { useState, useEffect } from "react"
import type { QuizSession, SingleAnswer, MultipleAnswer } from "@/types/quiz"

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
        onComplete?.()
      } else {
        setCurrentQuestionIndex(prev => prev + 1)
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
  }
}
