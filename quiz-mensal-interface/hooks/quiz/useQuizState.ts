import { useState, useEffect } from "react"
import type { QuizSession, SingleAnswer, MultipleAnswer } from "@/types/quiz"
import { secureCookieAuth } from "@/lib/auth-utils"

interface UseQuizStateProps {
  session: QuizSession
  onComplete?: () => void
}

export function useQuizState({ session, onComplete }: UseQuizStateProps) {
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(session.current_question_index)
  const [selectedAnswer, setSelectedAnswer] = useState<SingleAnswer | MultipleAnswer | null>(null)
  const [answers, setAnswers] = useState<Map<string, SingleAnswer | MultipleAnswer>>(new Map())
  const [otherTexts, setOtherTexts] = useState<Map<string, string>>(new Map())
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isCompleted, setIsCompleted] = useState(false)

  // No token management needed - handled by secure cookies

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
      const response = await secureCookieAuth.submitAnswer(
        questionId,
        responseValue,
        metadata
      )

      // Handle completion
      if (response.is_last_question) {
        setIsCompleted(true)
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
    setCurrentQuestionIndex,
    setSelectedAnswer,
    setAnswers,
    setOtherTexts,
    setIsSubmitting,
    setIsCompleted,
    handleSubmitAnswer,
  }
}
