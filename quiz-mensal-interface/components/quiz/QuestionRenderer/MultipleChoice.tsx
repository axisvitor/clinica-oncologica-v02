import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import type { QuizQuestion, SingleAnswer, MultipleAnswer } from '@/types/quiz'
import { memo } from 'react'

interface MultipleChoiceProps {
  question: QuizQuestion
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  otherText: string
  onAnswerChange: (value: SingleAnswer | MultipleAnswer) => void
  onOtherTextChange: (text: string, otherOptionValue: string) => void
}

export const MultipleChoice = memo(function MultipleChoice({
  question,
  selectedAnswer,
  onAnswerChange,
}: MultipleChoiceProps) {
  // Extract multiple answers from state
  let multipleAnswers: string[] = []
  if (selectedAnswer) {
    if (Array.isArray(selectedAnswer)) {
      multipleAnswers = selectedAnswer
    } else if (typeof selectedAnswer === 'object' && 'options' in selectedAnswer) {
      multipleAnswers = selectedAnswer.options
    }
  }

  return (
    <div className="space-y-3">
      {question.options?.map((option, index) => {
        const optionValue = typeof option === 'string' ? option : option.value
        const optionText = typeof option === 'string' ? option : option.text
        const optionId = `question-${question.id}-option-${index}`
        const isChecked = multipleAnswers.includes(optionValue)
        return (
          <div
            key={typeof option === 'string' ? index : option.id}
            className={`flex items-center space-x-3 p-4 rounded-xl border-2 transition-all ${
              isChecked
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/50 hover:bg-primary/5'
            }`}
          >
            <Checkbox
              id={optionId}
              checked={isChecked}
              onCheckedChange={(checked) => {
                let newAnswers: string[]
                if (checked) {
                  newAnswers = [...multipleAnswers, optionValue]
                } else {
                  newAnswers = multipleAnswers.filter((a) => a !== optionValue)
                }
                onAnswerChange(newAnswers.length > 0 ? newAnswers : [])
              }}
            />
            <Label htmlFor={optionId} className="flex-1 cursor-pointer font-medium">
              {optionText}
            </Label>
          </div>
        )
      })}
    </div>
  )
})
