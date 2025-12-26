import { useToast } from "@/hooks/use-toast"
import type { SingleAnswer, MultipleAnswer } from "@/types/quiz"

interface UseQuizNavigationProps {
  currentToken?: string // Deprecated: token handled by httpOnly cookies
  currentQuestionIndex: number
  currentQuestionId: string
  isLastQuestion: boolean
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  validateAnswer: (answer: SingleAnswer | MultipleAnswer | null) => { isValid: boolean; error?: string }
  prepareAnswerPayload: (answer: SingleAnswer | MultipleAnswer | null) => { answerValue: string | string[]; otherText?: string }
  onTokenUpdate?: (token: string) => void // Optional: not needed with httpOnly cookies
  onAnswerSaved: (questionId: string, answer: SingleAnswer | MultipleAnswer) => void
  onNextQuestion: () => void
  onComplete: () => void
  setIsSubmitting: (value: boolean) => void
}

export function useQuizNavigation(props: UseQuizNavigationProps) {
  const { toast } = useToast()

  const handlePreviousQuestion = (setCurrentQuestionIndex: (fn: (prev: number) => number) => void) => {
    if (props.currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1)
    }
  }

  const handleSubmitAnswer = async () => {
    const validation = props.validateAnswer(props.selectedAnswer)

    if (!validation.isValid) {
      toast({
        title: validation.error?.includes("resposta") ? "Resposta obrigatória" : "Texto obrigatório",
        description: validation.error,
        variant: "destructive"
      })
      return
    }

    props.setIsSubmitting(true)

    try {
      const { answerValue, otherText } = props.prepareAnswerPayload(props.selectedAnswer)

      // SECURITY FIX: Use API route with httpOnly cookie authentication
      // Get CSRF token
      const csrfResponse = await fetch('/api/csrf-token')
      const { csrfToken } = await csrfResponse.json()

      // Submit answer via API route (cookie sent automatically)
      const answerResponse = await fetch('/api/quiz/submit-answer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify({
          question_id: props.currentQuestionId,
          response_value: answerValue,
          response_metadata: { question_index: props.currentQuestionIndex, other_text: otherText }
        }),
        credentials: 'include' // Important: include cookies
      })

      if (!answerResponse.ok) {
        const errorData = await answerResponse.json()
        throw new Error(errorData.error || 'Failed to submit answer')
      }

      const response = await answerResponse.json()

      // SECURITY: Token rotation handled by httpOnly cookies
      // No need to update token in JavaScript anymore
      if (response.new_token && props.onTokenUpdate) {
        props.onTokenUpdate(response.new_token)
      }

      // Save answer locally
      if (props.selectedAnswer) {
        props.onAnswerSaved(props.currentQuestionId, props.selectedAnswer)
      }

      toast({
        title: "Resposta enviada!",
        description: props.isLastQuestion
          ? "Questionário concluído com sucesso!"
          : "Sua resposta foi registrada.",
      })

      // Move to next question or complete
      if (props.isLastQuestion) {
        props.onComplete()
      } else {
        props.onNextQuestion()
      }

    } catch (error) {
      console.error("Error submitting answer:", error)
      toast({
        title: "Erro ao enviar resposta",
        description: error instanceof Error ? error.message : "Tente novamente em alguns instantes.",
        variant: "destructive"
      })
    } finally {
      props.setIsSubmitting(false)
    }
  }

  return {
    handlePreviousQuestion,
    handleSubmitAnswer,
  }
}
