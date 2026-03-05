import type { SingleAnswer, MultipleAnswer, OtherAnswer } from '@/types/quiz'

export function useQuizAnswer() {
  const isOtherAnswer = (value: SingleAnswer | MultipleAnswer | null): value is OtherAnswer => {
    return Boolean(value && typeof value === 'object' && 'value' in value && 'customText' in value)
  }

  const isMultipleSelection = (
    value: SingleAnswer | MultipleAnswer | null,
  ): value is { options: string[]; otherText?: string } => {
    return Boolean(value && typeof value === 'object' && 'options' in value)
  }

  const handleAnswerChange = (value: SingleAnswer | MultipleAnswer) => {
    return value
  }

  const handleOtherTextChange = (
    text: string,
    otherOptionValue: string,
    selectedAnswer: SingleAnswer | MultipleAnswer | null,
  ): OtherAnswer => {
    // Always return a valid OtherAnswer object to preserve selection
    // Extract customText from existing answer if it's an OtherAnswer
    const existingCustomText = isOtherAnswer(selectedAnswer) ? selectedAnswer.customText : ''

    return { value: otherOptionValue, customText: text || existingCustomText }
  }

  const validateAnswer = (
    selectedAnswer: SingleAnswer | MultipleAnswer | null,
  ): { isValid: boolean; error?: string } => {
    if (!selectedAnswer) {
      return {
        isValid: false,
        error: 'Por favor, selecione uma resposta antes de continuar.',
      }
    }

    // Validate "Outra" option has text
    if (typeof selectedAnswer === 'object' && selectedAnswer && 'value' in selectedAnswer) {
      if (!selectedAnswer.customText || selectedAnswer.customText.trim() === '') {
        return {
          isValid: false,
          error: 'Por favor, digite sua resposta personalizada.',
        }
      }
    }

    return { isValid: true }
  }

  const prepareAnswerPayload = (selectedAnswer: SingleAnswer | MultipleAnswer | null) => {
    if (selectedAnswer === null) {
      return { answerValue: '' }
    }

    let answerValue: string | string[]
    let otherText: string | undefined

    if (isOtherAnswer(selectedAnswer)) {
      // Single choice with "Outra" option
      answerValue = selectedAnswer.value
      otherText = selectedAnswer.customText
    } else if (isMultipleSelection(selectedAnswer)) {
      // Multiple choice
      answerValue = selectedAnswer.options
      otherText = selectedAnswer.otherText
    } else {
      // Regular answer
      answerValue = selectedAnswer
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
