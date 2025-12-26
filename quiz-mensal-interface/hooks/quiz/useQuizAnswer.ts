import type { SingleAnswer, MultipleAnswer, OtherAnswer } from "@/types/quiz"

export function useQuizAnswer() {
  const handleAnswerChange = (value: SingleAnswer | MultipleAnswer) => {
    return value
  }

  const handleOtherTextChange = (
    text: string,
    otherOptionValue: string,
    selectedAnswer: SingleAnswer | MultipleAnswer | null
  ): OtherAnswer | null => {
    if (typeof selectedAnswer === 'object' && selectedAnswer && 'value' in selectedAnswer) {
      return { value: otherOptionValue, customText: text } as OtherAnswer
    }
    return null
  }

  const validateAnswer = (
    selectedAnswer: SingleAnswer | MultipleAnswer | null
  ): { isValid: boolean; error?: string } => {
    if (!selectedAnswer) {
      return {
        isValid: false,
        error: "Por favor, selecione uma resposta antes de continuar."
      }
    }

    // Validate "Outra" option has text
    if (typeof selectedAnswer === 'object' && selectedAnswer && 'value' in selectedAnswer) {
      if (!selectedAnswer.customText || selectedAnswer.customText.trim() === '') {
        return {
          isValid: false,
          error: "Por favor, digite sua resposta personalizada."
        }
      }
    }

    return { isValid: true }
  }

  const prepareAnswerPayload = (selectedAnswer: SingleAnswer | MultipleAnswer | null) => {
    let answerValue: string | string[]
    let otherText: string | undefined

    if (typeof selectedAnswer === 'object' && selectedAnswer && 'value' in selectedAnswer) {
      // Single choice with "Outra" option
      answerValue = selectedAnswer.value
      otherText = selectedAnswer.customText
    } else if (typeof selectedAnswer === 'object' && selectedAnswer && 'options' in selectedAnswer) {
      // Multiple choice
      answerValue = selectedAnswer.options
      otherText = selectedAnswer.otherText
    } else {
      // Regular answer
      answerValue = selectedAnswer as string | string[]
    }

    return { answerValue, otherText }
  }

  return {
    handleAnswerChange,
    handleOtherTextChange,
    validateAnswer,
    prepareAnswerPayload,
  }
}
