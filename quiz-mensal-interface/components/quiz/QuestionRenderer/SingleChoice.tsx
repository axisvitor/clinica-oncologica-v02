import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import type { QuizQuestion, SingleAnswer, MultipleAnswer } from "@/types/quiz"
import { memo } from "react"

interface SingleChoiceProps {
  question: QuizQuestion
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  otherText: string
  onAnswerChange: (value: SingleAnswer | MultipleAnswer) => void
  onOtherTextChange: (text: string, otherOptionValue: string) => void
}

export const SingleChoice = memo(function SingleChoice({
  question,
  selectedAnswer,
  onAnswerChange,
}: SingleChoiceProps) {
  // Get current value - handle both string and object types
  const singleValue = typeof selectedAnswer === 'object' && selectedAnswer && 'value' in selectedAnswer
    ? selectedAnswer.value
    : (selectedAnswer as string || "")

  return (
    <div className="space-y-3">
      <RadioGroup
        value={singleValue}
        onValueChange={(value) => onAnswerChange(value)}
        className="space-y-3"
      >
        {question.options?.map((option, index) => {
          const optionValue = typeof option === 'string' ? option : option.value
          const optionText = typeof option === 'string' ? option : option.text
          const optionId = `question-${question.id}-option-${index}`
          return (
            <div
              key={typeof option === 'string' ? index : option.id}
              className={`flex items-center space-x-3 p-4 rounded-xl border-2 transition-all cursor-pointer ${singleValue === optionValue
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/50 hover:bg-primary/5'
                }`}
            >
              <RadioGroupItem value={optionValue} id={optionId} />
              <Label
                htmlFor={optionId}
                className="flex-1 cursor-pointer font-medium"
              >
                {optionText}
              </Label>
            </div>
          )
        })}
      </RadioGroup>
    </div>
  )
})
