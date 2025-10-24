import { useToast } from "@/hooks/use-toast"
import { quizAPI } from "@/lib/api"
import type { SingleAnswer, MultipleAnswer } from "@/types/quiz"

interface UseQuizNavigationProps {
  currentToken: string
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

      const response = await quizAPI.submitAnswer(
        props.currentToken,
        props.currentQuestionId,
        answerValue,
        { question_index: props.currentQuestionIndex, other_text: otherText }
      )

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
